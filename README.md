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
