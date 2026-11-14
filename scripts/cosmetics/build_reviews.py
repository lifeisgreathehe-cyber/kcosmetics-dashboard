"""화장품: 2026-11-05 추가된 25개사 리뷰(scripts/deep/part_f.py의 REV)를 docs/data/reviews.json에 합친다.
기존 회사(손으로 쓴 리뷰)는 건드리지 않고, 25개사는 실적 추세 문장을 최신 companies.json으로 다시 만든다.
DART 수집(update.py --only dart) 뒤 자동 실행돼, 새 분기가 들어오면 '해석 갱신 예정' 표시가 붙어요."""
import json, os, re, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, os.path.join(ROOT, "scripts", "deep"))
from part_f import REV, VAL  # noqa: E402

BASIS = "2026Q2"  # 해석 원고가 기준으로 삼은 마지막 확정 분기(3분기 잠정실적 기사는 반영)
NEXT = "3분기 보고서는 11월 14일 전후 공시돼요. 공시되면 숫자와 해석을 함께 갱신해요."


def eok(v):
    v = round(v / 100)
    return f"{v/10000:,.1f}조" if abs(v) >= 10000 else f"{v:,}억"


def trend(co):
    Q = {k: {f: (v.get(f) or 0) for f in ("rev", "op", "ni")} for k, v in (co.get("quarterly") or {}).items() if v.get("rev")}
    ks = sorted(Q)[-4:]
    if len(ks) < 2:
        return [], None
    gs = []
    for k in ks:
        p = Q.get(f"{int(k[:4])-1}{k[4:]}", {}).get("rev")
        gs.append(f"{(Q[k]['rev']/p-1)*100:+.0f}%" if p else "-")
    om = [Q[k]["op"] / Q[k]["rev"] * 100 for k in ks]
    ni = sum(Q[k]["ni"] for k in ks)
    out = [f"매출 성장률(전년 같은 분기 대비)이 {' → '.join(gs)}였고, {ks[-1]} 매출은 {eok(Q[ks[-1]]['rev'])}원이었어요.",
           f"영업이익률은 {ks[0]} {om[0]:.1f}%에서 {ks[-1]} {om[-1]:.1f}%로 {'올랐어요' if om[-1] > om[0] + 0.5 else '내려왔어요' if om[-1] < om[0] - 0.5 else '비슷했어요'}.",
           f"최근 4개 분기 순이익 합계는 {eok(ni)}원이에요." if ni >= 0 else f"최근 4개 분기 순이익 합계는 {eok(-ni)}원 적자예요."]
    return out, ks[-1]


def main():
    cos = {c["code"]: c for c in json.load(open(os.path.join(ROOT, "docs/data/companies.json")))["companies"]}
    ctx = (json.load(open(os.path.join(ROOT, "docs/data/context.json"))).get("companies") or {})
    p = os.path.join(ROOT, "docs/data/reviews.json")
    rv = json.load(open(p))
    for code, r in REV.items():
        co = cos.get(code)
        if not co:
            continue
        old = rv["companies"].get(code) or {}
        tr, last = trend(co)
        ev = r["eval"]
        basis = r.get("basis", BASIS)
        if last and last > basis:
            ev = f"※ {last} 확정 실적이 새로 들어왔어요. 위 실적 동향 숫자는 {last} 기준이고, 아래 해석은 {basis} 실적과 잠정실적 기사를 기준으로 쓴 것이라 곧 다시 써요. " + ev
        f = (ctx.get(code) or {}).get("facts") or {}
        biz = dict(old.get("biz") or {})
        biz.update({"report": f.get("report", biz.get("report", "")), "url": f.get("url", biz.get("url", "")),
                    "mix_title": "사업보고서 매출 구성" if f.get("mix") else "",
                    "mix": [m for m in (f.get("mix") or []) if m.get("pct")],
                    "points": r["points"]})
        new = dict(old)
        new.update({"tone": r["tone"], "title": r["title"], "trend": tr, "eval": ev, "watch": r["watch"],
                    "basis": basis, "next": old.get("next") or NEXT, "biz": biz})
        new.setdefault("news", [])
        v = VAL.get(code) or {}
        for n in new["news"]:  # '자동 적정가' 시절에 쓴 가치 메모를 개별 가정 기준으로 바꾼다
            if n.get("val") and ("자동 적정가" in n["val"] or "개별 가정이 없어" in n["val"]):
                n["val"] = (f"정상 이익 {v['E1']:,}억원 개별 가정에 반영했어요." if v.get("E1")
                            else "이익이 불안정해 적정가는 계산하지 않아요.")
        rv["companies"][code] = new
    with open(p, "w", encoding="utf-8") as fp:
        json.dump(rv, fp, ensure_ascii=False, indent=1)
    print("reviews.json: 25개사 리뷰 반영", sum(1 for c in REV if c in rv["companies"]))


if __name__ == "__main__":
    main()
