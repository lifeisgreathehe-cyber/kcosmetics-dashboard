# 철강·비철금속 대시보드 원고 (docs/steel)

- 대상: `config/steel/companies.json` 71개사, 12개 그룹(고로·전기로·특수강·판재·강관·선재·유통/피팅·단조/원료·비철 제련·동/알루미늄·전선·무역/IT).
- `deep_a.py`~`deep_e.py`: 회사별 제품·서비스 해설, 실적 진단(사이클 vs 경쟁력), 뉴스 해석, 피셔 16문항, 해자, 전망, 리뷰, 적정가 가정(`val`), IR 분석(`ir`). `common.C()` 한 번으로 모두 등록한다.
- `sector.py`: 업종 공통 해설(고로·전기로·특수강·판재·강관·선재·유통·단조·비철·전선·무역), `news_sector.py`: 업종 공통 기사와 회사별 해석(`NS`).
- 빌드: `python scripts/steel/build_deep.py` → docs/steel/data/deep.json, reviews.json, 그리고 config/steel/valuation.json(`valuation_head.json` + 회사별 `val`).
- 적정가: `python scripts/build_valuation.py --industry steel` (cycle_mode, levered: 순차입은 이미 순이익에 이자로 반영돼 빼지 않음).
- 리뷰 자동 갱신: `scripts/reviews/manual_steel.py`가 deep_*.py 리뷰를 2026Q3 원고로 등록. 4분기 실적이 들어오면 refresh.py가 자동 원고로 바꾼다.
- 산업 사이클 진단: `docs/steel/data/cycle.json`, 숫자 하이라이트: `news_exports.json` (손으로 갱신).
- 초기 실적: `seed_ed.py`로 실적 랭킹(earnings-dashboard) 집계 29개사를 넣었고, 나머지는 국내 PC에서 `scripts\dart_all.bat` 실행 후 채워진다.
- 매일 뉴스(update-news), 10분 시세(update-quotes), 매주 KOSIS·관세청(update-data), 시가총액 대조(audit-market)는 공용 워크플로가 steel 폴더를 자동으로 포함한다.
