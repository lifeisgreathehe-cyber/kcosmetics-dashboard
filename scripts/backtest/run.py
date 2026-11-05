"""적정주가 1년 백테스트 — 미래참조 없이 과거 시점(T0)의 데이터만으로 적정가를 다시 계산하고 1년 뒤 실제 주가와 비교.

규칙(기계식, 사람 판단 없음):
- T0 시점에 '공시되어 있던' 실적만 사용: 분기 보고서는 분기말+45일(Q4는 사업보고서로 90일), 연간은 다음 해 3/31 이후.
  → T0=2025-11-05면 분기는 2025Q2까지, 연간은 2024년까지.
- 주가는 T0 이전 마지막 거래일 종가. 결과는 T0+1년 이전 마지막 거래일 종가(분할 조정, 배당 제외).
- 방법 A(TTM): 최근 4개 분기 지배순이익을 정상 이익으로.
- 방법 B(정상화): build_valuation.cycle_base — 연간 순이익률(6년 이상이면 최고·최저 해 제외) 평균 × 추세 매출.
- 할인 모델·성장 경로는 build_valuation.equity_value 그대로, 파라미터는 업종 공통 기본값(회사별 가정·사이클 위치·뉴스는 쓰지 않음).
- 순현금 조정 제외(과거 시점 재무상태표가 저장돼 있지 않음). 주식수는 현재 DART 유통주식수.
"""
import json, os, sys, math, datetime as dt, statistics as st

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from build_valuation import equity_value, cycle_base  # noqa: E402

T0 = dt.date(2025, 11, 5)
T1 = dt.date(2026, 11, 5)
IND = {
    "cosmetics": {"name": "화장품·미용의료", "data": "docs/data", "cfg": "config"},
    "semi": {"name": "반도체", "data": "docs/semi/data", "cfg": "config/semi"},
    "chem": {"name": "화학·정유", "data": "docs/chem/data", "cfg": "config/chem"},
    "battery": {"name": "2차전지", "data": "docs/battery/data", "cfg": "config/battery"},
}
# 화장품 설정에는 업종 기본값이 없어 미리 정한 중립값을 씀(결과를 보고 고친 값이 아님)
COSMETICS_DEFAULT = {"g": {"bear": 0.0, "base": 5.0, "bull": 10.0}, "r": 9.5, "c": 0.75}
GT = 2.0


def load(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return json.load(f)


def q_available(k, asof):
    y, q = int(k[:4]), int(k[-1])
    end = dt.date(y, q * 3, 30 if q in (2, 3) else 31)
    return end + dt.timedelta(days=90 if q == 4 else 45) <= asof


def a_available(y, asof):
    return dt.date(int(y) + 1, 3, 31) <= asof


def px_on(series, day):
    """day 이전(포함) 마지막 거래일 종가."""
    d, c = series["d"], series["c"]
    i = max((j for j, x in enumerate(d) if x <= day.isoformat()), default=None)
    return (d[i], c[i], i) if i is not None else (None, None, None)


def spearman(x, y):
    def rk(v):
        o = sorted(range(len(v)), key=lambda i: v[i]); r = [0] * len(v)
        for n, i in enumerate(o): r[i] = n
        return r
    if len(x) < 5: return None
    rx, ry = rk(x), rk(y); n = len(x)
    return round(1 - 6 * sum((a - b) ** 2 for a, b in zip(rx, ry)) / (n * (n * n - 1)), 3)


def summarize(rows, key):
    rs = [r for r in rows if r.get(key)]
    if not rs: return None
    up = [r[key]["upside"] for r in rs]; ret = [r["ret"] for r in rs]; exr = [r["ex_ret"] for r in rs]
    under = [r for r in rs if r[key]["upside"] >= 30]; over = [r for r in rs if r[key]["upside"] <= -30]
    mid = [r for r in rs if -30 < r[key]["upside"] < 30]
    srt = sorted(rs, key=lambda r: r[key]["upside"]); t = len(srt) // 3
    top, bot = srt[-t:] if t else [], srt[:t] if t else []
    mean = lambda v: round(sum(v) / len(v), 1) if v else None
    med = lambda v: round(st.median(v), 1) if v else None
    return {
        "n": len(rs),
        "hit_abs": round(sum(1 for r in rs if (r[key]["upside"] > 0) == (r["ret"] > 0)) / len(rs) * 100, 1),
        "hit_rel": round(sum(1 for r in rs if (r[key]["upside"] > 0) == (r["ex_ret"] > 0)) / len(rs) * 100, 1),
        "mape_fair": med([abs(r[key]["fair"] / r["p1"] - 1) * 100 for r in rs]),
        "mape_naive": med([abs(r["p0"] / r["p1"] - 1) * 100 for r in rs]),
        "closer": round(sum(1 for r in rs if abs(r["p1"] - r[key]["fair"]) < abs(r["p0"] - r[key]["fair"])) / len(rs) * 100, 1),
        "within20": round(sum(1 for r in rs if abs(r[key]["fair"] / r["p1"] - 1) <= .2) / len(rs) * 100, 1),
        "spearman": spearman(up, ret),
        "groups": {g: {"n": len(v), "mean": mean([r["ret"] for r in v]), "median": med([r["ret"] for r in v]),
                       "ex_mean": mean([r["ex_ret"] for r in v]),
                       "hit_pos": round(sum(1 for r in v if r["ret"] > 0) / len(v) * 100, 1) if v else None}
                   for g, v in (("under", under), ("mid", mid), ("over", over), ("top3", top), ("bot3", bot), ("all", rs))},
        "median_upside": med(up),
    }


def finding(I):
    """숫자에서 바로 만드는 요약 문장(다시 돌려도 숫자와 어긋나지 않게)."""
    A, B = I["A"], I["B"]
    sg = lambda v: f"{v:+.1f}%" if v is not None else "–"
    best = "A(최근 4분기)" if (A["spearman"] or 0) > (B["spearman"] or 0) else "B(정상화)"
    lvl = (f"적정가 '수준'은 1년 뒤 주가 예측으로는 맞지 않았어요. 기본 시나리오 적정가와 1년 뒤 주가의 오차 중앙값이 "
           f"A {A['mape_fair']:.0f}%·B {B['mape_fair']:.0f}%로, '주가가 그대로'라고 찍은 것({B['mape_naive']:.0f}%)보다 컸어요. "
           f"공통 가정이 보수적이라 대부분 종목이 고평가로 나왔어요(상승 여력 중앙값 B {B['median_upside']:+.0f}%).")
    def vd(S):
        sp, t, b = S["spearman"] or 0, S["groups"]["top3"], S["groups"]["bot3"]
        ok = (t["mean"] or 0) > (b["mean"] or 0) and (t["median"] or 0) > (b["median"] or 0)
        return "맞았어요" if sp >= .3 and ok else ("약하게 맞았어요" if sp >= .1 and ok else "거의 맞지 않았어요")
    rk = (f"종목 간 '순위'는 A(최근 4분기) 방식은 {vd(A)[:-2]}고, B(정상화) 방식은 {vd(B)}. 싸 보인 순위와 실제 수익률의 상관은 A {A['spearman']:+.2f}, B {B['spearman']:+.2f}이고, "
          f"싸 보인 상위 ⅓과 비싸 보인 하위 ⅓의 평균 수익률은 A {sg(A['groups']['top3']['mean'])} vs {sg(A['groups']['bot3']['mean'])}, "
          f"B {sg(B['groups']['top3']['mean'])} vs {sg(B['groups']['bot3']['mean'])}(중앙값 B {sg(B['groups']['top3']['median'])} vs {sg(B['groups']['bot3']['median'])})예요. "
          f"이번 1년은 {best} 쪽이 순위를 더 잘 맞혔어요. 업종 중앙값보다 더 오를지 맞힌 비율은 B {B['hit_rel']:.0f}%(50%가 동전 던지기)예요.")
    return lvl + " " + rk


def run():
    prices = load("raw/backtest/prices.json")["prices"]
    out = {"t0": T0.isoformat(), "t1": T1.isoformat(), "built": dt.date.today().isoformat(),
           "params": {}, "industries": {}}
    for ind, meta in IND.items():
        cos = load(meta["data"] + "/companies.json")["companies"]
        cfgc = {c["code"]: c for c in load(meta["cfg"] + "/companies.json")}
        dft = (load(meta["cfg"] + "/valuation.json").get("default") or COSMETICS_DEFAULT)
        par = {"g": dft["g"]["base"], "g_bear": dft["g"]["bear"], "g_bull": dft["g"]["bull"], "r": dft["r"], "c": dft["c"]}
        out["params"][ind] = par
        rows, skipped = [], []
        try:
            vsh = {k: v.get("shares") for k, v in load(meta["data"] + "/valuation.json")["companies"].items()}
        except Exception:  # noqa: BLE001
            vsh = {}
        for co in cos:
            code, name = co["code"], co["name"]
            mk = (cfgc.get(code) or {}).get("market") or co.get("market")
            Q = {k: v for k, v in (co.get("quarterly") or {}).items() if q_available(k, T0)}
            A = {y: v for y, v in (co.get("annual") or {}).items() if a_available(y, T0)}
            ks = sorted(Q)[-4:]
            if len(ks) < 4 or ks[-1] != "2025Q2":
                skipped.append({"code": code, "name": name, "why": "T0 시점 분기 실적 부족(DART 미수집 또는 신규 상장)"}); continue
            s = prices.get(code); ix = prices.get("KOSDAQ" if mk == "KOSDAQ" else "KOSPI")
            if not s or not ix:
                skipped.append({"code": code, "name": name, "why": "과거 주가 없음"}); continue
            d0, p0, i0 = px_on(s, T0); d1, p1, i1 = px_on(s, T1)
            if not p0 or not p1 or d0 < (T0 - dt.timedelta(days=10)).isoformat() or d1 < (T1 - dt.timedelta(days=10)).isoformat():
                skipped.append({"code": code, "name": name, "why": "T0 또는 1년 후 거래 없음(상장 시점·거래정지)"}); continue
            sh = (co.get("shares") or {}); common = sh.get("common") or (cfgc.get(code) or {}).get("shares") or (None if co.get("pref") else vsh.get(code))
            if not common:
                skipped.append({"code": code, "name": name, "why": "주식수 없음"}); continue
            pref = co.get("pref"); pref_sh = sh.get("pref") if pref else 0
            pp0 = px_on(prices[pref], T0)[1] if pref and pref_sh and prices.get(pref) else None
            if pref_sh and not pp0: pref_sh = 0
            mcap0 = (p0 * common + (pp0 or 0) * (pref_sh or 0)) / 1e6  # 백만원
            nsh = common + (pref_sh or 0)
            ttm_ni = sum(Q[k].get("ni") or 0 for k in ks); ttm_rev = sum(Q[k].get("rev") or 0 for k in ks)
            hb = cycle_base({"annual": A, "quarterly": Q})
            ix0, ix1 = px_on(ix, T0)[1], px_on(ix, T1)[1]
            ret = (p1 / p0 - 1) * 100; mret = (ix1 / ix0 - 1) * 100
            path = s["c"][i0:i1 + 1]
            r = {"code": code, "name": name, "group": co.get("group"), "market": mk, "p0": p0, "d0": d0, "p1": p1, "d1": d1,
                 "ret": round(ret, 1), "mkt_ret": round(mret, 1), "ex_ret": round(ret - mret, 1),
                 "max_up": round((max(path) / p0 - 1) * 100, 1), "max_dn": round((min(path) / p0 - 1) * 100, 1),
                 "mcap0": round(mcap0), "ttm_ni": ttm_ni, "ttm_rev": ttm_rev, "period": f"{ks[0]}~{ks[-1]}",
                 "per0": round(mcap0 / ttm_ni, 1) if ttm_ni > 0 else None,
                 "norm_ni": hb["norm_ni"] if hb else None, "norm_margin": hb["margin"] if hb else None,
                 "ttm_margin": round(ttm_ni / ttm_rev * 100, 1) if ttm_rev else None,
                 "spark": [round(v / p0 * 100, 1) for v in path[::5]]}
            for key, E in (("A", ttm_ni), ("B", hb["norm_ni"] if hb else None)):
                if E is None or E <= 0:
                    r[key] = None; continue
                vals = {k: equity_value(E, dft["g"][k], dft["r"], dft["c"], GT) for k in ("bear", "base", "bull")}
                fair = vals["base"] * 1e6 / nsh
                r[key] = {"fair": round(fair), "upside": round((vals["base"] / mcap0 - 1) * 100, 1),
                          "bear": round(vals["bear"] * 1e6 / nsh), "bull": round(vals["bull"] * 1e6 / nsh),
                          "in_range": vals["bear"] * 1e6 / nsh <= p1 <= vals["bull"] * 1e6 / nsh,
                          "verdict": "저평가" if vals["base"] / mcap0 >= 1.3 else ("고평가" if vals["base"] / mcap0 <= .7 else "적정권")}
            rows.append(r)
        if rows:  # 초과수익은 같은 업종 표본의 중앙값 대비(지수는 참고용)
            mid_ret = st.median(r["ret"] for r in rows)
            for r in rows:
                r["ex_ret"] = round(r["ret"] - mid_ret, 1)
        res = {"name": meta["name"], "median_ret": round(st.median(r["ret"] for r in rows), 1) if rows else None, "rows": rows, "skipped": skipped,
               "A": summarize(rows, "A"), "B": summarize(rows, "B"),
               "eq_ret": round(sum(r["ret"] for r in rows) / len(rows), 1) if rows else None}
        if rows:
            for key in ("A", "B"):
                if res[key]:
                    rs = [r for r in rows if r.get(key)]
                    res[key]["in_range"] = round(sum(1 for r in rs if r[key]["in_range"]) / len(rs) * 100, 1)
            res["by_group"] = {}
            for g in sorted({r["group"] for r in rows}):
                v = [r for r in rows if r["group"] == g]
                res["by_group"][g] = {"n": len(v), "ret": round(st.median([r["ret"] for r in v]), 1), "A": summarize(v, "A"), "B": summarize(v, "B")}
        if rows and res["A"] and res["B"]:
            res["finding"] = finding(res)
        out["industries"][ind] = res
        print(ind, "rows", len(rows), "skipped", len(skipped))
    idx = {}
    for k in ("KOSPI", "KOSDAQ"):
        if prices.get(k):
            a, b = px_on(prices[k], T0)[1], px_on(prices[k], T1)[1]
            idx[k] = {"t0": a, "t1": b, "ret": round((b / a - 1) * 100, 1)}
    out["index"] = idx
    out["findings"] = {k: v.get("finding") for k, v in out["industries"].items() if v.get("finding")}
    os.makedirs(os.path.join(ROOT, "docs/backtest/data"), exist_ok=True)
    with open(os.path.join(ROOT, "docs/backtest/data/backtest.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    run()
