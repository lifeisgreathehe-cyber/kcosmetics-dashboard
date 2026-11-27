"""리포트식 점검(rec.lens) — 모든 업종 대시보드 공용.

이엔에프테크놀로지 AI 기업분석 리포트(2026-11-26, 작성자 Zurini)를 역엔지니어링해서 우리 대시보드에 없던
도구만 골라 넣었다(/mnt/project-files/report/이엔에프_리포트_역엔지니어링.md, docs/report/METHOD.md).

  er5    5년 기대수익률(비관·기본·낙관) = ((5년 뒤 이익 × 종료 PER + 5년 누적 배당) ÷ 시가총액)^(1/5) − 1
         · 리포트와 다른 점(우리 쪽이 나은 부분 유지): 5년 뒤 이익은 TTM이나 회사 추정이 아니라 우리 정상 이익(E1,
           사이클·일회성 보정)에서 시나리오 성장률로 키운 값이다. 비관 이익은 '기본 × 60%' 고정 비율 대신
           막스 점검의 불황 이익(과거 두 번째로 나쁜 순이익률 × 추세 매출)을 쓴다.
         · 종료 PER은 리포트처럼 회사의 과거 연말 PER(절사평균)을 기준으로 기본 85%, 비관 70%, 낙관 120%.
           비관은 이익을 이미 불황 수준으로 낮췄으므로 PER을 리포트(7/9 = 78%)보다 과하게 깎지 않는다.
  shocks 과거 이익률 충격 사례: 분기 매출총이익률(없으면 영업이익률)이 고점에서 4%p 이상 떨어진 구간,
         바닥, 원래 수준(고점 −1%p) 회복까지 걸린 분기 수 + 지금 진행 중인 하락
  bridge 연도별 영업이익 변화 = 물량 효과(매출 변화 × 전년 이익률) + 이익률 효과(올해 매출 × 이익률 변화)
  sens   다음 해 영업이익 민감도(매출 증가율 4단계 × 매출총이익률 ±1%p, 판관비는 고정비처럼 3%+성장 일부)
  peers  같은 그룹 동종 비교(시가총액·매출·영업이익률·순이익·ROE·PER) + ROE 대비 PER 할인 여부
  plan   투자 방법: 나눠 사기 시작할 가격(기본 기대수익률이 할인율 r 이상이 되는 가격), 비중 확대 가격(안전마진 매수가),
         비중 축소 가격(낙관 적정가 또는 낙관 종료 PER 도달)

적정주가(dcf)·막스 점검(marks)은 바꾸지 않는다. 보여 주는 쪽은 docs/shared/lens.js.
"""
import json, os, statistics as st


def _yend_price(series, y):
    if not series:
        return None
    m = dict(zip(series.get("months") or [], series.get("close") or []))
    return m.get(f"{y}-12")


def _trim_mean(xs):
    xs = sorted(xs)
    if len(xs) >= 5:
        xs = xs[1:-1]
    return st.mean(xs) if xs else None


def _shocks(Q):
    ks = [k for k in sorted(Q) if (Q[k].get("rev") or 0) > 0]
    use_gp = sum(1 for k in ks if Q[k].get("gp") is not None) >= max(4, len(ks) - 1)
    f = "gp" if use_gp else "op"
    ser = [(k, Q[k][f] / Q[k]["rev"] * 100) for k in ks if Q[k].get(f) is not None]
    out, i = [], 0
    while i < len(ser) - 1:
        # 고점(직전 4개 분기 최고)에서 4%p 이상 떨어지는 구간 찾기
        # 기준 수준 = 그 분기까지 4개 분기 중앙값(한 분기 튀는 값에 끌려가지 않게)
        k0 = ser[i][0]
        m0 = min(ser[i][1], st.median([v for _, v in ser[max(0, i - 3):i + 1]]))
        j, tr, trk = i + 1, m0, None
        while j < len(ser) and ser[j][1] < m0 - 1:
            if ser[j][1] < tr:
                tr, trk = ser[j][1], ser[j][0]
            j += 1
        if trk and m0 - tr >= 4 and (j - i) >= 2:
            rec = ser[j][0] if j < len(ser) else None
            out.append({"start": k0, "start_m": round(m0, 1), "trough": trk, "trough_m": round(tr, 1),
                        "drop": round(m0 - tr, 1), "recovered": rec, "quarters": (j - i) if rec else None,
                        "ongoing": rec is None, "path": [[k, round(v, 1)] for k, v in ser[i:min(j + 1, len(ser))]]})
            i = j
        else:
            i += 1
    # 겹치는 작은 구간은 가장 큰 하락만 남긴다
    done = [s for s in out if not s["ongoing"]]
    q_med = st.median([s["quarters"] for s in done]) if done else None
    last = ser[-1] if ser else None
    peak4 = max(v for _, v in ser[-5:-1]) if len(ser) >= 5 else None
    now = None
    if last and peak4 is not None and peak4 - last[1] >= 2:
        now = {"q": last[0], "m": round(last[1], 1), "peak": round(peak4, 1), "gap": round(peak4 - last[1], 1)}
    return {"basis": "매출총이익률" if use_gp else "영업이익률", "list": out[-4:], "q_median": q_med, "now": now}


def _bridge(A, ys):
    rows = []
    for a, b in zip(ys[-6:], ys[-5:]):
        pa, pb = A[a], A[b]
        if not pa.get("rev") or not pb.get("rev") or pa.get("op") is None or pb.get("op") is None:
            continue
        ma, mb = pa["op"] / pa["rev"], pb["op"] / pb["rev"]
        vol = (pb["rev"] - pa["rev"]) * ma
        mar = pb["rev"] * (mb - ma)
        d = pb["op"] - pa["op"]
        main = "물량(매출)" if abs(vol) >= abs(mar) else "이익률"
        rows.append({"y": b, "d_op": round(d), "vol": round(vol), "margin": round(mar), "rev_g": round((pb["rev"] / pa["rev"] - 1) * 100, 1),
                     "opm": round(mb * 100, 1), "opm_prev": round(ma * 100, 1), "main": main})
    return rows


def _sens(A, ys, t, rec):
    if not ys:
        return None
    a = A[ys[-1]]
    base_rev = (t or {}).get("rev") or a.get("rev")
    if not base_rev:
        return None
    g0 = ((rec.get("hist") or {}).get("trend_g") or 5) / 100
    g0 = max(-0.05, min(0.2, g0))
    gs = [g0 - 0.10, g0 - 0.05, g0, g0 + 0.05]
    if a.get("gp") is not None and a.get("rev"):
        gm = st.mean([A[y]["gp"] / A[y]["rev"] for y in ys[-3:] if A[y].get("gp") is not None])
        sga = a["gp"] - a["op"]
        sga1 = sga * (base_rev / a["rev"]) * (1 + max(0.02, 0.6 * g0 + 0.03)) if sga > 0 else 0
        ms = [gm - 0.01, gm, gm + 0.01]
        grid = [[round(base_rev * (1 + g) * m - sga1) for m in ms] for g in gs]
        return {"kind": "gpm", "gs": [round(g * 100, 1) for g in gs], "ms": [round(m * 100, 1) for m in ms], "grid": grid,
                "base_rev": round(base_rev), "sga": round(sga1)}
    om = st.mean([A[y]["op"] / A[y]["rev"] for y in ys[-3:] if A[y].get("op") is not None and A[y].get("rev")])
    ms = [om - 0.01, om, om + 0.01]
    grid = [[round(base_rev * (1 + g) * m) for m in ms] for g in gs]
    return {"kind": "opm", "gs": [round(g * 100, 1) for g in gs], "ms": [round(m * 100, 1) for m in ms], "grid": grid, "base_rev": round(base_rev)}


def apply(cos, out, cfg, root, dd):
    by = {c["code"]: c for c in cos.get("companies", [])}
    shp = os.path.join(root, *dd, "stock_hist.json")
    sh = json.load(open(shp, encoding="utf-8")).get("series", {}) if os.path.exists(shp) else {}
    recs = out["companies"]
    # 업종 그룹별 PER 중앙값(과거 PER 자료가 부족한 회사의 기본값)
    grp_per = {}
    for code, rec in recs.items():
        if rec.get("per") and 2 < rec["per"] < 60:
            grp_per.setdefault(rec.get("group"), []).append(rec["per"])
    grp_per = {g: st.median(v) for g, v in grp_per.items() if v}
    for code, rec in recs.items():
        try:
            _one(code, rec, by.get(code) or {}, sh.get(code), recs, grp_per)
        except Exception as e:  # noqa: BLE001  한 회사 오류가 전체를 막지 않게
            print("lens 실패", code, e)


def _one(code, rec, co, series, recs, grp_per):
    d = rec.get("dcf") or {}
    mk = rec.get("marks") or {}
    price, shares = rec.get("price"), rec.get("shares")
    mcap = rec.get("mcap_eff") or rec.get("mcap")
    A = co.get("annual") or {}
    ys = [y for y in sorted(A) if (A[y].get("rev") or 0) > 0 and A[y].get("ni") is not None][-10:]
    L = {}
    # ---------- 과거 연말 PER ----------
    hp = []
    if shares:
        for y in ys:
            p = _yend_price(series, y)
            ni = A[y]["ni"]
            if p and ni and ni > 0:
                per = p * shares / 1e6 / ni
                if 2 < per < 60:
                    hp.append((y, round(per, 1)))
    tm = _trim_mean([p for _, p in hp]) if len(hp) >= 4 else None
    per_src = "과거 연말 PER" if tm else "동종 그룹 현재 PER 중앙값"
    if not tm:
        tm = grp_per.get(rec.get("group")) or 10
    pb = max(5, min(25, round(tm * 0.85 * 2) / 2))
    per = {"bear": max(4, round(pb * 0.7 * 2) / 2), "base": pb, "bull": min(30, round(pb * 1.2 * 2) / 2)}
    # ---------- 5년 기대수익률 ----------
    E1 = d.get("E1")
    S = d.get("scenarios") or {}
    if E1 and E1 > 0 and mcap and price and S:
        dps = ((rec.get("metrics") or {}).get("dps") or 0)
        div0 = dps * shares / 1e6 if shares else 0  # 연 배당 총액(백만원)
        ttm_ni = (rec.get("ttm") or {}).get("ni")
        pay = min(1, div0 / ttm_ni) if ttm_ni and ttm_ni > 0 else (min(1, div0 / E1) if E1 else 0)
        sc = {}
        stress_E = (mk.get("stress") or {}).get("E")
        for k in ("bear", "base", "bull"):
            g = (S.get(k) or {}).get("g", 0) / 100
            ET = E1 * (1 + g) ** 4  # E1 = 1년 뒤 이익 → 5년 뒤
            how = ""
            pk = per[k]
            path = ((d.get("cycle") or {}).get("ni_paths") or {}).get(k) or []
            dip = any(x < E1 * 0.9 for x in path[:5])
            # 비관 경로에 이미 불황 구간이 있으면(예: 2년 뒤 공급 과잉) 5년 뒤에 불황을 한 번 더 넣지 않는다(이중 차감 방지)
            if k == "bear" and not dip and stress_E is not None and stress_E < ET:
                ET = max(stress_E, 0)
                # 이익을 이미 불황 수준으로 낮췄으니 PER까지 크게 깎으면 이중 차감 → 기본 PER의 85%만
                pk = max(4, round(per["base"] * 0.85 * 2) / 2)
                how = "불황 " + ((mk.get("stress") or {}).get("how") or "")
            # 누적 배당: 지금 배당성향 유지, 이익이 정상 이익 쪽으로 움직인다고 보고 직선 보간
            cum = sum(pay * (E1 + (ET - E1) * (t - 1) / 4) if E1 > 0 else div0 for t in range(1, 6))
            cum = max(cum, div0 * 5 if k != "bear" else 0) if div0 else cum
            # 우리 모델과 맞추기: 5년 안의 사이클 초과이익(호황 경로 − 정상 이익) × 현금 전환율은 5년 뒤 현금으로 쌓이고,
            # 적정가 계산에 더한 순현금도 그대로 남는다고 본다(리포트에는 없는 보정 — 호황 정점 회사의 기대수익률 과소 방지)
            exc = sum(x - E1 for x in path[:5]) * (d.get("c") or 0.7)
            nc_add = d.get("net_cash_added") or 0
            v = ET * pk + exc + nc_add
            ret = ((max(v + cum, 1)) / mcap) ** 0.2 - 1 if v > 0 else -1
            sc[k] = {"E_T": round(ET), "per": pk, "g": round(g * 100, 1), "excess": round(exc), "nc": round(nc_add),
                     "stress": bool(k == "bear" and "불황" in how), "value": round(v), "div": round(cum),
                     "value_ps": round(v * 1e6 / shares) if shares else None, "E1": E1,
                     "div_ps": round(cum * 1e6 / shares) if shares else None,
                     "ret": round(ret * 100, 1), "how": how}
        w = mk.get("weights") or {"bear": 0.25, "base": 0.5, "bull": 0.25}
        wret = sum(w.get(k, 0) * sc[k]["ret"] for k in sc)
        r = d.get("r") or 10
        # 기본 기대수익률이 r이 되는 가격(나눠 사기 시작), 막스 안전마진 매수가(비중 확대), 낙관 가치(비중 축소)
        base = sc["base"]
        p_r = (base["value"] + base["div"]) / (1 + r / 100) ** 5 * 1e6 / shares if shares else None
        L["er5"] = {"years": 5, "per": per, "per_hist": hp, "per_mean": round(tm, 1), "per_src": per_src,
                    "payout": round(pay * 100, 1), "sc": sc, "weighted": round(wret, 1), "weights": w, "r": r}
        # 비중 축소: 리포트처럼 '정상 이익 기준 PER이 낙관 종료 PER을 넘는 가격'(+ 적정가에 더한 순현금)
        cut = ((E1 * per["bull"] + (d.get("net_cash_added") or 0)) * 1e6 / shares) if shares else None
        if cut and p_r and cut < p_r:
            cut = p_r * 1.3
        L["plan"] = {"start_ps": round(p_r) if p_r else None, "add_ps": mk.get("buy_ps"), "trim_ps": round(cut) if cut else None,
                     "trim_per": per["bull"], "price": price,
                     "zone": ("매수 구간(안전마진 확보)" if mk.get("buy_ps") and price <= mk["buy_ps"] else
                              "나눠 사기 구간" if p_r and price <= p_r else
                              "비중 축소 구간" if cut and price >= cut else "보유·관찰 구간")}
    # ---------- 이익률 충격 사례 ----------
    Q = co.get("quarterly") or {}
    if len(Q) >= 6:
        L["shocks"] = _shocks(Q)
    # ---------- 영업이익 변화 분해 ----------
    if len(ys) >= 3:
        L["bridge"] = _bridge(A, ys)
    # ---------- 민감도 ----------
    s = _sens(A, ys, rec.get("ttm"), rec)
    if s:
        L["sens"] = s
    # ---------- 동종 비교 ----------
    grp = rec.get("group")
    peers = []
    for c2, r2 in recs.items():
        if r2.get("group") != grp or not r2.get("mcap"):
            continue
        t2 = r2.get("ttm") or {}
        peers.append({"code": c2, "name": r2.get("name"), "self": c2 == code, "mcap": r2.get("mcap"),
                      "rev": t2.get("rev"), "opm": round(t2["op"] / t2["rev"] * 100, 1) if t2.get("rev") and t2.get("op") is not None else None,
                      "ni": t2.get("ni"), "roe": r2.get("roe"), "per": r2.get("per"), "pbr": r2.get("pbr")})
    if len(peers) >= 3:
        peers.sort(key=lambda x: -(x["mcap"] or 0))
        me = next((p for p in peers if p["self"]), None)
        if not me:
            peers = []
    if len(peers) >= 3:
        top = [p for p in peers if not p["self"]][:6]
        roes = [p["roe"] for p in peers if p["roe"] is not None]
        pers = [p["per"] for p in peers if p["per"] and p["per"] > 0]
        mr, mp = (st.median(roes) if roes else None), (st.median(pers) if pers else None)
        om = [p["opm"] for p in peers if p["opm"] is not None]
        mo = st.median(om) if om else None
        L["peers"] = {"group": grp, "n": len(peers), "rows": sorted(top + [me], key=lambda x: -(x["mcap"] or 0)),
                      "med_roe": round(mr, 1) if mr is not None else None, "med_per": round(mp, 1) if mp else None,
                      "med_opm": round(mo, 1) if mo is not None else None}
    if L:
        rec["lens"] = L
