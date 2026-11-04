"""반도체 회사별 리뷰(reviews_src.py) + 분기 실적 추세(companies.json) → docs/semi/data/reviews.json"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from reviews_src import R

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


def eok(v):
    v = round(v / 100)
    return f"{v/10000:,.1f}조" if abs(v) >= 10000 else f"{v:,}억"


def trend(co):
    Q = co["quarterly"]
    ks = sorted(Q)[-4:]
    out, gs = [], []
    for k in ks:
        prev = f"{int(k[:4])-1}{k[4:]}"
        p = Q.get(prev, {}).get("rev")
        gs.append(f"{(Q[k]['rev']/p-1)*100:+.0f}%" if p else "-")
    out.append(f"매출 성장률(전년 같은 분기 대비)이 {' → '.join(gs)}였고, {ks[-1]} 매출은 {eok(Q[ks[-1]]['rev'])}원이었어요.")
    om = [Q[k]["op"] / Q[k]["rev"] * 100 for k in ks if Q[k]["rev"]]
    out.append(f"영업이익률은 {ks[0]} {om[0]:.1f}%에서 {ks[-1]} {om[-1]:.1f}%로 {'올랐어요' if om[-1] > om[0] + 0.5 else '내려왔어요' if om[-1] < om[0] - 0.5 else '비슷했어요'}.")
    ni = sum(Q[k]["ni"] for k in ks)
    out.append(f"최근 4개 분기 순이익 합계는 {eok(ni)}원이에요." if ni > 0 else f"최근 4개 분기 순이익 합계는 {eok(-ni)}원 적자예요.")
    return out


def main():
    cos = {c["code"]: c for c in json.load(open(os.path.join(ROOT, "docs/semi/data/companies.json")))["companies"]}
    out = {"updated": "2026-11-04",
           "period": "DART 확정 실적(2026년 2분기까지) + 2026-11-04까지 발표된 3분기 실적(삼성전자·SK하이닉스·한미반도체)",
           "disclaimer": "공시 수치와 언론 보도를 바탕으로 정리한 참고용 해석이며 투자 권유가 아닙니다.",
           "companies": {}}
    for code, r in R.items():
        co = cos[code]
        docs = json.load(open(os.path.join(ROOT, f"raw/semi/dart_docs/{code}.json")))
        reps = docs.get("reports") or []
        rep = next((x for x in reps if "반기" in x["report_nm"]), None) or (reps[0] if reps else {})
        out["companies"][code] = {
            "tone": r["tone"], "title": r["title"],
            "trend": trend(co) + r.get("extra", []),
            "eval": r["eval"], "watch": r["watch"],
            "news": [{"date": d, "title": t, "url": u} for d, t, u in r.get("news", [])],
            "next": r["next"],
            "biz": {"report": rep.get("report_nm", ""), "url": rep.get("url", ""),
                    "mix_title": r.get("mix_title", ""),
                    "mix": [{"label": l, "pct": p} for l, p in r.get("mix", [])],
                    "points": r["points"]},
        }
    missing = set(cos) - set(R)
    assert not missing, missing
    with open(os.path.join(ROOT, "docs/semi/data/reviews.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("reviews.json", len(out["companies"]))


if __name__ == "__main__":
    main()
