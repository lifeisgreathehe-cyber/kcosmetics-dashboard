"""선행·동행 판정에 쓰는 통계 함수 (표준 라이브러리만 사용).

모든 시계열은 {"YYYY-MM": 값} 사전으로 다룬다.
"""
from __future__ import annotations

import math


def months_between(a: str, b: str) -> int:
    return (int(b[:4]) - int(a[:4])) * 12 + int(b[5:7]) - int(a[5:7])


def shift_month(m: str, k: int) -> str:
    y, mo = int(m[:4]), int(m[5:7]) - 1 + k
    y += mo // 12
    return f"{y:04d}-{mo % 12 + 1:02d}"


def ma(s: dict, n: int) -> dict:
    """n개월 이동평균(연속한 n개월이 모두 있을 때만)."""
    if n <= 1:
        return dict(s)
    out = {}
    for m in s:
        vals = [s.get(shift_month(m, -i)) for i in range(n)]
        if all(v is not None for v in vals):
            out[m] = sum(vals) / n
    return out


def transform(s: dict, tf: str) -> dict:
    """yoy: 전년 같은 달 대비 %, diff12: 12개월 차이, mom3: 3개월 전 대비 %, level: 그대로."""
    out = {}
    for m, v in s.items():
        if v is None:
            continue
        if tf == "level":
            out[m] = v
            continue
        lag = 3 if tf == "mom3" else 12
        p = s.get(shift_month(m, -lag))
        if p is None:
            continue
        if tf == "diff12":
            out[m] = v - p
        elif p > 0 and v > 0:
            out[m] = (v / p - 1) * 100
    return out


def _pairs(x: dict, y: dict, k: int, since: str | None = None):
    xs, ys = [], []
    for m, v in x.items():
        if since and m < since:
            continue
        w = y.get(shift_month(m, k))
        if w is not None:
            xs.append(v)
            ys.append(w)
    return xs, ys


def corr(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((a - mx) ** 2 for a in xs)
    syy = sum((b - my) ** 2 for b in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / math.sqrt(sxx * syy)


def acf(vals, lag):
    n = len(vals)
    if n <= lag + 2:
        return 0.0
    m = sum(vals) / n
    d = sum((v - m) ** 2 for v in vals)
    if d <= 0:
        return 0.0
    return sum((vals[i] - m) * (vals[i + lag] - m) for i in range(n - lag)) / d


def n_eff(xs, ys, J=24):
    """자기상관을 감안한 유효 표본 수 (Bartlett 근사). 전년비처럼 겹치는 구간으로 만든 시계열은
    120개월이라도 실제로 독립적인 관측은 훨씬 적다."""
    n = len(xs)
    s = 1.0
    for j in range(1, min(J, n // 3) + 1):
        s += 2 * acf(xs, j) * acf(ys, j)
    return max(3.0, n / max(s, 1.0))


def lead_lag(x: dict, y: dict, K=12, min_n=36, since=None):
    """r(k) = corr(x_t, y_{t+k}). k>0 이면 x 가 y 보다 k개월 먼저 움직인다(선행)."""
    prof = {}
    for k in range(-K, K + 1):
        xs, ys = _pairs(x, y, k, since)
        if len(xs) >= min_n:
            r = corr(xs, ys)
            if r is not None:
                prof[k] = (r, len(xs))
    return prof


def best_lag(prof: dict, sign: int | None):
    """기대 부호(sign)가 정해진 지표는 그 방향의 가장 강한 상관, 아니면 절댓값 최대.
    같은 크기면 0에 가까운(덜 극단적인) 시차를 고른다. 상관 곡선이 완만한 경우 우연한 먼 시차를
    고르지 않도록 최대값의 97% 이상인 시차 중 0에 가장 가까운 것을 쓴다."""
    if not prof:
        return None
    score = (lambda r: r * sign) if sign else abs
    top = max(score(r) for r, _ in prof.values())
    if top <= 0:
        k = min(prof, key=lambda k: (-abs(prof[k][0]), abs(k)))
        return k
    cands = [k for k, (r, _) in prof.items() if score(r) >= top * 0.97]
    return min(cands, key=lambda k: (abs(k), -k))


def forward_return(idx: dict, m: str, h: int):
    a, b = idx.get(m), idx.get(shift_month(m, h))
    if a and b:
        return (b / a - 1) * 100
    return None


def conditional_returns(x: dict, idx: dict, sign: int, h: int, step=3, since=None):
    """지표(부호 보정)가 최근 step개월 사이 좋아진 달 vs 나빠진 달 이후 h개월 업종 수익률 평균."""
    up, dn = [], []
    for m in sorted(x):
        if since and m < since:
            continue
        p = x.get(shift_month(m, -step))
        if p is None:
            continue
        fr = forward_return(idx, m, h)
        if fr is None:
            continue
        d = (x[m] - p) * (sign or 1)
        (up if d > 0 else dn).append(fr)
    avg = lambda a: round(sum(a) / len(a), 1) if a else None
    hit_up = round(100 * sum(1 for v in up if v > 0) / len(up)) if up else None
    hit_dn = round(100 * sum(1 for v in dn if v < 0) / len(dn)) if dn else None
    return {"h": h, "up_avg": avg(up), "up_n": len(up), "up_hit": hit_up,
            "dn_avg": avg(dn), "dn_n": len(dn), "dn_hit": hit_dn}


def percentile(vals, v):
    if not vals:
        return None
    return round(100 * sum(1 for a in vals if a <= v) / len(vals))
