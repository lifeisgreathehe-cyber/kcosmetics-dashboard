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
