# 기업분석 리포트 원고 쓰기 (매일 루틴용)

`docs/report/METHOD.md`(이엔에프 AI 리포트 역엔지니어링)의 순서·문체 그대로, 회사 한 곳의 원고를 `config/report/<코드>.json`에 쓴다. 원고가 있으면 화면은 자동 문장 대신 원고를 쓰고, 숫자 표·차트·모델 계산은 그대로 자동이다. 형식 예시는 `config/report/102710.json`.

## 1. 대상 고르기
`python3 scripts/report/next_batch.py -n 20` → 새 실적이 나온 기존 원고(다시 쓰기)가 먼저, 그다음 원고 없는 회사를 시가총액 순서로.

## 2. 회사마다 읽을 자료 (원본 툴의 ①~④ 단계)
먼저 `NODE_PATH=$(npm root -g) node scripts/report/digest.js <코드…>`로 실적·화면 엔진 추정·기대수익률·업종 분석을 한 번에 본다. 엔진 기본값이 회사와 맞지 않으면(지주회사, 사이클 정점 이익, 적자에서 회복 중, 순이익 전환율 왜곡) model을 억지로 고치지 말고 `er` 문단에 그 한계와 무엇을 봐야 하는지 적는다.
1. `docs/report/data/c/<코드>.json`: 10년 연간·분기 실적, BS, 배당, 주주, 사업보고서 본문 발췌(biz: 연혁·사업 개요·제품·원재료·매출처·연구개발), 가동률, 분기 이익률 충격(shocks), 동종 회사(peers), 뉴스와 월별 기사 수, 자료 종합(src)
2. 업종 파이프라인: `docs/<업종>/data/deep.json`(제품·경쟁·고객·조달·전망), `context.json`(사업보고서 사실·연관 기업 신호), `ir_analysis.json`(IR 전략·과거 IR 대비 변화·교차 검증), `reviews.json`(분기 리뷰·뉴스 해석)
3. WebSearch: 최근 실적 발표, 증권사 추정(영업이익 컨센서스), 업황(시장 규모 기관 수치, 원재료 가격, 고객 증설), 최근 1~2개월 뉴스. 숫자는 확인된 것만 쓰고 출처를 적는다. 지어내지 않는다.

## 3. 쓰는 항목 (JSON 키)
- `asof`(오늘), `basis`(원고가 반영한 최신 분기, 예 "2026Q3"), `title`(한 줄 투자 논지), `note`(자료 범위)
- `cover`: `overview`(무엇을 누구에게 팔고 강점·약점), `outlook`(올해 누적과 내년 변화 요인), `opinion`(기대수익률 + 나눠 사는 조건 + 비중 축소 조건, 매수/매도 단어 금지)
- `sections`: 아래 키 중 쓸 수 있는 것만(문자열, 문단 사이 빈 줄). 근거 없으면 빼서 자동 문장이 나오게 둔다.
  - 1장 `intro` `founding` `holders` `price` / 2장 `value_chain` `products` `mix` `customers` `subs` `essence` `cost` `capacity` `strategy`
  - 3장 `market` `downstream` `upstream` `competition` / 4장 `peers` `switching` `cost_adv` `pricing` `roic` `moat_sum`
  - 5장 `capex` `wc` `oneoff` `alloc` / 6장 `drivers_past` `analog` `ytd` `drivers_future` `forecast` `consensus`
  - 7장 `bull` `bear` `debate` `retail` `discount` / 10장 `judgment` `er` `how`
- `points`: [{h, body, check(확인할 지표)}] 3~5개. `risks`: [{h, body}] 3~5개, 각 위험을 비관 가정·민감도와 연결("비관 시나리오는 이 경우")
- `consensus`: [{src, year, op(억원)}] 확인된 증권사 추정만. `sources`: [{nm, url}]
- `model`(선택): 회사별 근거가 있을 때만 `growth`·`gpm`·`sga_growth`·`ni_conv`·`per{bear,base,bull}`·`dps`. 없으면 넣지 않아 엔진 기본값을 쓴다. 넣으면 `_note`에 근거.
- `segments`는 IR·사업보고서에 부문 매출이 있을 때만.

## 4. 문체 규칙 (METHOD.md 4장)
결론 먼저, 근거 숫자와 출처. 회사 주장은 "회사는 ~라고 적고 있다"로 구분. 일정이 밀린 신제품은 보수적으로. 증권사와 다르면 어느 가정이 다른지. 표지에서부터 약점도 쓴다. 해자는 등급 없이 서술형. 업황 약세가 사이클인지 경쟁력 저하인지 판단해 적는다. 금액은 억원·조원, 평서문(~다).

## 5. 마무리
`python3 -c "import json,glob;[json.load(open(p,encoding='utf-8')) for p in glob.glob('config/report/*.json')]"` 로 JSON 확인 → `python3 scripts/report/build.py` → 커밋·푸시.
