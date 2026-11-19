"""새 실적 감지: 회사별로 '가장 최근에 발표된 분기'와 그 숫자를 찾는다.

출처(우선순위)
 1. DART 확정치  — docs/<업종>/data/companies.json 의 quarterly (사용자 PC에서 수집)
 2. 네이버 금융 분기 실적 — raw/earnings/<업종>.json (GitHub Actions에서 fetch_naver()가 매일 받음, 잠정실적 공시 후 하루 안에 반영)
 3. 뉴스 제목·요약 — docs/<업종>/data/news.json + reviews.json 의 news (잠정실적 기사에서 숫자를 뽑음)

모든 금액 단위는 백만원(companies.json 과 같음)."""
import json, os, re, time, urllib.request, urllib.parse
import datetime as dt

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
KST = dt.timezone(dt.timedelta(hours=9))


def data_dir(ind):
    return os.path.join(ROOT, "docs", "data") if ind == "cosmetics" else os.path.join(ROOT, "docs", ind, "data")


def load(p, default=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def qkey(y, q):
    return f"{int(y)}Q{int(q)}"


def prev_q(k, n=1):
    y, q = int(k[:4]), int(k[-1])
    for _ in range(n):
        q -= 1
        if q == 0:
            y, q = y - 1, 4
    return qkey(y, q)


def yoy_key(k):
    return f"{int(k[:4]) - 1}{k[4:]}"


def expected_quarter(today=None):
    """오늘 기준으로 '이미 발표됐어야 할' 가장 최근 분기(잠정실적 기준)."""
    t = today or dt.datetime.now(KST).date()
    y, m = t.year, t.month
    if m >= 10:
        return qkey(y, 3)
    if m >= 7:
        return qkey(y, 2)
    if m >= 4:
        return qkey(y, 1)
    return qkey(y - 1, 4)


def next_release(k):
    """분기 k 다음 분기의 발표 시기 안내 문장."""
    y, q = int(k[:4]), int(k[-1])
    ny, nq = (y + 1, 1) if q == 4 else (y, q + 1)
    if nq == 4:
        return f"{ny}년 4분기(연간) 실적은 {ny+1}년 1월 말~2월 중순 잠정실적으로 먼저 나오고, 사업보고서는 3월 중순에 공시돼요."
    if nq == 1:
        return f"{ny}년 1분기 실적은 4월 말~5월 중순에 나와요(분기보고서 5월 15일 전후)."
    if nq == 2:
        return f"{ny}년 2분기 실적은 7월 말~8월 중순에 나와요(반기보고서 8월 14일 전후)."
    return f"{ny}년 3분기 실적은 10월 말~11월 중순에 나와요(분기보고서 11월 14일 전후)."


# ---------------------------------------------------------------- 뉴스에서 숫자 뽑기
NUM = r"(-?\d{1,4}(?:,\d{3})*(?:\.\d+)?)"
AMT = rf"(?:(\d+)\s*조\s*)?(?:{NUM}\s*억(?:\s*\d{{1,4}}\s*만)?|(?=\s*조))"
MAN = re.compile(r"억\s*(\d{1,4})\s*만")
METRIC = {
    "rev": r"(?:매출액|매출|영업수익|순매출)",
    "op": r"(?:영업이익|영업익|영업손실|영업손익)",
    "ni": r"(?:당기순이익|순이익|순손실|지배주주순이익)",
}
CHG = r"(?:\s*\(?\s*(?:전년\s*(?:동기|같은\s*기간)?\s*(?:대비|比)\s*)?([+\-−△▲▼]?\s*\d{1,4}(?:\.\d+)?)\s*%\s*(증가|감소|↑|↓|늘|줄|상승|하락|급증|급감)?)?"
QPAT = re.compile(r"(?:(20\d\d)\s*년\s*)?([1-4])\s*(?:분기|Q)|([1-4])Q(?:2[4-9]|\d\d)?|(?:20)?(\d\d)\s*\.?\s*([1-4])Q")
LOSS = re.compile(r"(적자|손실|적전|적자전환|적자 지속)")


def _amt(jo, eok):
    v = 0.0
    if jo:
        v += int(jo) * 10000
    if eok:
        v += float(eok.replace(",", ""))
    return v * 100  # 억 → 백만원


def parse_numbers(text):
    """'3분기 매출 1,556억원(+36.3%), 영업이익 334억' → {rev, op, rev_yoy, op_yoy}. 못 찾으면 빈 dict."""
    out = {}
    t = text.replace("억원", "억").replace("조원", "조")
    for f, kw in METRIC.items():
        # 금액이 먼저: '영업이익 334억' / '영업이익은 전년 동기 대비 28% 감소한 270억'
        m = next((x for x in re.finditer(kw + r"[은는이가도]?\s*(?:[^.。…\d]{0,25}?)" + AMT + CHG, t)
                  if "누적" not in t[max(0, x.start() - 12): x.end()] and "연간" not in t[max(0, x.start() - 8): x.start()]), None)
        if m and (m.group(1) or m.group(2)):
            v = _amt(m.group(1), m.group(2))
            mm = MAN.search(m.group(0))
            if mm:
                v += int(mm.group(1)) / 100  # 만원 → 백만원
            if v <= 0:
                continue
            seg = t[m.start(): m.end() + 6]
            if f in ("op", "ni") and LOSS.search(t[m.start(): m.start() + len(m.group(0)) + 2]) and "흑자" not in seg:
                v = -v
            out[f] = v
            if m.group(3):
                c = float(re.sub(r"[^\d.]", "", m.group(3)))
                neg = bool(re.search(r"[-−△▼]", m.group(3))) or (m.group(4) or "") in ("감소", "↓", "줄", "하락", "급감")
                out[f + "_yoy"] = -c if neg else c
        else:  # 증감률이 금액 앞: '영업이익이 28.2% 감소한 270억'
            m = next((x for x in re.finditer(kw + r"[은는이가도]?\s*(?:전년\s*(?:동기|같은\s*기간)?\s*(?:대비\s*)?)?" + r"([+\-−△▲▼]?\s*\d{1,4}(?:\.\d+)?)\s*%\s*(증가|감소|늘어난|줄어든|늘|줄|상승|하락|급증|급감)\S{0,3}\s*" + AMT, t)
                      if "누적" not in t[max(0, x.start() - 12): x.end()]), None)
            if m and (m.group(3) or m.group(4)):
                v = _amt(m.group(3), m.group(4))
                if v > 0:
                    out[f] = v
                    c = float(re.sub(r"[^\d.]", "", m.group(1)))
                    neg = bool(re.search(r"[-−△▼]", m.group(1))) or m.group(2) in ("감소", "줄어든", "줄", "하락", "급감")
                    out[f + "_yoy"] = -c if neg else c
    if "흑자전환" in t or "흑자 전환" in t:
        out["turn"] = "흑자 전환"
    elif "적자전환" in t or "적자 전환" in t:
        out["turn"] = "적자 전환"
        if "op" in out and out["op"] > 0 and re.search(r"영업\S{0,3}\s*적자전환|영업손실", t):
            out["op"] = -out["op"]
    if re.search(r"컨센서스|시장\s*(?:전망|기대|예상)|기대치|추정치|전망치", t):
        if re.search(r"(?:상회|웃돌|넘어|서프라이즈|깜짝|뛰어넘)", t):
            out["cons"] = "상회"
        elif re.search(r"(?:하회|밑돌|못\s*미|부진|쇼크|미달)", t):
            out["cons"] = "하회"
        elif re.search(r"부합|수준", t):
            out["cons"] = "부합"
    return out


def quarter_of(text, date):
    """기사 문장에서 몇 분기 실적인지. 연도가 없으면 기사 날짜로 추정."""
    m = QPAT.search(text)
    if not m:
        return None
    if m.group(2):
        y = int(m.group(1)) if m.group(1) else None
        q = int(m.group(2))
    elif m.group(3):
        y, q = None, int(m.group(3))
    else:
        y, q = 2000 + int(m.group(4)), int(m.group(5))
    if y is None:
        try:
            dy, dm = int(date[:4]), int(date[5:7])
        except ValueError:
            return None
        # 4분기 실적은 이듬해 1~3월에 발표
        y = dy - 1 if q == 4 and dm <= 4 else dy
    return qkey(y, q)


EARN = re.compile(r"(실적|영업이?익|영업손실|매출|순이익|흑자|적자|어닝|잠정)")
NOT_EARN = re.compile(r"(목표가|목표주가|전망|예상|추정|컨센서스|프리뷰|기대)")


def news_events(items, names=(), others=()):
    """뉴스 목록 → [{q, date, src, title, url, nums}] (실적 발표 기사만, 최신순).
    names: 이 회사 이름·별칭(제목에 있어야 함). others: 같은 업종 다른 회사 이름(제목이 그 회사 기사면 제외)."""
    out = []
    names = [x for x in names if x and len(x) >= 2]
    for n in items or []:
        title, summ = n.get("title", ""), n.get("summary", "") or n.get("read", "")
        date = n.get("date", "")
        if not date or not EARN.search(title):
            continue
        if names:
            if not any(x in title for x in names):
                # 리뷰에 손으로 붙인 기사(own)는 제목에 회사 이름이 없어도 쓰되, 다른 회사 이름이 있으면 그 회사 기사로 본다
                if not n.get("own") or any(o and len(o) >= 2 and o in title for o in others):
                    continue
            # 제목에 다른 회사 이름이 있고 우리 회사 정식 이름은 없으면 그 회사 기사('콜마홀딩스, 3분기…' 등)
            oth = [o for o in others if o and len(o) >= 2 and o in title and not any(o in x or x in o for x in names[:1])]
            if oth and names[0] not in title:
                continue
            # 여러 회사를 묶은 기사(제목에 상장사 이름 2개 이상)는 숫자가 누구 것인지 불분명해 제외
            if len(oth) >= 1 and names[0] in title and not re.match(r"^\W*" + re.escape(names[0]), title):
                continue
        q = quarter_of(title, date) or (quarter_of(summ, date) if EARN.search(summ) else None)
        if not q or q > expected_quarter(dt.date.fromisoformat(date[:10]) if re.match(r"\d{4}-\d\d-\d\d", date) else None):
            continue  # 아직 끝나지 않은 분기('4분기 전망')는 실적 기사가 아님
        nums = parse_numbers(title)
        if summ and (not names or any(x in title for x in names)):
            # '영업이익 17억원 전망' 같은 예상치 구절은 빼고 읽는다
            summ = " ".join(p for p in re.split(r"(?<=[.,])\s+|[()]", summ) if not re.search(r"전망|예상|추정|컨센서스|기대치|목표", p))
            for k, v in parse_numbers(summ).items():
                nums.setdefault(k, v)
        if not any(k in nums for k in ("rev", "op", "op_yoy", "rev_yoy", "turn")):
            continue
        # 증권사 전망·프리뷰 기사(아직 발표 전)는 제외. '기대치 상회/하회'처럼 발표 뒤 평가는 살린다
        if NOT_EARN.search(title) and not re.search(r"(상회|하회|웃돌|밑돌|부합|쇼크|서프라이즈|기록|달성|공시|발표)", title):
            continue
        out.append({"q": q, "date": date, "src": n.get("office") or n.get("src", ""), "title": title,
                    "url": n.get("url", ""), "nums": nums})
    out.sort(key=lambda e: (e["q"], e["date"]), reverse=True)
    return out


def merge_event(evs, q):
    """같은 분기 기사 여러 개의 숫자를 합친다(먼저 나온 값 우선, 비어 있는 칸은 다른 기사로 채움)."""
    nums, src = {}, []
    es = sorted([e for e in evs if e["q"] == q], key=lambda e: e["date"], reverse=True)  # 최신 기사 우선
    d0 = es[0]["date"] if es else ""
    for e in es:
        for k, v in e["nums"].items():
            if k == "cons" and e["date"] < (dt.date.fromisoformat(d0[:10]) - dt.timedelta(days=5)).isoformat():
                continue  # 발표 훨씬 전 프리뷰의 '기대 하회 전망'은 쓰지 않음
            nums.setdefault(k, v)
        src.append(e)
    return nums, src


# ---------------------------------------------------------------- 네이버 금융 분기 실적 (Actions 전용)
NAVER_Q = "https://m.stock.naver.com/api/stock/{code}/finance/quarter"


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://m.stock.naver.com/"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def _num(s):
    try:
        return float(str(s).replace(",", ""))
    except Exception:
        return None


def parse_naver_quarter(j):
    """네이버 분기 재무 JSON → {'2026Q3': {'rev','op','ni'}} (컨센서스 칸은 제외). 단위: 억원 → 백만원."""
    fi = j.get("financeInfo") or j
    titles = fi.get("trTitleList") or []
    rows = fi.get("rowList") or []
    out = {}
    for t in titles:
        if (t.get("isConsensus") or "N") == "Y":
            continue
        key = t.get("key") or ""
        m = re.match(r"(20\d\d)(\d\d)", key) or re.match(r"(20\d\d)\.(\d\d)", t.get("title", ""))
        if not m:
            continue
        mon = int(m.group(2))
        q = qkey(int(m.group(1)), (mon - 1) // 3 + 1)
        rec = {}
        for r in rows:
            nm = r.get("title", "")
            f = "rev" if nm.startswith("매출") else "op" if nm.startswith("영업이익") else "ni" if nm.startswith("당기순이익") else None
            if not f or f in rec:
                continue
            v = _num(((r.get("columns") or {}).get(key) or {}).get("value"))
            if v is not None:
                rec[f] = v * 100
        if rec.get("rev") or rec.get("op"):
            out[q] = rec
    return out


NAVER_MAIN = "https://finance.naver.com/item/main.naver?code={code}"


def parse_naver_main(html):
    """finance.naver.com 종목 메인의 '기업실적분석' 표(분기 칸)에서 매출·영업이익·순이익. (E) 표시는 추정치라 제외."""
    m = re.search(r'<div class="section cop_analysis">(.*?)</table>', html, re.S)
    if not m:
        return {}
    t = m.group(1)
    heads = [(d, "(E)" in rest) for d, rest in re.findall(r"<th[^>]*>\s*(20\d\d\.\d\d)(.*?)</th>", t, re.S)]
    # 앞 4칸은 연간, 뒤 6칸이 분기
    qcols = heads[4:] if len(heads) >= 10 else heads
    off = len(heads) - len(qcols)
    out = {}
    rows = {}
    for nm, f in (("매출액", "rev"), ("영업이익", "op"), ("당기순이익", "ni")):
        rm = re.search(r"<th[^>]*>\s*(?:<strong>)?\s*" + nm + r"\s*(?:</strong>)?\s*</th>(.*?)</tr>", t, re.S)
        if rm:
            rows[f] = [re.sub(r"<[^>]+>|\s", "", c) for c in re.findall(r"<td[^>]*>(.*?)</td>", rm.group(1), re.S)]
    for j, (per, est) in enumerate(qcols):
        if est:
            continue
        y, mo = int(per[:4]), int(per[5:7])
        rec = {}
        for f, cells in rows.items():
            if off + j < len(cells):
                v = _num(cells[off + j])
                if v is not None:
                    rec[f] = v * 100
        if rec.get("rev") or rec.get("op") is not None:
            out[qkey(y, (mo - 1) // 3 + 1)] = rec
    return out


def fetch_one(code):
    try:
        q = parse_naver_quarter(_get(NAVER_Q.format(code=code)))
        if q:
            return q
    except Exception:  # noqa: BLE001
        pass
    req = urllib.request.Request(NAVER_MAIN.format(code=code), headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.naver.com/"})
    with urllib.request.urlopen(req, timeout=15) as r:
        raw = r.read()
    for enc in ("utf-8", "euc-kr"):
        try:
            return parse_naver_main(raw.decode(enc))
        except UnicodeDecodeError:
            continue
    return {}


def fetch_naver(ind, codes, sleep=0.25):
    """Actions에서 매일 실행: raw/earnings/<업종>.json 에 회사별 분기 실적(잠정 포함)을 저장."""
    p = os.path.join(ROOT, "raw", "earnings", f"{ind}.json")
    old = load(p, {"companies": {}})
    got = 0
    for code in codes:
        try:
            q = fetch_one(code)
            if q:
                old["companies"][code] = q
                got += 1
        except Exception as e:  # noqa: BLE001
            print("  네이버 분기 실적 실패", code, str(e)[:80])
        time.sleep(sleep)
    old["source"] = "네이버 금융(FnGuide) 분기 실적 — 잠정실적 공시 반영"
    old["fetched"] = dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(old, f, ensure_ascii=False, indent=0)
    print(f"[{ind}] 네이버 분기 실적 {got}/{len(codes)}개사")
    return old
