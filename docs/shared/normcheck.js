/* 정상 이익·현금 전환율·PBR 점검 블록 — 7개 대시보드 공용.
   계산은 scripts/build_valuation.py가 하고(hist.margins·hist.oneoff·dcf.c_T·dcf.roe_norm), 여기서는 보여 주기만 한다.
   페이지 스크립트와 독립적으로 동작한다(자체 포맷 함수). */
(function(){
  const fmt=(v,d=0)=>v==null||isNaN(v)?'–':Number(v).toLocaleString('ko-KR',{maximumFractionDigits:d,minimumFractionDigits:d});
  const eok=v=>v==null?null:v/100;
  const row=(l,val,txt)=>`<div style="border-bottom:1px solid var(--line);padding:7px 2px"><div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;font-size:13px"><span style="color:var(--ink-2)">${l}</span><b style="text-align:right">${val}</b></div><div style="font-size:12.5px;line-height:1.55;color:var(--ink-2);margin-top:2px">${txt}</div></div>`;
  window.normBlock=function(v,V){
    const d=v&&v.dcf, h=v&&v.hist; if(!d) return '';
    const gT=(V||{}).terminal_growth??2, out=[];
    if(h&&h.margins){
      const adj={}; (h.oneoff||[]).forEach(a=>adj[a.year]=a);
      const chips=Object.entries(h.margins).map(([y,m])=>adj[y]
        ?`<span class="chip" title="일회성으로 보고 바꾼 해">${y} <s>${adj[y].ni_margin.toFixed(1)}%</s> → ${m.toFixed(1)}%</span>`
        :`<span class="chip">${y} ${m.toFixed(1)}%</span>`).join('');
      const one=(h.oneoff||[]).length
        ?` ${h.oneoff.map(a=>a.year).join('·')}년은 영업은 흑자인데 순이익만 평소와 크게 어긋나(손상차손·대손 같은 일회성) 그해 영업이익에 이 회사의 평소 비율을 곱한 값으로 바꿨어요. 10년에 1~2번 있는 회계 손실을 '불황 때 이익'으로 보면 정상 이익과 하방 가치를 모두 지나치게 낮게 잡게 돼요.`
        :'';
      out.push(row('사이클 평균 순이익률',`${h.margin.toFixed(1)}% × 추세 매출 ${fmt(eok(h.trend_rev))}억`,
        `${h.years}년 연간 순이익률${h.n>=6?'(가장 좋은 해와 나쁜 해 제외)':''} 평균이에요.${one}<div class="moat" style="margin:6px 0 0">${chips}</div>`));
    }
    const mo=((v.cycle||{}).midcycle||{}).oneoff||[];
    if(mo.length) out.push(row('평균 기간의 일회성 보정',mo.map(a=>`${a.year}년 ${a.ni_margin.toFixed(1)}% → ${a.adj_margin.toFixed(1)}%`).join(', '),
      '사이클 평균 이익을 낼 때 쓴 기간 안에서도, 영업은 흑자인데 순이익만 평소와 크게 어긋난 해는 그해 영업이익에 이 회사의 평소 비율을 곱한 이익률로 바꿔 평균했어요.'));
    const tc=v.ttm_core;
    if(tc) out.push(row('최근 4개 분기 일회성 보정',`${fmt(eok(tc.raw))}억 → ${fmt(eok(tc.ni))}억`,
      `최근 4개 분기 순이익이 영업이익과 평소 관계(순이익 ≈ 세후 영업이익 × ${tc.k})에서 크게 벗어나 일회성 손익이 섞였다고 보고, 영업이익 기준 이익을 정상 이익으로 썼어요.`));
    const tn=v.ttm_news;
    if(tn&&/일회성 손익 제외/.test(tn.period||'')&&v.ttm) out.push(row('최근 이익의 일회성 보정',`${fmt(eok(v.ttm.ni))}억 → ${fmt(eok(tn.ni))}억`,
      '지금 이익이 정상 이익보다 높거나 낮은 부분은 사이클 위치에 따라 1~3년만 이어진다고 보고 더하거나 빼요. 그 계산에 쓰는 최근 4개 분기 이익에서 일회성 손익을 빼고 영업이익 기준으로 바꿨어요.'));
    const cy=d.cycle;
    if(cy&&cy.ni_paths){
      const nm={bear:'약세',base:'기준',bull:'강세'}, jo=x=>fmt(eok(x)/10000,1)+'조';
      const big=Math.abs(d.E1)>=1e6, u=x=>big?jo(x):fmt(eok(x))+'억';
      const lines=['bear','base','bull'].filter(k=>cy.ni_paths[k]).map(k=>{
        const p=cy.ni_paths[k], xb=(cy.excess_by||{})[k];
        return `<div style="margin-top:3px"><b>${nm[k]}</b> ${p.length?p.map((x,i)=>`${i+1}년차 ${u(x)}`).join(' → ')+' → ':''}정상 ${u(d.E1)}${xb!=null?` <span style="color:var(--ink-2)">(정상 이익 대비 더한 가치 ${xb>=0?'+':''}${u(xb)})</span>`:''}</div>`;}).join('');
      out.push(row('시나리오별 이익 경로',`호황·불황이 몇 해 이어지나`,
        `경기순환주는 '지금 이익이 계속된다'고 보지 않고, 지금 이익이 몇 해 이어진 뒤 정상 이익으로 돌아온다고 봐요. 시나리오마다 그 기간을 다르게 둬요${cy.bear_trough&&!cy.path_note?` — 약세는 호황이 1년 만에 끝나고 불황 이익(${u(cy.trough_ni??0)}, 과거 두 번째로 나쁜 해의 이익률 기준)을 2년 거쳐요`:''}. 정상 이익을 넘는 부분은 현금 전환율 ${Math.round(d.c*100)}%만큼 현재가치로 더했어요.${cy.path_note?' '+cy.path_note:''}${lines}`));
    }
    if(d.implied_E1!=null&&d.E1>0){
      const r_=d.implied_E1/d.E1;
      out.push(row('주가에 반영된 정상 이익',`${fmt(eok(d.implied_E1))}억 (가정의 ${(r_*100).toFixed(0)}%)`,
        `기준 시나리오의 성장률·할인율을 그대로 둘 때, 지금 주가가 맞으려면 ${cy?'호황(불황)이 끝난 뒤 ':''}매년 이만큼 벌어야 해요. 이 리포트의 정상 이익은 ${fmt(eok(d.E1))}억이에요. `+
        (r_>1.25?'시장은 이 리포트보다 훨씬 높은 정상 이익을 기대하고 있어요. 그 근거(구조적 성장·점유율 상승)가 있는지가 관건이에요.':r_<0.8?'시장은 이 리포트보다 낮은 정상 이익만 가격에 넣고 있어요. 정상 이익 가정이 맞다면 싸게 거래되는 쪽이에요.':'시장 기대와 이 리포트의 정상 이익이 비슷해요.')));
    }
    if(v.net_cash_note) out.push(row('최신 순현금',`${fmt(eok(v.net_cash))}억`,v.net_cash_note));
    if(d.c_T!=null){
      const inc=d.c<1?gT/(1-d.c):null;
      const same=Math.abs(d.c_T-d.c)<0.005;
      out.push(row('현금 전환율',`1~5년 ${Math.round(d.c*100)}% → 영구 ${Math.round(d.c_T*100)}%`,
        same
          ?`이익의 ${Math.round(d.c*100)}%만 주주 몫으로 보고 끝까지 유지했어요.${d.roe_norm!=null&&d.roe_norm<d.r?` 정상 ROE(${d.roe_norm.toFixed(1)}%)가 자기자본비용(${d.r}%)보다 낮아, 재투자해도 큰 가치를 만들기 어렵다고 봤기 때문이에요.`:' 지주회사 할인이나 선박·항공기 교체 투자처럼 성장과 무관한 이유로 낮춘 값이라 그대로 뒀어요.'}`
          :`처음 5년은 투자 계획을 반영해 ${Math.round(d.c*100)}%만 주주 몫으로 보고, 성장률이 ${gT}%로 낮아지는 6~10년차에 ${Math.round(d.c_T*100)}%로 옮겨가요. ${Math.round(d.c*100)}%를 영원히 유지하면 '새 투자가 연 ${inc!=null?inc.toFixed(1):'–'}%만 번다'는 가정이 돼서, 새 투자 수익률을 자기자본비용 ${d.r}%와 정상 ROE ${d.roe_norm!=null?d.roe_norm.toFixed(1)+'%':'–'} 중 낮은 쪽으로 맞췄어요.`));
    }
    if(v.pbr!=null&&d.roe_norm!=null&&d.r>gT){
      const fair=Math.max(0,(d.roe_norm-gT)/(d.r-gT));
      out.push(row('PBR로 본 점검',`실제 ${v.pbr.toFixed(2)}배 · ROE로 본 적정 ${fair.toFixed(2)}배`,
        `정상 이익 기준 ROE ${d.roe_norm.toFixed(1)}%, 자기자본비용 ${d.r}%, 영구성장 ${gT}%면 적정 PBR ≈ (ROE − 성장) ÷ (자기자본비용 − 성장) = ${fair.toFixed(2)}배예요. `+
        (fair<1?'자산이 많아도 그 자산이 자본비용보다 적게 벌면 장부가치보다 싸게 거래되는 게 정상이에요. 그래서 낮은 PBR만으로 저평가라고 보지 않고, 자산 가치는 적정가에 따로 더하지 않았어요(팔 계획이 없는 사업용 자산이라서요). 다만 하방을 받쳐 주는 역할은 해요.'
                :'자산보다 이익을 잘 내는 회사라 PBR이 1배를 넘는 게 자연스러워요.')+
        (v.pbr<fair*0.8?' 실제 PBR이 이 값보다 낮아, ROE가 유지된다면 싸게 거래되는 쪽이에요.':v.pbr>fair*1.25?' 실제 PBR이 이 값보다 높아, 시장은 ROE가 더 오른다고 보고 있어요.':' 실제 PBR이 이 값과 비슷해요.')));
    }
    if(!out.length) return '';
    return `<h4>정상 이익과 가정 점검</h4><div style="border-top:1px solid var(--line);margin:6px 0 8px">${out.join('')}</div>`;
  };
})();
