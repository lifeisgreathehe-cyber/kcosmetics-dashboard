/* 입체 분석 블록 — 7개 대시보드 공용.
   scripts/context/build.py 가 매일 만드는 data/context.json 을 처음 필요할 때 한 번만 읽어서
   (1) 심층분석의 제품·경쟁·고객·조달 칸 아래에 사업보고서 근거를,
   (2) 심층분석 다음에 '여러 자료로 본 이 회사'(회사·업종·경쟁사·고객사·공급사 뉴스, 블로그, 관심도 추세, 사이클 vs 경쟁력 교차 판정)를 붙인다.
   페이지 스크립트의 함수·변수에 기대지 않는다. */
(function(){
  let DATA=null, loading=null;
  const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const REL={self:'회사',competitor:'경쟁사',customer:'고객사',supplier:'공급사',industry:'업종',blog:'블로그'};
  const TONE={'+':['pos','긍정'],'-':['neg','부정'],'0':['neu','중립']};
  const ORDER=['products','competition','customers','sourcing','cycle','moat','outlook'];
  const fmt=v=>v==null||isNaN(v)?'–':Number(v).toLocaleString('ko-KR',{maximumFractionDigits:0});
  const sgn=v=>(v>0?'+':'')+v.toFixed(1)+'%';

  const css=`.ctx-fact{font-size:13px;color:var(--ink-2);margin:6px 0 0;padding:6px 8px;border-left:3px solid var(--line);background:color-mix(in srgb,var(--line) 18%,transparent);border-radius:0 6px 6px 0}
.ctx-fact b{font-weight:600;color:var(--ink-1,inherit)}
.ctx-fact a{color:var(--accent)}
.ctx-box{border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:10px 0}
.ctx-head{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center}
.ctx-trend{display:inline-flex;gap:8px;align-items:center;font-size:12.5px;color:var(--ink-2)}
.ctx-trend svg{display:block}
.ctx-sec{margin-top:14px}
.ctx-sec h4{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.ctx-list{list-style:none;padding-left:0;margin:6px 0}
.ctx-list li{border-top:1px solid var(--line);padding:8px 0;font-size:14px}
.ctx-list li:first-child{border-top:0}
.ctx-list .rd{display:block;font-size:12.5px;color:var(--ink-2);margin-top:2px}
.ctx-tag{display:inline-block;font-size:11px;padding:1px 6px;border-radius:9px;border:1px solid var(--line);color:var(--ink-2);margin-right:4px;white-space:nowrap}
.ctx-rel{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:6px 0}
.ctx-mini{font-size:12px;color:var(--ink-3)}
.ctx-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:4px 18px}
@media (max-width:600px){.ctx-list li{font-size:13.5px}}`;
  const st=document.createElement('style');st.textContent=css;document.head.appendChild(st);

  function ensure(){
    if(DATA||loading) return loading;
    loading=fetch('data/context.json',{cache:'no-cache'}).then(r=>r.ok?r.json():{}).catch(()=>({})).then(d=>{DATA=d||{};fill()});
    return loading;
  }
  function fill(){
    document.querySelectorAll('[data-ctx]').forEach(el=>{
      const [code,key,deep]=el.dataset.ctx.split('|');
      el.innerHTML=key==='main'?main(code,deep==='1'):cell(code,key);
      el.removeAttribute('data-ctx');
    });
  }
  const co=code=>DATA&&DATA.companies&&DATA.companies[code];
  const src=f=>f&&f.url?` <a href="${esc(f.url)}" target="_blank" rel="noopener">${esc(f.report||'원문')}</a>`:'';

  // ---------- 심층분석 칸 아래 사업보고서 근거
  function cell(code,key){
    const x=co(code); if(!x||!x.facts) return '';
    const f=x.facts, P=[];
    if(key==='products'){
      if(f.mix&&f.mix.length) P.push(`<b>매출 구성</b> ${f.mix.map(m=>esc(m.label.replace(/\s+/g,''))+' '+m.pct.toFixed(1)+'%').join(' · ')}`);
      (f.products||[]).slice(0,1).forEach(t=>P.push(esc(t)));
      if(f.price&&f.price.length) P.push(`<b>판매단가 변화(전년 대비)</b> ${f.price.slice(0,4).map(m=>esc(m.item.replace(/\s+/g,''))+' '+sgn(m.chg)).join(' · ')}`);
    }else if(key==='competition'){
      (f.share||[]).slice(0,1).forEach(t=>P.push(`<b>점유율</b> ${esc(t)}`));
      (f.competition||[]).slice(0,1).forEach(t=>P.push(`<b>경쟁 요소</b> ${esc(t)}`));
    }else if(key==='customers'){
      (f.customers||[]).slice(0,1).forEach(t=>P.push(`<b>주요 고객</b> ${esc(t)}`));
      (f.channel||[]).slice(0,1).forEach(t=>P.push(`<b>판매 경로</b> ${esc(t)}`));
      (f.orders||[]).slice(0,1).forEach(t=>P.push(`<b>수주</b> ${esc(t)}`));
    }else if(key==='sourcing'){
      (f.materials||[]).slice(0,1).forEach(t=>P.push(esc(t)));
      if(f.mat_price&&f.mat_price.length) P.push(`<b>원재료 단가 변화(전년 대비)</b> ${f.mat_price.slice(0,4).map(m=>esc(m.item.replace(/\s+/g,''))+' '+sgn(m.chg)).join(' · ')}`);
      if(f.utilization!=null) P.push(`<b>가동률</b> ${f.utilization}%`);
    }
    if(!P.length) return '';
    return `<div class="ctx-fact">${P.map(p=>`<div>${p}</div>`).join('')}<div class="ctx-mini">사업보고서 원문 발췌 ·${src(f)}</div></div>`;
  }

  function spark(t){
    if(!t||!t.series||t.series.length<4) return '';
    const v=t.series.map(s=>s[1]), mx=Math.max(...v,1), w=150, h=34, n=v.length;
    const pts=v.map((y,i)=>`${(i/(n-1)*w).toFixed(1)},${(h-2-(y/mx)*(h-6)).toFixed(1)}`).join(' ');
    const ch=t.chg==null?'':`<span class="${t.chg>=0?'up':'down'}">${sgn(t.chg)}</span>`;
    return `<span class="ctx-trend" title="${esc(t.src)}"><svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(t.label)} 추세"><polyline fill="none" stroke="var(--accent)" stroke-width="1.8" points="${pts}"/></svg><span>${esc(t.label)} ${t.series.length}주 · 최근 4주 ${ch}</span></span>`;
  }

  function item(s){
    const [tc,tl]=TONE[s.tone]||TONE['0'];
    const who=s.rel==='self'||s.rel==='blog'?REL[s.rel]:`${REL[s.rel]}${s.who?' '+esc(s.who):''}`;
    return `<li><span class="sub">${esc((s.date||'').slice(5))}${s.office?' · '+esc(s.office):''}</span> <span class="ctx-tag">${who}</span><span class="tone ${tc}" style="font-size:11px">${tl}</span><br>
      ${s.url?`<a href="${esc(s.url)}" target="_blank" rel="noopener" style="color:var(--accent)">${esc(s.title)}</a>`:esc(s.title)}
      ${s.summary?`<span class="rd">${esc(s.summary)}</span>`:''}<span class="rd"><b>이렇게 보세요</b> ${esc(s.read)}</span></li>`;
  }

  // ---------- 심층분석 다음 '여러 자료로 본 이 회사'
  function main(code,hasDeep){
    const x=co(code);
    if(!x) return DATA&&DATA.companies?'':'';
    const f=x.facts||{}, S=DATA.sections||{}, sig=x.signals||[];
    const cnt=x.counts||{};
    const cntTxt=['self','industry','competitor','customer','supplier','blog'].filter(k=>cnt[k]).map(k=>`${REL[k]} ${cnt[k]}`).join(' · ');
    const rel={competitor:[],customer:[],supplier:[]};
    (x.related||[]).forEach(r=>rel[r.rel]&&rel[r.rel].push(r));
    const relHtml=Object.entries(rel).filter(([k,v])=>v.length).map(([k,v])=>`<span class="sub" style="margin-right:2px">${REL[k]}</span>${v.map(r=>`<span class="chip" title="${r.peer?'같은 업종 그룹':'심층분석·사업보고서에 언급'}">${esc(r.name)}</span>`).join('')}`).join('<span style="width:10px"></span>');
    const ck=x.check||{}, vd=ck.verdict;
    const vtone=vd?({'경쟁력 우위 신호':'pos','업황 순풍':'pos','경쟁력 점검 필요':'neg','사이클 영향 쪽':'neu'}[vd[0]]||'neu'):'neu';
    // 칸별 묶음
    const by={}; sig.forEach(s=>(by[s.sec]=by[s.sec]||[]).push(s));
    const secHtml=ORDER.filter(k=>by[k]&&by[k].length).map(k=>{
      const L=by[k], sm=(x.sections||{})[k]||{}, lt={'긍정 우세':'pos','부정 우세':'neg'}[sm.lean]||'neu';
      const extra=[];
      if(k==='cycle'){(f.cyclical||[]).slice(0,1).forEach(t=>extra.push(`<b>사업보고서가 말하는 경기 민감도</b> ${esc(t)}`));}
      if(k==='moat'&&f.share&&f.share[0]&&!hasDeep) extra.push(`<b>점유율</b> ${esc(f.share[0])}`);
      return `<div class="ctx-sec"><h4>${esc(S[k]||k)} <span class="tone ${lt}" style="font-size:11px">${esc(sm.lean||'')}</span><span class="ctx-mini">${sm.n||L.length}건 · 긍정 ${sm.pos||0} · 부정 ${sm.neg||0} · ${esc((sm.from||[]).join('·'))}</span></h4>
        ${extra.length?`<div class="ctx-fact">${extra.map(e=>`<div>${e}</div>`).join('')}</div>`:''}
        <ul class="ctx-list">${L.slice(0,4).map(item).join('')}</ul>
        ${L.length>4?`<details><summary class="sub">${L.length-4}건 더 보기</summary><ul class="ctx-list">${L.slice(4).map(item).join('')}</ul></details>`:''}</div>`;
    }).join('');
    const ind=(DATA.industry||{}), grp=Object.keys(ind).find(g=>(ind[g].news||[]).some(n=>sig.some(s=>s.rel==='industry'&&s.url===n.url)));
    const it=grp&&ind[grp].trend;
    // 심층분석이 없는 회사는 사업보고서 근거를 여기서 한꺼번에 보여 준다
    const factsGrid=hasDeep?'':`<div class="ctx-grid">${['products','competition','customers','sourcing'].map(k=>{const h=cell(code,k);return h?`<div><h4>${esc(S[k])}</h4>${h}</div>`:''}).join('')}</div>`;
    return `<h2 style="margin-top:22px">입체 분석: 여러 자료로 본 이 회사</h2>
     <p class="sub">${esc(DATA.updated||'')} 자동 갱신 · ${cntTxt||'수집된 기사 없음'} · 키워드로 자동 분류·해석한 참고 자료예요(사람이 쓴 심층분석을 보완)</p>
     ${f.overview&&f.overview.length?`<h4>사업 개요 (사업보고서 원문)</h4><ul>${f.overview.slice(0,3).map(t=>`<li>${esc(t)}</li>`).join('')}</ul><p class="ctx-mini">출처:${src(f)}</p>`:''}
     ${factsGrid}
     <div class="ctx-box">
      <div class="ctx-head"><b>종합 신호</b>${vd?`<span class="tone ${vtone}">${esc(vd[0])}</span>`:'<span class="tone neu">판단 보류</span>'}${spark(x.trend_search)}${spark(x.trend_news)}${it?spark(Object.assign({},it,{label:'업종('+grp+') '+it.label})):''}</div>
      <p style="margin:6px 0 0">${vd?esc(vd[1]):'회사·업종 뉴스가 아직 충분히 쌓이지 않아 사이클 요인과 경쟁력 요인을 가르지 못했어요.'}</p>
      ${(ck.notes||[]).length?`<ul style="margin:6px 0 0">${ck.notes.map(n=>`<li>${esc(n)}</li>`).join('')}</ul>`:''}
      ${relHtml?`<div class="ctx-rel">${relHtml}</div>`:''}
     </div>
     ${secHtml||'<p class="sub">최근 60일 안에 분류할 기사가 없어요.</p>'}
     <p class="src">자료: ${Object.entries(DATA.sources||{}).map(([k,v])=>`${esc(k)} — ${esc(v)}`).join(' / ')}. 회사 입장에서의 긍정·부정은 관계(경쟁사의 증설은 이 회사에 부담 등)를 반영해 자동으로 매겼어요.</p>`;
  }

  window.ctxBlock=function(c,D){
    const hasDeep=!!(D&&D.deep&&D.deep.companies&&D.deep.companies[c.code]);
    ensure();
    if(DATA) return main(c.code,hasDeep);
    return `<div data-ctx="${esc(c.code)}|main|${hasDeep?1:0}"><p class="sub" style="margin-top:18px">입체 분석 자료를 불러오는 중…</p></div>`;
  };
  window.ctxCell=function(code,key){
    ensure();
    if(DATA) return cell(code,key);
    return `<div data-ctx="${esc(code)}|${key}"></div>`;
  };
})();
