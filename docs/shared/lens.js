/* 리포트식 점검 — 모든 업종 대시보드 공용 (2026-11-27).
   이엔에프테크놀로지 AI 기업분석 리포트(작성자 Zurini)를 역엔지니어링해, 우리 대시보드에 없던 도구만 가져왔다:
   5년 기대수익률(비관·기본·낙관) · 투자 방법(나눠 사기·비중 확대·축소 가격) · 영업이익 변화 분해(물량 vs 이익률)
   · 과거 이익률 충격과 회복 기간 · 다음 해 영업이익 민감도 · 동종 비교.
   계산은 scripts/lens.py(rec.lens)가 하고 여기서는 보여 주기만 한다. 5년 뒤 이익은 리포트처럼 회사 추정이 아니라
   우리 정상 이익(사이클·일회성 보정)에서 출발한다. 같은 회사의 전체 리포트 형식은 docs/report 대시보드에 있다. */
(function(){
  const SRC=(document.currentScript&&document.currentScript.src)||'';
  const REPORT=SRC?SRC.replace(/shared\/lens\.js.*$/,'report/'):'../report/';
  const fmt=(v,d=0)=>v==null||isNaN(v)?'–':Number(v).toLocaleString('ko-KR',{maximumFractionDigits:d,minimumFractionDigits:d});
  const jo=v=>v==null?'–':(Math.abs(v)>=1e6?fmt(v/1e6,1)+'조':fmt(v/100)+'억');      // 백만원 → 억·조
  const sg=(v,d=1)=>v==null?'–':(v>0?'+':v<0?'−':'')+fmt(Math.abs(v),d)+'%';
  const sgj=v=>v==null?'–':(v>0?'+':v<0?'−':'')+jo(Math.abs(v));
  const col=v=>v==null?'':v>0?'up':v<0?'down':'';
  const box=(h)=>`<div style="border:1px solid var(--line);border-radius:10px;padding:12px 14px;background:var(--panel);min-width:0;margin:6px 0 10px">${h}</div>`;
  const tbl=(head,rows,al)=>`<div class="tbl" style="overflow-x:auto"><table><thead><tr>${head.map((h,i)=>`<th style="text-align:${i?'right':'left'};white-space:nowrap">${h}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr${r._self?' style="background:var(--accent-soft,rgba(80,120,255,.08));font-weight:600"':''}>${r.cells.map((c,i)=>`<td style="text-align:${i?'right':'left'};white-space:nowrap">${c}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  const qlab=q=>q?q.replace(/^(\d{2})(\d{2})Q(\d)$/,'$3Q$2'):'';

  function er5(L,v){
    const e=L.er5; if(!e) return '';
    const nm={bear:'비관',base:'기본',bull:'낙관'};
    const rows=['bear','base','bull'].map(k=>{const s=e.sc[k];return{cells:[
      `<b>${nm[k]}</b>`,
      jo(s.E_T)+(s.stress?' <span class="sub">(불황)</span>':` <span class="sub">(${sg(s.g,0)}/년)</span>`),
      fmt(s.per,1)+'배',
      s.excess?sgj(s.excess):'–',
      fmt(s.value_ps)+'원',
      fmt(s.div_ps)+'원',
      `<b class="${col(s.ret)}">${sg(s.ret)}</b>`]}});
    const b=e.sc.base, r=e.r;
    const verdict=b.ret>=r?`기본 시나리오의 연 ${fmt(b.ret,1)}%가 요구수익률(할인율) ${fmt(r,1)}%보다 높아 <b>장기 투자를 시작할 만한 가격</b>이에요.`
      :b.ret>=r-4?`기본 시나리오의 연 ${fmt(b.ret,1)}%가 요구수익률 ${fmt(r,1)}%에 조금 못 미쳐요. 가격이 내려오거나 정상 이익이 오른다는 증거가 나올 때까지 나눠 사는 정도가 맞아요.`
      :`기본 시나리오도 연 ${fmt(b.ret,1)}%로 요구수익률 ${fmt(r,1)}%보다 한참 낮아요. 지금 가격은 낙관 쪽 결과를 상당 부분 반영하고 있어요.`;
    const bear=e.sc.bear;
    const ph=(e.per_hist||[]).map(([y,p])=>`${y} ${fmt(p,1)}`).join(' · ');
    return `<h4>5년 기대수익률 (리포트식)</h4>
      <p class="sub" style="margin:0 0 4px">5년 뒤 주당 가치(5년 뒤 이익 × 종료 PER) + 5년간 받을 배당을 지금 주가와 비교해 연 몇 %짜리 투자인지 봐요. 5년 뒤 이익은 회사·증권사 추정이 아니라 이 대시보드의 <b>정상 이익 ${jo(b.E1)}</b>(사이클·일회성 보정)에서 시나리오 성장률로 키웠고, 남은 호황(불황) 기간의 초과이익은 현금으로 쌓인다고 봤어요.</p>
      ${tbl(['시나리오','5년 뒤 순이익','종료 PER','초과이익 현금','5년 뒤 주당 가치','누적 배당','연환산 기대수익률'],rows)}
      <p style="font-size:13px;line-height:1.65;margin:6px 0 2px">${verdict} 확률 가중(막스 점검의 비관 ${Math.round((e.weights.bear||0)*100)}%·기본 ${Math.round((e.weights.base||0)*100)}%·낙관 ${Math.round((e.weights.bull||0)*100)}%) 기대수익률은 <b class="${col(e.weighted)}">${sg(e.weighted)}</b>예요.</p>
      <p class="sub" style="margin:2px 0 0">종료 PER: ${e.per_src} 절사평균 ${fmt(e.per_mean,1)}배의 85%를 기본으로, 낙관 120%${bear.stress?', 비관은 이익을 이미 불황 수준으로 낮춰 PER은 기본의 85%만':', 비관 70%'}(리포트: 과거 평균보다 약간 낮게).${ph?` 과거 연말 PER: ${ph}.`:''} 배당은 지금 배당성향 ${fmt(e.payout,1)}% 유지.${bear.stress?` 비관 이익: ${bear.how.replace(/^불황\s*/,'')}.`:''}</p>`;
  }

  function plan(L,v){
    const p=L.plan; if(!p) return '';
    const t=(l,val,s,hl)=>`<div class="kpi"${hl?' style="outline:2px solid var(--accent)"':''}><div class="l">${l}</div><div class="v">${val}</div><div class="s">${s}</div></div>`;
    const z=p.zone;
    return `<h4>투자 방법 — 나눠 사고, 확인하며 늘리고, 비싸지면 줄이기</h4>
      <p class="sub" style="margin:0 0 4px">리포트처럼 '매수/매도' 대신 가격대별 행동을 정했어요. 지금 <b>${fmt(p.price)}원</b> → <b>${z}</b></p>
      <div class="vgrid">
        ${t('나눠 사기 시작',p.start_ps?fmt(p.start_ps)+'원 이하':'–','기본 시나리오 5년 기대수익률이 할인율 이상이 되는 가격',z==='나눠 사기 구간')}
        ${t('비중 확대',p.add_ps?fmt(p.add_ps)+'원 이하':'–','막스 점검의 안전마진 매수가(불황이 와도 버틸 가격)',z.startsWith('매수'))}
        ${t('비중 축소',p.trim_ps?fmt(p.trim_ps)+'원 이상':'–',`정상 이익 기준 PER이 낙관 종료 PER ${fmt(p.trim_per,1)}배에 닿는 가격`,z==='비중 축소 구간')}
      </div>`;
  }

  function watch(c,D){
    const r=(D&&D.reviews&&D.reviews.companies||{})[c&&c.code]; const dp=(D&&D.deep&&D.deep.companies||{})[c&&c.code];
    const ck=(dp&&dp.diagnosis&&dp.diagnosis.check)||[]; const w=ck.length>=3?ck:[].concat((r&&r.watch)||[],ck);
    const u=[...new Set(w)].slice(0,6);
    return u.length?`<p style="font-size:13px;margin:2px 0 8px"><b>비중을 늘리기 전에 확인할 지표</b>: ${u.join(' · ')}</p>`:'';
  }

  function bridge(L){
    const b=L.bridge; if(!b||!b.length) return '';
    const rows=b.map(x=>({cells:[x.y,`<b class="${col(x.d_op)}">${sgj(x.d_op)}</b>`,`${sgj(x.vol)} <span class="sub">(매출 ${sg(x.rev_g)})</span>`,`${sgj(x.margin)} <span class="sub">(${fmt(x.opm_prev,1)}→${fmt(x.opm,1)}%)</span>`,x.main]}));
    const big=b.filter(x=>x.main==='이익률').length;
    const take=big>=Math.ceil(b.length/2)?'이익 변화의 대부분이 이익률(원가·판가·고정비)에서 나왔어요. 매출이 늘어도 이익이 따라오지 않을 수 있는 회사라, 원가와 가격 전가를 먼저 봐야 해요.'
      :'이익 변화의 대부분이 물량(매출)에서 나왔어요. 고객 수요·출하량이 핵심 변수예요.';
    return `<h4>과거 영업이익 변화의 원인 — 물량 vs 이익률</h4>
      <p class="sub" style="margin:0 0 4px">영업이익 변화 = 물량 효과(매출 변화 × 전년 이익률) + 이익률 효과(올해 매출 × 이익률 변화). 리포트의 '연도별 변화 요인'을 숫자로 자동 분해했어요.</p>
      ${tbl(['연도','영업이익 변화','물량 효과','이익률 효과','주된 원인'],rows)}<p style="font-size:13px;margin:4px 0 8px">${take}</p>`;
  }

  function shocks(L){
    const s=L.shocks; if(!s||(!s.list.length&&!s.now)) return '';
    const rows=s.list.map(x=>({cells:[x.start,`${fmt(x.start_m,1)}%`,`${x.trough} ${fmt(x.trough_m,1)}%`,`−${fmt(x.drop,1)}%p`,x.recovered?`${x.recovered} (${x.quarters}분기)`:'<b>회복 전</b>']}));
    const now=s.now?`지금(${s.now.q}) ${s.basis}은 ${fmt(s.now.m,1)}%로 최근 고점 ${fmt(s.now.peak,1)}%보다 ${fmt(s.now.gap,1)}%p 낮아요.${s.q_median?` 과거 비슷한 하락은 원래 수준을 되찾는 데 보통 ${s.q_median}분기가 걸렸어요.`:''}`:'최근 4개 분기 안에 2%p 넘는 이익률 하락은 없어요.';
    return `<h4>과거 이익률 충격과 회복 기간</h4>
      <p class="sub" style="margin:0 0 4px">분기 ${s.basis}이 기준 수준(직전 4개 분기 중앙값)보다 4%p 넘게 떨어졌던 구간과, 기준 −1%p 안으로 돌아오기까지 걸린 분기 수예요. 리포트가 2021년 원가 급등기와 지금을 비교한 방식이에요(분기 자료는 2022년부터).</p>
      ${rows.length?tbl(['시작','기준 이익률','바닥','하락 폭','회복'],rows):''}<p style="font-size:13px;margin:4px 0 8px">${now}</p>`;
  }

  function sens(L){
    const s=L.sens; if(!s) return '';
    const lab=s.kind==='gpm'?'매출총이익률':'영업이익률';
    const rows=s.gs.map((g,i)=>({cells:[`매출 ${sg(g)}`,...s.grid[i].map((x,j)=>i===2&&j===1?`<b>${jo(x)}</b>`:jo(x))]}));
    return `<h4>다음 1년 영업이익 민감도</h4>
      <p class="sub" style="margin:0 0 4px">최근 4개 분기 매출 ${jo(s.base_rev)}에서 매출 증가율(가운데 = 추세 성장률)과 ${lab}(가운데 = 최근 3년 평균)이 달라질 때의 영업이익이에요.${s.kind==='gpm'?` 판관비 ${jo(s.sga)}은 고정비처럼 움직인다고 봐서, 매출이 꺾이면 이익이 더 크게 줄어요.`:''}</p>
      ${tbl(['', ...s.ms.map(m=>`${lab} ${fmt(m,1)}%`)],rows)}`;
  }

  function peers(L){
    const p=L.peers; if(!p) return '';
    const rows=p.rows.map(x=>({_self:x.self,cells:[x.name,jo(x.mcap),jo(x.rev),x.opm==null?'–':fmt(x.opm,1)+'%',jo(x.ni),x.roe==null?'–':fmt(x.roe,1)+'%',x.per?fmt(x.per,1)+'배':'적자',x.pbr?fmt(x.pbr,2)+'배':'–']}));
    const me=p.rows.find(x=>x.self)||{};
    let t='';
    if(me.roe!=null&&p.med_roe!=null&&me.per&&p.med_per){
      const hiR=me.roe>p.med_roe, loP=me.per<p.med_per;
      t=hiR&&loP?`ROE(${fmt(me.roe,1)}%)는 동종 중앙값(${fmt(p.med_roe,1)}%)보다 높은데 PER(${fmt(me.per,1)}배)은 중앙값(${fmt(p.med_per,1)}배)보다 낮아요. 시장이 할인하는 이유(이익 변동성·지배구조·고부가 제품 부족 등)를 찾는 것이 투자 판단의 핵심이에요.`
        :!hiR&&!loP?`ROE는 동종 중앙값보다 낮은데 PER은 높아요. 앞으로 이익이 크게 는다는 기대가 가격에 들어 있어요.`
        :hiR?`ROE와 PER이 모두 동종보다 높아요. 수익성 프리미엄을 받고 있어요.`:`ROE와 PER이 모두 동종보다 낮아요. 싼 이유가 수익성에 있어요.`;
      if(me.opm!=null&&p.med_opm!=null) t+=` 영업이익률은 ${fmt(me.opm,1)}%로 중앙값 ${fmt(p.med_opm,1)}%보다 ${me.opm>=p.med_opm?'높아요':'낮아요'}.`;
    }
    return `<h4>동종 비교 — ${p.group} ${p.n}개사 중 시가총액 상위</h4>
      ${tbl(['회사','시가총액','매출(4분기)','영업이익률','순이익','ROE','PER','PBR'],rows)}${t?`<p style="font-size:13px;margin:4px 0 8px">${t}</p>`:''}`;
  }

  window.lensBlock=function(v,D,c){
    const L=v&&v.lens; if(!L) return '';
    const code=c&&c.code;
    return box(`<div style="display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;align-items:baseline"><b style="font-size:15px">리포트식 점검</b>${code?`<a href="${REPORT}#${code}" target="_blank" rel="noopener" style="color:var(--accent);font-size:13px">이 회사 기업분석 리포트 전체 보기 →</a>`:''}</div>
      <p class="sub" style="margin:2px 0 6px">20년 가치투자자가 만든 AI 기업분석 툴의 리포트(이엔에프테크놀로지, 2026-11-26)를 역엔지니어링해서 가져온 도구예요. 적정주가는 위 정상 이익 모델 그대로이고, 여기서는 '연 몇 % 투자인지'와 '어떻게 사고팔지'를 봐요.</p>
      ${er5(L,v)}${plan(L,v)}${watch(c,D)}${bridge(L)}${shocks(L)}${sens(L)}${peers(L)}`);
  };
})();
