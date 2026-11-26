/* 산업동향 투자 지표 — 선행·동행 판정 (모든 업종 대시보드 공용)
   데이터: data/trends.json (scripts/trends/build.py 가 매일 만듦)
   사용: <script src="../shared/trends.js"></script> 만 넣으면 산업 동향 탭(#v-industry)의 맨 위 KPI 아래에 스스로 붙는다.
         다른 위치에 두려면 <div id="trend-lead"></div> 를 원하는 곳에 두면 그 안에 그린다.
   색은 페이지 CSS 변수(--ink, --ink-2, --ink-3, --line, --panel, --accent, --up, --down, --s1, --s2)를 쓴다. Chart.js 4 필요. */
(function () {
  const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const f1 = (v, d = 1) => v == null || isNaN(v) ? '–' : (+v).toLocaleString('ko-KR', { maximumFractionDigits: d, minimumFractionDigits: d });
  const sg = (v, d = 1) => v == null || isNaN(v) ? '–' : (v > 0 ? '+' : '') + f1(v, d);
  const ym = m => m ? `${m.slice(2, 4)}.${m.slice(5, 7)}` : '';
  const CLS = {
    lead: ['선행', 'tl-b-lead'], lead0: ['선행·발표 늦음', 'tl-b-lead0'], coin: ['동행', 'tl-b-coin'],
    lag: ['후행', 'tl-b-lag'], weak: ['관계 약함', 'tl-b-weak'], na: ['자료 부족', 'tl-b-weak']
  };
  const STYLE = `
  .tl-card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin:0 0 16px}
  .tl-card h2{font-size:16px;font-weight:600;margin:0 0 2px}
  .tl-sub{font-size:12.5px;color:var(--ink-3);margin:0 0 10px;line-height:1.55}
  .tl-verdict{border-radius:8px;padding:10px 12px;margin:8px 0 12px;font-size:14px;line-height:1.6;background:var(--accent-soft,#f3e7ef)}
  .tl-verdict b{font-weight:700}
  .tl-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
  .tl-chip{font-size:12px;border-radius:999px;padding:2px 9px;border:1px solid var(--line);background:var(--panel)}
  .tl-chip.up{color:var(--up);border-color:var(--up)} .tl-chip.down{color:var(--down);border-color:var(--down)}
  .tl-grid2{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(0,1fr);gap:16px;align-items:start}
  @media (max-width:820px){.tl-grid2{grid-template-columns:minmax(0,1fr)}}
  .tl-chart{position:relative;height:230px}
  .tl-legend{font-size:12px;color:var(--ink-3);line-height:1.6}
  .tl-legend p{margin:0 0 6px}
  .tl-seg{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0}
  .tl-seg button{font:inherit;font-size:12.5px;border:1px solid var(--line);background:var(--panel);color:var(--ink-2);border-radius:999px;padding:3px 10px;cursor:pointer}
  .tl-seg button[aria-pressed="true"]{background:var(--ink);color:var(--panel);border-color:var(--ink)}
  .tl-tbl{overflow-x:auto;-webkit-overflow-scrolling:touch}
  .tl-tbl>table{border-collapse:collapse;width:100%;font-size:13px;min-width:760px;table-layout:fixed}
  .tl-tbl th{font-weight:600;font-size:12px;color:var(--ink-3);text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);white-space:nowrap}
  .tl-tbl td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}
  .tl-tbl tr.tl-row{cursor:pointer} .tl-tbl tr.tl-row:hover td{background:var(--bg)}
  .tl-tbl tr.tl-grp td{font-weight:700;font-size:12.5px;color:var(--ink-2);background:var(--bg);cursor:default}
  .tl-num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
  .tl-name{font-weight:600} .tl-name small{display:block;font-weight:400;color:var(--ink-3);font-size:11.5px}
  .tl-b{display:inline-block;font-size:11.5px;font-weight:600;border-radius:4px;padding:1px 6px;white-space:nowrap}
  .tl-b-lead{background:#1baf7a22;color:var(--up)} .tl-b-lead0{background:#eda10022;color:#a87000}
  .tl-b-coin{background:#2a78d622;color:var(--s1,#2a78d6)} .tl-b-lag{background:#8a879422;color:var(--ink-2)}
  .tl-b-weak{background:transparent;color:var(--ink-3);border:1px dashed var(--line)}
  .tl-st-up{color:var(--up);font-weight:600} .tl-st-down{color:var(--down);font-weight:600} .tl-st-flat{color:var(--ink-3)}
  .tl-detail td{background:var(--bg);padding:12px;white-space:normal}
  .tl-detail td *{white-space:normal}
  .tl-tbl td.tl-name{white-space:normal}
  .tl-dgrid>div{min-width:0}
  .tl-dtext{overflow-wrap:anywhere}
  .tl-dgrid{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(0,1fr);gap:14px}
  @media (max-width:820px){.tl-dgrid{grid-template-columns:minmax(0,1fr)}}
  .tl-dtext{font-size:13px;line-height:1.65;color:var(--ink-2)} .tl-dtext p{margin:0 0 8px} .tl-dtext b{color:var(--ink)}
  .tl-small{font-size:11.5px;color:var(--ink-3)}
  .tl-tg{width:100%;font-size:12px;border-collapse:collapse;margin-top:6px} .tl-tg td{padding:3px 4px;border-bottom:1px solid var(--line)}
  details.tl-method{margin-top:12px;font-size:12.5px;color:var(--ink-2);line-height:1.65} details.tl-method summary{cursor:pointer;font-weight:600}
  `;

  let D = null, filter = 'all', open = null, charts = {};

  function mountPoint() {
    let el = document.getElementById('trend-lead');
    if (el) return el;
    const sec = document.querySelector('[data-viewpanel="industry"]');
    if (!sec) return null;
    el = document.createElement('div');
    el.id = 'trend-lead';
    const k = sec.querySelector('#kpis, .kpis');
    if (k && k.parentNode === sec) k.after(el); else sec.prepend(el);
    return el;
  }

  function stateCell(s) {
    const st = s.now && s.now.state;
    if (!st) return '<span class="tl-st-flat">–</span>';
    const t = { up: '▲ 좋아지는 중', down: '▼ 나빠지는 중', flat: '― 보합' }[st];
    return `<span class="tl-st-${st}">${t}</span>`;
  }

  function relCell(s) {
    const r = s.rel || {};
    const [t, c] = CLS[r.cls] || CLS.na;
    let extra = '';
    if (r.cls === 'lead' || r.cls === 'lead0') extra = ` ${r.k}개월`;
    else if (r.cls === 'lag') extra = ` ${-r.k}개월`;
    return `<span class="tl-b ${c}">${t}${extra}</span>`;
  }

  function condCell(s) {
    const c = (s.rel || {}).cond, cls = (s.rel || {}).cls;
    if (!c || c.up_avg == null || c.dn_avg == null || !['lead', 'lead0', 'coin'].includes(cls)) return '<span class="tl-small">–</span>';
    return `<span class="${c.up_avg >= 0 ? 'tl-st-up' : 'tl-st-down'}">${sg(c.up_avg)}%</span> / <span class="${c.dn_avg >= 0 ? 'tl-st-up' : 'tl-st-down'}">${sg(c.dn_avg)}%</span><br><span class="tl-small">${c.h}개월 뒤</span>`;
  }

  function nowVal(s) {
    const n = s.now || {};
    if (n.tf == null) return '–';
    const unit = s.tf === 'yoy' ? '%' : (s.tf === 'diff12' ? '' : '');
    return `${s.tf === 'level' ? f1(n.tf) : sg(n.tf)}${unit}<br><span class="tl-small">${ym(n.m)} · ${s.tf === 'yoy' ? '전년비' : s.tf === 'diff12' ? '1년 전 대비' : '수준'}</span>`;
  }

  function render() {
    const el = mountPoint();
    if (!el || !D) return;
    const sm = D.summary || {};
    const toneCls = { '우호적': 'up', '부정적': 'down' }[(sm.tone || '').replace('(약함)', '')] || '';
    const leadChips = ['up', 'down', 'flat'].map(k => ((sm.lead || {})[k] || []).map(n => `<span class="tl-chip ${k}">${k === 'up' ? '▲' : k === 'down' ? '▼' : '―'} ${esc(n)}</span>`).join('')).join('');
    const ix = D.index || {};
    const top = (ix.top_share || []).map(t => `${esc(t[0])} ${t[1]}%`).join(' · ');
    const groups = D.groups || [];
    const present = groups.filter(g => D.series.some(s => s.group === g));
    const btn = (k, t) => `<button type="button" data-f="${k}" aria-pressed="${filter === k}">${t}</button>`;
    let rows = '';
    for (const g of present) {
      const ss = D.series.filter(s => s.group === g && (filter === 'all' || (filter === 'lead' ? ['lead', 'lead0'].includes((s.rel || {}).cls) : filter === 'coin' ? (s.rel || {}).cls === 'coin' : g === filter)));
      if (!ss.length) continue;
      rows += `<tr class="tl-grp"><td colspan="7">${esc(g)}</td></tr>`;
      for (const s of ss) {
        if (s.missing) {
          rows += `<tr><td class="tl-name">${esc(s.name)}<small>${esc(s.source || '')}</small></td><td colspan="6" class="tl-small">${esc(s.note || '수집 대기')}</td></tr>`;
          continue;
        }
        const r = s.rel || {};
        rows += `<tr class="tl-row" data-id="${esc(s.id)}" aria-expanded="${open === s.id}">
          <td class="tl-name">${esc(s.name)}<small>${esc(s.source || '')}</small></td>
          <td class="tl-num">${nowVal(s)}</td>
          <td>${stateCell(s)}</td>
          <td>${relCell(s)}</td>
          <td class="tl-num">${r.r == null ? '–' : sg(r.r, 2)}${r.recent_r != null ? `<br><span class="tl-small">최근5년 ${sg(r.recent_r, 2)}</span>` : ''}</td>
          <td class="tl-num">${condCell(s)}</td>
          <td class="tl-small" style="min-width:60px">${open === s.id ? '접기 ▴' : '자세히 ▾'}</td></tr>`;
        if (open === s.id) rows += `<tr class="tl-detail"><td colspan="7">${detail(s)}</td></tr>`;
      }
    }
    el.innerHTML = `<div class="tl-card">
      <h2>투자 판단 지표 — 주가보다 먼저 움직이나?</h2>
      <p class="tl-sub">${esc(D.intro || '')} 각 지표의 전년비 흐름을 <b>${esc(ix.name || '업종 지수')}</b> 주가 전년비와 −12~+12개월 시차로 맞춰 봤어요. 행을 누르면 그래프와 해석이 열려요.</p>
      <div class="tl-verdict ${toneCls}"><b>지금 신호:</b> ${esc(sm.verdict || '')}${leadChips ? `<div class="tl-chips">${leadChips}</div>` : ''}</div>
      <div class="tl-grid2">
        <div><div class="tl-chart"><canvas id="tl-c-idx" role="img" aria-label="업종 주가지수와 코스피 비교"></canvas></div>
          <div class="tl-small">업종 지수: 대시보드 ${ix.n_companies || ''}개 상장사 월말 수정주가를 시가총액(현재 주식 수 기준)으로 가중한 값. 비중 상위: ${top}</div></div>
        <div class="tl-legend">
          <p><span class="tl-b tl-b-lead">선행 n개월</span> 지표가 주가보다 n개월 먼저 움직였어요. 발표 시차를 빼고도 1개월 이상 앞서야 '선행'이에요.</p>
          <p><span class="tl-b tl-b-lead0">선행·발표 늦음</span> 앞서긴 하지만 통계 발표가 늦어 실제로는 주가와 같은 때 알게 돼요.</p>
          <p><span class="tl-b tl-b-coin">동행</span> 주가와 같은 달(±1개월)에 움직여요. 주가 흐름이 업황으로 뒷받침되는지 확인용.</p>
          <p><span class="tl-b tl-b-lag">후행 n개월</span> 주가가 n개월 먼저 움직였어요. 시장이 이미 반영한 숫자예요.</p>
          <p><span class="tl-b tl-b-weak">관계 약함</span> 자기상관을 감안하면 우연일 수 있는 수준이에요.</p>
          <p>상관: −1~+1, 마이너스는 반대 방향. 개선 후/악화 후: 지표가 3개월 사이 주가에 유리한 쪽으로 움직인 달 이후 업종 평균 수익률 vs 반대의 경우.</p>
        </div>
      </div>
      <div class="tl-seg" role="group" aria-label="지표 거르기">${btn('all', '전체')}${btn('lead', '선행만')}${btn('coin', '동행만')}${present.map(g => btn(g, g)).join('')}</div>
      <div class="tl-tbl"><table><colgroup><col style="width:27%"><col style="width:12%"><col style="width:13%"><col style="width:15%"><col style="width:10%"><col style="width:14%"><col style="width:9%"></colgroup><thead><tr><th>지표</th><th class="tl-num">최근 값</th><th>최근 3개월</th><th>주가와의 관계</th><th class="tl-num">상관</th><th class="tl-num">개선 후 / 악화 후</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>
      <details class="tl-method"><summary>계산 방법과 한계</summary>
        <p>① 업종 지수: 대시보드 상장사 월말 수정주가(네이버 금융, 2000년~ 가능한 만큼)를 그 달 시가총액(현재 주식 수 × 그 달 주가)으로 가중해 연결했어요. 중소형 동일가중 지수·업종 그룹별·대형주별로도 같은 계산을 해서 '이 지표에 가장 민감한 곳'을 보여줘요.</p>
        <p>② 변환: 계절성이 있는 물량·금액·가격은 전년 같은 달 대비 %(잡음이 큰 지표는 3개월 평균), 금리·비율은 1년 전과의 차이, 순환변동치·심리지수·순환 지표는 수준 그대로 써요. 주가는 업종 지수의 전년비예요.</p>
        <p>③ 시차 상관: 지표(t)와 주가(t+k)의 상관을 k=−12~+12개월에서 계산해 가장 강한 시차를 골랐어요(기대 방향이 정해진 지표는 그 방향에서). 전년비는 이웃한 달끼리 겹쳐 실제 독립 관측이 적으므로, 자기상관을 감안한 유효 표본 수로 95% 유의 기준을 계산했고 |상관| 0.3 미만이면 '관계 약함'으로 뒀어요.</p>
        <p>④ 발표 시차: KOSIS 산업활동·서비스업 약 1개월, 수출입물가·관세청 약 0.5개월, 시장 가격·심리지수 0개월로 보고 '실제로 쓸 수 있는 앞섬'을 따로 표시해요.</p>
        <p>⑤ 한계: 과거 표본 안에서 찾은 관계(사후 적합)라 앞으로도 같다는 보장은 없어요. '최근 5년' 상관이 전체와 크게 다르면 관계가 바뀌는 중이라는 신호예요. 코로나처럼 전년비가 극단적으로 왜곡된 기간은 업종별로 계산에서 뺐어요${D.exclude_window ? `(이 업종: ${D.exclude_window.join('~')})` : ''}.</p>
        <p class="tl-small">갱신: ${esc(D.updated || '')} · 지표 원자료는 각 출처에서 매일·매월 자동 수집(GitHub Actions)</p>
      </details></div>`;
    el.querySelectorAll('.tl-seg button').forEach(b => b.onclick = () => { filter = b.dataset.f; open = null; render(); });
    el.querySelectorAll('tr.tl-row').forEach(tr => tr.onclick = () => { open = open === tr.dataset.id ? null : tr.dataset.id; render(); });
    drawIndex();
    if (open) drawDetail(D.series.find(s => s.id === open));
  }

  function detail(s) {
    const r = s.rel || {};
    const others = (s.best_others || []).map(t => `<tr><td>${esc(t.name)}</td><td class="tl-num">${t.k > 0 ? `지표가 ${t.k}개월 먼저` : t.k < 0 ? `주가가 ${-t.k}개월 먼저` : '같은 달'}</td><td class="tl-num">${sg(t.r, 2)}</td></tr>`).join('');
    const n = s.now || {};
    return `<div class="tl-dgrid">
      <div><div class="tl-chart" style="height:250px"><canvas id="tl-c-d" role="img" aria-label="${esc(s.name)}와 업종 주가 비교"></canvas></div>
        <div class="tl-small">파란 선: ${esc(s.name)} (${esc(s.tf_label)}${s.ma > 1 ? `, ${s.ma}개월 평균` : ''}) · 주황 선: 업종 지수 전년비${r.k ? ` (${r.k > 0 ? r.k + '개월 뒤 값을 당겨 겹침' : -r.k + '개월 앞 값을 밀어 겹침'})` : ''}</div>
        <div class="tl-chart" style="height:150px;margin-top:10px"><canvas id="tl-c-x" role="img" aria-label="시차별 상관"></canvas></div>
        <div class="tl-small">시차별 상관: 오른쪽(+)이 높으면 지표가 먼저, 왼쪽(−)이 높으면 주가가 먼저 움직였다는 뜻이에요.</div></div>
      <div class="tl-dtext">
        <p><b>왜 보나</b> ${esc(s.why || '')}</p>
        <p><b>읽는 법</b> ${esc(s.read || '')}</p>
        <p><b>주가와의 관계</b> ${esc(s.text || '')}</p>
        <p><b>지금</b> ${n.m ? `${ym(n.m)} 기준 원자료 ${f1(n.v, 1)} ${esc(s.unit || '')}, 변환값 ${s.tf === 'level' ? f1(n.tf) : sg(n.tf)}${s.tf === 'yoy' ? '%' : ''} (과거 분포에서 아래부터 ${n.pct}% 지점). 3개월 전보다 ${n.state === 'up' ? '주가에 유리한 쪽으로 움직였어요' : n.state === 'down' ? '주가에 불리한 쪽으로 움직였어요' : '큰 변화가 없어요'}.` : '–'}</p>
        <p class="tl-small">표본 ${r.n || '–'}개월 · 유효 표본 ${r.neff || '–'} · 유의 기준 |상관| ≥ ${r.thr != null ? f1(Math.max(r.thr, 0.3), 2) : '–'} · 발표 시차 약 ${s.pub_lag}개월</p>
        ${others ? `<p style="margin-top:8px"><b>더 민감하게 반응한 곳</b></p><table class="tl-tg">${others}</table>` : ''}
        <p class="tl-small" style="margin-top:8px">출처: ${s.url ? `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.source)}</a>` : esc(s.source)}</p>
      </div></div>`;
  }

  function kill(id) { if (charts[id]) { charts[id].destroy(); delete charts[id]; } }

  function drawIndex() {
    const cv = document.getElementById('tl-c-idx');
    if (!cv || !window.Chart) return;
    kill('idx');
    const ix = D.index, ms = ix.months;
    let i0 = ms.findIndex((m, i) => ix.cap[i] != null && ix.kospi[i] != null);
    if (i0 < 0) i0 = 0;
    const norm = arr => arr.map((v, i) => i < i0 || v == null || arr[i0] == null ? null : v / arr[i0] * 100);
    charts.idx = new Chart(cv, {
      type: 'line',
      data: { labels: ms.slice(i0), datasets: [
        { label: ix.name, data: norm(ix.cap).slice(i0), borderColor: css('--s2') || '#eb6834', borderWidth: 2, pointRadius: 0 },
        { label: '코스피', data: norm(ix.kospi).slice(i0), borderColor: css('--ink-3') || '#888', borderWidth: 1.2, pointRadius: 0, borderDash: [4, 3] }
      ] },
      options: { maintainAspectRatio: false, animation: false, interaction: { mode: 'index', intersect: false },
        plugins: { legend: { labels: { boxWidth: 12, color: css('--ink-2') } }, tooltip: { callbacks: { label: c => `${c.dataset.label}: ${f1(c.parsed.y, 0)}` } } },
        scales: { x: { ticks: { maxTicksLimit: 8, color: css('--ink-3') }, grid: { display: false } },
                  y: { type: 'logarithmic', title: { display: true, text: `${ms[i0]} = 100 (로그)`, color: css('--ink-3') }, ticks: { color: css('--ink-3'), callback: v => f1(v, 0) }, grid: { color: css('--line') } } } }
    });
  }

  function drawDetail(s) {
    if (!s || !window.Chart) return;
    kill('d'); kill('x');
    const ix = D.index, iy = {};
    ix.months.forEach((m, i) => { if (ix.yoy[i] != null) iy[m] = ix.yoy[i]; });
    const k = (s.rel || {}).k || 0;
    const sh = (m, n) => { let y = +m.slice(0, 4), mo = +m.slice(5, 7) - 1 + n; y += Math.floor(mo / 12); mo = ((mo % 12) + 12) % 12; return `${y}-${String(mo + 1).padStart(2, '0')}`; };
    const ms = s.months.filter((m, i) => s.x[i] != null);
    const xv = s.months.reduce((o, m, i) => (o[m] = s.x[i], o), {});
    const c1 = css('--s1') || '#2a78d6', c2 = css('--s2') || '#eb6834';
    charts.d = new Chart(document.getElementById('tl-c-d'), {
      type: 'line',
      data: { labels: ms, datasets: [
        { label: s.name, data: ms.map(m => xv[m]), borderColor: c1, borderWidth: 1.8, pointRadius: 0, yAxisID: 'y' },
        { label: `업종 주가 전년비${k ? (k > 0 ? ` (${k}개월 뒤)` : ` (${-k}개월 앞)`) : ''}`, data: ms.map(m => iy[sh(m, k)] ?? null), borderColor: c2, borderWidth: 1.5, pointRadius: 0, yAxisID: 'y2' }
      ] },
      options: { maintainAspectRatio: false, animation: false, interaction: { mode: 'index', intersect: false },
        plugins: { legend: { labels: { boxWidth: 12, color: css('--ink-2') } } },
        scales: { x: { ticks: { maxTicksLimit: 8, color: css('--ink-3') }, grid: { display: false } },
                  y: { position: 'left', ticks: { color: c1 }, grid: { color: css('--line') }, title: { display: true, text: s.tf_label, color: c1 } },
                  y2: { position: 'right', ticks: { color: c2, callback: v => v + '%' }, grid: { display: false } } } }
    });
    const prof = (s.rel || {}).prof || [];
    if (prof.length) charts.x = new Chart(document.getElementById('tl-c-x'), {
      type: 'bar',
      data: { labels: prof.map(p => (p[0] > 0 ? '+' : '') + p[0]), datasets: [{ data: prof.map(p => p[1]),
        backgroundColor: prof.map(p => p[0] === k ? c2 : (p[1] >= 0 ? c1 + '99' : (css('--down') || '#c0392b') + '99')) }] },
      options: { maintainAspectRatio: false, animation: false, plugins: { legend: { display: false }, tooltip: { callbacks: { title: c => `시차 ${c[0].label}개월`, label: c => `상관 ${sg(c.parsed.y, 2)}` } } },
        scales: { x: { ticks: { color: css('--ink-3'), maxRotation: 0, autoSkip: true }, grid: { display: false } }, y: { min: -1, max: 1, ticks: { color: css('--ink-3') }, grid: { color: css('--line') } } } }
    });
  }

  async function load() {
    try {
      const r = await fetch('data/trends.json', { cache: 'no-cache' });
      if (!r.ok) return;
      D = await r.json();
    } catch (e) { return; }
    if (!document.getElementById('tl-style')) {
      const st = document.createElement('style'); st.id = 'tl-style'; st.textContent = STYLE; document.head.appendChild(st);
    }
    render();
  }
  window.TrendLead = { reload: load };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', load); else load();
})();
