"""백테스트용 과거 일별 주가 수집 (GitHub Actions에서 실행: 클라우드 세션은 Yahoo·네이버가 막혀 있음).

출력: raw/backtest/prices.json  {code: {"src":..., "d":[YYYY-MM-DD...], "c":[종가(분할 조정)...]}}
기간: 2025-09-01 ~ 실행일. 지수(KOSPI ^KS11, KOSDAQ ^KQ11) 포함. 우선주 코드도 함께.
"""
import json, os, time, datetime as dt, urllib.request, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
START = dt.datetime(2025, 9, 1, tzinfo=dt.timezone.utc)
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/"
NAVER = "https://api.finance.naver.com/siseJson.naver"
KST = dt.timezone(dt.timedelta(hours=9))


def get(url, params):
    full = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(full, headers={"User-Agent": "Mozilla/5.0 (compatible; kcosmetics-dashboard backtest)"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()


def yahoo(sym):
    j = json.loads(get(YAHOO + sym, {"period1": int(START.timestamp()), "period2": int(time.time()), "interval": "1d"}))
    r = j["chart"]["result"][0]
    ts, cl = r["timestamp"], r["indicators"]["quote"][0]["close"]
    d, c = [], []
    for t, v in zip(ts, cl):
        if v:
            d.append(dt.datetime.fromtimestamp(t, KST).strftime("%Y-%m-%d"))
            c.append(round(v, 2))
    if len(d) < 50:
        raise ValueError("too short")
    return d, c


def naver(code):
    raw = get(NAVER, {"symbol": code, "requestType": 1, "startTime": START.strftime("%Y%m%d"),
                      "endTime": dt.date.today().strftime("%Y%m%d"), "timeframe": "day"}).decode("euc-kr", "ignore")
    rows = json.loads(raw.replace("'", '"').strip())
    d, c = [], []
    for row in rows[1:]:
        if row and row[4]:
            s = str(row[0]); d.append(f"{s[:4]}-{s[4:6]}-{s[6:8]}"); c.append(float(row[4]))
    if len(d) < 50:
        raise ValueError("too short")
    return d, c


def main():
    cos = {}
    for p in ("config/companies.json", "config/semi/companies.json", "config/chem/companies.json", "config/battery/companies.json"):
        for c in json.load(open(os.path.join(ROOT, p), encoding="utf-8")):
            cos[c["code"]] = c.get("market")
            if c.get("pref"):
                cos[c["pref"]] = c.get("market")
    out = {}
    for sym, key in (("^KS11", "KOSPI"), ("^KQ11", "KOSDAQ")):
        try:
            d, c = yahoo(sym); out[key] = {"src": "yahoo", "d": d, "c": c}
        except Exception as e:  # noqa: BLE001
            print("index fail", sym, e)
    for code, mk in cos.items():
        got = None
        for fn, arg in ((naver, code),) + tuple((yahoo, code + s) for s in ((".KQ", ".KS") if mk == "KOSDAQ" else (".KS", ".KQ"))):
            try:
                got = (fn.__name__,) + fn(arg); break
            except Exception as e:  # noqa: BLE001
                continue
        if got:
            out[code] = {"src": got[0], "d": got[1], "c": got[2]}
        else:
            print("fail", code)
        time.sleep(0.2)
    os.makedirs(os.path.join(ROOT, "raw", "backtest"), exist_ok=True)
    with open(os.path.join(ROOT, "raw", "backtest", "prices.json"), "w", encoding="utf-8") as f:
        json.dump({"fetched": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"), "prices": out}, f, separators=(",", ":"))
    print("ok", len(out), "of", len(cos) + 2)


if __name__ == "__main__":
    main()
