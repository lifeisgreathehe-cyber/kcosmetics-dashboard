#!/usr/bin/env python3
"""기업분석 리포트(docs/report)용 DART 추가 수집 — 사용자 PC(국내 IP)에서 실행.

리포트 툴(이엔에프 AI 리포트 역엔지니어링)이 쓰는 원자료 중 기존 update.py 가 모으지 않는 것:
  - 연결 재무상태표·현금흐름표·손익 세부(매출원가·판관비·세전이익) 10년치 (재작성 전기 금액 우선)
  - 최신 분기 재무상태표·누적 현금흐름
  - 배당(주당배당금·배당성향·배당수익률), 최대주주·특수관계인 지분, 5% 대량보유
  - 사업보고서 본문 중 연혁·배당·주주·대주주 거래 구간 (--no-docs 로 끔)

출력: raw/report/<종목코드>.json  (이미 받은 연도는 다시 받지 않는다)
사용: python scripts/report/collect_dart.py [--industry all|semi|...] [--code 102710] [--no-docs]
키:   환경변수 DART_API_KEY (scripts/report_dart.bat 이 키 파일에서 읽어 준다)
표준 라이브러리만 사용.
"""
from __future__ import annotations

import datetime as dt
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "raw" / "report"
DART = "https://opendart.fss.or.kr/api"
TODAY = dt.date.today()
FIRST_YEAR = 2015          # 2016년 값을 2016년 보고서의 '전기'가 아니라 2017년 보고서 전기로 받기 위해 1년 더
ARGV = sys.argv[1:]


def arg(name, default=None):
    return ARGV[ARGV.index(name) + 1] if name in ARGV and ARGV.index(name) + 1 < len(ARGV) else default


def log(*a):
    print("[report-dart]", *a, flush=True)


class LimitExceeded(Exception):
    pass


CALLS = 0


def get(path, params, raw=False):
    global CALLS
    q = urllib.parse.urlencode(params)
    for i in range(3):
        try:
            CALLS += 1
            req = urllib.request.Request(f"{DART}/{path}?{q}", headers={"User-Agent": "kcosmetics-dashboard/1.0"})
            with urllib.request.urlopen(req, timeout=90) as r:
                body = r.read()
            if raw:
                return body
            j = json.loads(body.decode("utf-8", errors="replace"))
            if j.get("status") == "020":
                raise LimitExceeded(j.get("message"))
            return j
        except LimitExceeded:
            raise
        except Exception as e:  # noqa: BLE001
            log(f"  GET 실패 {i + 1}/3 {path}: {e}")
            time.sleep(2 * (i + 1))
    return None


def num(s):
    if s in (None, "", "-"):
        return None
    try:
        return int(str(s).replace(",", "").strip())
    except ValueError:
        try:
            return float(str(s).replace(",", "").strip())
        except ValueError:
            return None


# ------------------------------------------------------------------ 회사 목록
def companies():
    ind = arg("--industry", "all")
    files = []
    if ind in ("all", "cosmetics"):
        files.append(("cosmetics", ROOT / "config" / "companies.json"))
    for p in sorted((ROOT / "config").glob("*/companies.json")):
        if ind in ("all", p.parent.name):
            files.append((p.parent.name, p))
    seen, out = set(), []
    for name, p in files:
        try:
            for c in json.loads(p.read_text("utf-8")):
                if c.get("code") and c["code"] not in seen and not c.get("foreign"):
                    seen.add(c["code"])
                    out.append({**c, "industry": name})
        except Exception as e:  # noqa: BLE001
            log("목록 읽기 실패", p, e)
    only = arg("--code")
    if only:
        out = [c for c in out if c["code"] in only.split(",")]
    return out


def corp_codes(key):
    body = get("corpCode.xml", {"crtfc_key": key}, raw=True)
    if not body or body[:2] != b"PK":
        return {}
    z = zipfile.ZipFile(io.BytesIO(body))
    root = ET.fromstring(z.read(z.namelist()[0]))
    return {(el.findtext("stock_code") or "").strip(): el.findtext("corp_code")
            for el in root.iter("list") if (el.findtext("stock_code") or "").strip()}


# ------------------------------------------------------------------ 재무제표 계정
def _n(s):
    return (s or "").replace(" ", "")


BS = {  # 필드: (account_id 후보, 계정명 후보)
    "assets": (["ifrs-full_Assets"], ["자산총계"]),
    "cash": (["ifrs-full_CashAndCashEquivalents"], ["현금및현금성자산"]),
    "st_fin": (["dart_ShortTermDepositsNotClassifiedAsCashEquivalents", "ifrs-full_ShortTermInvestments"], ["단기금융상품", "단기금융자산", "단기투자자산"]),
    "ar": (["dart_ShortTermTradeReceivable", "ifrs-full_TradeReceivables", "ifrs-full_CurrentTradeReceivables"], ["매출채권", "매출채권및기타채권", "매출채권및기타유동채권", "단기매출채권"]),
    "inv": (["ifrs-full_Inventories"], ["재고자산"]),
    "ppe": (["ifrs-full_PropertyPlantAndEquipment"], ["유형자산"]),
    "intang": (["ifrs-full_IntangibleAssetsOtherThanGoodwill", "ifrs-full_IntangibleAssetsAndGoodwill"], ["무형자산"]),
    "goodwill": (["ifrs-full_Goodwill"], ["영업권"]),
    "rou": (["ifrs-full_RightofuseAssets"], ["사용권자산"]),
    "assoc": (["ifrs-full_InvestmentsInAssociates", "ifrs-full_InvestmentsAccountedForUsingEquityMethod",
               "dart_InvestmentsInSubsidiariesJointVenturesAndAssociates"], ["관계기업투자", "관계기업및공동기업투자", "지분법적용투자주식"]),
    "liab": (["ifrs-full_Liabilities"], ["부채총계"]),
    "ap": (["dart_ShortTermTradePayables", "ifrs-full_TradePayables", "ifrs-full_CurrentTradePayables"], ["매입채무", "매입채무및기타채무", "매입채무및기타유동채무"]),
    "equity_total": (["ifrs-full_Equity"], ["자본총계"]),
    "equity_parent": (["ifrs-full_EquityAttributableToOwnersOfParent"], ["지배기업의소유주에게귀속되는자본", "지배기업소유주지분", "지배기업의소유지분"]),
    "minority": (["ifrs-full_NoncontrollingInterests"], ["비지배지분"]),
    "capital": (["ifrs-full_IssuedCapital"], ["자본금"]),
}
IS = {
    "rev": (["ifrs-full_Revenue"], ["매출액", "수익(매출액)", "영업수익", "매출"]),
    "cogs": (["ifrs-full_CostOfSales"], ["매출원가", "영업비용"]),
    "gp": (["ifrs-full_GrossProfit"], ["매출총이익", "매출총이익(손실)"]),
    "sga": (["dart_TotalSellingGeneralAdministrativeExpenses", "ifrs-full_SellingGeneralAndAdministrativeExpense"], ["판매비와관리비", "판매비및관리비"]),
    "op": (["dart_OperatingIncomeLoss"], ["영업이익", "영업이익(손실)", "영업손익"]),
    "pretax": (["ifrs-full_ProfitLossBeforeTax"], ["법인세비용차감전순이익", "법인세비용차감전순이익(손실)", "법인세차감전순이익"]),
    "tax": (["ifrs-full_IncomeTaxExpenseContinuingOperations"], ["법인세비용", "법인세비용(수익)"]),
    "ni_total": (["ifrs-full_ProfitLoss"], ["당기순이익", "당기순이익(손실)", "분기순이익", "반기순이익"]),
    "ni": (["ifrs-full_ProfitLossAttributableToOwnersOfParent"], ["지배기업의소유주에게귀속되는당기순이익", "지배기업소유주지분", "지배기업의소유주"]),
}
CF = {
    "ocf": (["ifrs-full_CashFlowsFromUsedInOperatingActivities"], ["영업활동현금흐름", "영업활동으로인한현금흐름"]),
    "icf": (["ifrs-full_CashFlowsFromUsedInInvestingActivities"], ["투자활동현금흐름", "투자활동으로인한현금흐름"]),
    "fincf": (["ifrs-full_CashFlowsFromUsedInFinancingActivities"], ["재무활동현금흐름", "재무활동으로인한현금흐름"]),
    "capex": (["ifrs-full_PurchaseOfPropertyPlantAndEquipment"], ["유형자산의취득", "유형자산취득"]),
    "div_paid": (["ifrs-full_DividendsPaidClassifiedAsFinancingActivities", "ifrs-full_DividendsPaid"], ["배당금의지급", "배당금지급", "현금배당금의지급"]),
    "buyback": (["ifrs-full_PaymentsToAcquireOrRedeemEntitysShares"], ["자기주식의취득", "자기주식취득"]),
}


def pick(rows, spec, col):
    ids, names = spec
    h = next((r for r in rows if r.get("account_id") in ids), None)
    if not h:
        nn = [_n(x) for x in names]
        h = next((r for r in rows if _n(r.get("account_nm")) in nn), None)
    return num(h.get(col)) if h else None


def extract(allrows, col):
    """col: thstrm_amount(당기) | frmtrm_amount(전기)."""
    bs = [r for r in allrows if r.get("sj_div") == "BS"]
    is_ = [r for r in allrows if r.get("sj_div") in ("IS", "CIS")]
    cf = [r for r in allrows if r.get("sj_div") == "CF"]
    out = {}
    for f, sp in BS.items():
        v = pick(bs, sp, col)
        if v is not None:
            out[f] = v
    debt = 0
    for r in bs:
        nm = _n(r.get("account_nm"))
        if (("차입금" in nm or nm in ("사채", "유동성사채", "전환사채", "신주인수권부사채", "교환사채", "유동성장기부채"))
                and not any(x in nm for x in ("상환", "이자", "리스", "합계", "할인", "조정"))):
            debt += num(r.get(col)) or 0
    out["debt"] = debt
    lease = sum(num(r.get(col)) or 0 for r in bs if "리스부채" in _n(r.get("account_nm")) and "합계" not in _n(r.get("account_nm")))
    if lease:
        out["lease"] = lease
    col_is = "thstrm_add_amount" if col == "thstrm_amount" and any(num(r.get("thstrm_add_amount")) is not None for r in is_) else col
    for f, sp in IS.items():
        v = pick(is_, sp, col_is)
        if v is not None:
            out[f] = v
    for f, sp in CF.items():
        v = pick(cf, sp, col)
        if v is not None:
            out[f] = abs(v) if f in ("capex", "div_paid", "buyback") else v
    dep = [num(r.get(col)) for r in cf if "감가상각" in _n(r.get("account_nm")) and "누계" not in _n(r.get("account_nm")) and num(r.get(col)) is not None]
    amo = [num(r.get(col)) for r in cf if "무형자산상각" in _n(r.get("account_nm")) and num(r.get(col)) is not None]
    if dep:
        out["dep"] = sum(abs(x) for x in dep)
    if amo:
        out["amort"] = sum(abs(x) for x in amo)
    if "gp" not in out and out.get("rev") is not None and out.get("cogs") is not None:
        out["gp"] = out["rev"] - out["cogs"]
    if "ni" not in out and "ni_total" in out:
        out["ni"] = out["ni_total"]
    return {k: (round(v / 1_000_000) if isinstance(v, (int, float)) else v) for k, v in out.items()}  # 백만원


def fin(key, corp, year, reprt):
    for fs in ("CFS", "OFS"):
        j = get("fnlttSinglAcntAll.json", {"crtfc_key": key, "corp_code": corp, "bsns_year": year, "reprt_code": reprt, "fs_div": fs})
        time.sleep(0.12)
        if j and j.get("status") == "000" and j.get("list"):
            return fs, j["list"]
    return None, None


# ------------------------------------------------------------------ 배당·주주
def dividends(key, corp, last_fy):
    out = {}
    for y in range(last_fy, FIRST_YEAR - 1, -3):
        j = get("alotMatter.json", {"crtfc_key": key, "corp_code": corp, "bsns_year": y, "reprt_code": "11011"})
        time.sleep(0.12)
        if not j or j.get("status") != "000":
            continue
        for r in j.get("list", []):
            se = _n(r.get("se"))
            kind = _n(r.get("stock_knd"))
            fld = ("dps" if "주당현금배당금" in se and (not kind or kind.startswith("보통")) else
                   "payout" if "현금배당성향" in se else
                   "yield" if "현금배당수익률" in se and (not kind or kind.startswith("보통")) else
                   "div_total" if "현금배당금총액" in se else None)
            if not fld:
                continue
            for col, yy in (("thstrm", y), ("frmtrm", y - 1), ("lwfr", y - 2)):
                v = num(r.get(col))
                if v is not None:
                    out.setdefault(str(yy), {}).setdefault(fld, v)   # 최신 보고서 값 우선
    return dict(sorted(out.items()))


def holders(key, corp, last_fy):
    for y in (last_fy, last_fy - 1):
        j = get("hyslrSttus.json", {"crtfc_key": key, "corp_code": corp, "bsns_year": y, "reprt_code": "11011"})
        time.sleep(0.12)
        if j and j.get("status") == "000" and j.get("list"):
            rows, total = [], None
            for r in j["list"]:
                if _n(r.get("stock_knd")) and not _n(r.get("stock_knd")).startswith("보통"):
                    continue
                pct = num(r.get("trmend_posesn_stock_qota_rt"))
                nm = (r.get("nm") or "").strip()
                if nm in ("계", "합계"):
                    total = pct
                elif nm and nm != "-":
                    rows.append({"nm": nm, "rel": (r.get("relate") or "").strip(), "pct": pct})
            if total is None:
                total = round(sum(x["pct"] or 0 for x in rows), 2)
            return {"year": y, "total": total, "list": sorted(rows, key=lambda x: -(x["pct"] or 0))[:12]}
    return None


def major5(key, corp):
    j = get("majorstock.json", {"crtfc_key": key, "corp_code": corp})
    time.sleep(0.12)
    if not j or j.get("status") != "000":
        return []
    last = {}
    for r in j.get("list", []):
        nm = (r.get("repror") or "").strip()
        d = r.get("rcept_dt") or ""
        if nm and (nm not in last or d > last[nm]["date"]):
            last[nm] = {"date": d, "nm": nm, "pct": num(r.get("stkrt")), "chg": num(r.get("stkrt_irds")),
                        "reason": (r.get("report_resn") or "").strip()[:80]}
    return sorted(last.values(), key=lambda x: x["date"], reverse=True)[:15]


# ------------------------------------------------------------------ 사업보고서 본문 구간
def _xml_to_text(x):
    x = re.sub(r"(?is)<(script|style).*?</\1>", "", x)
    x = re.sub(r"(?i)</?(TR)[^>]*>", "\n", x)
    x = re.sub(r"(?i)<(TD|TH|TE|TU)[^>]*>", " | ", x)
    x = re.sub(r"(?i)<(P|BR|TITLE|SECTION-\d)[^>]*>", "\n", x)
    x = re.sub(r"<[^>]+>", "", x)
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&cr;", "\n")):
        x = x.replace(a, b)
    x = re.sub(r"[ \t ]+", " ", x)
    return re.sub(r"\n\s*\n+", "\n", x).strip()


def _sec(t, start, end, cap=12000):
    best = ""
    for m in re.finditer(start, t):
        e = re.search(end, t[m.end():])
        seg = t[m.start(): m.end() + (e.start() if e else 30000)]
        if len(seg) > len(best):
            best = seg
    return best[:cap]


SECTIONS = {
    "history": (r"2\.\s*회사의\s*연혁", r"\n\s*3\.\s*자본금\s*변동"),
    "overview": (r"1\.\s*회사의\s*개요", r"\n\s*2\.\s*회사의\s*연혁"),
    "dividend": (r"\d\.\s*배당에\s*관한\s*사항", r"\n\s*\d\.\s*(증권의\s*발행|기타\s*재무)"),
    "shareholders": (r"VII\.\s*주주에\s*관한\s*사항", r"\n\s*VIII\.\s*임원"),
    "executives": (r"1\.\s*임원\s*및\s*직원\s*등의\s*현황", r"\n\s*2\.\s*임원의\s*보수"),
    "related": (r"X\.\s*대주주\s*등과의\s*거래내용", r"\n\s*XI\.\s*그\s*밖에"),
}


def annual_doc(key, corp, code):
    bgn = (TODAY - dt.timedelta(days=500)).strftime("%Y%m%d")
    j = get("list.json", {"crtfc_key": key, "corp_code": corp, "bgn_de": bgn, "end_de": TODAY.strftime("%Y%m%d"),
                          "pblntf_ty": "A", "page_count": 100})
    items = (j or {}).get("list", [])
    ann = next((i for i in sorted(items, key=lambda i: i["rcept_dt"], reverse=True)
                if i["report_nm"].strip().startswith("사업보고서") or "] 사업보고서" in i["report_nm"]), None)
    if not ann:
        return None
    body = get("document.xml", {"crtfc_key": key, "rcept_no": ann["rcept_no"]}, raw=True)
    if not body or body[:2] != b"PK":
        return None
    z = zipfile.ZipFile(io.BytesIO(body))
    names = sorted(z.namelist(), key=lambda nm: z.getinfo(nm).file_size, reverse=True)
    raw = z.read(names[0])
    x = raw.decode("utf-8", errors="ignore")
    if "사업" not in x:
        x = raw.decode("euc-kr", errors="ignore")
    t = _xml_to_text(x)
    out = {"report_nm": ann["report_nm"].strip(), "rcept_no": ann["rcept_no"],
           "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={ann['rcept_no']}"}
    for k, (a, b) in SECTIONS.items():
        s = _sec(t, a, b)
        if s:
            out[k] = s
    return out


# ------------------------------------------------------------------ 회사 1곳
def collect(key, corp, c, cache):
    rec = cache or {"code": c["code"], "name": c["name"], "annual": {}}
    rec["name"], rec["industry"] = c["name"], c["industry"]
    ann = rec.setdefault("annual", {})
    # 최근 사업연도: 올해-1 사업보고서가 있으면 그 해, 아직 없으면(1~3월) 올해-2
    last_fy = TODAY.year - 1
    if not ann.get(str(last_fy), {}).get("_final"):
        fs, rows = fin(key, corp, last_fy, "11011")
        if not rows:
            last_fy -= 1
    for y in range(last_fy, FIRST_YEAR, -1):
        if ann.get(str(y), {}).get("_final"):
            continue
        fs, rows = fin(key, corp, y, "11011")
        if not rows:
            continue
        cur = extract(rows, "thstrm_amount")
        keep = {k: v for k, v in ann.get(str(y), {}).items() if not k.startswith("_")} if ann.get(str(y), {}).get("_restated") else {}
        ann[str(y)] = {**cur, **keep, "_fs": fs, "_final": True, "_restated": bool(keep)}
        prev = extract(rows, "frmtrm_amount")   # 재작성 전기 금액 우선 (리포트 부록 주1)
        if prev.get("rev") is not None:
            old = ann.get(str(y - 1), {})
            ann[str(y - 1)] = {**old, **prev, "_fs": fs, "_restated": True}
    # 최신 분기(분기말 재무상태표·누적 손익·누적 현금흐름) — 사업연도 이후 분기만
    cands = [(y, rc, p) for y in (TODAY.year, TODAY.year - 1) for rc, p in (("11014", "Q3"), ("11012", "H1"), ("11013", "Q1")) if y > last_fy]
    for y, rc, p in cands:
        per = f"{y}{p}"
        if (rec.get("latest") or {}).get("period") == per:
            break
        fs, rows = fin(key, corp, y, rc)
        if rows:
            rec["latest"] = {"period": per, **extract(rows, "thstrm_amount"), "_fs": fs}
            break
    if not cands:
        rec.pop("latest", None)
    if not rec.get("div_checked") == str(last_fy):
        rec["dividends"] = dividends(key, corp, last_fy)
        rec["holders"] = holders(key, corp, last_fy)
        rec["div_checked"] = str(last_fy)
    rec["major5"] = major5(key, corp)
    if "--no-docs" not in ARGV and rec.get("docs_fy") != str(last_fy):
        try:
            d = annual_doc(key, corp, c["code"])
            if d:
                rec["docs"] = d
                rec["docs_fy"] = str(last_fy)
        except LimitExceeded:
            raise
        except Exception as e:  # noqa: BLE001
            log("  본문 실패", c["name"], e)
    rec["fetched"] = TODAY.isoformat()
    rec["unit"] = "백만원"
    return rec


def main():
    key = os.environ.get("DART_API_KEY", "").strip()
    if not key:
        log("DART_API_KEY 없음")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    cos = companies()
    log(f"대상 {len(cos)}개사")
    codes = corp_codes(key)
    if not codes:
        log("corpCode 조회 실패")
        return 1
    done = 0
    for i, c in enumerate(cos, 1):
        corp = codes.get(c["code"])
        if not corp:
            continue
        p = OUT / f"{c['code']}.json"
        cache = json.loads(p.read_text("utf-8")) if p.exists() else None
        if cache and cache.get("fetched") == TODAY.isoformat() and "--force" not in ARGV:
            continue
        try:
            rec = collect(key, corp, c, cache)
        except LimitExceeded as e:
            log("DART 하루 호출 한도 초과 — 여기까지 저장하고 멈춥니다. 내일 다시 실행하면 이어서 받습니다.", e)
            break
        p.write_text(json.dumps(rec, ensure_ascii=False, indent=0), "utf-8")
        done += 1
        print(f"  ({i}/{len(cos)}) {c['name']} · 호출 누적 {CALLS}", flush=True)
    log(f"완료 {done}개사, DART 호출 {CALLS}회")
    return 0


if __name__ == "__main__":
    sys.exit(main())
