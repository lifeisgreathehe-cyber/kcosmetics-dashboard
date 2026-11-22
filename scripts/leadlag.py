"""산업 데이터 ↔ 주가 선행·동행성 분석 (모든 업종 공용, 2026-11-22)

사용: python scripts/leadlag.py --industry ship   (all = config/*/leadlag.json 이 있는 모든 업종)
입력: config/<업종>/leadlag.json
  {
   "max_lag": 12,                       # 최대 시차(개월)
   "targets": {"groups": true,           # companies.json 그룹별 지수도 계산
               "companies": ["329180"]}, # 개별 기업 주가도 비교(선택)
   "series": [
     {"id": "ship_exp", "name": "선박 수출액", "file": "customs_exports.json", "path": "series.선박",
      "transform": "yoy", "unit": "백만 달러", "why": "왜 주가에 중요한가(한두 문장)", "expect": "+"},
     {"id": "rate", "name": "국고채 3년", "file": "indicators.json", "find": "rate3y", "transform": "diff12"},
     {"id": "x", "name": "...", "file": "../chem/data/crude_price.json", "path": "series.달러기준"}
   ]
  }
  - file: docs/<업종>/data 기준 경로. path(점으로 구분)는 그 파일의 months 와 같은 길이의 배열이거나 [["YYYY-MM", 값], ...] 목록.
    find: 파일이 [{id, series:[[YYYY-MM, 값]]}] 목록(또는 {"indicators": [...]})일 때 id로 찾는다.
  - transform: yoy(전년 같은 달 대비 %, 기본) · diff12(1년 전 대비 차이, 금리·비율용) · level(수준 그대로)
  - roll: n → 최근 n개월 합계(roll_how "mean"이면 평균)로 바꾼 뒤 transform (수주처럼 달마다 들쭉날쭉한 지표)
  - expect: "+"(지표가 오르면 주가에 좋음) / "-"(나쁨). 실제 상관 부호와 다르면 화면에 표시한다.
출력: docs/<업종>/data/leadlag.json — 화면은 docs/shared/leadlag.js 의 LeadLag.render(el, data)
주가: docs/<업종>/data/stock_hist.json(네이버 월봉 수정주가) 구성 종목의 월 수익률을 동일가중으로 이어 붙인 업종 지수.

방법: 지표 변화율 x(t)와 주가지수 1년 수익률 p(t+k)의 상관을 k=-max..+max 에서 계산해 |r|이 가장 큰 k를 고른다.
  k ≥ 2 → 지표가 k개월 '선행', |k| ≤ 1 → '동행', k ≤ -2 → 주가가 먼저 움직이는 '후행'.
  12개월 변화율끼리는 자기상관이 커서 그냥 n으로 유의성을 보면 과대평가된다 → Bartlett 유효 표본 수
  n_eff = n·(1-ρx·ρp)/(1+ρx·ρp) (ρ = 1개월 자기상관)로 |r| ≥ 2/√n_eff 를 '통계적으로 의미 있음'으로 본다.
  전·후반기 안정성: 같은 시차에서 표본 앞 절반과 뒤 절반의 r 부호가 같으면 '안정'.
"""
import datetime, glob, json, math, os, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def mshift(m, k):
    y, mo = int(m[:4]), int(m[5:7]) - 1 + k
    return f"{y + mo // 12:04d}-{mo % 12 + 1:02d}"


def load_series(data_dir, spec):
    p = os.path.normpath(os.path.join(data_dir, spec["file"]))
    if not os.path.exists(p):
        return {}
    d = json.load(open(p, encoding="utf-8"))
    if spec.get("find"):
        lst = d.get("indicators") if isinstance(d, dict) else d
        obj = next((o for o in (lst or []) if o.get("id") == spec["find"]), None)
        if not obj:
            return {}
        arr, months = obj.get(spec.get("path") or "series"), obj.get("months")
    else:
        arr, months = d, d.get("months")
        for k in (spec.get("path") or "").split("."):
            if k:
                arr = arr.get(k) if isinstance(arr, dict) else None
            if arr is None:
                return {}
        if isinstance(arr, dict) and "months" in arr:
            months, arr = arr["months"], arr.get("values") or arr.get("series")
    out = {}
    if arr and isinstance(arr[0], (list, tuple)):
        for m, v in arr:
            if v is not None:
                out[str(m)[:7]] = float(v)
    elif months:
        for m, v in zip(months, arr or []):
            if v is not None:
                out[str(m)[:7]] = float(v)
    return out


def rolling(s, n, how="sum"):
    o = {}
    for m in s:
        vs = [s.get(mshift(m, -i)) for i in range(n)]
        if all(v is not None for v in vs):
            o[m] = sum(vs) / (n if how == "mean" else 1)
    return o


def transform(s, how):
    if how == "level":
        return dict(s)
    o = {}
    for m, v in s.items():
        b = s.get(mshift(m, -12))
        if b is None:
            continue
        if how == "diff12":
            o[m] = v - b
        elif b > 0 and v > 0:
            o[m] = (v / b - 1) * 100
    return o


def corr(a, b):
    n = len(a)
    if n < 12:
        return None
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    if va <= 0 or vb <= 0:
        return None
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(va * vb)


def ac1(d):
    ks = sorted(d)
    a = [d[k] for k in ks[:-1] if mshift(k, 1) in d]
    b = [d[mshift(k, 1)] for k in ks[:-1] if mshift(k, 1) in d]
    r = corr(a, b)
    return r if r is not None else 0.0


def lagcorr(x, p, k):
    """corr(x(t), p(t+k)): k>0 이면 지표가 k개월 앞선다."""
    ms = sorted(m for m in x if mshift(m, k) in p)
    return [x[m] for m in ms], [p[mshift(m, k)] for m in ms], ms


def index_from(hist, codes):
    """동일가중 월 수익률을 이어 붙인 지수(첫 달 100)."""
    rets = {}
    for c in codes:
        s = hist.get(c)
        if not s:
            continue
        px = dict(zip(s["months"], s.get("close") or s.get("prices") or s.get("values") or []))
        for m, v in px.items():
            pv = px.get(mshift(m, -1))
            if v and pv:
                r = v / pv - 1
                if abs(r) < 1.5:  # 액면분할 등 이상치 제외
                    rets.setdefault(m, []).append(r)
    need = 3 if len(codes) >= 3 else 1
    ms = sorted(m for m, v in rets.items() if len(v) >= need)
    if not ms:
        return {}
    lvl, out = 100.0, {mshift(ms[0], -1): 100.0}
    for m in ms:
        lvl *= 1 + sum(rets[m]) / len(rets[m])
        out[m] = round(lvl, 3)
    return out


def analyse(x, p, max_lag):
    best = None
    rows = []
    for k in range(-max_lag, max_lag + 1):
        a, b, ms = lagcorr(x, p, k)
        r = corr(a, b)
        rows.append([k, None if r is None else round(r, 3)])
        if r is not None and (best is None or abs(r) > abs(best[1]) + 1e-9):
            best = (k, r, len(a), ms)
    if not best:
        return None
    k, r, n, ms = best
    r0 = next((v for kk, v in rows if kk == 0), None)
    rx, rp = ac1(x), ac1(p)
    q = max(min(rx * rp, 0.98), -0.5)
    n_eff = max(3.0, n * (1 - q) / (1 + q))
    thr = 2 / math.sqrt(n_eff)
    h = len(ms) // 2
    r1 = corr([x[m] for m in ms[:h]], [p[mshift(m, k)] for m in ms[:h]])
    r2 = corr([x[m] for m in ms[h:]], [p[mshift(m, k)] for m in ms[h:]])
    stable = r1 is not None and r2 is not None and (r1 > 0) == (r2 > 0) == (r > 0)
    if abs(r) < 0.2 or abs(r) < thr * 0.75:
        kind = "관계 약함"
    elif k >= 2:
        kind = f"{k}개월 선행"
    elif k <= -2:
        kind = f"{-k}개월 후행"
    else:
        kind = "동행"
    grade = "높음" if abs(r) >= thr and stable else "보통" if abs(r) >= thr * 0.75 else "낮음"
    return {"lag": k, "r": round(r, 3), "r0": r0, "n": n, "n_eff": round(n_eff, 1), "thr": round(thr, 3),
            "kind": kind, "grade": grade, "stable": stable,
            "halves": [None if r1 is None else round(r1, 3), None if r2 is None else round(r2, 3)],
            "period": [ms[0], ms[-1]], "curve": rows}


def signal(x, lag, r, expect):
    """지금 지표가 무엇을 말하나: 최근 값, 3개월 방향, 시차 반영 시 주가에 주는 신호."""
    ks = sorted(x)
    if not ks:
        return None
    last = ks[-1]
    v = x[last]
    prev = x.get(mshift(last, -3))
    trend = None if prev is None else ("상승" if v > prev else "하락" if v < prev else "보합")
    sgn = 1 if (r or 0) >= 0 else -1
    tone = "neu"
    if trend in ("상승", "하락"):
        good = (trend == "상승") == (sgn > 0)
        tone = "pos" if good else "neg"
    return {"month": last, "value": round(v, 2), "prev3": None if prev is None else round(prev, 2),
            "trend": trend, "tone": tone, "until": mshift(last, lag) if lag > 0 else None,
            "mismatch": bool(expect) and ((expect == "+") != (sgn > 0))}


KIND_TXT = {
    "선행": "지표가 주가보다 먼저 움직였어요. 지금 지표 방향이 앞으로 몇 달 주가 방향의 힌트가 돼요.",
    "동행": "지표와 주가가 거의 같은 달에 움직였어요. 주가 흐름을 확인하는 용도로 써요.",
    "후행": "주가가 지표보다 먼저 움직였어요. 시장이 이 숫자를 미리 반영하므로 발표 뒤 매매 신호로는 늦어요.",
    "관계 약함": "과거 10년 동안 주가와 뚜렷한 시차 관계가 없었어요. 업황 설명용으로만 보세요.",
}


def run(ind):
    cfgp = os.path.join(ROOT, "config", ind, "leadlag.json")
    if not os.path.exists(cfgp):
        print(f"[leadlag] {ind}: config 없음 — 건너뜀")
        return
    cfg = json.load(open(cfgp, encoding="utf-8"))
    data_dir = os.path.join(ROOT, "docs", ind, "data") if ind != "cosmetics" else os.path.join(ROOT, "docs", "data")
    hp = os.path.join(data_dir, "stock_hist.json")
    hist = json.load(open(hp, encoding="utf-8")).get("series", {}) if os.path.exists(hp) else {}
    cos = json.load(open(os.path.join(data_dir, "companies.json"), encoding="utf-8")).get("companies", [])
    tcfg = cfg.get("targets", {})
    excl = set(tcfg.get("exclude", []))
    members = [c["code"] for c in cos if c["code"] not in excl]
    targets = {"업종 지수": index_from(hist, members)}
    if tcfg.get("groups", True):
        for g in dict.fromkeys(c.get("group") for c in cos):
            codes = [c["code"] for c in cos if c.get("group") == g and c["code"] not in excl]
            idx = index_from(hist, codes)
            if len(idx) >= 36:
                targets[f"{g} 지수"] = idx
    names = {c["code"]: c["name"] for c in cos}
    for code in tcfg.get("companies", []):
        idx = index_from(hist, [code])
        if len(idx) >= 36:
            targets[names.get(code, code)] = idx
    tyoy = {k: transform(v, "yoy") for k, v in targets.items() if v}
    ml = int(cfg.get("max_lag", 12))
    res = []
    for sp in cfg.get("series", []):
        raw = load_series(data_dir, sp)
        if sp.get("roll"):  # 들쭉날쭉한 월별 값(수주·선박 수출)은 최근 n개월 합계(roll_how=mean이면 평균)로 바꾼 뒤 변화율을 잰다
            raw = rolling(raw, int(sp["roll"]), sp.get("roll_how", "sum"))
        x = transform(raw, sp.get("transform", "yoy"))
        item = {k: sp.get(k) for k in ("id", "name", "unit", "why", "expect", "group", "src", "roll")}
        item["transform"] = sp.get("transform", "yoy")
        item["n_raw"] = len(raw)
        if len(x) < 24:
            item["status"] = "데이터 부족(수집 대기)"
            res.append(item)
            continue
        T = {}
        for tn, p in tyoy.items():
            a = analyse(x, p, ml)
            if a:
                T[tn] = a
        item["targets"] = T
        main = T.get("업종 지수")
        if main:
            base = main["kind"].split(" ")[-1] if main["kind"] != "관계 약함" else "관계 약함"
            item["read"] = KIND_TXT.get(base, "")
            item["signal"] = signal(x, main["lag"], main["r"], sp.get("expect"))
        ks = sorted(x)[-60:]
        item["x"] = [[k, round(x[k], 2)] for k in ks]
        res.append(item)
    # 요약: 업종 지수 기준 신뢰 높음/보통인 선행 지표의 현재 신호를 모은다
    lead = [r for r in res if r.get("targets", {}).get("업종 지수", {}).get("kind", "").endswith("선행")
            and r["targets"]["업종 지수"]["grade"] in ("높음", "보통")]
    pos = sum(1 for r in lead if (r.get("signal") or {}).get("tone") == "pos")
    neg = sum(1 for r in lead if (r.get("signal") or {}).get("tone") == "neg")
    pidx = {k: [[m, v] for m, v in sorted(t.items())][-121:] for k, t in tyoy.items()}
    out = {"updated": datetime.date.today().isoformat(), "industry": ind, "max_lag": ml,
           "summary": {"leading": len(lead), "pos": pos, "neg": neg},
           "method": ("주가는 이 업종 구성 종목의 월말 수정주가로 만든 동일가중 지수(그룹별 지수·대표 기업 포함)의 1년 수익률이에요. "
                      "지표는 전년 같은 달 대비 변화율(금리·비율은 1년 전 대비 차이)로 바꾼 뒤, 지표를 0~" + str(ml) + "개월 앞당기거나 늦춰 가며 "
                      "주가 1년 수익률과의 상관계수를 계산해 가장 강한 시차를 골랐어요. 2개월 이상 앞서면 '선행', 1개월 이내면 '동행', "
                      "주가가 2개월 이상 먼저 움직이면 '후행'이에요. 12개월 변화율은 서로 겹쳐 있어 우연히 높은 상관이 나오기 쉬워서, "
                      "자기상관을 반영한 유효 표본 수로 기준선(2/√유효표본)을 정하고, 표본 앞·뒤 절반에서 같은 부호가 나와야 신뢰 '높음'으로 표시했어요. "
                      "상관은 인과가 아니고, 과거 관계가 앞으로도 유지된다는 보장은 없어요."),
           "price": pidx, "series": res}
    op = os.path.join(data_dir, "leadlag.json")
    json.dump(out, open(op, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[leadlag] {ind}: 지표 {len(res)}개, 대상 {len(tyoy)}개 → {op}")


if __name__ == "__main__":
    ind = sys.argv[sys.argv.index("--industry") + 1] if "--industry" in sys.argv else "all"
    inds = [os.path.basename(os.path.dirname(p)) for p in sorted(glob.glob(os.path.join(ROOT, "config", "*", "leadlag.json")))] if ind == "all" else [ind]
    for i in inds:
        try:
            run(i)
        except Exception as e:  # 한 업종 실패가 다른 업종을 막지 않게
            print(f"[leadlag] {i} 실패: {e}")
