"""회사별 심층 분석(part_a/b/c.py)을 docs/data/deep.json으로 만든다. 표준 라이브러리만 사용."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from part_a import D as A
from part_b import D as B
from part_c import D as C
from part_d import X as XD
from part_e import X as XE

FISHER = [
 "시장 잠재력: 앞으로 몇 년간 매출을 크게 늘릴 만한 시장을 가졌나",
 "신제품 의지: 기존 제품의 성장이 끝나도 새 제품을 만들어낼 의지가 있나",
 "연구개발 효율: 규모 대비 연구개발이 실제 성과로 이어지나",
 "영업 조직: 평균 이상의 판매 조직을 가졌나",
 "이익률: 충분한 이익률을 내나",
 "이익률 개선 노력: 이익률을 지키거나 높이려는 노력이 있나",
 "노사 관계: 노사 관계가 원만한가",
 "경영진 관계: 경영진 간 협력이 원활한가",
 "경영진의 두께: 핵심 경영진 아래 인재층이 두터운가",
 "원가·회계 관리: 원가 분석과 회계 통제가 잘 되나",
 "업종 고유 강점: 경쟁사보다 나은 업종 특유의 우위가 있나",
 "장기 시각: 단기 이익보다 장기 성장을 보나",
 "희석 위험: 성장을 위해 증자·전환사채로 지분이 희석될 우려가 낮은가",
 "투명성: 나쁜 소식도 솔직하게 알리나",
 "정직성: 경영진의 정직성에 의문이 없나",
 "(추가) 자본 배분: 배당·자사주 등 주주환원이 주주 친화적인가",
]

VERDICT = {"호조": ("실적 호조", "pos"), "사이클": ("사이클 요인", "neu"),
           "구조적": ("구조적 약화", "neg"), "혼합": ("사이클+구조 혼재", "neu")}


def main():
    root = os.path.join(os.path.dirname(__file__), "..", "..")
    comps = {}
    for src in (A, B, C):
        for code, d in src.items():
            assert len(d["fisher"]) == 16, (code, len(d["fisher"]))
            d = dict(d)
            d["fisher"] = [{"s": s, "a": a} for s, a in d["fisher"]]
            d["fisher_score"] = sum(f["s"] for f in d["fisher"])
            x = XD.get(code) or XE.get(code)
            assert x, ("해설 누락", code)
            g = x["diag"]
            d["explain"] = {"title": "", "sections": [{"h": t, "p": b} for t, b in x["explain"]]}
            d["diagnosis"] = {"verdict": VERDICT[g["verdict"]][0], "tone": VERDICT[g["verdict"]][1],
                              "summary": g["reason"], "evidence": g.get("evidence", [])}
            comps[code] = d
    import glob, importlib
    for f in sorted(glob.glob(os.path.join(os.path.dirname(__file__), "explain_*.py"))):
        for code, x in importlib.import_module(os.path.basename(f)[:-3]).E.items():
            if code in comps:
                ex = x["explain"]
                comps[code]["explain"] = {"title": ex.get("title", ""), "sections": [{"h": h, "p": t} for h, t in ex["sections"]]}
                comps[code]["diagnosis"] = x["diagnosis"]
    out = {
        "updated": "2026-11-05",
        "source": "DART 사업보고서(2025.12)·반기보고서(2026.06) 본문, 최근 4개 분기 실적, 2026년 10~11월 기사",
        "fisher_questions": FISHER,
        "fisher_note": "필립 피셔 『위대한 기업에 투자하라』의 15가지 질문에, 자본 배분(주주환원) 항목을 16번째로 더했어요. 2점 충족, 1점 부분 충족, 0점 미흡이에요. 노사·경영진 항목은 공개 정보가 적어 보수적으로 매겼어요.",
        "disclaimer": "공시와 언론 보도를 바탕으로 한 정성 평가이며 투자 권유가 아니에요.",
        "companies": comps,
    }
    p = os.path.join(root, "docs", "data", "deep.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("deep.json", len(comps), "companies")

if __name__ == "__main__":
    main()
