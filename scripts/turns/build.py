#!/usr/bin/env python3
"""주가 변곡점 해설 — 모든 산업 대시보드의 '실적·주가 비교 차트'에 나오는 변곡점마다 왜 오르고 내렸는지 설명을 만든다.

변곡점 두 종류
  ① 엇갈린 구간(차트의 초록·빨강 띠): 직전 1년 이익(4분기 합)과 주가가 반대로 움직인 분기. docs/shared/finchart.js 와 같은 규칙.
  ② 큰 흐름의 고점·저점: 월말 종가가 고점(저점)에서 30% 넘게 되돌린 지점(지그재그). 그 지점부터 다음 변곡점까지를 한 구간으로 설명.

구간마다 아래 근거를 숫자로 모아 문장으로 만든다(손으로 쓴 해설이 아니라 데이터에서 자동 생성 → 새 변곡점도 매일 자동 해설).
  · 주가 = 이익 × PER 로 나눠 보기: 이익이 움직였는지, 시장이 매기는 배수(PER)가 움직였는지
  · 밸류에이션 위치: 구간 시작 PER이 이 회사 자기 역사에서 상위 몇 %였는지(비쌌는지·쌌는지)
  · 시장·업종·회사 고유 몫: 같은 기간 코스피(코스닥)·같은 대시보드 업종·같은 사업군 중앙값과 비교
  · 실적 발표 반응: 구간 안 분기 실적(영업이익 전년 대비)과 발표 달의 업종 대비 주가 반응(서프라이즈·쇼크의 대리 지표)
  · 사후 확인: 구간이 끝난 뒤 1년 이익이 실제로 어떻게 됐는지(시장이 미리 반영한 것인지, 과민 반응이었는지)
  · 거시: 원/달러, 한·미 금리, 유가 변화(docs/shared/macro.json, Actions가 FRED·네이버에서 수집)
  · 사건 연표: scripts/turns/events.py (시장·산업·회사별 주요 사건, 날짜·숫자 포함, 손으로 작성)
  · 뉴스: 네이버 종목뉴스 누적본(data/news_hist.json) + reviews.json 뉴스 해석
설명되지 않는 몫이 크면 '원인 불확실'이라고 적는다.

사용: python scripts/turns/build.py            (모든 산업)
      python scripts/turns/build.py semi chem  (일부)
출력: docs/<업종>/data/turns/<종목코드>.json {"updated", "events": [...]} + docs/<업종>/data/turns.json(설명·회사별 개수)
"""
from __future__ import annotations

import datetime as dt
import json
import math
import re
import statistics as stx
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from events import EVENTS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
KST = dt.timezone(dt.timedelta(hours=9))
TH_E, TH_P = 0.05, 0.10   # finchart.js 와 같은 문턱
ZZ = 0.30                  # 고점·저점 판정: 30% 넘게 되돌리면 변곡점
IND_NAME = {"cosmetics": "화장품", "semi": "반도체", "chem": "화학·정유", "battery": "2차전지", "apparel": "의류",
            "food": "음식료", "logistics": "물류·운송", "travel": "여행"}
# 업종별 환율·유가 민감도(문장용): +1 원화 약세가 이익에 유리, -1 불리, 0 혼재
FX_SENS = {"cosmetics": 1, "semi": 1, "chem": 0, "battery": 1, "apparel": 1, "food": -1, "logistics": 0, "travel": 0}
OIL_SENS = {"chem": "정유는 재고평가이익·정제마진, 석유화학은 원가 부담", "logistics": "항공·해운 연료비 부담", "travel": "항공사 연료비·유류할증료(여행 수요 위축)",
            "food": "포장재·물류비 부담", "apparel": "합성섬유 원가"}


def industries(sel=None):
    out = []
    if (ROOT / "docs/data/companies.json").exists():
        out.append(("cosmetics", ROOT / "docs/data", ROOT / "config"))
    for p in sorted((ROOT / "docs").glob("*/data/companies.json")):
        ind = p.parent.parent.name
        out.append((ind, p.parent, ROOT / "config" / ind))
    return [x for x in out if not sel or x[0] in sel]


def jload(p, default=None):
    try:
        return json.loads(Path(p).read_text("utf-8"))
    except Exception:  # noqa: BLE001
        return default


# ---------------------------------------------------------------- 날짜 도우미
def qn(k):  # '2022Q3' → 정수
    return int(k[:4]) * 4 + int(k[5]) - 1


def qk(n):
    return f"{n // 4}Q{n % 4 + 1}"


def m2q(m):
    return qn(f"{m[:4]}Q{(int(m[5:7]) + 2) // 3}")


def madd(m, k):
    y, mo = int(m[:4]), int(m[5:7]) - 1 + k
    return f"{y + mo // 12}-{mo % 12 + 1:02d}"


def qend(n):  # 분기 마지막 달
    return f"{n // 4}-{(n % 4 + 1) * 3:02d}"


def reported_q(m):
    """m월 말에 시장이 알고 있던 마지막 분기(분기 끝 + 2개월 뒤 발표로 가정)."""
    n = m2q(m)
    while madd(qend(n), 2) > m:
        n -= 1
    return n


def kor_m(m):
    return f"{m[:4]}년 {int(m[5:7])}월"


def pct(r, sign=True):
    if r is None or not math.isfinite(r):
        return "–"
    x = r * 100
    s = f"{x:+.0f}%" if abs(x) >= 10 else f"{x:+.1f}%"
    return s if sign else s.lstrip("+")


def pp(r):
    return f"{r * 100:+.0f}%p"


def eok(v):  # 백만원 → 억/조
    if v is None:
        return "–"
    e = v / 100
    if abs(e) >= 10000:
        return f"{e / 10000:,.2f}조".replace(".00조", "조")
    return f"{e:,.0f}억"


def chg(a, b):
    if a is None or b is None:
        return None
    if a > 0 and b > 0:
        return b / a - 1
    return (b - a) / max(abs(a), abs(b), 1e-9)


# ---------------------------------------------------------------- 회사 한 곳
class Co:
    def __init__(self, c, series):
        self.c = c
        self.code, self.name = c["code"], c["name"]
        self.group = c.get("group") or ""
        self.market = c.get("market") or "KOSPI"
        self.Q = {k: v for k, v in (c.get("quarterly") or {}).items() if re.fullmatch(r"\d{4}Q[1-4]", k)}
        self.A = c.get("annual") or {}
        sh = (c.get("shares") or {})
        self.shares = sh.get("common") or sh.get("common_issued")
        self.px = {}
        if series:
            for m, v in zip(series.get("months", []), series.get("close", [])):
                if v and v > 0:
                    self.px[m] = v
        self.months = sorted(self.px)

    def val(self, n, f):
        r = self.Q.get(qk(n))
        return None if not r or r.get(f) is None else r[f]

    def ttm(self, n, f):
        s = 0
        for i in range(4):
            v = self.val(n - i, f)
            if v is None:
                return None
            s += v
        return s

    @property
    def ek(self):
        for f in ("op", "ni", "rev"):
            if any(self.ttm(qn(k), f) is not None for k in self.Q):
                return f
        return None

    def pq(self, n):  # 분기 마지막 관측 월 종가
        ms = [m for m in self.months if m2q(m) == n]
        return (self.px[ms[-1]], ms[-1]) if ms else (None, None)

    def ni_ttm_at(self, m):
        n = reported_q(m)
        v = self.ttm(n, "ni")
        if v is not None:
            return v, qk(n), "4분기 합"
        y = str(int(m[:4]) - (1 if int(m[5:7]) >= 3 else 2))
        a = self.A.get(y) or {}
        return (a.get("ni"), y, "연간") if a.get("ni") is not None else (None, None, None)

    def per_at(self, m):
        p = self.px.get(m)
        ni, _, _ = self.ni_ttm_at(m)
        if not p or not self.shares or ni is None or ni <= 0:
            return None
        return p * self.shares / (ni * 1e6)

    def ret(self, m0, m1):
        a, b = self.px.get(m0), self.px.get(m1)
        return b / a - 1 if a and b else None


# ---------------------------------------------------------------- 변곡점 찾기
def bands(co):
    """finchart.js sigAt 과 같은 규칙. 같은 종류가 이어진 분기는 한 구간으로 묶는다."""
    ek = co.ek
    if not ek:
        return []
    qs = sorted(qn(k) for k in co.Q)
    out = []
    for n in range(qs[0], qs[-1] + 1):
        e1, e0 = co.ttm(n, ek), co.ttm(n - 4, ek)
        p1, m1 = co.pq(n)
        p0, m0 = co.pq(n - 4)
        if e1 is None or e0 is None or not p1 or not p0:
            continue
        de, dp = chg(e0, e1), p1 / p0 - 1
        eu = 1 if de > TH_E else -1 if de < -TH_E else 0
        pu = 1 if dp > TH_P else -1 if dp < -TH_P else 0
        t = "opp" if eu > 0 > pu else "warn" if eu < 0 < pu else None
        if not t:
            continue
        if out and out[-1]["t"] == t and out[-1]["q1"] == n - 1:
            out[-1]["q1"] = n
        else:
            out.append({"t": t, "q0": n, "q1": n})
    return out


def zz_th(co):
    """변동성이 큰 종목은 문턱을 높여 잔물결을 변곡점으로 잡지 않는다: 연 변동성 × 0.8, 30~50%."""
    ms = co.months
    lr = [math.log(co.px[b] / co.px[a]) for a, b in zip(ms, ms[1:])]
    if len(lr) < 12:
        return ZZ
    vol = stx.pstdev(lr) * math.sqrt(12)
    return min(0.5, max(ZZ, round(vol * 0.8, 2)))


def zigzag(co, th=None):
    ms = co.months
    if len(ms) < 6:
        return []
    th = th or zz_th(co)
    v = lambda i: co.px[ms[i]]
    piv = []           # (index, 'peak'|'trough')
    hi = lo = 0
    trend = 0          # 0: 아직 방향 없음, 1: 상승 중(고점 추적), -1: 하락 중(저점 추적)
    for i in range(1, len(ms)):
        if trend == 0:
            hi = i if v(i) > v(hi) else hi
            lo = i if v(i) < v(lo) else lo
            if v(i) <= v(hi) * (1 - th):
                piv.append((hi, "peak")); trend, lo = -1, i
            elif v(i) >= v(lo) * (1 + th):
                piv.append((lo, "trough")); trend, hi = 1, i
        elif trend == 1:
            if v(i) > v(hi):
                hi = i
            elif v(i) <= v(hi) * (1 - th):
                piv.append((hi, "peak")); trend, lo = -1, i
        else:
            if v(i) < v(lo):
                lo = i
            elif v(i) >= v(lo) * (1 + th):
                piv.append((lo, "trough")); trend, hi = 1, i
    piv = [(0, "start")] + [p for p in piv if p[0] > 0]
    legs = []
    for (i0, k0), (i1, _) in zip(piv, piv[1:]):
        if i1 > i0:
            legs.append({"i0": i0, "i1": i1, "k0": k0})
    # 마지막 변곡점 이후 진행 중인 흐름
    last_i, last_k = piv[-1]
    end = len(ms) - 1
    if end > last_i:
        r = co.px[ms[end]] / co.px[ms[last_i]] - 1
        if abs(r) >= th * 0.67:  # 20% 이상이면 '진행 중' 구간으로 보여 줌
            legs.append({"i0": last_i, "i1": end, "k0": last_k, "open": True})
    out = []
    for g in legs:
        m0, m1 = ms[g["i0"]], ms[g["i1"]]
        out.append({"m0": m0, "m1": m1, "t": "up" if co.px[m1] > co.px[m0] else "down", "open": g.get("open", False)})
    # 첫 구간(데이터 시작점에서 출발)은 진짜 변곡점이 아니므로 시작 표시만 생략
    if out:
        out[0]["from_start"] = True
    return out


# ---------------------------------------------------------------- 시장·업종 비교
class Universe:
    def __init__(self, inds):
        self.cos = {}      # (ind, code) → Co
        self.by_ind = {}
        for ind, data, _cfg in inds:
            comp = (jload(data / "companies.json") or {}).get("companies") or []
            ser = ((jload(data / "stock_hist.json") or {}).get("series")) or {}
            lst = []
            for c in comp:
                co = Co(c, ser.get(c["code"]))
                self.cos[(ind, c["code"])] = co
                lst.append(co)
            self.by_ind[ind] = lst
        uniq = {}
        for (_, code), co in self.cos.items():
            uniq.setdefault(code, co)
        self.all = list(uniq.values())
        self.macro = jload(ROOT / "docs/shared/macro.json", {}) or {}

    @staticmethod
    def med(cos, m0, m1, skip=None):
        r = [c.ret(m0, m1) for c in cos if c.code != skip]
        r = [x for x in r if x is not None]
        return (stx.median(r), len(r)) if len(r) >= 3 else (None, len(r))

    def mseries(self, key):
        s = (self.macro.get("series") or {}).get(key) or {}
        return s.get("data") or {}

    def mval(self, key, m):
        d = self.mseries(key)
        if m in d:
            return d[m]
        prev = [k for k in d if k <= m]
        return d[max(prev)] if prev else None

    def index_ret(self, market, m0, m1):
        key = "KOSDAQ" if market == "KOSDAQ" else "KOSPI"
        a, b = self.mval(key, m0), self.mval(key, m1)
        return (b / a - 1, "코스닥" if key == "KOSDAQ" else "코스피") if a and b else (None, None)


# ---------------------------------------------------------------- 사건 연표 매칭
def match_events(ind, co, m0, m1, r=None):
    """구간과 겹치는 사건. 구간 전에 시작해 이어지던 사건은 주가 방향과 맞을 때만 붙인다(반대 방향 사건이 해설에 섞이지 않게)."""
    out = []
    lo, hi = madd(m0, -1), m1
    for e in EVENTS:
        d = e["d"]
        end = e.get("end", d)
        if end < lo or d > hi:
            continue
        if d < lo and r is not None and e["dir"] in "+-" and (e["dir"] == "+") != (r > 0):
            continue
        sc = e["scope"]
        ok = sc == "all" or sc == f"ind:{ind}" or (sc.startswith("grp:") and sc == f"grp:{ind}:{co.group}") \
            or (sc.startswith("code:") and co.code in sc[5:].split(","))
        if not ok:
            continue
        # 업종 사건 중 특정 사업군만 해당하는 것
        if e.get("groups") and co.group not in e["groups"]:
            continue
        if e.get("not_groups") and co.group in e["not_groups"]:
            continue
        out.append(e)
    rank = {"code": 0, "grp": 1, "ind": 2, "all": 3}
    inside = lambda e: e["d"] >= lo
    out.sort(key=lambda e: (rank[e["scope"].split(":")[0]], not inside(e), e["d"]))
    return out


# ---------------------------------------------------------------- 뉴스
NEWS_CAT = [
    ("실적", r"실적|영업이익|영업익|순이익|매출|어닝|서프라이즈|쇼크|흑자|적자|컨센서스|가이던스|잠정"),
    ("수주·계약", r"수주|공급계약|계약 체결|단일판매|납품|퀄|승인|인증|입찰"),
    ("자본·지배구조", r"유상증자|무상증자|전환사채|CB|BW|자사주|소각|배당|분할|합병|인수|매각|지분|경영권|최대주주|블록딜|오버행|상장|IPO|보호예수"),
    ("규제·정책", r"관세|규제|정책|정부|보조금|IRA|제재|수출규제|허가|FDA|식약처|공정위|과징금|소송|특허"),
    ("업황·수요", r"수요|업황|가격|단가|재고|감산|증설|점유율|출하|수출|판매량|운임|마진|스프레드"),
    ("목표가·리포트", r"목표가|목표주가|투자의견|리포트|매수|하향|상향"),
]


def news_cat(t):
    for cat, rx in NEWS_CAT:
        if re.search(rx, t):
            return cat
    return None


def news_in(news, m0, m1, limit=4):
    lo, hi = madd(m0, -1) + "-01", madd(m1, 1) + "-31"
    cand = []
    for x in news:
        d = x.get("date") or ""
        if not (lo <= d <= hi):
            continue
        cat = news_cat(x.get("title", ""))
        if not cat and not x.get("read"):
            continue
        pri = 0 if x.get("read") else (1 if cat in ("실적", "수주·계약", "자본·지배구조", "규제·정책") else 2)
        cand.append((pri, d, x, cat))
    cand.sort(key=lambda z: (z[0], z[1]))
    seen, out = set(), []
    for pri, d, x, cat in cand:
        k = re.sub(r"\W", "", x.get("title", ""))[:24]
        if k in seen:
            continue
        seen.add(k)
        out.append({"d": d, "t": x.get("title", ""), "u": x.get("url", ""), "src": x.get("office") or x.get("src") or "",
                    "cat": cat or "해석", "read": x.get("read", "")})
        if len(out) >= limit:
            break
    out.sort(key=lambda z: z["d"])
    return out


# ---------------------------------------------------------------- 해설 만들기
def describe(U, ind, co, m0, m1, kind, t, news, qq=None):
    """구간 [m0, m1] 의 주가 움직임을 근거별로 설명한다."""
    F = []          # [{tag, text}]
    drivers = []    # (크기, 짧은 문장)
    r = co.ret(m0, m1)
    p0, p1 = co.px.get(m0), co.px.get(m1)
    iname = IND_NAME.get(ind, ind)

    # 1) 시장·업종·사업군 비교
    rm, mname = U.index_ret(co.market, m0, m1)
    if rm is None:
        rm, nn = U.med(U.all, m0, m1, co.code)
        mname = f"7개 산업 대시보드 전체 {nn}개사 중앙값" if rm is not None else None
    ri, ni_ = U.med(U.by_ind.get(ind, []), m0, m1, co.code)
    grp = [c for c in U.by_ind.get(ind, []) if c.group == co.group]
    rg, ng = U.med(grp, m0, m1, co.code) if co.group else (None, 0)
    base = rg if rg is not None and ng >= 3 else ri
    resid = None
    if r is not None:
        parts = []
        if rm is not None:
            parts.append(f"{mname} {pct(rm)}")
        if ri is not None:
            parts.append(f"{iname} 업종({ni_}개사 중앙값) {pct(ri)}")
        if rg is not None and ng >= 3:
            parts.append(f"같은 사업군 '{co.group}'({ng}개사) {pct(rg)}")
        if base is not None:
            resid = (1 + r) / (1 + base) - 1
            ind_part = (1 + base) / (1 + rm) - 1 if rm is not None else None
            who = []
            if rm is not None and abs(rm) >= 0.10:
                who.append(("시장 전체", abs(math.log1p(rm)), rm))
            if ind_part is not None and abs(ind_part) >= 0.10:
                who.append(("업종 공통", abs(math.log1p(ind_part)), ind_part))
            if abs(resid) >= 0.10:
                who.append(("회사 고유", abs(math.log1p(resid)), resid))
            who.sort(key=lambda w: -w[1])
            if who:
                tot = sum(w[1] for w in who) or 1
                share = ", ".join(f"{w[0]} {w[1] / tot * 100:.0f}%" for w in who)
                lead = who[0]
                if lead[0] == "회사 고유":
                    concl = f"업종·시장 대비 상대 성과가 {pct(resid)}로 이 회사만의 이유가 컸어요"
                elif lead[0] == "업종 공통":
                    concl = f"{iname} 업종 전체가 {'함께 오른' if ind_part > 0 else '함께 빠진'} 영향이 가장 컸어요"
                else:
                    concl = f"시장 전체가 {'오른' if rm > 0 else '빠진'} 흐름의 영향이 가장 컸어요"
                F.append({"tag": "시장·업종 비교", "text": f"같은 기간 {', '.join(parts)}. 움직임을 나눠 보면 {share} 정도라, {concl}."})
                drivers.append((lead[1] + 0.01, concl))
            else:
                F.append({"tag": "시장·업종 비교", "text": f"같은 기간 {', '.join(parts)}로, 이 회사 움직임은 업종·시장과 큰 차이가 없었어요."})

    # 2) 이익 × PER 분해
    ek = co.ek
    # 띠(엇갈린 구간)는 차트와 같은 분기 실적끼리, 고점·저점 구간은 그 달에 발표돼 있던 실적으로 비교
    q0, q1 = qq or (reported_q(m0), reported_q(m1))
    e0 = co.ttm(q0, ek) if ek else None
    e1 = co.ttm(q1, ek) if ek else None
    en = {"op": "영업이익", "ni": "순이익", "rev": "매출"}.get(ek, "이익")
    if qq:
        def _per(m, q):
            ni, p = co.ttm(q, "ni"), co.px.get(m)
            return p * co.shares / (ni * 1e6) if p and co.shares and ni and ni > 0 else None
        per0, per1 = _per(m0, q0), _per(m1, q1)
    else:
        per0, per1 = co.per_at(m0), co.per_at(m1)
    de = chg(e0, e1)
    if e0 is not None and e1 is not None and q1 > q0:
        etxt = f"{qk(q0)}→{qk(q1)} {en}(4분기 합) {eok(e0)} → {eok(e1)}" + (f"({pct(de)})" if e0 > 0 and e1 > 0 else
                                                                         " (흑자 전환)" if e0 <= 0 < e1 else " (적자 전환)" if e1 <= 0 < e0 else "")
        if per0 and per1:
            dper = per1 / per0 - 1
            etxt += f", PER은 {per0:.1f}배 → {per1:.1f}배({pct(dper)})"
            if r is not None and e0 > 0 and e1 > 0:
                le, lp = math.log1p(de), math.log1p(dper)
                if abs(lp) > abs(le) * 1.5 and abs(lp) > 0.1:
                    msg = (f"이익보다 시장이 매기는 배수(PER)가 {'올라간(기대 상승)' if dper > 0 else '내려간(기대 하락)'} 영향이 더 컸어요")
                elif abs(le) > abs(lp) * 1.5 and abs(le) > 0.1:
                    msg = f"주가는 대체로 이익 변화를 따라 움직였어요"
                else:
                    msg = "이익 변화와 배수(PER) 변화가 함께 작용했어요"
                etxt += f". {msg}"
                drivers.append((max(abs(lp), abs(le)) * 0.9, msg))
        elif (co.ni_ttm_at(m0)[0] or 0) <= 0 or (co.ni_ttm_at(m1)[0] or 0) <= 0:
            etxt += ". 순이익이 적자인 시기가 있어 PER로는 설명할 수 없고, 주가가 이익보다 앞날의 기대·우려로 움직인 구간이에요"
        F.append({"tag": "이익과 PER", "text": etxt + "."})
    elif not co.Q:
        # 분기 실적이 없는 오래된 구간 → 연간 실적
        y0, y1 = str(int(m0[:4]) - 1), str(int(m1[:4]) - 1)
        a0, a1 = (co.A.get(y0) or {}).get("op"), (co.A.get(y1) or {}).get("op")
        if a0 is not None and a1 is not None and y1 > y0:
            F.append({"tag": "이익과 PER", "text": f"연간 영업이익 {y0}년 {eok(a0)} → {y1}년 {eok(a1)}" + (f"({pct(chg(a0, a1))})" if a0 > 0 and a1 > 0 else "") + "."})

    # 3) 밸류에이션 위치(자기 역사 대비)
    hist = [co.per_at(m) for m in co.months]
    hist = sorted(x for x in hist if x and 0 < x < 300)
    if per0 and len(hist) >= 24:
        rank = sum(1 for x in hist if x <= per0) / len(hist)
        med = stx.median(hist)
        lvl = "역사적으로 비싼 편(상위 20%)" if rank >= 0.8 else "역사적으로 싼 편(하위 20%)" if rank <= 0.2 else "역사적 중간 수준"
        vtxt = f"구간 시작({kor_m(m0)}) PER {per0:.1f}배는 이 회사 {len(hist) // 12}년여 월별 PER 중앙값 {med:.1f}배 대비 {lvl}이었어요"
        if r is not None:
            if rank >= 0.8 and r < 0:
                vtxt += ". 높은 기대가 이미 가격에 들어 있어 작은 실망에도 배수가 빠지기 쉬운 자리였어요"
                drivers.append((abs(math.log1p(r)) * 0.6, "출발점 밸류에이션이 높아 기대가 꺾이며 배수가 낮아졌어요"))
            elif rank <= 0.2 and r > 0:
                vtxt += ". 비관이 많이 반영된 가격이라 작은 개선에도 배수가 회복되기 쉬운 자리였어요"
                drivers.append((abs(math.log1p(r)) * 0.6, "출발점 밸류에이션이 낮아 개선 신호에 배수가 회복됐어요"))
            elif rank >= 0.8 and r > 0:
                vtxt += ". 이미 비싼 가격에서 더 오른 것이라, 이후 실적이 기대를 따라오는지가 중요했어요"
            elif rank <= 0.2 and r < 0:
                vtxt += ". 이미 싼 가격에서 더 빠진 것이라, 시장이 이익 자체가 더 줄 것으로 봤다는 뜻이에요"
        F.append({"tag": "밸류에이션", "text": vtxt + ". (PER은 현재 주식 수로 계산한 추정치예요)"})

    # 4) 실적 발표 반응(서프라이즈·쇼크 대리 지표)
    rx = []
    if ek:
        for n in range(q0 + 1, q1 + 1):
            am = madd(qend(n), 2)  # 발표 달(분기 끝 + 2개월 무렵)
            pm = madd(am, -1)
            if am < m0 or am > m1 or am not in co.px or pm not in co.px:
                continue
            v, pv = co.val(n, "op"), co.val(n - 4, "op")
            if v is None:
                continue
            mr = co.px[am] / co.px[pm] - 1
            peers = [c.ret(pm, am) for c in U.by_ind.get(ind, []) if c.code != co.code]
            peers = [x for x in peers if x is not None]
            ex = mr - stx.median(peers) if len(peers) >= 3 else mr
            rx.append((abs(ex), n, v, pv, mr, ex, am))
    if rx:
        rx.sort(reverse=True)
        _, n, v, pv, mr, ex, am = rx[0]
        y = chg(pv, v)
        yt = (f"전년 대비 {pct(y)}" if pv and pv > 0 and v > 0 else "흑자 전환" if pv is not None and pv <= 0 < v
              else "적자 전환" if pv is not None and v <= 0 < pv else "적자 지속" if v <= 0 else "")
        rev = co.val(n, "rev")
        bits = [b for b in (yt, f"영업이익률 {v / rev * 100:.1f}%" if rev else "") if b]
        txt = f"구간 안에서 주가 반응이 가장 컸던 실적은 {qk(n)} 영업이익 {eok(v)}{'(' + ', '.join(bits) + ')' if bits else ''}예요. 발표 무렵인 {kor_m(am)} 주가 {pct(mr)}, 업종보다 {pp(ex)}"
        if abs(ex) >= 0.08:
            good = ex > 0
            txt += f"로 시장 기대를 {'웃돈 서프라이즈' if good else '밑돈 실망(쇼크)'}로 받아들여졌을 가능성이 커요"
            if r is None or (ex > 0) == (r > 0):
                drivers.append((abs(ex) * 1.2, f"{qk(n)} 실적 발표({kor_m(am)}) 뒤 업종보다 {pp(ex)} {'반응 — 서프라이즈' if good else '반응 — 실망'}"))
        else:
            txt += "로, 실적 발표 자체가 큰 전환점은 아니었어요"
        F.append({"tag": "실적 발표 반응", "text": txt + ". (컨센서스 자료가 없어 발표 달 업종 대비 주가 반응으로 추정)"})

    # 5) 사후 확인 — 시장이 미리 반영했나
    if ek and e1 is not None:
        e2 = co.ttm(q1 + 4, ek)
        if e2 is not None:
            d2 = chg(e1, e2)
            r2 = co.ret(m1, madd(m1, 12)) if madd(m1, 12) in co.px else None
            if r is not None and d2 is not None:
                same = (r > 0) == (d2 > 0)
                txt = f"구간이 끝난 뒤 1년({qk(q1)}→{qk(q1 + 4)}) {en}은 {pct(d2) if e1 > 0 and e2 > 0 else eok(e1) + '→' + eok(e2)}"
                if r2 is not None:
                    txt += f", 주가는 {pct(r2)}"
                if abs(d2) >= 0.1:
                    txt += (". 주가가 이익 변화를 미리 반영한 셈이에요" if same else
                            ". 주가 방향과 이후 이익 방향이 반대라, 이 구간의 움직임은 결과적으로 과했던 셈이에요")
                else:
                    txt += ". 이후 이익은 크게 달라지지 않았어요"
                F.append({"tag": "사후 확인", "text": txt + "."})

    # 6) 거시
    mt = []
    fx0, fx1 = U.mval("USDKRW", m0), U.mval("USDKRW", m1)
    if fx0 and fx1 and abs(fx1 / fx0 - 1) >= 0.05:
        w = fx1 > fx0
        s = FX_SENS.get(ind, 0)
        eff = ("수출 비중이 큰 회사엔 원화 환산 이익 증가 요인" if s > 0 else "원재료 수입 비용 증가 요인" if s < 0 else "업체별로 득실이 갈리는 요인") if w else \
              ("수출 비중이 큰 회사엔 이익 감소 요인" if s > 0 else "원재료 수입 비용 감소 요인" if s < 0 else "업체별로 득실이 갈리는 요인")
        mt.append(f"원/달러 {fx0:,.0f}원 → {fx1:,.0f}원({pct(fx1 / fx0 - 1)}, 원화 {'약세' if w else '강세'}): {eff}이고, 원화 {'약세' if w else '강세'}는 보통 외국인 자금 {'이탈' if w else '유입'}과 함께 와요")
    k0, k1 = U.mval("KR10Y", m0), U.mval("KR10Y", m1)
    u0, u1 = U.mval("US10Y", m0), U.mval("US10Y", m1)
    if u0 is not None and u1 is not None and abs(u1 - u0) >= 0.5:
        mt.append(f"미국 10년 금리 {u0:.2f}% → {u1:.2f}%({u1 - u0:+.2f}%p): 금리가 {'오르면 먼 미래 이익의 현재가치가 줄어 성장주 배수가 눌리고' if u1 > u0 else '내리면 성장주 배수가 회복되기 쉽고'}")
    elif k0 is not None and k1 is not None and abs(k1 - k0) >= 0.5:
        mt.append(f"한국 10년 금리 {k0:.2f}% → {k1:.2f}%({k1 - k0:+.2f}%p)")
    o0, o1 = U.mval("BRENT", m0), U.mval("BRENT", m1)
    if o0 and o1 and abs(o1 / o0 - 1) >= 0.25 and ind in OIL_SENS:
        mt.append(f"브렌트유 ${o0:.0f} → ${o1:.0f}({pct(o1 / o0 - 1)}): {OIL_SENS[ind]} 요인")
    if mt:
        F.append({"tag": "거시 지표", "text": ". ".join(mt) + "."})

    # 7) 사건 연표
    ev = match_events(ind, co, m0, m1, r)
    srcs = []
    if ev:
        co_ev = [e for e in ev if e["scope"].startswith("code:")]
        oth = [e for e in ev if not e["scope"].startswith("code:")]
        for e in co_ev[:3]:
            F.append({"tag": "회사 사건", "text": f"{e['d'].replace('-', '.')} {e['title']} — {e['text']}"})
        ind_ev = [e for e in oth if e["scope"] != "all"][:3]
        mk_ev = [e for e in oth if e["scope"] == "all"][:2]
        oth = sorted(ind_ev + mk_ev, key=lambda e: e["d"])
        for e in oth:
            F.append({"tag": "업종 사건" if e["scope"] != "all" else "거시·시장 사건", "text": f"{e['d'].replace('-', '.')} {e['title']} — {e['text']}"})
        for e in (co_ev + oth)[:6]:
            if e.get("src"):
                srcs.append({"t": e["title"], "u": e["src"]})
        top = co_ev[0] if co_ev else (ind_ev + mk_ev)[0]
        e_dir = top.get("dir", "")
        if (e_dir == "+" and (r or 0) > 0) or (e_dir == "-" and (r or 0) < 0) or e_dir in ("±", ""):
            drivers.append((1.0 if co_ev else 0.5, f"{top['d'][:7].replace('-', '.')} {top['title']}"))

    # 8) 뉴스
    nw = news_in(news, m0, m1)
    if nw and not any(f["tag"] == "회사 사건" for f in F):
        key = [x for x in nw if x["cat"] in ("실적", "수주·계약", "자본·지배구조", "규제·정책")] or nw
        x = key[-1]
        drivers.append((0.45, f"뉴스: {x['d'][:7].replace('-', '.')} {x['t'][:40]}"))
    for x in nw:
        F.append({"tag": f"뉴스 · {x['cat']}", "text": f"{x['d']} {x['t']}" + (f" — {x['read']}" if x['read'] else ""), "u": x["u"]})

    # 9) 불확실성
    explained_co = any(f["tag"] in ("회사 사건", "실적 발표 반응") for f in F) or nw
    unc = None
    if resid is not None and abs(resid) >= 0.2 and not explained_co:
        unc = (f"업종·시장으로 설명되지 않는 회사 고유 몫(업종·시장 대비 상대 성과 {pct(resid)})이 큰데, 이 시기를 설명할 회사 사건·뉴스를 확인하지 못했어요. "
               "수급(대주주·기관 매매, 오버행), 테마성 매매, 공시되지 않은 사업 변화일 수 있어 원인은 불확실해요.")
    elif not drivers:
        unc = "뚜렷한 단일 원인을 찾지 못했어요. 아래 숫자는 사실이지만, 원인 연결은 추정이에요."
    if unc:
        F.append({"tag": "불확실", "text": unc})

    drivers.sort(key=lambda d: -d[0])
    seen, top3 = set(), []
    for _, d in drivers:
        if d not in seen:
            seen.add(d)
            top3.append(d)
    return F, top3[:3], srcs, unc is not None, resid


def build_company(U, ind, co, news):
    if len(co.months) < 6:
        return []
    events = []
    # ① 엇갈린 구간
    for b in bands(co):
        _, m1 = co.pq(b["q1"])
        _, m0 = co.pq(b["q0"] - 4)
        if not m0 or not m1:
            continue
        ek = co.ek
        en = {"op": "영업이익", "ni": "순이익", "rev": "매출"}[ek]
        e0, e1 = co.ttm(b["q0"] - 4, ek), co.ttm(b["q1"], ek)
        r = co.ret(m0, m1)
        F, drv, srcs, unc, resid = describe(U, ind, co, m0, m1, "band", b["t"], news, (b["q0"] - 4, b["q1"]))
        de = chg(e0, e1)
        head = f"{en}(4분기 합) {pct(de) if e0 and e1 and e0 > 0 and e1 > 0 else eok(e0) + '→' + eok(e1)}인데 주가 {pct(r)}"
        why = "; ".join(drv) if drv else "원인 불확실"
        lbl = "실적↑ 주가↓" if b["t"] == "opp" else "실적↓ 주가↑"
        if b["t"] == "opp":
            look = "이후 이익이 계속 늘었는지(사후 확인)를 보면, 이런 구간이 저가 매수 기회였는지 이익 정점 신호였는지 구분할 수 있어요."
        else:
            look = "실적이 아직 안 좋은데 주가가 먼저 오른 구간이에요. 이후 이익 회복이 따라왔는지(사후 확인)가 기대가 맞았는지를 말해 줘요."
        events.append({"kind": "band", "t": b["t"], "q0": qk(b["q0"]), "q1": qk(b["q1"]), "m0": m0, "m1": m1,
                       "title": f"{qk(b['q0'])}{'' if b['q0'] == b['q1'] else '~' + qk(b['q1'])} {lbl}",
                       "head": head, "why": why, "look": look, "f": F, "src": srcs, "unc": unc})
    # ② 큰 흐름의 고점·저점 (차트가 그리는 기간 = 4분기 합 실적이 시작되는 분기부터)
    ts = [qn(k) for k in co.Q if co.ttm(qn(k), "rev") is not None and co.pq(qn(k))[0]]
    cstart = qend(min(ts) - 1) if ts else ""
    for g in zigzag(co):
        m0, m1 = g["m0"], g["m1"]
        if m1 <= cstart:
            continue
        if g.get("from_start") and abs(co.ret(m0, m1) or 0) < ZZ:
            continue  # 데이터 시작점에서 출발한 밋밋한 구간은 변곡점이 아님
        r = co.ret(m0, m1)
        F, drv, srcs, unc, resid = describe(U, ind, co, m0, m1, "leg", g["t"], news)
        p0, p1 = co.px[m0], co.px[m1]
        start = "데이터 시작" if g.get("from_start") else ("고점" if g["t"] == "down" else "저점")
        months = (int(m1[:4]) - int(m0[:4])) * 12 + int(m1[5:7]) - int(m0[5:7])
        head = f"{kor_m(m0)} {start} {p0:,.0f}원 → {kor_m(m1)}{' 현재' if g['open'] else ''} {p1:,.0f}원({pct(r)}, {months}개월)"
        why = "; ".join(drv) if drv else "원인 불확실"
        look = ("상승을 이끈 요인(이익 증가인지, 배수 확대인지)이 지금도 유효한지 보면 다음 흐름을 판단하는 데 도움이 돼요." if g["t"] == "up" else
                "하락을 부른 요인이 이익 자체의 훼손이었는지, 배수(기대)의 조정이었는지에 따라 회복 경로가 달라져요.")
        events.append({"kind": "leg", "t": g["t"], "m0": m0, "m1": m1, "open": g["open"], "pivot": not g.get("from_start"),
                       "title": f"{kor_m(m0)}~{kor_m(m1)}{' (진행 중)' if g['open'] else ''} {'상승' if g['t'] == 'up' else '하락'} {pct(r)}",
                       "head": head, "why": why, "look": look, "f": F, "src": srcs, "unc": unc})
    events.sort(key=lambda e: (e["m0"], e["kind"]))
    for i, e in enumerate(events):
        e["id"] = i + 1
    return events


# ---------------------------------------------------------------- 연간 실적표: 크게 변한 해의 이유
def _yr(a, b):
    return chg(a, b)


def year_notes(U, ind, co, news):
    A = co.A
    ys = sorted(y for y in A if re.fullmatch(r"\d{4}", y))
    iname = IND_NAME.get(ind, ind)
    out = {}
    for y0, y in zip(ys, ys[1:]):
        a, b = A[y0] or {}, A[y] or {}
        rv0, rv1, op0, op1, ni0, ni1 = a.get("rev"), b.get("rev"), a.get("op"), b.get("op"), a.get("ni"), b.get("ni")
        if not rv0 or not rv1:
            continue
        gr = rv1 / rv0 - 1
        og = _yr(op0, op1)
        flip = lambda x0, x1: x0 is not None and x1 is not None and (x0 > 0) != (x1 > 0)
        big_rev = abs(gr) >= 0.15
        big_op = op0 is not None and op1 is not None and (flip(op0, op1) or (og is not None and abs(og) >= 0.4 and max(abs(op0), abs(op1)) >= rv1 * 0.01))
        big_ni = flip(ni0, ni1)
        if not (big_rev or big_op or big_ni):
            continue
        F, why = [], []
        def ch(x0, x1):
            if x0 is None or x1 is None:
                return "–"
            if x0 > 0 and x1 > 0:
                return pct(x1 / x0 - 1)
            return "흑자 전환" if x1 > 0 >= x0 else "적자 전환" if x0 > 0 >= x1 else "적자 축소" if x1 > x0 else "적자 확대"
        head = f"매출 {eok(rv0)}→{eok(rv1)}({pct(gr)}), 영업이익 {eok(op0)}→{eok(op1)}({ch(op0, op1)})"
        # 1) 업종·사업군 비교
        peers = []
        for c in U.by_ind.get(ind, []):
            if c.code == co.code:
                continue
            p0, p1 = (c.A.get(y0) or {}).get("rev"), (c.A.get(y) or {}).get("rev")
            if p0 and p1 and p0 > 0:
                peers.append((c, p1 / p0 - 1))
        im = stx.median([g for _, g in peers]) if len(peers) >= 5 else None
        gp = [g for c, g in peers if c.group == co.group]
        gm = stx.median(gp) if len(gp) >= 3 else None
        if im is not None:
            ref = gm if gm is not None else im
            diff = gr - ref
            t = f"같은 해 {iname} 업종 {len(peers)}개사 매출 증가율 중앙값 {pct(im)}" + (f", 같은 사업군 '{co.group}' {len(gp)}개사 {pct(gm)}" if gm is not None else "")
            if abs(diff) < 0.08 and abs(ref) >= 0.08:
                t += f". 이 회사도 비슷하게 움직여 업종 전체의 업황(수요·가격 사이클)이 주된 이유예요"
                why.append(f"업종 전체 업황 {'호조' if ref > 0 else '부진'}(사업군 중앙값 {pct(ref)})")
            elif abs(diff) >= 0.08:
                t += f". 업종보다 {pp(diff)} {'더 늘어' if diff > 0 else '더 줄어'} 회사 고유 요인(신규 고객·제품, 인수, 점유율 변화 등)이 컸어요"
                why.append(f"업종 대비 {pp(diff)} — 회사 고유 요인")
            else:
                t += ". 업종도 이 회사도 큰 변화가 없었어요"
            F.append({"tag": "업종 비교", "text": t + "."})
        # 2) 분기 흐름: 어느 분기에, 계단식인지
        qs = [f"{y}Q{i}" for i in range(1, 5)]
        qrow = []
        for k in qs:
            n = qn(k)
            v, pv = co.val(n, "rev"), co.val(n - 4, "rev")
            if v is not None and pv:
                qrow.append((k, v, v / pv - 1))
        if qrow:
            t = "분기별 매출 전년 대비: " + ", ".join(f"{k[-2:]} {pct(g)}" for k, _, g in qrow)
            steps = []
            for n in (range(qn(qs[0]), qn(qs[-1]) + 1) if gr >= 0.1 else []):
                v0, v1, v2 = co.val(n - 1, "rev"), co.val(n, "rev"), co.val(n + 1, "rev")
                if v0 and v1 and v0 > 0 and v1 / v0 - 1 >= 0.25 and (v2 is None or v2 >= v1 * 0.9):
                    # 업종 전체가 같이 뛴 분기(업황 반등)는 제외: 사업군 동료의 같은 분기 증가율 중앙값보다 20%p 이상 높을 때만
                    qq = lambda grp: [c.val(n, "rev") / c.val(n - 1, "rev") - 1 for c in U.by_ind.get(ind, [])
                                      if c.code != co.code and (grp is None or c.group == grp) and c.val(n, "rev") and c.val(n - 1, "rev") and c.val(n - 1, "rev") > 0]
                    pq_ = qq(co.group)
                    if len(pq_) < 3:
                        pq_ = qq(None)
                    if len(pq_) >= 3 and v1 / v0 - 1 - stx.median(pq_) < 0.2:
                        continue
                    # 매출총이익률이 같이 5%p 넘게 뛰면 물량·인수보다 판가(가격) 상승 → 계단식으로 보지 않음
                    g_0, g_1 = co.val(n - 1, "gp"), co.val(n, "gp")
                    if g_0 is not None and g_1 is not None and g_1 / v1 - g_0 / v0 >= 0.05:
                        continue
                    steps.append((qk(n), v1 / v0 - 1))
            if steps:
                k, g = steps[0]
                t += f". {k}에 분기 매출이 직전 분기보다 {pct(g)} 계단식으로 뛰고 유지됐어요. 같은 분기 동종사는 그만큼 늘지 않았고 마진도 함께 뛰지 않아 업황·가격보다는 신규 연결(인수·합병), 대형 계약, 신규 공장 가동처럼 한 번에 규모가 바뀌는 회사 고유 사건일 가능성이 커요"
                why.append(f"{k} 매출 계단식 증가(인수·대형 계약·증설 가능성)")
            F.append({"tag": "분기 흐름", "text": t + "."})
        # 3) 이익률: 가격·원가 vs 물량
        g0, g1 = a.get("gp"), b.get("gp")
        if g0 is not None and g1 is not None:
            m0_, m1_ = g0 / rv0 * 100, g1 / rv1 * 100
            o0_, o1_ = (op0 or 0) / rv0 * 100, (op1 or 0) / rv1 * 100
            t = f"매출총이익률 {m0_:.1f}% → {m1_:.1f}%, 영업이익률 {o0_:.1f}% → {o1_:.1f}%"
            dm = m1_ - m0_
            if gr > 0.05 and dm >= 1.5:
                t += ". 매출이 늘면서 마진도 좋아져 판매가격 인상·고마진 제품 비중 확대(믹스)나 가동률 상승 효과가 함께 있었어요"
                why.append("판가·믹스 개선으로 마진 상승")
            elif gr > 0.05 and dm <= -1.5:
                t += ". 매출은 늘었지만 마진이 낮아져, 원가 상승을 다 넘기지 못했거나 저마진 물량(유통·상품 매출) 위주로 늘었어요"
                why.append("원가 상승·저마진 물량으로 마진 하락")
            elif gr < -0.05 and dm <= -1.5:
                t += ". 매출 감소에 마진까지 낮아져, 고정비 부담(가동률 하락)이나 판가 하락이 겹쳤어요"
                why.append("물량 감소 + 판가 하락·고정비 부담")
            elif gr < -0.05 and dm >= 1.5:
                t += ". 매출은 줄었지만 마진은 좋아져, 저수익 사업 정리나 원가 하락 효과로 보여요"
            if op0 and op1 and op0 > 0 and op1 > 0 and abs(gr) >= 0.03:
                lev = (op1 / op0 - 1) / gr
                if lev >= 2:
                    t += f". 영업이익 변화율이 매출의 {lev:.1f}배라 고정비 레버리지가 크게 작용했어요"
            F.append({"tag": "이익률", "text": t + "."})
        # 4) 순이익이 영업이익과 다르게 움직였을 때
        if ni0 is not None and ni1 is not None and op0 is not None and op1 is not None:
            dn, do = ni1 - ni0, op1 - op0
            if abs(dn - do) >= max(abs(do), abs(rv1) * 0.02) and abs(dn - do) >= 1000:
                F.append({"tag": "영업외 요인", "text": f"순이익 변화({eok(ni0)}→{eok(ni1)})가 영업이익 변화({eok(op0)}→{eok(op1)})와 {eok(abs(dn - do))}만큼 달라요. 환손익·지분법 손익·자산 손상·처분이익 같은 영업 밖의 일회성 요인이 컸다는 뜻이라, 반복되는 이익으로 보면 안 돼요."})
                why.append("순이익은 영업외 일회성 요인 영향")
        # 5) 거시
        def yavg(key, yy):
            d = U.mseries(key)
            v = [d[m] for m in d if m.startswith(yy)]
            return sum(v) / len(v) if v else None
        fx0, fx1 = yavg("USDKRW", y0), yavg("USDKRW", y)
        mt = []
        if fx0 and fx1 and abs(fx1 / fx0 - 1) >= 0.04:
            mt.append(f"연평균 원/달러 {fx0:,.0f}원 → {fx1:,.0f}원({pct(fx1 / fx0 - 1)}): 달러로 파는 매출은 환율만으로 그만큼 원화 매출이 {'늘어요' if fx1 > fx0 else '줄어요'}")
        o0, o1 = yavg("BRENT", y0), yavg("BRENT", y)
        if o0 and o1 and abs(o1 / o0 - 1) >= 0.2 and ind in OIL_SENS:
            mt.append(f"연평균 브렌트유 ${o0:.0f} → ${o1:.0f}({pct(o1 / o0 - 1)}): {OIL_SENS[ind]}이고, 유가 연동 제품은 판가가 같이 움직여 매출이 커지거나 줄어요")
        if mt:
            F.append({"tag": "거시 지표", "text": ". ".join(mt) + "."})
        # 6) 사건·뉴스
        # 기저효과: 전년에 크게 줄었다가 되돌아온 해
        pa = A.get(str(int(y0) - 1)) or {}
        if op0 is not None and op1 is not None and pa.get("op") and pa["op"] > 0 and op0 < pa["op"] * 0.6 and op1 > op0:
            F.append({"tag": "기저효과", "text": f"{y0}년 영업이익이 {str(int(y0) - 1)}년 {eok(pa['op'])}에서 {eok(op0)}로 크게 줄었던 터라, 증가율이 커 보이는 데는 낮은 비교 기준(기저효과)도 작용했어요. {str(int(y0) - 1)}년 수준 대비로는 {pct(op1 / pa['op'] - 1)}예요."})
            why.append(f"{y0}년 급감 뒤 회복(기저효과)")
        if g0 is not None and g1 is not None and not any("마진" in w for w in why):
            o0_, o1_ = (op0 or 0) / rv0 * 100, (op1 or 0) / rv1 * 100
            if abs(o1_ - o0_) >= 1.5:
                why.append(f"영업이익률 {o0_:.1f}%→{o1_:.1f}%")
        dirn = (op1 - op0) if op0 is not None and op1 is not None and abs(og or 0) >= abs(gr) else (rv1 - rv0)
        ev = match_events(ind, co, f"{y}-01", f"{y}-12", dirn)
        for e in [e for e in ev if e["scope"].startswith("code:")][:3]:
            F.append({"tag": "회사 사건", "text": f"{e['d'].replace('-', '.')} {e['title']} — {e['text']}"})
            if e["dir"] == "±" or (e["dir"] == "+") == (dirn > 0):
                why.insert(0, e["title"])
        oth = [e for e in ev if not e["scope"].startswith("code:")][:3]
        for e in oth:
            F.append({"tag": "업종 사건" if e["scope"] != "all" else "거시·시장 사건", "text": f"{e['d'].replace('-', '.')} {e['title']} — {e['text']}"})
        fit = [e for e in oth if e["scope"] != "all" and f"{y}-01" <= e["d"] <= f"{y}-08" and e["dir"] in "+-" and (e["dir"] == "+") == (dirn > 0)]
        if fit:
            why.insert(0, f"{fit[0]['title']}({fit[0]['d'].replace('-', '.')})")
        for x in news_in(news, f"{y}-01", f"{y}-12", 3):
            F.append({"tag": f"뉴스 · {x['cat']}", "text": f"{x['d']} {x['t']}" + (f" — {x['read']}" if x['read'] else ""), "u": x["u"]})
        if not any(f["tag"] in ("회사 사건", "분기 흐름") and ("계단식" in f["text"] or f["tag"] == "회사 사건") for f in F) \
                and any("회사 고유" in w for w in why):
            F.append({"tag": "불확실", "text": "업종과 다르게 움직였는데 이 해의 회사 사건·뉴스를 확인하지 못해, 구체적 원인(어느 고객·제품·사업부인지)은 사업보고서 사업부문별 매출로 확인이 필요해요."})
        out[y] = {"head": head, "why": "; ".join(dict.fromkeys(why)) or "뚜렷한 단일 원인 없음", "f": F}
    return out


def news_for(data, code):
    out = []
    for fn in ("news_hist.json", "news.json"):
        d = jload(data / fn, {}) or {}
        out += (d.get("companies") or {}).get(code) or []
    rv = ((jload(data / "reviews.json", {}) or {}).get("companies") or {}).get(code) or {}
    for x in rv.get("news") or []:
        if x.get("date") and x.get("title"):
            out.append({"date": x["date"], "title": x["title"], "url": x.get("url", ""), "office": x.get("src", ""),
                        "read": x.get("read", "")})
    return out


def main():
    sel = [a for a in sys.argv[1:] if not a.startswith("-")]
    inds_all = industries()
    U = Universe(inds_all)
    now = dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    for ind, data, _cfg in industries(sel):
        res, n_ev = {}, 0
        yrs = {}
        for co in U.by_ind[ind]:
            nw = news_for(data, co.code)
            ev = build_company(U, ind, co, nw)
            yn = year_notes(U, ind, co, nw)
            if ev or yn:
                res[co.code] = ev
                yrs[co.code] = yn
                n_ev += len(ev)
        tdir = data / "turns"
        tdir.mkdir(exist_ok=True)
        for f in tdir.glob("*.json"):
            if f.stem not in res:
                f.unlink()
        for code, ev in res.items():
            body = json.dumps({"updated": now, "macro": bool(U.macro), "events": ev, "years": yrs.get(code) or {}}, ensure_ascii=False, separators=(",", ":"))
            f = tdir / f"{code}.json"
            old = f.read_text("utf-8") if f.exists() else ""
            if re.sub(r'"updated":"[^"]*",', "", old) != re.sub(r'"updated":"[^"]*",', "", body):
                f.write_text(body, "utf-8")
        out = {"updated": now, "macro": bool(U.macro), "method": (
            "변곡점: ① 직전 1년 이익(4분기 합)과 주가가 ±5%·±10% 넘게 엇갈린 분기(차트의 초록·빨강 띠) ② 월말 종가 기준 30% 넘게 되돌린 고점·저점. "
            "해설은 이익×PER 분해, 자기 역사 대비 PER 위치, 시장·업종·사업군 대비 움직임, 실적 발표 달 업종 대비 반응, 사후 1년 이익, 원/달러·금리·유가, "
            "시장·산업·회사 사건 연표, 종목 뉴스를 매일 자동으로 맞춰 만들어요."),
               "counts": {k: len(v) for k, v in res.items()}}
        (data / "turns.json").write_text(json.dumps(out, ensure_ascii=False, indent=0), "utf-8")
        sz = sum(f.stat().st_size for f in tdir.glob("*.json")) / 1024
        print(f"{ind}: {len(res)}개사, 변곡점 {n_ev}개, 회사별 파일 합계 {sz:.0f}KB")


if __name__ == "__main__":
    main()
