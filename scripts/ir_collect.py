#!/usr/bin/env python3
"""업종 공용 IR 자료 수집기 (표준 라이브러리만 사용).

DART 공시 목록에서 회사별 최근 N년의 '기업설명회(IR)개최' 공시를 찾아
공시 원문 링크(첨부된 IR 발표자료 포함)와 공시 본문 요약(일시·대상·설명회 내용)을
docs/<업종>/data/ir.json (화장품은 docs/data/ir.json) 에 저장한다.

DART는 해외 IP를 막으므로 국내 PC에서 실행한다.
  set /p DART_API_KEY=<..\\dart_key.txt
  python scripts\\ir_collect.py --industry apparel        (업종: cosmetics semi chem battery apparel ...)
  옵션: --years 3 (기본 3년), --pdf 4 (회사당 최근 몇 건의 첨부 PDF를 내려받을지, 기본 4, 0이면 안 받음)

PDF는 docs/<업종>/ir/<종목코드>/<날짜>_<접수번호>.pdf (화장품은 docs/ir/...)에 저장해 대시보드 원문 링크로 쓰고,
텍스트는 raw/<업종>/ir_text/<종목코드>_<날짜>_<접수번호>.txt (화장품은 raw/ir_text/...)로 뽑는다(pypdf 필요: pip install pypdf).
ir.json 스키마: {"source","fetched","years","companies":{코드:[{"rcept_no","date","title","url","body","pdfs":[{"path","url","pages","text"}]}]}}
  url = DART 공시 원문, pdfs[].path = 저장소 기준 경로(docs 아래), pdfs[].text = 추출 텍스트 경로(raw 아래)
"""
import datetime as dt
import io
import json
import os
import re
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import update as U  # noqa: E402  (update.py의 http_get·dart_corp_codes·_xml_to_text 재사용, --industry도 그대로 해석)

NPDF = int(sys.argv[sys.argv.index("--pdf") + 1]) if "--pdf" in sys.argv else 4
PDF_DIR = U.DATA.parent / "ir"          # docs/<업종>/ir  (화장품: docs/ir)
TXT_DIR = U.RAW / "ir_text"             # raw/<업종>/ir_text (화장품: raw/ir_text)
YEARS = int(sys.argv[sys.argv.index("--years") + 1]) if "--years" in sys.argv else 3


def ir_list(key, corp, bgn):
    out, page = [], 1
    while True:
        txt = U.http_get(f"{U.DART}/list.json", {"crtfc_key": key, "corp_code": corp, "bgn_de": bgn,
                                                 "end_de": U.TODAY.strftime("%Y%m%d"), "page_no": page, "page_count": 100})
        try:
            j = json.loads(txt or "{}")
        except json.JSONDecodeError:
            break
        for r in j.get("list") or []:
            if "기업설명회" in r.get("report_nm", "") or "IR" in r.get("report_nm", "").upper().split("(")[0]:
                out.append(r)
        if page >= int(j.get("total_page") or 1):
            break
        page += 1
        time.sleep(0.2)
    return out


def ir_body(key, rcept_no):
    body = U.http_get(f"{U.DART}/document.xml", {"crtfc_key": key, "rcept_no": rcept_no}, raw=True)
    if not body or body[:2] != b"PK":
        return ""
    try:
        z = zipfile.ZipFile(io.BytesIO(body))
        raw = z.read(max(z.namelist(), key=lambda nm: z.getinfo(nm).file_size))
        x = raw.decode("utf-8", errors="ignore")
        if "설명회" not in x:
            x = raw.decode("euc-kr", errors="ignore")
        t = U._xml_to_text(x)
    except Exception:  # noqa: BLE001
        return ""
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n", t).strip()
    return t[:1500]


def _get(url, raw=True):
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://dart.fss.or.kr/"})
        with urllib.request.urlopen(req, timeout=60) as r:
            b = r.read()
        return b if raw else b.decode("utf-8", "ignore")
    except Exception as e:  # noqa: BLE001
        U.log("받기 실패:", url, e)
        return None


def ir_pdfs(key, rcept_no):
    """IR 공시에 첨부된 PDF 원본(bytes 목록). ① document.xml zip 안의 PDF ② DART 뷰어의 첨부 문서 PDF 다운로드."""
    out = []
    body = U.http_get(f"{U.DART}/document.xml", {"crtfc_key": key, "rcept_no": rcept_no}, raw=True)
    if body and body[:2] == b"PK":
        try:
            z = zipfile.ZipFile(io.BytesIO(body))
            out += [z.read(n) for n in z.namelist() if n.lower().endswith(".pdf")]
        except Exception:  # noqa: BLE001
            pass
    if out:
        return out
    page = _get(f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}", raw=False) or ""
    dcms = set(re.findall(r"dcmNo=(\d+)", page)) | set(re.findall(r"\['dcmNo'\]\s*=\s*\"(\d+)\"", page))
    for dcm in sorted(dcms):
        lst = _get(f"https://dart.fss.or.kr/pdf/download/main.do?rcp_no={rcept_no}&dcm_no={dcm}", raw=False) or ""
        links = re.findall(r'href="(/pdf/download/[^"]+)"', lst) or [f"/pdf/download/pdf.do?rcp_no={rcept_no}&dcm_no={dcm}"]
        for ln in links:
            b = _get("https://dart.fss.or.kr" + ln.replace("&amp;", "&"))
            if b and b[:4] == b"%PDF":
                out.append(b)
        time.sleep(0.3)
    return out


def pdf_text(path):
    try:
        from pypdf import PdfReader
    except ImportError:
        return None, None
    try:
        rd = PdfReader(str(path))
        return len(rd.pages), "\n\n".join(f"[p.{i + 1}]\n" + (pg.extract_text() or "") for i, pg in enumerate(rd.pages))
    except Exception as e:  # noqa: BLE001
        U.log("PDF 텍스트 추출 실패:", path, e)
        return None, None


def save_pdfs(key, code, x):
    if x.get("pdfs"):
        return
    pdfs = []
    for i, b in enumerate(ir_pdfs(key, x["rcept_no"])[:3]):
        nm = f"{x['date']}_{x['rcept_no']}" + (f"_{i + 1}" if i else "")
        pp = PDF_DIR / code / f"{nm}.pdf"
        pp.parent.mkdir(parents=True, exist_ok=True)
        pp.write_bytes(b)
        rec = {"path": pp.relative_to(U.ROOT).as_posix(), "url": pp.relative_to(U.DATA.parent).as_posix(), "kb": len(b) // 1024}
        n, t = pdf_text(pp)
        if t:
            tp = TXT_DIR / f"{code}_{nm}.txt"
            tp.parent.mkdir(parents=True, exist_ok=True)
            tp.write_text(t, "utf-8")
            rec.update(pages=n, text=tp.relative_to(U.ROOT).as_posix())
        pdfs.append(rec)
    x["pdfs"] = pdfs


def main():
    key = (os.getenv("DART_API_KEY") or "").strip().split("=")[-1].strip()
    if not key:
        print("DART_API_KEY 환경변수가 없어요.")
        return 1
    cfg = json.loads((U.CONFIG / "companies.json").read_text("utf-8"))
    cfg = cfg["companies"] if isinstance(cfg, dict) else cfg
    codes = U.dart_corp_codes(key)
    bgn = (U.TODAY - dt.timedelta(days=365 * YEARS)).strftime("%Y%m%d")
    old = (U.load("ir.json") or {}).get("companies", {})
    res = {}
    for c in cfg:
        corp = codes.get(c["code"])
        if not corp:
            continue
        have = {x["rcept_no"]: x for x in old.get(c["code"], [])}
        items = []
        for r in ir_list(key, corp, bgn):
            rn = r["rcept_no"]
            x = have.get(rn) or {"rcept_no": rn, "date": f"{rn[:4]}-{rn[4:6]}-{rn[6:8]}", "title": r["report_nm"].strip(),
                                 "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rn}", "body": ir_body(key, rn)}
            items.append(x)
            time.sleep(0.2)
        items.sort(key=lambda x: x["rcept_no"], reverse=True)
        for x in items[:NPDF]:
            save_pdfs(key, c["code"], x)
            if x.get("pdfs"):
                U.log("  PDF:", x["date"], [p["path"] for p in x["pdfs"]])
        if items:
            res[c["code"]] = items[:12]
            U.log("IR:", c["name"], len(items), "건, 최신", items[0]["date"])
        time.sleep(0.2)
    try:
        import pypdf  # noqa: F401
    except ImportError:
        U.log("pypdf가 없어 PDF 텍스트는 뽑지 않았어요. 'pip install pypdf' 후 다시 실행하면 채워져요.")
    U.save("ir.json", {"source": "DART 공시(기업설명회(IR)개최) — 원문 링크에 IR 발표자료 첨부", "fetched": U.TODAY.isoformat(),
                       "years": YEARS, "companies": res})
    return 0


if __name__ == "__main__":
    sys.exit(main())
