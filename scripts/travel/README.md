# 여행 대시보드 원고 (docs/travel)

- 통계 자동 수집: `.github/workflows/update-travel.yml` (매일 10:30 KST) → `config/travel/kosis.json`(KOSIS) + `scripts/travel/fetch_market.py`(환율·유가)
- 회사별 분석: `deep_agency.py`(여행사)·`deep_dfs.py`(면세점·택스리펀드)·`deep_casino.py`(카지노)·`deep_hotel.py`(호텔·리조트)·`deep_xair.py`(항공: 물류 대시보드 `scripts/logistics/deep_air.py` 원고 공유 + 여행 관점 기사), 공통 해설 `tsector.py`
- IR 분석: `ir_travel.py` (항공은 `scripts/logistics/ir_notes.py` 공유)
- 매일 뉴스 해석: `news_YYYYMMDD.py` (ASOF, NEWS, UPD — 물류와 같은 형식)
- 빌드: `python scripts/travel/build_deep.py` → docs/travel/data/deep.json, reviews.json
- 적정가 가정: `config/travel/valuation.json` → `python scripts/build_valuation.py --industry travel`
- 산업 사이클 진단 `docs/travel/data/cycle.json`, 숫자 카드 `news_exports.json` (손으로 갱신)
- DART(국내 PC): `scripts\dart_all.bat` (travel 포함)
