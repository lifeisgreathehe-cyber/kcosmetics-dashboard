"""의류 대시보드 원고(co_*.py, news_*.py, ir_src.py) → docs/apparel/data/deep.json · reviews.json, config/apparel/valuation.json 회사별 가정.
update.py --industry apparel 가 DART 수집 뒤 이 파일의 main()을 불러 실적 추세 문장을 다시 채운다.
사용: python scripts/apparel/build_reviews.py  (그다음 python scripts/build_valuation.py --industry apparel)"""
import glob, importlib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "deep"))
from build import FISHER  # noqa: E402

UPDATED = "2026-11-08"
DATA = os.path.join(ROOT, "docs", "apparel", "data")
CFG = os.path.join(ROOT, "config", "apparel")

INDUSTRY_CYCLE = {
    "OEM·ODM 수출": "미국 의류 소매 재고는 2024~25년 정상화됐지만, 2026년 하반기 원화 강세(달러 환산 이익 감소)·나프타 급등(원사 원가)·미국 관세 비용 분담이 이익률을 눌러요. 고기능 OEM(영원무역)은 견조, 저가 대량 OEM(한세실업)은 바닥권이에요.",
    "패션 대형사": "2023~25년 3년 내리 줄던 내수 고가 패션 이익이 2026년 2분기부터 반등했어요(소비심리 107, 관광객 증가, 백화점 여성캐주얼 +15.6%). 사이클상 회복 초기예요.",
    "스포츠·아웃도어·골프": "골프는 코로나 붐 이후 하강·바닥권, 라이선스 캐주얼·아웃도어는 유행 퇴조로 브랜드별 명암이 커요. 글로벌 골프(아쿠쉬네트)는 성숙하지만 안정적이에요.",
    "캐주얼·여성·속옷·잡화": "백화점 여성복은 회복, 가두점 중저가·홈쇼핑·교복은 구조적 축소 국면이에요.",
    "섬유·소재·가죽": "범용 원사·면방은 중국 공급 과잉으로 구조적 약세, 신발 소재는 나이키·아디다스 재고 사이클 회복 대기예요. 가치는 자산(부동산·투자)에 기대는 회사가 많아요.",
}


def eok(v):
    v = round(v / 100)
    return f"{v/10000:,.1f}조" if abs(v) >= 10000 else f"{v:,}억"


def trend(co):
    Q = {k: v for k, v in (co.get("quarterly") or {}).items() if v.get("rev")}
    if len(Q) < 4:
        return ["DART 분기 실적 수집 전이에요. 수집되면 최근 4개 분기 매출 성장률·이익률이 자동으로 채워져요."]
    ks = sorted(Q)[-4:]
    gs = []
    for k in ks:
        p = Q.get(f"{int(k[:4])-1}{k[4:]}", {}).get("rev")
        gs.append(f"{(Q[k]['rev']/p-1)*100:+.0f}%" if p else "-")
    om = [(Q[k].get("op") or 0) / Q[k]["rev"] * 100 for k in ks]
    ni = sum(Q[k].get("ni") or 0 for k in ks)
    return [f"매출 성장률(전년 같은 분기 대비)이 {' → '.join(gs)}였고, {ks[-1]} 매출은 {eok(Q[ks[-1]]['rev'])}원이었어요.",
            f"영업이익률은 {ks[0]} {om[0]:.1f}%에서 {ks[-1]} {om[-1]:.1f}%로 {'올랐어요' if om[-1] > om[0] + 0.5 else '내려왔어요' if om[-1] < om[0] - 0.5 else '비슷했어요'}.",
            f"최근 4개 분기 순이익 합계는 {eok(ni)}원이에요." if ni > 0 else f"최근 4개 분기 순이익 합계는 {eok(-ni)}원 적자예요."]


def nd(t):
    d, ti, u, s, r, i = t
    return {"date": d, "title": ti, "url": u, "src": s, "read": r, "impact": i}


def main():
    src = {}
    for f in sorted(glob.glob(os.path.join(HERE, "co_*.py"))):
        src.update(importlib.import_module(os.path.basename(f)[:-3]).D)
    cfg = json.load(open(os.path.join(CFG, "companies.json"), encoding="utf-8"))
    cp = os.path.join(DATA, "companies.json")
    cos = {c["code"]: c for c in json.load(open(cp, encoding="utf-8"))["companies"]} if os.path.exists(cp) else {}
    grp = {c["code"]: c["group"] for c in cfg}
    news = {k: [nd(n) for n in v["news"]] for k, v in src.items()}
    asof = UPDATED
    for f in sorted(glob.glob(os.path.join(HERE, "news_2*.py"))):
        m = importlib.import_module(os.path.basename(f)[:-3])
        asof = max(asof, getattr(m, "ASOF", asof))
        for key, items in m.ADD.items():
            codes = [c for c in src if key == "@all" or key == "@" + grp.get(c, "")] if key.startswith("@") else [key]
            for c in codes:
                if c not in news:
                    continue
                new = [nd(n) for n in items]
                ts = {n["title"] for n in new}
                news[c] = [n for n in news[c] if n["title"] not in ts] + new
        for code, upd in getattr(m, "UPD", {}).items():
            if code in src:
                src[code]["review"].update(upd)
    from ir_src import IR, IRGO
    # 심층 분석
    deep = {}
    for code, d in src.items():
        x = dict(d["deep"])
        ir = IR.get(code, {})
        x["ir"] = dict(irgo=IRGO.format(code=code), docs=[{"date": a, "title": b, "url": c} for a, b, c in ir.get("docs", [])],
                       strategy=ir.get("strategy", []), targets=[{"item": a, "goal": b, "now": c} for a, b, c in ir.get("targets", [])],
                       feasibility=dict(zip(("tone", "text"), ir["feasibility"])) if ir.get("feasibility") else None,
                       changes=ir.get("changes", []), cross=ir.get("cross", []))
        deep[code] = x
    json.dump({"updated": UPDATED, "news_asof": asof,
               "source": "DART 사업보고서, 회사 IR 자료(IRGO·DART 기업설명회 공시), 2026년 3분기 실적·증권사 보고서와 2026년 8~11월 기사",
               "fisher_questions": FISHER,
               "fisher_note": "필립 피셔 『위대한 기업에 투자하라』의 15가지 질문에 자본 배분(주주환원)을 16번째로 더했어요. 2점 충족, 1점 부분 충족, 0점 미흡이에요. 공개 정보가 적은 항목은 보수적으로(1점) 매겼어요.",
               "disclaimer": "공시·IR 자료·언론 보도를 바탕으로 한 정성 평가이며 투자 권유가 아니에요.",
               "companies": deep}, open(os.path.join(DATA, "deep.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 리뷰
    dk = lambda n: n["date"]
    rv = {}
    for code, d in src.items():
        r = d["review"]
        co = cos.get(code, {})
        dp = os.path.join(ROOT, f"raw/apparel/dart_docs/{code}.json")
        reps = (json.load(open(dp, encoding="utf-8")).get("reports") or []) if os.path.exists(dp) else []
        rep = next((x for x in reps if "반기" in x["report_nm"]), None) or (reps[0] if reps else {})
        rv[code] = {"tone": r["tone"], "title": r["title"], "trend": trend(co), "eval": r["eval"], "watch": r["watch"],
                    "news": sorted(news[code], key=dk, reverse=True)[:10], "next": r["next"],
                    "biz": {"report": rep.get("report_nm", ""), "url": rep.get("url", ""), "mix_title": "", "mix": [], "points": r["points"]} if rep else None}
    json.dump({"updated": UPDATED, "news_asof": asof,
               "period": "2026년 3분기 실적 시즌(한섬·삼성물산 발표, 영원무역·한세실업·F&F·미스토 컨센서스)과 2026년 11월 8일까지의 기사",
               "disclaimer": "공시와 언론 보도를 바탕으로 정리한 참고용 해석이며 투자 권유가 아니에요. 각 기사 아래 '이렇게 보세요'는 기사 내용이 회사 가치에 어떤 의미인지에 대한 해석이에요.",
               "companies": {c["code"]: rv[c["code"]] for c in cfg if c["code"] in rv}},
              open(os.path.join(DATA, "reviews.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 내재가치 가정
    vc = {}
    for code, d in src.items():
        v = d["val"]
        if v.get("skip"):
            vc[code] = {"skip": v["skip"], "cyc_pos": v.get("pos"), "cycle_note": v["skip"]}
            continue
        b, m, u = v["g"]
        vc[code] = {"E1": v["E1"], "g": {"bear": b, "base": m, "bull": u}, "r": v["r"], "c": v["c"], "note": v["note"],
                    "cyc_pos": v["pos"], "cycle_note": INDUSTRY_CYCLE.get(grp.get(code), ""),
                    "cycle": {"phase": v["pos"], "note": v["note"], "w_mid": v["w"]}, **({"nc_adj": False} if v.get("nc") is False else {})}
    vp = os.path.join(CFG, "valuation.json")
    out = {"note": "사이클을 반영한 내재가치예요. ① 정상 이익(E1): 최근 1년 순이익이 아니라 회사별 사이클 위치를 판단해 정한 '사이클 중간' 지배순이익이에요. DART 연간 실적이 들어오면 과거 순이익률 평균(최고·최저 해 제외) × 최근 매출로 구한 사이클 평균 이익을 회사별 비중(w)만큼 섞어요. ② 최근 4개 분기 순이익이 정상 이익보다 높거나 낮은 부분은 사이클 위치에 따라 1~3년만 이어진다고 보고 현재가치만 더하거나 빼요. ③ 성장률(g)은 구조적 성장만 반영해요. ④ 10년 주주잉여현금흐름(이익 × 현금 전환율 c)을 자기자본비용 r로 할인하고 순현금은 더해요(지주사·비지배지분이 큰 회사는 제외).",
           "terminal_growth": 2.0, "asof": UPDATED, "cycle_mode": True, "industry_cycle": INDUSTRY_CYCLE,
           "default": {"g": {"bear": -3.0, "base": 1.0, "bull": 4.0}, "r": 12.0, "c": 0.55, "cyc_pos": "중립",
                       "note": "자동 가정(회사별 검토 전): 과거 순이익률과 추세 매출로 계산한 사이클 평균 이익을 그대로 썼어요."},
           "companies": vc}
    json.dump(out, open(vp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("apparel: deep", len(deep), "reviews", len(rv), "valuation", len(vc), "missing", sorted(set(grp) - set(src)))


if __name__ == "__main__":
    main()
