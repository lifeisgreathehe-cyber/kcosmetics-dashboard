"""D램·낸드 고정거래가격(DRAMeXchange, 월평균, 달러) — 언론 보도에서 확인한 값만 기록.
값 없는 달은 None(보도에서 확인 못 함). imp=True는 '전월과 같다'는 표현으로 추정한 값.
새 달이 나오면 ROWS에 한 줄 추가 후: python scripts/semi/memory_prices.py
"""
import json, os
# (월, DDR4 8Gb, 낸드 128Gb MLC, 출처 URL, 추정여부)
ROWS = [
 ("2020-10",2.85,None,"https://www.inews24.com/view/1354581",True),
 ("2020-11",2.85,4.2,"https://www.inews24.com/view/1354581",False),
 ("2020-12",2.85,4.2,"https://www.inews24.com/view/1354581",False),
 ("2021-01",3.00,4.2,"https://www.inews24.com/view/1354581",False),
 ("2021-02",3.00,4.2,"https://www.inews24.com/view/1354581",True),
 ("2021-03",3.00,4.2,"https://www.inews24.com/view/1354581",False),
 ("2021-04",3.80,4.56,"https://www.inews24.com/view/1363369",False),
 ("2021-05",3.80,4.56,"https://www.ddaily.co.kr/page/view/2021053114534485148",False),
 ("2021-07",4.10,None,"https://www.inews24.com/view/1447689",False),
 ("2021-10",3.71,None,"https://www.inews24.com/view/1544253",False),
 ("2022-01",3.41,4.81,"https://www.inews24.com/view/1447689",False),
 ("2022-02",3.41,4.81,"https://www.inews24.com/view/1455837",False),
 ("2022-04",3.41,4.81,"https://dailian.co.kr/news/view/1119101",True),
 ("2022-05",3.35,4.81,"https://dailian.co.kr/news/view/1119101",False),
 ("2022-08",2.85,None,"https://www.ddaily.co.kr/page/view/2022093014594033269",True),
 ("2022-09",2.85,4.30,"https://www.ddaily.co.kr/page/view/2022093014594033269",False),
 ("2022-10",2.21,4.14,"https://www.inews24.com/view/1544253",True),
 ("2022-11",2.21,4.14,"https://www.inews24.com/view/1544253",False),
 ("2023-01",1.81,4.14,"https://www.metroseoul.co.kr/article/20230228500385",True),
 ("2023-02",1.81,4.14,"https://www.metroseoul.co.kr/article/20230228500385",False),
 ("2024-04",2.1,4.9,"https://biz.sbs.co.kr/amp/article/20000169815",False),
 ("2024-11",1.35,2.16,"https://www.segye.com/newsView/20241129509986",False),
 ("2025-03",1.35,2.51,"https://www.newsis.com/view/NISX20250401_0003121277",False),
 ("2025-04",1.65,None,None,False),
 ("2025-06",2.6,3.1,None,False),
 ("2025-09",6.3,3.79,"https://v.daum.net/v/20250930184717578",False),
 ("2025-10",7.0,None,"https://www.fnnews.com/news/202511011055424273",False),
 ("2025-11",8.1,5.19,"https://biz.heraldcorp.com/article/2025112801383248503",False),
 ("2026-02",13.0,None,None,False),
 ("2026-03",13.0,17.73,"https://www.segye.com/newsView/20260430518350",False),
 ("2026-04",16.0,24.16,"https://www.segye.com/newsView/20260430518350",False),
 ("2026-05",20.0,26.5,"https://www.asiae.co.kr/article/2026052917261871195",False),
 ("2026-06",21.0,28.8,"https://biz.sbs.co.kr/article/20000320036",False),
 ("2026-07",24.0,30.1,"https://biz.sbs.co.kr/article/20000326267",False),
 ("2026-08",25.0,30.5,"https://biz.sbs.co.kr/article/20000331933",False),
 ("2026-09",26.0,30.61,"https://www.kita.net/board/totalTradeNews/totalTradeNewsDetail.do?no=105023",False),
 ("2026-10",27.5,30.61,"https://www.thelec.kr/news/articleView.html?idxno=64634",False),
]
READ = [
 ("D램은 아직 오르는 중", "DDR4 8Gb 고정가는 2025년 3월 1.35달러에서 2026년 10월 27.5달러로 약 20배가 됐어요. 2021년 고점(4.1달러)을 크게 넘었고 10월에도 사상 최고를 다시 썼어요. 트렌드포스는 4분기 PC D램 13~18% 추가 상승을 예상해요. HBM·서버용 증설에 생산능력이 쏠려 범용 D램 공급이 모자란 영향이에요."),
 ("낸드는 상승이 멈췄어요", "낸드 128Gb MLC는 2026년 9월과 10월이 30.61달러로 같아요. 21개월 연속 오르다 처음 멈춘 거예요. 과거 사이클에서는 '오르던 가격이 횡보'로 바뀐 뒤 몇 달 안에 하락으로 돌아선 경우가 많았어요(2021년 7월 D램 4.1달러 고점 → 2023년 1.81달러)."),
 ("어떻게 판단할까요", "① D램과 낸드 중 하나가 먼저 꺾이면 업황 정점이 가깝다는 신호예요. 지금은 낸드가 먼저 멈춘 단계예요. ② 메모리 회사 이익은 가격을 2~3개월 늦게 따라가요. 그래서 가격이 멈춰도 다음 분기 실적은 좋게 나올 수 있어요. ③ 주가는 보통 가격 정점보다 먼저 꺾여요. 매달 말 발표되는 고정가가 전월보다 내리기 시작하는지가 가장 중요한 확인점이에요."),
 ("어느 회사에 영향이 큰가요", "D램 가격은 삼성전자·SK하이닉스 이익에 직접 연결되고, 증설 장비(한미반도체·주성·원익IPS 등)와 소재 주문에도 시차를 두고 이어져요. 낸드가 꺾이면 낸드 비중이 높은 장비·소재(식각·증착용 가스, 낸드 컨트롤러)부터 주문이 줄 수 있어요."),
]
out = {"source":"DRAMeXchange(트렌드포스) 월평균 고정거래가격, 언론 보도 인용","unit":"달러","updated":ROWS[-1][0],
       "rows":[{"m":m,"dram":d,"nand":n,"url":u,"imp":i} for m,d,n,u,i in ROWS],"read":READ,
       "note":"보도에서 숫자를 확인한 달만 넣었어요. 빈 달은 보도에서 확인하지 못한 달이에요. 표의 *는 '전월과 같다'는 표현으로 정한 값이에요. 2026년 9~10월 일부 값은 기사마다 조금씩 달라 가장 많이 인용된 값을 썼어요."}
p = os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","..","docs","semi","data","memory_prices.json")
json.dump(out, open(p,"w",encoding="utf-8"), ensure_ascii=False, indent=1)
print("ok", len(ROWS))
