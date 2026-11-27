# 건설·건자재 대시보드 (docs/construction, `--industry construction`)

65개사, 9개 그룹: 대형 종합건설 · 플랜트·엔지니어링·CM · 중견 건설 · 지방 주택 · 전문건설·설비 · 시멘트·레미콘 · 건자재 · 인테리어·가구·주택설비 · 건설기계.

## 파일
- `config/construction/companies.json` 회사 목록, `kosis.json` 건설수주·기성·착공·인허가·분양·미분양·준공 후 미분양·시멘트 지수·자재 PPI·아파트 실거래가·주담대 금리, `customs.json` 건설기계·건자재 수출(HS 8429 등), `stock_hist.json` 월봉.
- `config/trends/construction.json` 산업동향 선행·동행 지표 26개(공용 trends 모듈, scripts/trends/README.md).
- `scripts/construction/cx_a.py ~ cx_d.py` 회사별 분석 원고(사업 설명·사이클 판정·뉴스 해석·피셔·해자·전망·3분기 리뷰·적정가 가정·IR). `cx_sector.py` 업종 공통 해설·공통 뉴스, `cx_common.py` 도우미.
  모듈 이름에 `cx_` 접두어를 붙인 이유: scripts/reviews/refresh.py가 여러 업종 원고를 한 프로세스에서 불러오는데, 다른 업종의 `common.py`·`deep_*.py`와 이름이 겹치면 엉뚱한 모듈이 쓰여요.
- `valuation_head.json` 적정가 머리말(사이클 설명·그룹별 사이클 위치), `snapshot.json` 시세 수집 전 임시 가격·주식 수·자본(실적 랭킹 집계, 2026-11-20 종가).
- `seed_ed.py` 첫 실적 시드(실적 랭킹 earnings-dashboard의 DART 연결 집계 → 33개사). 나머지 32개사는 국내 PC DART 수집 후 채워져요.
- `scripts/reviews/manual_construction.py` 3분기 손글씨 리뷰(4분기 실적이 들어오면 자동 원고로 바뀜).

## 다시 만들기
```
python scripts/construction/build_deep.py
python scripts/build_valuation.py --industry construction
```
뉴스 해석 추가: `scripts/construction/cx_news_YYYYMMDD.py` (ASOF, NEWS={"코드"|"@그룹"|"@all": [...]}, UPD={...}) 를 만들고 build_deep.py 실행.
