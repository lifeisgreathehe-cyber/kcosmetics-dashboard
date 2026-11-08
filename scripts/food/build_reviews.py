"""음식료 회사별 리뷰·최신 뉴스 해석(co_*.py의 R, news_add_*.py) + 분기 실적 추세(companies.json) → docs/food/data/reviews.json
news 항목: {date,title,url,src,read(이렇게 보세요),impact(+/-/0)} — 다른 산업 대시보드와 같은 스키마
매일 추가분: scripts/food/news_add_YYYYMMDD.py 의 ADD = {종목코드 | "@그룹명" | "@all": [뉴스 튜플]}, UPD = {종목코드: {바꿀 필드}}"""
import glob, importlib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.join(HERE, "..", "..")
UPDATED = "2026-11-08"


def clean(Q):
    return {k: {f: (v.get(f) or 0) for f in ("rev", "op", "ni")} for k, v in (Q or {}).items() if v.get("rev")}


def eok(v):
    v = round(v / 100)
    return f"{v/10000:,.1f}조" if abs(v) >= 10000 else f"{v:,}억"


def trend(co):
    Q = clean(co.get("quarterly"))
    if len(Q) < 4:
        return ["DART 분기 실적 수집 전이에요. 수집되면 최근 4개 분기 매출 성장률·이익률이 자동으로 채워져요. 그 전까지는 아래 평가에 적은 발표 실적·컨센서스를 참고하세요."]
    ks = sorted(Q)[-4:]
    gs = []
    for k in ks:
        p = Q.get(f"{int(k[:4])-1}{k[4:]}", {}).get("rev")
        gs.append(f"{(Q[k]['rev']/p-1)*100:+.0f}%" if p else "-")
    om = [Q[k]["op"] / Q[k]["rev"] * 100 for k in ks]
    ni = sum(Q[k]["ni"] for k in ks)
    return [f"매출 성장률(전년 같은 분기 대비)이 {' → '.join(gs)}였고, {ks[-1]} 매출은 {eok(Q[ks[-1]]['rev'])}원이었어요.",
            f"영업이익률은 {ks[0]} {om[0]:.1f}%에서 {ks[-1]} {om[-1]:.1f}%로 {'올랐어요' if om[-1] > om[0] + 0.5 else '내려왔어요' if om[-1] < om[0] - 0.5 else '비슷했어요'}.",
            f"최근 4개 분기 순이익 합계는 {eok(ni)}원이에요." if ni > 0 else f"최근 4개 분기 순이익 합계는 {eok(-ni)}원 적자예요."]


def dkey(d):
    if re.match(r"\d{4}-\d{2}", d):
        return d
    m = re.search(r"(\d+)월", d)
    return f"{d[:4]}-{int(m.group(1)):02d}" if m else f"{d[:4]}-06"


def main():
    R = {}
    for f in sorted(glob.glob(os.path.join(HERE, "co_*.py"))):
        R.update(importlib.import_module(os.path.basename(f)[:-3]).R)
    cos = {c["code"]: c for c in json.load(open(os.path.join(ROOT, "docs/food/data/companies.json"), encoding="utf-8"))["companies"]}
    asof = UPDATED
    for f in sorted(glob.glob(os.path.join(HERE, "news_add_*.py"))):
        m = importlib.import_module(os.path.basename(f)[:-3])
        asof = max(asof, getattr(m, "ASOF", asof))
        for key, items in m.ADD.items():
            codes = [c for c, co in cos.items() if key == "@all" or key == "@" + co.get("group", "")] if key.startswith("@") else [key]
            for c in codes:
                if c in R:
                    have = {n[1] for n in R[c]["news"]}
                    R[c]["news"] = R[c]["news"] + [n for n in items if n[1] not in have]
        for code, upd in getattr(m, "UPD", {}).items():
            if code in R:
                R[code].update(upd)
    out = {"updated": UPDATED, "news_asof": asof,
           "period": "2026년 3분기 실적 발표(삼양식품·KT&G·CJ프레시웨이·현대그린푸드 발표, 나머지는 11월 9~14일)와 최신 기사",
           "disclaimer": "공시와 언론 보도를 바탕으로 정리한 참고용 해석이며 투자 권유가 아닙니다. 각 기사 아래 '이렇게 보세요'는 기사 내용이 회사 가치에 어떤 의미인지에 대한 해석이에요.",
           "companies": {}}
    for code, co in cos.items():
        r = R.get(code)
        if not r:
            continue
        dp = os.path.join(ROOT, f"raw/food/dart_docs/{code}.json")
        docs = json.load(open(dp, encoding="utf-8")) if os.path.exists(dp) else {}
        reps = docs.get("reports") or []
        rep = next((x for x in reps if "반기" in x["report_nm"]), None) or (reps[0] if reps else {})
        news = sorted(r.get("news", []), key=lambda n: dkey(n[0]), reverse=True)
        out["companies"][code] = {
            "tone": r["tone"], "title": r["title"], "trend": trend(co), "eval": r["eval"], "watch": r["watch"],
            "news": [{"date": d, "title": t, "url": u, "src": s, "read": rd, "impact": im} for d, t, u, s, rd, im in news],
            "next": r["next"],
            "biz": {"report": rep.get("report_nm", "DART 사업보고서 수집 대기"), "url": rep.get("url", ""), "mix_title": r.get("mix_title", ""),
                    "mix": [{"label": l, "pct": p} for l, p in r.get("mix", [])], "points": r.get("points", [])},
        }
    missing = sorted(set(cos) - set(out["companies"]))
    with open(os.path.join(ROOT, "docs/food/data/reviews.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("reviews.json", len(out["companies"]), "missing", missing)


if __name__ == "__main__":
    main()
