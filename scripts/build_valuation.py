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


def main():
    cos = load(P("docs", "data", "companies.json"), {}) or {}
    prices = (load(P("docs", "data", "prices.json"), {}) or {}).get("prices", {})
    cfg = load(P("config", "valuation.json"), {}) or {}
    gT = cfg.get("terminal_growth", 2.0)
    out = {"updated": datetime.date.today().isoformat(), "method": cfg.get("note", ""),
           "terminal_growth": gT, "companies": {}}
    for co in cos.get("companies", []):
        code = co["code"]
        a = cfg.get("companies", {}).get(code)
        Q = co.get("quarterly", {}) or {}
        ks = sorted(Q)[-4:]
        rec = {"name": co["name"], "group": co.get("group")}
        if len(ks) == 4:
            ttm = {m: sum((Q[k].get(m) or 0) for k in ks) for m in ("rev", "op", "ni")}
            rec["ttm"] = dict(ttm, period=f"{ks[0]}~{ks[-1]}")
        if not a:
            out["companies"][code] = rec
            continue
        snap = a["snapshot"]
        px = prices.get(code)
        if px and px.get("price"):
            price, pdate = px["price"], px.get("date")
            mcap = px.get("mcap") or round(price * snap["shares"] / 1e6)
            psrc = "금융위원회 주식시세정보"
        else:
            price, pdate, mcap, psrc = snap["price"], snap["price_date"], snap["mcap"], "StockAnalysis 스냅샷"
        bs = co.get("bs") or {}
        equity = bs.get("equity") or snap.get("equity")
        eq_src = f"DART {bs.get('period')}" if bs.get("equity") else "스냅샷(PBR 역산)"
        if bs.get("cash") is not None and bs.get("debt") is not None:
            net_cash = (bs.get("cash") or 0) + (bs.get("st_fin") or 0) - (bs.get("debt") or 0)
        else:
            net_cash = snap.get("net_cash")
        shares = round(mcap * 1e6 / price) if price else snap["shares"]
        rec.update(price=price, price_date=pdate, price_source=psrc, mcap=mcap, shares=shares,
                   equity=equity, equity_source=eq_src, net_cash=net_cash,
                   dividend_yield=snap.get("dividend_yield"))
        t = rec.get("ttm")
        if t:
            ni = t["ni"]
            rec["per"] = round(mcap / ni, 1) if ni > 0 else None
            rec["roe"] = round(ni / equity * 100, 1) if equity else None
        rec["pbr"] = round(mcap / equity, 2) if equity else None
        E1 = a["E1"] * 100  # 억원 → 백만원
        sc = {}
        for k in ("bear", "base", "bull"):
            v = equity_value(E1, a["g"][k], a["r"], a["c"], gT)
            sc[k] = {"g": a["g"][k], "value": round(v), "per_share": round(v * 1e6 / shares),
                     "upside": round((v / mcap - 1) * 100, 1)}
        rec["dcf"] = {"E1": E1, "r": a["r"], "c": a["c"], "note": a.get("note", ""),
                      "fwd_per": round(mcap / E1, 1), "scenarios": sc,
                      "implied_g": implied_growth(mcap, E1, a["r"], a["c"], gT)}
        out["companies"][code] = rec
    with open(P("docs", "data", "valuation.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("valuation.json:", len(out["companies"]), "개사")


if __name__ == "__main__":
    main()
