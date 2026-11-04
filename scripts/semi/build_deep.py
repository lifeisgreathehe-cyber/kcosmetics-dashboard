"""반도체 회사별 심층 분석(deep_a/b/c.py) → docs/semi/data/deep.json"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "deep"))
from build import FISHER
from deep_a import D as A
from deep_b import D as B
from deep_c import D as C

def main():
    root = os.path.join(os.path.dirname(__file__), "..", "..")
    comps = {}
    for src in (A, B, C):
        for code, d in src.items():
            d = dict(d)
            rows = [l.strip() for l in d["fisher"].strip().split("\n")]
            assert len(rows) == 16, (code, len(rows))
            d["fisher"] = [{"s": int(l[0]), "a": l[2:].strip()} for l in rows]
            d["fisher_score"] = sum(f["s"] for f in d["fisher"])
            comps[code] = d
    out = {
        "updated": "2026-11-04",
        "source": "DART 사업보고서(2025.12)·반기보고서(2026.06) 본문, 최근 4개 분기 실적, 2026년 10~11월 기사",
        "fisher_questions": FISHER,
        "fisher_note": "필립 피셔 『위대한 기업에 투자하라』의 15가지 질문에, 자본 배분(주주환원) 항목을 16번째로 더했어요. 2점 충족, 1점 부분 충족, 0점 미흡이에요. 노사·경영진 항목은 공개 정보가 적어 보수적으로(1점) 매겼어요.",
        "disclaimer": "공시와 언론 보도를 바탕으로 한 정성 평가이며 투자 권유가 아니에요.",
        "companies": comps,
    }
    with open(os.path.join(root, "docs", "semi", "data", "deep.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("deep.json", len(comps), "companies")

if __name__ == "__main__":
    main()
