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


# 피셔 16줄을 간단히: sc="2111..."(16자리 점수), why={질문번호(0~15): 근거}. 근거가 없으면 점수별 기본 문장을 쓴다.
_DEF = {
    0: ("시장이 정체되거나 줄고 있어요.", "시장 성장은 완만해요.", "앞으로 커질 시장을 가졌어요."),
    1: ("신제품 시도가 드물어요.", "신사업을 시도하지만 아직 규모가 작아요.", "신제품·신사업 의지가 뚜렷해요."),
    2: ("연구개발 성과가 잘 보이지 않아요.", "연구개발 규모는 작지만 꾸준해요.", "연구개발이 실제 제품으로 이어지고 있어요."),
    3: ("판매 조직이 평범한 수준이에요.", "주요 고객과의 관계는 안정적이에요.", "국내외 판매망이 강해요."),
    4: ("이익률이 낮거나 적자예요.", "업황에 따라 이익률 변동이 커요.", "이익률이 업계 평균보다 높아요."),
    5: ("이익률 개선 노력이 잘 보이지 않아요.", "원가 절감·제품 믹스 개선을 진행 중이에요.", "고부가 제품으로 이익률을 높이고 있어요."),
    6: ("노사 갈등 이력이 있어요.", "공개 정보가 적어 보수적으로 매겼어요.", "노사 관계가 원만해요."),
    7: ("경영진 내부 갈등 우려가 있어요.", "공개 정보가 적어 보수적으로 매겼어요.", "경영진 협력에 문제가 보이지 않아요."),
    8: ("오너 의존도가 높아요.", "공개 정보가 적어 보수적으로 매겼어요.", "전문경영 인력층이 두터워요."),
    9: ("원가·회계 관리에 의문이 있어요.", "특별한 문제는 보이지 않아요.", "원가 관리가 철저해요."),
    10: ("뚜렷한 차별점이 약해요.", "틈새 시장에서 일정한 우위가 있어요.", "업종 특유의 확실한 우위가 있어요."),
    11: ("단기 대응 위주예요.", "보수적으로 운영해요.", "장기 투자를 꾸준히 해요."),
    12: ("증자·전환사채 가능성이 있어요.", "투자 확대 시 차입이 늘 수 있어요.", "재무가 탄탄해 희석 위험이 낮아요."),
    13: ("나쁜 소식 공개가 늦은 편이에요.", "필요한 공시는 하지만 설명은 적어요.", "실적 설명이 솔직해요."),
    14: ("정직성에 의문을 남긴 사건이 있어요.", "특별한 의문은 없어요.", "정직성에 의문이 없어요."),
    15: ("주주환원이 인색해요.", "배당은 하지만 규모가 작아요.", "배당·자사주 등 환원이 적극적이에요."),
}


def FZ(sc, why=None):
    why = why or {}
    assert len(sc) == 16, sc
    return "\n".join(f"{c} {why.get(i, _DEF[i][int(c)])}" for i, c in enumerate(sc))


# IR 분석: 최신 IR 자료의 성장전략·달성 가능성, 과거 IR 대비 변화, 경쟁사·공급사·고객사 IR 교차검증
#  latest   = [(날짜, 자료명, URL), ...]  최신 IR 원문(또는 원문을 옮긴 공시·컨콜 전문) 링크, 최신순
#  strategy = [(전략, IR이 말한 세부 내용, 달성 가능성 근거, 등급 높음/중간/낮음), ...]
#  changes  = [(항목, 예전 IR(시점·내용), 최신 IR, 어떻게 읽나), ...]
#  cross    = [(상대 회사, 관계, 상대 IR·발표 내용, 검증 결과 일치/부분 일치/불일치/확인 중), ...]
#  sources  = [(제목, URL), ...]  분석에 쓴 기사·자료
def IR(summary, latest, strategy, changes, cross, sources, kind="IR"):
    return dict(summary=summary, kind=kind,
                latest=[dict(date=d, title=t, url=u) for d, t, u in latest],
                strategy=[dict(item=a, detail=b, check=c, grade=g) for a, b, c, g in strategy],
                changes=[dict(item=a, before=b, now=c, read=r) for a, b, c, r in changes],
                cross=[dict(peer=p, rel=r, claim=c, result=v) for p, r, c, v in cross],
                sources=[dict(title=t, url=u) for t, u in sources])
