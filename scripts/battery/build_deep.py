"""2차전지 회사별 심층 분석(deep_*.py) → docs/battery/data/deep.json"""
import glob, importlib, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "deep"))
from build import FISHER  # noqa: E402


def conv(code, d):
    d = dict(d)
    rows = [l.strip() for l in d["fisher"].strip().split("\n") if l.strip()]
    assert len(rows) == 16, (code, len(rows))
    d["fisher"] = [{"s": int(l[0]), "a": l[2:].strip()} for l in rows]
    d["fisher_score"] = sum(f["s"] for f in d["fisher"])
    t, secs = d.pop("explain")
    d["explain"] = {"title": t, "sections": [{"h": h, "p": p} for h, p in secs]}
    v, tone, summ, cyc, st, chk = d.pop("diagnosis")
    d["diagnosis"] = {"verdict": v, "tone": tone, "summary": summ, "cycle": cyc, "structural": st, "check": chk}
    return d


def main():
    comps = {}
    for f in sorted(glob.glob(os.path.join(HERE, "deep_*.py"))):
        for code, d in importlib.import_module(os.path.basename(f)[:-3]).D.items():
            comps[code] = conv(code, d)
    out = {
        "updated": "2026-11-05",
        "source": "DART 사업보고서·분기보고서, 각사 실적 발표, 2026년 7~11월 기사, KOSIS·관세청 업황 지표",
        "fisher_questions": FISHER,
        "fisher_note": "필립 피셔 『위대한 기업에 투자하라』의 15가지 질문에, 자본 배분(주주환원) 항목을 16번째로 더했어요. 2점 충족, 1점 부분 충족, 0점 미흡이에요. 노사·경영진 항목은 공개 정보가 적으면 보수적으로(1점) 매겼어요.",
        "disclaimer": "공시와 언론 보도를 바탕으로 한 정성 평가이며 투자 권유가 아니에요.",
        "companies": comps,
    }
    with open(os.path.join(ROOT, "docs", "battery", "data", "deep.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("deep.json", len(comps), "companies")


if __name__ == "__main__":
    main()
