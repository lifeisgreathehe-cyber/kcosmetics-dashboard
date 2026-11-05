# 새로 추가한 회사의 전체 심층 분석 원고 공통 도우미 (2026-11-05)
# F(...)는 제품 해설·실적 진단(explain/diagnosis)과 심층 분석(deep)을 한 번에 만든다.
#  diag = (판정, 톤, 요약, [사이클 요인], [경쟁력 요인], [판단을 바꿀 신호])
#  fisher = 16줄 "점수 근거" (2=충족, 1=부분, 0=미흡), 질문 순서는 scripts/deep/build.py FISHER
#  moat = (등급, 점수 0~5, [원천], 이유),  outlook = (긍정/중립/부정, 요약, [기회], [위험])


def F(title, secs, diag, products, competition, customers, sourcing, fisher, moat, outlook):
    v, tone, sm, cy, st, ck = diag
    g, sc, srcs, why = moat
    ov, osm, up, rk = outlook
    return dict(
        explain=dict(title=title, sections=secs),
        diagnosis=dict(verdict=v, tone=tone, summary=sm, cycle=cy, structural=st, check=ck),
        deep=dict(products=products, competition=competition, customers=customers, sourcing=sourcing, fisher=fisher,
                  moat=dict(grade=g, score=sc, sources=srcs, reason=why),
                  outlook=dict(view=ov, summary=osm, upside=up, risks=rk)))
