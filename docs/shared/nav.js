// 모든 대시보드 공용 메뉴. 새 업종을 추가할 때는 이 목록만 고치면 된다.
// 사용: <div id="dash-nav"></div><script src="../shared/nav.js"></script> (화장품 루트는 shared/nav.js)
(function(){
  const L=[['','화장품'],['semi/','반도체'],['chem/','화학·정유'],['battery/','2차전지'],['food/','음식료'],['apparel/','의류'],['logistics/','물류·운송'],['auto/','자동차'],['steel/','철강'],['bio/','바이오·제약'],['construction/','건설·건자재'],['ship/','조선'],['energy/','에너지·전력'],['backtest/','적정주가 백테스트']];
  const s=document.currentScript, src=s?s.getAttribute('src'):'';
  const root=src.replace(/shared\/nav\.js.*$/,'');
  const here=location.pathname.replace(/index\.html$/,'');
  const el=document.getElementById('dash-nav'); if(!el) return;
  el.innerHTML=L.map(([p,n])=>{const cur=here.endsWith('/'+p)&&(p||!/\/(semi|chem|battery|food|apparel|logistics|auto|steel|bio|construction|ship|energy|backtest)\/$/.test(here));
    return cur?`<b>${n}</b>`:`<a href="${root}${p}" data-p="${p}" style="color:var(--accent)">${n}</a>`}).join(' · ');
  // 아직 배포되지 않은 업종(다른 PR에서 추가 중)은 메뉴에서 숨김
  el.querySelectorAll('a[data-p]').forEach(a=>{const p=a.dataset.p; if(!p) return;
    fetch(root+p+'index.html',{method:'HEAD'}).then(r=>{if(!r.ok) hide(a)}).catch(()=>{})});
  function hide(a){const prev=a.previousSibling; if(prev&&prev.nodeType===3) prev.remove(); else if(a.nextSibling&&a.nextSibling.nodeType===3) a.nextSibling.remove(); a.remove();}
})();
