#!/usr/bin/env python3
"""변곡점 해설용 데이터 수집 (GitHub Actions에서 실행 — 클라우드 세션에선 해외 사이트가 막혀 있음).

1) 거시 월별 지표 → docs/shared/macro.json
   KOSPI·KOSDAQ 월말 지수(네이버 차트, 실패 시 야후), 원/달러·미국 10년 금리·한국 10년 금리·브렌트유(FRED, 월평균)
2) 종목 뉴스 누적 → docs/<업종>/data/news_hist.json
   news.json 은 최근 90일·25건만 남기므로, 매일 합쳐 쌓아 두면 나중에 생긴 변곡점도 그 시기 뉴스로 설명할 수 있다.
   --backfill N : 네이버 종목뉴스를 회사마다 N페이지(1페이지 20건)까지 과거로 거슬러 받아 함께 쌓는다(처음 한 번·주 1회).

표준 라이브러리만 사용.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
KST = dt.timezone(dt.timedelta(hours=9))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
KEEP_PER_CO = 800   # 회사당 누적 뉴스 상한(최신순)
KEEP_RESEARCH = 600  # 회사당 증권사 리포트 제목 상한
REL = re.compile(r"실적|영업이익|영업익|순이익|매출|어닝|서프라이즈|쇼크|흑자|적자|컨센서스|가이던스|잠정|수주|계약|납품|인수|매각|합병|분할|"
                 r"증자|전환사채|자사주|소각|배당|경영권|최대주주|블록딜|상장|관세|규제|정책|보조금|소송|리콜|공장|증설|감산|가격|인상|인하|"
                 r"수출|점유율|목표가|하향|상향|급등|급락|신고가|52주|"
                 r"테마|관련주|수혜주|대장주|상한가|하한가|선거|후보|기대치|예상치|웃돌|밑돌|상회|하회|깜짝|부진|호실적|"
                 r"IR|기업설명회|컨퍼런스콜|NDR|주주환원|밸류업|관리종목|거래정지|감사의견")


def get(url, params=None, timeout=25, enc="utf-8"):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://finance.naver.com/"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode(enc, "ignore")


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------- 거시
def naver_index(sym):
    txt = get(f"https://fchart.stock.naver.com/sise.nhn?symbol={sym}&timeframe=month&count=240&requestType=0", enc="euc-kr")
    out = {}
    for m in re.finditer(r'data="([^"]+)"', txt):
        f = m.group(1).split("|")
        try:
            out[f"{f[0][:4]}-{f[0][4:6]}"] = round(float(f[4]), 2)
        except (ValueError, IndexError):
            pass
    return out


def yahoo_month(sym):
    j = json.loads(get(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}", {"range": "15y", "interval": "1mo"}))
    res = j["chart"]["result"][0]
    out = {}
    for t, c in zip(res["timestamp"], res["indicators"]["quote"][0]["close"]):
        if c:
            out[dt.datetime.fromtimestamp(t, KST).strftime("%Y-%m")] = round(c, 2)
    return out


def _try(fn):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        log("  1차 소스 실패, 대체 소스 시도:", e)
        return {}


def fred_month(sid, start="2014-01-01"):
    txt = get("https://fred.stlouisfed.org/graph/fredgraph.csv", {"id": sid, "cosd": start}, timeout=15)
    acc = {}
    for row in csv.reader(io.StringIO(txt)):
        if len(row) < 2 or not re.match(r"\d{4}-\d{2}", row[0]):
            continue
        try:
            v = float(row[1])
        except ValueError:
            continue
        acc.setdefault(row[0][:7], []).append(v)
    return {m: round(sum(v) / len(v), 3) for m, v in acc.items()}


def update_macro():
    p = ROOT / "docs/shared/macro.json"
    old = {}
    try:
        old = json.loads(p.read_text("utf-8")).get("series", {})
    except Exception:  # noqa: BLE001
        pass
    spec = {
        "KOSPI": ("코스피 월말", lambda: naver_index("KOSPI") or yahoo_month("^KS11")),
        "KOSDAQ": ("코스닥 월말", lambda: naver_index("KOSDAQ") or yahoo_month("^KQ11")),
        # FRED가 GitHub Actions에서 자주 응답하지 않아(2026-11-13 첫 실행 시간 초과) 야후 월봉으로 대체
        "USDKRW": ("원/달러 월말(FRED DEXKOUS 월평균, 실패 시 야후 KRW=X)", lambda: _try(lambda: fred_month("DEXKOUS")) or yahoo_month("KRW=X")),
        "US10Y": ("미국 10년 국채 금리(FRED DGS10, 실패 시 야후 ^TNX), %", lambda: _try(lambda: fred_month("DGS10")) or yahoo_month("^TNX")),
        "KR10Y": ("한국 10년 국채 금리 월(FRED IRLTLT01KRM156N), %", lambda: fred_month("IRLTLT01KRM156N")),
        "BRENT": ("브렌트유(FRED DCOILBRENTEU 월평균, 실패 시 야후 BZ=F), $/배럴", lambda: _try(lambda: fred_month("DCOILBRENTEU")) or yahoo_month("BZ=F")),
    }
    series, ok = {}, 0
    for k, (name, fn) in spec.items():
        d = {}
        try:
            d = fn()
        except Exception as e:  # noqa: BLE001
            log("거시 수집 실패:", k, e)
        if d:
            ok += 1
            series[k] = {"name": name, "data": dict(sorted(d.items()))}
        elif k in old:
            series[k] = old[k]
        time.sleep(0.3)
    if not series:
        log("거시 데이터 없음 — 파일 유지")
        return
    p.write_text(json.dumps({"updated": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"), "series": series},
                            ensure_ascii=False, separators=(",", ":")), "utf-8")
    log("거시:", ok, "/", len(spec), "개 지표 갱신")


# ---------------------------------------------------------------- 뉴스 누적
def industries():
    out = [("cosmetics", ROOT / "docs/data", ROOT / "config/companies.json")]
    for p in sorted((ROOT / "docs").glob("*/data/news.json")):
        ind = p.parent.parent.name
        out.append((ind, p.parent, ROOT / "config" / ind / "companies.json"))
    return out


def naver_news_page(code, page):
    d = json.loads(get(f"https://m.stock.naver.com/api/news/stock/{code}", {"pageSize": 20, "page": page}))
    groups = d if isinstance(d, list) else (d or {}).get("items") or []
    out = []
    for g in groups:
        for it in (g.get("items") if isinstance(g, dict) and "items" in g else [g]):
            if not isinstance(it, dict) or not it.get("title"):
                continue
            ts = str(it.get("datetime") or "")
            oid, aid = it.get("officeId"), it.get("articleId")
            title = re.sub(r"<[^>]+>", "", it.get("titleFull") or it["title"])
            for a, b in (("&quot;", '"'), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&#39;", "'")):
                title = title.replace(a, b)
            out.append({"date": f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}" if len(ts) >= 8 else "", "title": title.strip(),
                        "office": it.get("officeName") or "",
                        "url": f"https://n.news.naver.com/mnews/article/{oid}/{aid}" if oid and aid else it.get("url") or "",
                        "summary": re.sub(r"<[^>]+>", "", it.get("body") or "")[:160].strip()})
    return out


def update_news_hist(backfill=0):
    for ind, data, cfgp in industries():
        try:
            cfg = json.loads(cfgp.read_text("utf-8"))
            cfg = cfg["companies"] if isinstance(cfg, dict) else cfg
        except Exception:  # noqa: BLE001
            cfg = []
        kw = {c["code"]: (c.get("news_kw") or [c["name"]], c.get("news_ex") or []) for c in cfg}
        hp = data / "news_hist.json"
        hist = {}
        try:
            hist = json.loads(hp.read_text("utf-8")).get("companies", {})
        except Exception:  # noqa: BLE001
            pass
        cur = {}
        try:
            cur = json.loads((data / "news.json").read_text("utf-8")).get("companies", {})
        except Exception:  # noqa: BLE001
            pass
        added = 0
        for code in set(cur) | set(kw) | set(hist):
            items = list(cur.get(code) or [])
            if backfill and code in kw:
                k, ex = kw[code]
                for pg in range(1, backfill + 1):
                    try:
                        got = naver_news_page(code, pg)
                    except Exception as e:  # noqa: BLE001
                        log("과거 뉴스 실패:", ind, code, pg, e)
                        break
                    if not got:
                        break
                    for x in got:  # 회사 이야기이고, 주가에 영향을 줄 만한 기사만
                        t = x["title"] + " " + x["summary"]
                        if any(w in t for w in k) and not any(w in t for w in ex) and REL.search(x["title"]):
                            items.append(x)
                    time.sleep(0.12)
            merged = {(x.get("url") or x.get("title")): {kk: x.get(kk, "") for kk in ("date", "title", "office", "url")}
                      for x in (hist.get(code) or []) + items if x.get("date") and x.get("title")}
            seen, lst = set(), []
            for x in sorted(merged.values(), key=lambda x: x["date"], reverse=True):
                key = re.sub(r"\W", "", x["title"])[:30]
                if key in seen:
                    continue
                seen.add(key)
                lst.append(x)
            lst = lst[:KEEP_PER_CO]
            added += max(0, len(lst) - len(hist.get(code) or []))
            if lst:
                hist[code] = lst
        hp.write_text(json.dumps({"updated": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
                                  "note": "네이버 금융 종목뉴스 누적본(변곡점 해설용, 제목·날짜·링크만)", "companies": hist},
                                 ensure_ascii=False, separators=(",", ":")), "utf-8")
        log(f"뉴스 누적 {ind}: {len(hist)}개사, +{added}건")


# ---------------------------------------------------------------- 증권사 리포트 제목 누적(실적 기대 대비 판단용)
def naver_research_page(code, page):
    """네이버 금융 리서치 > 종목분석 목록: 날짜·제목·증권사·PDF. 제목('어닝 쇼크', '기대치 상회' 등)으로 실적이 기대 대비 어땠는지 읽는다."""
    html = get("https://finance.naver.com/research/company_list.naver",
               {"searchType": "itemCode", "itemCode": code, "page": page}, enc="euc-kr")
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        a = re.search(r'<a href="(company_read\.naver\?nid=\d+[^"]*)"[^>]*>(.*?)</a>', tr, re.S)
        dm = re.search(r'class="date"[^>]*>\s*(\d{2})\.(\d{2})\.(\d{2})', tr)
        if not a or not dm:
            continue
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        broker = re.sub(r"<[^>]+>|\s+", " ", tds[2]).strip() if len(tds) > 2 else ""
        pdf = re.search(r'href="(https?://[^"]+\.pdf)"', tr)
        title = re.sub(r"<[^>]+>", "", a.group(2)).strip()
        for x, y in (("&quot;", '"'), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&#39;", "'")):
            title = title.replace(x, y)
        out.append({"date": f"20{dm.group(1)}-{dm.group(2)}-{dm.group(3)}", "title": title, "office": broker,
                    "url": pdf.group(1) if pdf else "https://finance.naver.com/research/" + a.group(1).replace("&amp;", "&")})
    return out


def update_research(pages=1):
    for ind, data, cfgp in industries():
        try:
            cfg = json.loads(cfgp.read_text("utf-8"))
            cfg = cfg["companies"] if isinstance(cfg, dict) else cfg
        except Exception:  # noqa: BLE001
            cfg = []
        hp = data / "research_hist.json"
        hist = {}
        try:
            hist = json.loads(hp.read_text("utf-8")).get("companies", {})
        except Exception:  # noqa: BLE001
            pass
        added, fails = 0, 0
        for c in cfg:
            code = c["code"]
            got = []
            for pg in range(1, pages + 1):
                try:
                    g = naver_research_page(code, pg)
                except Exception as e:  # noqa: BLE001
                    fails += 1
                    if fails <= 3:
                        log("리포트 목록 실패:", ind, code, pg, e)
                    break
                if not g:
                    break
                got += g
                if len(g) < 30:
                    break
                time.sleep(0.15)
            old = hist.get(code) or []
            m = {(x["date"], x["title"]): x for x in old + got}
            lst = sorted(m.values(), key=lambda x: x["date"], reverse=True)[:KEEP_RESEARCH]
            added += max(0, len(lst) - len(old))
            if lst:
                hist[code] = lst
            time.sleep(0.1)
        hp.write_text(json.dumps({"updated": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
                                  "note": "네이버 금융 리서치 종목분석 리포트 제목 누적본(실적 기대 대비·증권사 시각 판단용)", "companies": hist},
                                 ensure_ascii=False, separators=(",", ":")), "utf-8")
        log(f"리포트 누적 {ind}: {len(hist)}개사, +{added}건")


if __name__ == "__main__":
    bf = int(sys.argv[sys.argv.index("--backfill") + 1]) if "--backfill" in sys.argv else 0
    if "--no-macro" not in sys.argv:
        update_macro()
    if "--no-news" not in sys.argv:
        update_news_hist(bf)
    if "--no-research" not in sys.argv:
        update_research(max(1, bf))
