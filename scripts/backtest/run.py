"""적정주가 백테스트 — 기준일 3개(2023·2024·2025년 11월) × 4개 업종 × 모델 변형 8개.

미래참조 차단: 분기 보고서는 분기말+45일(4Q는 90일), 연간은 다음 해 3/31이 지나야 사용. 주가는 기준일 이전 마지막 종가.
모델 선택: 2023·2024 기준일(학습)로만 고르고, 2025 기준일(확인)은 고른 뒤에 성적만 봄.
출력: docs/backtest/data/backtest.json
"""
import json, os, sys, math, datetime as dt, statistics as st
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research as R  # noqa: E402
from model import fair_value, relative, auto_position, VARIANTS  # noqa: E402

NAMES = {"cosmetics": "화장품·미용의료", "semi": "반도체", "chem": "화학·정유", "battery": "2차전지"}
BASE, CHOSEN = "B", "G"
TRAIN, HOLD = (2023, 2024), (2025,)


def verdict(u):
    return "저평가" if u >= 30 else ("고평가" if u <= -30 else "적정권")


def group_stats(rs, key):
    mean = lambda v: round(sum(v) / len(v), 1) if v else None
    med = lambda v: round(st.median(v), 1) if v else None
    srt = sorted(rs, key=lambda r: r[key]["upside"]); t = len(srt) // 3
    out = {}
    for g, v in (("under", [r for r in rs if r[key]["upside"] >= 30]), ("mid", [r for r in rs if -30 < r[key]["upside"] < 30]),
                 ("over", [r for r in rs if r[key]["upside"] <= -30]), ("top3", srt[-t:] if t else []), ("bot3", srt[:t] if t else []), ("all", rs)):
        out[g] = {"n": len(v), "mean": mean([r["ret"] for r in v]), "median": med([r["ret"] for r in v])}
    return out


def main():
    prices = R.load("raw/backtest/prices.json")["prices"]
    out = {"built": dt.date.today().isoformat(), "variants": VARIANTS, "base": BASE, "chosen": CHOSEN,
           "train": list(TRAIN), "hold": list(HOLD), "years": {}, "grid": {}, "index": {}, "industries": {k: {"name": v, "years": {}} for k, v in NAMES.items()}}
    res = {}
    for T0 in R.T0S:
        y = T0.year; T1 = T0.replace(year=y + 1)
        out["years"][y] = {"t0": T0.isoformat(), "t1": T1.isoformat()}
        out["index"][y] = {}
        for k in ("KOSPI", "KOSDAQ"):
            if prices.get(k):
                a, b = R.px(prices[k], T0)[1], R.px(prices[k], T1)[1]
                out["index"][y][k] = round((b / a - 1) * 100, 1)
        for ind in NAMES:
            rows, sc = R.evaluate(ind, T0, prices)
            res[(y, ind)] = sc
            out["grid"].setdefault(str(y), {})[ind] = {v: ({m: round(x, 3 if m == "ic" else 1) for m, x in s.items()} if s else None) for v, s in sc.items()}
            if not rows:
                out["industries"][ind]["years"][y] = {"rows": []}; continue
            med_ret = st.median(r["ret"] for r in rows)
            slim = []
            for r in rows:
                f = r["f"]
                d = {"code": r["code"], "name": r["name"], "group": r["group"], "p0": r["p0"], "p1": r["p1"],
                     "ret": round(r["ret"], 1), "ex_ret": round(r["ret"] - med_ret, 1),
                     "per0": round(r["mcap"] / f["ttm_ni"], 1) if f["ttm_ni"] > 0 else None,
                     "pos": auto_position(f), "period": f["period"]}
                for key in (BASE, CHOSEN):
                    v = r.get(key)
                    if v:
                        u = (v["base"] / r["mcap"] - 1) * 100
                        d[key] = {"fair": round(v["base"] * 1e6 / r["nsh"]), "bear": round(v["bear"] * 1e6 / r["nsh"]),
                                  "bull": round(v["bull"] * 1e6 / r["nsh"]), "upside": round(u, 1), "verdict": verdict(u)}
                slim.append(d)
            yr = {"rows": slim, "median_ret": round(med_ret, 1), "mean_ret": round(st.mean(r["ret"] for r in rows), 1)}
            for key in (BASE, CHOSEN):
                rs = [r for r in slim if r.get(key)]
                if len(rs) >= 6:
                    yr[key] = dict(out["grid"][str(y)][ind][key], groups=group_stats(rs, key))
            out["industries"][ind]["years"][y] = yr
            print(y, ind, len(rows))
    out["summary"] = {"train": R.summary(res, TRAIN), "hold": R.summary(res, HOLD)}
    # 판정의 크기: 학습 기간에서 '업종 대비 log 괴리'가 1년 초과수익을 얼마나 설명했나(회귀 기울기)
    xs, ys = [], []
    for T0 in R.T0S[:2]:
        for ind in NAMES:
            rows, par = R.universe(ind, T0, prices)
            rs = [(fair_value(r["f"], par, CHOSEN), r) for r in rows]
            rs = [(v, r) for v, r in rs if v]
            if len(rs) < 6: continue
            lg = [math.log(v["base"] / r["mcap"]) for v, r in rs]; lr = [math.log(r["p1"] / r["p0"]) for _, r in rs]
            mg, mr = st.median(lg), st.median(lr)
            xs += [max(-2, min(2, a - mg)) for a in lg]; ys += [b - mr for b in lr]
    mx, my = st.mean(xs), st.mean(ys)
    out["beta"] = round(sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs), 3)
    os.makedirs(os.path.join(R.ROOT, "docs/backtest/data"), exist_ok=True)
    with open(os.path.join(R.ROOT, "docs/backtest/data/backtest.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print("beta", out["beta"])


if __name__ == "__main__":
    main()
