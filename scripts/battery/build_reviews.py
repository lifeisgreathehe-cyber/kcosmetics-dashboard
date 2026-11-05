"""2차전지 회사별 리뷰·최신 뉴스 해석(reviews_*.py) + 분기 실적 추세(companies.json) → docs/battery/data/reviews.json
news 항목: {date,title,url,src,read(어떻게 봐야 하나),impact(+/-/0)} — 화장품·반도체와 같은 스키마"""
import glob, importlib, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.join(HERE, "..", "..")
UPDATED = "2026-11-05"


def clean(Q):
    return {k: {f: (v.get(f) or 0) for f in ("rev", "op", "ni")} for k, v in (Q or {}).items() if v.get("rev")}


def eok(v):
    v = round(v / 100)
    return f"{v/10000:,.1f}조" if abs(v) >= 10000 else f"{v:,}억"


def trend(co):
    Q = clean(co.get("quarterly"))
    if len(Q) < 4:
        return ["DART 분기 실적 수집 전이에요. 수집되면 최근 4개 분기 매출 성장률·이익률이 자동으로 채워져요."]
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
    """'2026-11-05' 그대로, '2026년 10월'·'2026년 상반기' 같은 대략 날짜는 정렬용으로 근사"""
    import re
    if re.match(r"\d{4}-\d{2}", d):
        return d
    y = d[:4]
    m = re.search(r"(\d+)월", d)
    return f"{y}-{int(m.group(1)):02d}" if m else f"{y}-06" if "상반기" in d else f"{y}-12" if "하반기" in d else f"{y}-00"


def main():
    R = {}
    for f in sorted(glob.glob(os.path.join(HERE, "reviews_*.py"))):
        R.update(importlib.import_module(os.path.basename(f)[:-3]).R)
    cos = {c["code"]: c for c in json.load(open(os.path.join(ROOT, "docs/battery/data/companies.json"), encoding="utf-8"))["companies"]}
    out = {"updated": UPDATED,
           "period": "2026년 3분기 실적 발표(LG엔솔·삼성SDI·SK온·에코프로비엠·포스코퓨처엠·롯데에너지머티·SKC 등)와 2026-11-05까지의 기사",
           "disclaimer": "공시와 언론 보도를 바탕으로 정리한 참고용 해석이며 투자 권유가 아닙니다. 각 기사 아래 '이렇게 보세요'는 기사 내용이 회사 가치에 어떤 의미인지에 대한 해석이에요.",
           "companies": {}}
    for code, co in cos.items():
        r = R.get(code)
        if not r:
            continue
        dp = os.path.join(ROOT, f"raw/battery/dart_docs/{code}.json")
        docs = json.load(open(dp, encoding="utf-8")) if os.path.exists(dp) else {}
        reps = docs.get("reports") or []
        rep = next((x for x in reps if "반기" in x["report_nm"]), None) or (reps[0] if reps else {})
        news = sorted(r.get("news", []), key=lambda n: dkey(n[0]), reverse=True)
        out["companies"][code] = {
            "tone": r["tone"], "title": r["title"], "trend": trend(co), "eval": r["eval"], "watch": r["watch"],
            "news": [{"date": d, "title": t, "url": u, "src": s, "read": rd, "impact": im} for d, t, u, s, rd, im in news],
            "next": r["next"],
            "biz": {"report": rep.get("report_nm", ""), "url": rep.get("url", ""), "mix_title": "", "mix": [],
                    "points": r.get("points", [])} if rep else None,
        }
    missing = sorted(set(cos) - set(out["companies"]))
    with open(os.path.join(ROOT, "docs/battery/data/reviews.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("reviews.json", len(out["companies"]), "missing", missing)


if __name__ == "__main__":
    main()
