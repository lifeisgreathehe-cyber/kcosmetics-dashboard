# 에너지·전력 대시보드 원고 (docs/energy)

94개사, 11개 하위 업종: 전력·발전(유틸리티), 원자력, 발전 정비·플랜트 기자재, 전력기기(변압기·차단기), 전선·케이블, ESS·전력IT·충전, 풍력, 태양광, 수소·연료전지, 가스·LPG·도시가스, 정유·윤활유.

| 파일 | 내용 |
|---|---|
| `universe.py` | 회사 목록·하위 업종·뉴스 검색어 → `config/energy/companies.json` |
| `seed_ed.py` | 초기 실적 시드(다른 대시보드 DART 실적 + 집계 데이터). 국내 PC에서 DART 수집하면 덮어써져요 |
| `sector.py` | 하위 업종별 전문가 해설(회사 해설 앞에 붙음) |
| `news_sector.py` | 업종 공통 뉴스와 회사별 해석(`NS`) |
| `deep_a~d.py` | 직접 쓴 74개사 심층 분석·리뷰·적정가 가정(정상 이익 E1, 성장률, 할인율) ·IR 분석 |
| `reuse.py` | 화학·철강·반도체·2차전지 대시보드와 겹치는 20개사: 그쪽 원고를 가져와 에너지 관점 뉴스를 앞에 붙임 |
| `build_deep.py` | 위 원고 → `docs/energy/data/deep.json`, `reviews.json`, `config/energy/valuation.json` |
| `valuation_head.json` | 적정가 방법 설명, 하위 업종별 사이클 위치 |

실행 순서
```
python scripts/energy/build_deep.py
python scripts/build_valuation.py --industry energy
```
산업동향 투자 지표(선행·동행 판정)는 `config/trends/energy.json`에 있어요(공용 모듈 `scripts/trends`).
