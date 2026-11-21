/* 하워드 막스 관점 점검 블록 — 7개 대시보드 공용.
   계산은 scripts/marks.py(build_valuation.py가 호출)가 하고, 여기서는 valuation.json의 rec.marks를 보여 준다.
   페이지 스크립트와 독립적으로 동작한다. */
(function(){
  const POSTXT={'호황 정점권':'이익이 사이클 꼭대기 근처예요. 좋은 숫자가 계속될 거라는 믿음이 가장 강할 때라 가장 조심할 자리예요.',
    '상승기':'이익이 평균보다 높고 늘고 있어요. 낙관이 쌓이는 구간이라 비관 쪽 확률을 조금 높였어요.',
    '중립':'이익이 평균 근처예요. 확률을 고르게 뒀어요.',
    '하강기':'이익이 줄고 있어요. 아직 바닥이 확인되지 않아 비관 쪽을 약간 더 뒀어요.',
    '바닥권':'이익이 평균보다 낮고 아직 나빠요. 나쁜 소식이 이미 가격에 들어 있을 가능성이 커서 낙관 쪽 확률을 높였어요.',
    '회복기':'이익이 평균보다 낮지만 다시 늘기 시작했어요. 낙관 쪽 확률을 조금 높였어요.'};
  const IND={cosmetics:'화장품',semi:'반도체',chem:'화학',battery:'2차전지',apparel:'의류',food:'음식료',logistics:'물류',auto:'자동차',steel:'철강'};
  const P=x=>Math.round(x*100)+'%';
  // 페이지 스크립트의 함수에 기대지 않도록 자체 포맷 함수를 둔다
  const fmt=(v,d=0)=>v==null||isNaN(v)?'–':Number(v).toLocaleString('ko-KR',{maximumFractionDigits:d,minimumFractionDigits:d});
  const pct=v=>v==null||!isFinite(v)?'–':(v>0?'+':'')+v.toFixed(1)+'%';
  function bar(m,v){
    const S=v.dcf.scenarios, vals=[m.down_ps,m.buy_ps,m.weighted_ps,S.bull.per_share,v.price].filter(x=>x!=null&&isFinite(x));
    const lo=Math.min(...vals)*0.9, hi=Math.max(...vals)*1.05||1, X=x=>Math.max(0,Math.min(100,(x-lo)/(hi-lo||1)*100)).toFixed(1);
    const W_=(a,b)=>Math.max(0,X(b)-X(a)).toFixed(1);
    const mk=(l,x,cls,top)=>`<div style="position:absolute;left:${X(x)}%;top:${top}px;transform:translateX(-50%);text-align:center;white-space:nowrap;font-size:11px;line-height:1.25" class="${cls}"><div style="width:2px;height:12px;margin:0 auto;background:currentColor"></div>${l}<br>${fmt(x)}</div>`;
    return `<div style="position:relative;height:84px;margin:8px 6px 4px" aria-label="현재가와 하방·매수가·가중 가치·낙관 가치 위치">
      <div style="position:absolute;left:${X(m.down_ps)}%;width:${W_(m.down_ps,m.buy_ps)}%;top:12px;height:6px;border-radius:3px;background:color-mix(in srgb,var(--up) 35%,transparent)"></div>
      <div style="position:absolute;left:${X(m.buy_ps)}%;width:${W_(m.buy_ps,S.bull.per_share)}%;top:12px;height:6px;border-radius:3px;background:var(--line)"></div>
      ${mk('하방',m.down_ps,'',20)}${mk('매수가',m.buy_ps,'',50)}${mk('가중',m.weighted_ps,'',20)}${mk('낙관',S.bull.per_share,'',50)}
      <div style="position:absolute;left:${X(v.price)}%;top:0;transform:translateX(-50%);font-size:11px;font-weight:700;color:var(--accent);white-space:nowrap">▼ 현재가</div>
    </div>`;
  }
  window.marksBlock=function(v,V){
    const m=v&&v.marks; if(!m||!v.dcf) return '';
    const M=(V||{}).marks_meta||{}, T=M.temperature, S=v.dcf.scenarios, w=m.weights, rk=m.risk;
    const parts=Object.entries(rk.parts).map(([k,x])=>`${k} ${x}`).join(' · ');
    const mkt=(M.market||[]).map(t=>`${IND[t.industry]||t.industry} ${t.label}(중앙 괴리율 ${pct(t.median_upside)}, 적정가보다 비싼 회사 ${t.share_above}%)`).join(', ');
    return `<h4>하워드 막스 관점 점검</h4>
   <h3 style="font-size:15px"><span class="tone ${m.tone}">${m.verdict}</span>안전마진 매수가 ${fmt(m.buy_ps)}원(현재가 대비 ${pct(m.buy_gap)}) · 확률 가중 가치 ${fmt(m.weighted_ps)}원</h3>
   ${bar(m,v)}
   <div style="border-top:1px solid var(--line);margin:6px 0 8px">
   <div style="border-bottom:1px solid var(--line);padding:7px 2px"><div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;font-size:13px"><span style="color:var(--ink-2)">사이클 위치</span><b style="text-align:right">${m.pos}</b></div><div style="font-size:12.5px;line-height:1.55;color:var(--ink-2);margin-top:2px">${m.pos_src}${m.pos_raw&&m.pos_raw!==m.pos?` ('${m.pos_raw}')`:''}. ${POSTXT[m.pos]||''}</div></div>
   <div style="border-bottom:1px solid var(--line);padding:7px 2px"><div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;font-size:13px"><span style="color:var(--ink-2)">시나리오 확률</span><b style="text-align:right">비관 ${P(w.bear)} · 기준 ${P(w.base)} · 낙관 ${P(w.bull)}</b></div><div style="font-size:12.5px;line-height:1.55;color:var(--ink-2);margin-top:2px">위 세 시나리오를 똑같이 믿지 않고 사이클 위치와 업종 분위기로 무게를 달리했어요${T?`. 업종 분위기: ${T.label}`:''}.</div></div>
   <div style="border-bottom:1px solid var(--line);padding:7px 2px"><div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;font-size:13px"><span style="color:var(--ink-2)">하방 가치</span><b style="text-align:right">${fmt(m.down_ps)}원 (${m.max_loss>0?'-'+m.max_loss.toFixed(1)+'%':'현재가보다 높음'})${m.down_ps===0?'<br><span style="font-size:11px">불황이 길면 주주 몫이 남지 않을 수 있음</span>':''}</b></div><div style="font-size:12.5px;line-height:1.55;color:var(--ink-2);margin-top:2px">${m.stress.how}. 비관 시나리오와 이 값 중 낮은 쪽이에요.</div></div>
   <div style="border-bottom:1px solid var(--line);padding:7px 2px"><div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;font-size:13px"><span style="color:var(--ink-2)">영구 손실 위험</span><b style="text-align:right">${rk.grade} (${rk.score}점/100)</b></div><div style="font-size:12.5px;line-height:1.55;color:var(--ink-2);margin-top:2px">${parts}. 주가가 출렁이는 정도가 아니라 돈을 되찾지 못할 가능성을 봐요.</div></div>
   <div style="border-bottom:1px solid var(--line);padding:7px 2px"><div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;font-size:13px"><span style="color:var(--ink-2)">필요한 안전마진</span><b style="text-align:right">${m.mos}%</b></div><div style="font-size:12.5px;line-height:1.55;color:var(--ink-2);margin-top:2px">위험 ${rk.grade} 기본값에 사이클 위치·업종 분위기를 더하고 뺐어요. 확률 가중 가치 × (1 − ${m.mos}%) = 매수가.</div></div>
   <div style="border-bottom:1px solid var(--line);padding:7px 2px"><div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;font-size:13px"><span style="color:var(--ink-2)">손익 비대칭</span><b style="text-align:right">${m.asym}${m.asym_ratio!=null?` (${m.asym_ratio}배)`:''}</b></div><div style="font-size:12.5px;line-height:1.55;color:var(--ink-2);margin-top:2px">낙관 시나리오까지 ${pct(m.up_bull)} vs 하방까지 ${m.max_loss>0?'-'+m.max_loss.toFixed(1)+'%':'0%'}. 오를 폭이 잃을 폭의 2배 이상이면 '유리'예요.</div></div>
   ${m.implied_margin!=null?`<div style="border-bottom:1px solid var(--line);padding:7px 2px"><div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;font-size:13px"><span style="color:var(--ink-2)">가격이 가정하는 순이익률</span><b style="text-align:right">${m.implied_margin}%</b></div><div style="font-size:12.5px;line-height:1.55;color:var(--ink-2);margin-top:2px">${m.hist_margin?`과거 범위 ${m.hist_margin[0]}%~${m.hist_margin[2]}%, 평균 ${m.hist_margin[1]}%. `:''}${m.base_margin!=null?`이 리포트의 정상 이익 가정은 ${m.base_margin}%. `:''}지금 시가총액을 기준 성장률로 정당화하려면 필요한 수익성이에요.</div></div>`:''}
   </div>
   <p><b>가격이 이미 믿고 있는 것:</b> ${m.note}</p>
   <details style="margin:6px 0 10px"><summary style="cursor:pointer;font-size:13px;color:var(--ink-2)">하워드 막스의 생각을 이 계산에 어떻게 넣었나</summary>
   <ul style="font-size:13px;line-height:1.6;margin:6px 0 0;padding-left:18px">
    <li><b>위험은 주가 변동이 아니라 영구적으로 돈을 잃을 가능성이에요.</b> 그래서 불황 이익이 3년 이어지는 하방 가치와, 적자 이력·이익 변동폭·차입 부담으로 위험 점수를 매겼어요. 일시적인 하락과 되돌릴 수 없는 손실을 구분하려고 불황을 영원히 가정하지는 않았어요.</li>
    <li><b>좋은 회사도 비싸게 사면 나쁜 투자예요.</b> 무엇을 사느냐보다 얼마에 사느냐가 수익을 정해요. 적정가 자체가 아니라 그보다 충분히 낮은 '안전마진 매수가'를 따로 냈어요.</li>
    <li><b>사이클은 반복되고, 사람들의 심리는 진자처럼 극단을 오가요.</b> 이익은 이미 사이클 평균(정상 이익)으로 맞췄고, 여기서는 회사의 사이클 위치와 업종 전체가 얼마나 낙관적인지(적정가보다 비싼 회사 비율)로 시나리오 확률과 필요한 안전마진을 조정했어요.</li>
    <li><b>2단계 사고: '좋은 회사인가'가 아니라 '시장이 생각하는 것보다 좋은가'를 물어요.</b> 지금 주가가 맞으려면 어떤 순이익률이 유지돼야 하는지 역산해 과거 범위와 비교했어요. 모두가 아는 좋은 소식은 이미 가격에 있어요.</li>
    <li><b>잘 맞히는 것보다 틀렸을 때 덜 잃는 게 중요해요.</b> 오를 폭과 잃을 폭을 나란히 놓아, 손익이 한쪽으로 기운 기회인지 봐요.</li>
    <li>미래는 하나의 숫자가 아니라 여러 가능성의 분포예요. 그래서 한 개의 적정가 대신 하방·가중 가치·낙관을 범위로 보여 줘요.</li>
   </ul>
   <p class="src">원칙은 『투자에 대한 생각(The Most Important Thing)』, 『투자와 마켓 사이클의 법칙(Mastering the Market Cycle)』, 오크트리 메모의 핵심 생각을 요약한 것이고, 숫자 규칙(확률·안전마진 폭·위험 점수 배점)은 이 대시보드가 정한 것이에요. 기존 기준 적정가는 바꾸지 않았어요.${mkt?` 지금 업종별 분위기: ${mkt}.`:''}</p>
   </details>`;
  };
})();
