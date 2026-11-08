"""IRGO(m.irgo.co.kr) 회사별 IR 자료를 GitHub Actions에서 수집한다.
- 목록: m.irgo.co.kr/IR-COMP/<코드> → raw/<업종>/irgo/<코드>.html
- 상세: IR자료/<id>/TB/... 와 '해당기업 IR팀' 리포트 페이지 → 첨부 PDF 원본 링크(file.irgo.co.kr)
- 텍스트: raw/<업종>/ir_text/<코드>_<날짜>_<id>.txt (pypdf)
- 목록 JSON: docs/<업종>/data/ir_web.json {fetched, source, companies:{code:[{date,title,kind,page,pdf,text,kb,pages}]}}"""
import json, os, re, sys, time, argparse, html, urllib.request, urllib.parse
ap = argparse.ArgumentParser()
ap.add_argument("--industry", default=""); ap.add_argument("--codes", default="")
ap.add_argument("--pdf", type=int, default=6, help="회사당 PDF 내려받을 최근 자료 수")
ap.add_argument("--probe", action="store_true", help="상세 페이지 HTML만 저장")
a = ap.parse_args()
ind = a.industry
cfg = f"config/{ind}/companies.json" if ind else "config/companies.json"
cj = json.load(open(cfg, encoding="utf-8")); L = cj if isinstance(cj, list) else cj.get("companies", cj)
codes = a.codes.split(",") if a.codes else [c["code"] for c in L]
RAW = f"raw/{ind}" if ind else "raw"; DOC = f"docs/{ind}" if ind else "docs"
os.makedirs(f"{RAW}/irgo", exist_ok=True); os.makedirs(f"{RAW}/ir_text", exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148",
      "Referer": "https://m.irgo.co.kr/"}
def get(u, binary=False):
    p = urllib.parse.urlsplit(u); u = urllib.parse.urlunsplit(p._replace(path=urllib.parse.quote(p.path)))
    b = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40).read()
    return b if binary else b.decode("utf-8", "replace")
def items(h):
    out = []
    for m in re.finditer(r'data-href="(https://m\.irgo\.co\.kr/(IR자료|리포트)/(\d+)/[^"]+)">(.*?)</li>', h, re.S):
        url, kind, iid, body = m.groups()
        t = re.search(r'<h3[^>]*>(.*?)</h3>', body, re.S); tail = re.search(r'tail_txt[^>]*>(.*?)</em>', body, re.S)
        title = html.unescape(re.sub(r'<[^>]+>', '', t.group(1))).strip() if t else ""
        who, _, date = (html.unescape(tail.group(1)).partition("I") if tail else ("", "", ""))
        who, date = who.strip(), date.strip()
        if kind == "리포트" and "IR팀" not in who: continue   # 증권사 리포트는 제외, 회사가 낸 실적자료만
        fn = re.search(r'\[A\d{6}\][^&<]*?\.pdf', body)
        out.append({"id": iid, "kind": "IR자료" if kind == "IR자료" else "실적자료", "date": date, "title": title,
                    "page": url, "file": fn.group(0) if fn else ""})
    seen, res = set(), []
    for i in sorted(out, key=lambda x: x["date"], reverse=True):
        if i["id"] in seen: continue
        seen.add(i["id"]); res.append(i)
    return res
def pdf_links(h):
    c = re.findall(r'(?:href|src|data-src|data-url)="([^"]+?\.pdf[^"]*)"', h, re.I)
    c += re.findall(r'(https?://[^"\'\s<>]+?(?:download|fileDown|FileDown|attach)[^"\'\s<>]*)', h)
    c += re.findall(r"'(https?://[^']+?\.pdf[^']*)'", h, re.I)
    return [html.unescape(x) if x.startswith("http") else urllib.parse.urljoin("https://m.irgo.co.kr/", html.unescape(x)) for x in c]
path = f"{DOC}/data/ir_web.json"
db = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {"companies": {}}
for c in codes:
    try:
        h = get("https://m.irgo.co.kr/IR-COMP/" + c)
    except Exception as e:
        print(c, "목록 실패", e); continue
    open(f"{RAW}/irgo/{c}.html", "w", encoding="utf-8").write(h)
    its = items(h); print(c, "자료", len(its))
    prev = {i["id"]: i for i in db["companies"].get(c, [])}
    # 최근 N건 + 과거 비교용으로 직전 3개 연도 각각에서 가장 늦은 자료 1건
    pick = set(range(min(a.pdf, len(its))))
    if its:
        y0 = int(its[0]["date"][:4] or 0)
        for y in (y0 - 1, y0 - 2, y0 - 3):
            k = next((n for n, i in enumerate(its) if i["date"].startswith(str(y))), None)
            if k is not None: pick.add(k)
    for n, it in enumerate(its):
        if it["id"] in prev and prev[it["id"]].get("pdf"):
            it.update({k: prev[it["id"]][k] for k in ("pdf", "text", "kb", "pages") if k in prev[it["id"]]}); continue
        if n not in pick: continue
        try:
            d = get(it["page"]); time.sleep(0.7)
        except Exception as e:
            print("  상세 실패", it["page"], e); continue
        if a.probe:
            open(f"{RAW}/irgo/{c}_{it['id']}.html", "w", encoding="utf-8").write(d); continue
        for u in pdf_links(d):
            try:
                b = get(u, binary=True)
            except Exception as e:
                print("  PDF 실패", u, e); continue
            if not b.startswith(b"%PDF"): continue
            # 원문 PDF는 저장소에 올리지 않고(용량) IRGO 원본 링크로 연결, 텍스트만 저장
            it["pdf"] = u; it["kb"] = len(b) // 1024
            try:
                import io
                from pypdf import PdfReader
                r = PdfReader(io.BytesIO(b)); it["pages"] = len(r.pages)
                txt = "\n\n".join(f"[p{i+1}]\n" + (p.extract_text() or "") for i, p in enumerate(r.pages))
                tp = f"{RAW}/ir_text/{c}_{it['date']}_{it['id']}.txt"; open(tp, "w", encoding="utf-8").write(txt); it["text"] = tp
            except Exception as e:
                print("  텍스트 실패", e)
            print("  PDF", it["date"], it["title"][:30], it["kb"], "KB"); break
        else:
            print("  PDF 링크 없음", it["page"])
    db["companies"][c] = [i for n, i in enumerate(its) if n < 30 or i.get("pdf")]
    time.sleep(1)
if not a.probe:
    db.update({"source": "IRGO (m.irgo.co.kr) · 상장사 IR 자료", "fetched": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())})
    os.makedirs(f"{DOC}/data", exist_ok=True); json.dump(db, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
