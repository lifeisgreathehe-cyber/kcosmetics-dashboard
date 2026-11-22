// 산업 데이터 ↔ 주가 선행·동행성 (모든 업종 공용). 데이터: docs/<업종>/data/leadlag.json (scripts/leadlag.py)
// 사용: <div class="card full" id="leadlag"></div> … LeadLag.render(document.getElementById('leadlag'), data)
(function(){
  const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const css=`.ll-t{width:100%;border-collapse:collapse;font-size:13px}.ll-t th,.ll-t td{padding:7px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
  .ll-t th{font-weight:500;color:var(--ink-2);font-size:12px;white-space:nowrap}.ll-t tr.ll-r{cursor:pointer}.ll-t tr.ll-r:hover{background:var(--accent-soft)}
  .ll-t tr.on{background:var(--accent-soft)}.ll-k{font-weight:600;white-space:nowrap}.ll-k.lead{color:var(--accent)}.ll-k.weak{color:var(--ink-3);font-weight:400}
  .ll-g{font-size:11.5px;padding:1px 6px;border-radius:9px;border:1px solid var(--line);white-space:nowrap}.ll-g.h{border-color:var(--accent);color:var(--accent)}
  .ll-s.pos{color:var(--up)}.ll-s.neg{color:var(--down)}.ll-why{font-size:12px;color:var(--ink-3);margin-top:2px}.ll-num{font-family:var(--font-mono);font-variant-numeric:tabular-nums;white-space:nowrap}
  .ll-box{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:14px}@media(max-width:760px){.ll-box{grid-template-columns:1fr}}
  .ll-sum{display:flex;gap:10px;flex-wrap:wrap;margin:6px 0 12px}.ll-sum div{background:var(--accent-soft);border-radius:8px;padding:8px 12px;font-size:13px}
  .ll-wrap{overflow-x:auto}`;
  function addCss(){if(document.getElementById('ll-css'))return;const s=document.createElement('style');s.id='ll-css';s.textContent=css;document.head.appendChild(s)}
  const kindCls=k=>k&&k.endsWith('선행')?'lead':k==='관계 약함'?'weak':'';
  const fmtv=(v,t)=>v==null?'–':(t==='level'?v.toFixed(1):(v>0?'+':'')+v.toFixed(1)+(t==='diff12'?'p':'%'));
  let ch1,ch2;
  function render(el,D){
    if(!el)return; addCss();
    if(!D||!D.series){el.innerHTML='<h2>산업 데이터의 주가 선행·동행성</h2><p class="sub">주가 월봉과 산업 데이터가 쌓이면 자동으로 계산돼요.</p>';return}
    const tnames=Object.keys(D.price||{});
    let tgt='업종 지수', sel=null;
    const S=D.series;
    el.innerHTML=`<h2>산업 데이터의 주가 선행·동행성</h2>
     <p class="sub">갱신 ${esc(D.updated)} · 지표를 0~${D.max_lag}개월 앞당기거나 늦춰 가며 주가 1년 수익률과의 상관을 잰 결과예요. 행을 누르면 아래에 두 선을 겹쳐 보여줘요.</p>
     <div class="ll-sum" id="ll-sum"></div>
     <div class="row"><div></div><label style="font-size:13px">비교할 주가 <select id="ll-tgt">${tnames.map(n=>`<option${n===tgt?' selected':''}>${esc(n)}</option>`).join('')}</select></label></div>
     <div class="ll-wrap"><table class="ll-t" id="ll-t"></table></div>
     <div class="ll-box"><div><h3 style="margin:0 0 4px;font-size:14px" id="ll-h"></h3><p class="sub" id="ll-hs"></p><div class="chart" style="height:260px"><canvas id="ll-c1"></canvas></div></div>
      <div><h3 style="margin:0 0 4px;font-size:14px">시차별 상관계수</h3><p class="sub">막대가 오른쪽(+)에서 크면 지표가 먼저, 왼쪽(−)에서 크면 주가가 먼저 움직였다는 뜻이에요. 점선은 우연으로 보기 어려운 기준선이에요.</p><div class="chart" style="height:260px"><canvas id="ll-c2"></canvas></div></div></div>
     <details style="margin-top:10px"><summary style="cursor:pointer;font-size:13px;color:var(--ink-2)">계산 방법과 읽는 법</summary><p style="font-size:13px;color:var(--ink-2)">${esc(D.method)}</p></details>`;
    const sm=D.summary||{};
    el.querySelector('#ll-sum').innerHTML=`<div>업종 지수를 앞서는 믿을 만한 지표 <b>${sm.leading||0}개</b></div><div>그중 지금 주가에 <b class="ll-s pos">긍정 ${sm.pos||0}</b> · <b class="ll-s neg">부정 ${sm.neg||0}</b></div>`;
    el.querySelector('#ll-tgt').onchange=e=>{tgt=e.target.value;table();if(sel)draw(sel)};
    function table(){
      const rows=S.map((s,i)=>{const a=(s.targets||{})[tgt]; const g=s.signal;
        if(!a)return `<tr><td>${esc(s.name)}<div class="ll-why">${esc(s.why||'')}</div></td><td colspan="4" class="ll-k weak">${esc(s.status||'계산 불가')}</td></tr>`;
        const sig=tgt==='업종 지수'&&g?`<span class="ll-s ${g.tone}">${g.month} ${fmtv(g.value,s.transform)} (3개월 전 ${fmtv(g.prev3,s.transform)}, ${g.trend||''})</span>${g.until?`<div class="ll-why">시차대로면 ${g.until}까지 주가에 ${g.tone==='pos'?'긍정':g.tone==='neg'?'부정':'중립'}</div>`:''}${g.mismatch?'<div class="ll-why">※ 예상과 반대 부호 — 다른 요인이 섞였을 수 있어요</div>':''}`:'–';
        return `<tr class="ll-r" data-i="${i}" tabindex="0"><td>${esc(s.name)}<div class="ll-why">${esc(s.why||'')}</div></td>
          <td class="ll-k ${kindCls(a.kind)}">${esc(a.kind)}</td><td class="ll-num">${a.r>0?'+':''}${a.r.toFixed(2)}<div class="ll-why">같은 달 ${a.r0==null?'–':a.r0.toFixed(2)}</div></td>
          <td><span class="ll-g ${a.grade==='높음'?'h':''}">${a.grade}</span><div class="ll-why">${a.stable?'앞·뒤 기간 같은 방향':'기간별 흔들림'}</div></td><td>${sig}</td></tr>`}).join('');
      const t=el.querySelector('#ll-t');
      t.innerHTML=`<thead><tr><th>지표 (변화율)</th><th>관계</th><th>상관 r</th><th>신뢰</th><th>지금 신호</th></tr></thead><tbody>${rows}</tbody>`;
      t.querySelectorAll('tr.ll-r').forEach(tr=>{const go=()=>{sel=+tr.dataset.i;t.querySelectorAll('tr').forEach(x=>x.classList.remove('on'));tr.classList.add('on');draw(sel)};tr.onclick=go;tr.onkeydown=e=>{if(e.key==='Enter')go()}});
      if(sel==null){const first=S.findIndex(s=>(s.targets||{})[tgt]&&(s.targets[tgt].kind||'').endsWith('선행'));const f=first>=0?first:S.findIndex(s=>(s.targets||{})[tgt]);if(f>=0){sel=f;const tr=t.querySelector(`tr[data-i="${f}"]`);tr&&tr.classList.add('on');draw(f)}}
      else {const tr=t.querySelector(`tr[data-i="${sel}"]`);tr&&tr.classList.add('on')}
    }
    function shift(m,k){let y=+m.slice(0,4),mo=+m.slice(5,7)-1+k;y+=Math.floor(mo/12);mo=((mo%12)+12)%12;return `${y}-${String(mo+1).padStart(2,'0')}`}
    function draw(i){
      const s=S[i],a=(s.targets||{})[tgt];if(!a||!window.Chart)return;
      const cs=getComputedStyle(document.documentElement),c1=cs.getPropertyValue('--s1').trim(),c2=cs.getPropertyValue('--s2').trim(),ink=cs.getPropertyValue('--ink-3').trim(),ln=cs.getPropertyValue('--line').trim();
      const P=Object.fromEntries(D.price[tgt]||[]);const X=s.x||[];
      const ms=X.map(([m])=>shift(m,a.lag));
      const months=[...new Set([...ms,...Object.keys(P)])].filter(m=>m>=(ms[0]||'')).sort();
      const xm=Object.fromEntries(X.map(([m,v])=>[shift(m,a.lag),v]));
      el.querySelector('#ll-h').textContent=`${s.name} vs ${tgt} 1년 수익률`;
      el.querySelector('#ll-hs').textContent=a.lag>0?`지표를 ${a.lag}개월 뒤로 밀어 그렸어요. 두 선이 겹치면 지표가 ${a.lag}개월 먼저 움직였다는 뜻이에요. ${s.read||''}`:a.lag<0?`지표를 ${-a.lag}개월 앞으로 당겨 그렸어요(주가가 먼저). ${s.read||''}`:`같은 달끼리 그렸어요. ${s.read||''}`;
      ch1&&ch1.destroy();ch2&&ch2.destroy();
      ch1=new Chart(el.querySelector('#ll-c1'),{type:'line',data:{labels:months,datasets:[
        {label:s.name+(s.transform==='level'?'':' (변화율)'),data:months.map(m=>xm[m]??null),borderColor:c1,backgroundColor:c1,yAxisID:'y',pointRadius:0,borderWidth:2,spanGaps:true},
        {label:tgt+' 1년 수익률(%)',data:months.map(m=>P[m]??null),borderColor:c2,backgroundColor:c2,yAxisID:'y2',pointRadius:0,borderWidth:2,spanGaps:true}]},
        options:{maintainAspectRatio:false,animation:false,interaction:{mode:'index',intersect:false},plugins:{legend:{labels:{color:ink,boxWidth:10}}},
          scales:{x:{ticks:{color:ink,maxTicksLimit:8},grid:{color:ln}},y:{ticks:{color:c1},grid:{color:ln}},y2:{position:'right',ticks:{color:c2},grid:{display:false}}}}});
      const cv=a.curve||[];
      ch2=new Chart(el.querySelector('#ll-c2'),{type:'bar',data:{labels:cv.map(([k])=>k),datasets:[
        {label:'상관계수',data:cv.map(([,r])=>r),backgroundColor:cv.map(([k])=>k===a.lag?c2:c1)},
        {type:'line',label:'기준선',data:cv.map(()=>a.thr),borderColor:ink,borderDash:[4,4],pointRadius:0,borderWidth:1},
        {type:'line',label:'',data:cv.map(()=>-a.thr),borderColor:ink,borderDash:[4,4],pointRadius:0,borderWidth:1}]},
        options:{maintainAspectRatio:false,animation:false,plugins:{legend:{display:false}},scales:{x:{title:{display:true,text:'시차(개월, +는 지표가 먼저)',color:ink},ticks:{color:ink},grid:{display:false}},y:{min:-1,max:1,ticks:{color:ink},grid:{color:ln}}}}});
    }
    table();
  }
  window.LeadLag={render};
})();
