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


# 사이클 위치별 기본 초과이익 경로: 최근 4분기 순이익과 정상 이익의 차이가 앞으로 몇 해 동안 얼마나 남는지(비율)
CYCLE_PATH = {"호황 정점권": [0.7, 0.3], "상승기": [1.0, 0.7, 0.3], "회복기": [0.8, 0.4], "중립": [],
              "하강기": [0.8, 0.4], "바닥권": [0.7, 0.3]}


def cycle_base(co):
    """과거 연간 실적으로 본 '사이클 평균' 정상 이익: 순이익률(최고·최저 해 제외 평균) × 추세 매출."""
    import math
    A = co.get("annual") or {}
    ys = [y for y in sorted(A) if (A[y].get("rev") or 0) > 0 and A[y].get("ni") is not None]
    Q = co.get("quarterly") or {}
    ks = sorted(Q)[-4:]
    if len(ys) < 3 or len(ks) < 4:
        return None
    ttm_rev = sum((Q[k].get("rev") or 0) for k in ks)
    ms = [A[y]["ni"] / A[y]["rev"] for y in ys]
    tm = sorted(ms)[1:-1] if len(ms) >= 6 else ms
    mm = sum(tm) / len(tm)
    pts = [(int(y) + .5, math.log(A[y]["rev"])) for y in ys]
    te = int(ks[-1][:4]) + int(ks[-1][-1]) / 4 - .5
    if ttm_rev > 0:
        pts.append((te, math.log(ttm_rev)))
    n = len(pts)
    mx, my = sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n
    b = sum((p[0] - mx) * (p[1] - my) for p in pts) / sum((p[0] - mx) ** 2 for p in pts)
    tr = math.exp(my + b * (te - mx))
    return {"years": f"{ys[0]}~{ys[-1]}", "n": len(ys), "margin": round(mm * 100, 1),
            "margin_range": [round(min(ms) * 100, 1), round(max(ms) * 100, 1)],
            "trend_rev": round(tr), "ttm_rev": ttm_rev, "norm_ni": round(tr * mm), "trend_g": round((math.exp(b) - 1) * 100, 1)}


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


def midcycle(annual, ttm_rev, cyc):
    """여러 해 연간 순이익률 평균 × 최근 4분기 매출 = 사이클 평균 이익(백만원)."""
    if not annual or not ttm_rev:
        return None
    lo, hi = (cyc.get("years") or [0, 9999])
    ex = set(cyc.get("exclude") or [])
    ys = [y for y in sorted(annual)
          if annual[y].get("rev") and annual[y].get("ni") is not None
          and lo <= int(y) <= hi and int(y) not in ex][-8:]
    if not ys:
        return None
    m = {y: annual[y]["ni"] / annual[y]["rev"] * 100 for y in ys}
    vals = sorted(m.values())
    used = vals[1:-1] if len(vals) >= 5 else vals
    avg = sum(used) / len(used)
    return {"years": f"{ys[0]}~{ys[-1]}", "n": len(ys), "trimmed": len(vals) >= 5,
            "excluded": sorted(ex), "margins": {y: round(v, 1) for y, v in m.items()},
            "avg_margin": round(avg, 1), "min": round(vals[0], 1), "max": round(vals[-1], 1),
            "ni": round(avg / 100 * ttm_rev)}


def quant_check(cos, out, cfg, dd):
    """백테스트로 검증한 기계식 모델(scripts/backtest/model.py, 변형 G)로 회사별 교차 점검값을 rec["quant"]에 붙임.
    사람이 정한 가정·사이클 판단과 독립적이라, 둘이 크게 엇갈리면 판단을 다시 보라는 신호로 씀. 본 적정가(dcf)는 그대로."""
    import math, statistics as st, sys as _s
    _s.path.insert(0, os.path.join(ROOT, "scripts", "backtest"))
    from model import features, fair_value, auto_position, TAX
    bt = load(P("docs", "backtest", "data", "backtest.json"), {}) or {}
    ind = {"docs/data": "cosmetics"}.get("/".join(dd), dd[1] if len(dd) > 2 else "cosmetics")
    dft = cfg.get("default") or {}
    par = {"g": dft.get("g") or {"bear": 0.0, "base": 5.0, "bull": 10.0}, "r": dft.get("r", 10.5), "c": dft.get("c", 0.7)}
    rows = []
    for co in cos.get("companies", []):
        rec = out["companies"].get(co["code"])
        if not rec or not rec.get("mcap") or not rec.get("shares"):
            continue
        f = features(co.get("annual"), co.get("quarterly"))
        if not f:
            continue
        v = fair_value(f, par, "G")
        q = {"pos": auto_position(f), "period": f["period"], "core": round(f["core"]), "norm": round(f["norm"]) if f.get("norm") else None,
             "ttm_ni": f["ttm_ni"], "oneoff": bool(f["ttm_op"] > 0 and (f["ttm_ni"] > 2 * f["ttm_op"] * TAX or f["ttm_ni"] < 0.3 * f["ttm_op"] * TAX))}
        if v:
            q.update(E=round(v["E"]), per_share=round(v["base"] * 1e6 / rec["shares"]), bear=round(v["bear"] * 1e6 / rec["shares"]),
                     bull=round(v["bull"] * 1e6 / rec["shares"]), upside=round((v["base"] / rec["mcap"] - 1) * 100, 1))
            rows.append((rec, q, math.log(v["base"] / rec["mcap"])))
        rec["quant"] = q
    if len(rows) >= 6:
        med = st.median(x for _, _, x in rows)
        srt = sorted(rows, key=lambda t: t[2])
        beta = bt.get("beta", 0.065)
        for i, (rec, q, lg) in enumerate(srt):
            q["pct"] = round(i / (len(srt) - 1) * 100)  # 업종 안에서 얼마나 싸 보이나(100=가장 쌈)
            q["tier"] = "싼 ⅓" if q["pct"] >= 200 / 3 else ("비싼 ⅓" if q["pct"] <= 100 / 3 else "가운데 ⅓")
            q["exp_ex"] = round((math.exp(beta * max(-2, min(2, lg - med))) - 1) * 100, 1)  # 백테스트 기울기로 본 1년 업종 대비 기대 초과수익
            hand = ((rec.get("dcf") or {}).get("scenarios") or {}).get("base", {}).get("upside")
            if hand is not None and not rec.get("auto"):
                q["conflict"] = (hand >= 30 and q["tier"] == "비싼 ⅓") or (hand <= -30 and q["tier"] == "싼 ⅓")
    yrs = ((bt.get("industries") or {}).get(ind) or {}).get("years") or {}
    hist = [(y, d.get("G")) for y, d in sorted(yrs.items()) if d.get("G")]
    out["quant_meta"] = {"model": "사이클 평균 이익 50% + 핵심 이익(일회성 제거) 50%, 업종 공통 가정", "par": par, "beta": bt.get("beta"),
                         "history": [{"year": y, "n": g["n"], "ic": g["ic"], "hit_rel": g["hit_rel"],
                                      "top3": g["groups"]["top3"]["mean"], "bot3": g["groups"]["bot3"]["mean"]} for y, g in hist]}


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
    out["industry_cycle"] = cfg.get("industry_cycle", {})
    # 반도체: 리뷰에 정리한 잠정실적(억원)
    latest = {k: v.get("latest") for k, v in ((load(P(*dd, "reviews.json"), {}) or {}).get("companies", {}) or {}).items()
              if v.get("latest")} if cfg.get("cycle_mode") else {}
    norm_ratio = {}
    # 다른 회사의 사이클 조정 비율을 따르는 회사(follow)는 뒤에서 계산
    order = sorted(cos.get("companies", []),
                   key=lambda c: 1 if ((cfg.get("companies", {}).get(c["code"]) or {}).get("cycle") or {}).get("follow") else 0)
    for co in order:
        code = co["code"]
        a = cfg.get("companies", {}).get(code)
        Q = co.get("quarterly", {}) or {}
        ks = sorted(Q)[-4:]
        rec = {"name": co["name"], "group": co.get("group")}
        if len(ks) == 4:
            ttm = {m: sum((Q[k].get(m) or 0) for k in ks) for m in ("rev", "op", "ni")}
            rec["ttm"] = dict(ttm, period=f"{ks[0]}~{ks[-1]}")
        dft = cfg.get("default")
        semi_cyc = cfg.get("cycle_mode")  # 반도체: 사이클 위치 + 사이클 평균 정상 이익(cycle_base)
        hb = cycle_base(co) if semi_cyc else None
        if hb:
            rec["hist"] = hb
        if semi_cyc and a and a.get("E1") is None:
            # 회사별 사이클 판단(cyc_pos·g·r·c)은 사람이 정하고, 정상 이익은 DART 이력으로 계산(음식료):
            # margin(정상 순이익률 %)이 있으면 추세 매출 × margin, 없으면 사이클 평균 이익 × E1_adj
            if hb and (a.get("margin") is not None or hb["norm_ni"] > 0):
                base_ni = hb["trend_rev"] * a["margin"] / 100 if a.get("margin") is not None else hb["norm_ni"] * a.get("E1_adj", 1.0)
                a = dict(dft or {}, **a, E1=round(base_ni / 100))
            else:
                rec["cycle"] = {"position": a.get("cyc_pos"), "note": a.get("cycle_note", ""), "basis": a.get("note", "")}
                a = None
                rec["pending"] = "DART 연간·분기 실적 수집 후 정상 이익을 계산해요"
        if semi_cyc:
            if not a and dft and hb and hb["norm_ni"] > 0 and not rec.get("pending"):
                a = dict(dft, E1=round(hb["norm_ni"] / 100))
                rec["auto"] = True
        elif not a and dft and dft.get("E1_years"):
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
        if a and a.get("skip"):
            rec["skip"] = a["skip"]
            rec["cycle"] = {"position": a.get("cyc_pos"), "note": a.get("cycle_note", "")}
            a = None
        if not a:
            out["companies"][code] = rec
            continue
        E1f = a["E1"] * 100  # 억원 → 백만원 (향후 12개월 전망 이익)
        cyc = a.get("cycle") or {}
        w = cyc.get("w_mid", 0) or 0
        mc = midcycle(co.get("annual"), (t or {}).get("rev"), cyc) if cyc and not cyc.get("follow") else None
        if cyc.get("follow"):
            E1 = round(E1f * norm_ratio.get(cyc["follow"], 1.0))
            basis = f"{cyc['follow']} 사이클 조정 비율 적용"
        elif mc and w:
            E1 = round(w * mc["ni"] + (1 - w) * E1f)
            basis = f"사이클 평균 이익 {w:.0%} + 전망 이익 {1 - w:.0%}"
        else:
            E1, basis = E1f, "전망 이익 100%"
        norm_ratio[code] = E1 / E1f if E1f else 1.0
        if cyc:
            rec["cycle"] = {"phase": cyc.get("phase"), "note": cyc.get("note", ""), "w_mid": w,
                            "follow": cyc.get("follow"), "industry": out["industry_cycle"].get(co.get("group"), ""),
                            "midcycle": mc, "ttm_margin": round(t["ni"] / t["rev"] * 100, 1) if t and t.get("rev") else None,
                            "ttm_ni": t["ni"] if t else None, "E1_fwd": E1f, "E1_basis": basis}
        # 순현금은 따로 더하고, 그 이자(세후 약 2%)는 영업 이익에서 뺀다 (순차입이면 반대)
        nc = (net_cash or 0) if a.get("nc_adj", True) else 0  # 비지배지분이 큰 지주·연결사는 제외
        if nc < 0 and cfg.get("debt_mode") == "levered":
            # 순이익은 이미 이자비용을 뺀 값이에요. 그 이익을 자기자본비용으로 할인한 FCFE 가치에서 차입금을 또 빼면,
            # 이자 되돌림(세후 2% × 현금전환율 ÷ (r−g))이 차입금보다 훨씬 작아 부채를 이중으로 벌점 줘요. 순차입이면 조정하지 않아요.
            rec["net_debt_levered"] = nc
            nc = 0
        E_op = E1 - nc * NC_YIELD
        # 반도체: 최근 4분기 순이익이 정상 이익보다 높거나 낮은 상태가 사이클 위치에 따라 몇 해 더 이어지는지
        xv, cy = 0, None
        if semi_cyc and t:
            path = a.get("excess", CYCLE_PATH.get(a.get("cyc_pos"), []))
            ni_now = t["ni"]
            lt = (latest or {}).get(code)
            ks_all = sorted(Q)
            if lt and lt.get("period") not in Q and lt.get("ni") is not None and len(ks_all) >= 3:
                # DART 반영 전 잠정실적이 있으면 최근 3개 분기 + 잠정 분기로 최근 이익을 다시 잡는다
                ni_now = sum((Q[k].get("ni") or 0) for k in ks_all[-3:]) + lt["ni"] * 100
                rec["ttm_news"] = {"period": f"{ks_all[-3]}~{lt['period']}", "ni": ni_now}
            if a.get("ni_now") is not None:
                # 일회성 손익(손상차손·평가손익)을 뺀 최근 이익을 사람이 정한 경우(억원)
                ni_now = a["ni_now"] * 100
                rec["ttm_news"] = {"period": a.get("ni_now_note", "일회성 손익을 뺀 최근 이익"), "ni": ni_now}
            ex = ni_now - E1
            xv = round(sum(ex * w_ * a["c"] / (1 + a["r"] / 100) ** (i + 1) for i, w_ in enumerate(path)))
            cy = {"position": a.get("cyc_pos", "중립"), "note": a.get("cycle_note", ""), "path": path,
                  "excess": ex, "excess_value": xv}
        sc = {}
        for k in ("bear", "base", "bull"):
            v = equity_value(E_op, a["g"][k], a["r"], a["c"], gT) + nc + xv
            v = max(v, 0)
            sc[k] = {"g": a["g"][k], "value": round(v), "per_share": round(v * 1e6 / shares),
                     "upside": round((v / mcap - 1) * 100, 1)}
        rec["dcf"] = {"E1": E1, "r": a["r"], "c": a["c"], "note": a.get("note", ""),
                      "fwd_per": round(mcap / E1f, 1) if E1f else None,
                      "norm_per": round(mcap / E1, 1) if E1 > 0 else None, "scenarios": sc,
                      "implied_g": implied_growth(mcap - nc - xv, E_op, a["r"], a["c"], gT),
                      **({"cycle": cy} if cy else {}),
                      "net_cash_added": nc}
        out["companies"][code] = rec
    try:
        quant_check(cos, out, cfg, dd)
    except Exception as e:  # noqa: BLE001  검증 모델 오류가 본 계산을 막지 않게
        print("quant_check 실패:", e)
    out["companies"] = {c["code"]: out["companies"][c["code"]] for c in cos.get("companies", [])
                        if c["code"] in out["companies"]}
    with open(P(*dd, "valuation.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("valuation.json:", len(out["companies"]), "개사")


if __name__ == "__main__":
    import sys
    main(sys.argv[sys.argv.index("--industry") + 1] if "--industry" in sys.argv else "cosmetics")
