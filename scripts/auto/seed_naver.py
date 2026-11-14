"""DART 수집 전 임시 실적: 네이버 금융(모바일) 연간·분기 재무 요약 → docs/<업종>/data/companies.json (source="naver").
국내 PC에서 DART를 돌리면 source="dart"로 통째로 바뀌어요(update.py는 naver 출처를 10년치 새로 받아요).
GitHub Actions에서만 실행(클라우드 세션에서는 네이버 접속이 막혀 있어요).
사용: python scripts/auto/seed_naver.py --industry auto [--probe 005380]"""
import json, re, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IND = sys.argv[sys.argv.index("--industry") + 1] if "--industry" in sys.argv else "auto"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
      "Referer": "https://m.stock.naver.com/"}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def num(s):
    if s is None:
        return None
    s = str(s).replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


ROWS = {"rev": ("매출액", "영업수익", "매출"), "op": ("영업이익",), "ni": ("당기순이익(지배)", "지배주주순이익", "당기순이익"),
        "equity": ("자본총계(지배)", "지배주주지분", "자본총계")}


def parse(j, freq):
    """financeInfo.trTitleList [{key:'202412', isConsensus:'N', title:'2024.12.'}], rowList [{title, columns:{key:{value}}}]"""
    fi = j.get("financeInfo") or j
    titles = [t for t in fi.get("trTitleList", []) if str(t.get("isConsensus", "N")) == "N"]
    rows = {r.get("title", "").strip(): r.get("columns", {}) for r in fi.get("rowList", [])}
    out = {}
    for t in titles:
        k = str(t.get("key"))
        if not re.match(r"^\d{6}$", k):
            continue
        y, m = k[:4], int(k[4:])
        per = y if freq == "annual" else f"{y}Q{(m - 1) // 3 + 1}"
        rec = {}
        for f, names in ROWS.items():
            for n in names:
                if n in rows and k in rows[n]:
                    v = num((rows[n][k] or {}).get("value"))
                    if v is not None:
                        rec[f] = round(v * 100)  # 억원 → 백만원
                        break
        if rec.get("rev") is not None:
            out[per] = rec
    return out


def main():
    cfg = json.loads((ROOT / "config" / IND / "companies.json").read_text("utf-8"))
    dp = ROOT / "docs" / IND / "data" / "companies.json"
    old = {c["code"]: c for c in (json.loads(dp.read_text("utf-8")).get("companies", []) if dp.exists() else [])}
    if "--probe" in sys.argv:
        code = sys.argv[sys.argv.index("--probe") + 1]
        for f in ("annual", "quarter"):
            j = get(f"https://m.stock.naver.com/api/stock/{code}/finance/{f}")
            (ROOT / "raw" / IND).mkdir(parents=True, exist_ok=True)
            (ROOT / "raw" / IND / f"naver_probe_{f}.json").write_text(json.dumps(j, ensure_ascii=False, indent=1)[:200000], "utf-8")
            print(f, json.dumps(parse(j, f), ensure_ascii=False)[:500])
        return
    out, ok = [], 0
    for c in cfg:
        o = old.get(c["code"])
        if o and o.get("source") == "dart":  # DART 자료가 있으면 그대로
            out.append({**o, **c})
            continue
        rec = {**c, "annual": {}, "quarterly": {}, "source": "naver"}
        try:
            A = parse(get(f"https://m.stock.naver.com/api/stock/{c['code']}/finance/annual"), "annual")
            Qr = parse(get(f"https://m.stock.naver.com/api/stock/{c['code']}/finance/quarter"), "quarter")
        except Exception as e:  # noqa: BLE001
            print("실패:", c["name"], e)
            out.append(o or rec)
            continue
        rec["annual"] = {y: {k: v.get(k) for k in ("rev", "op", "ni")} | {"gp": None} for y, v in A.items()}
        rec["quarterly"] = {q: {k: v.get(k) for k in ("rev", "op", "ni")} | {"gp": None} for q, v in sorted(Qr.items())}
        last = sorted(Qr)[-1] if Qr else None
        if last and Qr[last].get("equity"):
            rec["bs"] = {"period": last, "equity": Qr[last]["equity"]}
        if rec["quarterly"]:
            ok += 1
        out.append(rec)
        time.sleep(0.3)
    dp.parent.mkdir(parents=True, exist_ok=True)
    dp.write_text(json.dumps({"updated": time.strftime("%Y-%m-%d"), "source_note": "DART 수집 전 네이버 금융 요약 재무(임시)", "companies": out},
                             ensure_ascii=False, indent=0), "utf-8")
    print("seed:", ok, "/", len(cfg))


if __name__ == "__main__":
    main()
