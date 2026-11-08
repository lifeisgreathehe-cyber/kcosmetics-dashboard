"""여러 기준일 × 업종 × 모델 변형을 비교. 2023·2024 기준일 = 고르는 용도, 2025 기준일 = 확인용(홀드아웃)."""
import json, os, sys, datetime as dt, statistics as st
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model import features, fair_value, relative, VARIANTS  # noqa: E402

T0S = [dt.date(2023, 11, 6), dt.date(2024, 11, 5), dt.date(2025, 11, 5)]
IND = {"cosmetics": ("docs/data", "config"), "semi": ("docs/semi/data", "config/semi"),
       "chem": ("docs/chem/data", "config/chem"), "battery": ("docs/battery/data", "config/battery")}
COMMON = {"g": {"bear": 0.0, "base": 5.0, "bull": 10.0}, "r": 10.5, "c": 0.7}


def load(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return json.load(f)


def q_ok(k, asof):
    y, q = int(k[:4]), int(k[-1])
    end = dt.date(y, q * 3, 30 if q in (2, 3) else 31)
    return end + dt.timedelta(days=90 if q == 4 else 45) <= asof


def a_ok(y, asof):
    return dt.date(int(y) + 1, 3, 31) <= asof


def px(series, day):
    d = series["d"]; i = None
    lo, hi = 0, len(d) - 1
    while lo <= hi:
        m = (lo + hi) // 2
        if d[m] <= day.isoformat(): i = m; lo = m + 1
        else: hi = m - 1
    return (d[i], series["c"][i]) if i is not None else (None, None)


def spearman(x, y):
    if len(x) < 5: return None
    rk = lambda v: {i: n for n, i in enumerate(sorted(range(len(v)), key=lambda i: v[i]))}
    rx, ry = rk(x), rk(y); n = len(x)
    return 1 - 6 * sum((rx[i] - ry[i]) ** 2 for i in range(n)) / (n * (n * n - 1))


def universe(ind, T0, prices, par_mode="industry"):
    dd, cd = IND[ind]
    cos = load(dd + "/companies.json")["companies"]
    dft = load(cd + "/valuation.json").get("default") or COMMON
    par = {"g": dft["g"], "r": dft["r"], "c": dft["c"]} if par_mode == "industry" else COMMON
    T1 = T0.replace(year=T0.year + 1)
    out = []
    for co in cos:
        Q = {k: v for k, v in (co.get("quarterly") or {}).items() if q_ok(k, T0)}
        A = {y: v for y, v in (co.get("annual") or {}).items() if a_ok(y, T0)}
        f = features(A, Q)
        if not f: continue
        # 최근 분기가 너무 오래됐으면 제외(분기 실적 누락)
        last = sorted(Q)[-1]; ly, lq = int(last[:4]), int(last[-1])
        if (T0.year * 4 + (T0.month - 1) // 3) - (ly * 4 + lq - 1) > 3: continue
        s = prices.get(co["code"])
        sh = (co.get("shares") or {})
        common = sh.get("common")
        if not s or not common: continue
        d0, p0 = px(s, T0); d1, p1 = px(s, T1)
        if not p0 or not p1 or d0 < (T0 - dt.timedelta(days=10)).isoformat() or d1 < (T1 - dt.timedelta(days=10)).isoformat() or s["d"][0] > (T0 - dt.timedelta(days=20)).isoformat():
            continue
        pref, psh = co.get("pref"), sh.get("pref") or 0
        pp0 = px(prices[pref], T0)[1] if pref and psh and prices.get(pref) else None
        if not pp0: psh = 0
        mcap = (p0 * common + (pp0 or 0) * psh) / 1e6
        out.append({"code": co["code"], "name": co["name"], "group": co.get("group"), "market": co.get("market"),
                    "p0": p0, "p1": p1, "ret": (p1 / p0 - 1) * 100, "mcap": mcap, "nsh": common + psh, "f": f})
    return out, par


def score(rows, key):
    rs = [r for r in rows if r.get(key)]
    if len(rs) < 6: return None
    for r in rs: r["_up"] = (r[key]["base"] / r["mcap"] - 1) * 100
    med_ret = st.median(r["ret"] for r in rs)
    med_up = st.median(r["_up"] for r in rs)
    srt = sorted(rs, key=lambda r: r["_up"]); t = len(srt) // 3
    mean = lambda v: sum(v) / len(v)
    return {"n": len(rs), "ic": spearman([r["_up"] for r in rs], [r["ret"] for r in rs]),
            "spread": mean([r["ret"] for r in srt[-t:]]) - mean([r["ret"] for r in srt[:t]]),
            "spread_med": st.median([r["ret"] for r in srt[-t:]]) - st.median([r["ret"] for r in srt[:t]]),
            "hit_rel": sum(1 for r in rs if (r["_up"] > med_up) == (r["ret"] > med_ret)) / len(rs) * 100,
            "hit_abs": sum(1 for r in rs if (r["_up"] > 0) == (r["ret"] > 0)) / len(rs) * 100,
            "mape": st.median([abs(r[key]["base"] / r["mcap"] * r["p0"] / r["p1"] - 1) * 100 for r in rs]),
            "naive": st.median([abs(r["p0"] / r["p1"] - 1) * 100 for r in rs]),
            "med_up": st.median([r["_up"] for r in rs])}


def evaluate(ind, T0, prices):
    rows, par = universe(ind, T0, prices)
    for v in VARIANTS:
        for r in rows:
            r[v] = fair_value(r["f"], par, v)
        if v == "F":
            relative(rows, "F", 0.5)
    return rows, {v: score(rows, v) for v in VARIANTS}


if __name__ == "__main__":
    prices = load("raw/backtest/prices.json")["prices"]
    res = {}
    for T0 in T0S:
        for ind in IND:
            rows, sc = evaluate(ind, T0, prices)
            res[(T0.year, ind)] = sc
            print(f"\n== {T0} {ind} n={len(rows)}")
            for v, s in sc.items():
                if s: print(f"  {v} n={s['n']:3d} IC={s['ic']:+.2f} spread={s['spread']:+6.1f} (med {s['spread_med']:+6.1f}) hitrel={s['hit_rel']:4.0f} hitabs={s['hit_abs']:4.0f} mape={s['mape']:4.0f} naive={s['naive']:4.0f} medup={s['med_up']:+4.0f}")


def summary(res, years):
    out = {}
    for v in VARIANTS:
        cells = [res[k][v] for k in res if k[0] in years and res[k].get(v)]
        if cells:
            out[v] = {m: round(sum(c[m] for c in cells) / len(cells), 2) for m in ("ic", "spread", "spread_med", "hit_rel", "hit_abs", "mape", "naive")}
            out[v]["cells"] = len(cells)
    return out
