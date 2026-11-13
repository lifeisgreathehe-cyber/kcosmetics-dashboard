"""하워드 막스식 점검: 기존 적정가(정상 이익 DCF) 위에 '위험·사이클·가격이 가정하는 것'을 얹는다.

build_valuation.py가 회사별 계산을 끝낸 뒤 apply()를 불러 rec["marks"]와 out["marks_meta"]를 붙인다.
기존 dcf 값은 바꾸지 않는다(백테스트·비교표와의 연속성). 원칙 요약은 docs/shared/marks.js에 있다.

1) 위험 = 영구적 손실 가능성: 변동성이 아니라 '불황이 길어지면 얼마까지 잃을 수 있나'를 본다.
   불황 이익 = 과거 가장 나쁜 수준의 순이익률(6년 이상이면 두 번째로 나쁜 해) × 추세 매출.
   하방 가치 = 비관 시나리오 − 불황이 3년 이어지는 동안의 이익 부족분(현재가치) − 호황 초과이익 가치.
2) 사이클과 진자: 회사의 사이클 위치(정점권이면 비관 쪽, 바닥권이면 낙관 쪽으로 확률을 옮김)와
   업종 전체의 '온도'(주가가 적정가보다 얼마나 앞서 있나)로 시나리오 확률을 정한다 → 확률 가중 가치.
3) 안전마진: 위험 점수·사이클·온도로 필요한 할인율(15~55%)을 정하고, 확률 가중 가치 × (1 − 할인율) = 안전마진 매수가.
4) 2단계 사고: 지금 시가총액이 정당화되려면 순이익률이 몇 %로 유지돼야 하는지(역산)를 과거 범위와 비교한다.
5) 비대칭: 현재가에서 낙관 시나리오까지 오를 폭 ÷ 하방 가치까지 내릴 폭.
"""
import json, os, statistics as st

POS = ["호황 정점권", "상승기", "중립", "하강기", "바닥권", "회복기"]
# 사이클 위치별 (비관, 기준, 낙관) 확률. 정상 이익으로 '이익 수준'은 이미 맞췄으므로 여기서는 앞으로의 방향만 기운다.
W = {"호황 정점권": (.45, .40, .15), "상승기": (.35, .45, .20), "중립": (.25, .50, .25),
     "하강기": (.30, .50, .20), "바닥권": (.15, .45, .40), "회복기": (.20, .50, .30)}
# 사이클 위치별 필요한 안전마진 가감(%p): 정점권은 이익이 꺾일 때 손실이 크고, 바닥권은 나쁜 소식이 이미 가격에 있다.
MOS_CYC = {"호황 정점권": 10, "상승기": 5, "중립": 0, "하강기": 5, "바닥권": -5, "회복기": 0}
STRESS_YEARS = 3
MOS_BASE = {"낮음": 20, "보통": 30, "높음": 40}


def norm_pos(t):
    """대시보드마다 다른 사이클 표현(확장, 업사이클 후반, 수주 공백 …)을 6개 위치로 맞춘다."""
    if not t:
        return None
    t = str(t)
    if t in POS:
        return t
    for keys, p in ((("정점", "후반", "피크"), "호황 정점권"), (("회복", "통과", "반등"), "회복기"),
                    (("바닥", "저점", "구조적 하락"), "바닥권"), (("둔화", "하강", "공백", "하락", "조정"), "하강기"),
                    (("확장", "성장", "상승", "업사이클", "호황"), "상승기"), (("안정", "성숙", "중립"), "중립")):
        if any(k in t for k in keys):
            return p
    return None


def _pos_of(rec):
    d = rec.get("dcf") or {}
    for src, t in (("회사별 판단", (d.get("cycle") or {}).get("position")),
                   ("회사별 판단", (rec.get("cycle") or {}).get("position")),
                   ("회사별 판단", (rec.get("cycle") or {}).get("phase"))):
        p = norm_pos(t)
        if p:
            return p, src, t
    q = (rec.get("quant") or {}).get("pos")
    if q:
        return q, "숫자로 판단(최근 이익 vs 사이클 평균 × 이익 추세)", q
    return "중립", "판단 근거 없음", None


def temperature(recs):
    """업종 진자: 적정가(기준)보다 비싼 회사 비율과 괴리율 중앙값으로 낙관·비관 쏠림을 본다."""
    ups = [r["dcf"]["scenarios"]["base"]["upside"] for r in recs if r.get("dcf")]
    if len(ups) < 5:
        return None
    med = st.median(ups)
    above = sum(u < 0 for u in ups) / len(ups)
    if med <= -15 or above >= .65:
        lab, sh = "과열(낙관 쪽)", 1
    elif med <= -5 or above >= .55:
        lab, sh = "다소 뜨거움", 0
    elif med >= 25 or above <= .25:
        lab, sh = "냉각(비관 쪽)", -1
    elif med >= 10 or above <= .35:
        lab, sh = "다소 차가움", 0
    else:
        lab, sh = "중간", 0
    return {"n": len(ups), "median_upside": round(med, 1), "share_above": round(above * 100), "label": lab, "shift": sh}


def apply(cos, out, cfg, ev, cycle_base, gT, nc_yield, root, dd):
    by = {c["code"]: c for c in cos.get("companies", [])}
    recs = [r for r in out["companies"].values() if r.get("dcf") and r.get("shares")]
    temp = temperature(recs)
    sh = (temp or {}).get("shift", 0)
    for code, rec in out["companies"].items():
        d = rec.get("dcf")
        if not d or not rec.get("shares") or not rec.get("price"):
            continue
        co = by.get(code) or {}
        S, r, c = d["scenarios"], d["r"], d["c"]
        price, shares, mcap = rec["price"], rec["shares"], rec.get("mcap_eff") or rec["mcap"]
        nc = d.get("net_cash_added") or 0
        xv = (d.get("cycle") or {}).get("excess_value") or 0
        pos, psrc, praw = _pos_of(rec)
        # --- 1) 하방(영구적 손실) ---
        hb = rec.get("hist") or cycle_base(co)
        E1 = d["E1"]
        tr_m = None
        A = co.get("annual") or {}
        mc = (rec.get("cycle") or {}).get("midcycle")
        if hb and mc and mc.get("margins"):
            # 사업 구조가 바뀌어 평균 기간을 사람이 좁혀 둔 회사(화장품 등)는 그 기간의 이익률만 쓴다
            hb = dict(hb, years=mc["years"], margin=mc["avg_margin"], margin_range=[mc["min"], mc["max"]])
            ms = sorted(mc["margins"].values())
        elif hb and hb.get("margins"):
            # 일회성(손상차손·대손 등, 영업은 흑자인 해)을 걸러낸 순이익률. 불황은 '영업 이익이 줄어드는 것'이지
            # 과거 투자를 한 번에 상각한 회계 손실이 3년 내내 이어지는 게 아니에요(build_valuation.core_margins).
            ms = sorted(hb["margins"].values())
        elif hb:
            ms = sorted(A[y]["ni"] / A[y]["rev"] * 100 for y in A if (A[y].get("rev") or 0) > 0 and A[y].get("ni") is not None)
        if hb:
            tr_m = ms[1] if len(ms) >= 6 else ms[0]
            E_tr = min(E1, hb["trend_rev"] * tr_m / 100)
            how = f"{hb['years']} 중 {'두 번째로 ' if len(ms) >= 6 else '가장 '}나쁜 해의 순이익률 {tr_m:.1f}% × 추세 매출"
        else:
            E_tr = E1 * .6
            how = "실적 이력이 짧아 정상 이익의 60%를 불황 이익으로 가정"
        how += f", 이 상태가 {STRESS_YEARS}년 이어진 뒤 정상 이익으로 복귀(성장은 비관 가정)"
        # 불황이 STRESS_YEARS년 이어진 뒤 정상 이익으로 돌아온다고 보고, 비관 시나리오에서 그 기간의 이익 부족분(현재가치)을 뺀다.
        # 영구히 불황 이익을 가정하면 '일시적 하락'까지 영구 손실로 잡게 되므로(막스가 구분하는 두 위험), 기간을 정해 둔다.
        g_st = S["bear"]["g"]
        # 흑자 부족분은 현금전환율(c)만큼, 적자는 전액 현금 유출로 본다. 호황 초과이익 가치(xv>0)는 불황에선 없다.
        gap_y = (E1 - max(E_tr, 0)) * c + max(-E_tr, 0)
        short = sum(gap_y / (1 + r / 100) ** t for t in range(1, STRESS_YEARS + 1))
        stress = max(S["bear"]["value"] - max(short, 0) - max(xv, 0), 0)
        down = min(S["bear"]["value"], stress)
        down_ps = round(down * 1e6 / shares)
        loss = max(0.0, 1 - down_ps / price)
        # --- 위험 점수(0~100) ---
        ys = [y for y in A if A[y].get("ni") is not None]
        loss_share = sum(A[y]["ni"] < 0 for y in ys) / len(ys) if ys else 0
        p_loss = min(30, loss_share * 60)
        p_vol = 0
        if hb:
            lo, hi = hb["margin_range"]
            p_vol = min(25, (hi - lo) / max(abs(hb["margin"]), 2) * 8)
        eqv = rec.get("equity") or 0
        ncv = rec.get("net_cash")
        if eqv <= 0:
            p_lev = 25
        elif ncv is not None and ncv < 0:
            p_lev = min(25, -ncv / eqv * 25)
        else:
            p_lev = 0
        p_gap = min(20, loss * 25)
        score = round(p_loss + p_vol + p_lev + p_gap)
        grade = "낮음" if score < 25 else ("보통" if score < 50 else "높음")
        # --- 2) 사이클 확률 + 진자 ---
        wb, wm, wu = W.get(pos, W["중립"])
        if sh:
            m = .05 * sh
            wb, wu = round(wb + m, 2), round(max(wu - m, .05), 2)
            wm = round(1 - wb - wu, 2)
        wv = wb * S["bear"]["value"] + wm * S["base"]["value"] + wu * S["bull"]["value"]
        wv_ps = round(wv * 1e6 / shares)
        # --- 3) 안전마진 ---
        mos = MOS_BASE[grade] + MOS_CYC.get(pos, 0) + 5 * sh
        mos = max(15, min(55, mos))
        buy = round(wv_ps * (1 - mos / 100))
        # --- 4) 2단계 사고: 가격이 가정하는 순이익률 ---
        unit = ev(1.0, S["base"]["g"], r, c, gT, d.get("c_T"))
        E_imp = (mcap - nc - xv) / unit + nc * nc_yield if unit > 0 else None
        rev_ref = (hb or {}).get("trend_rev") or (rec.get("ttm") or {}).get("rev")
        imp_m = round(E_imp / rev_ref * 100, 1) if E_imp is not None and rev_ref else None
        base_m = round(E1 / rev_ref * 100, 1) if rev_ref else None
        # --- 5) 비대칭 ---
        up = S["bull"]["per_share"] / price - 1
        ratio = round(up / loss, 1) if loss > .02 and up > 0 else None
        if up <= 0:
            asym = "불리"
        elif loss <= .02:
            asym = "매우 유리"
        else:
            asym = "유리" if ratio >= 2 else ("균형" if ratio >= 1 else "불리")
        # --- 종합 ---
        if price <= buy:
            verdict, tone = "안전마진 확보", "pos"
        elif price <= wv_ps:
            verdict, tone = "가치 이하·안전마진 부족", "neu"
        elif price <= S["bull"]["per_share"]:
            verdict, tone = "기대 선반영", "neg"
        else:
            verdict, tone = "낙관 시나리오도 넘는 가격", "neg"
        note = second_level(rec, d, hb, imp_m, pos, temp, loss, up, asym, base_m)
        rec["marks"] = {
            "pos": pos, "pos_src": psrc, "pos_raw": praw,
            "weights": {"bear": wb, "base": wm, "bull": wu}, "weighted": round(wv), "weighted_ps": wv_ps,
            "weighted_upside": round((wv_ps / price - 1) * 100, 1),
            "stress": {"E": round(E_tr), "margin": round(tr_m, 1) if tr_m is not None else None, "g": g_st,
                       "value": round(stress), "per_share": round(stress * 1e6 / shares), "how": how},
            "down_ps": down_ps, "max_loss": round(loss * 100, 1), "up_bull": round(up * 100, 1),
            "asym_ratio": ratio, "asym": asym,
            "risk": {"score": score, "grade": grade,
                     "parts": {"적자 이력": round(p_loss), "이익 변동폭": round(p_vol), "차입 부담": round(p_lev), "하방 거리": round(p_gap)}},
            "mos": mos, "buy_ps": buy, "buy_gap": round((buy / price - 1) * 100, 1),
            "implied_margin": imp_m, "base_margin": base_m, "hist_margin": [hb["margin_range"][0], hb["margin"], hb["margin_range"][1]] if hb else None,
            "verdict": verdict, "tone": tone, "note": note}
    # 시장 전체 진자: 다른 대시보드가 마지막으로 만든 valuation.json의 온도를 모은다
    mkt = []
    for sub in ("", "semi", "chem", "battery", "apparel", "food", "logistics"):
        p = os.path.join(root, "docs", *( [sub] if sub else []), "data", "valuation.json")
        if os.path.join(*dd) == os.path.join("docs", *([sub] if sub else []), "data"):
            t = temp
        else:
            try:
                with open(p, encoding="utf-8") as f:
                    t = (json.load(f).get("marks_meta") or {}).get("temperature")
            except Exception:  # noqa: BLE001
                t = None
        if t:
            mkt.append({"industry": sub or "cosmetics", **t})
    out["marks_meta"] = {"temperature": temp, "market": mkt,
                         "weights": W, "mos_base": MOS_BASE, "mos_cycle": MOS_CYC}


def second_level(rec, d, hb, imp_m, pos, temp, loss, up, asym, base_m=None):
    """'시장은 이미 무엇을 가격에 넣었나'를 한두 문장으로."""
    g = d["scenarios"]["base"]["g"]
    s = []
    if imp_m is not None and hb:
        lo, avg, hi = hb["margin_range"][0], hb["margin"], hb["margin_range"][1]
        head = f"지금 주가가 맞으려면 이익이 연 {g}%씩 늘면서 순이익률 {imp_m}%가 이어져야 해요(과거 {lo}%~{hi}%, 평균 {avg}%{f", 이 리포트의 정상 이익 가정 {base_m}%" if base_m is not None else ""})."
        if imp_m > hi:
            s.append(head + " 과거 최고보다 높은 수익성을 이미 가격에 넣은 상태라, 좋은 소식이 나와도 '예상대로'일 뿐이고 실망하면 하락폭이 커요.")
        elif imp_m > avg * 1.15:
            s.append(head + " 평균보다 좋은 수익성이 이어진다는 낙관이 들어 있어요. 그 근거(신제품·점유율·가격 결정력)가 확인되는지가 관건이에요.")
        elif imp_m < max(lo, 0):
            s.append(head + " 과거 최악보다 낮은 수익성만 가정하고 있어요. 회사가 망가지지 않는다면 비관이 지나친 가격일 수 있어요.")
        elif imp_m < avg * .85:
            s.append(head + " 평균보다 낮은 수익성만 반영돼 있어 평균 회복만으로도 오를 여지가 있어요. 다만 구조적으로 경쟁력이 떨어진 거라면 이 가격이 맞아요.")
        else:
            s.append(head + " 평균적인 수익성을 가정하는 가격이라 특별한 낙관도 비관도 없어요.")
    elif d.get("implied_g") is not None:
        ig = d["implied_g"]
        s.append(f"지금 주가는 1~5년 이익이 연 {ig}%씩 늘어난다고 가정하는 셈이에요(기준 가정 {g}%).")
    if pos in ("호황 정점권", "상승기") and imp_m is not None and hb and imp_m >= hb["margin"]:
        s.append("사이클이 좋은 쪽에 있는데 가격도 좋은 수익성을 전제해, 남들과 같은 낙관에 올라타는 위치예요.")
    elif pos in ("바닥권", "하강기") and imp_m is not None and hb and imp_m < hb["margin"]:
        s.append("업황이 나쁜 쪽인데 가격도 낮은 수익성을 전제해, 남들이 피할 때 들여다볼 만한 위치예요. 회사가 불황을 버틸 체력이 있는지가 먼저예요.")
    if temp and temp["shift"] > 0:
        s.append(f"업종 전체가 {temp['label']} 상태라 확률을 비관 쪽으로 조금 옮겼어요.")
    elif temp and temp["shift"] < 0:
        s.append(f"업종 전체가 {temp['label']} 상태라 확률을 낙관 쪽으로 조금 옮겼어요.")
    tail = f"손익 구조는 '{asym}'{'이에요' if asym == '균형' else '예요'}."
    if loss < .005:
        s.append(f"불황이 길어진다고 가정한 하방 가치도 현재가보다 높고, 낙관 시나리오면 {round(up * 100):+d}%라 " + tail)
    else:
        s.append(f"불황이 길어지면 최대 약 {round(loss * 100)}% 손실, 낙관 시나리오면 {round(up * 100):+d}%로 " + tail)
    return " ".join(s)
