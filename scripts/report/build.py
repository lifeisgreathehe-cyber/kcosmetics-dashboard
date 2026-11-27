#!/usr/bin/env python3
"""기업분석 자동화 대시보드(docs/report) 데이터 빌드.

모든 업종 대시보드가 이미 모은 자료를 회사별 리포트 입력 파일로 모은다. 계산(ROIC·FCF·추정·기대수익률)은
화면(docs/report/report.js)에서 한다 — 가정을 바로 바꿔 볼 수 있게.

입력
  docs/<업종>/data/companies.json · quotes.json · valuation.json(시총·주식수) · stock_hist.json · news.json · news_hist.json · ir_web.json
  raw/<업종>/dart_docs/<코드>.json  사업보고서 '사업의 내용' 본문 → 표준 목차별 발췌
  raw/report/<코드>.json            scripts/report/collect_dart.py (PC) — 재무상태표·현금흐름 10년·배당·주주
  config/report/<코드>.json         Claude·사람이 쓴 원고와 모델 가정(있으면 자동 문장보다 우선)
출력
  docs/report/data/list.json, docs/report/data/c/<코드>.json
네트워크 없이 동작. 표준 라이브러리만 사용.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "report" / "data"
IND_NAMES = {"cosmetics": "화장품", "semi": "반도체", "chem": "화학·정유", "battery": "2차전지", "food": "음식료",
             "apparel": "의류", "logistics": "물류·운송", "auto": "자동차", "steel": "철강", "travel": "여행",
             "bio": "바이오·제약", "construction": "건설", "ship": "조선", "energy": "에너지"}


def jload(p, default=None):
    try:
        return json.loads(Path(p).read_text("utf-8"))
    except Exception:  # noqa: BLE001
        return default


def industries():
    out = [("cosmetics", ROOT / "docs" / "data", ROOT / "raw")]
    for d in sorted((ROOT / "docs").glob("*/data/companies.json")):
        ind = d.parent.parent.name
        out.append((ind, d.parent, ROOT / "raw" / ind))
    return out


def by_code(obj):
    """{companies: {code: x}} 또는 {companies: [{code}]} 모두 지원."""
    c = (obj or {}).get("companies", obj or {})
    if isinstance(c, list):
        return {x.get("code"): x for x in c if isinstance(x, dict) and x.get("code")}
    return c if isinstance(c, dict) else {}


# ------------------------------------------------------------- 사업보고서 표준 목차 발췌
BIZ_SECTIONS = [
    ("overview", "사업의 개요", r"\n\s*1\.\s*사업의\s*개요"),
    ("products", "주요 제품 및 서비스", r"\n\s*2\.\s*주요\s*제품"),
    ("materials", "원재료 및 생산설비", r"\n\s*3\.\s*원재료"),
    ("sales", "매출 및 수주상황", r"\n\s*4\.\s*매출"),
    ("risk", None, r"\n\s*5\.\s*위험관리"),  # 경계로만 사용(금융위험 관리 상투문은 싣지 않음)
    ("rnd", "주요계약 및 연구개발활동", r"\n\s*6\.\s*주요\s*계약"),
    ("etc", "기타 참고사항(산업·경쟁)", r"\n\s*7\.\s*기타\s*참고"),
]
HIST = ("history", "회사의 연혁", r"\n\s*2\.\s*회사의\s*연혁", r"\n\s*3\.\s*자본금")


def clean(s, cap):
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"(\n ?\| ?)+\n", "\n", s)
    s = s.strip()
    return s[:cap] + (" …(이하 생략)" if len(s) > cap else "")


def biz_extract(text, cap=2200):
    out = []
    pos = []
    for k, title, pat in BIZ_SECTIONS:
        m = list(re.finditer(pat, text))
        if m:
            pos.append((m[-1].start(), k, title))  # 목차가 아닌 본문(뒤쪽) 사용
    pos.sort()
    for i, (st, k, title) in enumerate(pos):
        en = pos[i + 1][0] if i + 1 < len(pos) else len(text)
        seg = text[st:en]
        seg = re.sub(r"^\s*\d\.\s*[^\n]{0,20}", "", seg, count=1)
        if title and len(seg.strip()) > 40:
            out.append({"k": k, "title": title, "text": clean(seg, cap)})
    k, title, a, b = HIST
    m = re.search(a, text)
    if m:
        e = re.search(b, text[m.end():])
        seg = text[m.end(): m.end() + (e.start() if e else 4000)]
        if len(seg.strip()) > 40:
            out.insert(0, {"k": k, "title": title, "text": clean(seg, 2500)})
    return out


def kpis_from_text(text):
    """본문에서 바로 쓸 수 있는 숫자: 가동률, 연구개발비 비율, 수출 비중."""
    out = {}
    i = re.search(r"가동[률율]", text)
    if i:
        m = re.findall(r"(\d{1,3}(?:\.\d+)?)\s*%", text[i.end(): i.end() + 400])
        vals = [float(x) for x in m if 0 < float(x) <= 150]
        if vals:
            out["utilization"] = vals[:4]
    m = re.search(r"연구개발비\s*/\s*매출액\s*비율[\s\S]{0,120}?(\d{1,2}\.\d+)\s*%", text)
    if m:
        out["rnd_ratio"] = float(m.group(1))
    return out


# ------------------------------------------------------------- 원가 충격 자동 탐지(분기 매출총이익률)
def gp_shocks(quarterly):
    ks = sorted(k for k, v in quarterly.items() if v.get("rev") and v.get("gp") is not None)
    gpm = [(k, quarterly[k]["gp"] / quarterly[k]["rev"] * 100) for k in ks]
    out = []
    i = 0
    while i < len(gpm) - 2:
        k0, g0 = gpm[i]
        trough = min(range(i + 1, min(i + 4, len(gpm))), key=lambda j: gpm[j][1])
        drop = g0 - gpm[trough][1]
        if drop >= 3.0:
            rec = next((j for j in range(trough + 1, len(gpm)) if gpm[j][1] >= g0 - 1.5), None)
            out.append({"start": k0, "start_gpm": round(g0, 1), "trough": gpm[trough][0], "trough_gpm": round(gpm[trough][1], 1),
                        "drop": round(drop, 1), "recovered": gpm[rec][0] if rec else None,
                        "quarters": (rec - i) if rec else None,
                        "path": [[gpm[j][0], round(gpm[j][1], 1)] for j in range(i, (rec + 1) if rec else len(gpm))]})
            i = (rec or len(gpm))
        else:
            i += 1
    return out[-3:]


def news_months(nh):
    m = {}
    for x in nh or []:
        d = (x.get("date") or "")[:7]
        if d:
            m[d] = m.get(d, 0) + 1
    return dict(sorted(m.items()))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "c").mkdir(exist_ok=True)
    today = dt.date.today().isoformat()
    lst = []
    all_cos = {}
    for ind, data, raw in industries():
        cos = jload(data / "companies.json", {}).get("companies", [])
        quotes = (jload(data / "quotes.json", {}) or {}).get("quotes", {}) or {}
        val = by_code(jload(data / "valuation.json"))
        hist = (jload(data / "stock_hist.json", {}) or {}).get("series", {})
        news = by_code(jload(data / "news.json"))
        newsh = by_code(jload(data / "news_hist.json"))
        irw = by_code(jload(data / "ir_web.json"))
        for c in cos:
            code = c.get("code")
            if not code or code in all_cos:
                continue
            all_cos[code] = (ind, data, raw, c, quotes.get(code), val.get(code), hist.get(code), news.get(code), newsh.get(code), irw.get(code))
    # 업종·그룹별 경쟁사 표 재료
    peers_pool = {}
    for code, (ind, data, raw, c, q, v, *_r) in all_cos.items():
        a = c.get("annual") or {}
        fy = max(a) if a else None
        rec = {"code": code, "name": c.get("name"), "group": c.get("group"),
               "mcap": (v or {}).get("mcap_eff") or (v or {}).get("mcap"), "fy": fy}
        if fy:
            rec.update({k: a[fy].get(k) for k in ("rev", "op", "ni")})
        rec["equity"] = ((c.get("bs") or {}).get("equity"))
        peers_pool.setdefault(ind, []).append(rec)

    for code, (ind, data, raw, c, q, v, h, nw, nh, ir) in all_cos.items():
        extra = jload(ROOT / "raw" / "report" / f"{code}.json") or {}
        manual = jload(ROOT / "config" / "report" / f"{code}.json") or {}
        docs = jload(raw / "dart_docs" / f"{code}.json") or {}
        reps = docs.get("reports") or []
        biz_txt = next((r.get("business") for r in reps if (r.get("report_nm") or "").startswith("사업보고서")), None) or (reps[0].get("business") if reps else "")
        annual = {y: dict(d) for y, d in (c.get("annual") or {}).items()}
        for y, d in (extra.get("annual") or {}).items():   # PC 추가 수집(재작성 전기 금액 우선)이 있으면 덮어쓴다
            base = annual.setdefault(y, {})
            for k, val_ in d.items():
                if not k.startswith("_") and val_ is not None:
                    base[k] = val_
        price = (q or {}).get("price") or (v or {}).get("price")
        peers = [p for p in peers_pool.get(ind, []) if p["group"] == c.get("group") and p["code"] != code]
        if len(peers) < 4:
            peers += [p for p in peers_pool.get(ind, []) if p["group"] != c.get("group") and p["code"] != code][: 6 - len(peers)]
        peers = sorted(peers, key=lambda p: -(p.get("mcap") or 0))[:8]
        out = {
            "code": code, "name": c.get("name"), "industry": ind, "industry_name": IND_NAMES.get(ind, ind),
            "group": c.get("group"), "market": c.get("market"), "built": today,
            "price": price, "price_time": (q or {}).get("time") or (v or {}).get("price_date"),
            "shares": (v or {}).get("shares") or (c.get("shares") or {}).get("common"),
            "shares_dart": c.get("shares"), "div_yield": (v or {}).get("dividend_yield"), "mcap": (v or {}).get("mcap_eff") or (v or {}).get("mcap"),
            "annual": dict(sorted(annual.items())), "quarterly": c.get("quarterly") or {},
            "bs_latest": c.get("bs"), "latest": extra.get("latest"),
            "dividends": extra.get("dividends") or {}, "holders": extra.get("holders"), "major5": extra.get("major5") or [],
            "dart_sections": (extra.get("docs") or {}),
            "extra_fetched": extra.get("fetched"),
            "prices": h, "news": (nw or [])[:25] if isinstance(nw, list) else [],
            "news_months": news_months(nh),
            "news_hist": [{k: x.get(k) for k in ("date", "title", "office", "url")} for x in (nh or [])[:40]] if isinstance(nh, list) else [],
            "ir": (ir or [])[:6] if isinstance(ir, list) else [],
            "biz": biz_extract(biz_txt) if biz_txt else [], "biz_kpi": kpis_from_text(biz_txt or ""),
            "biz_src": [{"nm": r.get("report_nm"), "url": r.get("url")} for r in reps],
            "shocks": gp_shocks(c.get("quarterly") or {}),
            "peers": [{**{"code": code, "name": c.get("name"), "self": True, "mcap": (v or {}).get("mcap_eff") or (v or {}).get("mcap"),
                          "fy": max(annual) if annual else None, "equity": (c.get("bs") or {}).get("equity")},
                       **({k: annual[max(annual)].get(k) for k in ("rev", "op", "ni")} if annual else {})}] + peers,
            "manual": manual,
        }
        # 이엔에프 원본처럼 '재작성 전'과 다를 수 있어 표시용 플래그
        out["restated"] = bool(extra.get("annual"))
        (OUT / "c" / f"{code}.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), "utf-8")
        lst.append({"code": code, "name": c.get("name"), "ind": ind, "ind_name": IND_NAMES.get(ind, ind), "group": c.get("group"),
                    "mcap": out["mcap"], "manual": bool(manual.get("sections") or manual.get("cover")), "extra": bool(extra)})
    lst.sort(key=lambda x: (-(x["manual"]), -(x["mcap"] or 0)))
    (OUT / "list.json").write_text(json.dumps({"built": today, "n": len(lst), "companies": lst}, ensure_ascii=False, separators=(",", ":")), "utf-8")
    print(f"[report] {len(lst)}개사 빌드 → docs/report/data (원고 {sum(x['manual'] for x in lst)}개, PC 추가 수집 {sum(x['extra'] for x in lst)}개)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
