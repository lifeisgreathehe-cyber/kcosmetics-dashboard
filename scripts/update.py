#!/usr/bin/env python3
"""국내 화장품 산업 대시보드 데이터 갱신 스크립트.

환경변수로 받은 API 키가 있는 소스만 갱신하고, 없는 소스는 기존 docs/data/*.json 을 그대로 둔다.
  DART_API_KEY    : 상장사 재무 (opendart.fss.or.kr)
  KOSIS_API_KEY   : 통계청·식약처 통계 (kosis.kr/openapi)
  DATA_GO_KR_KEY  : 관세청 품목별/국가별 수출입실적 (data.go.kr)

표준 라이브러리만 사용한다.
"""
from __future__ import annotations

import datetime as dt
import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data"
CONFIG = ROOT / "config"
TODAY = dt.date.today()


def log(*a):
    print("[update]", *a, flush=True)


def http_get(url: str, params: dict, retries: int = 3, raw: bool = False):
    q = urllib.parse.urlencode(params, safe="+")
    full = f"{url}?{q}"
    for i in range(retries):
        try:
            req = urllib.request.Request(full, headers={"User-Agent": "kcosmetics-dashboard/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read()
            return body if raw else body.decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            log(f"GET 실패 ({i + 1}/{retries}): {url} — {e}")
            time.sleep(2 * (i + 1))
    return None


def load(name):
    p = DATA / name
    return json.loads(p.read_text("utf-8")) if p.exists() else None


def save(name, obj):
    (DATA / name).write_text(json.dumps(obj, ensure_ascii=False, indent=0), "utf-8")
    log("저장:", name)


# ---------------------------------------------------------------- DART
DART = "https://opendart.fss.or.kr/api"
REPRT = {"Q1": "11013", "H1": "11012", "Q3": "11014", "FY": "11011"}

ACC = {
    "rev": (["ifrs-full_Revenue", "ifrs_Revenue"], ["매출액", "수익(매출액)", "영업수익", "매출", "매출 및 지분법손익"]),
    "gp": (["ifrs-full_GrossProfit", "ifrs_GrossProfit"], ["매출총이익", "매출총이익(손실)"]),
    "op": (["dart_OperatingIncomeLoss"], ["영업이익", "영업이익(손실)", "영업손익"]),
    "ni": (["ifrs-full_ProfitLossAttributableToOwnersOfParent", "ifrs_ProfitLossAttributableToOwnersOfParent"],
           ["지배기업의 소유주에게 귀속되는 당기순이익", "지배기업 소유주지분", "지배기업소유주지분", "지배기업의 소유주"]),
    "ni_total": (["ifrs-full_ProfitLoss", "ifrs_ProfitLoss"], ["당기순이익", "당기순이익(손실)", "분기순이익", "반기순이익"]),
}


def num(s):
    if s in (None, "", "-"):
        return None
    try:
        return int(str(s).replace(",", ""))
    except ValueError:
        return None


def dart_corp_codes(key):
    body = http_get(f"{DART}/corpCode.xml", {"crtfc_key": key}, raw=True)
    if not body:
        return {}
    z = zipfile.ZipFile(io.BytesIO(body))
    root = ET.fromstring(z.read(z.namelist()[0]))
    m = {}
    for el in root.iter("list"):
        sc = (el.findtext("stock_code") or "").strip()
        if sc:
            m[sc] = el.findtext("corp_code")
    return m


def dart_report(key, corp, year, reprt):
    """한 보고서의 손익 항목 추출. 반환: {field: (3개월또는연간, 누적)} 단위 원."""
    for fs in ("CFS", "OFS"):
        txt = http_get(f"{DART}/fnlttSinglAcntAll.json",
                       {"crtfc_key": key, "corp_code": corp, "bsns_year": year, "reprt_code": reprt, "fs_div": fs})
        if not txt:
            continue
        j = json.loads(txt)
        if j.get("status") != "000":
            continue
        rows = [r for r in j.get("list", []) if r.get("sj_div") in ("IS", "CIS")]
        out = {}
        for f, (ids, names) in ACC.items():
            hit = next((r for r in rows if r.get("account_id") in ids), None)
            if not hit:
                hit = next((r for r in rows if r.get("account_nm", "").replace(" ", "") in [n.replace(" ", "") for n in names]), None)
            if hit:
                a = num(hit.get("thstrm_amount"))
                c = num(hit.get("thstrm_add_amount"))
                out[f] = (a, c if c is not None else a)
        if out:
            if "ni" not in out and "ni_total" in out:  # 별도재무제표 등: 지배주주 구분이 없으면 당기순이익 사용
                out["ni"] = out["ni_total"]
            out["_fs"] = fs
            return out
        time.sleep(0.2)
    return None


def to_m(v):
    return None if v is None else round(v / 1_000_000)


def update_dart(key):
    cfg = json.loads((CONFIG / "companies.json").read_text("utf-8"))
    store = load("companies.json") or {"companies": []}
    old = {c["code"]: c for c in store.get("companies", [])}
    codes = dart_corp_codes(key)
    if not codes:
        log("DART corpCode 조회 실패 — 재무 갱신 건너뜀 (DART는 해외 IP 접속이 막혀 있어요)")
        return False
    last_year = TODAY.year - 1
    years_a = list(range(last_year - 9, last_year + 1))
    years_q = list(range(TODAY.year - 4, TODAY.year + 1))
    result = []
    for c in cfg:
        corp = codes.get(c["code"])
        rec = {**c, "annual": {}, "quarterly": {}, "source": "dart"}
        if not corp:
            log("corp_code 없음:", c["name"])
            result.append(old.get(c["code"], rec))
            continue
        log("DART:", c["name"])
        fy = {}
        for y in sorted(set(years_a) | set(years_q)):
            if y > TODAY.year - 1:
                continue
            r = dart_report(key, corp, y, REPRT["FY"])
            if r:
                fy[y] = r
                if y in years_a:
                    rec["annual"][str(y)] = {f: to_m(r[f][0]) if f in r else None for f in ("rev", "gp", "op", "ni")}
        for y in years_q:
            q1 = dart_report(key, corp, y, REPRT["Q1"])
            h1 = dart_report(key, corp, y, REPRT["H1"])
            q3 = dart_report(key, corp, y, REPRT["Q3"])
            for qn, r in (("Q1", q1), ("Q2", h1), ("Q3", q3)):
                if r:
                    rec["quarterly"][f"{y}{qn}"] = {f: to_m(r[f][0]) if f in r else None for f in ("rev", "gp", "op", "ni")}
            if y in fy and q3:
                q4 = {}
                for f in ("rev", "gp", "op", "ni"):
                    a = fy[y].get(f, (None,))[0]
                    cum = q3.get(f, (None, None))[1]
                    q4[f] = to_m(a - cum) if a is not None and cum is not None else None
                rec["quarterly"][f"{y}Q4"] = q4
        if not rec["annual"] and not rec["quarterly"]:
            result.append(old.get(c["code"], rec))
        else:
            result.append(rec)
    store = {"updated": TODAY.isoformat(), "companies": result}
    save("companies.json", store)
    return True


# ---------------------------------------------------------------- KOSIS
KOSIS = "https://kosis.kr/openapi/Param/statisticsParameterData.do"


def kosis_fetch(key, spec):
    p = {"method": "getList", "apiKey": key, "format": "json", "jsonVD": "Y",
         "orgId": spec["orgId"], "tblId": spec["tblId"], "itmId": spec.get("itmId", "ALL"),
         "objL1": spec.get("objL1", "ALL"), "prdSe": spec["prdSe"],
         "startPrdDe": spec["start"], "endPrdDe": spec.get("end", f"{TODAY.year}12" if spec["prdSe"] == "M" else str(TODAY.year))}
    for k in ("objL2", "objL3"):
        if k in spec:
            p[k] = spec[k]
    if spec["prdSe"] == "Q":
        p["endPrdDe"] = f"{TODAY.year}04"
    txt = http_get(KOSIS, p)
    if not txt:
        return None
    try:
        rows = json.loads(txt)
    except json.JSONDecodeError:
        log("KOSIS 응답 파싱 실패:", spec["file"], txt[:200])
        return None
    if isinstance(rows, dict):
        log("KOSIS 오류:", spec["file"], rows)
        return None
    return rows


def fmt_period(p, freq):
    if freq == "M":
        return f"{p[:4]}-{p[4:6]}"
    if freq == "Q":
        return f"{p[:4]}Q{int(p[4:6])}"
    return p[:4]


def update_kosis(key):
    specs = json.loads((CONFIG / "kosis.json").read_text("utf-8"))
    for spec in specs:
        rows = kosis_fetch(key, spec)
        if not rows:
            continue
        freq = spec["prdSe"]
        if spec.get("kind") == "ranked":
            years = {}
            for r in rows:
                y = r["PRD_DE"][:4]
                rank = r["C1_NM"]
                years.setdefault(y, {}).setdefault(rank, {})[r["ITM_NM"]] = r["DT"]
            out = {}
            for y, ranks in years.items():
                lst = []
                for rk in sorted(ranks, key=lambda s: int("".join(ch for ch in s if ch.isdigit()) or 0)):
                    d = ranks[rk]
                    lst.append([d.get("국가명"), num(d.get("수출액"))])
                out[y] = lst
            obj = load(spec["file"]) or {}
            obj.update({"years": out, "updated": TODAY.isoformat()})
            save(spec["file"], obj)
            continue
        series, periods = {}, set()
        for r in rows:
            name = spec.get("rename", {}).get(r.get(spec["series_key"]), r.get(spec["series_key"]))
            per = fmt_period(r["PRD_DE"], freq)
            periods.add(per)
            try:
                v = float(r["DT"])
                v = int(v) if v.is_integer() else v
            except (TypeError, ValueError):
                v = None
            series.setdefault(name, {})[per] = v
        periods = sorted(periods)
        obj = load(spec["file"]) or {}
        key_p = {"M": "months", "Q": "quarters", "Y": "years"}[freq]
        obj[key_p] = [int(p) if freq == "Y" else p for p in periods]
        if spec.get("flat"):
            for name, s in series.items():
                obj[name] = [s.get(p) for p in periods]
        elif spec.get("single"):
            obj["values"] = [next(iter(series.values())).get(p) for p in periods]
        else:
            obj["series"] = {name: [s.get(p) for p in periods] for name, s in series.items()}
        obj["updated"] = TODAY.isoformat()
        save(spec["file"], obj)


# ---------------------------------------------------------------- 관세청 (data.go.kr)
ITEM_URL = "https://apis.data.go.kr/1220000/Itemtrade/getItemtradeList"  # 관세청_품목별 수출입실적(GW)
NATION_URL = "https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList"  # 관세청_품목별 국가별 수출입실적(GW)
HS_GROUPS = {"3303": "향수", "3304": "기초·색조(3304)", "3305": "두발용", "3307": "면도·탈취 등"}
COUNTRIES = {"US": "미국", "CN": "중국", "JP": "일본", "HK": "홍콩", "VN": "베트남", "RU": "러시아", "TW": "대만", "AE": "UAE"}


def parse_items(xml_text):
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    items = []
    for it in root.iter("item"):
        items.append({c.tag: (c.text or "").strip() for c in it})
    return items


def month_ranges(start: dt.date, end: dt.date):
    y = start.year
    while y <= end.year:
        s = f"{y}01" if y > start.year else start.strftime("%Y%m")
        e = f"{y}12" if y < end.year else end.strftime("%Y%m")
        yield s, e
        y += 1


def sum_by_month(items, field="expDlr", hs=None):
    """월별 합계. 응답에 요청한 HS 코드와 정확히 같은 행이 있으면 그 행만 쓰고(상·하위 단위 중복 방지), 없으면 모든 행을 더한다."""
    out = {}
    if hs and any(it.get("hsCd") == hs for it in items):
        items = [it for it in items if it.get("hsCd") == hs]
    for it in items:
        ym = it.get("year", "")
        if "." not in ym:  # 총계 행 제외
            continue
        y, m = ym.split(".")[:2]
        key = f"{y}-{int(m):02d}"
        v = num(it.get(field))
        if v is not None:
            out[key] = out.get(key, 0) + v
    return out


def update_customs(key):
    start = dt.date(TODAY.year - 5, 1, 1)
    end = TODAY.replace(day=1) - dt.timedelta(days=1)
    by_hs = {}
    imp_total = {}
    for hs, label in HS_GROUPS.items():
        agg = {}
        for s, e in month_ranges(start, end):
            txt = http_get(ITEM_URL, {"serviceKey": key, "strtYymm": s, "endYymm": e, "hsSgn": hs})
            if not txt:
                continue
            items = parse_items(txt)
            if not items:
                log(f"관세청 응답에 데이터 없음 (HS {hs}, {s}~{e}):", txt[:200].replace(key, "***"))
            for k, v in sum_by_month(items, hs=hs).items():
                agg[k] = agg.get(k, 0) + v
            for k, v in sum_by_month(items, "impDlr", hs=hs).items():
                imp_total[k] = imp_total.get(k, 0) + v
            time.sleep(0.3)
        if agg:
            by_hs[label] = agg
    if not by_hs:
        log("관세청 품목별 데이터 없음 — 건너뜀")
        return
    months = sorted({m for s in by_hs.values() for m in s})
    series = {lab: [round(s.get(m, 0) / 1e6, 2) if m in s else None for m in months] for lab, s in by_hs.items()}
    total = [round(sum(by_hs[l].get(m, 0) for l in by_hs) / 1e6, 2) for m in months]
    save("customs_exports.json", {
        "title": "화장품 월별 수출액 (관세청)", "source": "관세청 품목별 수출입실적 (HS 3303·3304·3305·3307)",
        "url": "https://www.data.go.kr/data/15100475/openapi.do", "unit": "백만 달러", "months": months,
        "total": total, "series": series,
        "imports": [round(imp_total.get(m, 0) / 1e6, 2) for m in months], "updated": TODAY.isoformat()})

    # 국가별 (HS 3304 기준)
    cs = {}
    for cc, nm in COUNTRIES.items():
        agg = {}
        for s, e in month_ranges(dt.date(TODAY.year - 2, 1, 1), end):
            txt = http_get(NATION_URL, {"serviceKey": key, "strtYymm": s, "endYymm": e, "cntyCd": cc, "hsSgn": "3304"})
            if txt:
                for k, v in sum_by_month(parse_items(txt), hs="3304").items():
                    agg[k] = agg.get(k, 0) + v
            time.sleep(0.3)
        if agg:
            cs[nm] = agg
    if cs:
        months = sorted({m for s in cs.values() for m in s})
        save("customs_by_country.json", {
            "title": "국가별 월별 수출액 (HS 3304)", "source": "관세청 국가별 품목별 수출입실적",
            "unit": "백만 달러", "months": months,
            "series": {n: [round(s.get(m, 0) / 1e6, 2) if m in s else None for m in months] for n, s in cs.items()},
            "updated": TODAY.isoformat()})


# ---------------------------------------------------------------- main
def main():
    # 사용법: python scripts/update.py [--only dart|kosis|customs]
    # DART는 해외 IP(GitHub Actions 등)에서 접속이 막혀 있어 국내 PC에서 --only dart 로 실행한다.
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    ran = []
    if os.getenv("KOSIS_API_KEY") and only in (None, "kosis"):
        update_kosis(os.environ["KOSIS_API_KEY"]); ran.append("KOSIS")
    if os.getenv("DATA_GO_KR_KEY") and only in (None, "customs"):
        update_customs(os.environ["DATA_GO_KR_KEY"]); ran.append("관세청")
    if os.getenv("DART_API_KEY") and only in (None, "dart"):
        ok = update_dart(os.environ["DART_API_KEY"].strip().split("=")[-1].strip())
        if ok:
            ran.append("DART")
    if only:  # 부분 실행은 meta를 덮어쓰지 않고 소스 목록만 합친다
        meta = load("meta.json") or {}
        meta["sources_updated"] = sorted(set(meta.get("sources_updated", [])) | set(ran))
        meta[f"last_run_{only}"] = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M KST")
        save("meta.json", meta)
        log("완료:", ran)
        return
    meta = load("meta.json") or {}
    meta["last_run"] = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M KST")
    meta["sources_updated"] = ran
    save("meta.json", meta)
    log("완료:", ran or "키 없음 — 기존 데이터 유지")


if __name__ == "__main__":
    sys.exit(main())
