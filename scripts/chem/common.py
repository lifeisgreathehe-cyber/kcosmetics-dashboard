# 화학·정유 회사별 심층 분석 원고 공통 도우미 (2026-11-05)
# F(...)는 제품 해설(explain)·실적 진단(diagnosis)·최근 뉴스 해석(news)·심층 분석(deep)을 한 번에 만든다.
#  secs  = [(소제목, 본문), ...]  주요 제품을 전문가 수준으로 설명
#  diag  = (판정, 톤 pos/neu/neg, 요약, [사이클 요인], [경쟁력 요인], [판단을 바꿀 신호])
#  news  = [(날짜, 제목, URL, 매체, 어떻게 읽어야 하나, 영향 pos/neu/neg), ...]
#  fisher = 16줄 "점수 근거" (2=충족, 1=부분, 0=미흡), 질문 순서는 scripts/deep/build.py FISHER
#  moat = (등급 넓음/좁음/없음, 점수 0~5, [원천], 이유),  outlook = (긍정/중립/부정, 요약, [기회], [위험])


def F(title, secs, diag, news, products, competition, customers, sourcing, fisher, moat, outlook):
    v, tone, sm, cy, st, ck = diag
    g, sc, srcs, why = moat
    ov, osm, up, rk = outlook
    rows = [l.strip() for l in fisher.strip().split("\n")]
    assert len(rows) == 16, (title, len(rows))
    fs = [{"s": int(l[0]), "a": l[2:].strip()} for l in rows]
    return dict(
        explain=dict(title=title, sections=[{"h": h, "p": p} for h, p in secs]),
        diagnosis=dict(verdict=v, tone=tone, summary=sm, cycle=cy, structural=st, check=ck),
        news=[dict(date=d, title=t, url=u, src=s, read=r, impact=i) for d, t, u, s, r, i in news],
        products=products, competition=competition, customers=customers, sourcing=sourcing,
        fisher=fs, fisher_score=sum(f["s"] for f in fs),
        moat=dict(grade=g, score=sc, sources=srcs, reason=why),
        outlook=dict(view=ov, summary=osm, upside=up, risks=rk))
