# 조선·조선기자재 대시보드 (docs/ship, `--industry ship`)

- 기업 37개사: `config/ship/companies.json` (완성선 6 · 엔진·추진 6 · LNG 보냉재 4 · 배관·피팅·밸브 6 · 블록·의장·해양구조물 6 · 전장·친환경 기자재 7 · 선박 서비스·해양 2)
- 통계: `config/ship/kosis.json` (기계수주통계 선박·내연기관, 선박 건조업 생산·출하지수, 선박용 엔진 수출물가), `config/ship/customs.json` (HS 8901·8905·8906 + 기자재)
- 후판 가격은 철강 대시보드의 `docs/steel/data/steel_ppi.json`을 그대로 읽어요.
- 산업동향 선행·동행 판정: 공용 모듈 `config/trends/ship.json` (scripts/trends/README.md)

## 분석 원고 고치는 법
1. `scripts/ship/deep_a.py`(완성선) · `deep_b.py`(엔진·LNG) · `deep_c.py`(피팅·블록) · `deep_d.py`(전장·서비스)에서 회사의 `C(...)`를 고쳐요. 업종 공통 해설은 `sector.py`, 공통 뉴스는 `news_sector.py`.
2. `python scripts/ship/build_deep.py` → deep.json · reviews.json · config/ship/valuation.json
3. `python scripts/build_valuation.py --industry ship` → docs/ship/data/valuation.json
- 정상 이익(E1)은 사이클 평균 이익이에요. 지금 이익과의 차이는 `excess` 배수(연도별)로 몇 년에 걸쳐 줄어들게 했어요(호황 정점 이익을 그대로 쓰지 않음).
- `ni_now`는 영업외 손익(금융자산 평가·외환 파생)이 큰 회사의 '최근 이익'을 영업이익 기준으로 바꾼 값이에요.
