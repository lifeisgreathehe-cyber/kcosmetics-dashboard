"""의류 '사이클이 바뀌는 신호' 장기 시계열(최대 20년) → docs/apparel/data/signals.json

국내 지표(백화점 의복 판매액지수, 의복 제조업 출하·재고지수, 나프타·면화 수입 단가)는 update.py --industry apparel 의
KOSIS·관세청 수집 결과(retail_index.json, production_index.json, customs_exports.json)를 화면에서 그대로 쓰고,
여기서는 해외 지표만 FRED(미국 세인트루이스 연준, API 키 없이 CSV)에서 받는다.
  · 원/달러 환율(월평균)              EXKOUS
  · 국제 면화 가격(¢/lb, IMF)          PCOTTINDUSDM
  · 미국 의류점 재고/판매 비율·재고액   MRTSIR4481USS · MRTSIM4481USS (NAICS 개편으로 ID가 바뀌면 후보를 차례로 시도)
  · 미국 관세 수입(분기, 연율 십억$)    B235RC1Q027SBEA ÷ 상품 수입 A255RC1Q027SBEA → 실효 관세율(%)
서울 기온(월평균)은 기상청 종관기상관측(ASOS) 서울(108) 일자료를 공공데이터포털(DATA_GO_KR_KEY)로 받아 월평균을 낸다.
키가 없거나 막히면 Open-Meteo 재분석(ERA5) 서울 격자값으로 대신한다. 지난 연도는 raw/apparel/seoul_temp_cache.json 에 저장.
사용: python scripts/apparel/signals.py   (.github/workflows/apparel-signals.yml 이 매일 실행)
"""
import csv
import datetime as dt
import io
import json
import os
import time
import urllib.parse
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
OUT = os.path.join(ROOT, "docs", "apparel", "data", "signals.json")
START = "2005-01-01"  # 2006년부터 20년 + 전년 대비 계산용 1년
TEMP_START = 2010  # 최근 5년 그래프 + 평년(직전 10년 평균) 계산용
CACHE = os.path.join(ROOT, "raw", "apparel", "seoul_temp_cache.json")
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={}&cosd=" + START


def fred(ids):
    """후보 ID를 차례로 받아 가장 최근 값까지 있는 시계열을 고른다. 반환: (id, [(YYYY-MM-DD, 값)])"""
    best = (None, [])
    for sid in ids:
        rows = []
        for _ in range(3):
            try:
                req = urllib.request.Request(FRED.format(sid), headers={"User-Agent": "Mozilla/5.0 (compatible; kcosmetics-dashboard)"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    txt = r.read().decode("utf-8", "ignore")
                rd = csv.reader(io.StringIO(txt))
                next(rd, None)
                for d, v in rd:
                    try:
                        rows.append((d, float(v)))
                    except ValueError:
                        pass  # '.' = 결측
                break
            except Exception as e:  # noqa: BLE001
                print("FRED 실패:", sid, e)
                time.sleep(3)
        if rows and (not best[1] or rows[-1][0] > best[1][-1][0]):
            best = (sid, rows)
    return best


def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "kcosmetics-dashboard/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception as e:  # noqa: BLE001
            print("GET 실패:", url.split("?")[0], e)
            time.sleep(3 * (i + 1))
    return None


def kma_year(key, y, end):
    """기상청 ASOS 서울(108) 일자료 1년치 → {YYYY-MM-DD: 평균기온}"""
    s, e = f"{y}0101", min(f"{y}1231", end)
    q = urllib.parse.urlencode({"serviceKey": urllib.parse.unquote(key), "pageNo": 1, "numOfRows": 400, "dataType": "JSON",
                                "dataCd": "ASOS", "dateCd": "DAY", "startDt": s, "endDt": e, "stnIds": "108"}, safe="+")
    txt = get("http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList?" + q)
    try:
        items = json.loads(txt)["response"]["body"]["items"]["item"]
    except Exception:  # noqa: BLE001
        print("기상청 응답 이상:", y, (txt or "")[:200].replace(key, "***"))
        return {}
    return {it["tm"]: float(it["avgTa"]) for it in items if it.get("avgTa") not in (None, "")}


def meteo(y, end):
    e = min(f"{y}-12-31", f"{end[:4]}-{end[4:6]}-{end[6:]}")
    txt = get(f"https://archive-api.open-meteo.com/v1/archive?latitude=37.5714&longitude=126.9658&start_date={y}-01-01&end_date={e}"
              "&daily=temperature_2m_mean&timezone=Asia%2FSeoul")
    try:
        d = json.loads(txt)["daily"]
        return {t: v for t, v in zip(d["time"], d["temperature_2m_mean"]) if v is not None}
    except Exception:  # noqa: BLE001
        return {}


def seoul_temp():
    """연도별 {월: 평균기온}. 지난 연도는 캐시, 올해·작년은 매번 새로 받음."""
    key = os.environ.get("DATA_GO_KR_KEY", "")
    cache = {}
    if os.path.exists(CACHE):
        try:
            cache = json.load(open(CACHE, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            cache = {}
    today = dt.date.today()
    end = (today - dt.timedelta(days=1)).strftime("%Y%m%d")
    srcs = set()
    for y in range(TEMP_START, today.year + 1):
        ys = str(y)
        if ys in cache and y < today.year - 1 and cache[ys].get("n", 0) >= 360:
            srcs.add(cache[ys].get("src", "kma"))
            continue
        daily, src = (kma_year(key, y, end), "kma") if key else ({}, "kma")
        if len(daily) < 20:
            daily, src = meteo(y, end), "era5"
        if not daily:
            continue
        mon = {}
        for d, v in daily.items():
            mon.setdefault(d[:7], []).append(v)
        cache[ys] = {"src": src, "n": len(daily), "m": {m: round(sum(v) / len(v), 2) for m, v in mon.items()}}
        srcs.add(src)
        time.sleep(0.5)
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    months = sorted(m for c in cache.values() for m in c["m"])
    if not months:
        return None
    vals = {m: v for c in cache.values() for m, v in c["m"].items()}
    era = srcs == {"era5"}
    return dict(title="서울 월평균 기온", unit="℃",
                source=("Open-Meteo 재분석(ERA5) 서울 격자 일평균 기온의 월평균" if era else
                        "기상청 종관기상관측(ASOS) 서울(108) 일평균 기온의 월평균" + (" (일부 연도는 ERA5 재분석으로 보완)" if "era5" in srcs else "")),
                url="https://open-meteo.com/en/docs/historical-weather-api" if era else "https://www.data.go.kr/data/15059093/openapi.do",
                months=months, values=[vals[m] for m in months])


def monthly(rows):
    return {"months": [d[:7] for d, _ in rows], "values": [round(v, 4) for _, v in rows]}


def main():
    old = {}
    if os.path.exists(OUT):
        try:
            old = json.load(open(OUT, encoding="utf-8")).get("series", {})
        except Exception:  # noqa: BLE001
            old = {}
    S = {}
    spec = [
        ("usdkrw", ["EXKOUS"], "원/달러 환율(월평균)", "원", "FRED·미국 연준(H.10) 원/달러 월평균"),
        ("cotton", ["PCOTTINDUSDM"], "국제 면화 가격", "센트/파운드", "FRED·IMF 1차 상품가격(Cotlook A 지수)"),
        ("us_cloth_isr", ["MRTSIR4481USS", "MRTSIR448USS", "MRTSIR4581USS", "MRTSIR458USS"], "미국 의류점 재고/판매 비율", "개월", "FRED·미국 인구조사국 소매업 월간조사(계절조정)"),
        ("us_cloth_inv", ["MRTSIM4481USS", "MRTSIM448USS", "MRTSIM4581USS", "MRTSIM458USS"], "미국 의류점 재고액", "백만 달러", "FRED·미국 인구조사국 소매업 월간조사(계절조정)"),
    ]
    for key, ids, title, unit, src in spec:
        sid, rows = fred(ids)
        if rows:
            S[key] = dict(title=title, unit=unit, source=src, id=sid, url=f"https://fred.stlouisfed.org/series/{sid}", **monthly(rows))
        elif key in old:
            S[key] = old[key]  # 이번에 못 받으면 지난 값 유지
        time.sleep(1)
    _, duty = fred(["B235RC1Q027SBEA"])
    _, imp = fred(["A255RC1Q027SBEA"])
    if duty and imp:
        im = dict(imp)
        q = [(d, v / im[d] * 100) for d, v in duty if im.get(d)]
        S["us_tariff"] = dict(title="미국 실효 관세율(관세 수입 ÷ 상품 수입)", unit="%", source="FRED·미국 경제분석국(BEA) 국민계정, 분기 연율",
                              url="https://fred.stlouisfed.org/series/B235RC1Q027SBEA",
                              quarters=[f"{d[:4]}Q{(int(d[5:7]) - 1) // 3 + 1}" for d, _ in q], values=[round(v, 2) for _, v in q])
    elif "us_tariff" in old:
        S["us_tariff"] = old["us_tariff"]
    try:
        tp = seoul_temp()
    except Exception as e:  # noqa: BLE001
        print("서울 기온 실패:", e)
        tp = None
    if tp:
        S["seoul_temp"] = tp
    elif "seoul_temp" in old:
        S["seoul_temp"] = old["seoul_temp"]
    out = {"updated": dt.date.today().isoformat(), "start": START[:7],
           "note": "국내 지표는 KOSIS·관세청 수집분(retail_index·production_index·customs_exports)을 함께 써요.", "series": S}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print("signals:", {k: (v.get("id"), (v.get("months") or v.get("quarters"))[-1]) for k, v in S.items()})


if __name__ == "__main__":
    main()
