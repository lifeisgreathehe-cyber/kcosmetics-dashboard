"""시가총액·주식수·PER·PBR 외부 대조 (네이버 금융 + 금융위원회 주식시세정보).

모든 대시보드의 종목(우선주 포함)에 대해 외부 원천 값을 받아 raw/audit/market_check.json에 저장한다.
build_valuation.py가 이 파일의 상장주식수를 주식수 교차 검증에 쓰고, 차이가 크면 경고를 남긴다.
실행: python scripts/audit_market.py  (GitHub Actions: audit-market.yml)
"""
import datetime as dt
import json
import os
import pathlib
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
INDS = ["cosmetics", "semi", "chem", "battery", "apparel", "food", "logistics", "auto", "steel"]
UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://m.stock.naver.com/"}
PRICE_URL = "https://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo"


def get(url, params=None, quiet=False):
    full = url + ("?" + urllib.parse.urlencode(params) if params else "")
    for i in range(2):
        try:
            with urllib.request.urlopen(urllib.request.Request(full, headers=UA), timeout=20) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            err = str(e)
            if quiet:
                return None
            time.sleep(1 + i)
    print("실패:", url[:70], err)
    return None


def naver(code):
    out = {}
    j = get(f"https://m.stock.naver.com/api/stock/{code}/integration")
    if j:
        out["name"] = j.get("stockName")
        out["infos"] = {t.get("code"): t.get("value") for t in (j.get("totalInfos") or [])}
    b = get(f"https://m.stock.naver.com/api/stock/{code}/basic")
    if b:
        out["basic"] = {k: b.get(k) for k in ("stockName", "closePrice", "marketStatus", "localTradedAt", "stockExchangeType",
                                              "tradeStopType", "itemCode") if k in b}
    return out


def krx(code, key):
    j = get(PRICE_URL, {"serviceKey": key, "resultType": "json", "numOfRows": 5, "pageNo": 1, "likeSrtnCd": code})
    try:
        items = [i for i in j["response"]["body"]["items"]["item"] if i.get("srtnCd") == code]
    except Exception:  # noqa: BLE001
        return None
    if not items:
        return None
    last = max(items, key=lambda i: i["basDt"])
    return {k: last.get(k) for k in ("basDt", "itmsNm", "clpr", "lstgStCnt", "mrktTotAmt", "mrktCtg")}


def main():
    key = os.environ.get("DATA_GO_KR_KEY")
    codes = {}
    for ind in INDS:
        p = ROOT / ("config" if ind == "cosmetics" else f"config/{ind}") / "companies.json"
        if not p.exists():  # 아직 없는 업종(다른 브랜치에서 추가 중)은 건너뜀
            continue
        for c in json.loads(p.read_text("utf-8")):
            codes.setdefault(c["code"], {"name": c["name"], "inds": []})["inds"].append(ind)
            if c.get("pref"):
                codes.setdefault(c["pref"], {"name": c["name"] + "우", "inds": [], "pref_of": c["code"]})["inds"].append(ind)
    out = {"fetched": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M KST"), "codes": {}}
    krx_ok = bool(key)
    cfg_pref = {m["pref_of"] for m in codes.values() if m.get("pref_of")}
    prev = {}
    try:  # 이미 우선주를 찾아본 종목은 지난 결과를 재사용(매일 수천 건 요청을 피함)
        prev = json.loads((ROOT / "raw" / "audit" / "market_check.json").read_text("utf-8")).get("codes", {})
    except Exception:  # noqa: BLE001
        pass
    for code, m in list(codes.items()):
        p = prev.get(code) or {}
        if p.get("pref_checked") and not m.get("pref_of"):
            m["pref_checked"] = True
            if p.get("pref_found"):
                m["pref_found"] = p["pref_found"]
                codes.setdefault(p["pref_found"], {"name": m["name"] + "우", "inds": m["inds"], "pref_of": code})
    for code in [c for c, m in codes.items() if not m.get("pref_of") and c not in cfg_pref and not m.get("pref_checked")]:
        codes[code]["pref_checked"] = True
        # 설정에 없는 우선주 찾기(종목코드 끝자리 5·7·9·K)
        for suf in ("5", "7", "9", "K"):
            pc = code[:5] + suf
            if pc == code or pc in codes:
                continue
            b = get(f"https://m.stock.naver.com/api/stock/{pc}/basic", quiet=True)
            if b and (b.get("stockName") or "").rstrip().endswith(("우", "우B", "우(전환)")) and b.get("stockName", "").startswith(codes[code]["name"][:2]):
                codes[code]["pref_found"] = pc
                codes[pc] = {"name": b["stockName"], "inds": codes[code]["inds"], "pref_of": code}
                break
            time.sleep(0.05)
    for i, (code, meta) in enumerate(sorted(codes.items())):
        rec = dict(meta, naver=naver(code))
        if krx_ok:
            k = krx(code, key)
            if k is None and i == 0:
                print("금융위 시세 API 응답 없음 — 건너뜀")
                krx_ok = False
            rec["krx"] = k
        out["codes"][code] = rec
        time.sleep(0.15)
    d = ROOT / "raw" / "audit"
    d.mkdir(parents=True, exist_ok=True)
    (d / "market_check.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), "utf-8")
    print("저장:", len(out["codes"]), "종목")


if __name__ == "__main__":
    main()
