"""중국 상품선물(상하이·다롄·정저우) 일별 종가 → 월평균 → docs/chem/data/market_recent.json

관세청 품목별 수출입 단가는 다음 달 15일에 확정돼 1.5개월 늦어요. 그 사이(최근 1~2개월)
스프레드를 이어 그리기 위해, 같은 제품의 중국 선물 월평균 가격 변화율을 관세청 마지막 달
단가에 곱해 '추정 연장치'를 만들어요(계산은 화면에서). 이 파일은 그 변화율의 원재료예요.

실행: python scripts/chem/market_futures.py   (GitHub Actions에서 매일 실행)
출처: Sina Finance 선물 일봉(연결 근월물, 위안/톤·원유는 위안/배럴)
"""
import json, os, re, sys, time, datetime as dt, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "docs", "chem", "data", "market_recent.json")

# 관세청 품목 라벨 → (선물 코드, 설명, 직접 지표 여부)
# direct=False 는 같은 제품 선물이 없어 가장 가까운 지표로 대신한 것(화면에 '대체' 표시)
MAP = {
    "원유": ("SC0", "상하이 INE 원유", True),
    "경질유(나프타·휘발유)": ("SC0", "상하이 INE 원유(나프타는 원유 변화율로 대체)", False),
    "LDPE": ("L0", "다롄 LLDPE", False),
    "HDPE": ("L0", "다롄 LLDPE(HDPE는 LLDPE 변화율로 대체)", False),
    "LLDPE": ("L0", "다롄 LLDPE", True),
    "PP": ("PP0", "다롄 PP", True),
    "프로필렌": ("PL0", "정저우 프로필렌", True),
    "PVC": ("V0", "다롄 PVC", True),
    "MEG": ("EG0", "다롄 에틸렌글리콜", True),
    "SM": ("EB0", "다롄 스티렌", True),
    "벤젠": ("BZ0", "다롄 순수벤젠", True),
    "파라자일렌": ("PX0", "정저우 PX", True),
    "PTA": ("TA0", "정저우 PTA", True),
    "PET": ("PR0", "정저우 PET 병칩", True),
    "폴리에스터 단섬유": ("PF0", "정저우 폴리에스터 단섬유", True),
    "가성소다": ("SH0", "정저우 가성소다", True),
    "BR": ("BR0", "상하이 BR(부타디엔고무)", True),
    "SBR": ("BR0", "상하이 BR(SBR은 BR 변화율로 대체)", False),
}

URL = "https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_x=/InnerFuturesNewService.getDailyKLine?symbol={}"


def fetch(sym):
    req = urllib.request.Request(URL.format(sym), headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn/"})
    for i in range(3):
        try:
            raw = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
            m = re.search(r"\((\[.*\])\)", raw, re.S)
            if not m:
                return None
            rows = json.loads(m.group(1))
            return [(r["d"], float(r["c"])) for r in rows if r.get("c")]
        except Exception as e:  # noqa
            print(f"  {sym} 재시도 {i+1}: {e}", file=sys.stderr)
            time.sleep(2 * (i + 1))
    return None


def monthly(rows, since="2024-01"):
    acc = {}
    for d, c in rows:
        m = d[:7]
        if m >= since and c > 0:
            acc.setdefault(m, []).append(c)
    return {m: {"avg": round(sum(v) / len(v), 2), "n": len(v)} for m, v in sorted(acc.items())}


def main():
    prev = {}
    if os.path.exists(OUT):
        try:
            prev = json.load(open(OUT, encoding="utf-8")).get("series", {})
        except Exception:
            prev = {}
    series, cache = {}, {}
    for item, (sym, desc, direct) in MAP.items():
        if sym not in cache:
            rows = fetch(sym)
            cache[sym] = rows
            print(f"{sym}: {len(rows) if rows else 0}일")
        rows = cache[sym]
        if not rows:
            if item in prev:
                series[item] = prev[item]  # 실패 시 이전 값 유지
            continue
        series[item] = {"sym": sym, "desc": desc, "direct": direct, "last": {"date": rows[-1][0], "close": rows[-1][1]},
                        "months": monthly(rows)}
    if not series:
        print("수집 실패: 기존 파일 유지", file=sys.stderr)
        return 1
    out = {"source": "중국 상품선물 일봉 종가 월평균(Sina Finance, 연결 근월물)",
           "fetched": dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
           "note": "관세청 확정 단가가 없는 최근 달은, 마지막 관세청 단가 × (해당 월 선물 평균 ÷ 관세청 마지막 달 선물 평균)으로 추정해요. 위안화 표시라 환율 변동은 반영되지 않아요.",
           "series": series}
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("저장", OUT, len(series), "품목")
    return 0


if __name__ == "__main__":
    sys.exit(main())
