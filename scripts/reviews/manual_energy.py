"""에너지·전력 3분기(2026Q3) 실적 리뷰 — 손으로 쓴 원고 (2026-11-22).
원고 본문은 scripts/energy/deep_*.py 의 review 항목(회사별 3분기 실적·사이클 판단)을 그대로 쓴다.
refresh.py 는 basis(2026Q3) 이상의 분기가 들어오기 전까지 이 원고를 쓰고, 4분기 실적이 들어오면 자동 원고로 바뀐다.
'실적 동향'(trend) 숫자 문장은 build_deep.py 가 DART 숫자로 만든 것을 그대로 둔다."""
import glob, importlib, json, os, sys

B = "2026Q3"
A = "2026-11-22"
_HERE = os.path.dirname(os.path.abspath(__file__))
_ENERGY = os.path.join(_HERE, "..", "energy")


def _build():
    sys.path.insert(0, _ENERGY)
    try:
        for p in sorted(glob.glob(os.path.join(_ENERGY, "deep_*.py"))):
            importlib.import_module(os.path.basename(p)[:-3])
        D = importlib.import_module("common").D
    finally:
        sys.path.remove(_ENERGY)
    try:
        cur = json.load(open(os.path.join(_HERE, "..", "..", "docs", "energy", "data", "reviews.json"), encoding="utf-8"))["companies"]
    except Exception:
        cur = {}
    out = {}
    for code, d in D.items():
        r = d["review"]
        c = cur.get(code) or {}
        trend = (c.get("_base") or c).get("trend") or []
        out[code] = {"basis": B, "asof": A, "tone": r["tone"], "title": r["title"], "trend": trend,
                     "eval": r["eval"], "watch": r["watch"], "next": r["next"]}
    return out


REV = _build()
