/* 실적 한눈에 보기 — 주가와 실적을 같은 출발점(=100)에서 비교하는 차트. 모든 산업 대시보드 공용.
   사용법: <script src="(상대경로)/shared/finchart.js"></script> (Chart.js 4 먼저 로드)
     const h = FinChart.render(el, {
       price: {months:["2016-12",...], close:[...]},   // stock_hist.json series[code] (없으면 실적만)
       quarterly: {"2025Q3": {rev, gp, op, ni}, ...},   // companies.json quarterly (백만원, 분기 단독)
       niLabel: "지배주주순이익",                        // 선택
       source: "네이버 금융 월봉(수정주가, 월말 종가)"     // 선택: 출처 표기
     });  h.destroy() 로 정리.
   구성: ① 기간 동안의 변화율 타일(주가·매출·영업이익·순이익)과 한 줄 해석
         ② 지수 차트: 기간 첫 분기를 100으로 놓고 주가(분기 말 종가)와 최근 4개 분기 합계(TTM) 실적을 한 축(로그)에 겹침
         ③ 분기 막대: 매출액·영업이익·순이익(같은 분기 축, 위 차트와 세로로 정렬)
         ④ 표로 보기
   색은 페이지 CSS 변수(--ink, --ink-2, --ink-3, --line, --panel, --s1~s3, --up, --down)를 읽는다. */
(function () {
  const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const RANGES = [['12', '3년'], ['20', '5년'], ['40', '10년'], ['all', '전체']];
  let RANGE = '20';            // 회사를 바꿔도 고른 기간 유지
  const HIDDEN = new Set();    // 범례에서 끈 계열 유지
  const YW = 44;    // 모든 차트의 왼쪽 축 폭·오른쪽 여백을 같게 → 분기 위치가 세로로 정렬

  const fmt = v => v == null || !isFinite(v) ? '–' : Math.round(v).toLocaleString('ko-KR');
  const eok = v => { // 억원 → 읽기 좋은 표기
    if (v == null || !isFinite(v)) return '–';
    const a = Math.abs(v);
    if (a >= 10000) return (v / 10000).toLocaleString('ko-KR', { maximumFractionDigits: a >= 100000 ? 1 : 2 }) + '조';
    return fmt(v) + '억';
  };
  const pct = r => (r >= 0 ? '+' : '') + (Math.abs(r) >= 10 ? Math.round(r * 100).toLocaleString('ko-KR') : (r * 100).toFixed(r * 100 >= 100 || r * 100 <= -100 ? 0 : 1)) + '%';
  const qn = k => +k.slice(0, 4) * 4 + (+k.slice(5) - 1);
  const qk = n => `${Math.floor(n / 4)}Q${n % 4 + 1}`;
  const m2q = m => `${m.slice(0, 4)}Q${Math.ceil(+m.slice(5, 7) / 3)}`;

  function injectStyle() {
    if (document.getElementById('fc-style')) return;
    const s = document.createElement('style'); s.id = 'fc-style';
    s.textContent = `
.fc-top{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;flex-wrap:wrap;margin:0 0 10px}
.fc-segs{display:flex;gap:4px;flex-wrap:wrap}.fc-segs[hidden]{display:none}
.fc-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin:0 0 10px}
.fc-kpi{border:1px solid var(--line);border-radius:8px;padding:8px 10px;background:var(--panel)}
.fc-kpi .l{font-size:12px;color:var(--ink-2);display:flex;align-items:center;gap:6px}
.fc-kpi .sw{display:inline-block;width:14px;height:3px;border-radius:2px}
.fc-kpi .v{font-family:var(--font-mono,ui-monospace,monospace);font-size:20px;font-weight:500;font-variant-numeric:tabular-nums;margin:2px 0 0;color:var(--ink)}
.fc-kpi .v small{font-size:12px;color:var(--ink-3);margin-left:4px}
.fc-kpi .s{font-size:11.5px;color:var(--ink-3);line-height:1.45}
.fc-read{font-size:13px;color:var(--ink-2);margin:0 0 12px;line-height:1.6}
.fc-read b{color:var(--ink)}
.fc-leg{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:12.5px;color:var(--ink-2);margin:0 0 4px}
.fc-leg button{all:unset;cursor:pointer;display:inline-flex;align-items:center;gap:6px;padding:2px 0}
.fc-leg button[aria-pressed="false"]{opacity:.4}
.fc-leg button:focus-visible{outline:2px solid var(--ink-3);outline-offset:2px;border-radius:3px}
.fc-leg .sw{display:inline-block;width:16px;height:3px;border-radius:2px}
.fc-ttl{font-size:12px;font-weight:600;color:var(--ink-2);margin:10px 0 0}
.fc-ttl span{font-weight:400;color:var(--ink-3)}
.fc-c{position:relative}
.fc-note{font-size:11.5px;color:var(--ink-3);margin:6px 0 0;line-height:1.55}
.fc-tbl{margin-top:10px;font-size:12.5px}
.fc-tbl summary{cursor:pointer;color:var(--ink-2)}
.fc-tbl .w{overflow-x:auto;max-height:360px;margin-top:6px}
.fc-tbl table{border-collapse:collapse;width:100%;min-width:620px}
.fc-tbl th,.fc-tbl td{padding:4px 8px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
.fc-tbl th{font-weight:500;color:var(--ink-2);font-size:11.5px;position:sticky;top:0;background:var(--panel)}
.fc-tbl td{font-family:var(--font-mono,ui-monospace,monospace);font-size:12px}
.fc-tbl td:first-child,.fc-tbl th:first-child{text-align:left}
@media (max-width:600px){.fc-kpi .v{font-size:17px}}`;
    document.head.appendChild(s);
  }

  // 공유 크로스헤어: 한 차트에 마우스를 올리면 모든 패널에 같은 분기 세로선
  function crosshair(group) {
    return {
      id: 'fcCross',
      afterDatasetsDraw(ch) {
        if (group.idx == null) return;
        const x = ch.scales.x.getPixelForValue(group.idx);
        if (x < ch.chartArea.left || x > ch.chartArea.right) return;
        const c = ch.ctx; c.save(); c.strokeStyle = css('--ink-3'); c.lineWidth = 1; c.setLineDash([3, 3]);
        c.beginPath(); c.moveTo(x, ch.chartArea.top); c.lineTo(x, ch.chartArea.bottom); c.stroke(); c.restore();
      }
    };
  }

  function render(el, o) {
    injectStyle();
    const charts = [];
    build(el, o, charts);
    return { destroy() { charts.forEach(c => c.destroy()); charts.length = 0; } };
  }

  function build(el, o, charts) {
    const Q = o.quarterly || {};
    const NI = o.niLabel || '순이익';
    const P = o.price && o.price.months && o.price.months.length ? o.price : null;

    // ---- 분기 단위로 맞추기
    const qkeys = Object.keys(Q).filter(k => /^\d{4}Q[1-4]$/.test(k)).sort();
    const val = (k, f) => Q[k] && Q[k][f] != null ? Q[k][f] / 100 : null; // 억원
    const ttm = (n, f) => { let s = 0; for (let i = 0; i < 4; i++) { const v = val(qk(n - i), f); if (v == null) return null; s += v; } return s; };
    const pq = {}; // 분기 → 그 분기 마지막 달 종가
    if (P) P.months.forEach((m, i) => { const v = P.close[i]; if (v > 0) pq[qn(m2q(m))] = { v, m }; });
    const pqn = Object.keys(pq).map(Number);
    const qnums = qkeys.map(qn);
    const ttmStart = qnums.filter(n => ttm(n, 'rev') != null);
    if (!qnums.length && !pqn.length) { el.innerHTML = '<p class="sub">표시할 주가·실적 데이터가 아직 없어요.</p>'; return; }
    const end = Math.max(...qnums, ...pqn);
    // 시작: 주가와 TTM 매출이 모두 있는 첫 분기(둘 중 하나가 없으면 있는 쪽 기준)
    let start;
    if (ttmStart.length && pqn.length) start = ttmStart.find(n => pq[n]) ?? Math.max(ttmStart[0], Math.min(...pqn));
    else if (ttmStart.length) start = ttmStart[0];
    else if (qnums.length && pqn.length) start = Math.max(qnums[0], Math.min(...pqn));
    else start = Math.min(...(qnums.length ? qnums : pqn));
    const total = end - start + 1;
    const opts = RANGES.filter(([k]) => k === 'all' || +k < total);
    if (!opts.some(([k]) => k === RANGE)) RANGE = 'all';
    const n0 = RANGE === 'all' ? start : Math.max(start, end - +RANGE + 1);
    const axis = []; for (let n = n0; n <= end; n++) axis.push(n);
    const labels = axis.map(qk);

    // ---- 계열
    const lastEarn = Math.max(...qnums.filter(n => n <= end), -Infinity);
    const S = [
      { k: 'px', label: '주가', unit: '원', color: css('--ink') || '#222', w: 2.6,
        raw: axis.map(n => pq[n] ? pq[n].v : null) },
      { k: 'rev', label: '매출액', color: css('--s1') || '#2a78d6', w: 2, raw: axis.map(n => ttm(n, 'rev')) },
      { k: 'op', label: '영업이익', color: css('--s2') || '#eb6834', w: 2, raw: axis.map(n => ttm(n, 'op')) },
      { k: 'ni', label: NI, color: css('--s3') || '#1baf7a', w: 2, raw: axis.map(n => ttm(n, 'ni')) }
    ].filter(s => s.raw.some(v => v != null));
    // 공통 기준 분기: 모든 계열 값이 있는 첫 분기(없으면 각자 첫 값)
    const bi = axis.findIndex((_, i) => S.every(s => s.raw[i] != null));
    S.forEach(s => {
      const i0 = bi >= 0 ? bi : s.raw.findIndex(v => v != null);
      let i1 = -1; s.raw.forEach((v, i) => { if (v != null) i1 = i; });
      s.i0 = i0; s.i1 = i1; s.b = s.raw[i0]; s.e = s.raw[i1];
      // 로그 지수는 양수만 가능: 기간 중 적자(≤0)가 있으면 지수선에서 빼고 막대로만 보여준다
      s.indexable = s.raw.slice(i0).every(v => v == null || v > 0) && s.b > 0;
      s.idx = s.raw.map((v, i) => s.indexable && v != null && i >= i0 ? v / s.b * 100 : null);
    });
    const px = S.find(s => s.k === 'px');
    const baseQ = bi >= 0 ? labels[bi] : labels[0];
    const yrs = s => (s.i1 - s.i0) / 4;

    // ---- KPI 타일
    const tile = s => {
      const name = s.k === 'px' ? '주가' : `${s.label} <span style="color:var(--ink-3)">최근 4분기 합</span>`;
      const from = s.k === 'px' ? `${labels[s.i0]} 말 ${fmt(s.b)}원` : `${labels[s.i0]} ${eok(s.b)}`;
      const to = s.k === 'px' ? `${pq[axis[s.i1]].m} ${fmt(s.e)}원` : `${labels[s.i1]} ${eok(s.e)}`;
      let v;
      if (s.b > 0 && s.e > 0) {
        const r = s.e / s.b - 1, y = yrs(s), cagr = y >= 1 ? Math.pow(s.e / s.b, 1 / y) - 1 : null;
        v = `${pct(r)}${cagr != null ? `<small>연 ${pct(cagr)}</small>` : ''}`;
      } else if (s.b <= 0 && s.e > 0) v = '흑자 전환';
      else if (s.b > 0 && s.e <= 0) v = '적자 전환';
      else v = s.e > s.b ? '적자 축소' : '적자 확대';
      return `<div class="fc-kpi"><div class="l"><span class="sw" style="background:${s.color}"></span>${name}</div><div class="v">${v}</div><div class="s">${from} → ${to}</div></div>`;
    };

    // ---- 한 줄 해석: 주가 변화 vs 이익 변화 → 이익 대비 주가 배수(멀티플) 변화
    let read = '';
    const earn = ['op', 'ni', 'rev'].map(k => S.find(s => s.k === k)).find(s => s && s.b > 0 && s.e > 0);
    if (px && earn && px.b > 0) {
      // 같은 기간끼리 비교: 실적 마지막 분기 말 주가 기준
      const pe = px.raw[earn.i1] ?? px.e, rp = pe / px.b, re = earn.e / earn.b, mult = rp / re - 1;
      const nm = earn.k === 'rev' ? '매출' : earn.label;
      const what = earn.k === 'rev' ? 'PSR(매출 대비 주가 배수)' : earn.k === 'op' ? '영업이익 대비 주가 배수' : 'PER(이익 대비 주가 배수)';
      read = `<b>${labels[earn.i0]}→${labels[earn.i1]}</b> 주가는 <b>${pct(rp - 1)}</b>, ${nm}(최근 4분기 합)은 <b>${pct(re - 1)}</b> 변했어요. `;
      if (Math.abs(mult) < 0.1) read += `주가가 이익과 거의 같은 속도로 움직여 ${what}는 비슷하게 유지됐어요. 주가 변화가 대부분 실적으로 설명된다는 뜻이에요.`;
      else if (mult > 0) read += `주가가 ${nm}보다 더 많이 ${rp >= 1 ? '올라' : '버텨'} ${what}가 <b>${pct(mult)}</b> 높아졌어요. 앞으로의 성장 기대가 주가에 먼저 반영됐거나 시장이 더 높은 값을 쳐주게 됐다는 뜻이라, 기대만큼 실적이 따라오는지가 중요해요.`;
      else read += `${nm}이 주가보다 더 좋아져 ${what}가 <b>${pct(mult)}</b> 낮아졌어요. 실적 개선이 아직 주가에 덜 반영됐거나, 시장이 지금 이익이 오래가지 못할 거라고(사이클 고점 등) 보고 있다는 뜻이에요.`;
      if (px.i1 > earn.i1) read += ` 실적 발표 이후(${labels[earn.i1 + 1]}~) 주가는 ${pct(px.e / pe - 1)} 더 움직였어요.`;
    }
    const excluded = S.filter(s => !s.indexable && s.k !== 'px').map(s => s.label);

    // ---- DOM
    const cur = RANGE;
    el.innerHTML = `
      <div class="fc-top"><div class="fc-kpis" style="flex:1 1 520px;margin:0">${S.map(tile).join('')}</div>
        <div class="fc-segs" role="group" aria-label="기간"${opts.length < 2 ? ' hidden' : ''}>${opts.map(([k, l]) => `<button class="seg" data-v="${k}" aria-pressed="${k === cur}">${l}</button>`).join('')}</div></div>
      ${read ? `<p class="fc-read">${read}</p>` : ''}
      <div class="fc-ttl">${baseQ}을 100으로 놓고 본 변화 <span>· 로그 눈금이라 기울기가 같으면 성장률이 같아요 · 실적은 최근 4개 분기 합계, 주가는 분기 말 종가</span></div>
      <div class="fc-leg">${S.filter(s => s.indexable).map(s => `<button type="button" data-k="${s.k}" aria-pressed="${!HIDDEN.has(s.k)}"><span class="sw" style="background:${s.color};height:${s.k === 'px' ? 4 : 3}px"></span>${s.k === 'px' ? '주가' : s.label + '(4분기 합)'}</button>`).join('')}</div>
      <div class="fc-c" style="height:${el.clientWidth < 600 ? 250 : 300}px"><canvas aria-label="주가와 실적 지수 비교 차트"></canvas></div>
      ${excluded.length ? `<p class="fc-note">${excluded.join('·')}은 이 기간에 적자(4분기 합 0 이하) 구간이 있어 지수로 나타낼 수 없어서 아래 분기 막대로만 보여줘요.</p>` : ''}
      ${['rev', 'op', 'ni'].filter(k => qkeys.some(q => Q[q][k] != null)).map(k => `<div class="fc-ttl">${k === 'rev' ? '매출액' : k === 'op' ? '영업이익' : NI} <span>· 분기, 억원</span></div><div class="fc-c" style="height:${k === 'ni' ? 112 : 96}px"><canvas data-k="${k}"></canvas></div>`).join('')}
      <p class="fc-note">주가: ${o.source || '월말 종가(수정주가)'} · 실적: 분기 ${qkeys[0] || '–'}~${qkeys[qkeys.length - 1] || '–'}. 주가는 1주 가격이라 유상증자·자사주 소각처럼 주식 수가 바뀌면 이익 변화와 차이가 날 수 있어요.</p>
      <details class="fc-tbl"><summary>표로 보기</summary><div class="w"><table><thead><tr><th>분기</th><th>분기 말 주가(원)</th><th>매출액</th><th>영업이익</th><th>${NI}</th><th>매출 4분기 합</th><th>영업이익 4분기 합</th><th>${NI} 4분기 합</th></tr></thead><tbody>
      ${axis.slice().reverse().map(n => `<tr><td>${qk(n)}</td><td>${pq[n] ? fmt(pq[n].v) : '–'}</td>${['rev', 'op', 'ni'].map(f => `<td>${fmt(val(qk(n), f))}</td>`).join('')}${['rev', 'op', 'ni'].map(f => `<td>${fmt(ttm(n, f))}</td>`).join('')}</tr>`).join('')}
      </tbody></table><p class="fc-note">단위: 억원(주가 제외)</p></div></details>`;

    el.querySelectorAll('.fc-segs button').forEach(b => b.onclick = () => { RANGE = b.dataset.v; redraw(); });
    const redraw = () => { charts.forEach(c => c.destroy()); charts.length = 0; build(el, o, charts); };

    const grid = css('--line') || '#e5e5e5', ink3 = css('--ink-3') || '#888', ink2 = css('--ink-2') || '#555';
    const font = getComputedStyle(document.body).fontFamily;
    const group = { idx: null };
    const cross = crosshair(group);
    const narrow = el.clientWidth < 600, PADR = narrow ? 92 : 118;
    const step = Math.max(1, Math.ceil(axis.length / 4 / (narrow ? 4 : 10)));
    const xScale = show => ({
      type: 'category', labels, offset: true,
      grid: { display: false }, border: { color: grid },
      ticks: { display: show, color: ink3, maxRotation: 0, autoSkip: false, font: { size: 11 },
        callback: (v, i) => { const l = labels[i]; return l.endsWith('Q1') && (+l.slice(0, 4)) % step === 0 ? (narrow ? "'" + l.slice(2, 4) : l.slice(0, 4)) : ''; } }
    });
    const hover = (e, act, ch) => {
      const x = ch.scales.x, i = Math.round(x.getValueForPixel(e.x));
      const ni = e.type === 'mouseout' || i < 0 || i >= labels.length ? null : i;
      if (ni !== group.idx) { group.idx = ni; charts.forEach(c => c !== ch && c.draw()); }
    };
    const leave = { id: 'fcLeave', afterEvent(ch, a) { if (a.event.type === 'mouseout' && group.idx != null) { group.idx = null; charts.forEach(c => c.draw()); } } };

    // ① 지수 차트
    const vis = S.filter(s => s.indexable);
    const endLabels = {
      id: 'fcEnd',
      afterDatasetsDraw(ch) {
        const c = ch.ctx, A = ch.chartArea, items = [];
        ch.data.datasets.forEach((d, di) => {
          if (!ch.isDatasetVisible(di)) return;
          const s = d._s, meta = ch.getDatasetMeta(di), p = meta.data[s.i1];
          if (!p || s.idx[s.i1] == null) return;
          items.push({ y: p.y, x: p.x, s, t: `${s.k === 'px' ? '주가' : s.k === 'ni' ? '순이익' : narrow ? { rev: '매출', op: '영업익' }[s.k] : s.label} ${pct(s.idx[s.i1] / 100 - 1)}` });
        });
        items.sort((a, b) => a.y - b.y);
        for (let i = 1; i < items.length; i++) if (items[i].y - items[i - 1].y < 14) items[i].y = items[i - 1].y + 14;
        const over = items.length ? items[items.length - 1].y - (A.bottom + 4) : 0;
        if (over > 0) items.forEach(it => it.y -= over);
        c.save(); c.font = `600 11px ${font}`; c.textBaseline = 'middle';
        items.forEach(it => {
          c.fillStyle = it.s.color; c.fillRect(A.right + 6, it.y - 1.5, 8, 3);
          c.fillStyle = ink2; c.fillText(it.t, A.right + 17, it.y);
        });
        c.restore();
      }
    };
    const ys = vis.flatMap(s => s.idx.filter(v => v != null));
    const ymin = Math.min(100, ...ys), ymax = Math.max(100, ...ys);
    const wide = ymax / ymin > 3;
    const idxCanvas = el.querySelector('.fc-c canvas');
    if (vis.length) charts.push(new Chart(idxCanvas, {
      type: 'line',
      data: { labels, datasets: vis.map(s => ({ _s: s, label: s.label, data: s.idx, borderColor: s.color, backgroundColor: s.color,
        borderWidth: s.w, pointRadius: 0, pointHoverRadius: 4, pointHoverBorderWidth: 2, pointHoverBorderColor: css('--panel') || '#fff',
        tension: 0, spanGaps: true, hidden: HIDDEN.has(s.k) })) },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        layout: { padding: { top: 8, right: PADR, bottom: 0, left: 0 } },
        interaction: { mode: 'index', intersect: false },
        onHover: hover,
        plugins: { legend: { display: false },
          tooltip: { filter: it => it.raw != null, itemSort: (a, b) => b.raw - a.raw,
            callbacks: {
              title: it => labels[it[0].dataIndex] + (pq[axis[it[0].dataIndex]] ? ` (주가 ${pq[axis[it[0].dataIndex]].m})` : ''),
              label: it => { const s = it.dataset._s, r = s.raw[it.dataIndex];
                return ` ${s.k === 'px' ? '주가' : s.label} ${fmt(it.raw)} · ${s.k === 'px' ? fmt(r) + '원' : '4분기 합 ' + eok(r)}`; } } } },
        scales: {
          x: xScale(true),
          y: { type: 'logarithmic', position: 'left', min: ymin * 0.92, max: ymax * 1.08,
            afterFit: sc => { sc.width = YW; },
            grid: { color: c => c.tick && Math.abs(c.tick.value - 100) < 1e-6 ? ink3 : grid, lineWidth: c => c.tick && Math.abs(c.tick.value - 100) < 1e-6 ? 1.2 : 1 },
            border: { display: false },
            afterBuildTicks: sc => {
              const t = [], lo = sc.min, hi = sc.max;
              const gen = ms => { t.length = 0; for (let e = Math.floor(Math.log10(lo)) - 1; e <= Math.ceil(Math.log10(hi)); e++)
                ms.forEach(m => { const v = m * 10 ** e; if (v >= lo && v <= hi) t.push({ value: v }); }); };
              gen(wide ? [1, 2, 5] : [1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 6, 8]);
              if (wide && t.length < 5) gen([1, 1.5, 2, 3, 5, 7]);
              if (t.length > 9) gen([1, 3]);
              if (!t.some(x => x.value === 100)) t.push({ value: 100 });
              sc.ticks = t.sort((a, b) => a.value - b.value);
            },
            ticks: { color: ink3, font: { size: 10.5 }, autoSkip: false, callback: v => fmt(v) } }
        }
      },
      plugins: [cross, endLabels, leave]
    }));
    else idxCanvas.parentElement.outerHTML = '<p class="fc-note">지수로 비교할 수 있는 계열이 없어요(실적이 4개 분기 이상 쌓이면 나타나요).</p>';

    el.querySelectorAll('.fc-leg button').forEach(b => b.onclick = () => {
      const k = b.dataset.k, on = HIDDEN.has(k); on ? HIDDEN.delete(k) : HIDDEN.add(k);
      b.setAttribute('aria-pressed', String(on));
      const ch = charts[0], di = ch.data.datasets.findIndex(d => d._s.k === k);
      ch.setDatasetVisibility(di, on); ch.update();
    });

    // ② 분기 막대
    const bars = [...el.querySelectorAll('canvas[data-k]')];
    bars.forEach((cv, bi2) => {
      const k = cv.dataset.k, last = bi2 === bars.length - 1;
      const s = { rev: S.find(x => x.k === 'rev'), op: S.find(x => x.k === 'op'), ni: S.find(x => x.k === 'ni') }[k];
      const color = s ? s.color : { rev: css('--s1'), op: css('--s2'), ni: css('--s3') }[k];
      const data = axis.map(n => val(qk(n), k));
      const yoy = i => { const a = data[i], p = val(qk(axis[i] - 4), k); return a != null && p != null && p > 0 ? a / p - 1 : null; };
      const lastI = data.reduce((a, v, i) => v != null ? i : a, -1);
      const tag = {
        id: 'fcTag',
        afterDatasetsDraw(ch) {
          if (lastI < 0) return;
          const c = ch.ctx, A = ch.chartArea, y = yoy(lastI);
          c.save(); c.font = `600 11px ${font}`; c.fillStyle = ink2; c.textBaseline = 'top';
          let ty = A.top;
          if (narrow) { c.fillText(labels[lastI], A.right + 8, ty); ty += 14; }
          c.fillText(narrow ? eok(data[lastI]) : `${labels[lastI]} ${eok(data[lastI])}`, A.right + 8, ty);
          if (y != null) { c.font = `11px ${font}`; c.fillStyle = y >= 0 ? (css('--up') || '#0a0') : (css('--down') || '#c00'); c.fillText(narrow ? `YoY ${pct(y)}` : `전년 대비 ${pct(y)}`, A.right + 8, ty + 15); }
          c.restore();
        }
      };
      charts.push(new Chart(cv, {
        type: 'bar',
        data: { labels, datasets: [{ data, backgroundColor: data.map(v => v != null && v < 0 ? (css('--down') || '#c0392b') : color), borderRadius: 2, borderSkipped: 'start', categoryPercentage: 0.82, barPercentage: 0.9, maxBarThickness: 18 }] },
        options: {
          responsive: true, maintainAspectRatio: false, animation: false,
          layout: { padding: { top: 6, right: PADR, bottom: 0, left: 0 } },
          interaction: { mode: 'index', intersect: false },
          onHover: hover,
          plugins: { legend: { display: false },
            tooltip: { filter: it => it.raw != null, callbacks: {
              title: it => labels[it[0].dataIndex],
              label: it => { const i = it.dataIndex, q = Q[labels[i]] || {}, y = yoy(i), out = [` ${eok(it.raw)}${y != null ? ` · 전년 대비 ${pct(y)}` : ''}`];
                if (k === 'rev' && q.gp != null && q.rev) out.push(` 매출총이익률 ${(q.gp / q.rev * 100).toFixed(1)}%`);
                if (k === 'op' && q.rev) out.push(` 영업이익률 ${(q.op / q.rev * 100).toFixed(1)}%`);
                if (k === 'ni' && q.rev) out.push(` 순이익률 ${(q.ni / q.rev * 100).toFixed(1)}%`);
                return out; } } } },
          scales: {
            x: xScale(last),
            y: { position: 'left', afterFit: sc => { sc.width = YW; }, border: { display: false },
              grid: { color: c => c.tick && c.tick.value === 0 ? ink3 : grid },
              ticks: { color: ink3, font: { size: 10.5 }, maxTicksLimit: 3, callback: v => { const a = Math.abs(v); return a >= 10000 ? (v / 10000).toLocaleString('ko-KR', { maximumFractionDigits: 1 }) + '조' : fmt(v); } } }
          }
        },
        plugins: [cross, tag, leave]
      }));
    });

  }
  window.FinChart = { render };
})();
