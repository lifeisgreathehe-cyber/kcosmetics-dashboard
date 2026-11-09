"""음식료 회사별 원고(scripts/food/co_*.py의 D·V) → docs/food/data/deep.json, config/food/valuation.json
실행: python scripts/food/build_deep.py  (그다음 python scripts/build_valuation.py --industry food)"""
import glob, importlib, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "deep"))
from build import FISHER  # noqa: E402

VAL_NOTE = ("사이클을 반영한 내재가치예요. ① 정상 이익(E1): 최근 1년 순이익이 아니라, DART 10년 연간 순이익률(가장 좋은 해·나쁜 해를 뺀 평균)과 추세 매출로 "
            "'사이클 평균 이익'을 계산하고, 회사별로 판단한 정상 순이익률(margin)이나 조정 배수(E1_adj)를 적용해요. 음식료는 경기보다 원가 사이클"
            "(곡물·원당·유지·환율 → 1~2분기 뒤 마진, 가격 인상 후 회복)과 과징금 같은 일회성 손익이 이익을 흔들어요. ② 사이클 초과(부족) 이익: 최근 4개 분기 "
            "순이익이 정상 이익보다 높거나 낮은 부분은 사이클 위치(상승기·중립·하강기·바닥권 등)에 따라 1~3년만 이어진다고 보고 그 현재가치만 더하거나 빼요. "
            "③ 성장률(g)은 해외 확장 같은 구조적 성장만 반영해요. ④ 10년 주주잉여현금흐름(이익 × 현금 전환율 c)을 자기자본비용 r로 할인, 6~10년차 성장률은 2%로 수렴, "
            "순현금은 더하고 차입은 빼요.")


def mods():
    return [importlib.import_module(os.path.basename(f)[:-3]) for f in sorted(glob.glob(os.path.join(HERE, "co_*.py")))]


def main():
    comps, val = {}, {}
    for m in mods():
        comps.update(m.D)
        val.update(getattr(m, "V", {}))
    # 공정위 담합 과징금(영업외 일회성)으로 최근 4개 분기 순이익이 적자인 회사: 사이클 부족 이익으로 2년 더 이어진다고 보면 안 돼요.
    # 최근 4개 분기 영업이익 × 0.7(법인세·이자 근사)을 '일회성을 뺀 최근 이익'으로 써요(2026Q2 DART 기준, 억원).
    FINE = {"001680": 1222, "003960": 644, "145990": 792, "008040": 224, "001790": 367}
    for code, ni in FINE.items():
        if code in val:
            val[code]["ni_now"] = ni
            val[code]["ni_now_note"] = "공정위 과징금(일회성)을 뺀 최근 이익(최근 4개 분기 영업이익 × 0.7)"
    # 사조동아원은 2026년 6월 10:1 주식병합. DART 2분기 주식수(1억4,095만주)가 병합 전이라 병합 후 주식수를 써요.
    if "008040" in val:
        val["008040"]["snapshot"] = {"shares": 14094619}
    out = {"updated": "2026-11-08",
           "source": "DART 사업보고서·분기보고서, 각사 실적 발표, 2026년 7~11월 기사, KOSIS·관세청 업황 지표",
           "fisher_questions": FISHER,
           "fisher_note": "필립 피셔 『위대한 기업에 투자하라』의 15가지 질문에 자본 배분(주주환원)을 16번째로 더했어요. 2점 충족, 1점 부분 충족, 0점 미흡이에요. 노사·경영진 항목은 공개 정보가 적으면 보수적으로(1점) 매겼어요.",
           "disclaimer": "공시와 언론 보도를 바탕으로 한 정성 평가이며 투자 권유가 아니에요.",
           "companies": comps}
    with open(os.path.join(ROOT, "docs", "food", "data", "deep.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    cfg = {"note": VAL_NOTE, "terminal_growth": 2.0, "asof": "2026-11-08", "cycle_mode": True, "debt_mode": "levered",
           "default": {"g": {"bear": -1.0, "base": 3.0, "bull": 6.0}, "r": 9.0, "c": 0.7, "cyc_pos": "중립",
                       "note": "자동 가정: 과거 10년 순이익률과 추세 매출로 계산한 사이클 평균 이익을 그대로 썼어요."},
           "industry_cycle": {
               "종합식품": "곡물·유지·환율 원가가 3분기에 정점을 지나고, 7~9월 가격 인상이 4분기부터 반영되는 '원가 부담 후반' 국면이에요. 공정위 담합 조사로 내수 가격 결정력은 약해졌어요.",
               "라면": "해외(미국·중국·유럽) 수요가 구조적으로 커지는 성장 국면이에요. 국내는 가격 인상과 담합 조사가 동시에 걸려 있어요.",
               "제과·빙과·제빵": "카카오·유지 원가 부담이 1년 넘게 이어진 뒤 정점을 지나는 회복 초입이에요. 해외 법인 비중이 큰 회사가 앞서 회복해요.",
               "유가공": "출산율 하락과 수입 멸균유 증가로 국내 흰우유는 구조적 축소, 단백질·컵커피·수출이 대안이에요.",
               "음료·주류": "음주 인구 감소와 경기 둔화로 주류는 구조적 둔화, 음료는 제로·건강 트렌드로 정체 속 믹스 개선 국면이에요.",
               "소재(제분·제당·전분)": "국제 곡물·원당 가격 상승기에 담합 과징금과 가격 인하 압력이 겹친 '이익 압박' 국면이에요.",
               "수산": "어가(참치 등)와 어획량 변동이 이익을 좌우해요. 2026년은 참치 어가 약세·어획 부진에서 회복 중이에요.",
               "육류·사료": "닭고기·돼지고기 시세는 3~4년 주기의 공급 사이클을 타요. 2026년 상반기 닭고기값 급등 뒤 공급이 늘며 정상화 중이고, 사료는 곡물 상승을 1~2분기 늦게 가격에 넘겨요.",
               "식자재·급식": "외식 경기 둔화로 식자재 유통 마진이 눌리고, 단체급식은 식수 회복·가격 인상으로 안정적인 국면이에요.",
               "담배·인삼": "국내 담배는 정체지만 해외 궐련·전자담배가 성장하는 경기 방어 + 구조 성장 국면이에요."},
           "companies": val}
    with open(os.path.join(ROOT, "config", "food", "valuation.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    from ir_data import IR
    ira = {"updated": "2026-11-08",
           "note": "IR 자료(실적 발표, 기업가치 제고 계획, 인베스터 데이)와 그 보도를 바탕으로 성장전략의 달성 가능성을 판단하고, 경쟁사·공급사·고객사 자료와 대조했어요. 원문 PDF는 IRGO(KIND 공시 IR)에서 자동으로 받아 링크해요.",
           "companies": {}}
    for code, x in IR.items():
        ira["companies"][code] = {
            "asof": x["asof"], "deck": x["deck"], "summary": x["summary"], "verdict": x["verdict"],
            "strategy": [{"h": h, "claim": c, "feas": f, "why": w} for h, c, f, w in x["strategy"]],
            "changes": x["changes"],
            "cross": [{"who": a, "rel": b, "src": c, "read": d} for a, b, c, d in x["cross"]],
            "docs": [{"date": d, "title": t, "url": u} for d, t, u in x["docs"]]}
    with open(os.path.join(ROOT, "docs", "food", "data", "ir_analysis.json"), "w", encoding="utf-8") as f:
        json.dump(ira, f, ensure_ascii=False, indent=1)
    print("deep.json", len(comps), "companies · valuation.json", len(val))


if __name__ == "__main__":
    main()
