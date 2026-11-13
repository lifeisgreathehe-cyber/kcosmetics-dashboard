"""입체 분석용 외부 자료 수집기 (네트워크).

- 구글 뉴스 RSS: 업종 뉴스, 회사 뉴스(언론사 폭넓게), 대시보드 밖 연관 기업 뉴스. 키 필요 없음.
- 네이버 블로그: NAVER_CLIENT_ID/SECRET(네이버 개발자센터 무료 키)이 있으면 공식 검색 API,
  없으면 블로그 섹션 검색 응답을 읽는다.
- 네이버 데이터랩 검색어 트렌드: 같은 키가 있을 때만 (주간 검색량 지수).
모든 함수는 실패해도 예외 대신 빈 값을 돌려준다 (하루 수집이 실패해도 이전 자료를 유지하려고).
"""
import datetime as dt
import email.utils
import html
import json
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
KST = dt.timezone(dt.timedelta(hours=9))
STATS = {"gnews": [0, 0], "blog": [0, 0], "datalab": [0, 0]}  # [성공, 실패]


def _get(url, headers=None, data=None, timeout=12):
    h = {"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _clean(s):
    s = html.unescape(re.sub(r"<[^>]+>", "", s or ""))
    return re.sub(r"\s+", " ", s).strip()


def gnews(query, days=90, n=60):
    """구글 뉴스 RSS 검색 → [{date, title, office, url}] 최신순."""
    q = f"{query} when:{days}d"
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q, "hl": "ko", "gl": "KR", "ceid": "KR:ko"})
    for attempt in range(2):
        try:
            root = ET.fromstring(_get(url))
            out = []
            for it in root.iter("item"):
                title = _clean(it.findtext("title"))
                src = it.find("source")
                office = _clean(src.text) if src is not None else ""
                if office and title.endswith(" - " + office):
                    title = title[: -len(office) - 3]
                d = it.findtext("pubDate")
                try:
                    date = email.utils.parsedate_to_datetime(d).astimezone(KST).date().isoformat()
                except Exception:
                    date = ""
                out.append({"date": date, "title": title, "office": office, "url": it.findtext("link") or ""})
            STATS["gnews"][0] += 1
            out.sort(key=lambda x: x["date"], reverse=True)
            return out[:n]
        except Exception as e:
            err = e
            time.sleep(3)
    STATS["gnews"][1] += 1
    print("gnews 실패", query, str(err)[:120])
    return []


def _naver_keys():
    return os.environ.get("NAVER_CLIENT_ID"), os.environ.get("NAVER_CLIENT_SECRET")


def blogs(query, n=8):
    """블로그 글 → ([{date, title, office(블로그명), url, summary}], 전체 글 수 or None)."""
    cid, sec = _naver_keys()
    try:
        if cid and sec:
            url = "https://openapi.naver.com/v1/search/blog.json?" + urllib.parse.urlencode({"query": query, "display": 20, "sort": "date"})
            d = json.loads(_get(url, {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": sec}))
            out = [{"date": f"{x['postdate'][:4]}-{x['postdate'][4:6]}-{x['postdate'][6:8]}", "title": _clean(x["title"]),
                    "office": _clean(x.get("bloggername")), "url": x["link"], "summary": _clean(x.get("description"))[:200]}
                   for x in d.get("items", [])]
            total = d.get("total")
        else:
            url = "https://section.blog.naver.com/ajax/SearchList.naver?" + urllib.parse.urlencode(
                {"countPerPage": 7, "currentPage": 1, "endDate": "", "keyword": query, "orderBy": "recentdate", "startDate": "", "type": "post"})
            raw = _get(url, {"Referer": "https://section.blog.naver.com/Search/Post.naver?keyword=" + urllib.parse.quote(query)})
            raw = raw[raw.find("{"):]
            d = json.loads(raw).get("result") or {}
            out = []
            for x in d.get("searchList") or []:
                ts = x.get("addDate")
                date = dt.datetime.fromtimestamp(ts / 1000, KST).date().isoformat() if isinstance(ts, (int, float)) else ""
                out.append({"date": date, "title": _clean(x.get("noTagTitle") or x.get("title")), "office": _clean(x.get("blogName")),
                            "url": x.get("postUrl") or "", "summary": _clean(x.get("contents"))[:200]})
            total = d.get("totalCount")
        STATS["blog"][0] += 1
        return out[:n], total
    except Exception as e:
        STATS["blog"][1] += 1
        if STATS["blog"][1] <= 3:
            print("블로그 실패", query, str(e)[:120])
        return [], None


def datalab(groups, weeks=26):
    """네이버 데이터랩 주간 검색량 지수. groups: {이름: [키워드..]} (최대 5개) → {이름: [[주, 지수]...]}"""
    cid, sec = _naver_keys()
    if not (cid and sec) or not groups:
        return {}
    end = dt.date.today()
    start = end - dt.timedelta(weeks=weeks)
    body = {"startDate": start.isoformat(), "endDate": end.isoformat(), "timeUnit": "week",
            "keywordGroups": [{"groupName": k[:20], "keywords": v[:5]} for k, v in list(groups.items())[:5]]}
    try:
        d = json.loads(_get("https://openapi.naver.com/v1/datalab/search",
                            {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": sec, "Content-Type": "application/json"},
                            data=json.dumps(body).encode()))
        STATS["datalab"][0] += 1
        res = {}
        for r in d.get("results", []):
            name = next((k for k in groups if k[:20] == r["title"]), r["title"])
            res[name] = [[x["period"], round(x["ratio"], 2)] for x in r.get("data", [])]
        return res
    except Exception as e:
        STATS["datalab"][1] += 1
        print("데이터랩 실패", str(e)[:120])
        return {}
