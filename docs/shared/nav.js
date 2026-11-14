// 모든 대시보드 공용 메뉴. 새 업종을 추가할 때는 이 목록만 고치면 된다.
// 사용: <div id="dash-nav"></div><script src="../shared/nav.js"></script> (화장품 루트는 shared/nav.js)
(function(){
  const L=[['','화장품'],['semi/','반도체'],['chem/','화학·정유'],['battery/','2차전지'],['food/','음식료'],['apparel/','의류'],['logistics/','물류·운송'],['auto/','자동차'],['steel/','철강'],['backtest/','적정주가 백테스트']];
  const s=document.currentScript, src=s?s.getAttribute('src'):'';
  const root=src.replace(/shared\/nav\.js.*$/,'');
  const here=location.pathname.replace(/index\.html$/,'');
  const el=document.getElementById('dash-nav'); if(!el) return;
  el.innerHTML=L.map(([p,n])=>{const cur=here.endsWith('/'+p)&&(p||!/\/(semi|chem|battery|food|apparel|logistics|auto|steel|backtest)\/$/.test(here));
    return cur?`<b>${n}</b>`:`<a href="${root}${p}" style="color:var(--accent)">${n}</a>`}).join(' · ');
})();
