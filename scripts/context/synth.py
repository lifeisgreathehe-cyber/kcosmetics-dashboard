"""모은 기사·블로그를 분석 칸(제품·경쟁·고객·조달·사이클·해자·전망)에 나누고, 한 줄 해석을 붙인다.

규칙 기반(키워드)이라 사람이 쓴 해석보다 거칠다. 그래서 화면에는 '자동 분류'라고 표시하고,
사람이 쓴 심층분석과 방향이 엇갈리면 '재검토 신호'로 띄워 사람이 다시 보게 한다.
"""
import re

SECTIONS = {
    "products": "제품·서비스",
    "competition": "경쟁",
    "customers": "고객·수요처",
    "sourcing": "원재료·조달",
    "cycle": "업황·사이클",
    "moat": "해자(경쟁우위)",
    "outlook": "전망·이벤트",
}

POS = r"상향|상회|↑|증가|상승|호조|개선|최대|흑자|확대|회복|반등|돌파|신고가|급증|성장|수혜|기대|호실적|서프라이즈|순항|강세|품절|인기|1위|선정|수상|흥행|돌풍|러브콜|청신호"
NEG = r"하향|하회|↓|감소|하락|부진|적자|악화|둔화|우려|쇼크|급락|축소|철수|취소|연기|위기|손실|역성장|약세|하향|경고|타격|논란|리콜|소송|과징금|압수수색|파업|화재|사고|부담|불확실|적신호|침체|구조조정|감산|폐쇄"

# (분류, 정규식, 기본 칸)
CATS = [
    ("pr", r"채용|멘토링|미술관|장학|성료|기부|봉사|후원|캠페인|화보|팝업|협업|컬래버|콜라보|동참|나눔|사회공헌|기념식|행사 개최|전시회 참가|모델 발탁|앰배서더|홍보대사|이벤트|프로모션|할인 행사|증정", None),
    ("risk", r"소송|리콜|압수수색|횡령|배임|화재|사고|과징금|불매|파업|상장폐지|감사의견|거래정지|유상증자|전환사채|CB 발행|회생|부도|제재", "outlook"),
    ("analyst", r"목표가|목표주가|투자의견|매수 유지|중립 하향|커버리지", "outlook"),
    ("earn_dn", r"(?:기대치|컨센서스|예상|전망치)[^,.…]{0,6}하회|적자 ?전환|적자 지속|어닝 ?쇼크|실적 부진|영업손실|역성장|영업이?익[^,.…]{0,14}(?:감소|급감|줄|↓|-\d)|매출[^,.]{0,12}(?:감소|급감|줄)", "cycle"),
    ("earn_up", r"(?:기대치|컨센서스|예상|전망치)[^,.…]{0,6}상회|사상 최대|역대 최대|최대 실적|어닝 ?서프라이즈|흑자 ?전환|호실적|깜짝 실적|실적 개선|영업이?익[^,.…]{0,14}(?:증가|급증|늘|↑|\+\d)|매출[^,.…]{0,12}(?:증가|급증|늘|↑)|판매 호조", "cycle"),
    ("order", r"수주|공급 ?계약|납품 ?계약|계약 체결|단일판매|양해각서|MOU|협약|파트너십|공급사로 선정|벤더 등록|퀄 테스트|품질 ?인증", "customers"),
    ("launch", r"출시|론칭|런칭|신제품|신규 브랜드|개발 성공|양산|품목허가|허가 획득|승인|FDA|임상|선보|공개", "products"),
    ("hot", r"인기|품절|열풍|흥행|돌풍|판매 급증|매출 급증|트렌드|대란|입소문|역대급|오픈런|완판|1위 등극|랭킹", "products"),
    ("capex", r"증설|신공장|공장 준공|준공|착공|설비 ?투자|캐파|CAPA|생산능력|생산 ?라인|투자 확대|신규 투자", "outlook"),
    ("input", r"원재료|원자재|원가|원료|유가|국제유가|환율|원당|원맥|곡물|리튬|니켈|코발트|구리|면화|납사|운임 상승|전기료|인건비", "sourcing"),
    ("price", r"가격 ?인상|판가|단가|값 (?:오른|올라|인상)|가격 ?인하|가격 하락|가격 상승|ASP", "products"),
    ("policy", r"관세|규제|보조금|정책|법안|수출 ?통제|반덤핑|IRA|세액공제|공정위|국회|정부|인허가", "outlook"),
    ("share", r"점유율|1위|선두|독점|과점|시장 지배|격차", "moat"),
    ("tech", r"특허|기술력|세계 최초|국내 최초|독자 기술|차세대|원천기술|국산화", "moat"),
    ("mna", r"인수|합병|매각|지분 ?(?:취득|매각|투자)|경영권|분할|자회사 편입", "outlook"),
    ("holder", r"배당|자사주|주주환원|소각|밸류업", "outlook"),
    ("rival", r"경쟁 심화|출혈|가격 경쟁|저가 공세|추격|공세|위협|맹추격|격전|각축", "competition"),
    ("cycle", r"업황|사이클|수요 회복|수요 둔화|재고 조정|공급 ?과잉|감산|가동률|스프레드|운임|시황|바닥|피크|정점|슈퍼사이클|불황|호황|성수기|비수기", "cycle"),
    ("export", r"수출|해외|미국|중국|일본|유럽|아마존|진출|글로벌|역직구|현지", "customers"),
]

# 분류 × 관계별 해석 (관계: self 본인, competitor 경쟁사, customer 고객사, supplier 공급사, industry 업종, blog 블로그)
READ = {
    ("earn_up", "self"): "실적이 좋아지고 있다는 뉴스예요. 일회성(환율·자산매각)인지, 제품 판매가 늘어서인지 실적 발표 숫자로 확인하세요.",
    ("earn_dn", "self"): "실적이 나빠졌다는 뉴스예요. 같은 업종 회사들도 함께 나빠졌다면 업황(사이클) 탓, 이 회사만 나쁘면 경쟁력 문제일 가능성이 커요.",
    ("earn_up", "competitor"): "경쟁사 실적이 좋아요. 업종 전체 수요가 살아나는 신호일 수 있지만, 이 회사 실적이 따라오지 못하면 점유율을 뺏기고 있다는 뜻이에요.",
    ("earn_dn", "competitor"): "경쟁사도 부진해요. 이 회사만의 문제가 아니라 업황(사이클) 영향일 가능성을 높여 주는 근거예요.",
    ("earn_up", "customer"): "고객사 실적이 좋아요. 고객이 잘 팔면 부품·원료·서비스 주문이 늘 가능성이 커요(보통 1~2분기 시차).",
    ("earn_dn", "customer"): "고객사가 부진해요. 발주 감소나 단가 인하 압력으로 이어질 수 있어 다음 분기 매출을 조심해서 보세요.",
    ("earn_up", "supplier"): "공급사 실적이 좋아요. 공급사가 가격 협상력을 가지는 국면이면 이 회사 원가에는 부담일 수 있어요.",
    ("earn_dn", "supplier"): "공급사가 부진해요. 원재료 공급 과잉·가격 하락 국면이면 이 회사 원가에는 도움이 돼요.",
    ("order", "self"): "새 계약·수주 뉴스예요. 계약 금액이 최근 연매출의 몇 %인지, 언제 매출로 잡히는지가 핵심이에요.",
    ("order", "competitor"): "경쟁사가 수주했어요. 같은 고객을 두고 경쟁했다면 이 회사에는 기회 상실, 업종 전체 발주가 늘어난 것이라면 긍정 신호예요.",
    ("order", "customer"): "고객사가 큰 계약을 땄어요. 고객의 생산이 늘면 이 회사 납품도 늘 수 있어요.",
    ("launch", "self"): "신제품·신규 사업 뉴스예요. 매출 비중이 의미 있게 커질 수 있는지(가격·시장 크기·경쟁 제품)를 보세요.",
    ("launch", "competitor"): "경쟁사 신제품이에요. 이 회사 주력 제품과 겹치는지, 가격을 낮춰 들어오는지 확인하세요.",
    ("launch", "customer"): "고객사 신제품이에요. 이 회사 제품·부품이 들어가는지에 따라 수혜가 갈려요.",
    ("hot", "self"): "제품이 소비자에게 인기를 얻고 있다는 신호예요. 반짝 유행인지, 재구매가 이어지는 브랜드인지 몇 달 지켜봐야 해요.",
    ("hot", "blog"): "블로그에서 제품 언급·후기가 늘고 있어요. 실제 판매로 이어지는지 다음 분기 매출과 함께 확인하세요.",
    ("hot", "competitor"): "경쟁 제품이 인기를 얻고 있어요. 이 회사 제품 수요를 빼앗는지 지켜보세요.",
    ("capex", "self"): "설비 투자 뉴스예요. 수요가 확실하면 미래 매출을 키우지만, 수요가 꺾이면 감가상각 부담과 가동률 하락이 돼요.",
    ("capex", "competitor"): "경쟁사가 생산능력을 늘려요. 업계 공급이 늘면 가격 경쟁이 심해질 수 있어 이 회사 마진에 부담이에요.",
    ("capex", "customer"): "고객사가 투자를 늘려요. 장비·소재·부품 회사에는 앞으로 주문이 늘 수 있다는 선행 신호예요.",
    ("capex", "supplier"): "공급사가 생산을 늘려요. 원재료 조달이 쉬워지고 가격이 안정될 수 있어요.",
    ("input", "self"): "원재료·환율 등 원가 뉴스예요. 원가 상승분을 판매가에 넘길 수 있는 회사인지가 이익을 가르는 포인트예요.",
    ("input", "industry"): "업종 원가 변수 뉴스예요. 가격 전가력이 약한 회사부터 마진이 흔들려요.",
    ("input", "supplier"): "공급사 쪽 가격 뉴스예요. 원재료 값이 오르면 이 회사 원가 부담, 내리면 마진 개선 요인이에요.",
    ("price", "self"): "판매 가격 뉴스예요. 가격을 올리고도 판매량이 유지되면 브랜드·기술 힘(해자)이 있다는 뜻이에요.",
    ("price", "competitor"): "경쟁사 가격 변화예요. 경쟁사가 값을 내리면 이 회사도 따라 내려야 하는지 보세요.",
    ("policy", "self"): "정책·규제 뉴스예요. 규정이 확정되는 시점과 이 회사 매출 중 영향받는 비중을 확인하세요.",
    ("policy", "industry"): "업종 전체에 걸리는 정책 변수예요. 수혜·피해가 회사별로 갈리니 해외 매출·생산지 구조를 함께 보세요.",
    ("share", "self"): "점유율·순위 뉴스예요. 순위가 오르면 경쟁력 강화, 떨어지면 경쟁력 약화의 직접 증거예요.",
    ("share", "competitor"): "경쟁사 점유율 변화예요. 경쟁사가 오르는 만큼 이 회사가 내려갔는지 확인하세요.",
    ("tech", "self"): "기술 우위 뉴스예요. 특허·최초 기술이 실제 가격 프리미엄이나 고객 확보로 이어질 때 해자가 돼요.",
    ("tech", "competitor"): "경쟁사 기술 진전이에요. 이 회사의 기술 격차가 좁혀지는지 지켜보세요.",
    ("mna", "self"): "인수·합병·지분 거래예요. 비싸게 샀는지, 본업과 시너지가 있는지가 주주가치를 좌우해요.",
    ("mna", "competitor"): "경쟁사 인수·합병이에요. 업계 재편으로 경쟁 구도가 바뀔 수 있어요.",
    ("holder", "self"): "주주환원 뉴스예요. 이익 대비 배당·자사주 소각 규모가 지속 가능한지 보세요.",
    ("rival", "self"): "경쟁이 심해지고 있다는 뉴스예요. 가격 인하가 이어지면 업황이 좋아져도 이익이 늘기 어려워요.",
    ("rival", "industry"): "업종 경쟁 심화 신호예요. 원가 경쟁력이 낮은 회사부터 수익성이 나빠져요.",
    ("cycle", "self"): "업황(사이클) 관련 뉴스예요. 이 회사 실적 변화가 업황을 따라가는지 비교해 보세요.",
    ("cycle", "industry"): "업종 사이클 신호예요. 회복이면 실적 바닥 통과, 둔화면 이익 정점 가능성을 의미해요.",
    ("cycle", "competitor"): "경쟁사 쪽 업황 뉴스예요. 같은 업황에서 이 회사 실적이 더 좋으면 경쟁력이 앞선 거예요.",
    ("cycle", "customer"): "고객 산업의 업황 뉴스예요. 고객 산업이 좋아지면 1~2분기 뒤 이 회사 주문으로 이어지는 경우가 많아요.",
    ("export", "self"): "해외 사업 뉴스예요. 해외 매출 비중과 성장률이 실제 실적에 나타나는지 확인하세요.",
    ("export", "industry"): "업종 수출 흐름이에요. 수출이 늘면 업종 매출이 살아나는 신호지만, 회사별로 지역 노출이 달라요.",
    ("analyst", "self"): "증권사 의견 변화예요. 목표가 숫자보다 바꾼 이유(실적 추정치 변경인지, 업황·밸류에이션 판단 변경인지)를 보세요.",
    ("analyst", "competitor"): "경쟁사에 대한 증권사 의견 변화예요. 업종 전체 눈높이가 바뀌는 중인지 함께 보세요.",
    ("risk", "self"): "리스크 이벤트예요. 금액·기간·재발 가능성을 따져 일회성인지, 기업 신뢰에 금이 가는 일인지 구분하세요.",
    ("risk", "competitor"): "경쟁사에 악재가 생겼어요. 고객이 이 회사로 옮겨 오는 반사이익이 생길 수 있어요.",
    ("risk", "customer"): "고객사 리스크예요. 대금 회수·발주 중단 가능성을 확인하세요.",
}
DEFAULT_READ = {
    "self": "회사 관련 소식이에요. 매출·이익·경쟁 구도 중 무엇이 달라지는지 생각해 보세요.",
    "competitor": "경쟁사 소식이에요. 이 회사와 같은 시장에서 무엇이 달라지는지 비교해 보세요.",
    "customer": "고객사 소식이에요. 고객의 생산·판매 변화는 보통 1~2분기 뒤 이 회사 주문으로 이어져요.",
    "supplier": "공급사 소식이에요. 원재료 가격·공급 안정성에 영향이 있는지 보세요.",
    "industry": "업종 전반 소식이에요. 업황이 좋아지는지 나빠지는지 가늠하는 배경 정보예요.",
    "blog": "블로그 글이에요. 소비자·투자자 관심의 온도를 보여 주지만 사실 확인은 필요해요.",
}
REL_LABEL = {"self": "회사", "competitor": "경쟁사", "customer": "고객사", "supplier": "공급사", "industry": "업종", "blog": "블로그"}


def tone_of(text):
    p, n = len(re.findall(POS, text)), len(re.findall(NEG, text))
    return "+" if p > n else "-" if n > p else "0"


def classify(item, rel):
    """기사 1건 → (분류, 칸, 이 회사 입장에서의 톤, 해석)."""
    text = item.get("title", "") + " " + (item.get("summary") or "")[:160]
    cat, sec = None, None
    for c, rx, s in CATS:
        if re.search(rx, text):
            cat, sec = c, s
            break
    raw = tone_of(text)
    if cat == "pr":
        sec = {"blog": "products", "industry": "cycle", "competitor": "competition", "customer": "customers", "supplier": "sourcing"}.get(rel, "products")
        return cat, sec, "0", "홍보·행사성 소식이에요. 브랜드 노출에는 도움이 되지만 실적에 주는 영향은 작아요." if rel in ("self", "blog") else "연관 기업의 홍보·행사성 소식이에요. 이 회사 실적과의 관련은 작아요."
    if cat in ("earn_up", "hot", "holder"):
        raw = "+"
    elif cat in ("earn_dn", "risk"):
        raw = "-"
    elif cat == "analyst":
        raw = "+" if re.search(r"상향|올려|↑|매수 ?(?:유지|제시)", text) and not re.search(r"하향|내려|↓", text) else "-" if re.search(r"하향|내려|↓", text) else "0"
    elif cat == "input":  # 원가: 상승 = 부담, 하락 = 도움
        raw = "-" if re.search(r"상승|급등|오르|올라|인상|강세", text) else "+" if re.search(r"하락|급락|내리|내려|인하|약세|안정", text) else "0"
    # 관계에 따라 이 회사 입장의 톤으로 바꾼다
    t = raw
    if rel == "competitor":
        if cat == "capex" or (cat in ("share", "tech", "order", "hot") and raw == "+"):
            t = "-"
        elif cat in ("launch", "export", "price", "policy", "mna", "holder", None):
            t = "0"
        elif cat == "risk":
            t = "+"
        elif cat in ("earn_up", "earn_dn", "cycle"):
            t = "0"  # 업황 신호로 쓰되 직접 호재·악재로 보지 않는다
    elif rel == "supplier" and cat in ("earn_up", "price"):
        t = "0"
    # 칸: 관계가 칸을 정하는 경우
    if rel == "competitor" and sec not in ("cycle",):
        sec = "competition"
    elif rel == "customer" and sec not in ("cycle",):
        sec = "customers"
    elif rel == "supplier":
        sec = "sourcing"
    elif rel == "blog" and sec in (None, "outlook", "cycle", "customers"):
        sec = "products"
    elif rel == "industry" and sec in (None, "customers", "outlook") and cat != "policy":
        sec = "cycle"
    sec = sec or ("cycle" if rel == "industry" else "outlook")
    read = READ.get((cat, rel)) or (READ.get((cat, "self")) if rel == "blog" else None) or DEFAULT_READ[rel]
    return cat, sec, t, read


def summarize_section(items):
    if not items:
        return None
    c = {"+": 0, "-": 0, "0": 0}
    for x in items:
        c[x["tone"]] += 1
    rels = sorted({REL_LABEL[x["rel"]] for x in items})
    lean = "긍정 우세" if c["+"] >= c["-"] + 2 else "부정 우세" if c["-"] >= c["+"] + 2 else "엇갈림"
    return {"n": len(items), "pos": c["+"], "neg": c["-"], "neu": c["0"], "lean": lean, "from": rels}


def cross_check(sig, deep_x, trend):
    """사이클 vs 경쟁력 교차 판정 + 사람이 쓴 전망과의 엇갈림."""
    def score(rel, secs=None, cats=None):
        xs = [x for x in sig if x["rel"] == rel and (secs is None or x["sec"] in secs) and (cats is None or x.get("cat") in cats)]
        return sum(1 if x["tone"] == "+" else -1 if x["tone"] == "-" else 0 for x in xs), len(xs)

    own, n_own = score("self")
    ind, n_ind = score("industry")
    comp_up = sum(1 for x in sig if x["rel"] == "competitor" and x.get("cat") in ("earn_up", "order", "share", "hot"))
    comp_dn = sum(1 for x in sig if x["rel"] == "competitor" and x.get("cat") in ("earn_dn",))
    cust, n_cust = score("customer")
    notes = []
    verdict = None
    if n_own >= 3 and n_ind >= 3 and own != 0:
        if own < 0 and ind < 0:
            verdict = ("사이클 영향 쪽", "회사 뉴스와 업종 뉴스가 함께 부정적이에요. 회사만의 문제라기보다 업황(사이클) 영향일 가능성이 커요.")
        elif own < 0 <= ind or (own < 0 and comp_up >= 2):
            verdict = ("경쟁력 점검 필요", "업종이나 경쟁사 뉴스는 나쁘지 않은데 회사 뉴스만 부정적이에요. 점유율·제품 경쟁력이 약해지는지 확인이 필요해요.")
        elif own > 0 and ind <= 0:
            verdict = ("경쟁력 우위 신호", "업종 분위기는 좋지 않은데 회사 뉴스는 긍정적이에요. 업황보다 회사 고유 경쟁력이 작동하는 신호예요.")
        elif own > 0 and ind > 0:
            verdict = ("업황 순풍", "회사와 업종 뉴스가 함께 긍정적이에요. 실적 개선의 상당 부분이 업황(사이클) 덕분일 수 있어, 정점 신호도 같이 지켜보세요.")
    if comp_dn >= 2 and own <= 0:
        notes.append("경쟁사들도 부진하다는 뉴스가 여러 건이라 업황 요인의 비중이 커 보여요.")
    if n_cust >= 2:
        notes.append(f"고객사 뉴스 {n_cust}건이 {'긍정' if cust > 0 else '부정' if cust < 0 else '중립'} 쪽이에요. 고객 업황은 보통 1~2분기 뒤 이 회사 주문에 반영돼요.")
    if trend and trend.get("chg") is not None:
        ch = trend["chg"]
        if ch >= 50:
            notes.append(f"{trend['label']}이 직전 같은 기간보다 {ch:.0f}% 늘었어요. 시장의 관심이 빠르게 커지는 중이에요.")
        elif ch <= -40:
            notes.append(f"{trend['label']}이 직전 같은 기간보다 {abs(ch):.0f}% 줄었어요. 관심이 식는 중이에요.")
    if deep_x and (deep_x.get("outlook") or {}).get("view"):
        v = deep_x["outlook"]["view"]
        recent = [x for x in sig if x["rel"] in ("self", "industry")][:15]
        s = sum(1 if x["tone"] == "+" else -1 if x["tone"] == "-" else 0 for x in recent)
        if v == "긍정" and s <= -4:
            notes.append("심층분석의 전망은 '긍정'인데 최근 회사·업종 뉴스는 부정 쪽이 많아요. 전망을 다시 볼 신호예요.")
        elif v == "부정" and s >= 4:
            notes.append("심층분석의 전망은 '부정'인데 최근 회사·업종 뉴스는 긍정 쪽이 많아요. 바닥 통과 여부를 다시 볼 신호예요.")
    return {"verdict": verdict, "notes": notes}
