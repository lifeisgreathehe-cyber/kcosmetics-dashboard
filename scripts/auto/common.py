# 자동차 회사별 원고 공통 도우미 (2026-11-14 작성)
# 회사마다 co(...) 한 번으로 세 가지를 같이 적는다 (scripts/auto/co_*.py).
#  D[code]  심층 분석: 제품·서비스 전문가 해설, 실적 진단(사이클 vs 경쟁력), 제품·경쟁·고객·조달, 피셔 16문항, 해자, 3~4년 전망
#  R[code]  최근 4개 분기 리뷰와 최신 뉴스 해석 (tone, title, eval, watch, news, next, points)
#  VAL[code] 내재가치 가정: 사이클 위치(cyc_pos)·성장 시나리오 g·자기자본비용 r·현금 전환율 c, 정상 이익(E1 억원 또는 margin 정상 순이익률 % 또는 E1_adj)
# news 튜플: (날짜, 제목, URL, 매체, 이렇게 보세요, 영향 "+"/"-"/"0")
import importlib.util, os
_sp = importlib.util.spec_from_file_location("chem_common", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "chem", "common.py"))
_cc = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(_cc)
FZ = _cc.FZ  # 피셔 16문항: FZ("16자리 점수", {문항번호(0~15): 근거}) — 근거 없는 문항은 점수별 기본 문장

D, R, VAL = {}, {}, {}


def V(pos, note_cycle, g, r, c, note, margin=None, adj=None, E1=None, **kw):
    """pos: 호황 정점권·상승기·회복기·중립·하강기·바닥권 / g=(비관, 기준, 낙관) 1~5년차 이익 성장률 %
    정상 이익: E1(억원, 사람이 직접) > margin(정상 순이익률 %, 추세 매출에 곱함) > adj(DART 사이클 평균 이익 배수)"""
    d = dict(cyc_pos=pos, cycle_note=note_cycle, g=dict(bear=g[0], base=g[1], bull=g[2]), r=r, c=c, note=note)
    if E1 is not None:
        d["E1"] = E1
    if margin is not None:
        d["margin"] = margin
    if adj is not None:
        d["E1_adj"] = adj
    d.update(kw)
    return d


def co(code, title, secs, diag, products, competition, customers, sourcing, fisher, moat, outlook, review, val):
    v, tone, sm, cy, st, ck = diag
    g, sc, srcs, why = moat
    ov, osm, up, rk = outlook
    rows = [l.strip() for l in fisher.strip().split("\n")]
    assert len(rows) == 16, (title, len(rows))
    fs = [{"s": int(l[0]), "a": l[2:].strip()} for l in rows]
    D[code] = dict(
        explain=dict(title=title, sections=[{"h": h, "p": p} for h, p in secs]),
        diagnosis=dict(verdict=v, tone=tone, summary=sm, cycle=cy, structural=st, check=ck),
        products=products, competition=competition, customers=customers, sourcing=sourcing,
        fisher=fs, fisher_score=sum(f["s"] for f in fs),
        moat=dict(grade=g, score=sc, sources=srcs, reason=why),
        outlook=dict(view=ov, summary=osm, upside=up, risks=rk))
    review.setdefault("next", NEXT)
    review.setdefault("points", [])
    R[code] = review
    VAL[code] = val


NEXT = "3분기 분기보고서는 11월 14일까지 공시돼요. 4분기·연간 실적은 2027년 1월 말~2월 중순(대형사 잠정실적)과 3월 사업보고서로 나와요."

# ------------------------------------------------------------------ 업종 공통 기사 (여러 회사에 같이 붙는 뉴스)
S_TARIFF_COST = ("2026-09-29", "현대차·기아, 관세 10조에 곳간 5조 줄었다…부품사에 번지는 관세 청구서", "https://www.dailian.co.kr/news/view/1695874", "데일리안",
  "현대차·기아는 2025년 관세 비용 약 7조원, 2026년 상반기에도 3조원 넘게 인식했고 두 회사 합산 영업이익(EBIT)이 2024년 24조원에서 2025년 16조원으로 줄었어요. 관세는 부품사의 미국 법인(수입자)이 내고 현대차가 1차 협력사 부담을 소급 지원했지만, 원가 압박이 길어지면 납품 단가 인하로 부품사에 번질 수 있다는 경고예요. 1차 협력사 1,430곳 납품액 71.7조원 중 현대차 52%, 기아 38%라 그룹 의존도가 높은 부품사일수록 이 위험에 노출돼요. 부품 관세 환급(미국 생산차 가격의 3.75%)은 2030년까지 유지돼요.", "-")
S_TARIFF_JAN = ("2026-01-26", "'관세 25%' 폭탄 발언에 현대차주 급브레이크", "https://www.heraldk.com/article/2026012617304711353", "헤럴드경제",
  "트럼프 대통령이 한국 국회의 무역협정 비준 지연을 이유로 자동차 관세를 15%에서 25%로 되돌리겠다고 SNS에 올렸어요. 삼성증권은 25%가 되면 연간 관세 영향을 현대차 5조원·기아 4조원으로 추정했어요. 날짜가 없는 발언이라 비준 압박용으로 해석됐고 실제 세율은 15%로 유지되고 있어요. 이런 '정책 꼬리 위험'은 정상 이익을 정할 때 할인 요인(비관 시나리오)으로 넣었어요.", "-")
S_ELECTION = ("2026-11-08", "[美선거 산업여파] 자동차 관세 부담 지속될 듯…전기차는 기대", "https://www.fnnews.com/news/202611080532096016", "파이낸셜뉴스(연합뉴스)",
  "11월 3일 중간선거에서 민주당이 상·하원을 가져갔지만, 한국산 차 15% 관세는 무역확장법 232조(대통령 권한)라 의회만으로 바로 내려가긴 어려워요. 현대차그룹은 대미 투자를 260억 달러로 늘리고 미국 판매의 현지 생산 비중을 2024년 40%에서 2029년 80% 이상으로 높일 계획이에요. 결국 관세는 '없어질 비용'이 아니라 '현지화로 줄여갈 비용'으로 봐야 해요. 부품 관세 상쇄 제도의 2030년 연장, 멕시코 생산 부품사의 USMCA 리스크도 함께 짚었어요.", "0")
S_EXPORT_OCT = ("2026-11-01", "올해 수출 '꿈의 1조 달러' 눈앞…10월 자동차 수출 65.5억 달러, 10월 최대", "https://www.koreancenter.or.kr/news/articleView.html?idxno=1432880", "연합뉴스",
  "10월 자동차 수출은 65.5억 달러로 18.1% 늘어 역대 10월 최대였어요. 추석 연휴가 9월로 옮겨 조업일수가 늘었고 하이브리드 수출이 좋았어요. 8~9월 파업·연휴로 빠졌던 물량이 돌아오는 중이라 4분기 완성차·부품 매출은 3분기보다 좋아질 가능성이 커요. 다만 기저효과가 섞여 있어 '수요가 강해졌다'고 읽기보다는 '생산이 정상화됐다'고 보는 게 맞아요.", "+")
S_SEP = ("2026-10-19", "2026년 9월 자동차산업 동향 (산업통상부)", "https://www.motir.go.kr/kor/article/ATCL3f49a5a8c/172302/view", "산업통상부",
  "9월 자동차 수출 60.5억 달러(-5.5%), 내수 13.5만 대(-14.3%), 생산 34.7만 대(+3.7%)였어요. 생산은 임금협상 타결로 파업 손실을 만회했지만, 내수는 추석 연휴(영업일 3일 감소)·신차 대기·전기차 보조금 소진으로 줄었어요. 중동 전쟁과 주요국 규제로 중고차 수출이 줄어 중동 수출이 -7%였어요. 친환경차가 내수의 59%를 차지할 만큼 하이브리드 전환이 빨라요.", "0")
S_AUG = ("2026-09-17", "8월 車수출·생산·내수 트리플 감소…파업 직격탄", "https://www.newsis.com/view/NISX20260917_0003793115", "뉴시스",
  "8월 자동차 수출은 38.5억 달러로 29.8% 줄었고, 현대차 국내 생산은 54.8% 급감했어요. 원인은 수요가 아니라 파업과 조업일수 감소예요. 임금협상이 모두 타결돼 하반기 회복을 전망했어요. 부품사 입장에선 3분기 매출이 일시적으로 빠진 것이라 경쟁력 약화로 볼 일은 아니에요(일회성 생산 차질).", "-")
S_HK3Q = ("2026-10-29", "현대차, 판매 11% 급감에도 영업익 5.5% 증가…연간 목표는 낮췄다", "https://www.fnnews.com/news/202610291611190711", "파이낸셜뉴스",
  "현대차 3분기 매출 45.1조원(-3.4%), 영업이익 2.68조원(+5.5%)이었지만 판매는 92만 대(-11.3%)로 줄었어요. 연간 판매 목표를 416만→400만 대, 영업이익률 목표를 6.3~7.3%→5.5~6.5%로 낮췄어요. 완성차 감산은 1~2개월 시차로 부품사 매출에 그대로 이어져요.", "-")
S_KIA3Q = ("2026-10-30", "기아, 3분기 영업익 1조8183억원…미국 HEV 점유율 10%대", "https://m.ceoscoredaily.com/page/view/2026103016280201739", "CEO스코어데일리",
  "기아 3분기 매출 31.6조원(+10.1%), 영업이익 1.82조원(+24.3%)이었지만 시장 기대(약 2.3~2.4조원)를 크게 밑돌았어요. 관세 인하로 약 5,300억원 이익이 늘었지만 원자재(-3,680억원)·중동 판매 차질과 물류비(-2,090억원)·인센티브(-7,270억원)가 더 컸어요. 판매는 7.9% 늘어 기아 협력사(차체·내장)의 물량은 견조해요.", "0")
S_MOBIS3Q = ("2026-10-30", "외형·내실 모두 끌어올린 모비스…고민거리도 선명해졌다", "https://news.bizwatch.co.kr/article/industry/2026/10/30/0016", "비즈니스워치",
  "현대모비스 3분기 모듈·핵심부품 영업이익 335억원(흑자 전환), A/S 8,807억원이에요. 주요 고객사 완성차 생산량은 -2.3%, 전기차 생산량은 +12.8%였어요. 그룹 전체 생산은 줄었지만 유럽 전기차 물량이 늘어 전동화 부품(배터리 시스템·구동 모터) 업체에는 숨통이 트였어요.", "0")
S_TIRE3Q = ("2026-11-10", "같은 타이어 팔아도 남는 돈은 8배…한국·금호·넥센, 수익성 격차 왜?", "https://m.dailian.co.kr/news/view/1713094/", "데일리안",
  "3분기 영업이익률이 한국타이어(타이어 사업) 18.0%, 금호타이어 10.5%, 넥센타이어 2.2%로 크게 갈렸어요. 차이는 18인치 이상 고인치 비중(49.7%·48.8%·41.5%)과 미국 공장 유무예요. 한국은 테네시, 금호는 조지아 공장이 있어 15% 관세를 피하지만, 넥센은 미국 생산이 없어 관세와 운반비(매출의 10.3%)를 그대로 떠안아요.", "0")
S_TIRE2Q = ("2026-08-04", "고부가 타이어가 갈랐다…타이어 3사, 최대 매출에도 영업익 희비", "https://newstomato.com/ReadNews.aspx?no=1309163", "뉴스토마토",
  "미국 수입 타이어에는 기본 관세 4% + 232조 관세 15% + 회사별 반덤핑 관세(한국 13.03%, 금호 10.53%, 넥센 8.02%)가 붙어요. 고인치 타이어 이익률은 15~20%, 일반 타이어는 약 5%로 추정돼요. 하반기 변수로 중동 정세에 따른 천연고무 가격과 해상운임 상승을 꼽았어요.", "0")
S_ELECTION_STOCK = ("2026-11-05", "미 민주당 상·하원 장악에 현대차 3.53% 상승", "https://www.insight.co.kr/news/580848", "인사이트",
  "현대차 10월 미국 판매는 7만3,452대(+5%)로 10월 최대였고 하이브리드 비중이 29%예요. 미국 전기차 세액공제(최대 7,500달러)는 9월 30일 끝나 전기차보다 하이브리드가 미국 판매를 이끌고 있어요. 하이브리드 부품(변속기·모터·배터리 시스템·열관리)을 만드는 부품사에 유리한 흐름이에요.", "+")


# ------------------------------------------------------------------ 중소형 부품사용 짧은 서식
def sm(code, title, secs, diag, pcs, fz, moat, outlook, rv, val):
    """pcs = (products, competition, customers, sourcing), fz = FZ(...) 결과"""
    co(code, title, secs, diag, pcs[0], pcs[1], pcs[2], pcs[3], fz, moat, outlook, rv, val)


def RV(tone, title, eval_, watch, news, points=None):
    return dict(tone=tone, title=title, eval=eval_, watch=watch, news=news, points=points or [])


Q3_NOTE = "분기보고서(11월 14일 공시) 숫자는 PC에서 DART 수집을 돌리면 위 실적 표와 4분기 추이에 자동으로 채워져요."
