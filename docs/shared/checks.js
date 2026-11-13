/* 투자지표 타일 · 시나리오 적정가 띠 · 버핏/린치/피셔 숫자 체크 — 7개 대시보드 공용.
   계산은 scripts/checks.py(rec.metrics·rec.checks)와 build_valuation.py·marks.py가 하고, 여기서는 보여 주기만 한다.
   내재가치 리포트 위쪽 타일에 이미 있는 시가총액·PER(TTM)·ROE·PBR·순현금은 다시 그리지 않는다.
   실적 랭킹 대시보드의 회사 페이지 형식을 참고했다(2026-11-13). */
(function(){
  const fmt=(v,d=0)=>v==null||isNaN(v)?'–':Number(v).toLocaleString('ko-KR',{maximumFractionDigits:d,minimumFractionDigits:d});
  const eok=v=>v==null?null:v/100;
  const jo=v=>v==null?'–':(Math.abs(v)>=1e6?fmt(v/1e6,1)+'조':fmt(v/100)+'억');
  const sg=v=>v==null?'–':(v>0?'+':'')+fmt(v,1)+'%';
  const kp=(l,val,sub)=>`<div class="kpi"><div class="l">${l}</div><div class="v">${val}</div><div class="s">${sub||''}</div></div>`;
  const qlab=q=>q?q.replace(/(\d{4})Q(\d)/,'$1년 $2분기'):'최근 분기';

  function tiles(v){
    const m=v.metrics; if(!m) return '';
    const x=[];
    x.push(kp('PER 분기 연환산',m.per_q!=null?fmt(m.per_q,1)+'배':'적자',`${qlab(m.q)} 순이익 ${jo(m.ni_q)} × 4`));
    x.push(kp('POR 최근 4분기',m.por_ttm!=null?fmt(m.por_ttm,1)+'배':'영업적자',`영업이익 ${jo(m.op_ttm)} 기준`));
    x.push(kp('POR 분기 연환산',m.por_q!=null?fmt(m.por_q,1)+'배':'영업적자',`${qlab(m.q)} 영업이익 ${jo(m.op_q)} × 4`));
    if(m.cns_per!=null) x.push(kp('컨센서스 PER',fmt(m.cns_per,1)+'배','증권사 예상 이익 기준(네이버 금융)'));
    x.push(kp('PEG',m.peg!=null?fmt(m.peg,2):'–',m.peg_g!=null?`PER ÷ 5년 순이익 성장률 ${fmt(m.peg_g,1)}%`:'성장률 계산 불가(적자 구간)'));
    x.push(kp('배당수익률',m.div_yield!=null?fmt(m.div_yield,2)+'%':'–',m.dps?`주당 ${fmt(m.dps)}원(최근 결산)`:'배당 정보 없음'));
    if(m.debt_eq!=null) x.push(kp('차입금 ÷ 자본',fmt(m.debt_eq)+'%','이자 붙는 빚만(부채비율과 달라요)'));
    if(m.ret_1y!=null) x.push(kp('1년 주가',`<span class="${m.ret_1y>=0?'up':'down'}">${sg(m.ret_1y)}</span>`,`${m.ret_1y_from} 월말 종가 대비`));
    return `<h4>투자지표</h4><p class="sub" style="margin:0 0 4px">PER은 지배주주 순이익, POR은 영업이익 기준이에요. '분기 연환산'은 ${qlab(m.q)} 한 분기 값 × 4라 호황·불황의 지금 속도를, '최근 4분기'는 1년 합계를 보여 줘요. 둘의 차이가 크면 이익이 빠르게 바뀌는 중이에요.</p><div class="vgrid">${x.join('')}</div>`;
  }

  function strip(v){
    const d=v.dcf; if(!d||!v.price) return '';
    const S=d.scenarios, mk=v.marks||{};
    const pts=[['약세',S.bear.per_share,'b'],['기준',S.base.per_share,'m'],['강세',S.bull.per_share,'u']];
    if(mk.buy_ps) pts.push(['안전마진 매수가',mk.buy_ps,'s']);
    if(mk.weighted_ps) pts.push(['확률 가중',mk.weighted_ps,'w']);
    const all=pts.map(p=>p[1]).concat([v.price]).filter(x=>x!=null&&x>0);
    if(all.length<2) return '';
    const lo=Math.min(...all)*0.9, hi=Math.max(...all)*1.05, X=p=>((p-lo)/(hi-lo)*100).toFixed(2);
    const col={b:'var(--down)',m:'var(--accent)',u:'var(--up)',s:'var(--ink-3)',w:'var(--ink-2)'};
    const top=pts.filter(p=>'bmu'.includes(p[2])), bot=pts.filter(p=>!'bmu'.includes(p[2]));
    const tx=p=>{const x=+X(p[1]);return x<10?'0':x>90?'-100%':'-50%'};
    const lab=(p,up)=>`<div style="position:absolute;left:${X(p[1])}%;transform:translateX(${tx(p)});${up?'bottom:calc(50% + 9px)':'top:calc(50% + 9px)'};font-size:11.5px;white-space:nowrap;text-align:${tx(p)==='0'?'left':tx(p)==='-50%'?'center':'right'};color:var(--ink-2)">${up?`${p[0]}<br><b style="color:var(--ink)">${fmt(p[1])}</b>`:`<b style="color:var(--ink)">${fmt(p[1])}</b><br>${p[0]}`}</div>`;
    const dot=p=>`<div style="position:absolute;left:${X(p[1])}%;top:50%;width:11px;height:11px;margin:-5.5px 0 0 -5.5px;border-radius:50%;background:${col[p[2]]};${'sw'.includes(p[2])?'opacity:.75':''}"></div>`;
    return `<h4>시나리오별 적정주가 한눈에</h4>
      <div style="position:relative;height:110px;margin:4px 14px 2px">
        <div style="position:absolute;left:0;right:0;top:50%;height:2px;background:var(--line)"></div>
        ${pts.map(dot).join('')}
        <div style="position:absolute;left:${X(v.price)}%;top:calc(50% - 14px);width:3px;height:28px;margin-left:-1.5px;background:var(--ink)"></div>
        ${top.map(p=>lab(p,true)).join('')}${bot.map(p=>lab(p,false)).join('')}
      </div>
      <p class="sub" style="text-align:right;margin:0 0 6px">검은 막대 = 현재가 <b>${fmt(v.price)}원</b>${mk.buy_ps?' · 안전마진 매수가·확률 가중은 하워드 막스식 점검 값이에요':''}</p>`;
  }

  function card(title,list,take,foot){
    if(!list||!list.length) return '';
    const ic=o=>o===true?'<span style="color:var(--up);font-weight:700">✓</span>':o===false?'<span style="color:var(--down);font-weight:700">✕</span>':'<span style="color:var(--ink-3)">·</span>';
    return `<div style="border:1px solid var(--line);border-radius:10px;padding:12px 14px;background:var(--panel);min-width:0">
      <div style="font-weight:600;margin-bottom:6px">${title}</div>
      ${list.map(c=>`<div style="display:grid;grid-template-columns:18px 1fr auto;gap:8px;padding:6px 0;border-bottom:1px solid var(--line);font-size:13px;align-items:start">${ic(c.ok)}<span>${c.name}${c.note?`<div style="font-size:11.5px;color:var(--ink-3);margin-top:1px">${c.note}</div>`:''}</span><span style="font-variant-numeric:tabular-nums;color:var(--ink-2);text-align:right">${c.val}</span></div>`).join('')}
      ${take?`<p style="font-size:12.5px;line-height:1.6;margin:8px 0 0">${take}</p>`:''}${foot?`<p class="sub" style="margin:6px 0 0">${foot}</p>`:''}</div>`;
  }

  function masters(v){
    const c=v.checks; if(!c) return '';
    return `<h4>투자 대가 체크리스트 (숫자로 보는 항목)</h4>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:10px;margin:6px 0 8px">
        ${card('워런 버핏',c.buffett,c.buffett_take)}
        ${card(`피터 린치 · ${c.lynch_cat||''}`,c.lynch,c.lynch_take,c.lynch_cat_note?`분류 기준: ${c.lynch_cat_note}`:'')}
        ${card('필립 피셔',c.fisher,'','15개 질문 전체 평가는 이 회사의 심층 분석에 있어요.')}
      </div>`;
  }

  window.extraBlock=function(v){
    if(!v||!v.dcf) return '';
    return tiles(v)+strip(v)+masters(v);
  };
})();
