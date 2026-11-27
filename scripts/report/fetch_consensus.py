"""증권사 컨센서스(네이버 금융·FnGuide 제공) 하루 한 번 스냅숏 → raw/consensus/history.json

GitHub Actions에서 실행한다(클라우드 작업 환경은 네이버 접속이 막혀 있음). 매일 쌓아 두면
리포트 화면 '가이던스와 컨센서스 비교'에 최근 몇 개월의 컨센서스 변화와 주가 변화를 나란히 보여 준다.

저장 형식: {"updated": "...", "series": {code: [[date, {"cy": {"y","rev","op","ni"}, "nq": {"q","op"},
            "tp": 목표주가 평균, "rec": 투자의견 평균, "price": 종가}], ...]}}
사용: python scripts/report/fetch_consensus.py [--codes 005930,000660] [--limit N]
"""
import datetime as dt
import json
import pathlib
import re
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "raw" / "consensus" / "history.json"
LIST = ROOT / "docs" / "report" / "data" / "list.json"
UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://m.stock.naver.com/"}


def get(url):
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=15) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            time.sleep(1 + i)
    return None


def num(s):
    try:
        return float(str(s).replace(",", ""))
    except Exception:  # noqa: BLE001
        return None


def consensus_cols(j):
    """재무 JSON에서 컨센서스(추정) 칸만 → [(key, title, {rev,op,ni})] (억원)."""
    fi = (j or {}).get("financeInfo") or j or {}
    out = []
    for t in fi.get("trTitleList") or []:
        if (t.get("isConsensus") or "N") != "Y":
            continue
        key = t.get("key") or ""
        rec = {}
        for r in fi.get("rowList") or []:
            nm = r.get("title", "")
            f = "rev" if nm.startswith("매출") else "op" if nm.startswith("영업이익") and "률" not in nm else "ni" if nm.startswith("지배주주순이익") else None
            if f and f not in rec:
                v = num(((r.get("columns") or {}).get(key) or {}).get("value"))
                if v is not None:
                    rec[f] = v
        if rec:
            out.append((key, t.get("title", ""), rec))
    return out


def find_key(o, pat):
    """중첩 JSON에서 이름이 pat에 맞는 첫 값."""
    if isinstance(o, dict):
        for k, v in o.items():
            if re.search(pat, k, re.I) and not isinstance(v, (dict, list)):
                return v
        for v in o.values():
            r = find_key(v, pat)
            if r is not None:
                return r
    elif isinstance(o, list):
        for v in o:
            r = find_key(v, pat)
            if r is not None:
                return r
    return None


def snap(code):
    s = {}
    a = consensus_cols(get(f"https://m.stock.naver.com/api/stock/{code}/finance/annual"))
    if a:
        key, title, rec = a[0]
        m = re.match(r"(20\d\d)", key) or re.match(r"(20\d\d)", title)
        s["cy"] = {"y": int(m.group(1)) if m else None, **rec}
        if len(a) > 1:
            key2, title2, rec2 = a[1]
            m2 = re.match(r"(20\d\d)", key2) or re.match(r"(20\d\d)", title2)
            s["ny"] = {"y": int(m2.group(1)) if m2 else None, **rec2}
    q = consensus_cols(get(f"https://m.stock.naver.com/api/stock/{code}/finance/quarter"))
    if q:
        key, title, rec = q[0]
        m = re.match(r"(20\d\d)(\d\d)", key) or re.match(r"(20\d\d)\.(\d\d)", title)
        s["nq"] = {"q": f"{m.group(1)}Q{(int(m.group(2)) - 1) // 3 + 1}" if m else title, **rec}
    i = get(f"https://m.stock.naver.com/api/stock/{code}/integration")
    if i:
        tp = num(find_key(i, r"priceTargetMean|targetPrice"))
        rc = num(find_key(i, r"recommMean"))
        if tp:
            s["tp"] = tp
        if rc:
            s["rec"] = rc
        cp = None
        for t in i.get("totalInfos") or []:
            if t.get("code") in ("lastClosePrice", "closePrice"):
                cp = num(t.get("value"))
        if cp is None:
            cp = num(find_key(i, r"^closePrice$"))
        if cp:
            s["price"] = cp
    return s


def main():
    codes = None
    if "--codes" in sys.argv:
        codes = sys.argv[sys.argv.index("--codes") + 1].split(",")
    else:
        L = json.loads(LIST.read_text("utf-8"))["companies"]
        codes = list(dict.fromkeys(c["code"] for c in sorted(L, key=lambda x: -(x.get("mcap") or 0))))
    if "--limit" in sys.argv:
        codes = codes[: int(sys.argv[sys.argv.index("--limit") + 1])]
    H = json.loads(OUT.read_text("utf-8")) if OUT.exists() else {"series": {}}
    today = (dt.datetime.utcnow() + dt.timedelta(hours=9)).date().isoformat()
    ok = 0
    for n, code in enumerate(codes):
        s = snap(code)
        if not s:
            continue
        ser = H["series"].setdefault(code, [])
        ser[:] = [r for r in ser if r[0] != today] + [[today, s]]
        ok += 1
        if n % 100 == 0:
            print(n, code, json.dumps(s, ensure_ascii=False)[:160], flush=True)
        time.sleep(0.15)
    H["updated"] = today
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(H, ensure_ascii=False, separators=(",", ":")), "utf-8")
    print(f"[consensus] {ok}/{len(codes)}개사 스냅숏 저장 ({today})")


if __name__ == "__main__":
    main()
