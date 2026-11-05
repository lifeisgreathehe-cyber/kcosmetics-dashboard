"""TTM 지표(PER·ROE·PBR)와 내재가치 시나리오를 계산해 docs/data/valuation.json 생성.

입력: docs/data/companies.json (DART 분기 실적, bs), docs/data/prices.json (있으면 최신 시세),
      config/valuation.json (가정 + 시세/자본 스냅샷)
표준 라이브러리만 사용.
"""
import json, os, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)


def load(p, default=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


NC_YIELD = 0.02


def path_growth(g1, gT, years=10):
    """1~5년차 g1, 6~10년차 gT로 선형 수렴."""
    out = []
    for t in range(1, years + 1):
        if t <= 5:
            out.append(g1)
        else:
            w = (t - 5) / 5
            out.append(g1 + (gT - g1) * w)
    return out


def equity_value(E1, g1, r, c, gT):
    """주주잉여현금흐름(FCFE = 이익 × c) 10년 + 영구가치. 단위는 E1과 동일."""
    r, gT_, g1_ = r / 100, gT / 100, g1 / 100
    gs = path_growth(g1_, gT_)
    pv, E = 0.0, E1
    for t in range(1, 11):
        if t > 1:
            E *= 1 + gs[t - 1]
        pv += E * c / (1 + r) ** t
    tv = E * (1 + gT_) * c / (r - gT_)
    return pv + tv / (1 + r) ** 10


def implied_growth(target, E1, r, c, gT):
    """시가총액을 정당화하는 1~5년차 성장률(역DCF). 이분법."""
    lo, hi = -30.0, 80.0
    if equity_value(E1, lo, r, c, gT) > target:
        return lo
    if equity_value(E1, hi, r, c, gT) < target:
        return None
    for _ in range(80):
        mid = (lo + hi) / 2
        if equity_value(E1, mid, r, c, gT) < target:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 1)


def main(industry="cosmetics"):
    dd = ("docs", "data") if industry == "cosmetics" else ("docs", industry, "data")
    cd = ("config",) if industry == "cosmetics" else ("config", industry)
    cos = load(P(*dd, "companies.json"), {}) or {}
    prices = (load(P(*dd, "prices.json"), {}) or {}).get("prices", {})
    quotes = (load(P(*dd, "quotes.json"), {}) or {})
    qsrc, quotes = quotes.get("source"), quotes.get("quotes", {})
    cfg = load(P(*cd, "valuation.json"), {}) or {}
    gT = cfg.get("terminal_growth", 2.0)
    # DART에서 주식수를 못 읽은 회사는 설정 파일의 shares(보통주 유통주식수)를 쓴다
    manual = {c["code"]: c["shares"] for c in (load(P(*cd, "companies.json"), []) or []) if c.get("shares")}
    out = {"updated": datetime.date.today().isoformat(), "method": cfg.get("note", ""),
           "terminal_growth": gT, "asof": cfg.get("asof"), "companies": {}}
    for co in cos.get("companies", []):
        code = co["code"]
        a = cfg.get("companies", {}).get(code)
        Q = co.get("quarterly", {}) or {}
        ks = sorted(Q)[-4:]
        rec = {"name": co["name"], "group": co.get("group")}
        if len(ks) == 4:
            ttm = {m: sum((Q[k].get(m) or 0) for k in ks) for m in ("rev", "op", "ni")}
            rec["ttm"] = dict(ttm, period=f"{ks[0]}~{ks[-1]}")
        dft = cfg.get("default")
        if not a and dft and dft.get("E1_years"):
            # 경기순환 업종: 최근 N개 연도 지배순이익 평균(사이클 평균)을 정상 이익으로 쓰는 자동 가정
            A = co.get("annual", {}) or {}
            ys = [A[y].get("ni") for y in sorted(A)[-dft["E1_years"]:] if A[y].get("ni") is not None]
            if len(ys) >= 3 and sum(ys) > 0:
                a = dict(dft, E1=round(sum(ys) / len(ys) / 100))
                a["note"] = dft.get("note", "").replace("{n}", str(len(ys)))
                rec["auto"] = True
        elif not a and dft and rec.get("ttm") and rec["ttm"]["ni"] > 0:
            # 개별 가정이 없는 회사: 최근 4개 분기 순이익을 그대로 쓰는 자동 가정
            a = dict(dft, E1=round(rec["ttm"]["ni"] / 100))
            rec["auto"] = True
        snap = (a or {}).get("snapshot") or {}
        px = prices.get(code)
        qt = quotes.get(code)
        dsh = co.get("shares") or {}  # DART 유통주식수 (보통주·우선주)
        shares0 = (px or {}).get("shares") or snap.get("shares") or dsh.get("common") or manual.get(code)
        if not shares0:
            out["companies"][code] = rec
            continue
        pref = co.get("pref")
        pref_sh = dsh.get("pref") if pref else None
        pq = quotes.get(pref) if pref else None
        if qt and qt.get("price"):
            price, pdate, psrc = qt["price"], qt.get("time"), qsrc or "실시간 시세"
            mcap = round(price * shares0 / 1e6)
            if pref_sh and pq and pq.get("price"):  # 우선주 시가총액 합산
                mcap += round(pq["price"] * pref_sh / 1e6)
        elif px and px.get("price"):
            price, pdate = px["price"], px.get("date")
            mcap = px.get("mcap") or round(price * shares0 / 1e6)
            psrc = "금융위원회 주식시세정보"
        elif snap.get("price"):
            price, pdate, mcap, psrc = snap["price"], snap["price_date"], snap["mcap"], "StockAnalysis 스냅샷"
        else:
            out["companies"][code] = rec
            continue
        bs = co.get("bs") or {}
        equity = bs.get("equity") or snap.get("equity")
        eq_src = f"DART {bs.get('period')}" if bs.get("equity") else "스냅샷(PBR 역산)"
        if bs.get("cash") is not None and bs.get("debt") is not None:
            net_cash = (bs.get("cash") or 0) + (bs.get("st_fin") or 0) - (bs.get("debt") or 0)
            if not bs.get("debt") and snap.get("net_cash") is not None:  # 차입금 계정을 못 찾은 경우 보수적으로
                net_cash = min(net_cash, snap["net_cash"])
        else:
            net_cash = snap.get("net_cash")
        shares = shares0 + (pref_sh or 0)  # 주당 가치는 보통주+우선주 기준
        rec.update(price=price, price_date=pdate, price_source=psrc, mcap=mcap, shares=shares,
                   equity=equity, equity_source=eq_src, net_cash=net_cash,
                   dividend_yield=snap.get("dividend_yield"))
        t = rec.get("ttm")
        if t:
            ni = t["ni"]
            rec["per"] = round(mcap / ni, 1) if ni > 0 else None
            rec["roe"] = round(ni / equity * 100, 1) if equity else None
        rec["pbr"] = round(mcap / equity, 2) if equity else None
        if not a:
            out["companies"][code] = rec
            continue
        E1 = a["E1"] * 100  # 억원 → 백만원
        # 순현금은 따로 더하고, 그 이자(세후 약 2%)는 영업 이익에서 뺀다 (순차입이면 반대)
        nc = (net_cash or 0) if a.get("nc_adj", True) else 0  # 비지배지분이 큰 지주·연결사는 제외
        E_op = E1 - nc * NC_YIELD
        sc = {}
        for k in ("bear", "base", "bull"):
            v = equity_value(E_op, a["g"][k], a["r"], a["c"], gT) + nc
            v = max(v, 0)
            sc[k] = {"g": a["g"][k], "value": round(v), "per_share": round(v * 1e6 / shares),
                     "upside": round((v / mcap - 1) * 100, 1)}
        rec["dcf"] = {"E1": E1, "r": a["r"], "c": a["c"], "note": a.get("note", ""),
                      "fwd_per": round(mcap / E1, 1), "scenarios": sc,
                      "implied_g": implied_growth(mcap - nc, E_op, a["r"], a["c"], gT),
                      "net_cash_added": nc}
        out["companies"][code] = rec
    with open(P(*dd, "valuation.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("valuation.json:", len(out["companies"]), "개사")


if __name__ == "__main__":
    import sys
    main(sys.argv[sys.argv.index("--industry") + 1] if "--industry" in sys.argv else "cosmetics")
