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
from research import NOTES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
KST = dt.timezone(dt.timedelta(hours=9))
TH_E, TH_P = 0.05, 0.10   # finchart.js 와 같은 문턱
ZZ = 0.30                  # 고점·저점 판정: 30% 넘게 되돌리면 변곡점
IND_NAME = {"cosmetics": "화장품", "semi": "반도체", "chem": "화학·정유", "battery": "2차전지", "apparel": "의류",
            "food": "음식료", "logistics": "물류·운송"}
# 업종별 환율·유가 민감도(문장용): +1 원화 약세가 이익에 유리, -1 불리, 0 혼재
FX_SENS = {"cosmetics": 1, "semi": 1, "chem": 0, "battery": 1, "apparel": 1, "food": -1, "logistics": 0}
OIL_SENS = {"chem": "정유는 재고평가이익·정제마진, 석유화학은 원가 부담", "logistics": "항공·해운 연료비 부담",
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

    def earn(self, n, f):
        """n분기까지 1년 실적: 4분기 합, 분기 자료가 없으면 그 직전 연간 실적. (값, 라벨)"""
        for k in range(3):  # 아직 발표 전이면 직전 분기까지
            v = self.ttm(n - k, f)
            if v is not None:
                return v, qk(n - k)
        y = str(n // 4 if n % 4 == 3 else n // 4 - 1)
        a = (self.A.get(y) or {}).get(f)
        return (a, f"{y}년") if a is not None else (None, None)

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
                    "cat": cat or "해석", "read": x.get("read", ""), "imp": x.get("impact", "")})
        if len(out) >= limit:
            break
    out.sort(key=lambda z: z["d"])
    return out



# ---------------------------------------------------------------- 리포트·뉴스 제목에서 실적 기대 대비·테마 읽기
BEAT = re.compile(r"서프라이즈|깜짝|상회|웃돌|웃돈|기대 ?이상|호실적|사상 ?최대|역대 ?최대|최대 ?실적|어닝 ?비트|모멘텀 폭격|이익 급증|레버리지")
MISS = re.compile(r"쇼크|하회|밑돌|밑돈|기대 ?이하|기대에 못|부진|실망|어닝 ?미스|컨센서스 ?미달|아쉬운|눈높이 ?하향|목표가 ?하향|적자 ?전환|적자전환")
EARN_T = re.compile(r"실적|분기|영업이익|영업익|순이익|매출|어닝|[1-4]Q|Review|리뷰|잠정|서프라이즈|쇼크|컨센서스")
THEME = re.compile(r"테마|관련주|수혜주|대장주|정치인|대선|총선|지방선거|선거|후보|상한가")


def _d(x):
    return x.get("date") or x.get("d") or ""


def earn_verdict(items, n):
    """n분기 실적 발표 무렵(분기 끝 +20일~+75일, 4분기는 +95일) 리포트·기사 제목의 평가. (부호, 대표 항목, 근거 수)"""
    y, m = int(qend(n)[:4]), int(qend(n)[5:7])
    base = dt.date(y, m, 28)
    lo = (base + dt.timedelta(days=20)).isoformat()
    hi = (base + dt.timedelta(days=95 if n % 4 == 3 else 75)).isoformat()
    b, mm = [], []
    for x in items:
        d, t = _d(x), x.get("title", "")
        if not (lo <= d <= hi) or not EARN_T.search(t):
            continue
        if BEAT.search(t) and not MISS.search(t):
            b.append(x)
        elif MISS.search(t) and not BEAT.search(t):
            mm.append(x)
    if len(b) == len(mm):
        return 0, None, 0
    win = b if len(b) > len(mm) else mm
    win.sort(key=lambda x: (0 if x.get("kind") == "research" else 1, _d(x)))
    return (1 if win is b else -1), win[0], len(win)


def theme_hits(items, m0, m1):
    lo, hi = madd(m0, -1) + "-01", m1 + "-31"
    out = [x for x in items if lo <= _d(x) <= hi and THEME.search(x.get("title", "")) and re.search(r"테마|관련주|수혜주|대장주", x.get("title", ""))]
    seen, res = set(), []
    for x in sorted(out, key=_d):
        k = re.sub(r"\W", "", x["title"])[:20]
        if k not in seen:
            seen.add(k)
            res.append(x)
    return res


def notes_in(co, m0, m1):
    lo, hi = madd(m0, -1) + "-01", m1 + "-31"
    return [n for n in NOTES if n["code"] == co.code and lo <= n["d"] <= hi]

# ---------------------------------------------------------------- 해설 만들기: 6개 요인
CATS = [("earn", "실적"), ("cycle", "업황"), ("trend", "트렌드"), ("news", "뉴스"), ("val", "밸류에이션"), ("cat", "촉매제"), ("macro", "거시·시장")]
CNAME = dict(CATS)


def _sg(x, th=0.0):
    return 0 if x is None or abs(x) < th else (1 if x > 0 else -1)


def josa(w, a="은", b="는"):
    c = (w or " ").rstrip(")")[-1:]
    return a if "가" <= c <= "힣" and (ord(c) - 0xAC00) % 28 else b


def _evline(e):
    return f"{e['d'].replace('-', '.')} {e['title']}: {e['text']}"


def pick_events(ind, co, m0, m1, r):
    """구간을 설명할 사건만 고른다.
    · 날짜가 분명한 사건(촉매제·거시)은 구간 시작 1개월 전~구간 끝 사이에 일어난 것만.
    · 업황·트렌드처럼 이어지는 배경은 구간 전에 시작했어도 구간과 겹치고 주가 방향과 맞을 때만.
    · 방향이 엇갈리는(±) 시장 사건은 다른 근거가 있으면 뺀다. 변곡점 원인은 대개 시작점 근처라 시작에 가까운 순으로."""
    lo, hi = madd(m0, -1), m1
    up = (r or 0) > 0
    out = []
    for e in EVENTS:
        d, end = e["d"], e.get("end", e["d"])
        if end < lo or d > hi:
            continue
        sc = e["scope"]
        ok = sc == "all" or sc == f"ind:{ind}" or (sc.startswith("code:") and co.code in sc[5:].split(","))
        if not ok or (e.get("groups") and co.group not in e["groups"]) or (e.get("not_groups") and co.group in e["not_groups"]):
            continue
        inside = d >= lo
        match = e["dir"] == "±" or (e["dir"] == "+") == up
        if not inside and not (e["cat"] in ("cycle", "trend") and match and e["dir"] != "±"):
            continue
        out.append(dict(e, _in=inside, _match=match))
    def dist(e):
        y, m = int(e["d"][:4]), int(e["d"][5:7])
        return abs((y - int(m0[:4])) * 12 + m - int(m0[5:7]))
    out.sort(key=lambda e: (not e["_match"], e["scope"] == "all", dist(e)))
    return out


def describe(U, ind, co, m0, m1, news, qq=None):
    r = co.ret(m0, m1)
    up = (r or 0) > 0
    iname = IND_NAME.get(ind, ind)
    C = {k: {"k": k, "s": 0, "w": 0.0, "t": "", "b": "", "ev": []} for k, _ in CATS}
    ev = pick_events(ind, co, m0, m1, r)
    by = lambda c: [e for e in ev if e["cat"] == c]

    # ---- 시장 위치(코스피·업종·사업군)
    rm, mname = U.index_ret(co.market, m0, m1)
    if rm is None:
        rm, nn = U.med(U.all, m0, m1, co.code)
        mname = f"7개 대시보드 전체 {nn}개사 중앙값" if rm is not None else None
    ri, ni_ = U.med(U.by_ind.get(ind, []), m0, m1, co.code)
    grp = [c for c in U.by_ind.get(ind, []) if c.group == co.group]
    rg, ng = U.med(grp, m0, m1, co.code) if co.group else (None, 0)
    base = rg if rg is not None and ng >= 3 else ri
    resid = (1 + r) / (1 + base) - 1 if r is not None and base is not None else None
    ind_part = ((1 + base) / (1 + rm) - 1) if base is not None and rm is not None else base
    # 같이 움직였나: 회사 움직임 중 업종(사업군) 공통 몫. 업종이 따라 움직이지 않았으면 시장·거시로 설명하지 않는다.
    la = math.log1p(r) if r is not None and r > -1 else None
    lb = math.log1p(base) if base is not None and base > -1 else None
    comove = (max(0.0, min(1.0, lb / la)) if la and lb is not None and la * lb > 0 else 0.0) if la else 0.0
    own = (la - lb) if la is not None and lb is not None else None   # 회사 고유 몫(로그)

    # ---- 거시·시장
    M = C["macro"]
    bits = []
    if rm is not None:
        bits.append(f"같은 기간 {mname}{josa(mname)} {pct(rm)} 움직였어요" + (
            f". 하지만 {iname} 업종 중앙값은 {pct(base)}로 이 회사와 다르게 움직여, 시장 흐름이 이 회사 주가를 설명하는 몫은 작아요" if comove < 0.4 and base is not None else ""))
    fx0, fx1 = U.mval("USDKRW", m0), U.mval("USDKRW", m1)
    if fx0 and fx1 and abs(fx1 / fx0 - 1) >= 0.05:
        w_ = fx1 > fx0
        s_ = FX_SENS.get(ind, 0)
        eff = ("수출 비중이 큰 회사의 원화 환산 이익엔 플러스" if s_ > 0 else "원재료 수입 비용엔 부담" if s_ < 0 else "회사별로 득실이 갈리는 변화") if w_ else \
              ("수출 비중이 큰 회사의 이익엔 마이너스" if s_ > 0 else "원재료 수입 비용엔 도움" if s_ < 0 else "회사별로 득실이 갈리는 변화")
        bits.append(f"원/달러는 {fx0:,.0f}원에서 {fx1:,.0f}원으로 {'올라(원화 약세)' if w_ else '내려(원화 강세)'} {eff}였고, 원화 {'약세 땐 외국인 자금이 빠지기' if w_ else '강세 땐 외국인 자금이 들어오기'} 쉬워요")
    u0, u1 = U.mval("US10Y", m0), U.mval("US10Y", m1)
    if u0 is not None and u1 is not None and abs(u1 - u0) >= 0.5:
        bits.append(f"미국 10년 금리가 {u0:.2f}%에서 {u1:.2f}%로 {'올라 성장주 배수를 누르는' if u1 > u0 else '내려 성장주 배수를 받쳐 주는'} 환경이었어요")
    o0, o1 = U.mval("BRENT", m0), U.mval("BRENT", m1)
    if o0 and o1 and abs(o1 / o0 - 1) >= 0.25 and ind in OIL_SENS:
        bits.append(f"브렌트유가 ${o0:.0f}에서 ${o1:.0f}로 {pct(o1 / o0 - 1)} 움직였는데, 이는 {OIL_SENS[ind]} 요인이에요")
    mev = [e for e in by("macro") if e["_in"] and (e["_match"] or e["dir"] == "±") and (comove >= 0.4 or e["scope"] != "all")]
    mev = [e for e in mev if e["dir"] != "±"][:2] or mev[:1]
    M["ev"] = [_evline(e) for e in mev]
    M["t"] = ". ".join(bits) + ("." if bits else "")
    if rm is not None and abs(rm) >= 0.05:
        M["s"], M["w"] = _sg(rm), 0.8 * abs(math.log1p(rm)) * (0.2 + 0.8 * comove)
        M["b"] = f"시장 전체 {'상승' if rm > 0 else '하락'}({mname.split('(')[0].split(' ')[0] if '대시보드' not in mname else '전체 중앙값'} {pct(rm)}{', ' + mev[0]['title'] if mev and mev[0]['dir'] in '+-' and (mev[0]['dir'] == '+') == (rm > 0) else ''})"
    elif mev:
        M["b"] = mev[0]["title"]

    # ---- 업황: 업종 주가·업종 매출·이 회사 이익 + 업황 사건
    Y = C["cycle"]
    ek = co.ek
    q0, q1 = qq or (reported_q(m0), reported_q(m1))
    e0, l0 = co.earn(q0, ek) if ek else (None, None)
    e1, l1 = co.earn(q1, ek) if ek else (None, None)
    en = {"op": "영업이익", "ni": "순이익", "rev": "매출"}.get(ek, "이익")
    de = chg(e0, e1) if e0 is not None and e1 is not None and q1 > q0 and l0 != l1 else None
    rv = []
    for c in U.by_ind.get(ind, []):
        a, b = c.earn(q0, "rev")[0], c.earn(q1, "rev")[0]
        if a and b and a > 0 and q1 > q0:
            rv.append(b / a - 1)
    rvm = stx.median(rv) if len(rv) >= 5 else None
    bits = []
    if ri is not None:
        bits.append(f"{iname} 업종 주가는 중앙값 {pct(ri)}" + (f"(시장 대비 {pct(ind_part)})" if rm is not None and ind_part is not None else ""))
    if rvm is not None:
        phase = "확장" if rvm >= 0.1 else "회복" if rvm >= 0.03 else "위축" if rvm <= -0.05 else "정체"
        bits.append(f"업종 회사들의 매출(4분기 합)은 중앙값 {pct(rvm)}로 업황이 {phase} 국면이었어요")
    E = C["earn"]
    ebits = []
    if de is not None:
        ebits.append(f"이 회사 {en}(1년치)은 {l0} {eok(e0)} → {l1} {eok(e1)}" + (f"({pct(de)})" if e0 > 0 and e1 > 0 else " (흑자 전환)" if e0 <= 0 < e1 else " (적자 전환)" if e1 <= 0 < e0 else ""))
    esc_ = ((0.9 * math.log1p(de) if e0 > 0 and e1 > 0 else 0.7 * _sg(de)) if de is not None and abs(de) >= 0.1 else 0)
    yev = [e for e in by("cycle") if comove >= 0.3 or e["scope"].startswith("code:")][:2]
    Y["ev"] = [_evline(e) for e in yev]
    Y["t"] = ". ".join(bits) + ("." if bits else "")
    # 업황 점수: 업종 매출 흐름 + 이 회사 이익 흐름 + 업종 주가(시장 몫은 거시에서 따로) + 업황 사건
    clip = lambda x, a=1.0: max(-a, min(a, x))
    kk = 0.3 + 0.7 * comove   # 업종 공통 몫이 작으면 업황 설명력도 작다
    sc_ = (0.8 * kk * clip(math.log1p(rvm), 0.8) if rvm is not None and abs(rvm) >= 0.03 else 0) \
        + (0.3 * kk * clip(math.log1p(ind_part), 0.8) if ind_part is not None and abs(ind_part) >= 0.1 else 0)
    sc_ += sum((0.25 if e["dir"] == "+" else -0.25) for e in yev if e["dir"] in "+-")
    Y["s"], Y["w"] = _sg(sc_, 0.05), abs(sc_)
    if Y["s"]:
        good = Y["s"] > 0
        ev_t = yev[0]["title"] + ", " if yev and yev[0]["_match"] and yev[0]["dir"] != "±" else ""
        if rvm is not None and _sg(rvm, 0.03) == Y["s"]:
            Y["b"] = f"{iname} 업황 {'호조' if good else '부진'}({ev_t}업종 매출 {pct(rvm)})"
        else:
            Y["b"] = f"{iname} 업황 {'호조' if good else '부진'}({ev_t.rstrip(', ') or '업종 주가 ' + pct(ri)})"

    # ---- 트렌드: 구조적 변화·테마
    T = C["trend"]
    tev = by("trend")[:2]
    T["ev"] = [_evline(e) for e in tev]
    months = (int(m1[:4]) - int(m0[:4])) * 12 + int(m1[5:7]) - int(m0[5:7])
    if tev:
        s_ = sum((1 if e["dir"] == "+" else -1) for e in tev if e["dir"] in "+-")
        T["s"], T["w"] = _sg(s_), 0.35 * len([e for e in tev if e["_match"]]) + (0.3 if any(e["scope"].startswith("code:") for e in tev) else 0)
        T["b"] = tev[0]["title"]
        T["t"] = "주가에 영향을 준 구조적 흐름(일시적 이벤트가 아닌, 수요·경쟁 구도의 변화)이에요."
    elif resid is not None and abs(resid) >= 0.5 and months >= 12:
        T["t"] = (f"업종 대비 {pct(resid)}의 초과 {'상승' if resid > 0 else '하락'}이 {months}개월 이어졌어요. 일회성 사건보다는 제품·시장 지위 변화 같은 "
                  "지속적인 흐름이 있었을 가능성이 높지만, 연표·뉴스에서 확인된 트렌드는 없어 추정이에요.")
        T["s"], T["w"], T["b"] = _sg(resid), 0.1, f"업종 대비 {months}개월 초과 {'상승' if resid > 0 else '하락'}(원인 추정)"

    # ---- 뉴스
    N = C["news"]
    nw = news_in(news, m0, m1)
    imp = {"pos": 1, "neg": -1}
    pos = sum(imp.get(x.get("imp"), 0) for x in nw)
    N["ev"] = [f"{x['d']} [{x['cat']}] {x['t']}" + (f": {x['read']}" if x["read"] else "") for x in nw]
    N["u"] = [x["u"] for x in nw]
    if nw:
        key = [x for x in nw if x["cat"] in ("실적", "수주·계약", "자본·지배구조", "규제·정책")] or nw
        N["s"], N["w"] = _sg(pos), min(0.35, 0.1 * len(nw)) if pos else 0.1
        N["b"] = f"'{key[-1]['t'][:34]}' 등 회사 뉴스"
        N["t"] = f"이 시기 회사 관련 기사 {len(nw)}건을 골랐어요" + (f". 해석상 {'긍정' if pos > 0 else '부정'} 기사가 더 많았어요" if pos else "") + "."

    # ---- 밸류에이션
    V = C["val"]
    if qq:
        def _per(m, q):
            ni, p = co.ttm(q, "ni"), co.px.get(m)
            return p * co.shares / (ni * 1e6) if p and co.shares and ni and ni > 0 else None
        per0, per1 = _per(m0, q0), _per(m1, q1)
    else:
        per0, per1 = co.per_at(m0), co.per_at(m1)
    hist = sorted(x for x in (co.per_at(m) for m in co.months) if x and 0 < x < 300)
    rank = sum(1 for x in hist if x <= per0) / len(hist) if per0 and len(hist) >= 24 else None
    med = stx.median(hist) if len(hist) >= 24 else None
    bits = []
    if per0 and per1:
        dper = per1 / per0 - 1
        bits.append(f"PER이 {per0:.1f}배에서 {per1:.1f}배로 {pct(dper)} {'높아졌어요(시장이 더 비싸게 쳐 줌)' if dper > 0 else '낮아졌어요(시장이 덜 쳐 줌)'}")
        if de is not None and e0 and e1 and e0 > 0 and e1 > 0 and r is not None:
            le, lp = abs(math.log1p(de)), abs(math.log1p(dper))
            sh = lp / (le + lp) if le + lp > 0 else 0
            bits.append(f"주가 변화 중 이익 몫이 {100 - sh * 100:.0f}%, 배수(PER) 몫이 {sh * 100:.0f}%예요")
        V["s"], V["w"] = _sg(dper, 0.1), abs(math.log1p(dper))
        V["b"] = f"PER {per0:.0f}배→{per1:.0f}배 {'재평가' if dper > 0 else '축소'}"
    if rank is not None:
        lvl = "비싼 편(상위 20%)" if rank >= 0.8 else "싼 편(하위 20%)" if rank <= 0.2 else "중간 수준"
        tail = ""
        if rank >= 0.8 and not up:
            tail = ". 기대가 많이 들어간 가격이라 작은 실망에도 배수가 빠지기 쉬운 자리였어요"
        elif rank <= 0.2 and up:
            tail = ". 비관이 많이 반영된 가격이라 작은 개선에도 배수가 회복되기 쉬운 자리였어요"
        elif rank >= 0.8 and up:
            tail = ". 이미 비싼 가격에서 더 오른 것이라 실적이 기대를 따라와야 유지되는 구간이었어요"
        elif rank <= 0.2 and not up:
            tail = ". 이미 싼 가격에서 더 빠진 건 시장이 이익 자체가 더 줄 것으로 봤다는 뜻이에요"
        bits.insert(0, f"출발점({kor_m(m0)}) PER {per0:.1f}배는 이 회사 {len(hist) // 12}년여 PER 중앙값 {med:.1f}배 대비 {lvl}이었어요{tail}")
        if (rank >= 0.8 and not up) or (rank <= 0.2 and up):
            V["w"] += 0.2
            V["s"] = V["s"] or (1 if up else -1)
    if not per0 or not per1:
        if ek and ((co.ni_ttm_at(m0)[0] or 0) <= 0 or (co.ni_ttm_at(m1)[0] or 0) <= 0):
            bits.append("순이익이 적자인 시기가 있어 PER을 쓸 수 없어요. 이익보다 앞날의 기대·우려로 움직인 구간이에요")
    V["t"] = ". ".join(bits) + ("." if bits else "") + (" (PER은 현재 주식 수로 계산한 추정치)" if bits and per0 else "")

    # ---- 촉매제: 실적 발표(시장 기대 대비)·IR·테마·회사 공시
    K = C["cat"]
    E["ev"], E["u"], ebest, eitems = [], [], None, []
    if ek:
        rx = []
        nmon = {nt["d"][:7] for nt in notes_in(co, m0, m1) if nt["cat"] in ("cat", "earn")}
        for n in range(q0 + 1, q1 + 2):
            am, pm = madd(qend(n), 2), madd(qend(n), 1)
            if am < m0 or am > madd(m1, 0) or am not in co.px or pm not in co.px:
                continue
            v, pv = co.val(n, "op"), co.val(n - 4, "op")
            if v is None or am in nmon or pm in nmon:
                continue
            mr = co.px[am] / co.px[pm] - 1
            peers = [x for x in (c.ret(pm, am) for c in U.by_ind.get(ind, []) if c.code != co.code) if x is not None]
            ex = mr - stx.median(peers) if len(peers) >= 3 else mr
            vs, vx, vn = earn_verdict(news, n)
            score = max(-0.6, min(0.6, ex)) * 1.5 + 0.45 * vs
            rx.append((abs(score), n, v, pv, ex, am, vs, vx, vn, score))
        rx.sort(key=lambda z: -z[0])
        for _, n, v, pv, ex, am, vs, vx, vn, score in rx[:3]:
            if abs(ex) < 0.08 and not vs:
                continue
            yt = (f"전년 대비 {pct(chg(pv, v))}" if pv and pv > 0 and v > 0 else "흑자 전환" if pv is not None and pv <= 0 < v
                  else "적자 전환" if pv is not None and v <= 0 < pv else "적자 지속" if v <= 0 else "")
            t = f"{qk(n)} 실적(영업이익 {eok(v)}, {yt})"
            if vs:
                kw = (BEAT if vs > 0 else MISS).search(vx["title"]).group(0)
                t += (f"은 증권가·언론이 '{kw}'로 평가했어요({vx.get('office') or ''} {_d(vx)} '{vx['title'][:48]}'"
                      + (f" 등 {vn}건" if vn > 1 else "") + ")")
                t += f". 발표 달({kor_m(am)}) 주가는 업종보다 {pp(ex)} " + (
                    "더 올라 기대를 웃돈 실적이 주가를 끌어올렸어요" if ex > 0.03 and vs > 0 else
                    "더 빠져 기대에 못 미친 실적이 주가를 끌어내렸어요" if ex < -0.03 and vs < 0 else
                    "움직였는데, 실적 평가와 반대여서 '좋은 소식이 이미 가격에 반영(재료 소멸)'됐거나 다른 요인이 더 컸던 것으로 보여요" if abs(ex) >= 0.03 else "움직여 반응은 크지 않았어요")
                E["ev"].append(f"{_d(vx)} [{'증권사 리포트' if vx.get('kind') == 'research' else '기사'}] {vx['title']}" + (f" ({vx.get('office')})" if vx.get("office") else ""))
                E["u"].append(vx.get("url") or None)
            else:
                t += (f" 발표 무렵인 {kor_m(am)} 주가가 업종보다 {pp(ex)} {'더 올라 시장 기대를 웃돈 것으로' if ex > 0 else '더 빠져 기대에 못 미친 것으로'} 보여요"
                      "(증권가 평가 기사를 찾지 못해 발표 달 주가 반응으로 추정)")
            ebits.append(t)
            esc_ += score
            eitems.append((score, f"{qk(n)} 실적 {'기대 상회' if vs > 0 else '기대 하회(어닝 쇼크)' if vs < 0 else ('서프라이즈 추정' if ex > 0 else '실망 추정')}"
                           + f"(발표 달 업종 대비 {pp(ex)})"))
    E["t"] = ". ".join(ebits) + ("." if ebits else "")
    E["s"], E["w"] = _sg(esc_, 0.05), abs(esc_)
    ebest = next((b_ for sc0, b_ in eitems if _sg(sc0) == E["s"]), None)
    if E["s"]:
        co_t = (f"{en} {pct(de) if e0 > 0 and e1 > 0 else '흑자 전환' if e1 > 0 else '적자 전환'}" if de is not None and e0 and e1 else "")
        E["b"] = ebest or ""
        if co_t and (not ebest or _sg(de or 0) == E["s"]):
            E["b"] = (ebest + ", " if ebest else "") + f"1년 {co_t}"
        E["b"] = E["b"] or f"실적 {'개선' if E['s'] > 0 else '악화'}"
    bits, sc_, best, K["u"], K["ev"] = [], 0.0, None, [], []
    # 테마
    th = theme_hits(news, m0, m1)
    if th:
        sgn = 1 if up else -1
        bits.append(f"이 시기 '{th[0]['title'][:50]}'({_d(th[0])}) 등 테마·관련주 기사가 {len(th)}건 나왔어요. 테마 매매는 실적과 무관하게 주가를 움직이고, 재료가 사라지면 되돌려지기 쉬워요" if up else
                    f"'{th[0]['title'][:50]}'({_d(th[0])})처럼 테마로 오른 주가였어요. 테마는 회사의 이익을 바꾸지 않아, 재료가 사라지자 실적 수준으로 되돌아갔어요")
        sc_ += 0.4 * sgn
        best = best or f"테마 매매({th[0]['title'][:24]})"
        for x in th[:2]:
            K["ev"].append(f"{_d(x)} [테마] {x['title']}" + (f" ({x.get('office')})" if x.get("office") else ""))
            K["u"].append(x.get("url") or None)
    months_ = (int(m1[:4]) - int(m0[:4])) * 12 + int(m1[5:7]) - int(m0[5:7])
    if r is not None and r >= 0.8 and months_ <= 9 and own is not None and own >= 0.45 and not (de is not None and de >= 0.2):
        bits.append(f"이익 개선 없이 {months_}개월 만에 {pct(r)} 오르며 업종을 크게 앞질렀어요. 실적이 아닌 테마·수급(단기 매매)으로 오른 급등일 가능성이 높아요")
        sc_ += 0.3
        best = best or "실적 뒷받침 없는 급등(테마·수급성)"
    kev = [e for e in by("catalyst") if e["_in"]][:3]
    K["ev"] += [_evline(e) for e in kev]
    K["u"] += [None] * len(kev)
    for e in kev:
        if e["dir"] in "+-":
            sc_ += (0.6 if e["scope"].startswith("code:") else 0.35 * (0.3 + 0.7 * comove)) * (1 if e["dir"] == "+" else -1)
    K["t"] = ". ".join(bits) + ("." if bits else "")
    K["s"], K["w"] = _sg(sc_, 0.05), abs(sc_)
    if K["s"]:
        cand = [e for e in kev if e["_match"] and e["dir"] != "±"]
        K["b"] = cand[0]["title"] if cand and (cand[0]["scope"].startswith("code:") or not best) else (best or (kev[0]["title"] if kev else ""))

    # ---- 직접 확인한 원인(scripts/turns/research.py): 해당 요인 맨 앞에, 가장 큰 무게로
    for nt in notes_in(co, m0, m1):
        X = C[nt["cat"]]
        sg = 1 if nt["dir"] == "+" else -1
        u = list(X.get("u") or [])
        u += [None] * (len(X["ev"]) - len(u))
        X["ev"] = [f"✔ {nt['d'].replace('-', '.')} {nt['title']}: {nt['text']}" + (f" ({nt['office']})" if nt["office"] else "")] + X["ev"]
        X["u"] = [nt["url"] or None] + u
        X.setdefault("vn", []).append((sg, nt))
    d0_ = 1 if up else -1
    has_note = False
    for X in C.values():
        if not X.get("vn"):
            continue
        has_note = True
        same = [nt for sg, nt in X["vn"] if sg == d0_]
        X["s"] = d0_ if same else -d0_
        X["w"] = max(X["w"], 0.9 + 0.2 * len(same)) if same else max(X["w"], 0.5)
        # 주가 방향과 같은 원인을 앞에(최근 것부터), 반대 방향은 맥락으로 뒤에
        pairs = list(zip(X["ev"], X["u"]))
        nn = len(X["vn"])
        notes_p, rest = pairs[:nn][::-1], pairs[nn:]
        key = lambda p_: 0 if any(p_[0].startswith(f"✔ {nt['d'].replace('-', '.')} {nt['title']}") for nt in same) else 1
        notes_p.sort(key=key)
        X["ev"], X["u"] = [p_[0] for p_ in notes_p + rest], [p_[1] for p_ in notes_p + rest]
        lead = sorted(same, key=lambda nt: nt["d"], reverse=not up)[:2] or [nt for _, nt in X["vn"]][:1]
        X["b"] = " · ".join(nt["title"] for nt in lead)
        X["t"] = ("기사 원문으로 확인한 원인이에요(✔). " + X["t"]).strip()
        X["ok"] = 1
        del X["vn"]
    if has_note and not C["trend"]["ev"]:
        C["trend"].update({"s": 0, "w": 0.0, "b": "", "t": ""})

    # ---- 사후 확인
    after = ""
    d2 = None
    if ek and e1 is not None:
        if l1 == qk(q1 if l1 == qk(q1) else qn(l1) if re.fullmatch(r"\d{4}Q[1-4]", l1 or "") else 0):
            e2, l2 = co.ttm(qn(l1) + 4, ek), qk(qn(l1) + 4)
        elif l1 and l1.endswith("년"):
            l2 = f"{int(l1[:4]) + 1}년"
            e2 = (co.A.get(l2[:4]) or {}).get(ek)
        else:
            e2, l2 = None, None
        if e2 is not None and r is not None:
            d2 = chg(e1, e2)
            r2 = co.ret(m1, madd(m1, 12)) if madd(m1, 12) in co.px else None
            after = f"구간 뒤 1년({l1}→{l2}) {en}은 {pct(d2) if e1 > 0 and e2 > 0 else eok(e1) + '→' + eok(e2)}" + (f", 주가는 {pct(r2)}" if r2 is not None else "")
            if abs(d2 or 0) >= 0.1:
                after += ". 주가가 이익 변화를 미리 반영한 셈이에요." if (r > 0) == (d2 > 0) else ". 이후 이익은 반대로 움직여, 이 구간의 주가 움직임은 결과적으로 과했던 셈이에요."
            else:
                after += ". 이후 이익은 크게 달라지지 않았어요."

    # ---- 요약(헤드라인)
    d0 = 1 if up else -1
    drive = sorted([c for c in C.values() if c["s"] == d0 and c["w"] >= 0.08 and c["b"] and not (c["k"] in ("macro", "cycle") and comove < 0.4)], key=lambda c: -c["w"])
    oppo = sorted([c for c in C.values() if c["s"] == -d0 and c["w"] >= 0.12 and c["b"]], key=lambda c: -c["w"])
    for c in C.values():
        c["lvl"] = 0 if not c["s"] else 3 if c["w"] >= 0.45 else 2 if c["w"] >= 0.2 else 1
    if drive:
        lead = ", ".join(f"{'①②'[i]} {CNAME[c['k']]} — {c['b']}" for i, c in enumerate(drive[:2]))
        head = f"{'상승' if up else '하락'}을 이끈 핵심 요인: {lead}."
        cy = C["earn"]
        if cy["s"] == -d0 and d2 is not None and _sg(d2, 0.1) == d0:
            dtx = pct(d2) if e1 > 0 and e2 > 0 else f"{eok(e1)}→{eok(e2)}"
            head += (f" 당시 업황·실적은 아직 좋았지만, 시장은 다가올 이익 감소를 먼저 반영했어요(이후 1년 {en} {dtx})." if not up else
                     f" 당시 업황·실적은 아직 나빴지만, 시장은 회복을 먼저 반영했어요(이후 1년 {en} {dtx}).")
            oppo = [c for c in oppo if c["k"] != "earn"]
        if own is not None and abs(own) >= 0.2 and comove < 0.5 and base is not None:
            head += (f" 같은 기간 {iname} 업종 중앙값은 {pct(base)}" + (f", {mname.split('(')[0]}{josa(mname.split('(')[0])} {pct(rm)}" if rm is not None and '대시보드' not in (mname or '') else "")
                     + f"였어요. 업종과 {'반대로' if (base or 0) * (r or 0) < 0 else '크게 다르게'} 움직였으니 이 {'상승' if up else '하락'}은 시장보다 회사 고유 요인의 몫이 커요.")
            if not any(c["k"] in ("earn", "cat", "news") or c.get("ok") for c in drive[:2]):
                head += " 다만 이 시기 회사 고유 원인(실적 발표 반응·공시·뉴스)을 자료에서 확인하지 못해 원인 연결은 불확실해요."
        if oppo:
            head += f" 반대로 작용한 요인: {CNAME[oppo[0]['k']]} — {oppo[0]['b']} ({'부담이었지만 흐름을 바꾸진 못함' if up else '버팀목이었지만 하락을 막진 못함'})."
    else:
        head = "뚜렷하게 주가를 움직인 요인을 찾지 못했어요."
    unc = None
    company_ev = C["cat"]["ev"] or C["news"]["ev"] or C["trend"]["ev"]
    if resid is not None and abs(resid) >= 0.2 and not company_ev and not C["cat"]["t"]:
        unc = (f"업종·시장 대비 상대 성과가 {pct(resid)}로 회사 고유 요인이 컸는데, 이 시기 회사 사건·뉴스·실적 반응에서 원인을 확인하지 못했어요. "
               "수급(대주주·기관 매매, 오버행)이나 테마성 매매일 수 있어 원인은 불확실해요.")
    elif not drive:
        unc = "어느 요인도 뚜렷하지 않아 원인 연결은 추정이에요."
    for c in C.values():
        if not c["t"] and not c["ev"]:
            c["t"] = "이 시기에 이 요인으로 볼 근거를 찾지 못했어요."
            c["none"] = True
    cats = [{kk: v for kk, v in C[k].items() if kk != "w" and v not in ("", [], None)} | {"w": round(C[k]["w"], 2)} for k, _ in CATS]
    return {"sum": head, "cats": cats, "after": after, "unc": unc, "drive": [c["k"] for c in drive[:2]]}


def look_text(t, drive):
    nm = "·".join(CNAME[k] for k in drive) or "주된 요인"
    if t in ("up", "warn"):
        return f"이 상승을 이끈 {nm} 요인이 지금도 살아 있는지가 다음 흐름을 가르는 열쇠예요. 요인이 꺾이면(예: 업황 정점, 배수 과열, 촉매 소멸) 되돌림이 올 수 있어요."
    return f"이 하락을 부른 {nm} 요인이 이익 자체를 훼손한 것인지, 기대(배수)만 낮춘 것인지에 따라 회복 경로가 달라져요. 그 요인이 풀리는 신호를 지켜보세요."


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
        D = describe(U, ind, co, m0, m1, news, (b["q0"] - 4, b["q1"]))
        de = chg(e0, e1)
        head = f"{en}(4분기 합) {pct(de) if e0 and e1 and e0 > 0 and e1 > 0 else eok(e0) + '→' + eok(e1)}인데 주가 {pct(r)}"
        lbl = "실적↑ 주가↓" if b["t"] == "opp" else "실적↓ 주가↑"
        events.append(dict({"kind": "band", "t": b["t"], "q0": qk(b["q0"]), "q1": qk(b["q1"]), "m0": m0, "m1": m1,
                            "title": f"{qk(b['q0'])}{'' if b['q0'] == b['q1'] else '~' + qk(b['q1'])} {lbl}", "head": head,
                            "look": look_text("warn" if b["t"] == "warn" else "down", D["drive"])}, **D))
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
        D = describe(U, ind, co, m0, m1, news)
        p0, p1 = co.px[m0], co.px[m1]
        start = "데이터 시작" if g.get("from_start") else ("고점" if g["t"] == "down" else "저점")
        months = (int(m1[:4]) - int(m0[:4])) * 12 + int(m1[5:7]) - int(m0[5:7])
        head = f"{kor_m(m0)} {start} {p0:,.0f}원 → {kor_m(m1)}{' 현재' if g['open'] else ''} {p1:,.0f}원({pct(r)}, {months}개월)"
        events.append(dict({"kind": "leg", "t": g["t"], "m0": m0, "m1": m1, "open": g["open"], "pivot": not g.get("from_start"),
                            "title": f"{kor_m(m0)}~{kor_m(m1)}{' (진행 중)' if g['open'] else ''} {'상승' if g['t'] == 'up' else '하락'} {pct(r)}",
                            "head": head, "look": look_text(g["t"], D["drive"])}, **D))
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
    for x in ((jload(data / "research_hist.json", {}) or {}).get("companies") or {}).get(code) or []:
        out.append(dict(x, kind="research"))
    rv = ((jload(data / "reviews.json", {}) or {}).get("companies") or {}).get(code) or {}
    for x in rv.get("news") or []:
        if x.get("date") and x.get("title"):
            out.append({"date": x["date"], "title": x["title"], "url": x.get("url", ""), "office": x.get("src", ""),
                        "read": x.get("read", ""), "impact": x.get("impact", "")})
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
