#!/usr/bin/env python3
"""산업동향 지표 × 업종 주가: 선행·동행 판정 → docs/<업종>/data/trends.json (화장품은 docs/data)

모든 업종이 같이 쓰는 공용 모듈. 업종마다 config/trends/<업종>.json 에 '투자 판단에 쓸 지표' 목록만 적으면
- 지표 값 읽기(이미 대시보드가 모으는 KOSIS·관세청 파일, 공용 시장 가격 docs/shared/markets.json,
  추가 KOSIS 지표 docs/shared/trend_kosis.json, 거시 docs/shared/macro.json)
- 업종 주가지수 만들기(대시보드 상장사 월봉 → 시가총액 가중 지수, 중소형 동일가중 지수, 그룹별·대형주별)
- 지표 전년비 vs 주가 전년비의 시차 상관(−12~+12개월), 자기상관 보정 유의성, 지표 개선/악화 뒤 실제 수익률
- 지금 신호(최근 3개월 방향)와 업종 종합 신호
를 한 번에 계산한다. 새 업종은 config/trends/<업종>.json 만 추가하면 된다.

실행: python scripts/trends/build.py --industry all   (네트워크 불필요 — fetch.py 가 받아 둔 파일만 읽음)
"""
from __future__ import annotations

import datetime as dt
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stats as S  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
CFG = ROOT / "config" / "trends"
SHARED = ROOT / "docs" / "shared"
KST = dt.timezone(dt.timedelta(hours=9))
START = "2005-01"          # 화면·계산에 쓰는 가장 이른 달
MIN_N = 36                 # 상관 계산 최소 겹치는 달 수
TF_LABEL = {"yoy": "전년 같은 달 대비 %", "diff12": "1년 전과의 차이", "level": "수준(그대로)", "mom3": "3개월 전 대비 %"}


def data_dir(ind):
    return ROOT / "docs" / "data" if ind == "cosmetics" else ROOT / "docs" / ind / "data"


def jload(p):
    try:
        return json.loads(Path(p).read_text("utf-8"))
    except Exception:  # noqa: BLE001
        return None


# ------------------------------------------------------------------ 지표 읽기
_cache = {}


def _file(ind, name):
    p = ROOT / name if "/" in name else data_dir(ind) / name
    if p not in _cache:
        _cache[p] = jload(p)
    return _cache[p]


def _dig(obj, path):
    for part in path.split("."):
        if obj is None:
            return None
        if isinstance(obj, dict):
            obj = obj.get(part)
        else:
            return None
    return obj


def _monthkey(m):
    m = str(m)
    if len(m) == 6 and m.isdigit():
        return f"{m[:4]}-{m[4:]}"
    return m[:7]


def resolve(ind, src) -> dict:
    """src 사양 → {"YYYY-MM": 값}."""
    if "calc" in src:  # 파생: ratio(a/b), diff(a−b), sum
        a = resolve(ind, src["a"]) if "a" in src else {}
        b = resolve(ind, src["b"]) if "b" in src else {}
        out = {}
        if src["calc"] == "ratio":
            for m in a:
                if b.get(m):
                    out[m] = a[m] / b[m] * src.get("scale", 1)
        elif src["calc"] == "diff":
            for m in a:
                if m in b:
                    out[m] = a[m] - b[m]
        elif src["calc"] == "yoy_gap":  # a 전년비 − b 전년비 (출하−재고 순환 등)
            ya, yb = S.transform(a, "yoy"), S.transform(b, "yoy")
            out = {m: ya[m] - yb[m] for m in ya if m in yb}
        elif src["calc"] == "sum":
            parts = [resolve(ind, x) for x in src["parts"]]
            ms = set.intersection(*(set(p) for p in parts)) if parts else set()
            out = {m: sum(p[m] for p in parts) for m in ms}
        return out
    if "concat" in src:  # 같은 통계의 구·신 표를 이어 붙임(뒤쪽 우선)
        out = {}
        for part in src["concat"]:
            out.update(resolve(ind, part))
        return out
    if "market" in src:
        mk = _file(ind, "docs/shared/markets.json") or {}
        return {m: v for m, v in ((mk.get("series", {}).get(src["market"]) or {}).get("data", {}) or {}).items() if v is not None}
    if "kosis" in src:
        kk = _file(ind, "docs/shared/trend_kosis.json") or {}
        return {m: v for m, v in ((kk.get("series", {}).get(src["kosis"]) or {}).get("data", {}) or {}).items() if v is not None}
    if "macro" in src:
        mc = _file(ind, "docs/shared/macro.json") or {}
        return {m: v for m, v in ((mc.get("series", {}).get(src["macro"]) or {}).get("data", {}) or {}).items() if v is not None}
    obj = _file(src.get("ind", ind), src["file"]) if "ind" not in src else _file(src["ind"], src["file"] if "/" in src["file"] else str(data_dir(src["ind"]).relative_to(ROOT) / src["file"]))
    if obj is None:
        return {}
    if "rows" in src:  # [{m:..., field:...}]
        out = {}
        for r in _dig(obj, src["rows"]) or []:
            v = r.get(src["field"])
            if v is not None:
                out[_monthkey(r[src.get("date", "m")])] = v
        return out
    val = _dig(obj, src["path"]) if src.get("path") else obj
    longd = (_file(ind, "docs/shared/trend_kosis.json") or {}).get("long", {}).get(f"{src.get('ind', ind)}:{src['file']}")
    if longd and src.get("path", "").startswith("series.") or (longd and src.get("path") == "values"):
        key = src["path"][7:] if src["path"].startswith("series.") else "values"
        base = dict(longd.get(key) or {})  # 2005년부터 받은 같은 KOSIS 표(앞부분) + 대시보드 파일(최근, 우선)
        base.update(_plain(obj, val))
        return base
    return _plain(obj, val)


def _plain(obj, val):
    if isinstance(val, dict) and "values" in val:
        months, vals = val.get("months") or [], val["values"]
    elif isinstance(val, dict) and "months" in val and isinstance(val["months"], dict):  # {"months": {m: {"avg":..}}}
        return {m: (x.get("avg") if isinstance(x, dict) else x) for m, x in val["months"].items() if x is not None}
    elif isinstance(val, dict):
        return {_monthkey(m): x for m, x in val.items() if x is not None and str(m)[:4].isdigit()}
    else:
        months, vals = obj.get("months") or [], val or []
    return {_monthkey(m): v for m, v in zip(months, vals) if v is not None}


# ------------------------------------------------------------------ 업종 주가지수
def build_indices(ind, cfg):
    hist = (jload(data_dir(ind) / "stock_hist.json") or {}).get("series", {})
    long = (jload(ROOT / "raw" / "trends" / f"stock_long_{ind}.json") or {}).get("series", {})
    for code, lh in long.items():  # 네이버 월봉은 최근 10년뿐 → 더 긴 이력(fetch.py --only stocks)이 있으면 앞쪽을 이어 붙임
        h = hist.get(code)
        d = dict(zip(lh.get("months", []), lh.get("close", [])))
        if h:
            first = h["months"][0]
            # 두 소스의 수정주가 기준이 다를 수 있어 겹치는 첫 달 비율로 맞춘다
            ratios = [c / d[m] for m, c in zip(h["months"], h["close"]) if d.get(m) and c]
            consistent = len(ratios) >= 6 and max(ratios) / min(ratios) < 1.15  # 액면분할 미반영 등 기준이 다르면 버림
            if first in d and d[first] and consistent:
                f = h["close"][0] / d[first]
                d = {m: c * f for m, c in d.items() if m < first and c}
                d.update(dict(zip(h["months"], h["close"])))
            else:
                d = dict(zip(h["months"], h["close"]))
        ms = sorted(d)
        hist[code] = {"name": lh.get("name"), "months": ms, "close": [d[m] for m in ms]}
    val = (jload(data_dir(ind) / "valuation.json") or {}).get("companies", {})
    comps = (jload(data_dir(ind) / "companies.json") or {}).get("companies", [])
    group_of = {c["code"]: c.get("group", "") for c in comps}
    name_of = {c["code"]: c.get("name", c["code"]) for c in comps}
    exclude = set(cfg.get("index_exclude", []))
    px = {}
    for code, h in hist.items():
        if code in exclude or not h.get("months"):
            continue
        s = {m: c for m, c in zip(h["months"], h["close"]) if c}
        if len(s) >= 6:
            px[code] = s
    mcap = {}
    for code, s in px.items():
        v = val.get(code) or {}
        mc = v.get("mcap_eff") or v.get("mcap")
        last = s[max(s)]
        if mc and last:
            mcap[code] = (mc, last)
    months = sorted({m for s in px.values() for m in s})

    def index(codes, weighted=True):
        lvl, out = 100.0, {}
        started = False
        for i, m in enumerate(months):
            if i == 0:
                continue
            p = months[i - 1]
            num = den = 0.0
            for c in codes:
                s = px.get(c)
                if not s or p not in s or m not in s:
                    continue
                r = s[m] / s[p] - 1
                if abs(r) > 2.0:  # 액면·병합 등 이상치
                    continue
                if weighted:
                    if c not in mcap:
                        continue
                    mc, last = mcap[c]
                    w = mc * s[p] / last  # 현재 주식 수 기준 그 달 시가총액
                else:
                    w = 1.0
                num += w * r
                den += w
            if den <= 0:
                if started:
                    out[m] = lvl
                continue
            if not started:
                out[p] = 100.0
                started = True
            lvl *= 1 + num / den
            out[m] = round(lvl, 3)
        return out

    codes = list(px)
    by_cap = sorted([c for c in codes if c in mcap], key=lambda c: -mcap[c][0])
    targets = []
    cap = index(codes, True)
    targets.append({"id": "cap", "name": cfg.get("index_name", "업종 시총가중"), "kind": "industry", "idx": cap})
    small = [c for c in codes if c not in by_cap[:3]]
    if len(small) >= 5:
        targets.append({"id": "eq", "name": "중소형 동일가중(시총 상위 3개 제외)", "kind": "industry", "idx": index(small, False)})
    groups = {}
    for c in codes:
        groups.setdefault(group_of.get(c, ""), []).append(c)
    for g, cs in groups.items():
        if g and len(cs) >= 2 and len(groups) > 1:
            targets.append({"id": "g:" + g, "name": g, "kind": "group", "idx": index(cs, True), "n": len(cs)})
    for c in cfg.get("key_companies") or by_cap[:3]:
        if c in px:
            targets.append({"id": c, "name": name_of.get(c, c), "kind": "company", "idx": dict(px[c])})
    total_mcap = sum(v[0] for v in mcap.values())
    top_share = [(name_of.get(c, c), round(100 * mcap[c][0] / total_mcap, 1)) for c in by_cap[:5]] if total_mcap else []
    return targets, top_share, len(codes)


# ------------------------------------------------------------------ 판정
def classify(k, r, sig, pub_lag):
    if k is None or r is None:
        return "na", "자료 부족"
    if not sig or abs(r) < 0.3:
        return "weak", "관계 약함"
    if abs(k) >= 12:  # 상관이 시차 끝(±12개월)에서 가장 크면 추세가 겹친 것일 가능성이 커 판정을 보류
        return "weak", "관계 약함(시차 1년 이상)"
    if k >= 2:
        eff = k - pub_lag
        if eff >= 1:
            return "lead", f"선행 {k}개월"
        return "lead0", f"선행 {k}개월(발표 시차 감안 시 동행)"
    if k <= -2:
        return "lag", f"후행 {-k}개월"
    return "coin", "동행"


def fmt(v, d=1):
    return None if v is None else round(v, d)


def describe(sr, rel, tgt_name):
    k, r, cls = rel.get("k"), rel.get("r"), rel.get("cls")
    sign_word = "같은 방향" if (r or 0) >= 0 else "반대 방향"
    pub = sr.get("pub_lag", 1)
    c = rel.get("cond") or {}
    if cls == "na":
        return f"겹치는 기간이 {MIN_N}개월이 안 돼 아직 판정하지 않았어요. 자료가 쌓이면 자동으로 계산돼요."
    if cls == "weak":
        return (f"{tgt_name} 주가와 뚜렷한 시차 관계가 없어요(가장 강한 상관 {r:+.2f}, {k:+d}개월). "
                "주가 타이밍보다 업황 이해·이익 추정용으로 보세요.")
    base = f"지표와 {tgt_name} 주가는 {sign_word}로 움직였어요(상관 {r:+.2f})."
    if cls in ("lead", "lead0"):
        t = f"{base} 지표가 평균 {k}개월 먼저 움직였고, 발표가 약 {pub}개월 늦게 나오므로 실제로 쓸 수 있는 앞섬은 약 {max(k - pub, 0)}개월이에요."
    elif cls == "coin":
        t = f"{base} 주가와 거의 같은 달에 움직여요 — 지금 주가 흐름이 업황으로 뒷받침되는지 확인하는 지표예요."
    else:
        t = (f"{base} 주가가 약 {-k}개월 먼저 움직이고 지표가 뒤따랐어요 — 주가가 이미 반영한 뒤 확인되는 숫자라, "
             "지표가 좋아진 걸 보고 사면 늦을 수 있어요. 반대로 지표가 나쁜데 주가가 버티면 바닥 신호일 수 있어요.")
    if c.get("up_avg") is not None and c.get("dn_avg") is not None and cls in ("lead", "lead0", "coin"):
        t += (f" 과거에 지표가 3개월 사이 좋아진(주가에 유리한 쪽으로 움직인) 뒤 {c['h']}개월 업종 수익률은 평균 {c['up_avg']:+.1f}%"
              f"(상승 확률 {c['up_hit']}%), 나빠진 뒤는 {c['dn_avg']:+.1f}%였어요.")
    if (rel.get("n") or 0) < 60:
        t += f" 겹치는 기간이 {rel.get('n')}개월로 짧아 참고용으로만 보세요."
    if rel.get("recent_r") is not None and r is not None and abs(r) >= 0.3:
        rr = rel["recent_r"]
        if rr * r < 0 or abs(rr) < 0.2:
            t += f" 다만 최근 5년만 보면 상관이 {rr:+.2f}로 약해져 관계가 흔들리고 있어요."
        elif abs(rr) > abs(r) + 0.1:
            t += f" 최근 5년엔 상관이 {rr:+.2f}로 더 강해졌어요."
    return t


def run(ind):
    p = CFG / f"{ind}.json"
    cfg = jload(p)
    if not cfg:
        print(f"[trends] {ind}: config/trends/{ind}.json 없음 — 건너뜀")
        return False
    if not (data_dir(ind) / "stock_hist.json").exists():
        print(f"[trends] {ind}: stock_hist.json 없음 — 건너뜀")
        return False
    common = jload(CFG / "_common.json") or {"series": []}
    skip = set(cfg.get("skip_common", []))
    specs = list(cfg["series"]) + [s for s in common["series"] if s["id"] not in skip]
    targets, top_share, n_cos = build_indices(ind, cfg)
    main = targets[0]
    idx_yoy = {t["id"]: S.transform(t["idx"], "yoy") for t in targets}
    ex = cfg.get("exclude_window")  # 예: 코로나처럼 전년비가 극단적으로 왜곡된 기간은 통계에서 뺌(그래프엔 그대로 표시)
    inwin = (lambda m: ex[0] <= m <= ex[1]) if ex else (lambda m: False)
    idx_yoy_stat = {k: {m: v for m, v in d.items() if not inwin(m)} for k, d in idx_yoy.items()}
    last_m = max(main["idx"]) if main["idx"] else None
    recent_since = S.shift_month(last_m, -72) if last_m else None  # 최근 5년(+전년비 계산분)
    out_series = []
    for sp in specs:
        raw = {m: v for m, v in resolve(ind, sp["src"]).items() if m >= START and isinstance(v, (int, float))}
        if not raw:
            print(f"[trends] {ind}: {sp['id']} 데이터 없음")
            out_series.append({**{k: sp.get(k) for k in ("id", "name", "group", "unit", "source", "url", "why", "read")},
                               "missing": True, "note": sp.get("missing_note", "아직 수집 전이에요(다음 자동 갱신 때 채워져요).")})
            continue
        tf = sp.get("tf", "yoy")
        x = S.transform(S.ma(raw, sp.get("ma", 1)), tf)
        sign = sp.get("sign")
        sx = sp.get("exclude_window")
        xs_stat = {m: v for m, v in x.items() if not inwin(m) and not (sx and sx[0] <= m <= sx[1])}
        rel = {}
        tg_rows = []
        for t in targets:
            prof = S.lead_lag(xs_stat, idx_yoy_stat[t["id"]], 12, MIN_N)
            if not prof:
                continue
            k = S.best_lag(prof, sign)
            r, n = prof[k]
            xs, ys = S._pairs(xs_stat, idx_yoy_stat[t["id"]], k)
            ne = S.n_eff(xs, ys)
            thr = 1.96 / math.sqrt(max(ne - 2, 1))
            sig = abs(r) >= max(thr, 0.3)
            row = {"id": t["id"], "name": t["name"], "kind": t["kind"], "k": k, "r": fmt(r, 2), "n": n, "sig": sig}
            if t is main:
                cls, label = classify(k, r, sig, sp.get("pub_lag", 1))
                rp = S.lead_lag(xs_stat, idx_yoy_stat[t["id"]], 12, 24, since=recent_since)
                h = min(max(k, 3), 12) if k and k > 0 else 3
                rel = {"k": k, "r": fmt(r, 2), "r0": fmt(prof.get(0, (None,))[0], 2), "n": n, "neff": round(ne, 1),
                       "thr": fmt(thr, 2), "sig": sig, "cls": cls, "label": label,
                       "eff_lead": (k - sp.get("pub_lag", 1)) if k is not None else None,
                       "recent_r": fmt(rp.get(k, (None,))[0], 2) if rp else None,
                       "prof": [[kk, round(prof[kk][0], 3)] for kk in sorted(prof)],
                       "cond": S.conditional_returns(xs_stat, t["idx"], sign or (1 if r >= 0 else -1), h)}
            tg_rows.append(row)
        if not rel:
            rel = {"cls": "na", "label": "자료 부족", "n": len(x)}
        eff_sign = sign or (1 if (rel.get("r") or 0) >= 0 else -1)
        # 지금 신호: 변환값이 3개월 전보다 좋아졌나(부호 보정)
        xm = sorted(x)
        now = {}
        if xm:
            lm = xm[-1]
            prev = x.get(S.shift_month(lm, -3))
            vals = list(x.values())
            sd = (sum((v - sum(vals) / len(vals)) ** 2 for v in vals) / max(len(vals) - 1, 1)) ** 0.5 if len(vals) > 2 else 0
            d = (x[lm] - prev) if prev is not None else None
            state = None
            if d is not None:
                state = "flat" if sd and abs(d) < 0.15 * sd else ("up" if d * eff_sign > 0 else "down")
            now = {"m": lm, "v": fmt(raw.get(lm)), "tf": fmt(x[lm]), "d3": fmt(d), "state": state,
                   "pct": S.percentile(vals, x[lm]), "raw_m": max(raw)}
        others = sorted([r for r in tg_rows if r["id"] != main["id"] and r["sig"]], key=lambda r: -abs(r["r"] or 0))[:4]
        months = sorted(raw)
        rec = {k: sp.get(k) for k in ("id", "name", "group", "unit", "source", "url", "why", "read", "sign", "pub_lag", "ma")}
        rec.update({"tf": tf, "tf_label": TF_LABEL.get(tf, tf), "months": months, "raw": [fmt(raw[m], 3) for m in months],
                    "x": [fmt(x.get(m), 2) for m in months], "rel": rel, "now": now, "targets": tg_rows, "best_others": others})
        rec["text"] = describe(sp, rel, main["name"])
        out_series.append(rec)
    # 종합 신호
    def tally(classes):
        up = [s["name"] for s in out_series if s.get("rel", {}).get("cls") in classes and s.get("now", {}).get("state") == "up"]
        dn = [s["name"] for s in out_series if s.get("rel", {}).get("cls") in classes and s.get("now", {}).get("state") == "down"]
        fl = [s["name"] for s in out_series if s.get("rel", {}).get("cls") in classes and s.get("now", {}).get("state") == "flat"]
        return {"up": up, "down": dn, "flat": fl}
    lead = tally(("lead", "lead0"))
    coin = tally(("coin",))
    nl = len(lead["up"]) + len(lead["down"]) + len(lead["flat"])
    if nl:
        share = len(lead["up"]) / nl
        tone = "우호적" if share >= 0.6 else ("부정적" if len(lead["down"]) / nl >= 0.6 else "엇갈림")
        verdict = {"우호적": f"주가보다 먼저 움직였던 지표 {nl}개 중 {len(lead['up'])}개가 최근 3개월 사이 좋아지고 있어요 — 앞으로 몇 달 업종 주가에 우호적인 신호가 우세해요.",
                   "부정적": f"주가보다 먼저 움직였던 지표 {nl}개 중 {len(lead['down'])}개가 최근 3개월 사이 나빠지고 있어요 — 업종 주가에 부담이 될 수 있는 신호가 우세해요.",
                   "엇갈림": f"주가보다 먼저 움직였던 지표 {nl}개의 방향이 엇갈려요(좋아짐 {len(lead['up'])} · 나빠짐 {len(lead['down'])} · 보합 {len(lead['flat'])}) — 방향을 단정하기 이른 구간이에요."}[tone]
    else:
        tone, verdict = "없음", "통계적으로 뚜렷한 선행 지표가 아직 없어요. 동행 지표로 현재 업황을 확인하세요."
    idx_months = sorted(main["idx"])
    kospi = resolve(ind, {"market": "yahoo:^KS11"}) or resolve(ind, {"macro": "KOSPI"})
    out = {
        "updated": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
        "industry": ind, "title": cfg.get("title", ""), "intro": cfg.get("intro", ""),
        "index": {"name": main["name"], "n_companies": n_cos, "top_share": top_share, "months": idx_months,
                  "cap": [main["idx"][m] for m in idx_months],
                  "eq": [next((t["idx"].get(m) for t in targets if t["id"] == "eq"), None) for m in idx_months],
                  "kospi": [kospi.get(m) for m in idx_months],
                  "yoy": [fmt(idx_yoy["cap"].get(m)) for m in idx_months]},
        "targets": [{"id": t["id"], "name": t["name"], "kind": t["kind"]} for t in targets],
        "summary": {"tone": tone, "verdict": verdict, "lead": lead, "coin": coin},
        "exclude_window": ex,
        "groups": cfg.get("groups") or ["수요·물량", "가격·마진", "공급·재고", "원가", "거시·금융"],
        "series": out_series,
    }
    dst = data_dir(ind) / "trends.json"
    dst.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), "utf-8")
    ok = sum(1 for s in out_series if not s.get("missing"))
    print(f"[trends] {ind}: 지표 {ok}/{len(out_series)}개, 선행 {nl}개 → {dst.relative_to(ROOT)} ({dst.stat().st_size // 1024}KB)")
    return True


def main():
    ind = sys.argv[sys.argv.index("--industry") + 1] if "--industry" in sys.argv else "all"
    inds = [p.stem for p in sorted(CFG.glob("*.json")) if not p.stem.startswith("_") and p.stem != "kosis"] if ind == "all" else [ind]
    for i in inds:
        try:
            run(i)
        except Exception as e:  # noqa: BLE001 — 한 업종 오류가 다른 업종을 막지 않게
            import traceback
            traceback.print_exc()
            print(f"[trends] {i}: 실패 {e}")


if __name__ == "__main__":
    main()
