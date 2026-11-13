"""투자지표 타일 + 버핏·린치·피셔 숫자 체크리스트 (7개 대시보드 공용).

build_valuation.py가 회사별 계산·막스 점검을 끝낸 뒤 apply()를 불러 rec["metrics"], rec["checks"]를 붙인다.
화면은 docs/shared/checks.js의 extraBlock(v, V)가 그린다. 내재가치 리포트에 이미 있는 지표(시가총액·PER(TTM)·ROE·PBR·
순현금·정상 PER)는 다시 만들지 않고, 없는 것만 더한다: 분기 연환산 PER, POR(영업이익 기준), 컨센서스 PER, PEG, 배당수익률,
차입금 ÷ 자본, 1년 주가.
실적 랭킹 대시보드(earnings-dashboard)의 회사 페이지 형식을 참고했다(2026-11-13 채진 요청).
현금흐름(영업현금흐름·설비투자)과 연도별 자기자본은 아직 수집하지 않아, 그것이 필요한 항목(주주이익 전환율, 10년 평균 ROE)은
정상 이익 기준 ROE 같은 대체 지표로 보고 그렇게 적는다.
"""
import json, os, statistics as st


def _num(s):
    try:
        return float(str(s).replace(",", "").replace("배", "").replace("%", "").replace("원", "").strip())
    except (TypeError, ValueError):
        return None


def _cagr(a, b, n):
    if a is None or b is None or a <= 0 or b <= 0 or n <= 0:
        return None
    return ((b / a) ** (1 / n) - 1) * 100


def _ret_1y(series, price, asof):
    """월말 종가 시계열에서 12개월 전 종가 대비 현재가 변화율(%)."""
    if not series or not price:
        return None, None
    ms, cs = series.get("months") or [], series.get("close") or series.get("closes") or series.get("prices") or []
    if not ms or len(ms) != len(cs):
        return None, None
    y, m = int(asof[:4]), int(asof[5:7])
    tgt = f"{y - 1}-{m:02d}"
    if tgt in ms:
        i = ms.index(tgt)
    else:
        prev = [i for i, x in enumerate(ms) if x <= tgt]
        if not prev:
            return None, None
        i = prev[-1]
    base = cs[i]
    return (round((price / base - 1) * 100, 1), ms[i]) if base else (None, None)


def lynch_category(A, ys, rec, cyc_mode):
    """피터 린치의 6가지 분류를 숫자로 근사."""
    ni = [A[y]["ni"] for y in ys]
    rev = [A[y]["rev"] for y in ys]
    ms = [A[y]["ni"] / A[y]["rev"] * 100 for y in ys if A[y]["rev"]]
    g5 = _cagr(rev[-6], rev[-1], 5) if len(rev) >= 6 else _cagr(rev[0], rev[-1], len(rev) - 1)
    d = rec.get("dcf") or {}
    nc, mcap, pbr = rec.get("net_cash") or 0, rec.get("mcap_eff") or rec.get("mcap") or 0, rec.get("pbr")
    swing = (max(ms) - min(ms)) if ms else 0
    if len(ni) >= 3 and ni[-2] < 0 < ni[-1]:
        return "회생주", "적자에서 흑자로 돌아선 회사"
    if pbr is not None and pbr < 0.7 and mcap and nc > 0.3 * mcap:
        return "자산주", "순현금·자산이 시가총액에 비해 큰 회사"
    if (cyc_mode and swing >= 15) or swing >= 25 or any(x < 0 for x in ni):
        return "경기순환주", "업황에 따라 이익이 크게 오르내리는 회사"
    if g5 is not None and g5 >= 20:
        return "고성장주", "매출이 연 20% 이상 늘어 온 회사"
    if g5 is not None and g5 < 5:
        return "저성장주", "매출 성장률이 연 5% 미만인 회사"
    return "대형우량주(스탤워트)", "연 5~20%로 꾸준히 크는 회사"


def apply(cos, out, cfg, root, dd):
    by = {c["code"]: c for c in cos.get("companies", [])}
    mk = (json.load(open(os.path.join(root, "raw", "audit", "market_check.json"), encoding="utf-8")).get("codes", {})
          if os.path.exists(os.path.join(root, "raw", "audit", "market_check.json")) else {})
    shp = os.path.join(root, *dd, "stock_hist.json")
    sh = json.load(open(shp, encoding="utf-8")).get("series", {}) if os.path.exists(shp) else {}
    cyc_mode = bool(cfg.get("cycle_mode"))
    asof = out.get("updated")
    for code, rec in out["companies"].items():
        co = by.get(code) or {}
        if not rec.get("price") or not rec.get("mcap"):
            continue
        A = co.get("annual") or {}
        ys = [y for y in sorted(A) if (A[y].get("rev") or 0) > 0 and A[y].get("ni") is not None][-10:]
        Q = co.get("quarterly") or {}
        qk = [k for k in sorted(Q) if Q[k].get("ni") is not None]
        mcap = rec.get("mcap_eff") or rec["mcap"]
        t = rec.get("ttm") or {}
        lq = Q[qk[-1]] if qk else {}
        nv = ((mk.get(code) or {}).get("naver") or {}).get("infos") or {}
        bs = co.get("bs") or {}
        eq, debt = rec.get("equity"), bs.get("debt")
        m = {"q": qk[-1] if qk else None, "ttm_period": t.get("period")}
        m["per_q"] = round(mcap / (lq["ni"] * 4), 1) if lq.get("ni") and lq["ni"] > 0 else None
        m["ni_q"] = lq.get("ni")
        m["por_ttm"] = round(mcap / t["op"], 1) if t.get("op") and t["op"] > 0 else None
        m["op_ttm"] = t.get("op")
        m["por_q"] = round(mcap / (lq["op"] * 4), 1) if lq.get("op") and lq["op"] > 0 else None
        m["op_q"] = lq.get("op")
        m["cns_per"] = _num(nv.get("cnsPer"))
        m["div_yield"] = _num(nv.get("dividendYieldRatio"))
        m["dps"] = _num(nv.get("dividend"))
        m["debt_eq"] = round(debt / eq * 100) if debt is not None and eq and eq > 0 else None
        r1, base_m = _ret_1y(sh.get(code), rec["price"], asof)
        m["ret_1y"], m["ret_1y_from"] = r1, base_m
        # 성장률: 최근 5년 지배순이익 연평균(양 끝이 흑자일 때). 린치의 PEG는 '이익 성장률' 기준
        ni5 = _cagr(A[ys[-6]]["ni"], A[ys[-1]]["ni"], 5) if len(ys) >= 6 else None
        rv5 = _cagr(A[ys[-6]]["rev"], A[ys[-1]]["rev"], 5) if len(ys) >= 6 else None
        m["ni_cagr5"], m["rev_cagr5"] = (round(ni5, 1) if ni5 is not None else None), (round(rv5, 1) if rv5 is not None else None)
        per = rec.get("per")
        g = min(ni5, 50) if ni5 is not None else None  # 50% 넘는 성장은 지속 불가로 보고 상한
        m["peg"] = round(per / g, 2) if per and g and g > 0 else None
        m["peg_g"] = round(g, 1) if g is not None else None
        rec["metrics"] = m

        # ---------- 체크리스트 ----------
        d = rec.get("dcf") or {}
        ck = {"buffett": [], "lynch": [], "fisher": []}
        add = lambda who, name, ok, val, note="": ck[who].append({"name": name, "ok": ok, "val": val, "note": note})
        n = len(ys)
        roe_n = d.get("roe_norm")
        add("buffett", "정상 이익 기준 ROE 15% 이상", None if roe_n is None else roe_n >= 15,
            "–" if roe_n is None else f"{roe_n:.1f}%", "연도별 자기자본을 아직 수집하지 않아 10년 평균 대신 정상 이익 ÷ 현재 자본")
        roe_t = rec.get("roe")
        add("buffett", "최근 4분기 ROE 15% 이상", None if roe_t is None else roe_t >= 15, "–" if roe_t is None else f"{roe_t:.1f}%")
        loss = [y for y in ys if A[y]["ni"] < 0]
        add("buffett", f"최근 {n}년 적자 낸 해 없음", not loss if n else None, "·".join(loss) if loss else (f"{n}년 모두 흑자" if n else "–"))
        om = [A[y]["op"] / A[y]["rev"] for y in ys if A[y].get("op") is not None]
        cv = (st.pstdev(om) / abs(st.mean(om))) if len(om) >= 4 and st.mean(om) > 0 else None
        add("buffett", "영업이익률이 안정적(변동계수 0.35 미만)", None if cv is None else cv < 0.35,
            "적자 평균" if cv is None and om else ("–" if cv is None else f"{cv:.2f}"), "표준편차 ÷ 평균, 작을수록 예측 가능한 사업")
        gm = [A[y]["gp"] / A[y]["rev"] for y in ys[-5:] if A[y].get("gp") is not None]
        gma = st.mean(gm) * 100 if gm else None
        add("buffett", "매출총이익률 40% 이상(5년 평균)", None if gma is None else gma >= 40, "–" if gma is None else f"{gma:.1f}%",
            "가격 결정력의 흔적. 유통·제조 하청은 구조적으로 낮아요")
        E1 = d.get("E1")
        if debt is not None:
            yrs = debt / E1 if E1 and E1 > 0 else None
            add("buffett", "차입금을 정상 이익 4년 안에 갚을 수 있음", None if yrs is None else yrs <= 4,
                "차입 없음" if not debt else ("–" if yrs is None else f"{yrs:.1f}년"), "금융사는 해당 없음")
        # 린치
        if m["peg"] is not None or per:
            add("lynch", "PEG 1 이하 (PER ÷ 이익 성장률)", None if m["peg"] is None else m["peg"] <= 1,
                "–" if m["peg"] is None else f"{m['peg']:.2f}", f"성장률 = 최근 5년 순이익 연평균 {m['peg_g']:.1f}%(상한 50%)" if m["peg_g"] is not None else "5년 전 또는 지금이 적자라 성장률 계산 불가")
        dy = m["div_yield"] or 0
        tr = (g + dy) / per if per and g is not None else None
        add("lynch", "(성장률 + 배당수익률) ÷ PER 1.5 이상", None if tr is None else tr >= 1.5, "–" if tr is None else f"{tr:.1f}", "2 이상이면 매우 좋음")
        nc = rec.get("net_cash")
        add("lynch", "순현금 보유", None if nc is None else nc > 0, "–" if nc is None else f"{nc / 100:,.0f}억")
        if m["debt_eq"] is not None:
            add("lynch", "차입금이 자본보다 적음", m["debt_eq"] < 100, f"{m['debt_eq']}%")
        cat, cat_note = lynch_category(A, ys, rec, cyc_mode) if n >= 3 else ("분류 불가", "실적 이력이 짧아요")
        # 피셔(숫자로 볼 수 있는 항목만)
        up = sum(1 for a, b in zip(ys[-6:], ys[-5:]) if A[b]["rev"] > A[a]["rev"])
        add("fisher", "매출이 꾸준히 늘어남(최근 5년 중 4년 이상 증가)", up >= 4 if n >= 6 else None, f"{up}/{min(5, n - 1)}년 증가", "피셔 1번 질문: 매출 성장 잠재력")
        if len(om) >= 6:
            rcnt, prev = st.mean(om[-3:]) * 100, st.mean(om[:-3]) * 100
            add("fisher", "영업이익률 개선(최근 3년 평균 > 이전 평균)", rcnt > prev, f"{rcnt:.1f}% vs {prev:.1f}%", "피셔 5·6번 질문: 이익률과 개선 노력")
        if len(ys) >= 6 and A[ys[-6]].get("op") and A[ys[-1]].get("op"):
            og = _cagr(A[ys[-6]]["op"], A[ys[-1]]["op"], 5)
            add("fisher", "영업이익이 매출보다 빠르게 늘어남(5년)", None if og is None or rv5 is None else og > rv5,
                "–" if og is None or rv5 is None else f"{og:.1f}% vs {rv5:.1f}%", "규모가 커질수록 남는 게 많아지는 사업인지(영업 레버리지)")
        # 한 줄 해석(숫자 기준 자동 문장)
        pos = (d.get("cycle") or {}).get("position") or (rec.get("cycle") or {}).get("position") or ""
        bok = sum(1 for c in ck["buffett"] if c["ok"]); btot = sum(1 for c in ck["buffett"] if c["ok"] is not None)
        bw = [c["name"] for c in ck["buffett"] if c["ok"] is False]
        bt = f"버핏 관점: 숫자 기준 {bok}/{btot}개 통과. "
        if bok >= btot - 1 and btot:
            bt += "이익이 높고 안정적이며 빚 부담이 적어 '예측 가능한 좋은 사업'에 가까워요."
        elif loss or (cv is not None and cv >= 0.35):
            bt += "이익이 크게 오르내려(" + ("적자 " + "·".join(loss) + "년" if loss else f"변동계수 {cv:.2f}") + ") 버핏이 말한 '10년 뒤 이익을 예측할 수 있는 사업'의 요건은 약해요. 사려면 정상 이익보다 충분히 싸야 해요."
        else:
            bt += "약한 부분: " + ", ".join(bw[:2]) + "."
        if cat == "경기순환주":
            lt = ("린치 관점: 경기순환주예요. 린치는 경기순환주의 PER이 가장 낮을 때가 이익 정점일 수 있다고 경고했어요."
                  + (f" 지금 PER {per:.1f}배가 낮아 보여도 사이클 위치({pos})를 보면 이익이 꺾일 가능성을 먼저 봐야 해요."
                     if per and per < 10 and ("정점" in pos or "상승" in pos) else
                     " 공급 증가(증설·재고)와 가격 둔화 신호를 지켜봐야 해요."))
        elif cat == "고성장주":
            lt = "린치 관점: 고성장주예요. PEG가 1 이하이고 성장이 이어질 여지(새 시장·점유율)가 있는지가 핵심이에요." + (f" 지금 PEG {m['peg']:.2f}." if m["peg"] else "")
        elif cat == "회생주":
            lt = "린치 관점: 회생주예요. 흑자 전환이 일회성인지, 빚을 버틸 현금이 있는지가 핵심이에요."
        elif cat == "자산주":
            lt = "린치 관점: 자산주예요. 숨은 자산(현금·부동산·지분)이 주주에게 돌아올 길(배당·자사주·매각)이 있는지가 핵심이에요."
        elif cat == "저성장주":
            lt = "린치 관점: 저성장주예요. 린치는 이런 회사에서 배당수익률과 싼 가격 외에는 큰 수익을 기대하지 않았어요."
        else:
            lt = "린치 관점: 꾸준히 크는 대형우량주예요. 린치는 이런 회사에서 30~50% 수익을 보고 비싸지면 갈아탔어요."
        rec["checks"] = {**ck, "lynch_cat": cat, "lynch_cat_note": cat_note, "buffett_take": bt, "lynch_take": lt}
