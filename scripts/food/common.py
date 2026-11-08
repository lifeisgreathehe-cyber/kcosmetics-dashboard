# 음식료 회사별 원고 공통 도우미 (2026-11-08 작성)
# 회사마다 세 가지를 한 파일(scripts/food/co_*.py)에 같이 적는다.
#  D[code] = F(...)  심층 분석: 제품 전문가 해설·실적 진단(사이클 vs 경쟁력)·해자·피셔 16문항·3~4년 전망
#  R[code] = dict(tone, title, eval, watch, news, next, points)  최근 4개 분기 리뷰와 최신 뉴스 해석
#  V[code] = dict(cyc_pos, cycle_note, g, r, c, margin 또는 E1_adj, note)  내재가치 가정(사이클 위치·정상 이익)
# news 항목: (날짜, 제목, URL, 매체, 이렇게 보세요, 영향 "+"/"-"/"0")
import importlib.util, os
_sp = importlib.util.spec_from_file_location("chem_common", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "chem", "common.py"))
_cc = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(_cc)
_FZ = _cc.FZ  # 피셔 16문항 기본 문장(화학 스레드와 같은 문구)


def FZ(sc, why=None):
    return _FZ(sc, why)


def F(title, secs, diag, products, competition, customers, sourcing, fisher, moat, outlook):
    v, tone, sm, cy, st, ck = diag
    g, sc, srcs, why = moat
    ov, osm, up, rk = outlook
    rows = [l.strip() for l in fisher.strip().split("\n")]
    assert len(rows) == 16, (title, len(rows))
    fs = [{"s": int(l[0]), "a": l[2:].strip()} for l in rows]
    return dict(
        explain=dict(title=title, sections=[{"h": h, "p": p} for h, p in secs]),
        diagnosis=dict(verdict=v, tone=tone, summary=sm, cycle=cy, structural=st, check=ck),
        products=products, competition=competition, customers=customers, sourcing=sourcing,
        fisher=fs, fisher_score=sum(f["s"] for f in fs),
        moat=dict(grade=g, score=sc, sources=srcs, reason=why),
        outlook=dict(view=ov, summary=osm, upside=up, risks=rk))


def V(pos, note_cycle, g, r, c, note, margin=None, adj=None, **kw):
    """pos: 호황 정점권·상승기·회복기·중립·하강기·바닥권 / g=(비관, 기준, 낙관) / margin=정상 순이익률(%) 또는 adj=사이클 평균 이익 배수"""
    d = dict(cyc_pos=pos, cycle_note=note_cycle, g=dict(bear=g[0], base=g[1], bull=g[2]), r=r, c=c, note=note)
    if margin is not None:
        d["margin"] = margin
    if adj is not None:
        d["E1_adj"] = adj
    d.update(kw)
    return d


NEXT_3Q = "3분기 분기보고서는 11월 14일까지 공시돼요. 그 전에 잠정실적(공정공시)이 나오면 바로 반영해요."

# 업종 공통 기사 (여러 회사에 같이 붙는 뉴스)
S_FTC_RAMEN = ("2026-11-02", "CJ제일제당·대상 이어 농심·오뚜기까지…공정위, 식품업계 전방위 조사", "https://zdnet.co.kr/view/?no=20261102171520", "지디넷코리아",
  "공정위가 10월 14일 CJ제일제당·대상·오뚜기 등의 김치·두부·유지류·선물세트·즉석밥·장류 가격을, 10월 28일엔 농심·삼양식품·오뚜기·팔도의 라면값 인상 시기·폭 사전 협의 여부를 현장조사했어요. 올해 이미 설탕(4,083억원)·밀가루(6,710억원)·전분당(7,476억원) 담합에 과징금 1조8천억원대가 매겨졌어요. 혐의가 확정되면 일회성 과징금이 나오고, 더 중요하게는 앞으로 2~3년 '원가가 올라도 가격을 쉽게 못 올리는' 압력이 생겨요. 그래서 정상 이익률을 잡을 때 내수 가격 결정력을 조금 낮춰 봤어요.", "-")
S_FTC_PROC = ("2026-10-14", "공정위, 가공식품 6개 식품군 가격 담합 의혹 조사 착수", "https://sateconomy.co.kr/news/view/1065597804574269", "토요경제",
  "새로 꾸린 중점조사기획단(약 40명)의 첫 대형 사건이에요. 아직 사실 확인 단계라 위반이 확정된 건 아니에요. 다만 정부가 '먹거리 물가'를 정책 과제로 잡았다는 신호라, 내수 비중이 큰 회사일수록 가격 인상으로 원가를 넘기는 속도가 느려질 수 있어요.", "-")
S_PRICE = ("2026-08-14", "식품업계, 해외 사업이 희비 갈랐다…농심·삼양·오리온 웃고 CJ·롯데칠성·삼립 울상", "https://www.ceoscoredaily.com/page/view/2026081415575314032", "CEO스코어데일리",
  "2분기 실적은 해외 비중이 큰 회사(삼양·농심·오리온)가 좋고 내수 중심 회사(CJ제일제당 식품·롯데칠성·삼립)가 나빴어요. 7~10월엔 CJ제일제당(27개 품목 평균 8%)·농심(43개 브랜드 5.8%)·오뚜기·롯데칠성·해태 등이 줄줄이 가격을 올렸어요. 원가가 먼저 오르고 가격이 1~2분기 늦게 따라가는 구조라, 4분기~내년 상반기에 마진이 회복되는 게 음식료의 전형적인 원가 사이클이에요.", "0")
S_3Q = ("2026-10-18", "불닭·신라면 날고, 내수는 주춤…식품업계 3분기 실적도 '해외'가 가른다", "https://www.mt.co.kr/living/2026/10/18/2026101511584592963", "머니투데이",
  "3분기 컨센서스는 삼양식품(영업이익 +43%)·농심(+15%)·빙그레(+30%)·롯데웰푸드(+24%)가 좋고, CJ제일제당(-4%)·롯데칠성(-8%)이 약해요. 1~9월 라면 수출은 13억 달러로 27% 늘었어요. 원/달러 환율이 7월 1,497원에서 9월 1,359원으로 내려와 수입 원재료 부담은 4분기부터 줄어드는 방향이에요.", "0")
S_FX = ("2026-10-21", "3Q26 Preview: 악재보다는 호재를 봐야 할 때 (음식료 Overweight)", "https://file.alphasquare.co.kr/media/pdfs/market-report/%EC%9D%8C%EC%8B%9D%EB%A3%8C3Q2620261021%ED%82%A4%EC%9B%80%EC%A6%9D%EA%B6%8C.pdf", "키움증권",
  "3분기 원재료 투입 단가는 소맥 톤당 250달러(+30%), 대두 453달러(+22%), 옥수수 188달러(+19%)로 1년 전보다 크게 올랐고, 4분기엔 원당이 459달러(+38%)로 더 올라요. 반대로 원/달러는 3분기 평균 1,423원에서 4분기 1,349원으로 내려갈 전망이에요. 곡물 상승과 환율 하락이 서로 상쇄되는 구간이라, 가격을 올린 회사는 4분기부터 마진이 좋아지고 못 올린 회사는 더 눌려요.", "0")
