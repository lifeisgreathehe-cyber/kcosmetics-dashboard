"""사업보고서(DART) 본문에서 회사 분석의 '근거 문장'을 자동으로 뽑는다.

손으로 쓴 심층분석(deep.json)이 한 줄짜리(예: "여성복.")인 회사도
제품 매출 구성·판매경로·주요 고객·원재료 가격·가동률·시장점유율·경쟁요소·업황 특성을
사업보고서 원문 문장 그대로(출처 링크와 함께) 보여 줄 수 있게 한다. 네트워크를 쓰지 않는다.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# 섹션 제목 패턴 → 키
HEADS = {
    "overview": r"사업의\s*개요",
    "products": r"주요\s*제품|주요\s*상품|주요\s*서비스|제품\s*및\s*서비스",
    "materials": r"원재료",
    "channel": r"판매\s*경로|판매\s*방법|판매\s*조직",
    "strategy": r"판매\s*전략|영업\s*전략",
    "customers": r"주요\s*(?:매출처|거래처|고객|판매처)",
    "orders": r"수주\s*(?:상황|현황)",
    "share": r"시장\s*점유율",
    "competition": r"경쟁\s*(?:요소|상황|현황|우위|력|구조|사|업체)|경쟁의\s*(?:요소|양상|형태)",
    "industry": r"산업의\s*특성|업계의\s*현황|산업의\s*성장성|경기\s*변동|시장의\s*특성|계절성",
    "rnd": r"연구\s*개발\s*(?:실적|활동|현황)",
}
HEAD_MARK = r"(?:^|\n|(?<=다\.)|(?<=다\. ))\s*(?:[가-하]\.|\(\d{1,2}\)|\d{1,2}\.|\d{1,2}\)|[①-⑳]|[○●■□▶-])\s*[^\n]{0,30}?"
BOILER = re.compile(r"위험회피|파생상품|스왑|평가손익|외상매출|어음|대금을 회수|나눈\s*(?:값|수치|금액)|기준으로 작성|산출하였|산출한|산정하였|다음과 같|아래와 같|아래 표|하기와 같|참고하시기|참조하시기|기재하였|기재하고|해당사항\s*없|해당 사항\s*없|작성기준일|본 보고서|보고서 제출|연결실체는 \d|단위\s*:|이하 같음|별도로 기재|상기 ")
SUFFIX = re.compile(r"^(?:\s*(?:등의|등|의|및|에\s*관한\s*사항|에\s*대한\s*사항|현황|추이|상황|요소|우위|특성|방법|조직|전략|실적|내용|개요|계획|동향|가격변동추이|가격\s*변동\s*추이|비율|구성|형태|양상|점유율|정책|경로)\s*)+")


def _pick_report(doc):
    """본문이 사업의 내용으로 시작하는(추출이 제대로 된) 가장 최근 보고서를 고른다."""
    best = None
    for r in doc.get("reports") or []:
        t = r.get("business") or ""
        i = t.find("사업의 개요")
        score = sum(1 for p in HEADS.values() if re.search(p, t[:80000]))
        ok = 0 <= i < 3000
        key = (ok, score)
        if best is None or key > best[0]:
            best = (key, r)
    return best[1] if best else None


def _body(t):
    """사업의 내용 본문만 (목차 표 줄은 무시하고, 표가 아닌 줄의 'III. 재무에 관한'에서 자른다)."""
    pos, start, end = 0, None, None
    for line in t.split("\n"):
        ls = line.lstrip()
        if not ls.startswith("|"):
            if start is None and "사업의 개요" in ls:
                start = pos
            elif start is not None and re.match(r"(?:III|Ⅲ)\.\s*재무에 관한", ls):
                end = pos
                break
        pos += len(line) + 1
    return t[(start or 0):end]


def _strip_tables(t):
    return "\n".join(l for l in t.split("\n") if not l.lstrip().startswith("|"))


def _sections(txt, key, maxlen=2500):
    """key 섹션 본문들(제목 뒤 ~ 다음 제목 전)을 돌려준다."""
    out = []
    for m in re.finditer(HEAD_MARK + "(?:" + HEADS[key] + ")", txt):
        s = txt[m.end():m.end() + maxlen]
        s = SUFFIX.sub("", s)
        n = re.search(r"\n\s*(?:[가-하]\.|\(\d{1,2}\)|\d{1,2}\.\s|\d{1,2}\))\s*\S", s[20:])
        if n:
            s = s[:20 + n.start()]
        out.append(s.strip())
    return out


HEAD_FRAG = re.compile(r"^(?:[^.]{0,25}?(?:[가-하]\.|\(\d{1,2}\)|\d{1,2}\))\s*[^.]{0,30}?(?:현황|추이|사항|개요|특성|성장성|전략|경로|요소|우위)\s*)+")
INFO = re.compile(r"\d|경기|성장|규모|수요|공급|경쟁|진입|점유|고객|수출|가격|원가|기술|특허|인증|1위|선두|독점|과점")


LEAD = re.compile(r"^(?:[,\s]*(?:서비스|생산설비(?:\s*등)?|판매방법\s*등|방법\s*및\s*전략\s*등|및\s*전략\s*등|등)\s*)?"
                  r"(?:(?:[가-하]\.|\(\d{1,2}\)|\d{1,2}\)|[①-⑳]|\d-\d\.)\s*[^.]{0,24}?(?=당사|회사는|연결회사|동사|당 사|국내|해외|주요|현재|[A-Z]{2,}))+")


def _clean(p):
    p = p.strip(" -※*·")
    p = LEAD.sub("", p)
    p = re.sub(r"^\(?[가-힣 ]{2,14}\)\s*-\s*", "", p)
    p = re.sub(r"^(?:으로는|로는)\s", "주요 거래처로는 ", p)  # "(산업의 성장성) - "
    return p.strip(" -※*·,)")


def _sents(s, n=2, need=None, maxc=230, rank=False):
    s = re.sub(r"\s+", " ", s)
    parts = re.split(r"(?<=다\.)\s*|(?<=음\.)\s*|(?<=함\.)\s*", s)
    parts = [HEAD_FRAG.sub("", p.strip()) if len(p) > 60 else p for p in parts]
    parts = [re.sub(r"^(?:및\s*)?당사의\s*(?:현황|개요)\s*", "", p) for p in parts]
    if rank:  # 숫자·업황 단어가 든 문장을 먼저 (원래 순서는 유지)
        parts = sorted(parts, key=lambda x: 0 if INFO.search(x) else 1)
    res = []
    for p in parts:
        p = _clean(p)
        if len(p) < 18 or BOILER.search(p) or p.startswith(("출처", "주)", "주1", "주2", "*")):
            continue
        if not re.search(r"(?:다|음|함)\.?$", p) or len(re.findall(r"(?:^|\s)(?:[가-하]\.|[①-⑳]|\(\d{1,2}\))\s", p)) >= 2:
            continue
        if not re.search(r"[가-힣]{2}", p):
            continue
        if need and not re.search(need, p):
            continue
        if len(p) > maxc:
            p = p[:maxc].rsplit(" ", 1)[0] + "…"
        if not any(p in q or q in p for q in res):
            res.append(p)
        if len(res) >= n:
            break
    return res


NUM = re.compile(r"^\(?-?[\d,]+(?:\.\d+)?\)?%?$")


def _num(x):
    x = x.replace(",", "").replace("%", "").strip()
    neg = x.startswith("(") and x.endswith(")")
    x = x.strip("()")
    try:
        v = float(x)
    except ValueError:
        return None
    return -v if neg else v


def _cells(t):
    return [l.strip().lstrip("|").strip() for l in t.split("\n") if l.lstrip().startswith("|")]


SKIP_LABEL = re.compile(r"^(?:계|합\s*계|소\s*계|총\s*계|합계|기\s*타|내부거래|연결조정|조정|단위|구\s*분|비율|매출액|비중|%|-)$")


def _mix(raw):
    """'주요 제품' 표에서 (이름, 금액, 비율%) 행을 찾아 매출 구성으로 만든다."""
    m = re.search(HEADS["products"], raw)
    if not m:
        return []
    seg = raw[m.start(): m.start() + 12000]
    nx = re.search(r"\n\s*(?:[나-하]\.)", seg[50:])
    if nx:
        seg = seg[:50 + nx.start()]
    cells = _cells(seg)
    items = []
    for i in range(len(cells) - 2):
        a, b, c = cells[i], cells[i + 1], cells[i + 2]
        if NUM.match(a) or not a or len(a) > 40 or SKIP_LABEL.match(a.replace(" ", "")):
            continue
        vb, vc = _num(b) if NUM.match(b) else None, _num(c) if NUM.match(c) else None
        if vb is None or vc is None:
            continue
        if 0 < vc <= 100 and abs(vb) >= vc:
            items.append({"label": re.sub(r"\s+", " ", a), "pct": round(vc, 1)})
    seen, out = set(), []
    for x in items:
        k = x["label"].replace(" ", "")
        if k in seen:
            continue
        seen.add(k)
        out.append(x)
    tot = sum(x["pct"] for x in out)
    if not out or tot < 60 or tot > 140:
        return []
    out.sort(key=lambda x: -x["pct"])
    return out[:8]


def _materials(raw, anchor=r"원재료"):
    """가격 표: 이름 + 3개 기 숫자(당기·전기·전전기) → 전기 대비 변화율.
    anchor='원재료' → 원재료 매입가, '주요 제품' → 제품 판매가(ASP)."""
    a = re.search(anchor, raw)
    if not a:
        return []
    m = re.search(r"가격", raw[a.start():a.start() + 6000])
    if not m:
        return []
    st = a.start() + m.start()
    seg = raw[st: st + 4000]
    stop = re.search(r"\n\s*(?:\d\.|[가-하]\.)\s*(?!.*가격)", seg[100:])
    if stop:
        seg = seg[:100 + stop.start()]
    cells = _cells(seg)
    out = []
    for i in range(len(cells) - 3):
        a = cells[i]
        if not a or NUM.match(a) or len(a) > 30 or SKIP_LABEL.match(a.replace(" ", "")) or re.search(r"제\s*\d+\s*기|20\d\d|단위|구\s*분|품\s*목|원재료", a):
            continue
        v = [_num(x) if NUM.match(x) else None for x in cells[i + 1:i + 4]]
        if None in v[:2] or not v[1]:
            continue
        chg = (v[0] / v[1] - 1) * 100
        if abs(chg) > 300:
            continue
        if any(o["item"] == re.sub(r"\s+", " ", a) for o in out):
            return []  # 같은 이름이 반복되면(수입/내수 등 구분 열) 표 해석을 믿을 수 없다
        out.append({"item": re.sub(r"\s+", " ", a), "now": v[0], "prev": v[1], "chg": round(chg, 1)})
        if len(out) >= 6:
            break
    return out


def facts(doc):
    r = _pick_report(doc)
    if not r:
        return None
    raw = _body(r.get("business") or "")
    txt = _strip_tables(raw)
    f = {"report": r.get("report_nm"), "url": r.get("url"), "date": r.get("rcept_dt")}

    def grab(key, n=2, need=None, rank=False):
        res = []
        for s in _sections(txt, key):
            for x in _sents(s, n, need, rank=rank):
                if not any(x in q or q in x for q in res):
                    res.append(x)
            if len(res) >= n:
                break
        return res[:n]

    f["overview"] = grab("overview", 3)
    f["products"] = grab("products", 2)
    f["mix"] = _mix(raw)
    f["materials"] = grab("materials", 2)
    f["mat_price"] = _materials(raw)
    f["price"] = _materials(raw, HEADS["products"])
    f["channel"] = grab("channel", 2)
    f["strategy"] = grab("strategy", 1)
    f["customers"] = grab("customers", 2)
    f["orders"] = grab("orders", 1, r"수주")
    sh = []
    for s in re.split(r"(?<=다\.)\s*", re.sub(r"\s+", " ", txt)):
        s = _clean(s)
        if "점유율" in s and not s.startswith("출처") and re.search(r"\d+(?:\.\d+)?\s*%|1위|2위|3위|선두|최대", s) and not BOILER.search(s) and 18 < len(s) < 300:
            if s.strip() not in sh:
                sh.append(s.strip())
        if len(sh) >= 2:
            break
    f["share"] = sh or [x for x in grab("share", 2) if "점유" in x][:1]
    f["competition"] = grab("competition", 2, rank=True)
    f["industry"] = grab("industry", 3, rank=True)
    f["cyclical"] = []
    for s in re.split(r"(?<=다\.)\s*", re.sub(r"\s+", " ", txt)):
        if re.search(r"경기\s*(?:변동|순환|민감|에 민감|의 영향)|계절적|경기에 따라|전방\s*산업의?\s*(?:경기|업황)", s) and 18 < len(s) < 260 and not BOILER.search(s):
            f["cyclical"].append(s.strip())
            if len(f["cyclical"]) >= 2:
                break
    ut = re.search(r"평균\s*가동률[^\d]{0,40}?(\d{1,3}(?:\.\d+)?)\s*%", raw) or re.search(r"가동률[^\n]{0,80}?(\d{1,3}(?:\.\d+)?)\s*%", txt)
    if ut and 0 < float(ut.group(1)) <= 150:
        f["utilization"] = float(ut.group(1))
    return {k: v for k, v in f.items() if v not in ([], None, "")}


def dart_dir(industry):
    return ROOT / "raw" / ("dart_docs" if industry == "cosmetics" else f"{industry}/dart_docs")


def load_facts(industry, code):
    p = dart_dir(industry) / f"{code}.json"
    if not p.exists():
        return None
    try:
        return facts(json.loads(p.read_text("utf-8")))
    except Exception as e:  # 한 회사 파싱 실패가 전체를 멈추지 않게
        print("bizfacts 실패", industry, code, e)
        return None


if __name__ == "__main__":
    import sys
    ind, code = sys.argv[1], sys.argv[2]
    print(json.dumps(load_facts(ind, code), ensure_ascii=False, indent=1))
