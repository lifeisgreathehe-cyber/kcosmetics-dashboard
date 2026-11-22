"""신약 파이프라인 위험조정 순현재가치(rNPV) — build_valuation.py가 config의 회사 가정에 "pipeline"이 있으면 부른다.

이익이 없는 신약 개발사는 PER·이익 할인(DCF)로 값을 매길 수 없어요. 대신 후보물질 하나하나를
'성공하면 벌 돈 × 성공 확률 ÷ (1+할인율)^시간'으로 더하고, 회사가 버티는 데 쓰는 고정비를 빼요.

config/<업종>/valuation.json 의 회사 가정:
  "skip": "rNPV",              # 이익 기반 DCF를 건너뛰고 rNPV만 (적자 신약 개발사)
  "pipeline": [                # 후보물질(자산)별 가정. 금액은 모두 억원
    {"name": "ALT-B4(키트루다SC)", "ind": "고형암", "phase": "출시", "pos": 1.0,
     "peak": 60000,            # 최고 매출(전 세계, 파트너 매출 기준이면 share는 로열티율)
     "share": 0.02,            # 회사 몫(로열티율 또는 직접 판매 시 영업이익률)
     "launch": 2025,           # 출시(예정) 연도. 없으면 단계별 기본값
     "life": 10,               # 출시 뒤 최고 매출을 유지하는 기간(특허 만료까지)
     "ramp": 5,                # 최고 매출까지 걸리는 해
     "ms": 3000,               # 남은 마일스톤(성공 시 받을 돈, 억원). 출시 1년 전에 받는다고 봐요
     "note": "근거"}],
  "platform": 2000,            # 아직 특정되지 않은 미래 기술이전(플랫폼) 가치(억원, 근거는 platform_note)
  "burn": 600, "burn_years": 4,# 파이프라인에 배분되지 않은 연간 고정비(억원)와 기간 → 현재가치를 뺌
  "r_rnpv": 11                 # 할인율(%), 없으면 config 머리말 rnpv_r 또는 11%
이익이 있는 회사(E1 있음)는 DCF 적정가에 파이프라인 가치를 '더하는' 방식(add)이에요. 이미 이익에 들어간 출시 품목은 넣지 않아요.
시나리오: 비관 = 성공확률 ×0.6·최고매출 ×0.7·플랫폼 ×0.5, 낙관 = 성공확률 ×1.3(최대 0.95)·최고매출 ×1.3·플랫폼 ×1.5.
"""
import datetime

POS = {"전임상": 0.06, "1상": 0.10, "1/2상": 0.15, "2상": 0.22, "2/3상": 0.40, "3상": 0.55, "허가신청": 0.85, "허가": 0.97, "출시": 1.0}
YEARS_TO_LAUNCH = {"전임상": 7, "1상": 6, "1/2상": 5, "2상": 4.5, "2/3상": 3.5, "3상": 2.5, "허가신청": 1, "허가": 0.5, "출시": 0}
TAX = 0.22
SCEN = {"bear": (0.6, 0.7, 0.5), "base": (1.0, 1.0, 1.0), "bull": (1.3, 1.3, 1.5)}


def asset_value(p, r, pos_k=1.0, peak_k=1.0, year0=None):
    """자산 하나의 rNPV(억원). 매년 현금 = 매출 × 회사 몫 × (1-세율), 출시 전 마일스톤은 성공 확률을 곱해 할인."""
    year0 = year0 or datetime.date.today().year
    ph = p.get("phase", "2상")
    pos0 = p.get("pos", POS.get(ph, 0.2))
    pos = 1.0 if pos0 >= 1 else min(pos0 * pos_k, 0.95)
    launch = p.get("launch") or round(year0 + YEARS_TO_LAUNCH.get(ph, 4))
    ramp, life, peak = max(p.get("ramp", 5), 1), p.get("life", 10), p.get("peak", 0) * peak_k
    share = p.get("share", 0.1)
    v = 0.0
    t0 = max(launch - year0, 0)
    for y in range(0, life + 4):          # 출시 후 life년 + 특허 만료 뒤 3년(매출 30%·15%·5%)
        yr = launch + y
        if yr < year0:
            continue
        if y < ramp:
            s = peak * (y + 1) / ramp
        elif y < life:
            s = peak
        else:
            s = peak * (0.3, 0.15, 0.05, 0)[min(y - life, 3)]
        t = yr - year0 + 0.5
        v += pos * s * share * (1 - TAX) / (1 + r) ** t
    if p.get("ms"):
        t = max(t0 - 1, 0) + 0.5
        v += pos * p["ms"] * (1 - TAX) / (1 + r) ** t
    return v


def value(a, cfg):
    r = (a.get("r_rnpv") or cfg.get("rnpv_r") or 11) / 100
    out = {}
    for k, (pk, sk, fk) in SCEN.items():
        assets = [asset_value(p, r, pk, sk) for p in a["pipeline"]]
        out[k] = {"assets": assets, "platform": (a.get("platform") or 0) * fk}
    by = int(a.get("burn_years", 4))
    burn_pv = sum((a.get("burn") or 0) / (1 + r) ** (t + 0.5) for t in range(by))
    return r, out, burn_pv


def apply(out, cfg):
    """build_valuation.main()의 out에 rNPV를 붙인다. 금액 단위는 valuation.json과 같은 백만원."""
    for code, rec in out["companies"].items():
        a = (cfg.get("companies") or {}).get(code) or {}
        if not a.get("pipeline") and not a.get("platform"):
            continue
        a = dict(a, pipeline=a.get("pipeline") or [])
        r, sc, burn_pv = value(a, cfg)
        shares, mcap = rec.get("shares"), rec.get("mcap_eff") or rec.get("mcap")
        d = rec.get("dcf")
        mode = "add" if d else "pure"
        assets = [dict(name=p.get("name"), ind=p.get("ind", ""), phase=p.get("phase"), pos=p.get("pos", POS.get(p.get("phase"), 0.2)),
                       peak=p.get("peak"), share=p.get("share"), launch=p.get("launch") or round(datetime.date.today().year + YEARS_TO_LAUNCH.get(p.get("phase"), 4)),
                       ms=p.get("ms"), note=p.get("note", ""), value=round(v * 100))
                  for p, v in zip(a["pipeline"], sc["base"]["assets"])]
        nc = rec.get("net_cash") or 0
        if a.get("nc_share") is not None and nc > 0:
            nc = round(nc * a["nc_share"])
        res = {"mode": mode, "r": round(r * 100, 1), "assets": assets, "platform": round((a.get("platform") or 0) * 100),
               "platform_note": a.get("platform_note", ""), "burn": a.get("burn"), "burn_years": a.get("burn_years", 4),
               "burn_pv": round(burn_pv * 100), "note": a.get("rnpv_note") or a.get("note", ""), "scenarios": {}}
        for k, s in sc.items():
            pipe = (sum(s["assets"]) + s["platform"]) * 100  # 백만원
            if mode == "pure":
                v = max(pipe + nc - burn_pv * 100, 0)
            else:
                v = d["scenarios"][k]["value"] + pipe
            row = {"pipeline": round(pipe), "value": round(v)}
            if shares and mcap:
                row.update(per_share=round(v * 1e6 / shares), upside=round((v / mcap - 1) * 100, 1))
            res["scenarios"][k] = row
        if mode == "pure":
            res["net_cash"] = nc
            if mcap:  # 시장이 매긴 파이프라인 가치 = 시가총액 − 순현금 + 고정비 현재가치
                res["implied_pipeline"] = round(mcap - nc + burn_pv * 100)
        else:
            # DCF 적정가에 파이프라인 가치를 더해 시나리오 값을 바꾼다(원래 값은 dcf.scenarios_ex_pipeline에 보관)
            d["scenarios_ex_pipeline"] = {k: dict(v) for k, v in d["scenarios"].items()}
            for k, row in res["scenarios"].items():
                d["scenarios"][k].update({kk: row[kk] for kk in ("value", "per_share", "upside") if kk in row})
            d["pipeline_added"] = res["scenarios"]["base"]["pipeline"]
        rec["rnpv"] = res
