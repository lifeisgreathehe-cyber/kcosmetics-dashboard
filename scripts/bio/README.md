# 바이오·제약 대시보드 (docs/bio, `--industry bio`)

91개사 · 10개 그룹(바이오의약품·CDMO, 상위 제약, 중견 제약·일반약, 제약 지주, 플랫폼·기술수출, 신약 상업화·후기 임상, 세포·유전자치료, 백신·동물약품, 진단·유전체, 의료기기·AI 의료).

## 파일
- `universe.py` → `config/bio/companies.json` (회사 목록·그룹)
- `common.py` `C()` 한 번으로 회사별 심층 분석·뉴스 해석·피셔·리뷰·적정가 가정·IR 분석을 등록
- `sector.py` 업종 공통 해설, `news_sector.py` 업종 공통 뉴스
- `deep_a.py`~`deep_f.py` 회사별 원고 → `build_deep.py` 가 `docs/bio/data/deep.json`·`reviews.json`, `config/bio/valuation.json`(= `valuation_head.json` + 원고의 val) 생성
- `seed_ed.py` DART 수집 전 실적 랭킹(earnings-dashboard) 집계로 실적 시드
- 리뷰 손글씨 원고: `scripts/reviews/manual_bio.py`
- 산업동향 선행·동행 지표: `config/trends/bio.json` (공용 trends 모듈)

## 적정가
- 이익을 내는 회사: 공용 `scripts/build_valuation.py` (정상 이익 E1·사이클 위치·시나리오 DCF)
- 이익이 없거나 계약금·마일스톤에 좌우되는 회사: `"skip": "rNPV"` + `pipeline` → `scripts/rnpv.py` 가 후보물질별 '성공 확률 × 현금흐름 현재가치 + 순현금 − 고정비'
- 흑자 회사에 파이프라인이 있으면 DCF 값에 rNPV를 더함(`dcf.pipeline_added`)

## 다시 만들기
```
python3 scripts/bio/build_deep.py
python3 scripts/build_valuation.py --industry bio
python3 scripts/reviews/refresh.py --industry bio
```
`docs/bio/data/cycle.json`(사이클 진단)·`news_exports.json`(숫자로 보는 동향)은 손으로 갱신해요.
