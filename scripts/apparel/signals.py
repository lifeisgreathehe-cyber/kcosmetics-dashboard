"""의류 '사이클이 바뀌는 신호' 장기 시계열(최대 20년) → docs/apparel/data/signals.json

국내 지표(백화점 의복 판매액지수, 의복 제조업 출하·재고지수, 나프타·면화 수입 단가)는 update.py --industry apparel 의
KOSIS·관세청 수집 결과(retail_index.json, production_index.json, customs_exports.json)를 화면에서 그대로 쓴다.
여기서는 해외 지표와 날씨를 받는다(모두 API 키 불필요, GitHub Actions에서 실행).
  · 원/달러 환율(월평균)        FRED EXKOUS → 막히면 Yahoo Finance KRW=X 일별 종가의 월평균
  · 국제 면화 가격(¢/lb)        FRED PCOTTINDUSDM → 막히면 Yahoo CT=F(ICE 면화 선물 근월물) 월평균
  · 미국 의류점 재고/판매·재고액 미국 인구조사국 EITS API(소매업 월간조사, 계절조정)
  · 미국 실효 관세율(월)         미국 인구조사국 수입 통계 API: 계산 관세(CAL_DUT_MO) ÷ 소비용 수입액(CON_VAL_MO), 전체·의류(HS 61+62)
  · 서울 월평균 기온            기상청 ASOS 서울(108) 일자료(DATA_GO_KR_KEY에 해당 서비스 활용신청 필요) → 안 되면 Open-Meteo ERA5
FRED는 GitHub Actions에서 응답이 끊기는 일이 잦아 짧게 한 번만 시도한다.
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
TCACHE = os.path.join(ROOT, "raw", "apparel", "us_tariff_cache.json")
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/"
CENSUS = "https://api.census.gov/data/timeseries/"
FRED_OK = [True]  # 한 번 막히면 이번 실행에서는 더 시도하지 않음
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={}&cosd=" + START


def fred(ids):
    """후보 ID를 차례로 받아 가장 최근 값까지 있는 시계열을 고른다. 반환: (id, [(YYYY-MM-DD, 값)])"""
    best = (None, [])
    for sid in ids:
        if not FRED_OK[0]:
            break
        rows = []
        try:
            req = urllib.request.Request(FRED.format(sid), headers={"User-Agent": "Mozilla/5.0 (compatible; kcosmetics-dashboard)"})
            with urllib.request.urlopen(req, timeout=20) as r:
                txt = r.read().decode("utf-8", "ignore")
            rd = csv.reader(io.StringIO(txt))
            next(rd, None)
            for d, v in rd:
                try:
                    rows.append((d, float(v)))
                except ValueError:
                    pass  # '.' = 결측
        except Exception as e:  # noqa: BLE001
            print("FRED 실패(이번 실행은 FRED 건너뜀):", sid, e)
            FRED_OK[0] = False
        if rows and (not best[1] or rows[-1][0] > best[1][-1][0]):
            best = (sid, rows)
    return best


def yahoo_monthly(sym):
    """Yahoo 일별 종가 → 월평균 [(YYYY-MM, 값)]"""
    p1 = int(dt.datetime(2005, 1, 1, tzinfo=dt.timezone.utc).timestamp())
    txt = get(f"{YAHOO}{sym}?period1={p1}&period2={int(time.time())}&interval=1d", ua="Mozilla/5.0 (compatible; kcosmetics-dashboard)")
    try:
        r = json.loads(txt)["chart"]["result"][0]
    except Exception:  # noqa: BLE001
        print("Yahoo 응답 이상:", sym, (txt or "")[:150])
        return []
    mon = {}
    for ts, v in zip(r["timestamp"], r["indicators"]["quote"][0]["close"]):
        if v:
            mon.setdefault(dt.datetime.utcfromtimestamp(ts).strftime("%Y-%m"), []).append(v)
    return [(m, sum(v) / len(v)) for m, v in sorted(mon.items())]


def census_json(path, params):
    q = urllib.parse.urlencode(params, safe=":*+")
    txt = get(CENSUS + path + "?" + q)
    try:
        rows = json.loads(txt)
        return [dict(zip(rows[0], r)) for r in rows[1:]]
    except Exception:  # noqa: BLE001
        print("Census 응답 이상:", path, (txt or "")[:200])
        return []


def us_retail(dtype):
    """소매업 월간조사(MRTS) 의류점(NAICS 448 → 2022 개편 후 458) 계절조정 시계열. dtype: IR(재고/판매), IM(재고액)"""
    rows = census_json("eits/mrts", {"get": "cell_value,data_type_code,category_code,seasonally_adj,time_slot_id",
                                      "for": "us:*", "time": "from 2005-01", "data_type_code": dtype, "seasonally_adj": "yes"})
    cats = {}
    for r in rows:
        cats.setdefault(r.get("category_code"), {})[r["time"][:7]] = r["cell_value"]
    print("MRTS", dtype, "categories:", sorted(c for c in cats if c))
    best = None
    for c in ("4481", "448", "4581", "458"):
        if c in cats and (best is None or len(cats[c]) > len(cats[best])):
            best = c
    if not best:
        return None, []
    out = []
    for m, v in sorted(cats[best].items()):
        try:
            out.append((m, float(v)))
        except (TypeError, ValueError):
            pass
    return best, out


def us_tariff():
    """수입 통계(HS 2단위)로 월별 실효 관세율: 전체, 의류(61+62). 지난 연도는 캐시."""
    cache = {}
    if os.path.exists(TCACHE):
        try:
            cache = json.load(open(TCACHE, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            cache = {}
    today = dt.date.today()
    for y in range(2013, today.year + 1):  # API 수록 시작 2013년
        if str(y) in cache and y < today.year - 1:
            continue
        rows = census_json("intltrade/imports/hs", {"get": "CON_VAL_MO,CAL_DUT_MO,I_COMMODITY", "COMM_LVL": "HS2",
                                                     "time": f"from {y}-01 to {y}-12"})
        if not rows:
            continue
        agg = {}
        for r in rows:
            m = r["time"][:7]
            try:
                v, d = float(r["CON_VAL_MO"]), float(r["CAL_DUT_MO"])
            except (TypeError, ValueError):
                continue
            a = agg.setdefault(m, [0, 0, 0, 0])
            a[0] += v; a[1] += d
            if r["I_COMMODITY"] in ("61", "62"):
                a[2] += v; a[3] += d
        cache[str(y)] = agg
        time.sleep(1)
    os.makedirs(os.path.dirname(TCACHE), exist_ok=True)
    json.dump(cache, open(TCACHE, "w", encoding="utf-8"), ensure_ascii=False)
    allm = {m: a for c in cache.values() for m, a in c.items()}
    ms = sorted(m for m, a in allm.items() if a[0] > 0)
    return ms, [round(allm[m][1] / allm[m][0] * 100, 2) for m in ms], [round(allm[m][3] / allm[m][2] * 100, 2) if allm[m][2] else None for m in ms]


def get(url, tries=3, ua="kcosmetics-dashboard/1.0"):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua})
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
    txt = get("http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList?" + q, tries=1)
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
    kma_ok = bool(key) and len(kma_year(key, today.year - 1, end)) > 300  # 기상청 서비스 활용신청이 안 된 키면 403
    print("기상청 ASOS 사용 가능:", kma_ok)
    for y in range(TEMP_START, today.year + 1):
        ys = str(y)
        if ys in cache and y < today.year - 1 and cache[ys].get("n", 0) >= 360 and (cache[ys].get("src") == "kma" or not kma_ok):
            srcs.add(cache[ys].get("src", "kma"))
            continue
        daily, src = (kma_year(key, y, end), "kma") if kma_ok else ({}, "kma")
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

    def keep(key, val):
        if val:
            S[key] = val
        elif key in old:
            S[key] = old[key]  # 이번에 못 받으면 지난 값 유지

    # 환율·면화: FRED 우선, 막히면 Yahoo
    for key, fid, ysym, title, unit, fsrc, ysrc, yurl in [
        ("usdkrw", "EXKOUS", "KRW=X", "원/달러 환율(월평균)", "원", "FRED·미국 연준(H.10) 원/달러 월평균",
         "Yahoo Finance 원/달러(KRW=X) 일별 종가의 월평균", "https://finance.yahoo.com/quote/KRW%3DX/"),
        ("cotton", "PCOTTINDUSDM", "CT=F", "국제 면화 가격", "센트/파운드", "FRED·IMF 1차 상품가격(Cotlook A 지수)",
         "ICE 면화 선물 근월물(CT=F, Yahoo Finance) 일별 종가의 월평균", "https://finance.yahoo.com/quote/CT%3DF/"),
    ]:
        sid, rows = fred([fid])
        if rows:
            keep(key, dict(title=title, unit=unit, source=fsrc, id=sid, url=f"https://fred.stlouisfed.org/series/{sid}", **monthly(rows)))
            continue
        rows = yahoo_monthly(ysym)
        keep(key, dict(title=title, unit=unit, source=ysrc, id=ysym, url=yurl,
                       months=[m for m, _ in rows], values=[round(v, 2) for _, v in rows]) if rows else None)
    # 미국 의류점 재고/판매·재고액
    for key, dt_, title, unit in [("us_cloth_isr", "IR", "미국 의류점 재고/판매 비율", "개월"), ("us_cloth_inv", "IM", "미국 의류점 재고액", "백만 달러")]:
        try:
            cat, rows = us_retail(dt_)
        except Exception as e:  # noqa: BLE001
            print("MRTS 실패:", e); cat, rows = None, []
        keep(key, dict(title=title, unit=unit, source=f"미국 인구조사국 소매업 월간조사(MRTS, NAICS {cat} 의류점, 계절조정)", id=cat,
                       url="https://www.census.gov/retail/index.html", months=[m for m, _ in rows], values=[round(v, 2) for _, v in rows]) if rows else None)
    # 미국 실효 관세율(월)
    try:
        ms, tot, app = us_tariff()
    except Exception as e:  # noqa: BLE001
        print("관세율 실패:", e); ms = []
    keep("us_tariff", dict(title="미국 실효 관세율(계산 관세 ÷ 소비용 수입액)", unit="%",
                           source="미국 인구조사국 수입 통계(HS 2단위 합계, 월)", url="https://www.census.gov/foreign-trade/data/index.html",
                           months=ms, values=tot, apparel=app) if ms else None)
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
