"""백테스트로 검증한 기계식 적정가 모델(공용). build_valuation.py와 scripts/backtest/*에서 같이 씀.

입력은 '그 시점에 알 수 있던' 연간·분기 실적과 주가뿐이고, 사람의 판단(사이클 위치·회사별 가정·뉴스)은 쓰지 않아요.
변형(variant)별로 정상 이익 E·성장률 g를 다르게 잡고, 마지막에 업종 상대가치를 섞을 수 있어요.
"""
import math, statistics as st

TAX = 0.78  # 영업이익 → 세후 이익 환산(법인세 등 약 22%)
CYCLE_PATH = {"상승기": [1.0, 0.7, 0.3], "하강기": [0.8, 0.4], "회복기": [0.8, 0.4], "바닥권": [0.7, 0.3], "중립": []}


def path_growth(g1, gT, years=10):
    return [g1 if t <= 5 else g1 + (gT - g1) * (t - 5) / 5 for t in range(1, years + 1)]


def equity_value(E1, g1, r, c, gT=2.0):
    r, gT_, g1_ = r / 100, gT / 100, g1 / 100
    gs = path_growth(g1_, gT_)
    pv, E = 0.0, E1
    for t in range(1, 11):
        if t > 1:
            E *= 1 + gs[t - 1]
        pv += E * c / (1 + r) ** t
    return pv + E * (1 + gT_) * c / (r - gT_) / (1 + r) ** 10


def features(annual, quarterly):
    """연간(공시된 해만)·분기(공시된 분기만) 실적 → 모델 입력값. 분기 4개 미만이면 None."""
    A, Q = annual or {}, quarterly or {}
    ks = sorted(Q)
    if len(ks) < 4:
        return None
    last4 = ks[-4:]
    s = lambda keys, m: sum((Q[k].get(m) or 0) for k in keys)
    f = {"period": f"{last4[0]}~{last4[-1]}", "ttm_ni": s(last4, "ni"), "ttm_op": s(last4, "op"), "ttm_rev": s(last4, "rev")}
    # 이익 모멘텀: 최근 2개 분기 영업이익 vs 1년 전 같은 2개 분기
    l2 = ks[-2:]
    p2 = [f"{int(k[:4]) - 1}Q{k[-1]}" for k in l2]
    if all(k in Q for k in p2):
        a, b = s(l2, "op"), s(p2, "op")
        f["mom"] = (a - b) / abs(b) if b else (1.0 if a > 0 else -1.0)
        f["rev_mom"] = (s(l2, "rev") / s(p2, "rev") - 1) if s(p2, "rev") > 0 else None
    # 일회성 손익을 덜 타는 '핵심 이익': 순이익과 세후 영업이익의 평균, 둘이 크게 다르면 영업이익 쪽
    op_at = f["ttm_op"] * TAX
    ni = f["ttm_ni"]
    # 최근 2개 분기를 연환산한 핵심 이익(지금 이익 속도)
    o2, n2 = s(l2, "op") * TAX * 2, s(l2, "ni") * 2
    f["run"] = o2 if (o2 > 0 and (n2 > 2 * o2 or n2 < 0.3 * o2)) else (o2 + n2) / 2
    f["core"] = op_at if (op_at > 0 and (ni > 2 * op_at or ni < 0.3 * op_at)) else (ni + op_at) / 2
    # 사이클 평균 이익(순이익률 절사평균 × 추세 매출) — build_valuation.cycle_base와 같은 계산
    ys = [y for y in sorted(A) if (A[y].get("rev") or 0) > 0 and A[y].get("ni") is not None]
    if len(ys) >= 3 and f["ttm_rev"] > 0:
        ms = [A[y]["ni"] / A[y]["rev"] for y in ys]
        tm = sorted(ms)[1:-1] if len(ms) >= 6 else ms
        mm = sum(tm) / len(tm)
        te = int(last4[-1][:4]) + int(last4[-1][-1]) / 4 - .5
        pts = [(int(y) + .5, math.log(A[y]["rev"])) for y in ys] + [(te, math.log(f["ttm_rev"]))]
        n = len(pts); mx = sum(p[0] for p in pts) / n; my = sum(p[1] for p in pts) / n
        b = sum((p[0] - mx) * (p[1] - my) for p in pts) / sum((p[0] - mx) ** 2 for p in pts)
        f["norm"] = math.exp(my + b * (te - mx)) * mm
        f["norm_margin"] = mm * 100
        f["trend_g"] = (math.exp(b) - 1) * 100
        f["years"] = f"{ys[0]}~{ys[-1]}"
        # 매출 성장의 안정성: 감소한 해 비율
        f["rev_down_share"] = sum(1 for a, b2 in zip(ys, ys[1:]) if A[b2]["rev"] < A[a]["rev"]) / max(1, len(ys) - 1)
    return f


def auto_position(f):
    """사람 판단 대신 숫자로 정하는 사이클 위치: 최근 핵심 이익이 정상 이익보다 높은가 × 이익이 늘고 있는가."""
    if f.get("norm") is None or f.get("mom") is None:
        return "중립"
    hi = f["core"] > f["norm"] * 1.1
    lo = f["core"] < f["norm"] * 0.9
    up = f["mom"] > 0.05
    dn = f["mom"] < -0.05
    if hi and up: return "상승기"
    if hi and dn: return "하강기"
    if lo and up: return "회복기"
    if lo and dn: return "바닥권"
    return "중립"


VARIANTS = {
    "A": "최근 4분기 순이익",
    "B": "사이클 평균 이익(현행 기본)",
    "C": "핵심 이익(일회성 제거)",
    "D": "사이클 평균 + 숫자로 정한 사이클 위치",
    "E": "D + 추세 성장률",
    "F": "E + 업종 상대가치 50%",
    "G": "사이클 평균 50% + 핵심 이익 50%",
    "H": "사이클 평균 50% + 최근 2분기 연환산 이익 50%",
}


def fair_value(f, par, variant):
    """적정 주주가치(백만원)와 근거. par = {g:{bear,base,bull}, r, c}. 업종 상대가치(F)는 relative()에서 따로 섞음."""
    r, c = par["r"], par["c"]
    g = dict(par["g"])
    pos, xv = "중립", 0.0
    if variant == "A":
        E = f["ttm_ni"]
    elif variant == "C":
        E = f["core"]
    elif variant in ("G", "H"):
        if f.get("norm") is None:
            return None
        E = 0.5 * f["norm"] + 0.5 * (f["core"] if variant == "G" else f["run"])
    else:
        E = f.get("norm")
        if E is None:
            return None
        if variant in ("D", "E", "F"):
            pos = auto_position(f)
            ex = f["core"] - E
            xv = sum(ex * w * c / (1 + r / 100) ** (i + 1) for i, w in enumerate(CYCLE_PATH[pos]))
        if variant in ("E", "F") and f.get("trend_g") is not None:
            # 구조 성장률: 업종 기본 성장률과 과거 추세 매출 성장률의 평균, -3~12% 사이
            tg = max(-3.0, min(12.0, f["trend_g"]))
            d = (g["base"] + tg) / 2 - g["base"]
            g = {k: v + d for k, v in g.items()}
    if E is None or E <= 0:
        return None
    vals = {k: max(0.0, equity_value(E, g[k], r, c) + xv) for k in ("bear", "base", "bull")}
    return {"E": E, "g": g["base"], "pos": pos, "excess_value": xv, **vals}


def relative(rows, key="fv", w=0.5):
    """업종 상대가치: 같은 업종 표본의 '시가총액 ÷ 정상 이익' 중앙값을 각 회사 정상 이익에 곱한 값을 w만큼 섞음.
    모두 같은 시점 주가만 쓰므로 미래참조가 없어요. rows: [{mcap, fv:{E, base, bear, bull}}]."""
    pes = [r["mcap"] / r[key]["E"] for r in rows if r.get(key) and r[key]["E"] > 0 and r["mcap"] > 0]
    if len(pes) < 5:
        return None
    med = st.median(pes)
    for r in rows:
        v = r.get(key)
        if not v:
            continue
        rel = v["E"] * med + v.get("excess_value", 0)
        b0 = v["base"]
        for k in ("bear", "base", "bull"):
            v[k] = (1 - w) * v[k] + w * rel * (v[k] / b0 if b0 else 1)
        v["rel_pe"] = med
    return med
