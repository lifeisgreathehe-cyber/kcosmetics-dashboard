# 산업동향 투자 지표 · 선행/동행 판정 (모든 업종 공용)

각 대시보드 '산업 동향' 탭 맨 위의 **투자 판단 지표 — 주가보다 먼저 움직이나?** 카드를 만드는 모듈.

## 새 업종에 붙이는 법 (3단계)
1. `config/trends/<업종>.json` 작성 — `series` 에 지표를 나열 (형식은 semi.json 참고).
   - `src` 종류
     - `{"file":"customs_exports.json","path":"series.메모리"}` 대시보드가 이미 모으는 파일 (`total`, `series.X`, `extra.X.imports`, `unit_price.X`, `values` 등 점 경로)
     - `{"ind":"travel","file":"inbound_new.json","path":"series.중국"}` 다른 업종 파일
     - `{"market":"yahoo:^SOX"}` / `{"market":"sina:RB0"}` 시장 가격 (fetch.py 가 자동으로 받음)
     - `{"kosis":"lead_cycle"}` 추가 KOSIS 지표 (`config/trends/kosis.json` 에 사양 추가)
     - `{"calc":"ratio"|"diff"|"yoy_gap"|"sum", ...}` 파생 지표, `{"concat":[...]}` 구·신 통계표 연결
   - `tf`: `yoy`(기본, 전년비 %) · `diff12`(1년 차이) · `level`(그대로), `ma`: 이동평균 개월, `sign`: 주가에 유리한 방향(+1/−1), `pub_lag`: 발표 시차(개월)
   - `why`/`read`: 화면에 나오는 '왜 보나'·'읽는 법' 문장
   - 공통 거시 지표(`_common.json`)는 자동으로 붙음. 빼려면 `skip_common`.
   - 코로나 같은 왜곡 기간은 `exclude_window: ["2020-02","2024-06"]` (업종 전체 또는 지표별).
2. 업종 `index.html` 에 `<script src="../shared/trends.js"></script>` 한 줄 (산업 동향 탭 KPI 아래에 스스로 붙음).
3. 끝. `update-trends.yml` 이 매일 18:10 KST 에 config/trends 의 모든 업종을 계산한다.

## 파일
- `fetch.py` — 장기 월봉(`raw/trends/stock_long_<업종>.json`), 시장 가격(`docs/shared/markets.json`), 추가 KOSIS·2005년부터의 KOSIS 장기 이력(`docs/shared/trend_kosis.json`). Actions 전용(클라우드 세션은 외부 사이트 차단).
- `build.py` — 업종 지수(시총가중·중소형 동일가중·그룹별·대형주) 계산, 시차 상관(−12~+12개월), 자기상관 보정 유의성, 지표 개선/악화 뒤 수익률, 지금 신호 → `docs/<업종>/data/trends.json`. 네트워크 불필요.
- `stats.py` — 통계 함수.
- `docs/shared/trends.js` — 화면.
