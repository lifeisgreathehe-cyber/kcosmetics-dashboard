/* 최근 20개 분기 TTM(최근 4개 분기 합) 추이 + 주가 — 모든 산업 대시보드 공용.
   사용법: <script src="(상대경로)/shared/ttmchart.js"></script> (Chart.js 4 먼저 로드)
     TTMChart.render(canvasEl, quarterly, {niLabel:'지배주주순이익', subEl, n:20, price})
       quarterly: companies.json 의 quarterly ({"2025Q3": {rev, op, ni}, ...}, 백만원, 분기 단독)
       price: stock_hist.json series[code] ({months:["2016-12",...], close:[...]}, 월말 수정종가). 없으면 주가 칸 생략.
   - TTM은 연속된 4개 분기가 모두 있을 때만 계산(한 분기라도 빠지면 그 시점은 비움 → 선이 끊김).
   - 한 차트 안에 위에서부터 주가 · 매출액 · 영업이익 · 순이익 칸을 세로로 쌓고(같은 분기축), 칸마다 y축을 그 계열의 범위에 맞춰
     증감폭이 잘 보이게 함. 0을 지나는 칸(적자 전환 등)은 0선을 진하게 표시. 차트 높이는 이 모듈이 정함(데스크톱 약 1,200px).
   - companies.json·stock_hist.json이 바뀌면 페이지가 다시 그릴 때 자동으로 반영돼요. 따로 생성하는 파일이 없어요. */
(function () {
  const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const charts = new WeakMap();
  const prevQ = q => { let y = +q.slice(0, 4), n = +q.slice(5) - 1; if (n < 1) { n = 4; y--; } return `${y}Q${n}`; };
  const eok = v => v == null || !isFinite(v) ? null : Math.round(v / 100);  // 백만원 → 억원
  const fmt = v => v == null || !isFinite(v) ? '–' : Math.round(v).toLocaleString('ko-KR');
  const tick = v => { const a = Math.abs(v); return a >= 10000 ? (v / 10000).toLocaleString('ko-KR', { maximumFractionDigits: 1 }) + '조' : fmt(v); };
  const amt = v => v == null || !isFinite(v) ? '–' : (Math.abs(v) >= 10000 ? tick(v) : fmt(v) + '억');
  const chg = (c, p) => {
    if (c == null || p == null) return '';
    if (p <= 0 && c > 0) return ' (흑자전환)';
    if (p > 0 && c <= 0) return ' (적자전환)';
    if (p < 0 && c < 0) return ' (적자지속)';
    if (!p) return '';
    const r = (c - p) / Math.abs(p) * 100;
    return ` (${r >= 0 ? '+' : ''}${r.toFixed(1)}%)`;
  };

  // quarterly → [{q, rev, op, ni}] TTM 시계열(억원). 4개 분기가 모두 있어야 계산.
  function series(quarterly, n) {
    const Q = quarterly || {};
    const keys = Object.keys(Q).sort();
    const out = [];
    for (const q of keys) {
      const w = [q]; while (w.length < 4) w.push(prevQ(w[w.length - 1]));
      const row = { q };
      for (const m of ['rev', 'op', 'ni']) {
        const vals = w.map(k => Q[k] ? Q[k][m] : null);
        row[m] = vals.every(v => v != null && isFinite(v)) ? eok(vals.reduce((a, b) => a + b, 0)) : null;
      }
      if (row.rev != null || row.op != null || row.ni != null) out.push(row);
    }
    // 첫 TTM 이전 구간 제외 후 최근 n개
    return out.slice(-n);
  }

  const niceCeil = x => { if (!(x > 0)) return 1; const e = Math.pow(10, Math.floor(Math.log10(x))), m = x / e;
    return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10) * e; };
  // 칸 하나의 y범위: 데이터 범위에 맞춘 깔끔한 눈금(T칸). 범위가 아주 좁으면 최소 폭을 둬서 잡음이 과장되지 않게 함.
  function fit(vals, T) {
    T = T || 4;
    const v = vals.filter(x => x != null && isFinite(x)); if (!v.length) return {};
    let lo = Math.min(...v), hi = Math.max(...v);
    const minSpan = Math.max(Math.abs(hi), Math.abs(lo)) * 0.08 || 1;
    if (hi - lo < minSpan) { const m = (hi + lo) / 2; lo = m - minSpan / 2; hi = m + minSpan / 2; }
    const pad = (hi - lo) * 0.06; lo = lo >= 0 ? Math.max(0, lo - pad) : lo - pad; hi = hi <= 0 ? Math.min(0, hi + pad) : hi + pad;
    // 눈금 4~6칸 중 빈 공간이 가장 적은 조합을 고름
    let best = null;
    for (let t = 4; t <= 6; t++) {
      let st = niceCeil((hi - lo) / t), mn = Math.floor(lo / st) * st;
      while (mn + t * st < hi) { st = niceCeil(st * 1.01); mn = Math.floor(lo / st) * st; }
      const k = Math.ceil((hi - mn) / st), r = { min: mn, max: mn + k * st, step: st };
      if (!best || r.max - r.min < best.max - best.min) best = r;
    }
    return best;
  }
  // 주가 요약: 마지막 실적 분기 말 종가, 1년 전 분기 말 대비, 가장 최근 월말 종가
  function pxLine(price, q) {
    const p = qPrice(price, q); if (p == null) return '';
    const p1 = qPrice(price, prevQ(prevQ(prevQ(prevQ(q)))));
    const n = price.months.length - 1, lm = price.months[n], lc = price.close[n];
    const r = (a, b) => b ? ` (${a >= b ? '+' : ''}${((a - b) / b * 100).toFixed(1)}%)` : '';
    return `<br><b>주가</b> ${q} 말 ${fmt(p)}원${p1 ? r(p, p1) : ''}` + (lm && lc != null && lm > q.slice(0, 4) + '-' + String(+q.slice(5) * 3).padStart(2, '0') ? ` · 최근(${lm}) ${fmt(lc)}원${r(lc, p)}` : '') +
      ' <span style="color:var(--ink-3)">(괄호는 각각 1년 전 분기 말, 마지막 실적 분기 말 대비)</span>';
  }
  // 분기 말 월의 월말 종가 (Q1→3월, Q2→6월 …)
  function qPrice(price, q) {
    if (!price || !price.months) return null;
    const m = `${q.slice(0, 4)}-${String(+q.slice(5) * 3).padStart(2, '0')}`;
    const i = price.months.indexOf(m);
    return i >= 0 && price.close[i] != null ? price.close[i] : null;
  }

  function render(canvas, quarterly, opt) {
    opt = opt || {};
    const NI = opt.niLabel || '지배주주순이익';
    const rows = series(quarterly, opt.n || 20);
    const old = charts.get(canvas); if (old) old.destroy();
    if (opt.subEl) {
      if (rows.length < 1) { opt.subEl.textContent = '연속된 4개 분기 실적이 없어 TTM을 계산할 수 없어요.'; }
      else {
        const last = rows[rows.length - 1], yago = rows.find(r => r.q === prevQ(prevQ(prevQ(prevQ(last.q)))));
        opt.subEl.innerHTML = `단위: 억원(주가는 원) · 실적의 각 점은 그 분기까지 최근 4개 분기 합계 · 주가는 그 분기 마지막 달 말 종가(수정주가) · 칸마다 세로축을 그 값의 범위에 맞춰 증감폭이 잘 보이게 했어요(0부터 시작하지 않을 수 있음)` +
          (rows.length < (opt.n || 20) ? ` · 수집된 분기가 적어 ${rows.length}개 시점만 표시` : '') +
          `<br><b>${last.q} TTM</b> 매출액 ${amt(last.rev)}${yago ? chg(last.rev, yago.rev) : ''} · 영업이익 ${amt(last.op)}${yago ? chg(last.op, yago.op) : ''} · ${NI} ${amt(last.ni)}${yago ? chg(last.ni, yago.ni) : ''}` +
          (yago ? ' <span style="color:var(--ink-3)">(괄호는 1년 전 TTM 대비)</span>' : '') + pxLine(opt.price, last.q);
      }
    }
    if (!rows.length) return null;
    const labels = rows.map(r => r.q);
    const px = labels.map(q => qPrice(opt.price, q));
    const hasPx = px.some(v => v != null);
    const s = [1, 2, 7, 4].map(i => css('--s' + i));
    const ink2 = css('--ink-2'), ink3 = css('--ink-3'), grid = css('--line');
    const mobile = window.innerWidth < 640;
    const panels = [
      hasPx && { id: 'yp', key: 'px', label: '주가 (분기 말 월말 종가)', short: '주가', unit: '원', data: px, color: ink2, tf: v => won(v) },
      { id: 'yr', key: 'rev', label: '매출액 TTM', short: '매출액', data: rows.map(r => r.rev), color: s[0], tf: tick },
      { id: 'yo', key: 'op', label: '영업이익 TTM', short: '영업이익', data: rows.map(r => r.op), color: s[1], tf: tick },
      { id: 'yn', key: 'ni', label: `${NI} TTM`, short: NI, data: rows.map(r => r.ni), color: s[2], tf: tick }
    ].filter(Boolean);
    // 높이: 칸당 데스크톱 280px(모바일 230px) → 4칸이면 약 1,200px(기존 340px의 3.5배)
    const wrap = canvas.parentElement;
    if (wrap) wrap.style.height = (panels.length * (mobile ? 230 : 280) + 70) + 'px';
    const scales = { x: { ticks: { color: ink3, maxRotation: 0, autoSkipPadding: 12, font: { size: 11 } }, grid: { color: grid }, border: { color: grid } } };
    // Chart.js는 같은 stack의 축을 '나중에 정의한 것이 위'로 쌓음 → 역순으로 정의해 주가가 맨 위에 오게 함
    const W = mobile ? 50 : 78;
    const won = v => mobile && Math.abs(v) >= 10000 ? (v / 10000).toLocaleString('ko-KR', { maximumFractionDigits: 1 }) + '만' : fmt(v);
    panels.slice().reverse().forEach((p, i) => {
      const r = fit(p.data, 4);
      const crosses = r.min < 0 && r.max > 0;
      scales[p.id] = {
        type: 'linear', position: 'left', stack: 'ttm', stackWeight: 1, min: r.min, max: r.max,
        title: { display: !mobile, text: p.short + (p.unit ? `(${p.unit})` : ''), color: p.color, font: { size: 11.5, weight: '700' } },
        // 칸 경계(맨 위·맨 아래) 눈금 숫자는 옆 칸과 겹치므로 숨김(맨 아래 칸의 바닥 눈금만 표시)
        ticks: { color: p.color, font: { size: mobile ? 10 : 11 }, callback: (v, k, a) => k === a.length - 1 || (k === 0 && p !== panels[panels.length - 1]) ? '' : p.tf(v), stepSize: r.step, maxTicksLimit: 6 },
        afterFit: ax => { ax.width = W; },
        grid: { color: c => crosses && c.tick && c.tick.value === 0 ? ink3 : grid, lineWidth: c => crosses && c.tick && c.tick.value === 0 ? 1.5 : 1 },
        border: { display: true, color: ink3, width: 1 }
      };
    });
    const ch = new Chart(canvas, {
      type: 'line',
      data: {
        labels,
        datasets: panels.map(p => ({ type: 'line', label: p.label, data: p.data, yAxisID: p.id, borderColor: p.color, backgroundColor: p.color,
          borderWidth: 2.4, pointRadius: mobile ? 1.8 : 3, pointHoverRadius: 5, tension: .2, spanGaps: p.key === 'px', _unit: p.unit || '억원' }))
      },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false, position: 'top', labels: { color: ink2, boxWidth: 10, boxHeight: 10, usePointStyle: true, font: { size: 11.5 } } },
          tooltip: { callbacks: { title: x => `${x[0].label} (실적은 최근 4개 분기 합)`, label: x => `${x.dataset.label}: ${fmt(x.raw)}${x.dataset._unit}` } }
        },
        scales
      },
      plugins: [{
        // 칸 사이 구분선 + 칸 왼쪽 위에 이름 표시(한 차트 안의 칸들이 서로 이어져 보이지 않게)
        id: 'ttmPanels',
        afterDatasetsDraw(c) {
          const g = c.ctx, ca = c.chartArea, bg = css('--panel') || '#fff';
          g.save();
          panels.forEach((p, i) => {
            const sc = c.scales[p.id]; if (!sc) return;
            if (i > 0) {
              g.fillStyle = bg; g.fillRect(ca.left, sc.top - 1, ca.right - ca.left, 3);
              g.strokeStyle = ink3; g.lineWidth = 1; g.beginPath(); g.moveTo(ca.left - W, sc.top + 0.5); g.lineTo(ca.right, sc.top + 0.5); g.stroke();
            }
            g.font = `700 ${mobile ? 11 : 12}px system-ui, sans-serif`; g.textBaseline = 'top';
            const t = p.label, tw = g.measureText(t).width;
            g.globalAlpha = .85; g.fillStyle = bg; g.fillRect(ca.left + 4, sc.top + 4, tw + 10, 18); g.globalAlpha = 1;
            g.fillStyle = p.color; g.fillText(t, ca.left + 9, sc.top + 7);
          });
          g.restore();
        }
      }]
    });
    charts.set(canvas, ch);
    return ch;
  }

  window.TTMChart = { render, series };
})();
