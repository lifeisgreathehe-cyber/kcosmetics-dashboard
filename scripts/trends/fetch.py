#!/usr/bin/env python3
"""산업동향 공용 지표 수집 (GitHub Actions에서 실행 — 클라우드 세션은 해외 사이트가 막혀 있음).

1) 시장 가격 → docs/shared/markets.json
   config/trends/*.json 에서 쓰는 "market" 코드를 모두 모아 받는다.
   - yahoo:<티커>  야후 파이낸스 월봉 종가 (해외 주가지수·상품선물·환율·ETF)
   - sina:<코드>   시나 파이낸스 중국 상품선물 일봉 → 월평균 (철근·열연·철광석·니켈·리튬 등)
2) 추가 KOSIS 지표 → docs/shared/trend_kosis.json  (config/trends/kosis.json, KOSIS_API_KEY 필요)
   경기종합지수 순환변동치, 소비자심리지수, 품목별 수출물가 등 대시보드 파일에 아직 없던 지표.

받기에 실패한 지표는 이전 값을 그대로 둔다(한 소스가 막혀도 다른 지표·화면은 계속 돌아가게).
표준 라이브러리만 사용.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CFG = ROOT / "config" / "trends"
OUT_M = ROOT / "docs" / "shared" / "markets.json"
OUT_K = ROOT / "docs" / "shared" / "trend_kosis.json"
KST = dt.timezone(dt.timedelta(hours=9))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"


def log(*a):
    print("[trends-fetch]", *a, flush=True)


def get(url, params=None, timeout=30, headers=None):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params, safe="+")
    h = {"User-Agent": UA}
    h.update(headers or {})
    last = None
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (i + 1))
    raise last


def _walk(o, acc):
    if isinstance(o, dict):
        if isinstance(o.get("market"), str):
            acc.add(o["market"])
        for v in o.values():
            _walk(v, acc)
    elif isinstance(o, list):
        for v in o:
            _walk(v, acc)


BASE_MARKETS = {"yahoo:^KS11"}  # 업종 지수와 비교하는 코스피(20년)


def market_codes():
    acc = set(BASE_MARKETS)
    for p in CFG.glob("*.json"):
        try:
            _walk(json.loads(p.read_text("utf-8")), acc)
        except Exception as e:  # noqa: BLE001
            log("설정 읽기 실패", p.name, e)
    return sorted(acc)


def yahoo(sym):
    txt = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}",
              {"range": "20y", "interval": "1mo"})
    res = json.loads(txt)["chart"]["result"][0]
    out = {}
    for t, c in zip(res.get("timestamp") or [], res["indicators"]["quote"][0].get("close") or []):
        if c:
            out[dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m")] = round(c, 4)
    return out


def sina(sym):
    url = f"https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_x=/InnerFuturesNewService.getDailyKLine?symbol={sym}"
    txt = get(url, headers={"Referer": "https://finance.sina.com.cn/"})
    m = re.search(r"\((\[.*\])\)", txt, re.S)
    if not m:
        return {}
    acc = {}
    for r in json.loads(m.group(1)):
        try:
            c = float(r["c"])
        except (KeyError, TypeError, ValueError):
            continue
        acc.setdefault(r["d"][:7], []).append(c)
    return {k: round(sum(v) / len(v), 2) for k, v in acc.items() if v}


NAMES = {}  # 화면용 설명은 각 업종 설정의 name/source 에 있음


def update_markets():
    old = json.loads(OUT_M.read_text("utf-8")) if OUT_M.exists() else {"series": {}}
    series = old.get("series", {})
    ok = fail = 0
    for code in market_codes():
        kind, _, sym = code.partition(":")
        try:
            data = yahoo(sym) if kind == "yahoo" else sina(sym) if kind == "sina" else {}
            if len(data) < 6:
                raise ValueError(f"데이터 {len(data)}개")
            series[code] = {"data": dict(sorted(data.items())), "fetched": dt.date.today().isoformat(),
                            "how": "월봉 종가" if kind == "yahoo" else "일봉 종가 월평균(연결 근월물)"}
            ok += 1
        except Exception as e:  # noqa: BLE001
            fail += 1
            log("실패", code, e)
        time.sleep(0.4)
    OUT_M.write_text(json.dumps({"updated": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
                                 "source": "Yahoo Finance 월봉 · Sina Finance 중국 상품선물", "series": series},
                                ensure_ascii=False, separators=(",", ":")), "utf-8")
    log(f"시장 가격 {ok}개 갱신, {fail}개 실패 → {OUT_M.relative_to(ROOT)}")


KOSIS = "https://kosis.kr/openapi/Param/statisticsParameterData.do"


LONG_START = "200501"


def _files(o, acc, ind):
    if isinstance(o, dict):
        if isinstance(o.get("file"), str) and "/" not in o["file"]:
            acc.add((o.get("ind", ind), o["file"]))
        for v in o.values():
            _files(v, acc, ind)
    elif isinstance(o, list):
        for v in o:
            _files(v, acc, ind)


def long_specs():
    """대시보드 파일(config/<업종>/kosis.json 으로 2015년부터 받는 월간 KOSIS 표)을 2005년부터 다시 받는 사양.
    대시보드 그래프는 그대로 두고, 선행·동행 통계에만 더 긴 역사를 쓴다(2008년 금융위기 등 사이클 포함)."""
    used = set()
    for ind in industries():
        try:
            _files(json.loads((CFG / f"{ind}.json").read_text("utf-8")), used, ind)
        except Exception:  # noqa: BLE001
            pass
    out = {}
    for ind, fname in used:
        kp = ROOT / "config" / ("kosis.json" if ind == "cosmetics" else f"{ind}/kosis.json")
        if not kp.exists():
            continue
        for sp in json.loads(kp.read_text("utf-8")):
            if sp.get("file") == fname and sp.get("prdSe") == "M" and sp.get("start", "") > LONG_START and not sp.get("flat"):
                out[(ind, fname)] = sp
    return out


def update_kosis(key):
    specs = json.loads((CFG / "kosis.json").read_text("utf-8"))
    old = json.loads(OUT_K.read_text("utf-8")) if OUT_K.exists() else {"series": {}}
    series = old.get("series", {})
    today = dt.date.today()
    for sp in specs:
        p = {"method": "getList", "apiKey": key, "format": "json", "jsonVD": "Y", "orgId": sp["orgId"], "tblId": sp["tblId"],
             "itmId": sp.get("itmId", "ALL"), "objL1": sp.get("objL1", "ALL"), "prdSe": "M",
             "startPrdDe": sp.get("start", "200801"), "endPrdDe": f"{today.year}12"}
        for k in ("objL2", "objL3"):
            if k in sp:
                p[k] = sp[k]
        try:
            rows = json.loads(get(KOSIS, p, timeout=60))
            if isinstance(rows, dict):
                raise ValueError(str(rows)[:200])
            rows = [r for r in rows if all(r.get(k) == v for k, v in (sp.get("where") or {}).items())]
            data = {}
            for r in rows:
                try:
                    data[f"{r['PRD_DE'][:4]}-{r['PRD_DE'][4:6]}"] = float(r["DT"])
                except (TypeError, ValueError, KeyError):
                    pass
            if len(data) < 6:
                raise ValueError(f"데이터 {len(data)}개")
            series[sp["id"]] = {"name": sp.get("name", sp["id"]), "data": dict(sorted(data.items())),
                                "url": f"https://kosis.kr/statHtml/statHtml.do?orgId={sp['orgId']}&tblId={sp['tblId']}",
                                "fetched": today.isoformat()}
            log("KOSIS", sp["id"], len(data), "개월")
        except Exception as e:  # noqa: BLE001
            log("KOSIS 실패", sp["id"], str(e).replace(key, "***"))
        time.sleep(0.3)
    long = old.get("long", {})
    for (ind, fname), sp in long_specs().items():
        p = {"method": "getList", "apiKey": key, "format": "json", "jsonVD": "Y", "orgId": sp["orgId"], "tblId": sp["tblId"],
             "itmId": sp.get("itmId", "ALL"), "objL1": sp.get("objL1", "ALL"), "prdSe": "M",
             "startPrdDe": LONG_START, "endPrdDe": f"{today.year}12"}
        for k in ("objL2", "objL3"):
            if k in sp:
                p[k] = sp[k]
        try:
            rows = json.loads(get(KOSIS, p, timeout=90))
            if isinstance(rows, dict):
                raise ValueError(str(rows)[:200])
            rows = [r for r in rows if all(r.get(k) == v for k, v in (sp.get("where") or {}).items())]
            ser = {}
            for r in rows:
                name = "values" if sp.get("single") else sp.get("rename", {}).get(r.get(sp["series_key"]), r.get(sp["series_key"]))
                try:
                    ser.setdefault(name, {})[f"{r['PRD_DE'][:4]}-{r['PRD_DE'][4:6]}"] = float(r["DT"])
                except (TypeError, ValueError, KeyError):
                    pass
            if ser:
                long[f"{ind}:{fname}"] = {k: dict(sorted(v.items())) for k, v in ser.items()}
                log("KOSIS 장기", ind, fname, len(ser), "계열", min(min(v) for v in ser.values()), "~")
        except Exception as e:  # noqa: BLE001
            log("KOSIS 장기 실패", ind, fname, str(e).replace(key, "***"))
        time.sleep(0.3)
    OUT_K.write_text(json.dumps({"updated": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"), "series": series, "long": long},
                                ensure_ascii=False, separators=(",", ":")), "utf-8")


def industries():
    return [p.stem for p in sorted(CFG.glob("*.json")) if not p.stem.startswith("_") and p.stem != "kosis"]


def data_dir(ind):
    return ROOT / "docs" / "data" if ind == "cosmetics" else ROOT / "docs" / ind / "data"


def naver_long(code):
    txt = get("https://api.finance.naver.com/siseJson.naver",
              {"symbol": code, "requestType": "1", "startTime": "20000101",
               "endTime": dt.date.today().strftime("%Y%m%d"), "timeframe": "month"},
              headers={"Referer": "https://finance.naver.com/"})
    out = {}
    for m in re.finditer(r'\["(\d{8})",\s*([\d.]+),\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)', txt):
        out[f"{m.group(1)[:4]}-{m.group(1)[4:6]}"] = float(m.group(5))
    return out


def yahoo_stock(code, market):
    for suf in ((".KQ", ".KS") if market == "KOSDAQ" else (".KS", ".KQ")):
        try:
            d = yahoo(code + suf)
            if len(d) > 12:
                return d
        except Exception:  # noqa: BLE001
            pass
    return {}


def update_stocks(only_ind=None):
    """업종 지수용 장기 월봉(2000년~). 네이버 월봉 API가 실패하면 야후. 이미 받은 종목은 최근 3개월만 덮어씀."""
    out_dir = ROOT / "raw" / "trends"
    out_dir.mkdir(parents=True, exist_ok=True)
    for ind in industries():
        if only_ind and ind != only_ind:
            continue
        cp = data_dir(ind) / "companies.json"
        if not cp.exists():
            continue
        comps = json.loads(cp.read_text("utf-8")).get("companies", [])
        dst = out_dir / f"stock_long_{ind}.json"
        old = json.loads(dst.read_text("utf-8")) if dst.exists() else {"series": {}}
        ser = old.get("series", {})
        ok = 0
        for c in comps:
            code = c["code"]
            have = ser.get(code)
            if have and have.get("months") and have["months"][-1] >= (dt.date.today() - dt.timedelta(days=95)).strftime("%Y-%m") \
                    and "--refresh" not in sys.argv:
                continue  # 장기 이력은 앞부분만 쓰므로 이미 있으면 다시 받지 않음(최근 달은 stock_hist.json이 채움)
            d = {}
            try:
                d = naver_long(code)
            except Exception as e:  # noqa: BLE001
                log("네이버 장기 월봉 실패", code, e)
            if len(d) < 12:
                d = yahoo_stock(code, c.get("market"))
            if d:
                ms = sorted(d)
                ser[code] = {"name": c.get("name"), "months": ms, "close": [d[m] for m in ms]}
                ok += 1
            time.sleep(0.15)
        dst.write_text(json.dumps({"updated": dt.date.today().isoformat(), "source": "네이버 금융 월봉(실패 시 야후), 2000년~",
                                   "series": ser}, ensure_ascii=False, separators=(",", ":")), "utf-8")
        log(f"{ind}: 장기 월봉 {ok}개 새로 받음, 전체 {len(ser)}개")


def main():
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    if only in (None, "stocks"):
        update_stocks(sys.argv[sys.argv.index("--industry") + 1] if "--industry" in sys.argv else None)
    if only in (None, "markets"):
        update_markets()
    if only in (None, "kosis"):
        key = os.getenv("KOSIS_API_KEY")
        if key:
            update_kosis(key)
        else:
            log("KOSIS_API_KEY 없음 — KOSIS 추가 지표는 건너뜀")


if __name__ == "__main__":
    main()
