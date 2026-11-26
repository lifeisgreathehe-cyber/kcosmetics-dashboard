"""건설·건자재 회사별 분석 원고(scripts/construction/cx_a~d.py의 D) → docs/construction/data/deep.json + reviews.json + config/construction/valuation.json

매일 추가하는 뉴스 해석: scripts/construction/cx_news_YYYYMMDD.py
  ASOF = "YYYY-MM-DD"
  NEWS = {"종목코드" 또는 "@그룹명" 또는 "@all": [(날짜, 제목, URL, 매체, 해석, "+"/"-"/"0"), ...]}
  UPD  = {"종목코드": {"title": ..., "eval": ..., "tone": ...}}   # 리뷰 제목·평가 갱신(선택)
실행: python scripts/construction/build_deep.py
"""
import copy, datetime, glob, importlib, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "deep"))
from build import FISHER
from cx_common import IMP


def load_all():
    # 모듈 이름은 cx_ 접두어(다른 업종 common.py·deep_*.py와 한 프로세스에서 섞이지 않게)
    for f in sorted(glob.glob(os.path.join(HERE, "cx_[a-z].py"))):
        importlib.import_module(os.path.basename(f)[:-3])
    from cx_common import D
    return D


def eok(v):
    v = round(v / 100)
    return f"{v/10000:,.1f}조" if abs(v) >= 10000 else f"{v:,}억"


def trend(co):
    Q = {k: {f: (v.get(f) or 0) for f in ("rev", "op", "ni")} for k, v in (co.get("quarterly") or {}).items() if v.get("rev")}
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


SNAP = os.path.join(HERE, "snapshot.json")


def snapshot(code, v):
    """시세 수집 전 임시 가격·주식 수·자본(실적 랭킹 집계, 2026-11-21 종가). 금융위 시세·DART가 들어오면 그쪽이 우선이에요."""
    snaps = json.load(open(SNAP, encoding="utf-8")) if os.path.exists(SNAP) else {}
    s = dict(snaps.get(code) or {})
    s.update({k: x for k, x in (v.get("snapshot") or {}).items()})
    return {k: x for k, x in s.items() if x is not None}


def write_valuation(V, cos):
    """config/construction/valuation.json = 머리말(valuation_head.json) + 회사별 가정(deep_*.py의 val). 직접 고치지 말고 원고를 고친다."""
    head = json.load(open(os.path.join(HERE, "valuation_head.json"), encoding="utf-8"))
    head["companies"] = {c: dict(V[c], snapshot=snapshot(c, V[c])) for c in cos if c in V}
    json.dump(head, open(os.path.join(ROOT, "config/construction/valuation.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def main():
    D = load_all()
    cos = {c["code"]: c for c in json.load(open(os.path.join(ROOT, "docs/construction/data/companies.json"), encoding="utf-8"))["companies"]}
    asof = "2026-11-22"
    for f in sorted(glob.glob(os.path.join(HERE, "cx_news_2*.py"))):
        m = importlib.import_module(os.path.basename(f)[:-3])
        asof = max(asof, getattr(m, "ASOF", asof))
        for key, items in m.NEWS.items():
            codes = [c for c, co in cos.items() if key == "@all" or key == "@" + co.get("group", "")] if key.startswith("@") else [key]
            for c in codes:
                if c not in D:
                    continue
                ts = {n[1] for n in items}
                D[c]["news_raw"] = list(items) + [n for n in D[c]["news_raw"] if n[1] not in ts]
        for code, upd in getattr(m, "UPD", {}).items():
            if code in D:
                D[code]["review"].update(upd)
    from cx_common import IR, V
    write_valuation(V, cos)
    deep, rev = {}, {}
    for code, x in D.items():
        news = sorted(x["news_raw"], key=lambda n: n[0], reverse=True)
        y = copy.deepcopy(x)
        y.pop("news_raw"); r = y.pop("review")
        y["news"] = [dict(date=d, title=t, url=u, src=s, read=rd, impact=IMP.get(i, "neu")) for d, t, u, s, rd, i in news][:8]
        ir = IR.get(code)
        if ir:  # IR 분석: 성장전략·달성 가능성, 과거 IR 대비 변화, 교차검증
            y["ir"] = {"docs": ir["docs"], "verdict": ir["verdict"], "changes": ir["changes"],
                       "strategy": [dict(h=a, claim=b, feas=c, why=d) for a, b, c, d in ir["strategy"]],
                       "cross": [dict(peer=a, claim=b, verdict=c, read=d) for a, b, c, d in ir["cross"]]}
        deep[code] = y
        dp = os.path.join(ROOT, f"raw/construction/dart_docs/{code}.json")
        docs = json.load(open(dp, encoding="utf-8")) if os.path.exists(dp) else {}
        reps = docs.get("reports") or []
        rep = next((z for z in reps if "반기" in z["report_nm"]), None) or (reps[0] if reps else {})
        rev[code] = {"tone": r["tone"], "title": r["title"], "trend": trend(cos.get(code, {})), "eval": r["eval"], "watch": r["watch"],
                     "news": [{"date": d, "title": t, "url": u, "src": s, "read": rd, "impact": i} for d, t, u, s, rd, i in news],
                     "next": r["next"],
                     "biz": {"report": rep.get("report_nm", ""), "url": rep.get("url", ""), "mix_title": "", "mix": [], "points": []} if rep else None}
    today = datetime.date.today().isoformat()
    out = {"updated": today, "news_asof": asof,
           "source": "DART 사업보고서·분기보고서, 2026년 3분기 잠정실적·IR 자료, 실적 랭킹(DART 연결 집계), KOSIS 건설·주택 통계와 2026년 8~11월 기사",
           "fisher_questions": FISHER,
           "fisher_note": "필립 피셔 『위대한 기업에 투자하라』의 15가지 질문에 자본 배분(주주환원)을 16번째로 더했어요. 2점 충족, 1점 부분 충족, 0점 미흡이에요. 노사·경영진 항목은 공개 정보가 적어 보수적으로 매겼어요.",
           "disclaimer": "공시와 언론 보도를 바탕으로 한 정성 평가이며 투자 권유가 아니에요.",
           "companies": {c: deep[c] for c in cos if c in deep}}
    json.dump(out, open(os.path.join(ROOT, "docs/construction/data/deep.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ro = {"updated": today, "news_asof": asof,
          "period": "2026년 3분기 실적(잠정)과 건설수주·미분양·PF·시멘트 출하 기사",
          "disclaimer": "공시와 언론 보도를 바탕으로 정리한 참고용 해석이며 투자 권유가 아닙니다. 각 기사 아래 '이렇게 보세요'는 기사 내용이 회사 가치에 어떤 의미인지에 대한 해석이에요.",
          "companies": {c: rev[c] for c in cos if c in rev}}
    json.dump(ro, open(os.path.join(ROOT, "docs/construction/data/reviews.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("deep/reviews:", len(out["companies"]), "missing", sorted(set(cos) - set(deep)))


if __name__ == "__main__":
    main()
