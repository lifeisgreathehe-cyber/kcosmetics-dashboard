/* 회사별 장기 주가 + 분기 실적(매출액·매출총이익·영업이익·순이익) 세로 패널 차트 — 모든 산업 대시보드 공용.
   사용법: <script src="(상대경로)/shared/finchart.js"></script> (Chart.js 4 먼저 로드)
     const h = FinChart.render(el, {
       price: {months:["2016-01",...], close:[...]},          // stock_hist.json series[code] (없으면 주가 패널 생략)
       quarterly: {"2025Q3": {rev, gp, op, ni}, ...},          // companies.json quarterly (백만원)
       niLabel: "지배주주순이익",                               // 선택
       range: "fin" | "all"                                    // 선택: 실적 기간에 맞춤(기본) / 주가 전체
     });  h.destroy() 로 정리.
   색은 페이지 CSS 변수(--s1, --s2, --ink-2, --ink-3, --line, --up, --down)를 읽는다. */
(function () {
  const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const YW = 58; // 모든 패널 y축 폭을 같게 해서 x축 정렬
  const fmt = v => v == null ? '–' : Math.round(v).toLocaleString('ko-KR');
  function qx(k) { const y = +k.slice(0, 4), q = +k.slice(5); return y + (q * 3 - 1) / 12; }
  function mx(m) { const y = +m.slice(0, 4), mo = +m.slice(5, 7); return y + (mo - 0.5) / 12; }
  const qlabel = x => { const y = Math.floor(x), q = Math.round((x - y) * 12 + 1) / 3; return `${y}Q${Math.round(q)}`; };
  const mlabel = x => { const y = Math.floor(x), m = Math.round((x - y) * 12 + 0.5); return `${y}-${String(m).padStart(2, '0')}`; };

  const extremes = {
    id: 'fcExtremes',
    afterDatasetsDraw(ch, a, o) {
      if (!o || !o.on) return;
      const ds = ch.data.datasets[0], pts = ch.getDatasetMeta(0).data;
      if (!pts.length) return;
      let hi = 0, lo = 0;
      ds.data.forEach((p, i) => { if (p.y > ds.data[hi].y) hi = i; if (p.y < ds.data[lo].y) lo = i; });
      const c = ch.ctx; c.save(); c.font = '600 11px system-ui, sans-serif';
      [[hi, '최고', css('--up') || '#d33', -8], [lo, '최저', css('--down') || '#36c', 16]].forEach(([i, t, col, dy]) => {
        const p = pts[i], d = ds.data[i];
        const s = `${t} ${fmt(d.y)} (${mlabel(d.x)})`;
        c.fillStyle = col; const w = c.measureText(s).width;
        let x = p.x + 6; if (x + w > ch.chartArea.right) x = p.x - w - 6;
        c.fillText(s, x, Math.min(Math.max(p.y + dy, ch.chartArea.top + 10), ch.chartArea.bottom - 2));
      });
      c.restore();
    }
  };

  function render(el, o) {
    const charts = [];
    const Q = o.quarterly || {}, qk = Object.keys(Q).sort();
    const P = o.price && o.price.months && o.price.months.length ? o.price : null;
    let x0, x1;
    const fx0 = qk.length ? qx(qk[0]) - 0.25 : null, fx1 = qk.length ? qx(qk[qk.length - 1]) + 0.25 : null;
    const px0 = P ? mx(P.months[0]) : null, px1 = P ? mx(P.months[P.months.length - 1]) + 0.1 : null;
    if (o.range === 'all' && P) { x0 = Math.min(px0, fx0 ?? px0); x1 = Math.max(px1, fx1 ?? px1); }
    else { x0 = fx0 ?? px0; x1 = Math.max(fx1 ?? -1e9, px1 ?? -1e9); }
    if (x0 == null) { el.innerHTML = '<p class="sub">표시할 주가·실적 데이터가 아직 없어요.</p>'; return { destroy() {} }; }
    const panels = [];
    if (P) panels.push({ key: 'price', label: '주가 (월말 종가, 원)', h: 230,
      data: P.months.map((m, i) => ({ x: mx(m), y: P.close[i] })).filter(p => p.y && p.x >= x0 - 0.01 && p.x <= x1) });
    [['rev', '매출액'], ['gp', '매출총이익'], ['op', '영업이익'], ['ni', o.niLabel || '순이익']].forEach(([k, l]) => {
      const d = qk.filter(q => Q[q] && Q[q][k] != null).map(q => ({ x: qx(q), y: Q[q][k] / 100 }));
      if (d.length) panels.push({ key: k, label: l + ' (분기, 억원)', h: 118, data: d });
    });
    el.innerHTML = panels.map((p, i) => `<div class="fc-p" style="position:relative;height:${p.h + (i === panels.length - 1 ? 22 : 0)}px;border-top:${i ? '1px solid ' + (css('--line') || '#ddd') : '0'}">
      <div style="position:absolute;left:${YW + 6}px;top:4px;font-size:12px;font-weight:600;color:${css('--ink-2')};z-index:1;pointer-events:none">${p.label}</div><canvas></canvas></div>`).join('');
    const grid = css('--line') || '#e5e5e5', ink3 = css('--ink-3') || '#888';
    const cs = el.querySelectorAll('canvas');
    panels.forEach((p, i) => {
      const last = i === panels.length - 1, isP = p.key === 'price';
      const ys = p.data.map(d => d.y), mn = Math.min(...ys), mxv = Math.max(...ys);
      const logy = isP && mn > 0 && mxv / mn > 4;
      const col = isP ? (css('--s1') || '#2a6') : (css('--s2') || '#83c');
      charts.push(new Chart(cs[i], {
        type: 'line',
        data: { datasets: [{ data: p.data, borderColor: col, backgroundColor: col, borderWidth: isP ? 1.6 : 1.4,
          pointRadius: isP ? 0 : 2.2, pointHoverRadius: 4, tension: 0, spanGaps: false }] },
        options: {
          responsive: true, maintainAspectRatio: false, animation: false, parsing: false, normalized: true,
          layout: { padding: { top: 20, right: 8, bottom: 0, left: 0 } },
          interaction: { mode: 'nearest', axis: 'x', intersect: false },
          plugins: { legend: { display: false }, fcExtremes: { on: isP },
            tooltip: { callbacks: { title: it => isP ? mlabel(it[0].parsed.x) : qlabel(it[0].parsed.x),
              label: it => isP ? `${fmt(it.parsed.y)}원` : `${fmt(it.parsed.y)}억원` } } },
          scales: {
            x: { type: 'linear', min: x0, max: x1, grid: { color: grid, drawTicks: false },
              ticks: { display: last, stepSize: 1, color: ink3, autoSkip: true, maxTicksLimit: 14, callback: v => Number.isInteger(v) ? String(v) : '' },
              border: { display: false } },
            y: { type: logy ? 'logarithmic' : 'linear', position: 'right', grid: { color: grid },
              afterFit: s => { s.width = YW; },
              ticks: { color: ink3, maxTicksLimit: isP ? 6 : 3, callback: v => logy && ![1, 2, 5].includes(+String(v)[0]) ? '' : fmt(v) },
              border: { display: false } }
          }
        },
        plugins: [extremes]
      }));
    });
    return { destroy() { charts.forEach(c => c.destroy()); } };
  }
  window.FinChart = { render };
})();
