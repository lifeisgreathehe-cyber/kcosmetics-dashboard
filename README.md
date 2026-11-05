# 국내 화장품 산업 대시보드

공공데이터(관세청·KOSIS·식약처)와 DART 전자공시로 국내 화장품 산업 동향과 상장사 실적을 한눈에 보는 정적 웹페이지입니다.

- 웹페이지: `docs/index.html` (GitHub Pages: Settings → Pages → Branch `main`, 폴더 `/docs`)
- 데이터: `docs/data/*.json`
- 수집 스크립트: `scripts/update.py` (표준 라이브러리만 사용)
- 자동 갱신: `.github/workflows/update-data.yml` — 매주 월요일, 매월 16일 09:00 KST. Actions 탭에서 수동 실행도 가능.

## API 키 (Settings → Secrets and variables → Actions)

| Secret 이름 | 발급처 | 용도 |
|---|---|---|
| `DART_API_KEY` | https://opendart.fss.or.kr | 상장사 10년 연간·분기 매출액/매출총이익/영업이익/지배주주순이익 |
| `KOSIS_API_KEY` | https://kosis.kr/openapi | 식약처 화장품산업현황, 온라인쇼핑동향, 판매액지수 |
| `DATA_GO_KR_KEY` | https://www.data.go.kr (관세청 품목별·국가별 수출입실적) | HS 3303·3304·3305·3307 월별 수출입 |

키가 없는 소스는 기존 데이터를 그대로 유지합니다.

## 대상 기업

`config/companies.json`에서 추가·삭제할 수 있습니다 (종목코드, 이름, 업종 그룹).

## 로컬 실행

```bash
DART_API_KEY=... python scripts/update.py
cd docs && python -m http.server
```

## 분기 리뷰 · 내재가치
- `docs/data/reviews.json`: 회사별 최근 4개 분기 실적 동향과 평가 (분기 실적 발표 후 갱신)
- `config/valuation.json`: 회사별 내재가치 가정(정상화 이익, 성장 시나리오, 할인율)과 시세 스냅샷
- `scripts/build_valuation.py`: TTM PER·ROE·PBR, 시나리오 적정가, 역DCF 내재 성장률을 계산해 `docs/data/valuation.json` 생성. `update.py` 실행 끝에 자동 호출돼요.

## 반도체 대시보드 (`docs/semi/`)
같은 구조로 국내 반도체 산업 대시보드를 함께 운영해요. 주소: https://lifeisgreathehe-cyber.github.io/kcosmetics-dashboard/semi/
- 설정: `config/semi/` (companies.json 34개사, kosis.json 생산·출하·재고지수·수출물가, customs.json HS 8541·8542·8486)
- 데이터: `docs/semi/data/`, 사업보고서 본문: `raw/semi/dart_docs/`
- 모든 스크립트에 `--industry semi`를 붙이면 반도체용으로 동작해요. 예) `python scripts/update.py --industry semi --only dart`
- 삼성전자는 우선주(005935) 시가총액을 합산해요 (`pref` 필드). 유통주식수는 DART 주식총수 현황에서 받아요.

## 화학·정유 대시보드 (`docs/chem/`)
주소: https://lifeisgreathehe-cyber.github.io/kcosmetics-dashboard/chem/
- 설정: `config/chem/` (companies.json 61개사: 정유·윤활유/유통·석유화학·정밀/스페셜티·합성섬유·도료·비료), kosis.json(석유정제·화학 생산/출하/재고지수, 석유제품·화학 수출물가, 원유 수입물가), customs.json(HS 2710·29·39·4002 수출, 2709 원유 수입, 국가별 HS 39)
- 내재가치 자동 가정은 최근 1년 이익이 아니라 최근 7개 연도 지배순이익 평균(사이클 평균)을 정상 이익으로 씀 (`config/chem/valuation.json`의 `default.E1_years`)
- DART 수집(국내 PC): `python scripts\update.py --industry chem --only dart`
