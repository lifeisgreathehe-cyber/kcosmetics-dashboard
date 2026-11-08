# 물류·운송 대시보드 원고 (docs/logistics)

- `deep_ship.py`·`deep_air.py`·`deep_logi.py`·`deep_port.py`: 회사별 서비스 해설, 실적 진단(사이클 vs 경쟁력), 뉴스 해석, 피셔 16문항, 해자, 전망, 리뷰. `common.K()` 한 번으로 deep.json·reviews.json 원고를 같이 만든다.
- `sector.py`: 업종 공통 해설·공통 뉴스.
- 매일 뉴스 해석: `news_YYYYMMDD.py` (ASOF, NEWS = {코드 | "@그룹" | "@all": [(날짜, 제목, URL, 매체, 해석, "+"/"-"/"0")]}, UPD = {코드: {title/eval/tone}}).
- 빌드: `python scripts/logistics/build_deep.py` → docs/logistics/data/deep.json, reviews.json
- 적정가 가정: `config/logistics/valuation.json` (cycle_mode, 회사별 cyc_pos·정상 이익 E1 또는 E1 없이 자동+E1_mult) → `python scripts/build_valuation.py --industry logistics`
- 산업 사이클 진단: `docs/logistics/data/cycle.json`, 숫자 하이라이트: `news_exports.json` (손으로 갱신)
- DART(국내 PC): `python scripts\update.py --industry logistics --only dart`
