"""다른 대시보드와 겹치는 20개사: 그쪽 deep.json·reviews.json·valuation.json을 가져와 에너지 관점 뉴스를 앞에 더한다.
원고 수정은 원래 대시보드(scripts/chem, scripts/steel, scripts/semi, scripts/battery)에서 하면 돼요."""
import copy, json, os
from news_sector import N_CABLE, N_GRID, N_GRID2, N_TRX, N_HSOL, N_OCI, N_SMP10, N_KOGAS, N_CSW, N_OFFW

SRC = {"chem": "009830 010060 018670 017940 128820 096770 010950 078930 267250 002960 003650 014530",
       "steel": "006260 001440 000500 006340 229640 044490", "semi": "011930", "battery": "089980"}
IMP = {"+": "pos", "-": "neg", "0": "neu"}


def _n(item, read=None, impact=None):
    d, t, u, s, r, i = item
    return dict(date=d, title=t, url=u, src=s, read=read or r, impact=impact or i)


CABLE = [_n(N_CABLE), _n(N_GRID, "한전 송배전 투자 확대는 초고압·중저압 케이블 수요를 늘려요.", "+")]
EXTRA = {
    "006260": CABLE + [_n(N_OFFW, "해상풍력 입찰 확대는 LS전선의 해저 케이블 수주로 이어져요.", "+")],
    "001440": CABLE + [_n(N_OFFW, "대한전선 해저 케이블 공장 가동 시점과 해상풍력 입찰이 맞물려요.", "+")],
    "000500": CABLE, "006340": CABLE,
    "229640": [_n(N_GRID2, "전력망 병목은 HVDC·초고압 송전 투자를 앞당겨 LS에코에너지(케이블) 수요에 긍정적이에요.", "+")],
    "044490": [_n(N_CSW, "풍력 타워·단조품 발주는 씨에스윈드와 같은 사이클을 타요. 해상풍력 공백은 태웅에도 부담이에요.", "-")],
    "009830": [_n(N_HSOL), _n(N_SMP10, "국내 SMP·REC 하락은 국내 태양광 발전사업 수익에 부담이에요.", "-")],
    "010060": [_n(N_OCI)],
    "011930": [_n(N_HSOL, "한화큐셀의 미국 모듈 흑자는 미국 태양광 장비 수요가 유지된다는 신호예요.", "+")],
    "078930": [_n(N_KOGAS, "도시가스·LNG 도매 요금 동결은 GS의 발전(GS EPS)·에너지 계열 수익에 영향을 줘요.", "0")],
    "267250": [_n(N_TRX, "HD현대일렉트릭의 변압기 호황이 지주사 HD현대 가치에 반영돼요.", "+")],
}


def load_reuse(root):
    D, R, V = {}, {}, {}
    for ind, codes in SRC.items():
        dp = json.load(open(os.path.join(root, f"docs/{ind}/data/deep.json"), encoding="utf-8"))["companies"]
        rp = json.load(open(os.path.join(root, f"docs/{ind}/data/reviews.json"), encoding="utf-8"))["companies"]
        vp = json.load(open(os.path.join(root, f"config/{ind}/valuation.json"), encoding="utf-8"))["companies"]
        for c in codes.split():
            if c not in dp:
                continue
            ex = EXTRA.get(c, [])
            d = copy.deepcopy(dp[c])
            ts = {n["title"] for n in ex}
            d["news"] = ([dict(n, impact=IMP.get(n["impact"], n["impact"])) for n in ex] + [n for n in d.get("news", []) if n["title"] not in ts])[:8]
            d["reused_from"] = ind
            D[c] = d
            r = copy.deepcopy(rp.get(c) or {})
            if r:
                r["news"] = ex + [n for n in r.get("news", []) if n["title"] not in ts]
            R[c] = r
            if c in vp:
                V[c] = copy.deepcopy(vp[c])
    return D, R, V
