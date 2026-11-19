"""자동차 회사별 원고(scripts/auto/co_*.py의 co(...)) → docs/auto/data/deep.json, config/auto/valuation.json, docs/auto/data/ir_analysis.json
실행: python scripts/auto/build_deep.py  (그다음 python scripts/auto/build_reviews.py, python scripts/build_valuation.py --industry auto)"""
import glob, importlib, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "deep"))
from build import FISHER  # noqa: E402
import common  # noqa: E402

ASOF = "2026-11-14"
VAL_NOTE = ("사이클을 반영한 내재가치예요. ① 정상 이익(E1): 최근 1년 순이익이 아니라, 회사별로 판단한 사이클 중간 이익을 써요. 사람이 직접 정한 E1(억원)이 "
            "있으면 그것을, 없으면 DART 10년 연간 순이익률(최고·최저 해 제외 평균, 일회성 손익 보정)과 추세 매출로 계산한 '사이클 평균 이익'에 정상 순이익률(margin) "
            "또는 조정 배수(E1_adj)를 적용해요. 자동차는 판매량(금리·소비 경기), 환율, 미국 관세(2025년 25% → 15%), 원자재(강판·알루미늄·고무), 인센티브 경쟁과 "
            "파업 같은 일회성 생산 차질이 이익을 흔들어요. ② 사이클 초과(부족) 이익: 최근 4개 분기 순이익이 정상 이익보다 높거나 낮은 부분은 사이클 위치에 따라 "
            "1~3년만 이어진다고 보고 그 현재가치만 더하거나 빼요. ③ 성장률(g)은 하이브리드·현지 생산·전장처럼 구조적 성장만 반영해요. ④ 10년 주주잉여현금흐름"
            "(이익 × 현금 전환율 c)을 자기자본비용 r로 할인, 6~10년차 성장률은 2%로 수렴, 순현금은 더하고 순차입은 이미 이자비용이 이익에서 빠져 있어 따로 빼지 않아요.")


def mods():
    return [importlib.import_module(os.path.basename(f)[:-3]) for f in sorted(glob.glob(os.path.join(HERE, "co_*.py")))]


def main():
    ms = mods()
    for f in sorted(glob.glob(os.path.join(HERE, "news_*.py"))):  # 날짜별 보강: VAL 덮어쓰기
        m = importlib.import_module(os.path.basename(f)[:-3])
        for code, vo in getattr(m, "VAL", {}).items():
            if code in common.VAL:
                common.VAL[code] = {k: v for k, v in dict(common.VAL[code], **vo).items() if not (k == "E1_adj" and "margin" in vo)}
    out = {"updated": ASOF,
           "source": "DART 사업보고서·분기보고서, 각사 실적 발표·IR(인베스터 데이), 2026년 1~11월 기사, KOSIS·관세청·산업통상부 자동차산업 동향",
           "fisher_questions": FISHER,
           "fisher_note": "필립 피셔 『위대한 기업에 투자하라』의 15가지 질문에 자본 배분(주주환원)을 16번째로 더했어요. 2점 충족, 1점 부분 충족, 0점 미흡이에요. 노사·경영진 항목은 공개 정보가 적으면 보수적으로(1점) 매겼어요. 자동차는 노조 파업이 실적에 직접 영향을 주기 때문에 노사 항목을 실제 파업 이력으로 매겼어요.",
           "disclaimer": "공시와 언론 보도를 바탕으로 한 정성 평가이며 투자 권유가 아니에요.",
           "companies": common.D}
    with open(os.path.join(ROOT, "docs", "auto", "data", "deep.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    cfg = {"note": VAL_NOTE, "terminal_growth": 2.0, "asof": ASOF, "cycle_mode": True, "debt_mode": "levered",
           "default": {"g": {"bear": -2.0, "base": 2.0, "bull": 5.0}, "r": 10.0, "c": 0.6, "cyc_pos": "중립",
                       "note": "자동 가정: 과거 10년 순이익률과 추세 매출로 계산한 사이클 평균 이익을 그대로 썼어요."},
           "industry_cycle": {
               "완성차": "2023년 정점(현대차 영업이익 15.1조원) 이후 미국 관세(2025년 25%, 11월부터 15%)·인센티브 경쟁·원자재로 3년째 이익이 줄어드는 '이익 하강기 후반'이에요. 판매량은 하이브리드 덕에 버티지만 대당 이익이 낮아졌어요. 관세는 현지 생산 확대(2029년 미국 판매의 80%)로 줄여가는 비용이에요.",
               "모듈·핵심부품": "완성차 감산(파업·중동 판매 차질)의 영향을 받지만, 전동화 부품과 A/S가 받쳐주는 '중립' 국면이에요. 미국 관세는 완성차가 대부분 분담했어요.",
               "차체·섀시": "현대차·기아 생산량에 1~2개월 시차로 연동돼요. 2024~25년 미국 공장(HMGMA) 증설 투자를 마치고 가동률이 오르는 구간이지만, 2026년 3분기는 파업으로 일시 감소했어요.",
               "파워트레인·구동": "엔진 부품은 구조적 축소, 하이브리드 변속기·감속기·전동화 부품은 성장하는 '세대 교체' 국면이에요. 회사별로 내연기관 비중에 따라 사이클보다 구조 변화가 더 중요해요.",
               "내외장": "차량 생산 대수에 비례하는 저마진 물량 사업이에요. 미국·인도 현지 공장 비중이 높은 회사가 관세를 덜 맞아요.",
               "전장·자율주행": "램프·커넥터·와이어링은 차량 생산과 함께, 자율주행 센서·SW는 신차 채택 주기에 따라 움직여요. 자율주행 소형사는 아직 적자 투자 국면이에요.",
               "타이어·고무": "2023~24년 원재료 하락기 호황 뒤, 2026년은 천연고무·운임 상승과 미국 관세로 이익률이 회사별로 갈리는 국면이에요(미국 공장·고인치 비중이 핵심).",
               "유통·렌탈": "고금리로 중고차·렌터카 수요가 눌렸다가 금리 인하로 회복을 기다리는 '바닥권~회복 초입'이에요. 롯데렌탈·케이카 모두 지배구조 변화(매각·인수)가 있었어요."},
           "companies": common.VAL}
    with open(os.path.join(ROOT, "config", "auto", "valuation.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    from ir_data import IR
    ira = {"updated": ASOF,
           "note": "IR 자료(실적 발표, CEO 인베스터 데이, 기업가치 제고 계획)와 그 보도를 바탕으로 성장전략의 달성 가능성을 판단하고, 경쟁사·공급사·고객사 자료와 대조했어요. 원문 PDF는 IRGO(KIND 공시 IR)에서 자동으로 받아 링크해요.",
           "companies": {}}
    for code, x in IR.items():
        ira["companies"][code] = {
            "asof": x["asof"], "deck": x["deck"], "summary": x["summary"], "verdict": x["verdict"],
            "strategy": [{"h": h, "claim": c, "feas": f, "why": w} for h, c, f, w in x["strategy"]],
            "changes": x["changes"],
            "cross": [{"who": a, "rel": b, "src": c, "read": d} for a, b, c, d in x["cross"]],
            "docs": [{"date": d, "title": t, "url": u} for d, t, u in x["docs"]]}
    with open(os.path.join(ROOT, "docs", "auto", "data", "ir_analysis.json"), "w", encoding="utf-8") as f:
        json.dump(ira, f, ensure_ascii=False, indent=1)
    print("deep.json", len(common.D), "companies · valuation.json", len(common.VAL), "· IR", len(IR))


if __name__ == "__main__":
    main()
