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



def _num(s):
    try:
        return float(str(s).replace(",", "").strip())
    except Exception:  # noqa: BLE001
        return None


def _eok(s):
    """네이버 '7조 5,807억' → 백만원"""
    import re
    if not s or s == "N/A":
        return None
    s = s.replace(",", "").replace(" ", "")
    t = 0.0
    m = re.search(r"([\d.]+)조", s)
    t += float(m.group(1)) * 1e4 if m else 0
    m = re.search(r"([\d.]+)억", s)
    t += float(m.group(1)) if m else 0
    return t * 100 if t else None


def listed_shares(mk, code):
    """외부(네이버 금융) 시가총액 ÷ 주가로 본 현재 상장주식수(자기주식 포함). raw/audit/market_check.json."""
    n = ((mk.get(code) or {}).get("naver") or {})
    mv, px = _eok((n.get("infos") or {}).get("marketValue")), _num((n.get("basic") or {}).get("closePrice"))
    return round(mv * 1e6 / px) if mv and px else None


def resolve_shares(dart_out, dart_issued, listed):
    """유통주식수(자기주식 제외)와 상장주식수를 정한다.

    DART 유통주식수는 마지막 정기보고서 시점 값이라 그 뒤의 무상증자·액면병합·유상증자를 모른다.
    네이버 상장주식수(현재, 자기주식 포함)가 있으면 그것을 기준으로 하고, 자기주식만 DART에서 뺀다.
    반환 (유통, 상장, 메모)
    """
    if not listed:
        return dart_out, dart_out, None
    if not dart_out:
        return listed, listed, "DART 주식수 없음: 상장주식수 사용"
    if dart_issued and dart_issued >= dart_out:
        tre = dart_issued - dart_out
        out = listed - tre
        if out > 0.5 * listed:
            return out, listed, None
    r = listed / dart_out
    if 0.99 <= r <= 1.5:  # 차이는 자기주식으로 본다(네이버 시총이 억 단위 반올림이라 1% 오차 허용)
        return dart_out, max(listed, dart_out), None
    return listed, listed, f"DART 유통주식수 {dart_out:,.0f}주 → 현재 상장 {listed:,.0f}주(보고서 이후 주식 수 변동)"



def ttm_keys(Q):
    """최근 4개 '연속' 분기(순이익 값이 있는)만 TTM으로 쓴다. 중간 분기가 비면 그 앞의 연속 4개 분기."""
    qi = lambda k: int(k[:4]) * 4 + int(k[-1]) - 1
    ks = [k for k in sorted(Q) if (Q[k] or {}).get("ni") is not None]
    for i in range(len(ks) - 4, -1, -1):
        w = ks[i:i + 4]
        if qi(w[-1]) - qi(w[0]) == 3:
            return w
    return []


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


def terminal_c(c, r, gT, roe=None):
    """영구 성장 구간(11년차~)의 현금 전환율 c_T.
    이익의 (1−c)를 재투자해 gT만큼 자란다면 새 투자의 수익률은 gT/(1−c)예요. c=0.5, gT=2%면 '새 투자가 영원히 4%만 번다'는
    가정이라, 정상 ROE가 10%를 넘는 회사에는 지나치게 박해요. 새 투자가 버는 수익률 = min(자기자본비용 r, 이 회사의 정상 ROE)로 보고
    c_T = max(c, 1 − gT / 그 수익률)로 둬요. 정상 ROE가 낮은 회사(자산은 많은데 이익이 적은 회사)는 c가 거의 그대로라
    '싸 보이는 저PBR'을 기계적으로 올려 주지 않아요. 설정 파일의 c_T가 있으면 그 값을 써요."""
    ret = min(r, roe) if roe is not None and roe > 0 else r
    return round(max(c, 1 - gT / ret), 3) if ret > gT else c


def equity_value(E1, g1, r, c, gT, cT=None):
    """주주잉여현금흐름(FCFE = 이익 × c) 10년 + 영구가치. 단위는 E1과 동일.
    6~10년차에 성장률이 gT로 수렴하는 동안 현금 전환율도 c → c_T로 함께 옮겨가요(성장이 줄면 재투자도 준다)."""
    if cT is None:
        cT = c
    r, gT_, g1_ = r / 100, gT / 100, g1 / 100
    gs = path_growth(g1_, gT_)
    pv, E = 0.0, E1
    for t in range(1, 11):
        if t > 1:
            E *= 1 + gs[t - 1]
        ct = c if t <= 5 else c + (cT - c) * (t - 5) / 5
        pv += E * ct / (1 + r) ** t
    tv = E * (1 + gT_) * cT / (r - gT_)
    return pv + tv / (1 + r) ** 10


# 사이클 위치별 기본 초과이익 경로: 최근 4분기 순이익과 정상 이익의 차이가 앞으로 몇 해 동안 얼마나 남는지(비율)
CYCLE_PATH = {"호황 정점권": [0.7, 0.3], "상승기": [1.0, 0.7, 0.3], "회복기": [0.8, 0.4], "중립": [],
              "하강기": [0.8, 0.4], "바닥권": [0.7, 0.3]}


TAX_OP = 0.78  # 영업이익 → 세후 이익(법인세 약 22%), scripts/backtest/model.py의 TAX와 같은 값


def core_margins(A, ys, k_ys=None):
    """연도별 순이익률. 단, 영업은 흑자인데 순이익만 평소와 크게 어긋난 해(손상차손·대손충당금·처분손익 같은 일회성)는
    '그해 세후 영업이익 × 이 회사의 평소 비율(순이익 ÷ 세후 영업이익, 중앙값)'로 바꿔요.
    평소 비율에 이자·지분법·비지배지분 같은 구조적 차이가 들어 있어서, 원래 있는 이자 부담은 그대로 남아요.
    어긋남 기준: 그해 비율이 평소의 0.35배 미만이거나 2.5배 초과, 그리고 차이가 매출의 0.5% 이상.
    그런 해가 2개 이하이고 전체의 ¼ 미만일 때만 바꿔요. 더 자주 나오면 일회성이 아니라 사업의 일부로 봐요.
    반환: (순이익률 목록, 바꾼 해 목록[{year, ni_margin, adj_margin}])"""
    import statistics as st
    raw = [A[y]["ni"] / A[y]["rev"] for y in ys]
    pos = [y for y in ys if (A[y].get("op") or 0) > 0]
    k = op_ni_ratio(A, k_ys or ys)
    if len(pos) < 3 or k is None:
        return raw, []
    flag = set()
    for y in pos:
        op = A[y]["op"] * TAX_OP
        q = A[y]["ni"] / op
        if (q < 0.35 * k or q > 2.5 * k) and abs(A[y]["ni"] - k * op) >= 0.005 * A[y]["rev"]:
            flag.add(y)
    if not flag or len(flag) > 2 or len(flag) * 4 >= len(ys):
        return raw, []
    out, adj = [], []
    for y, m in zip(ys, raw):
        if y in flag:
            a = A[y]["op"] * TAX_OP * k / A[y]["rev"]
            adj.append({"year": y, "ni_margin": round(m * 100, 2), "adj_margin": round(a * 100, 2)})
            out.append(a)
        else:
            out.append(m)
    return out, adj


def op_ni_ratio(A, ys=None):
    """이 회사의 평소 '순이익 ÷ 세후 영업이익' 비율(영업 흑자인 해의 중앙값). 이자·지분법·비지배지분 같은 구조적 차이를 담아요."""
    import statistics as st
    ys = [y for y in (ys or A) if (A.get(y) or {}).get("ni") is not None and (A[y].get("op") or 0) > 0 and (A[y].get("rev") or 0) > 0]
    if len(ys) < 4:
        return None
    k = st.median(A[y]["ni"] / (A[y]["op"] * TAX_OP) for y in ys)
    return k if k > 0 else None


def core_ttm(co, ttm):
    """최근 4개 분기 순이익에 일회성 손익이 섞였는지 보고, 섞였으면 '세후 영업이익 × 평소 비율'로 바꾼 값을 돌려줘요.
    기준은 연도별 보정(core_margins)과 같아요. 반환 None(보정 없음) 또는 {"ni", "raw", "k"}."""
    if not ttm or (ttm.get("op") or 0) <= 0 or not ttm.get("rev"):
        return None
    A = co.get("annual") or {}
    k = op_ni_ratio(A)
    if k is None:
        return None
    # 최근 3년 비율도 본다: 지분법 이익이 커지는 등 구조가 바뀌어 최근 몇 해 내내 비율이 달라졌다면 일회성이 아니에요
    ys = [y for y in sorted(A) if A[y].get("ni") is not None and (A[y].get("op") or 0) > 0][-3:]
    rs = sorted(A[y]["ni"] / (A[y]["op"] * TAX_OP) for y in ys)
    k_rec = rs[len(rs) // 2] if rs else k
    op = ttm["op"] * TAX_OP
    q = ttm["ni"] / op
    off = lambda kk: kk > 0 and (q < 0.35 * kk or q > 2.5 * kk)
    if off(k) and (len(rs) < 3 or off(k_rec)) and abs(ttm["ni"] - k * op) >= 0.005 * ttm["rev"]:
        return {"ni": round(k * op), "raw": ttm["ni"], "k": round(k, 2)}
    return None


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
    ms, adj = core_margins(A, ys)
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
            "trend_rev": round(tr), "ttm_rev": ttm_rev, "norm_ni": round(tr * mm), "trend_g": round((math.exp(b) - 1) * 100, 1),
            "margins": {y: round(m * 100, 2) for y, m in zip(ys, ms)}, "oneoff": adj}


TROUGH_YEARS = 2  # 약세 시나리오에서 호황이 끝난 뒤 거치는 불황 연수(실적 랭킹 대시보드의 약세 경로와 같은 틀)


def scenario_flows(a, path, ex, E1, hb):
    """시나리오마다 '지금 이익이 정상 이익보다 높거나 낮은 상태'가 몇 해 이어지는지를 다르게 본다.
    경기순환주의 불확실성은 성장률보다 '호황(불황)이 언제 끝나느냐'에 더 크게 달려 있어서예요.
    - 설정에 ni_path(시나리오별 연도별 순이익, 억원)가 있으면 그대로 써요(사람이 업황 조사로 정한 경로).
    - 호황(초과이익 > 0): 기준 = 설정 경로, 강세 = 호황 1년 더, 약세 = 1년만 유지 → 불황 이익 2년 → 반쯤 회복 → 정상.
      불황 이익 = 과거 두 번째로 나쁜 해의 순이익률(일회성 보정) × 추세 매출, 적자는 0으로.
    - 불황(초과이익 < 0): 기준 = 설정 경로, 약세 = 부진 1년 더, 강세 = 1년 빨리 회복.
    반환 (시나리오별 초과이익 흐름[백만원], 약세에 불황 연도를 넣었는지, 불황 이익)"""
    npth = a.get("ni_path")
    if npth:
        fl = {k: [x * 100 - E1 for x in npth.get(k) or npth["base"]] for k in ("bear", "base", "bull")}
        return fl, True, None
    base = [ex * w for w in path]
    if not path or ex == 0:
        return {"bear": base, "base": base, "bull": base}, False, None
    if ex > 0:
        E_tr = None
        if hb and hb.get("margins"):
            ms = sorted(hb["margins"].values())
            tr_m = ms[1] if len(ms) >= 6 else ms[0]
            E_tr = max(0, min(E1, hb["trend_rev"] * tr_m / 100))
        if E_tr is None:
            E_tr = E1 * 0.6
        gap = E_tr - E1
        bear = [ex * path[0]] + [gap] * TROUGH_YEARS + [gap * 0.5]
        return {"bear": bear, "base": base, "bull": [ex * path[0]] + base}, True, E_tr
    return {"bear": base + [base[-1]], "base": base, "bull": base[1:]}, False, None


def implied_e1(target, g, r, c, gT, cT, nc):
    """지금 시가총액(순현금·초과이익 가치 제외)을 정당화하려면 정상 이익이 얼마여야 하나(기준 성장률 기준).
    equity_value는 이익에 비례하므로 1원당 가치로 나누면 돼요. 순현금 이자분(NC_YIELD)은 다시 더해 E1과 같은 기준으로 맞춰요."""
    per1 = equity_value(1.0, g, r, c, gT, cT)
    if per1 <= 0:
        return None
    return round(target / per1 + nc * NC_YIELD)


def implied_growth(target, E1, r, c, gT, cT=None):
    """시가총액을 정당화하는 1~5년차 성장률(역DCF). 이분법."""
    lo, hi = -30.0, 80.0
    if equity_value(E1, lo, r, c, gT, cT) > target:
        return lo
    if equity_value(E1, hi, r, c, gT, cT) < target:
        return None
    for _ in range(80):
        mid = (lo + hi) / 2
        if equity_value(E1, mid, r, c, gT, cT) < target:
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
    ms, adj = core_margins(annual, ys, k_ys=list(annual))  # 사람이 고른 기간 안에서도 일회성 해는 영업이익 기준으로 바꿔요
    m = {y: x * 100 for y, x in zip(ys, ms)}
    vals = sorted(m.values())
    used = vals[1:-1] if len(vals) >= 5 else vals
    avg = sum(used) / len(used)
    return {"years": f"{ys[0]}~{ys[-1]}", "n": len(ys), "trimmed": len(vals) >= 5,
            "excluded": sorted(ex), "margins": {y: round(v, 1) for y, v in m.items()},
            "avg_margin": round(avg, 1), "min": round(vals[0], 1), "max": round(vals[-1], 1),
            "ni": round(avg / 100 * ttm_rev), "oneoff": adj}


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
                     bull=round(v["bull"] * 1e6 / rec["shares"]), upside=round((v["base"] / rec.get("mcap_eff", rec["mcap"]) - 1) * 100, 1))
            rows.append((rec, q, math.log(v["base"] / rec.get("mcap_eff", rec["mcap"]))))
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
    ccfg = load(P(*cd, "companies.json"), []) or []
    manual = {c["code"]: c["shares"] for c in ccfg if c.get("shares")}
    manual_pref = {c["code"]: c["pref_shares"] for c in ccfg if c.get("pref_shares")}
    pref_cfg = {c["code"]: c["pref"] for c in ccfg if c.get("pref")}
    # 외부 대조(네이버 금융 상장주식수·우선주 종가): scripts/audit_market.py가 매일 갱신
    mk = (load(P("raw", "audit", "market_check.json"), {}) or {}).get("codes", {})
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
        ks = ttm_keys(Q)
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
            yk = [y for y in sorted(A)[-dft["E1_years"]:] if A[y].get("ni") is not None and (A[y].get("rev") or 0) > 0]
            ms, adj = core_margins(A, yk, k_ys=list(A))
            ys = [m * A[y]["rev"] for y, m in zip(yk, ms)]  # 일회성 해는 영업이익 기준 이익으로
            if adj:
                rec["oneoff_years"] = adj
            if len(ys) >= 3 and sum(ys) > 0:
                a = dict(dft, E1=round(sum(ys) / len(ys) / 100))
                a["note"] = dft.get("note", "").replace("{n}", str(len(ys)))
                rec["auto"] = True
        elif not a and dft and rec.get("ttm") and (core_ttm(co, rec["ttm"]) or rec["ttm"])["ni"] > 0:
            # 개별 가정이 없는 회사: 최근 4개 분기 순이익을 쓰는 자동 가정(일회성 손익이 섞였으면 영업이익 기준으로 바꿔요)
            ct = core_ttm(co, rec["ttm"])
            a = dict(dft, E1=round((ct or rec["ttm"])["ni"] / 100))
            if ct:
                rec["ttm_core"] = ct
                a["note"] = (dft.get("note", "") + f" 최근 4개 분기 순이익 {ct['raw'] / 100:,.0f}억원에 일회성 손익이 섞여 영업이익 기준 {ct['ni'] / 100:,.0f}억원으로 바꿨어요").strip()
            rec["auto"] = True
        snap = (a or {}).get("snapshot") or {}
        px = prices.get(code)
        qt = quotes.get(code)
        dsh = co.get("shares") or {}  # DART 유통주식수 (보통주·우선주)
        lst = listed_shares(mk, code)
        sh_out, sh_lst, sh_note = resolve_shares(dsh.get("common") or snap.get("shares") or manual.get(code),
                                                 dsh.get("common_issued"), lst)
        if px and px.get("shares") and not lst:
            sh_lst = px["shares"]
        shares0 = sh_out
        if not shares0:
            out["companies"][code] = rec
            continue
        pref = co.get("pref") or pref_cfg.get(code) or (mk.get(code) or {}).get("pref_found")
        p_lst = listed_shares(mk, pref) if pref else None
        p_out, p_lst, _ = resolve_shares(dsh.get("pref") or manual_pref.get(code), dsh.get("pref_issued"), p_lst) if pref else (None, None, None)
        pq = quotes.get(pref) if pref else None
        pprice = (pq or {}).get("price")
        if pref and not pprice:  # 우선주 시세가 없으면 네이버 대조 파일의 종가
            pprice = _num((((mk.get(pref) or {}).get("naver") or {}).get("basic") or {}).get("closePrice"))
        if qt and qt.get("price"):
            price, pdate, psrc = qt["price"], qt.get("time"), qsrc or "실시간 시세"
        elif px and px.get("price"):
            price, pdate, psrc = px["price"], px.get("date"), "금융위원회 주식시세정보"
        elif snap.get("price"):
            price, pdate, psrc = snap["price"], snap["price_date"], "StockAnalysis 스냅샷"
        else:
            out["companies"][code] = rec
            continue
        # 시가총액(표시) = 상장주식수(자기주식 포함) × 주가 + 우선주 — 네이버·거래소 표기와 같은 기준
        # 평가 기준 시가총액 = 유통주식수(자기주식 제외) × 주가 + 우선주 → PER·PBR·적정가 괴리율에 사용
        mcap = round(price * (sh_lst or shares0) / 1e6)
        mcap_eff = round(price * shares0 / 1e6)
        if pref and p_out:
            pp = pprice or price  # 우선주 시세를 끝내 못 구하면 보통주 가격으로(보수적)
            mcap += round(pp * (p_lst or p_out) / 1e6)
            mcap_eff += round(pp * p_out / 1e6)
        sh_chk = {"dart_common": dsh.get("common"), "dart_period": dsh.get("period"), "listed": lst,
                  "pref": pref, "pref_shares": p_out, "pref_price": pprice}
        if sh_note:
            sh_chk["note"] = sh_note
        bs = co.get("bs") or {}
        equity = bs.get("equity") or snap.get("equity")
        eq_src = f"DART {bs.get('period')}" if bs.get("equity") else "스냅샷(PBR 역산)"
        if bs.get("cash") is not None and bs.get("debt") is not None:
            net_cash = (bs.get("cash") or 0) + (bs.get("st_fin") or 0) - (bs.get("debt") or 0)
            if not bs.get("debt") and snap.get("net_cash") is not None:  # 차입금 계정을 못 찾은 경우 보수적으로
                net_cash = min(net_cash, snap["net_cash"])
        else:
            net_cash = snap.get("net_cash")
        nc_note = None
        if a and a.get("net_cash_now") is not None:
            # 분기 보고서 반영 전 최신 순현금(잠정실적 발표·IR, 억원)을 사람이 정한 경우
            net_cash = a["net_cash_now"] * 100
            nc_note = a.get("net_cash_note", "최신 발표 기준 순현금")
        # 주당 가치: 평가 기준 시가총액을 보통주 가격으로 나눈 '보통주 환산 유통주식수'로 나눈다
        # (우선주는 시장가 비율만큼 가치를 나눠 가짐) → 적정주가/현재가 − 1 = 괴리율이 정확히 맞는다
        shares = round(mcap_eff * 1e6 / price)
        rec.update(price=price, price_date=pdate, price_source=psrc, mcap=mcap, mcap_eff=mcap_eff, shares=shares,
                   shares_check=sh_chk,
                   equity=equity, equity_source=eq_src, net_cash=net_cash, **({"net_cash_note": nc_note} if nc_note else {}),
                   dividend_yield=snap.get("dividend_yield"))
        t = rec.get("ttm")
        if t:
            ni = t["ni"]
            rec["per"] = round(mcap_eff / ni, 1) if ni > 0 else None
            rec["roe"] = round(ni / equity * 100, 1) if equity else None
        rec["pbr"] = round(mcap_eff / equity, 2) if equity and equity > 0 else None
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
            ct = core_ttm(co, t)
            if ct:  # 최근 4분기에 일회성 손익이 섞였으면 초과(부족) 이익도 영업이익 기준으로
                ni_now = ct["ni"]
                rec["ttm_news"] = {"period": f"{t['period']} 일회성 손익 제외(영업이익 기준)", "ni": ni_now}
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
            flows, bear_trough, E_tr = scenario_flows(a, path, ex, E1, hb)
            disc = lambda fl: round(sum(f * a["c"] / (1 + a["r"] / 100) ** (i + 1) for i, f in enumerate(fl)))
            xv_by = {k: disc(fl) for k, fl in flows.items()}
            xv = xv_by["base"]
            cy = {"position": a.get("cyc_pos", "중립"), "note": a.get("cycle_note", ""), "path": path,
                  "excess": ex, "excess_value": xv, "excess_by": xv_by, "bear_trough": bear_trough,
                  # 시나리오별 연도별 순이익 경로(백만원): 이 뒤로는 정상 이익 E1에서 시나리오 성장률로 자라요
                  "ni_paths": {k: [round(E1 + f) for f in fl] for k, fl in flows.items()},
                  **({"trough_ni": round(E_tr)} if E_tr is not None else {}),
                  **({"path_note": a["ni_path_note"]} if a.get("ni_path_note") else {})}
        roe_n = E1 / equity * 100 if equity and equity > 0 else None  # 정상 이익 기준 ROE(%)
        if a.get("c_T"):
            cT = a["c_T"]
        elif co.get("group") in (cfg.get("c_T_keep_groups") or []):
            cT = a["c"]  # 선박·항공기처럼 성장이 없어도 교체 투자가 감가상각보다 큰 업종은 c를 그대로 둬요
        elif any(w in (a.get("note") or "") + co["name"] for w in ("지주", "홀딩스")):
            cT = a["c"]  # 지주회사는 c를 낮춰 '배당으로만 현금이 올라온다'는 지주 할인을 넣었어요. 재투자 문제가 아니라 그대로 둬요
        else:
            cT = terminal_c(a["c"], a["r"], gT, roe_n)
        sc = {}
        xv_by = (cy or {}).get("excess_by") or {}
        for k in ("bear", "base", "bull"):
            v = equity_value(E_op, a["g"][k], a["r"], a["c"], gT, cT) + nc + xv_by.get(k, xv)
            v = max(v, 0)
            sc[k] = {"g": a["g"][k], "value": round(v), "per_share": round(v * 1e6 / shares),
                     "upside": round((v / mcap_eff - 1) * 100, 1)}
        rec["dcf"] = {"E1": E1, "r": a["r"], "c": a["c"], "note": a.get("note", ""),
                      "fwd_per": round(mcap_eff / E1f, 1) if E1f else None,
                      "norm_per": round(mcap_eff / E1, 1) if E1 > 0 else None, "scenarios": sc,
                      "c_T": cT, "roe_norm": round(roe_n, 1) if roe_n is not None else None,
                      "implied_g": implied_growth(mcap_eff - nc - xv, E_op, a["r"], a["c"], gT, cT),
                      "implied_E1": implied_e1(mcap_eff - nc - xv, a["g"]["base"], a["r"], a["c"], gT, cT, nc),
                      **({"cycle": cy} if cy else {}),
                      "net_cash_added": nc}
        out["companies"][code] = rec
    try:
        quant_check(cos, out, cfg, dd)
    except Exception as e:  # noqa: BLE001  검증 모델 오류가 본 계산을 막지 않게
        print("quant_check 실패:", e)
    try:
        # 하워드 막스식 점검(위험=영구 손실, 사이클·진자, 안전마진, 가격이 가정하는 것, 비대칭). 기존 dcf는 그대로.
        import sys as _s
        _s.path.insert(0, os.path.join(ROOT, "scripts"))
        import marks
        marks.apply(cos, out, cfg, equity_value, cycle_base, gT, NC_YIELD, ROOT, dd)
    except Exception as e:  # noqa: BLE001
        import traceback; traceback.print_exc()
        print("marks 실패:", e)
    try:
        # 투자지표 타일·버핏/린치/피셔 숫자 체크(실적 랭킹 대시보드 형식 참고). 적정가는 바꾸지 않아요.
        import sys as _s
        _s.path.insert(0, os.path.join(ROOT, "scripts"))
        import checks
        checks.apply(cos, out, cfg, ROOT, dd)
    except Exception as e:  # noqa: BLE001
        import traceback; traceback.print_exc()
        print("checks 실패:", e)
    out["companies"] = {c["code"]: out["companies"][c["code"]] for c in cos.get("companies", [])
                        if c["code"] in out["companies"]}
    with open(P(*dd, "valuation.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("valuation.json:", len(out["companies"]), "개사")


if __name__ == "__main__":
    import sys
    main(sys.argv[sys.argv.index("--industry") + 1] if "--industry" in sys.argv else "cosmetics")
