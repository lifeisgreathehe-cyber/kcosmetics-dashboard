# 반도체 매일 뉴스 해석

매일 저녁 `docs/semi/data/news.json`(하루 6번 자동 수집)에서 새로 나온 회사 기사를 읽고,
`news_daily/YYYYMMDD.py`에 해석을 적는다. 파일 안에서는 `news_src.py`의 함수를 그대로 쓴다.

```python
ASOF = "2026-11-06"   # 이 날짜까지 반영
ADD("108320",
    [("2026-11-06", "기사 제목", "030/0003482341", "매체", "어떻게 볼까(해요체)", "pos|neg|neu")],
    take="(선택) 최신 판단 문단 교체", latest=L(rev, op, ni, "잠정실적 설명"), tone="pos", asof=ASOF)
SECTOR.append(("2026-11-06", "업종 공통 기사", NV + "...", "매체", {"전공정 장비": ("해석", "neg")}, ("기본 해석", "neu")))
```

숫자를 바꾸는 뉴스(잠정실적, 대형 수주, 일회성 손익)는 `valuation_src.py`의 E1·사이클 위치·now=도 고친다.
그다음 `python3 scripts/semi/build_reviews.py && python3 scripts/semi/valuation_src.py && python3 scripts/build_valuation.py --industry semi`.
