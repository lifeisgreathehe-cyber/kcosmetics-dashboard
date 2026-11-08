"""화학·정유 회사별 심층 분석(scripts/chem/deep_*.py의 D) → docs/chem/data/deep.json"""
import datetime, glob, importlib, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "deep"))
from build import FISHER


def main():
    comps = {}
    for f in sorted(glob.glob(os.path.join(HERE, "deep_*.py"))):
        comps.update(importlib.import_module(os.path.basename(f)[:-3]).D)
    # 매일 쓰는 뉴스 해석(scripts/chem/news_YYYYMMDD.py의 NEWS)을 회사별 news에 합친다: 같은 제목은 새 해석으로, 최신 8개까지
    asof = None
    for f in sorted(glob.glob(os.path.join(HERE, "news_*.py"))):
        m = importlib.import_module(os.path.basename(f)[:-3])
        asof = getattr(m, "ASOF", asof)
        for code, items in m.NEWS.items():
            if code not in comps:
                continue
            new = [dict(date=d, title=t, url=u, src=s, read=r, impact=i) for d, t, u, s, r, i in items]
            ts = {n["title"] for n in new}
            old = [n for n in comps[code].get("news", []) if n["title"] not in ts]
            comps[code]["news"] = sorted(new + old, key=lambda n: n["date"], reverse=True)[:8]
    # IR 분석(scripts/chem/ir_*.py의 IRS {code: IR(...)})을 회사별 ir로 합친다
    for f in sorted(glob.glob(os.path.join(HERE, "ir_*.py"))):
        m = importlib.import_module(os.path.basename(f)[:-3])
        for code, v in m.IRS.items():
            if code in comps:
                comps[code]["ir"] = v
    out = {"updated": datetime.date.today().isoformat(), "news_asof": asof,
           "source": "DART 사업보고서·반기보고서, 2026년 3분기 잠정실적과 2026년 10~11월 기사",
           "fisher_questions": FISHER,
           "fisher_note": "필립 피셔 『위대한 기업에 투자하라』의 15가지 질문에 자본 배분(주주환원)을 16번째로 더했어요. 2점 충족, 1점 부분 충족, 0점 미흡이에요. 노사·경영진 항목은 공개 정보가 적어 보수적으로 매겼어요.",
           "disclaimer": "공시와 언론 보도를 바탕으로 한 정성 평가이며 투자 권유가 아니에요.",
           "companies": comps}
    with open(os.path.join(HERE, "..", "..", "docs", "chem", "data", "deep.json"), "w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=1)
    print("deep.json", len(comps), "companies")


if __name__ == "__main__":
    main()
