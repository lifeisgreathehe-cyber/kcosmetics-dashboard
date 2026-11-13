/* 최근 20개 분기 TTM(최근 4개 분기 합) 꺾은선 — 매출액·영업이익·지배주주순이익. 모든 산업 대시보드 공용.
   사용법: <script src="(상대경로)/shared/ttmchart.js"></script> (Chart.js 4 먼저 로드)
     TTMChart.render(canvasEl, quarterly, {niLabel:'지배주주순이익', subEl, n:20})
       quarterly: companies.json 의 quarterly ({"2025Q3": {rev, op, ni}, ...}, 백만원, 분기 단독)
   - TTM은 연속된 4개 분기가 모두 있을 때만 계산(한 분기라도 빠지면 그 시점은 비움 → 선이 끊김).
   - 매출액은 왼쪽 축, 영업이익·순이익은 오른쪽 보조축. 이익이 적자로 내려가도 두 축의 0선이 같은 높이에 오도록 맞춤.
   - companies.json이 바뀌면(새 분기 공시) 페이지가 다시 그릴 때 자동으로 반영돼요. 따로 생성하는 파일이 없어요. */
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

  // 두 축의 0선이 같은 높이에 오도록, 눈금 수(T)를 공유하는 깔끔한 범위·간격을 계산
  const niceCeil = x => { if (!(x > 0)) return 1; const e = Math.pow(10, Math.floor(Math.log10(x))), m = x / e;
    return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10) * e; };
  // 왼쪽(매출액)과 오른쪽(이익) 축이 같은 눈금 수(T)를 쓰게 해서 격자선이 겹치도록 함.
  // 매출액 축: 변동 폭이 작으면 0부터, 0 근처까지 안 내려가는 큰 회사·급성장 구간은 데이터 범위에 맞춤(이익이 적자여도 매출 축은 음수로 늘리지 않음).
  // 이익 축: 항상 0을 포함하고 0선을 진하게 표시.
  function ranges(L, R, T) {
    T = T || 6;
    const fit = (lo, hi) => {
      if (hi <= lo) hi = lo + 1;
      let st = niceCeil((hi - lo) / T), mn = Math.floor(lo / st) * st;
      while (mn + T * st < hi) { st = niceCeil(st * 1.01); mn = Math.floor(lo / st) * st; }
      return { min: mn, max: mn + T * st, step: st };
    };
    const lmin = Math.min(...L), lmax = Math.max(...L);
    const l = lmin >= 0 && lmin < 0.45 * lmax ? fit(0, lmax) : fit(lmin, lmax);
    const rmin = Math.min(0, ...R), rmax = Math.max(0, ...R);
    const f = rmax - rmin > 0 ? -rmin / (rmax - rmin) : 0;
    let nb = f > 0 ? Math.max(1, Math.round(f * T)) : 0; if (nb >= T) nb = T - 1;
    if (rmax > 0 && nb === T) nb = T - 1;
    const na = T - nb;
    const st = niceCeil(Math.max(rmax / (na || 1), nb ? -rmin / nb : 0) * 1.02);
    return { l, r: { min: -nb * st, max: na * st, step: st } };
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
        opt.subEl.innerHTML = `단위: 억원 · 각 점은 그 분기까지 최근 4개 분기 합계 · 왼쪽 축 매출액, 오른쪽 축 영업이익·${NI}` +
          (rows.length < (opt.n || 20) ? ` · 수집된 분기가 적어 ${rows.length}개 시점만 표시` : '') +
          `<br><b>${last.q} TTM</b> 매출액 ${amt(last.rev)}${yago ? chg(last.rev, yago.rev) : ''} · 영업이익 ${amt(last.op)}${yago ? chg(last.op, yago.op) : ''} · ${NI} ${amt(last.ni)}${yago ? chg(last.ni, yago.ni) : ''}` +
          (yago ? ' <span style="color:var(--ink-3)">(괄호는 1년 전 TTM 대비)</span>' : '');
      }
    }
    if (!rows.length) return null;
    const s = [1, 2, 7].map(i => css('--s' + i));
    const ink2 = css('--ink-2'), ink3 = css('--ink-3'), grid = css('--line');
    const num = a => a.filter(v => v != null);
    const rg = ranges(num(rows.map(r => r.rev)), num(rows.flatMap(r => [r.op, r.ni])));
    const ln = (label, data, color, axis, extra) => Object.assign({ type: 'line', label, data, yAxisID: axis, borderColor: color, backgroundColor: color,
      borderWidth: 2.2, pointRadius: 2.5, pointHoverRadius: 5, tension: .2, spanGaps: false }, extra || {});
    const ch = new Chart(canvas, {
      type: 'line',
      data: {
        labels: rows.map(r => r.q),
        datasets: [
          ln('매출액 (왼쪽 축)', rows.map(r => r.rev), s[0], 'y', { borderWidth: 2.8 }),
          ln('영업이익 (오른쪽 축)', rows.map(r => r.op), s[1], 'y2'),
          ln(`${NI} (오른쪽 축)`, rows.map(r => r.ni), s[2], 'y2', { borderDash: [5, 3] })
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { position: 'bottom', labels: { color: ink2, boxWidth: 10, boxHeight: 10, usePointStyle: true, font: { size: 11.5 } } },
          tooltip: { callbacks: { title: x => `${x[0].label} 기준 최근 4개 분기 합`, label: x => `${x.dataset.label.replace(/ \(.+\)$/, '')}: ${fmt(x.raw)}억원` } }
        },
        scales: {
          x: { ticks: { color: ink3, maxRotation: 0, autoSkipPadding: 12, font: { size: 11 } }, grid: { display: false }, border: { color: grid } },
          y: { position: 'left', min: rg.l.min, max: rg.l.max, title: { display: true, text: '매출액', color: s[0], font: { size: 11, weight: '600' } },
            ticks: { color: s[0], font: { size: 11 }, callback: tick, stepSize: rg.l.step }, grid: { color: grid }, border: { display: false } },
          y2: { position: 'right', min: rg.r.min, max: rg.r.max, title: { display: true, text: `영업이익 · ${NI}`, color: ink2, font: { size: 11, weight: '600' } },
            ticks: { color: ink2, font: { size: 11 }, callback: tick, stepSize: rg.r.step },
            grid: { drawOnChartArea: true, color: c => c.tick && c.tick.value === 0 ? ink3 : 'transparent', lineWidth: c => c.tick && c.tick.value === 0 ? 1 : 0 },
            border: { display: false } }
        }
      }
    });
    charts.set(canvas, ch);
    return ch;
  }

  window.TTMChart = { render, series };
})();
