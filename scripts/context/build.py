"""회사별 '입체 분석' 자료 만들기 → docs/<업종>/data/context.json (화장품은 docs/data/context.json)

한 회사를 여러 각도에서 본다:
  1) 사업보고서 원문 근거(제품 매출구성·판매경로·주요 고객·원재료 가격·점유율·경쟁요소·업황 특성)  ← bizfacts.py
  2) 회사 뉴스(네이버 금융 + 구글 뉴스)  3) 업종 뉴스  4) 경쟁사·고객사·공급사 뉴스
  5) 블로그 글(소비자·투자자 반응)  6) 관심도 추세(뉴스 언급량, 네이버 키가 있으면 검색량)
그리고 모든 기사를 제품·경쟁·고객·조달·사이클·해자·전망 칸에 나누고 '이렇게 보세요' 해석을 붙인다(synth.py).

사용법:
  python scripts/context/build.py --industry apparel            # 수집 + 생성
  python scripts/context/build.py --industry all --offline       # 네트워크 없이(사업보고서 근거·기존 뉴스만) 다시 생성
"""
import datetime as dt
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bizfacts  # noqa: E402
import fetch  # noqa: E402
import synth  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
KST = dt.timezone(dt.timedelta(hours=9))
TODAY = dt.datetime.now(KST).date()
CFG = json.loads((ROOT / "config/context/industries.json").read_text("utf-8"))
INDUSTRIES = ["cosmetics", "semi", "chem", "battery", "apparel", "food", "logistics"]
CONSUMER = {"cosmetics", "apparel", "food"}


def cfg_path(ind):
    return ROOT / ("config/companies.json" if ind == "cosmetics" else f"config/{ind}/companies.json")


def data_dir(ind):
    return ROOT / ("docs/data" if ind == "cosmetics" else f"docs/{ind}/data")


def jload(p, default=None):
    try:
        return json.loads(Path(p).read_text("utf-8"))
    except Exception:
        return default


def companies(ind):
    return jload(cfg_path(ind), []) or []


def all_index():
    """대시보드 전체 회사 이름 → (업종, 코드)"""
    idx = {}
    for ind in INDUSTRIES:
        for c in companies(ind):
            idx.setdefault(c["name"], (ind, c["code"]))
    return idx


def _has(text, name):
    if re.fullmatch(r"[A-Za-z0-9&\-. ]+", name):
        return re.search(r"(?<![A-Za-z])" + re.escape(name) + r"(?![A-Za-z])", text) is not None
    return name in text


def related(ind, c, deep_x, facts, idx, glob_names, peers):
    """심층분석·사업보고서 문장에 나온 이름으로 경쟁사·고객사·공급사를 찾는다. 부족하면 같은 그룹 회사로 경쟁사를 채운다."""
    me = c["name"]
    aliases = set([me] + (c.get("news_kw") or []))
    texts = {
        "customer": " ".join([(deep_x or {}).get("customers", "")] + facts.get("customers", []) + facts.get("channel", [])),
        "supplier": " ".join([(deep_x or {}).get("sourcing", "")] + facts.get("materials", [])),
        "competitor": " ".join([(deep_x or {}).get("competition", "")] + facts.get("share", []) + facts.get("competition", [])),
    }
    names = sorted(set(idx) | set(glob_names), key=len, reverse=True)
    out, used = [], set()
    for rel in ("customer", "supplier", "competitor"):
        t = texts[rel]
        k = 0
        for n in names:
            if len(n) < 2 or n in used or any(n in a or a in n for a in aliases):
                continue
            if _has(t, n):
                # '현대차증권' 안의 '현대차'처럼 더 긴 이름에 포함된 경우는 건너뛴다
                if any(n in u and n != u for u in used):
                    continue
                used.add(n)
                ic = idx.get(n)
                out.append({"name": n, "rel": rel, "ind": ic[0] if ic else None, "code": ic[1] if ic else None})
                k += 1
                if k >= (5 if rel != "supplier" else 4):
                    break
    if sum(1 for x in out if x["rel"] == "competitor") < 3:
        for p in peers:
            if p["code"] == c["code"] or p["name"] in used:
                continue
            used.add(p["name"])
            out.append({"name": p["name"], "rel": "competitor", "ind": ind, "code": p["code"], "peer": True})
            if sum(1 for x in out if x["rel"] == "competitor") >= 4:
                break
    return out


def query_for(ind, c):
    n = c["name"]
    short = len(n) <= 2 or re.fullmatch(r"[A-Za-z0-9&\- .]+", n)
    return f'"{n}" {CFG[ind]["hint"]}' if short else f'"{n}"'


def week_of(d):
    y, w, _ = dt.date.fromisoformat(d).isocalendar()
    return f"{y}-W{w:02d}"


def trend_from(series, label, src):
    """[[주, 값]...] → 최근 4주 vs 직전 4주 변화율"""
    if not series or len(series) < 6:
        return None
    v = [x[1] for x in series]
    a, b = sum(v[-4:]), sum(v[-8:-4])
    chg = (a / b - 1) * 100 if b else None
    return {"label": label, "src": src, "series": series[-26:], "chg": None if chg is None else round(chg, 1)}


def norm_title(t):
    return re.sub(r"\W", "", t or "")[:28]


def build(ind, offline=False, all_news=None):
    cos = companies(ind)
    if not cos:
        return None
    dd = data_dir(ind)
    deep = (jload(dd / "deep.json", {}) or {}).get("companies", {})
    news = (jload(dd / "news.json", {}) or {}).get("companies", {})
    old = (jload(dd / "context.json", {}) or {})
    oldc = old.get("companies", {})
    icfg = CFG[ind]
    idx = all_index()
    cutoff60 = (TODAY - dt.timedelta(days=60)).isoformat()
    cutoff30 = (TODAY - dt.timedelta(days=30)).isoformat()
    groups = {}
    for c in cos:
        groups.setdefault(c.get("group") or "기타", []).append(c)

    # ---------- 1) 업종 뉴스 + 검색 트렌드
    industry = {}
    for g, members in groups.items():
        gq = (icfg["groups"].get(g) or {})
        items = []
        if not offline:
            for q in gq.get("news", []):
                items += fetch.gnews(q, days=30, n=25)
                time.sleep(0.6)
        seen, uniq = set(), []
        for x in sorted(items, key=lambda x: x["date"], reverse=True):
            k = norm_title(x["title"])
            if k in seen:
                continue
            seen.add(k)
            cat, sec, tone, read = synth.classify(x, "industry")
            uniq.append({**x, "rel": "industry", "cat": cat, "sec": sec, "tone": tone, "read": read})
        if not uniq:  # 수집 실패 → 지난 자료 유지
            uniq = ((old.get("industry") or {}).get(g) or {}).get("news", [])
        tr = None
        if not offline and gq.get("trend"):
            dl = fetch.datalab({g: gq["trend"]})
            if dl.get(g):
                tr = trend_from(dl[g], "네이버 검색량", "네이버 데이터랩")
        if not tr:
            tr = ((old.get("industry") or {}).get(g) or {}).get("trend")
        industry[g] = {"queries": gq.get("news", []), "trend_kw": gq.get("trend", []), "news": uniq[:12],
                       "lean": synth.summarize_section(uniq[:12]), "trend": tr}

    # ---------- 2) 회사별 근거 + 연관 기업
    facts_all, rel_all = {}, {}
    for c in cos:
        f = bizfacts.load_facts(ind, c["code"]) or {}
        facts_all[c["code"]] = f
        rel_all[c["code"]] = related(ind, c, deep.get(c["code"]), f, idx, icfg.get("global", []), groups.get(c.get("group") or "기타", []))

    # ---------- 3) 대시보드 밖 연관 기업 뉴스 (이름당 1회)
    gl_news = {}
    need = sorted({r["name"] for rs in rel_all.values() for r in rs if not r.get("code")})
    for n in need:
        if offline:
            break
        items = fetch.gnews(f'"{n}" {icfg["hint"]}', days=30, n=15)  # 업종어를 붙여 엉뚱한 기사(예: 코스트코 핫도그)를 줄인다
        gl_news[n] = [x for x in items if n.lower() in x["title"].lower()][:4]
        time.sleep(0.6)

    # ---------- 4) 회사별 수집 + 분류
    out = {}
    blog_ok = 0
    for c in cos:
        code, name = c["code"], c["name"]
        prev = oldc.get(code) or {}
        prev_sig = prev.get("signals") or []
        sig = []

        # 회사 뉴스: 네이버 금융(이미 수집됨) + 구글 뉴스
        own = [{**x, "src": "네이버 금융"} for x in (news.get(code) or [])]
        gn = []
        if not offline:
            gn = fetch.gnews(query_for(ind, c), days=90, n=80)
            time.sleep(0.5)
        kw = c.get("news_kw") or [name]
        gn_rel = [x for x in gn if any(k in x["title"] for k in kw)]
        seen = set()
        for x in sorted(own + [{**x, "src": "구글 뉴스"} for x in gn_rel], key=lambda x: (x["date"], x.get("time", "")), reverse=True):
            k = norm_title(x["title"])
            if k in seen or x["date"] < cutoff60:
                continue
            seen.add(k)
            cat, sec, tone, read = synth.classify(x, "self")
            sig.append({"date": x["date"], "title": x["title"], "url": x["url"], "office": x.get("office", ""), "rel": "self",
                        "who": name, "cat": cat, "sec": sec, "tone": tone, "read": read})
            if len([s for s in sig if s["rel"] == "self"]) >= 14:
                break
        if not gn and not own:
            sig += [s for s in prev_sig if s["rel"] == "self"]

        # 관심도 추세: 구글 뉴스 주간 언급량 (지난 값과 합쳐 26주까지 유지)
        wk = dict((prev.get("trend_news") or {}).get("series") or [])
        if gn_rel:
            cnt = Counter(week_of(x["date"]) for x in gn_rel if x["date"])
            this_w = week_of(TODAY.isoformat())
            start = TODAY - dt.timedelta(weeks=12)
            for i in range(13):
                w = week_of((start + dt.timedelta(weeks=i)).isoformat())
                if w != this_w:
                    wk[w] = cnt.get(w, 0)
        series = sorted(wk.items())[-26:]
        t_news = trend_from([list(x) for x in series], "뉴스 언급량", "구글 뉴스 주간 기사 수") if series else None

        # 연관 기업 뉴스
        for r in rel_all[code]:
            if r.get("code"):
                pool = (all_news.get(r["code"]) or []) if all_news else []
                pool = [x for x in pool if x["date"] >= cutoff30 and any(k in x["title"] for k in [r["name"]])][:3]
            else:
                pool = gl_news.get(r["name"]) or [s for s in prev_sig if s.get("who") == r["name"]]
            for x in pool[:3]:
                cat, sec, tone, read = synth.classify(x, r["rel"])
                if cat == "pr":
                    continue  # 연관 기업의 홍보성 기사는 뺀다
                sig.append({"date": x["date"], "title": x["title"], "url": x["url"], "office": x.get("office", ""), "rel": r["rel"],
                            "who": r["name"], "cat": cat, "sec": sec, "tone": tone, "read": read})

        # 같은 기사가 여러 연관 기업에 걸리면 한 번만, 연관 기업 기사는 최대 12건
        seen_u, rel_n, keep = set(), 0, []
        for s_ in sig:
            if s_["url"] in seen_u:
                continue
            seen_u.add(s_["url"])
            if s_["rel"] in ("competitor", "customer", "supplier"):
                rel_n += 1
                if rel_n > 12:
                    continue
            keep.append(s_)
        sig = keep

        # 업종 뉴스 (그룹 뉴스 중 최근 5건)
        for x in (industry.get(c.get("group") or "기타") or {}).get("news", [])[:5]:
            sig.append({k: x[k] for k in ("date", "title", "url", "office", "rel", "cat", "sec", "tone", "read")} | {"who": c.get("group")})

        # 블로그
        bl = []
        if not offline:
            qs = [query_for(ind, c).replace('"', "")]
            brands = [k for k in kw if k != name and len(k) >= 2]
            if ind in CONSUMER and brands:
                qs.append(brands[0] if len(brands[0]) > 2 else f"{brands[0]} {icfg['hint']}")
            for q in qs:
                items, total = fetch.blogs(q)
                bl += items
                time.sleep(0.4)
        if bl:
            blog_ok += 1
            seen = set()
            for x in sorted(bl, key=lambda x: x["date"], reverse=True):
                k = norm_title(x["title"])
                if k in seen or not x["date"] or x["date"] < cutoff60:
                    continue
                seen.add(k)
                cat, sec, tone, read = synth.classify(x, "blog")
                sig.append({"date": x["date"], "title": x["title"], "url": x["url"], "office": x.get("office", ""), "rel": "blog",
                            "who": "블로그", "cat": cat, "sec": sec, "tone": tone, "read": read, "summary": (x.get("summary") or "")[:110]})
                if len([s for s in sig if s["rel"] == "blog"]) >= 5:
                    break
        else:
            sig += [s for s in prev_sig if s["rel"] == "blog"]

        sig.sort(key=lambda x: x["date"], reverse=True)
        by = {}
        for s in sig:
            by.setdefault(s["sec"], []).append(s)
        sections = {k: synth.summarize_section(v) for k, v in by.items()}
        t_search = prev.get("trend_search")
        out[code] = {
            "name": name,
            "facts": facts_all[code],
            "related": rel_all[code],
            "sections": sections,
            "signals": sig[:45],  # 화면은 sec(칸)별로 묶어 보여 주고, 다음 수집이 실패하면 재사용
            "trend_news": t_news,
            "trend_search": t_search,
            "check": synth.cross_check(sig, deep.get(code), t_news),
            "counts": dict(Counter(s["rel"] for s in sig)),
        }

    # ---------- 5) 회사 검색량 (네이버 키가 있을 때, 5개씩)
    if not offline:
        batch = []
        for c in cos:
            kws = [k for k in (c.get("news_kw") or [c["name"]]) if len(k) >= 2][:3]
            batch.append((c["code"], kws))
        for i in range(0, len(batch), 5):
            grp = {code: kws for code, kws in batch[i:i + 5]}
            res = fetch.datalab(grp)
            for code, s in res.items():
                t = trend_from(s, "네이버 검색량", "네이버 데이터랩(회사·브랜드명)")
                if t and code in out:
                    out[code]["trend_search"] = t
                    out[code]["check"] = synth.cross_check(out[code]["signals"], deep.get(code), t)
            if not res:
                break
            time.sleep(0.3)

    res = {
        "updated": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
        "industry_label": icfg["label"],
        "sections": synth.SECTIONS,
        "sources": {
            "사업보고서": "DART 사업보고서·반기보고서 본문(사업의 내용) 자동 발췌",
            "회사 뉴스": "네이버 금융 종목뉴스 + 구글 뉴스 검색(최근 60일)",
            "업종 뉴스": "구글 뉴스 검색(업종 그룹별 검색어, 최근 30일)",
            "연관 기업": "심층분석·사업보고서에 나온 경쟁사·고객사·공급사의 최근 30일 뉴스",
            "블로그": "네이버 블로그 최신 글" + (" (공식 검색 API)" if fetch._naver_keys()[0] else ""),
            "관심도": "구글 뉴스 주간 기사 수" + (" + 네이버 데이터랩 검색량" if fetch._naver_keys()[0] else ""),
        },
        "fetch_stats": {k: {"ok": v[0], "fail": v[1]} for k, v in fetch.STATS.items()} if not offline else old.get("fetch_stats"),
        "industry": industry,
        "companies": out,
    }
    (dd / "context.json").write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")), "utf-8")
    print(f"[{ind}] {len(out)}개사 · 블로그 {blog_ok} · 통계 {fetch.STATS}")
    return res


def load_all_news():
    allm = {}
    for ind in INDUSTRIES:
        allm.update((jload(data_dir(ind) / "news.json", {}) or {}).get("companies", {}))
    return allm


if __name__ == "__main__":
    ind = sys.argv[sys.argv.index("--industry") + 1] if "--industry" in sys.argv else "all"
    offline = "--offline" in sys.argv
    allnews = load_all_news()
    for i in (INDUSTRIES if ind == "all" else [ind]):
        build(i, offline, allnews)
