/* 실적 한눈에 보기 — 실적과 주가가 같은 방향인지, 엇갈리는지(기회·주의)를 한눈에. 모든 산업 대시보드 공용.
   사용법: <script src="(상대경로)/shared/finchart.js"></script> (Chart.js 4 먼저 로드)
     const h = FinChart.render(el, {
       price: {months:["2016-12",...], close:[...]},   // stock_hist.json series[code] (없으면 실적만)
       quarterly: {"2025Q3": {rev, gp, op, ni}, ...},   // companies.json quarterly (백만원, 분기 단독)
       niLabel: "지배주주순이익",                        // 선택
       source: "네이버 금융 월봉(수정주가, 월말 종가)",    // 선택: 출처 표기
       code: "090430", turnsUrl: "data/turns/"           // 선택: 변곡점 해설(scripts/turns/build.py 가 만든 <code>.json)
     });  h.destroy() 로 정리.
     FinChart.annual(tableWrapEl, code, "data/turns/")   // 선택: 연간 실적표 아래에 '매출·이익이 크게 바뀐 해의 이유'
   변곡점 해설: 띠(엇갈린 분기)와 큰 고점·저점(번호 원)에 마우스를 올리면 요약, 클릭하면 차트 아래 목록에서 근거(이익×PER, 밸류에이션 위치,
   시장·업종 대비, 실적 발표 반응, 사후 1년, 거시, 사건 연표, 뉴스)를 펼쳐 보여 줘요.
   구성: ① 방향 신호 카드: 최근 1년 이익(4분기 합)과 주가가 같은 방향인지, 엇갈리는지 + 이 종목의 과거 같은 신호 뒤 1년 주가
         ② 변화율 타일(주가·매출·영업이익·순이익)
         ③ 나란히 보기(기본): 주가·매출·영업이익·순이익을 세로로 긴 패널에 같은 시간축으로 쌓음. y축은 각 계열 범위에 맞춤.
            엇갈린 분기는 모든 패널 배경에 색(초록=실적↑주가↓ 기회 후보, 빨강=실적↓주가↑ 주의)
            겹쳐 보기: 첫 분기=100 지수(로그)로 한 축에 겹침
         ④ 표로 보기
   색은 페이지 CSS 변수(--ink, --ink-2, --ink-3, --line, --panel, --s1~s3, --up, --down)를 읽는다. */
(function () {
  const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const RANGES = [['12', '3년'], ['20', '5년'], ['40', '10년'], ['all', '전체']];
  const ST = { range: '20', view: 'stack', mode: 'ttm' };  // 회사를 바꿔도 유지
  const HIDDEN = new Set();
  const YW = 52;                // 모든 패널 y축 폭 동일 → 세로 정렬
  const TH_E = 0.05, TH_P = 0.10; // 방향 판정 문턱: 이익 ±5%, 주가 ±10%
  const TC = {};                // 변곡점 해설 파일 캐시
  const loadTurns = url => TC[url] || (TC[url] = fetch(url).then(r => r.ok ? r.json() : null).catch(() => null));
  const esc = t => String(t == null ? '' : t).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const TF = { f: 'all' };      // 해설 목록 필터(회사를 바꿔도 유지)

  const fmt = v => v == null || !isFinite(v) ? '–' : Math.round(v).toLocaleString('ko-KR');
  const eok = v => {
    if (v == null || !isFinite(v)) return '–';
    const a = Math.abs(v);
    if (a >= 10000) return (v / 10000).toLocaleString('ko-KR', { maximumFractionDigits: a >= 100000 ? 1 : 2 }) + '조';
    return fmt(v) + '억';
  };
  const tickEok = v => { const a = Math.abs(v); return a >= 10000 ? (v / 10000).toLocaleString('ko-KR', { maximumFractionDigits: 2 }) + '조' : fmt(v); };
  const pct = r => { if (r == null || !isFinite(r)) return '–'; const x = r * 100; return (x >= 0 ? '+' : '') + (Math.abs(x) >= 100 ? Math.round(x).toLocaleString('ko-KR') : x.toFixed(1)) + '%'; };
  const wrap = (t, w) => { const out = []; let line = ''; String(t).split(' ').forEach(x => { if ((line + ' ' + x).trim().length > w && line) { out.push(line); line = x; } else line = (line + ' ' + x).trim(); }); if (line) out.push(line); return out.slice(0, 6); };
  const qn = k => +k.slice(0, 4) * 4 + (+k.slice(5) - 1);
  const qk = n => `${Math.floor(n / 4)}Q${n % 4 + 1}`;
  const m2q = m => `${m.slice(0, 4)}Q${Math.ceil(+m.slice(5, 7) / 3)}`;
  const chg = (a, b) => a == null || b == null ? null : (a > 0 && b > 0 ? b / a - 1 : (b - a) / Math.max(Math.abs(a), Math.abs(b), 1e-9));

  function injectStyle() {
    if (document.getElementById('fc-style')) return;
    const s = document.createElement('style'); s.id = 'fc-style';
    s.textContent = `
.fc-ctl{display:flex;gap:8px 14px;flex-wrap:wrap;justify-content:flex-end;margin:0 0 10px}
.fc-segs{display:flex;gap:4px;flex-wrap:wrap}.fc-segs[hidden]{display:none}
.fc-sig{border:1px solid var(--line);border-left:4px solid var(--ink-3);border-radius:8px;padding:10px 14px;margin:0 0 10px;background:var(--panel)}
.fc-sig.opp{border-left-color:var(--up)}.fc-sig.warn{border-left-color:var(--down)}
.fc-sig .h{display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:15px;font-weight:600;color:var(--ink);margin:0 0 4px}
.fc-sig .chip{font-size:11.5px;font-weight:600;padding:1px 8px;border-radius:99px;border:1px solid currentColor;color:var(--ink-2)}
.fc-sig.opp .chip{color:var(--up)}.fc-sig.warn .chip{color:var(--down)}
.fc-sig p{margin:2px 0;font-size:13px;color:var(--ink-2);line-height:1.6}.fc-sig b{color:var(--ink)}
.fc-sig .sub{font-size:12px;color:var(--ink-3)}
.fc-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin:0 0 12px}
.fc-kpi{border:1px solid var(--line);border-radius:8px;padding:8px 10px;background:var(--panel)}
.fc-kpi .l{font-size:12px;color:var(--ink-2);display:flex;align-items:center;gap:6px}
.fc-kpi .sw{display:inline-block;width:14px;height:3px;border-radius:2px}
.fc-kpi .v{font-family:var(--font-mono,ui-monospace,monospace);font-size:20px;font-weight:500;font-variant-numeric:tabular-nums;margin:2px 0 0;color:var(--ink)}
.fc-kpi .v small{font-size:12px;color:var(--ink-3);margin-left:4px}
.fc-kpi .s{font-size:11.5px;color:var(--ink-3);line-height:1.45}
.fc-key{display:flex;flex-wrap:wrap;gap:4px 16px;font-size:12px;color:var(--ink-2);margin:0 0 2px}
.fc-key i{display:inline-block;width:12px;height:12px;border-radius:2px;vertical-align:-2px;margin-right:5px}
.fc-key .n{color:var(--ink-3)}
.fc-leg{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:12.5px;color:var(--ink-2);margin:4px 0}
.fc-leg button{all:unset;cursor:pointer;display:inline-flex;align-items:center;gap:6px;padding:2px 0}
.fc-leg button[aria-pressed="false"]{opacity:.4}
.fc-leg button:focus-visible{outline:2px solid var(--ink-3);outline-offset:2px;border-radius:3px}
.fc-leg .sw{display:inline-block;width:16px;height:3px;border-radius:2px}
.fc-pt{display:flex;justify-content:space-between;align-items:baseline;gap:8px;flex-wrap:wrap;margin:14px 0 2px;font-size:12.5px}
.fc-pt .t{font-weight:600;color:var(--ink-2)}.fc-pt .t span{font-weight:400;color:var(--ink-3)}
.fc-pt .v{font-family:var(--font-mono,ui-monospace,monospace);font-size:12.5px;color:var(--ink)}
.fc-pt .v .up{color:var(--up)}.fc-pt .v .down{color:var(--down)}
.fc-c{position:relative}
.fc-note{font-size:11.5px;color:var(--ink-3);margin:6px 0 0;line-height:1.55}
.fc-tbl{margin-top:10px;font-size:12.5px}
.fc-tbl summary{cursor:pointer;color:var(--ink-2)}
.fc-tbl .w{overflow-x:auto;max-height:360px;margin-top:6px}
.fc-tbl table{border-collapse:collapse;width:100%;min-width:680px}
.fc-tbl th,.fc-tbl td{padding:4px 8px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
.fc-tbl th{font-weight:500;color:var(--ink-2);font-size:11.5px;position:sticky;top:0;background:var(--panel)}
.fc-tbl td{font-family:var(--font-mono,ui-monospace,monospace);font-size:12px}
.fc-tbl td:first-child,.fc-tbl th:first-child{text-align:left}
.fc-turns{margin:16px 0 0;border-top:1px solid var(--line);padding-top:12px}
.fc-turns .th{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;margin:0 0 6px}
.fc-turns h4,.fc-yn h4{margin:0;font-size:15px;color:var(--ink)}
.fc-turns .lead,.fc-yn .lead{font-size:12.5px;color:var(--ink-2);margin:0 0 8px;line-height:1.6}
.fc-tc{border:1px solid var(--line);border-left:4px solid var(--ink-3);border-radius:8px;margin:0 0 8px;background:var(--panel)}
.fc-tc.t-up,.fc-tc.t-opp{border-left-color:var(--up)}.fc-tc.t-down,.fc-tc.t-warn{border-left-color:var(--down)}
.fc-tc.sel{box-shadow:0 0 0 2px var(--ink-3)}
.fc-tc summary{cursor:pointer;list-style:none;padding:9px 12px;display:grid;grid-template-columns:auto 1fr;gap:2px 10px;align-items:start}
.fc-tc summary::-webkit-details-marker{display:none}
.fc-tc .no{grid-row:span 4;align-self:start;display:inline-flex;align-items:center;justify-content:center;min-width:22px;height:22px;border-radius:11px;font-size:12px;font-weight:700;color:#fff;background:var(--ink-3)}
.fc-tc.t-up .no,.fc-tc.t-opp .no{background:var(--up)}.fc-tc.t-down .no,.fc-tc.t-warn .no{background:var(--down)}
.fc-tc .tt{font-weight:600;font-size:13.5px;color:var(--ink)}
.fc-tc .hd{font-size:12.5px;color:var(--ink-2);font-family:var(--font-mono,ui-monospace,monospace)}
.fc-tc .why{font-size:13px;color:var(--ink);line-height:1.55}.fc-tc .why b{color:var(--ink-2);font-weight:600}
.fc-tc .bd,.fc-yn .bd{padding:0 12px 10px 44px}
.fc-tc ul,.fc-yn ul{margin:4px 0 6px;padding:0;list-style:none}
.fc-tc li,.fc-yn li{font-size:12.8px;color:var(--ink-2);line-height:1.6;margin:0 0 5px}
.fc-tag{display:inline-block;font-size:11px;font-weight:600;color:var(--ink-2);border:1px solid var(--line);border-radius:99px;padding:0 7px;margin-right:6px;white-space:nowrap}
.fc-tag.unc{color:var(--down);border-color:currentColor}
.fc-tc .look,.fc-yn .look{font-size:12.5px;color:var(--ink);margin:4px 0 0;line-height:1.6}
.fc-tc a,.fc-yn a{color:var(--ink-2)}
.fc-tc .chips{grid-column:2;display:flex;flex-wrap:wrap;gap:4px;margin-top:4px}
.fc-chip{font-size:11px;line-height:18px;padding:0 7px;border-radius:99px;border:1px solid var(--line);color:var(--ink-3);white-space:nowrap}
.fc-chip.c-p{color:var(--up);border-color:currentColor}.fc-chip.c-m{color:var(--down);border-color:currentColor}.fc-chip.dr{font-weight:700}
.fc-cats{display:grid;gap:6px;margin:4px 0 6px}
.fc-cat{border-left:3px solid var(--line);padding:2px 0 2px 10px}
.fc-cat.c-p{border-left-color:var(--up)}.fc-cat.c-m{border-left-color:var(--down)}
.fc-cat .ch{display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 8px}
.fc-cat .nm{font-weight:700;font-size:13px;color:var(--ink)}.fc-cat .sg{font-weight:700;font-size:13px}
.fc-cat.c-p .sg{color:var(--up)}.fc-cat.c-m .sg{color:var(--down)}.fc-cat .lv{font-size:10px;letter-spacing:1px;color:var(--ink-3)}
.fc-cat .br{font-size:12.5px;color:var(--ink-2)}
.fc-cat p{margin:2px 0 0;font-size:12.8px;color:var(--ink);line-height:1.6}
.fc-cat.none p{color:var(--ink-3)}.fc-cat.none .nm{color:var(--ink-3);font-weight:600}
.fc-cat ul{margin:3px 0 2px}.fc-cat li{font-size:12.3px}
.fc-yn{margin:12px 0 0}
.fc-yn details{border:1px solid var(--line);border-radius:8px;margin:0 0 6px;background:var(--panel)}
.fc-yn summary{cursor:pointer;padding:8px 12px;font-size:13px;color:var(--ink);line-height:1.55}
.fc-yn summary .y{font-weight:700;margin-right:8px}.fc-yn summary .hd{font-family:var(--font-mono,ui-monospace,monospace);font-size:12.5px;color:var(--ink-2)}
.fc-yn summary .why{display:block;color:var(--ink-2);font-size:12.5px}
.fc-yn .bd{padding-left:12px}
.fc-ydot{all:unset;cursor:pointer;display:inline-block;margin-left:4px;width:15px;height:15px;line-height:15px;text-align:center;border-radius:8px;font-size:10px;font-weight:700;color:#fff;background:var(--ink-3);vertical-align:1px}
.fc-ydot:focus-visible{outline:2px solid var(--ink-3);outline-offset:2px}
@media (max-width:600px){.fc-kpi .v{font-size:17px}.fc-ctl{justify-content:flex-start}.fc-tc .bd{padding-left:12px}}`;
    document.head.appendChild(s);
  }

  function render(el, o) {
    injectStyle();
    const charts = [];
    el._fcO = o;
    build(el, o, charts);
    if (o.code && o.turnsUrl && !o._turns) {
      loadTurns(o.turnsUrl + o.code + '.json').then(t => {
        if (!t || el._fcO !== o) return;
        o._turns = t; charts.forEach(c => c.destroy()); charts.length = 0; build(el, o, charts);
      });
    }
    return { destroy() { charts.forEach(c => c.destroy()); charts.length = 0; } };
  }

  function build(el, o, charts) {
    const Q = o.quarterly || {};
    const NI = o.niLabel || '순이익';
    const P = o.price && o.price.months && o.price.months.length ? o.price : null;

    // ---- 데이터 정리 (실적은 억원)
    const qkeys = Object.keys(Q).filter(k => /^\d{4}Q[1-4]$/.test(k)).sort();
    const val = (n, f) => { const r = Q[qk(n)]; return r && r[f] != null ? r[f] / 100 : null; };
    const ttm = (n, f) => { let s = 0; for (let i = 0; i < 4; i++) { const v = val(n - i, f); if (v == null) return null; s += v; } return s; };
    const ser = (n, f) => ST.mode === 'q' ? val(n, f) : ttm(n, f);
    const pq = {};   // 분기 → 그 분기 마지막 달 종가
    const PM = [];   // 월별 종가
    if (P) P.months.forEach((m, i) => { const v = P.close[i]; if (v > 0) { const n = qn(m2q(m)); pq[n] = { v, m }; PM.push({ n, mo: +m.slice(5, 7), v, m }); } });
    const pqn = Object.keys(pq).map(Number), qnums = qkeys.map(qn);
    if (!qnums.length && !pqn.length) { el.innerHTML = '<p class="sub">표시할 주가·실적 데이터가 아직 없어요.</p>'; return; }
    const ttmStart = qnums.filter(n => ttm(n, 'rev') != null);
    const end = Math.max(...qnums, ...pqn);
    let start;
    if (ttmStart.length && pqn.length) start = ttmStart.find(n => pq[n]) ?? Math.max(ttmStart[0], Math.min(...pqn));
    else if (ttmStart.length) start = ttmStart[0];
    else if (qnums.length && pqn.length) start = Math.max(qnums[0], Math.min(...pqn));
    else start = Math.min(...(qnums.length ? qnums : pqn));
    const total = end - start + 1;
    const opts = RANGES.filter(([k]) => k === 'all' || +k < total);
    if (!opts.some(([k]) => k === ST.range)) ST.range = 'all';
    const n0 = ST.range === 'all' ? start : Math.max(start, end - +ST.range + 1);
    const axis = []; for (let n = n0; n <= end; n++) axis.push(n);
    const labels = axis.map(qk);
    const X = n => n - n0;                               // 분기 → x
    const XM = p => X(p.n) + ((p.mo - 1) % 3 - 2) / 3;   // 월 → x (분기 말 달 = 정수)

    const colors = { px: css('--ink') || '#222', rev: css('--s1') || '#2a78d6', op: css('--s2') || '#eb6834', ni: css('--s3') || '#1baf7a' };
    const names = { px: '주가', rev: '매출액', op: '영업이익', ni: NI };
    const fields = ['rev', 'op', 'ni'].filter(f => qkeys.some(k => Q[k][f] != null));

    // ---- 방향 신호: 직전 1년 대비 이익(4분기 합)과 주가(분기 말) 변화
    const ek = ['op', 'ni', 'rev'].find(f => ttmStart.some(n => ttm(n, f) != null));
    const sigAt = n => {
      if (!ek) return null;
      const e1 = ttm(n, ek), e0 = ttm(n - 4, ek), p1 = pq[n] && pq[n].v, p0 = pq[n - 4] && pq[n - 4].v;
      if (e1 == null || e0 == null || !p1 || !p0) return null;
      const de = chg(e0, e1), dp = p1 / p0 - 1;
      const eu = de > TH_E ? 1 : de < -TH_E ? -1 : 0, pu = dp > TH_P ? 1 : dp < -TH_P ? -1 : 0;
      const t = eu > 0 && pu < 0 ? 'opp' : eu < 0 && pu > 0 ? 'warn' : eu && pu && eu === pu ? (eu > 0 ? 'up' : 'down') : 'flat';
      return { t, de, dp, e0, e1, p0, p1 };
    };
    const sig = axis.map(sigAt);
    // 이 종목 전체 이력에서 같은 신호 뒤 1년 주가
    const after = t => {
      const r = [];
      for (const n of qnums) { const s = sigAt(n); if (s && s.t === t && pq[n + 4]) r.push(pq[n + 4].v / pq[n].v - 1); }
      return r;
    };
    let li = -1; sig.forEach((s, i) => { if (s) li = i; });

    // ---- 변곡점 해설(있으면): 보이는 기간 안의 것만, 날짜순 번호
    const XMm = m => X(qn(m2q(m))) + ((+m.slice(5, 7) - 1) % 3 - 2) / 3;
    const TE = ((o._turns && o._turns.events) || []).filter(e => e.kind === 'band' ? qn(e.q1) >= n0 && qn(e.q0) <= end : qn(m2q(e.m1)) >= n0)
      .map((e, i) => Object.assign({}, e, { no: i + 1 }));
    const span = e => e.kind === 'band' ? [X(qn(e.q0)) - 0.5, X(qn(e.q1)) + 0.5] : [Math.max(-0.5, XMm(e.m0)), XMm(e.m1)];
    const pxAt = {}; PM.forEach(p => { pxAt[p.m] = p.v; });
    const evAt = xv => {  // x 위치에 걸친 해설: 띠 우선, 없으면 가장 짧은 큰 흐름 구간
      const b = TE.filter(e => e.kind === 'band' && xv >= span(e)[0] && xv <= span(e)[1]);
      if (b.length) return b;
      return TE.filter(e => e.kind === 'leg' && xv >= span(e)[0] && xv <= span(e)[1]).sort((a, c) => (span(a)[1] - span(a)[0]) - (span(c)[1] - span(c)[0])).slice(0, 1);
    };
    const pivotNear = xv => TE.find(e => e.kind === 'leg' && e.pivot && Math.abs(XMm(e.m0) - xv) <= 0.5);

    let sigHtml = '';
    if (li >= 0) {
      const s = sig[li], n = axis[li], en = ek === 'op' ? '영업이익' : ek === 'ni' ? NI : '매출';
      const T = {
        opp: ['기회 후보', '실적은 좋아지는데 주가는 내렸어요', '이익이 늘었는데 주가가 빠졌다면 시장이 실적을 아직 덜 반영했거나, 이익이 오래가지 못할 거라고(일회성 이익, 사이클 고점) 보고 있다는 뜻이에요. 리뷰와 적정주가에서 이익의 지속성을 확인해 보세요.'],
        warn: ['주의', '실적은 나빠지는데 주가는 올랐어요', '이익이 줄었는데 주가가 올랐다면 앞으로의 회복이나 새 성장 기대가 먼저 반영된 상태예요. 기대만큼 실적이 따라오지 않으면 주가가 되돌아갈 수 있어요.'],
        up: ['같은 방향', '실적과 주가가 함께 오르고 있어요', '주가 상승을 실적이 뒷받침하고 있어요. 이익보다 주가가 훨씬 빨리 오르면 기대가 앞서가는 것이니 변화율 차이를 함께 보세요.'],
        down: ['같은 방향', '실적과 주가가 함께 내리고 있어요', '실적 둔화가 주가에 반영되는 중이에요. 실적이 바닥을 찍는 신호가 먼저 나오는지 지켜볼 구간이에요.'],
        flat: ['뚜렷한 차이 없음', '실적과 주가 모두 큰 방향 차이가 없어요', `이익 ±${TH_E * 100}%, 주가 ±${TH_P * 100}% 안에서 움직여 방향을 판단하기 어려워요.`]
      }[s.t];
      const hist = (s.t === 'opp' || s.t === 'warn') ? after(s.t) : [];
      const histTxt = hist.length ? `이 종목에서 같은 신호가 나왔던 ${hist.length}개 분기 뒤 1년 주가는 평균 <b>${pct(hist.reduce((a, b) => a + b, 0) / hist.length)}</b>, 오른 경우 ${hist.filter(x => x > 0).length}번이에요${hist.length < 4 ? '(표본이 적어 참고만)' : ''}.` : '';
      const lastP = PM.length ? PM[PM.length - 1] : null;
      const since = lastP && lastP.n > n ? ` 실적 발표 분기 이후 지금(${lastP.m})까지 주가는 ${pct(lastP.v / s.p1 - 1)} 더 움직였어요.` : '';
      sigHtml = `<div class="fc-sig ${s.t}"><div class="h"><span class="chip">${T[0]}</span>${T[1]}</div>
        <p>${qk(n - 4)}→${qk(n)} 1년 동안 ${en}(최근 4분기 합) <b>${s.e0 > 0 && s.e1 > 0 ? pct(s.de) : `${s.e0 <= 0 && s.e1 > 0 ? '흑자 전환 ' : s.e0 > 0 && s.e1 <= 0 ? '적자 전환 ' : ''}${eok(s.e0)} → ${eok(s.e1)}`}</b>, 주가(분기 말) <b>${pct(s.dp)}</b>.${since}</p>
        <p>${T[2]}</p>${histTxt ? `<p class="sub">${histTxt}</p>` : ''}</div>`;
    }

    // ---- 변화율 타일 (기간 전체)
    const tl = [];
    const pxi = axis.map(n => pq[n] ? pq[n].v : null);
    const firstLast = arr => { let a = -1, b = -1; arr.forEach((v, i) => { if (v != null) { if (a < 0) a = i; b = i; } }); return [a, b]; };
    if (pqn.length) {
      const bi = axis.findIndex((n, i) => pxi[i] != null && (!ek || ttm(n, 'rev') != null));
      const [, b] = firstLast(pxi), lastP = PM[PM.length - 1];
      if (bi >= 0) { const v0 = pxi[bi], v1 = lastP.v, y = (lastP.n - axis[bi]) / 4;
        tl.push({ k: 'px', name: '주가', v: pct(v1 / v0 - 1), cagr: y >= 1 ? Math.pow(v1 / v0, 1 / y) - 1 : null, s: `${labels[bi]} 말 ${fmt(v0)}원 → ${lastP.m} ${fmt(v1)}원` }); }
      void b;
    }
    fields.forEach(f => {
      const arr = axis.map(n => ttm(n, f)), [a, b] = firstLast(arr);
      if (a < 0 || a === b) return;
      const v0 = arr[a], v1 = arr[b], y = (b - a) / 4;
      const v = v0 > 0 && v1 > 0 ? pct(v1 / v0 - 1) : v0 <= 0 && v1 > 0 ? '흑자 전환' : v0 > 0 && v1 <= 0 ? '적자 전환' : v1 > v0 ? '적자 축소' : '적자 확대';
      tl.push({ k: f, name: `${names[f]} <span style="color:var(--ink-3)">4분기 합</span>`, v, cagr: v0 > 0 && v1 > 0 && y >= 1 ? Math.pow(v1 / v0, 1 / y) - 1 : null, s: `${labels[a]} ${eok(v0)} → ${labels[b]} ${eok(v1)}` });
    });
    const tiles = tl.map(t => `<div class="fc-kpi"><div class="l"><span class="sw" style="background:${colors[t.k]}"></span>${t.name}</div><div class="v">${t.v}${t.cagr != null ? `<small>연 ${pct(t.cagr)}</small>` : ''}</div><div class="s">${t.s}</div></div>`).join('');

    // ---- DOM
    const seg = (grp, list, cur) => `<div class="fc-segs" role="group" aria-label="${grp}" data-g="${grp}"${list.length < 2 ? ' hidden' : ''}>${list.map(([k, l]) => `<button class="seg" data-v="${k}" aria-pressed="${k === cur}">${l}</button>`).join('')}</div>`;
    const anySig = sig.some(s => s && (s.t === 'opp' || s.t === 'warn'));
    const key = ek && pqn.length ? `<div class="fc-key"><span><i style="background:${tint('--up', 0.28)}"></i>실적↑ 주가↓ (기회 후보)</span><span><i style="background:${tint('--down', 0.28)}"></i>실적↓ 주가↑ (주의)</span><span class="n">직전 1년 대비 ${ek === 'op' ? '영업이익' : ek === 'ni' ? NI : '매출'}(4분기 합) ±${TH_E * 100}%·주가 ±${TH_P * 100}% 넘게 엇갈린 분기${anySig ? '' : ' · 이 기간엔 없어요'}</span></div>` : '';
    el.innerHTML = `
      ${sigHtml}
      <div class="fc-kpis">${tiles}</div>
      <div class="fc-ctl">${seg('보기', [['stack', '나란히 보기'], ['index', '겹쳐 보기']], ST.view)}${ST.view === 'stack' ? seg('실적 기준', [['ttm', '4분기 합'], ['q', '분기']], ST.mode) : ''}${seg('기간', opts, ST.range)}</div>
      ${key}
      <div class="fc-body"></div>
      ${TE.length ? '<div class="fc-turns"></div>' : ''}
      <p class="fc-note">주가: ${o.source || '월말 종가(수정주가)'} · 실적: 분기 ${qkeys[0] || '–'}~${qkeys[qkeys.length - 1] || '–'}. 4분기 합은 계절성을 없앤 1년치 실적이에요. 주가는 1주 가격이라 유상증자·자사주 소각처럼 주식 수가 바뀌면 이익 변화와 차이가 날 수 있어요. 방향 신호는 판단 보조용이며 매수·매도 추천이 아니에요.</p>
      <details class="fc-tbl"><summary>표로 보기</summary><div class="w"><table><thead><tr><th>분기</th><th>분기 말 주가(원)</th><th>매출액</th><th>영업이익</th><th>${NI}</th><th>매출 4분기 합</th><th>영업이익 4분기 합</th><th>${NI} 4분기 합</th><th>방향</th></tr></thead><tbody>
      ${axis.slice().reverse().map((n, j) => { const s = sig[axis.length - 1 - j]; return `<tr><td>${qk(n)}</td><td>${pq[n] ? fmt(pq[n].v) : '–'}</td>${['rev', 'op', 'ni'].map(f => `<td>${fmt(val(n, f))}</td>`).join('')}${['rev', 'op', 'ni'].map(f => `<td>${fmt(ttm(n, f))}</td>`).join('')}<td>${s ? { opp: '실적↑ 주가↓', warn: '실적↓ 주가↑', up: '함께 ↑', down: '함께 ↓', flat: '–' }[s.t] : '–'}</td></tr>`; }).join('')}
      </tbody></table><p class="fc-note">단위: 억원(주가 제외)</p></div></details>`;

    const redraw = () => { charts.forEach(c => c.destroy()); charts.length = 0; build(el, o, charts); };
    el.querySelectorAll('.fc-segs button').forEach(b => b.onclick = () => {
      const g = b.parentElement.dataset.g, v = b.dataset.v;
      if (g === '기간') ST.range = v; else if (g === '보기') ST.view = v; else ST.mode = v;
      redraw();
    });

    // ---- 공통 차트 부품
    const grid = css('--line') || '#e5e5e5', ink3 = css('--ink-3') || '#888';
    const font = getComputedStyle(document.body).fontFamily;
    const narrow = el.clientWidth < 600;
    const step = Math.max(1, Math.ceil(axis.length / 4 / (narrow ? 4 : 10)));
    const group = { idx: null };
    const xScale = show => ({
      type: 'linear', min: -0.5, max: axis.length - 0.5, grid: { display: false }, border: { color: grid },
      afterBuildTicks: sc => { sc.ticks = axis.map((n, i) => ({ value: i })).filter(t => labels[t.value].endsWith('Q1') && (+labels[t.value].slice(0, 4)) % step === 0); },
      ticks: { display: show, color: ink3, maxRotation: 0, autoSkip: false, font: { size: 11 },
        callback: v => { const l = labels[Math.round(v)]; return l ? (narrow ? "'" + l.slice(2, 4) : l.slice(0, 4)) : ''; } }
    });
    const shade = {
      id: 'fcShade',
      beforeDatasetsDraw(ch) {
        const c = ch.ctx, A = ch.chartArea, x = ch.scales.x;
        c.save();
        sig.forEach((s, i) => {
          if (!s || (s.t !== 'opp' && s.t !== 'warn')) return;
          const a = Math.max(A.left, x.getPixelForValue(i - 0.5)), b = Math.min(A.right, x.getPixelForValue(i + 0.5));
          c.fillStyle = tint(s.t === 'opp' ? '--up' : '--down', 0.13); c.fillRect(a, A.top, b - a, A.bottom - A.top);
        });
        const se = TE.find(e => e.id === o._sel);
        if (se) {
          const [u, w] = span(se), a = Math.max(A.left, x.getPixelForValue(u)), b = Math.min(A.right, x.getPixelForValue(w));
          if (b > a) { c.fillStyle = tint('--ink-3', 0.12); c.fillRect(a, A.top, b - a, A.bottom - A.top);
            c.strokeStyle = css('--ink-3') || '#888'; c.setLineDash([4, 3]); c.lineWidth = 1; c.strokeRect(a + 0.5, A.top + 0.5, b - a - 1, A.bottom - A.top - 1); }
        }
        c.restore();
      }
    };
    const badge = (c, x, y, n, col) => {
      c.save(); c.beginPath(); c.arc(x, y, 8, 0, Math.PI * 2); c.fillStyle = col; c.fill();
      c.lineWidth = 1.5; c.strokeStyle = css('--panel') || '#fff'; c.stroke();
      c.fillStyle = '#fff'; c.font = `700 10px ${getComputedStyle(document.body).fontFamily}`; c.textAlign = 'center'; c.textBaseline = 'middle';
      c.fillText(String(n), x, y + 0.5); c.restore();
    };
    const marks = {  // 주가 패널: 띠 번호(위쪽), 고점·저점 번호(가격 위치)
      id: 'fcTurns',
      afterDatasetsDraw(ch) {
        if (!TE.length || !ch.canvas.dataset.px) return;
        const A = ch.chartArea, x = ch.scales.x, y = ch.scales.y, c = ch.ctx;
        TE.forEach(e => {
          const col = css(e.t === 'up' || e.t === 'opp' ? '--up' : '--down') || '#888';
          if (e.kind === 'band') {
            const [u, w] = span(e), px = x.getPixelForValue((u + w) / 2);
            if (px >= A.left && px <= A.right) badge(c, px, A.top + 9, e.no, col);
          } else if (e.pivot && pxAt[e.m0] != null) {
            const px = x.getPixelForValue(XMm(e.m0)), py = y.getPixelForValue(pxAt[e.m0]);
            if (px < A.left - 2 || px > A.right + 2) return;
            const peak = e.t === 'down';
            let by = py + (peak ? -13 : 13); if (by < A.top + 26) by = py + 13;  // 위쪽 띠 번호와 겹치지 않게
            badge(c, px, Math.min(A.bottom - 9, by), e.no, col);
          }
        });
      }
    };
    const pick = (ch, ev) => {
      const xv = ch.scales.x.getValueForPixel(ev.x);
      const e = (ch.canvas.dataset.px && pivotNear(xv)) || evAt(xv)[0];
      if (!e) return;
      o._sel = e.id; charts.forEach(c => c.draw()); openCard(e.id, true);
    };
    function openCard(id, scroll) {
      const box = el.querySelector('.fc-turns'); if (!box) return;
      box.querySelectorAll('.fc-tc').forEach(d => d.classList.toggle('sel', +d.dataset.id === id));
      const d = box.querySelector(`.fc-tc[data-id="${id}"]`);
      if (!d) { if (TF.f !== 'all') { TF.f = 'all'; drawList(); openCard(id, scroll); } return; }
      d.open = true; if (scroll) d.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
    function drawList() {
      const box = el.querySelector('.fc-turns'); if (!box) return;
      const F = { all: ['전체', () => true], leg: ['큰 흐름(고점·저점)', e => e.kind === 'leg'], band: ['실적·주가 엇갈림', e => e.kind === 'band'] };
      const list = TE.filter(F[TF.f][1]).slice().reverse();
      const CN = { earn: '실적', cycle: '업황', trend: '트렌드', news: '뉴스', val: '밸류에이션', cat: '촉매제', macro: '거시·시장' };
      const SG = (c, t) => c.none ? '–' : c.s > 0 ? '↑' : c.s < 0 ? '↓' : '·';
      const sc = c => c.none ? 'n' : c.s > 0 ? 'p' : c.s < 0 ? 'm' : 'z';
      const lv = c => c.none ? '' : `<span class="lv" title="영향 ${['약함', '약함', '보통', '강함'][c.lvl || 0]}">${'●'.repeat(Math.max(1, c.lvl || 1))}${'○'.repeat(3 - Math.max(1, c.lvl || 1))}</span>`;
      const evl = c => (c.ev || []).length ? `<ul>${c.ev.map((x, i) => `<li>${esc(x)}${c.u && c.u[i] ? ` <a href="${esc(c.u[i])}" target="_blank" rel="noopener">기사</a>` : ''}</li>`).join('')}</ul>` : '';
      const chips = e => `<span class="chips">${e.cats.map(c => `<span class="fc-chip c-${sc(c)}${(e.drive || []).includes(c.k) ? ' dr' : ''}">${CN[c.k] || c.k} ${SG(c)}</span>`).join('')}</span>`;
      const card = e => e.cats ? `<details class="fc-tc t-${e.t}${e.id === o._sel ? ' sel' : ''}" data-id="${e.id}"${e.id === o._sel ? ' open' : ''}><summary><span class="no">${e.no}</span><span class="tt">${esc(e.title)}</span><span class="hd">${esc(e.head)}</span><span class="why">${esc(e.sum)}</span>${chips(e)}</summary>
        <div class="bd"><div class="fc-cats">${e.cats.map(c => `<div class="fc-cat c-${sc(c)}${c.none ? ' none' : ''}"><div class="ch"><span class="nm">${CN[c.k] || c.k}</span><span class="sg">${SG(c)}</span>${lv(c)}${c.b ? `<span class="br">${esc(c.b)}</span>` : ''}</div><p>${esc(c.t)}</p>${evl(c)}</div>`).join('')}</div>
        ${e.after ? `<p class="look"><b>이후 확인</b> ${esc(e.after)}</p>` : ''}${e.unc ? `<p class="look"><span class="fc-tag unc">불확실</span>${esc(e.unc)}</p>` : ''}
        <p class="look"><b>앞으로 볼 점</b> ${esc(e.look)}</p></div></details>`
        : `<details class="fc-tc t-${e.t}${e.id === o._sel ? ' sel' : ''}" data-id="${e.id}"${e.id === o._sel ? ' open' : ''}><summary><span class="no">${e.no}</span><span class="tt">${esc(e.title)}</span><span class="hd">${esc(e.head)}</span><span class="why"><b>왜?</b> ${esc(e.why)}</span></summary>
        <div class="bd"><ul>${(e.f || []).map(f => `<li><span class="fc-tag${f.tag === '불확실' ? ' unc' : ''}">${esc(f.tag)}</span>${esc(f.text)}${f.u ? ` <a href="${esc(f.u)}" target="_blank" rel="noopener">기사</a>` : ''}</li>`).join('')}</ul>
        <p class="look"><b>앞으로 볼 점</b> ${esc(e.look)}</p></div></details>`;
      box.innerHTML = `<div class="th"><h4>변곡점마다 왜 오르고 내렸나 · ${TE.length}개</h4><div class="fc-segs" role="group" aria-label="해설 종류">${Object.entries(F).map(([k, [l]]) => `<button class="seg" data-f="${k}" aria-pressed="${k === TF.f}">${l}</button>`).join('')}</div></div>
        <p class="lead">차트의 번호 원과 색 띠를 누르면 해당 해설이 열려요. 오르내린 이유를 실적(시장 기대 대비)·업황·트렌드·뉴스·밸류에이션·촉매제·거시·시장으로 나눠 설명하고, 맨 위 한 줄에 가장 크게 작용한 요인을 요약했어요. ✔는 기사 원문으로 확인한 원인이에요. ↑는 주가를 올린 쪽, ↓는 내린 쪽, ●●●는 영향의 크기예요. 그 시기에 근거가 없는 요인은 '–'로 표시했어요. 숫자는 데이터에서 자동 계산했고, 원인 연결은 추정이에요.</p>
        ${list.map(card).join('') || '<p class="lead">이 종류의 변곡점이 없어요.</p>'}
        <p class="fc-note">해설 갱신 ${esc((o._turns && o._turns.updated) || '')} · 시장 비교는 ${o._turns && o._turns.macro === false ? '7개 산업 대시보드 전체 중앙값' : '코스피(코스닥 상장사는 코스닥)'} 기준</p>`;
      box.querySelectorAll('.fc-segs button').forEach(b => b.onclick = () => { TF.f = b.dataset.f; drawList(); });
      box.querySelectorAll('.fc-tc').forEach(d => {
        d.addEventListener('toggle', () => { if (d.open) { o._sel = +d.dataset.id; box.querySelectorAll('.fc-tc').forEach(x => x.classList.toggle('sel', x === d)); charts.forEach(c => c.draw()); } });
      });
    }
    drawList();
    const cross = {
      id: 'fcCross',
      afterDatasetsDraw(ch) {
        if (group.idx == null) return;
        const x = ch.scales.x.getPixelForValue(group.idx);
        if (x < ch.chartArea.left || x > ch.chartArea.right) return;
        const c = ch.ctx; c.save(); c.strokeStyle = ink3; c.lineWidth = 1; c.setLineDash([3, 3]);
        c.beginPath(); c.moveTo(x, ch.chartArea.top); c.lineTo(x, ch.chartArea.bottom); c.stroke(); c.restore();
      },
      afterEvent(ch, a) { if (a.event.type === 'mouseout' && group.idx != null) { group.idx = null; charts.forEach(c => c.draw()); } }
    };
    const hover = (e, act, ch) => {
      const i = Math.round(ch.scales.x.getValueForPixel(e.x));
      const ni = i < 0 || i >= labels.length ? null : i;
      if (ni !== group.idx) { group.idx = ni; charts.forEach(c => c !== ch && c.draw()); }
    };
    const fit = (vals, logOk) => {
      const v = vals.filter(x => x != null && isFinite(x));
      if (!v.length) return {};
      let lo = Math.min(...v), hi = Math.max(...v);
      if (logOk && lo > 0 && hi / lo > 5) return { type: 'logarithmic', min: lo / 1.08, max: hi * 1.08 };
      const pad = (hi - lo || Math.abs(hi) || 1) * 0.08;
      return { type: 'linear', beginAtZero: false, suggestedMin: lo >= 0 ? Math.max(0, lo - pad) : lo - pad, suggestedMax: hi <= 0 ? Math.min(0, hi + pad) : hi + pad };
    };
    const body = el.querySelector('.fc-body');

    if (ST.view === 'index') return drawIndex();

    // ---- 나란히 보기: 세로로 긴 패널
    const H = narrow ? { px: 190, f: 150 } : { px: 240, f: 190 };
    const panels = [];
    if (PM.length) panels.push({ k: 'px', data: PM.filter(p => XM(p) >= -0.7).map(p => ({ x: XM(p), y: p.v, m: p.m })) });
    fields.forEach(f => panels.push({ k: f, data: axis.map((n, i) => ({ x: i, y: ser(n, f) })).filter(p => p.y != null) }));
    const unitTxt = ST.mode === 'q' ? '분기' : '최근 4분기 합';
    body.innerHTML = panels.map((p, i) => {
      let right = '';
      if (p.k === 'px' && p.data.length) { const l = p.data[p.data.length - 1]; right = `${l.m} ${fmt(l.y)}원`; }
      else if (p.data.length) {
        const l = p.data[p.data.length - 1], n = axis[l.x], prev = ser(n - 4, p.k), y = chg(prev, l.y);
        right = `${labels[l.x]} ${eok(l.y)}${y != null ? ` <span class="${y >= 0 ? 'up' : 'down'}">전년 대비 ${pct(y)}</span>` : ''}`;
      }
      return `<div class="fc-pt"><span class="t">${names[p.k]} <span>· ${p.k === 'px' ? '월말 종가, 원' : unitTxt + ', 억원'}</span></span><span class="v">${right}</span></div>
        <div class="fc-c" style="height:${(p.k === 'px' ? H.px : H.f) + (i === panels.length - 1 ? 18 : 0)}px"><canvas data-i="${i}"${p.k === 'px' ? ' data-px="1"' : ''} aria-label="${names[p.k]} 추이"></canvas></div>`;
    }).join('');
    if (!panels.length) body.innerHTML = '<p class="fc-note">그릴 데이터가 없어요.</p>';
    const zero = { id: 'fcZero', beforeDatasetsDraw(ch) { const y = ch.scales.y; if (y.type !== 'linear' || y.min > 0 || y.max < 0) return; const c = ch.ctx, p = y.getPixelForValue(0); c.save(); c.strokeStyle = ink3; c.lineWidth = 1; c.beginPath(); c.moveTo(ch.chartArea.left, p); c.lineTo(ch.chartArea.right, p); c.stroke(); c.restore(); } };
    panels.forEach((p, i) => {
      const isP = p.k === 'px', last = i === panels.length - 1, col = colors[p.k];
      const ys = fit(p.data.map(d => d.y), isP);
      charts.push(new Chart(body.querySelector(`canvas[data-i="${i}"]`), {
        type: 'line',
        data: { datasets: [{ data: p.data, borderColor: col, backgroundColor: col, borderWidth: isP ? 2 : 2.4,
          pointRadius: isP ? 0 : (ST.mode === 'q' ? 2.8 : 2), pointHoverRadius: 5, pointHoverBorderWidth: 2, pointHoverBorderColor: css('--panel') || '#fff',
          pointBackgroundColor: isP ? col : p.data.map(d => d.y < 0 ? (css('--down') || '#c0392b') : col),
          segment: isP ? undefined : { borderColor: c => (c.p0.parsed.y < 0 || c.p1.parsed.y < 0) ? (css('--down') || '#c0392b') : col },
          tension: 0, spanGaps: true }] },
        options: {
          responsive: true, maintainAspectRatio: false, animation: false, parsing: false, normalized: true,
          layout: { padding: { top: 6, right: 10, bottom: 0, left: 0 } },
          interaction: { mode: 'nearest', axis: 'x', intersect: false },
          onHover: hover,
          plugins: { legend: { display: false },
            tooltip: { callbacks: {
              title: it => isP ? it[0].raw.m : labels[Math.round(it[0].parsed.x)],
              label: it => {
                if (isP) return ` ${fmt(it.parsed.y)}원`;
                const i2 = Math.round(it.parsed.x), n = axis[i2], y = chg(ser(n - 4, p.k), it.parsed.y), q = Q[qk(n)] || {}, out = [` ${eok(it.parsed.y)}${y != null ? ` · 전년 대비 ${pct(y)}` : ''}`];
                if (q.rev && p.k !== 'rev' && ST.mode === 'q') out.push(` 분기 ${p.k === 'op' ? '영업' : '순'}이익률 ${(q[p.k] / q.rev * 100).toFixed(1)}%`);
                const s = sig[i2]; if (s && (s.t === 'opp' || s.t === 'warn')) out.push(s.t === 'opp' ? ' ▲ 실적↑ 주가↓ 분기' : ' ▼ 실적↓ 주가↑ 분기');
                return out; },
              afterBody: it => {
                if (!TE.length || !it.length) return [];
                const xv = it[0].parsed.x, pv = isP && pivotNear(xv), es = pv ? [pv] : evAt(xv);
                return es.length ? [''].concat(es.flatMap(e => wrap(`(${e.no}) ${e.title}: ${e.sum || e.why}`, 46)), ['클릭하면 아래에 근거가 열려요']) : [];
              } } } },
          onClick: (ev, act, ch) => pick(ch, ev),
          scales: {
            x: xScale(last),
            y: Object.assign({ position: 'left', afterFit: sc => { sc.width = YW; }, grid: { color: grid }, border: { display: false },
              ticks: { color: ink3, font: { size: 10.5 }, maxTicksLimit: 5, callback: v => isP ? fmt(v) : tickEok(v) } }, ys,
              ys.type === 'logarithmic' ? { afterBuildTicks: logTicks, ticks: { color: ink3, font: { size: 10.5 }, autoSkip: false, callback: v => fmt(v) } } : {})
          }
        },
        plugins: [shade, zero, cross, marks]
      }));
    });
    return;

    // ---- 겹쳐 보기: 첫 분기 = 100 지수
    function drawIndex() {
      const S = [{ k: 'px', w: 2.6, raw: pxi }].concat(fields.map(f => ({ k: f, w: 2, raw: axis.map(n => ttm(n, f)) })))
        .filter(s => s.raw.some(v => v != null));
      const bi = axis.findIndex((_, i) => S.every(s => s.raw[i] != null));
      S.forEach(s => {
        const i0 = bi >= 0 ? bi : s.raw.findIndex(v => v != null);
        let i1 = -1; s.raw.forEach((v, i) => { if (v != null) i1 = i; });
        s.i0 = i0; s.i1 = i1; s.b = s.raw[i0];
        s.ok = s.b > 0 && s.raw.slice(i0).every(v => v == null || v > 0);
        s.idx = s.raw.map((v, i) => s.ok && v != null && i >= i0 ? v / s.b * 100 : null);
      });
      const vis = S.filter(s => s.ok), ex = S.filter(s => !s.ok).map(s => names[s.k]);
      const PADR = narrow ? 92 : 118;
      body.innerHTML = `<div class="fc-pt"><span class="t">${bi >= 0 ? labels[bi] : labels[0]} = 100 <span>· 로그 눈금이라 기울기가 같으면 성장률이 같아요 · 실적은 4분기 합, 주가는 분기 말 종가</span></span></div>
        <div class="fc-leg">${vis.map(s => `<button type="button" data-k="${s.k}" aria-pressed="${!HIDDEN.has(s.k)}"><span class="sw" style="background:${colors[s.k]}"></span>${names[s.k]}</button>`).join('')}</div>
        <div class="fc-c" style="height:${narrow ? 300 : 420}px"><canvas aria-label="주가와 실적 지수 비교"></canvas></div>
        ${ex.length ? `<p class="fc-note">${ex.join('·')}은 이 기간에 적자(4분기 합 0 이하) 구간이 있어 지수로 나타낼 수 없어요. 나란히 보기에서 확인하세요.</p>` : ''}`;
      if (!vis.length) { body.querySelector('.fc-c').outerHTML = '<p class="fc-note">지수로 비교할 계열이 없어요.</p>'; return; }
      const ys = vis.flatMap(s => s.idx.filter(v => v != null));
      const ymin = Math.min(100, ...ys), ymax = Math.max(100, ...ys);
      const endLabels = {
        id: 'fcEnd',
        afterDatasetsDraw(ch) {
          const c = ch.ctx, A = ch.chartArea, items = [];
          ch.data.datasets.forEach((d, di) => {
            if (!ch.isDatasetVisible(di)) return;
            const s = d._s, pt = ch.getDatasetMeta(di).data[s.i1];
            if (!pt || s.idx[s.i1] == null) return;
            const nm = s.k === 'px' ? '주가' : s.k === 'ni' ? '순이익' : narrow ? { rev: '매출', op: '영업익' }[s.k] : names[s.k];
            items.push({ y: pt.y, s, t: `${nm} ${pct(s.idx[s.i1] / 100 - 1)}` });
          });
          items.sort((a, b) => a.y - b.y);
          for (let i = 1; i < items.length; i++) if (items[i].y - items[i - 1].y < 14) items[i].y = items[i - 1].y + 14;
          const over = items.length ? items[items.length - 1].y - (A.bottom + 4) : 0;
          if (over > 0) items.forEach(it => it.y -= over);
          c.save(); c.font = `600 11px ${font}`; c.textBaseline = 'middle';
          items.forEach(it => { c.fillStyle = colors[it.s.k]; c.fillRect(A.right + 6, it.y - 1.5, 8, 3); c.fillStyle = css('--ink-2'); c.fillText(it.t, A.right + 17, it.y); });
          c.restore();
        }
      };
      const ch = new Chart(body.querySelector('canvas'), {
        type: 'line',
        data: { datasets: vis.map(s => ({ _s: s, label: names[s.k], data: s.idx.map((v, i) => ({ x: i, y: v })).filter(p => p.y != null),
          borderColor: colors[s.k], backgroundColor: colors[s.k], borderWidth: s.w, pointRadius: 0, pointHoverRadius: 4, tension: 0, hidden: HIDDEN.has(s.k) })) },
        options: {
          responsive: true, maintainAspectRatio: false, animation: false, parsing: false,
          layout: { padding: { top: 8, right: PADR, bottom: 0, left: 0 } },
          interaction: { mode: 'index', intersect: false }, onHover: hover, onClick: (ev, act, c) => pick(c, ev),
          plugins: { legend: { display: false }, tooltip: { itemSort: (a, b) => b.parsed.y - a.parsed.y, callbacks: {
            title: it => labels[Math.round(it[0].parsed.x)],
            label: it => { const s = it.dataset._s, r = s.raw[Math.round(it.parsed.x)]; return ` ${names[s.k]} ${fmt(it.parsed.y)} · ${s.k === 'px' ? fmt(r) + '원' : '4분기 합 ' + eok(r)}`; } } } },
          scales: { x: xScale(true),
            y: { type: 'logarithmic', position: 'left', min: ymin / 1.08, max: ymax * 1.08, afterFit: sc => { sc.width = YW; }, border: { display: false },
              grid: { color: c => c.tick && Math.abs(c.tick.value - 100) < 1e-6 ? ink3 : grid },
              afterBuildTicks: sc => { logTicks(sc); if (!sc.ticks.some(t => t.value === 100)) sc.ticks.push({ value: 100 }); sc.ticks.sort((a, b) => a.value - b.value); },
              ticks: { color: ink3, font: { size: 10.5 }, autoSkip: false, callback: v => fmt(v) } } }
        },
        plugins: [shade, cross, endLabels]
      });
      charts.push(ch);
      body.querySelectorAll('.fc-leg button').forEach(b => b.onclick = () => {
        const k = b.dataset.k, on = HIDDEN.has(k); on ? HIDDEN.delete(k) : HIDDEN.add(k);
        b.setAttribute('aria-pressed', String(on));
        ch.setDatasetVisibility(ch.data.datasets.findIndex(d => d._s.k === k), on); ch.update();
      });
    }
  }

  function logTicks(sc) {
    const lo = sc.min, hi = sc.max, t = [];
    const gen = ms => { t.length = 0; for (let e = Math.floor(Math.log10(lo)) - 1; e <= Math.ceil(Math.log10(hi)); e++) ms.forEach(m => { const v = m * 10 ** e; if (v >= lo && v <= hi) t.push({ value: v }); }); };
    gen([1, 2, 5]);
    if (t.length < 4) gen([1, 1.5, 2, 3, 5, 7]);
    if (t.length < 4) gen([1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 6, 8]);
    if (t.length > 9) gen([1, 3]);
    sc.ticks = t;
  }
  function tint(v, a) {
    const c = css(v) || '#888888';
    const m = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(c);
    if (!m) return `color-mix(in srgb, ${c} ${Math.round(a * 100)}%, transparent)`;
    let h = m[1]; if (h.length === 3) h = h.split('').map(x => x + x).join('');
    return `rgba(${parseInt(h.slice(0, 2), 16)},${parseInt(h.slice(2, 4), 16)},${parseInt(h.slice(4, 6), 16)},${a})`;
  }
  // ---- 연간 실적표: 매출·이익이 크게 바뀐 해마다 이유
  function annual(wrap, code, url) {
    if (!wrap || !code || !url) return;
    injectStyle();
    wrap._fcCode = code;
    const old = wrap.parentNode && wrap.parentNode.querySelector('.fc-yn'); if (old) old.remove();
    loadTurns(url + code + '.json').then(t => {
      if (!t || wrap._fcCode !== code) return;
      const Y = t.years || {}, ys = Object.keys(Y).sort().reverse();
      if (!ys.length) return;
      const prev = wrap.parentNode.querySelector('.fc-yn'); if (prev) prev.remove();
      const box = document.createElement('div'); box.className = 'fc-yn';
      box.innerHTML = `<h4>매출·이익이 크게 바뀐 해, 왜 그랬나</h4><p class="lead">매출 ±15% 이상, 영업이익 ±40% 이상이거나 흑자·적자가 바뀐 해예요. 업종 같은 해 증가율, 분기 흐름(계단식 증가는 인수·대형 계약 신호), 이익률(가격·원가 vs 물량), 영업외 요인, 환율·유가, 사건 연표와 뉴스를 맞춰 자동으로 정리했어요. 표의 ? 를 눌러도 열려요.</p>` +
        ys.map(y => { const v = Y[y]; return `<details data-y="${y}"><summary><span class="y">${y}년</span><span class="hd">${esc(v.head)}</span><span class="why"><b>왜?</b> ${esc(v.why)}</span></summary><div class="bd"><ul>${v.f.map(f => `<li><span class="fc-tag${f.tag === '불확실' ? ' unc' : ''}">${esc(f.tag)}</span>${esc(f.text)}${f.u ? ` <a href="${esc(f.u)}" target="_blank" rel="noopener">기사</a>` : ''}</li>`).join('')}</ul></div></details>`; }).join('');
      wrap.insertAdjacentElement('afterend', box);
      wrap.querySelectorAll('thead th').forEach(th => {
        const y = th.textContent.trim();
        if (!Y[y] || th.querySelector('.fc-ydot')) return;
        const b = document.createElement('button'); b.className = 'fc-ydot'; b.textContent = '?'; b.title = `${y}년에 왜 크게 바뀌었나`; b.setAttribute('aria-label', b.title);
        b.onclick = () => { const d = box.querySelector(`details[data-y="${y}"]`); if (d) { d.open = true; d.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); } };
        th.appendChild(b);
      });
    });
  }
  window.FinChart = { render, annual };
})();
