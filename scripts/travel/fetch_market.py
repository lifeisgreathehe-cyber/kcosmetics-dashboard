#!/usr/bin/env python3
"""여행 대시보드: 환율·유가 월간 시계열 (Yahoo Finance 월봉, 키 불필요).

여행 수요는 환율(원화 가치)에 민감하다: 원화 약세 → 방한 외국인↑·해외여행↓, 엔저 → 일본 여행↑.
항공사 비용의 30% 안팎이 연료비라 국제유가(브렌트)도 함께 모은다.
GitHub Actions(update-travel.yml)에서 매일 실행 → docs/travel/data/market.json
"""
import datetime as dt
import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "travel" / "data" / "market.json"
SYMS = [  # (야후 심볼, 이름, 배수)
    ("KRW=X", "원/달러", 1),
    ("JPYKRW=X", "원/100엔", 100),
    ("CNYKRW=X", "원/위안", 1),
    ("TWDKRW=X", "원/대만달러", 1),
    ("BZ=F", "브렌트유(달러/배럴)", 1),
]


def get(sym):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=25y&interval=1mo"
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=40) as r:
                j = json.loads(r.read().decode())
            res = j["chart"]["result"][0]
            ts, cl = res["timestamp"], res["indicators"]["quote"][0]["close"]
            out = {}
            for t, c in zip(ts, cl):
                if c is None:
                    continue
                m = dt.datetime.utcfromtimestamp(t).strftime("%Y-%m")
                out[m] = c
            return out
        except Exception as e:  # noqa: BLE001
            print("[market] 실패", sym, e)
            time.sleep(3 * (i + 1))
    return None


def main():
    old = json.loads(OUT.read_text("utf-8")) if OUT.exists() else {}
    series = {}
    for sym, name, mul in SYMS:
        s = get(sym)
        if s:
            series[name] = {m: round(v * mul, 2) for m, v in s.items()}
        elif old.get("series", {}).get(name):
            prev = old["series"][name]
            series[name] = dict(zip(old["months"], prev))
    if not series:
        print("[market] 데이터 없음 — 기존 파일 유지")
        return
    months = sorted({m for s in series.values() for m in s if m >= "2003-01"})
    obj = {"title": "환율·국제유가 (월말)", "source": "Yahoo Finance 월봉 종가 (서울외환시장 환율과 소폭 다를 수 있음)",
           "url": "https://finance.yahoo.com/quote/KRW=X/", "months": months,
           "series": {k: [s.get(m) for m in months] for k, s in series.items()},
           "updated": dt.date.today().isoformat()}
    OUT.write_text(json.dumps(obj, ensure_ascii=False, indent=0), "utf-8")
    print("[market] 저장", len(months), "개월")


if __name__ == "__main__":
    main()
