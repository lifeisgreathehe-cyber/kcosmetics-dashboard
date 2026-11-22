"""바이오 선행·동행성 보조 지표 (update-leadlag.yml이 계산 전에 실행) → docs/bio/data/leadlag_market.json

- 미국 바이오 지수 ETF 월말 종가(Yahoo Finance): XBI(SPDR S&P Biotech, 중소형 동일가중), IBB(iShares 나스닥 바이오)
- 공용 거시 지표(docs/shared/macro.json, update-turns.yml이 갱신)의 미국 10년 금리·원/달러·코스닥을 같은 months 배열로 옮겨 담음
Yahoo가 막히면 기존 파일 값을 유지한다.
"""
import datetime as dt, json, os, time, urllib.request
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
OUT = os.path.join(ROOT, "docs", "bio", "data", "leadlag_market.json")
SYMS = [("XBI", "XBI"), ("IBB", "IBB")]


def get(sym):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=25y&interval=1mo"
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=40) as r:
                res = json.loads(r.read().decode())["chart"]["result"][0]
            out = {}
            for t, c in zip(res["timestamp"], res["indicators"]["quote"][0]["close"]):
                if c is not None:
                    out[dt.datetime.utcfromtimestamp(t).strftime("%Y-%m")] = round(c, 2)
            return out
        except Exception as e:  # noqa: BLE001
            print("[bio leadlag] 실패", sym, e)
            time.sleep(3 * (i + 1))
    return None


def main():
    old = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    series = {}
    for sym, name in SYMS:
        s = get(sym)
        if not s and old.get("series", {}).get(name):
            s = {m: v for m, v in zip(old["months"], old["series"][name]) if v is not None}
        if s:
            series[name] = s
    try:
        mac = json.load(open(os.path.join(ROOT, "docs", "shared", "macro.json"), encoding="utf-8"))["series"]
        for k in ("US10Y", "USDKRW", "KOSDAQ"):
            if mac.get(k, {}).get("data"):
                series[k] = mac[k]["data"]
    except Exception as e:  # noqa: BLE001
        print("[bio leadlag] macro.json 없음", e)
    if not series:
        return
    months = sorted({m for s in series.values() for m in s if m >= "2005-01"})
    obj = {"title": "미국 바이오 지수·금리·환율 (월말)", "source": "Yahoo Finance 월봉(XBI·IBB), 공용 거시 지표(macro.json)",
           "months": months, "series": {k: [s.get(m) for m in months] for k, s in series.items()},
           "updated": dt.date.today().isoformat()}
    json.dump(obj, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print("[bio leadlag]", {k: len(v) for k, v in series.items()})


if __name__ == "__main__":
    main()
