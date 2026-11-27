// 기업분석 자동화 대시보드 — 이엔에프테크놀로지 AI 리포트(2026-11-26)를 역엔지니어링한 목차·계산식을 그대로 쓴다.
// 데이터: data/c/<코드>.json (scripts/report/build.py). 모든 계산은 여기서 하므로 가정을 바꾸면 리포트 전체가 다시 계산된다.
// 단위: 입력은 백만원, 화면은 억원(리포트와 같음).
(function () {
'use strict';
const $ = s => document.querySelector(s);
const LIVE = 'https://raw.githubusercontent.com/lifeisgreathehe-cyber/kcosmetics-dashboard/live-data/';
const TAX = 0.242;          // 리포트 ROIC 세율(법인세+지방세)
const COST_OF_CAPITAL = 0.08;
const S = { list: null, d: null, ov: {}, M: null };

// ---------------------------------------------------------------- 형식
const isNum = v => typeof v === 'number' && isFinite(v);
const eok = v => isNum(v) ? Math.round(v / 100).toLocaleString('ko-KR') : '–';       // 백만원 → 억원
const won = v => isNum(v) ? Math.round(v).toLocaleString('ko-KR') : '–';
const pct = (v, d = 1) => isNum(v) ? (v * 100).toFixed(d) + '%' : '–';
const pp = v => isNum(v) ? (v >= 0 ? '+' : '−') + Math.abs(v * 100).toFixed(1) + '%p' : '–';
const sg = (v, d = 0) => isNum(v) ? (v >= 0 ? '+' : '−') + Math.abs(v * 100).toFixed(d) + '%' : '–';
const x1 = v => isNum(v) ? v.toFixed(1) : '–';
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const median = a => { const s = a.filter(isNum).slice().sort((x, y) => x - y); if (!s.length) return null; const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
const mean = a => { const s = a.filter(isNum); return s.length ? s.reduce((x, y) => x + y, 0) / s.length : null; };
const std = a => { const m = mean(a), s = a.filter(isNum); return s.length > 1 ? Math.sqrt(s.reduce((x, y) => x + (y - m) ** 2, 0) / (s.length - 1)) : null; };
const josa = (w, a, b) => { const c = (w || '').charCodeAt((w || '').length - 1); return c >= 0xac00 && c <= 0xd7a3 && (c - 0xac00) % 28 ? a : b; };
const eunNeun = w => w + josa(w, '은', '는');

// ---------------------------------------------------------------- 수익모델
function buildModel(d, ov) {
  const man = (d.manual && d.manual.model) || {};
  const A = d.annual || {}, Q = d.quarterly || {};
  const yrs = Object.keys(A).filter(y => isNum(A[y].rev)).sort();
  if (!yrs.length) return null;
  const FY = +yrs[yrs.length - 1], CY = FY + 1, T = CY + 5;
  const shares = d.shares || (d.shares_dart && d.shares_dart.common) || null;
  const price = d.price;
  const hasGP = isNum(A[FY].gp);
  const rows = {};
  yrs.forEach(y => { const a = A[y]; rows[y] = { ...a, est: false }; });
  const r = y => rows[y] || {};
  // 분기
  const qk = Object.keys(Q).sort();
  const cyq = qk.filter(k => k.startsWith(CY + 'Q'));
  const n = cyq.length;
  const sumQ = (ks, f) => ks.reduce((s, k) => s + (isNum(Q[k][f]) ? Q[k][f] : 0), 0);
  const prevSame = cyq.map(k => FY + k.slice(4));
  const prevRest = [1, 2, 3, 4].map(i => FY + 'Q' + i).filter(k => !prevSame.includes(k));
  const ytd = n ? { rev: sumQ(cyq, 'rev'), gp: sumQ(cyq, 'gp'), op: sumQ(cyq, 'op'), ni: sumQ(cyq, 'ni'), n, prev_rev: sumQ(prevSame, 'rev'), prev_op: sumQ(prevSame, 'op'), prev_ni: sumQ(prevSame, 'ni') } : null;
  // 올해(CY) 추정: 누적 + 남은 분기(작년 같은 분기 × 누적 성장률, 이익률은 누적 이익률 × 작년 계절성)
  let cy = null, cyNote = '';
  if (man.cy) { cy = { ...man.cy }; cyNote = '원고 가정'; }
  else if (n === 4) { cy = { rev: ytd.rev, gp: ytd.gp, op: ytd.op, ni: ytd.ni }; cyNote = '4개 분기 합계'; }
  else if (n > 0 && ytd.prev_rev > 0) {
    const g = ytd.rev / ytd.prev_rev - 1;
    const restRev = sumQ(prevRest, 'rev') * (1 + g);
    const opmY = ytd.op / ytd.rev, gpmY = hasGP ? ytd.gp / ytd.rev : null;
    const fyOpmSame = ytd.prev_rev ? sumQ(prevSame, 'op') / ytd.prev_rev : null;
    const restPrevRev = sumQ(prevRest, 'rev');
    const fyOpmRest = restPrevRev ? sumQ(prevRest, 'op') / restPrevRev : null;
    const season = (fyOpmSame > 0 && isNum(fyOpmRest)) ? clamp(fyOpmRest / fyOpmSame, 0.3, 1.2) : 1;
    const qMax = Math.max(...cyq.map(k => Q[k].rev ? Q[k].op / Q[k].rev : -1));
    const restOp = restRev * Math.min(opmY * season, qMax > 0 ? qMax : opmY * season);   // 남은 분기 이익률은 올해 최고 분기를 넘지 않게
    const conv = ytd.op > 0 ? clamp(ytd.ni / ytd.op, 0, 1.2) : 0.7;
    const gpmRest = hasGP && isNum(gpmY) ? gpmY - (opmY - opmY * season) * 0.5 : null;
    cy = { rev: ytd.rev + restRev, gp: hasGP ? ytd.gp + restRev * gpmRest : null, op: ytd.op + restOp, ni: ytd.ni + restOp * conv };
    cyNote = `${n}개 분기 실적 + 남은 ${4 - n}개 분기 추정(작년 같은 분기 × 누적 성장률 ${sg(g)}, 영업이익률 ${pct(opmY)} × 작년 계절성 ${season.toFixed(2)})`;
    cy._rest = { rev: restRev, op: restOp, opm: restRev ? restOp / restRev : null, season };
  }
  // 과거 통계
  const last = k => yrs.slice(-k).map(Number);
  const back = k => yrs.length > k ? +yrs[yrs.length - 1 - k] : +yrs[0];
  const y0 = back(5);
  const gHist = r(y0).rev > 0 ? Math.pow(r(FY).rev / r(y0).rev, 1 / (FY - y0)) - 1 : 0.03;
  // 정상 이익률 = 최근 10년(한 사이클) 평균 — 리포트처럼 사이클 위치를 반영해 현재 이익률에서 천천히 되돌린다
  const gpm5 = hasGP ? mean(last(10).map(y => r(y).gp / r(y).rev)) : null;
  const opm5 = mean(last(10).map(y => r(y).op / r(y).rev));
  const convs = last(5).map(y => (r(y).op > 0 && isNum(r(y).ni)) ? r(y).ni / r(y).op : null).filter(v => isNum(v) && v > 0 && v < 1.5);
  const kDef = convs.length ? clamp(median(convs), 0.3, 1.1) : 0.7;
  // 기준 연도(추정 출발점)
  const startY = cy ? CY : FY;
  if (cy) rows[CY] = { ...cy, est: true, partial: !man.cy && n < 4 };
  const base = rows[startY];
  const fy = (cy ? [] : [CY]).concat([1, 2, 3, 4, 5].map(i => CY + i)).filter(y => y <= T);
  const gStart = cy && r(FY).rev > 0 ? cy.rev / r(FY).rev - 1 : gHist;
  const g1 = clamp(0.5 * gStart + 0.5 * gHist, -0.05, 0.2);
  const mStart = hasGP && base.gp != null ? base.gp / base.rev : null;
  const m1 = hasGP ? gpm5 + (mStart - gpm5) * 0.8 : null;
  const o1 = opm5 + (base.op / base.rev - opm5) * 0.8;
  const pick = (key, y, def) => {
    const u = ov[key] && ov[key][y]; if (isNum(u)) return u;
    const m = man[key] && man[key][y]; if (isNum(m)) return m;
    return def;
  };
  const one = (key, def) => isNum(ov[key]) ? ov[key] : isNum(man[key]) ? man[key] : def;
  const k = one('ni_conv', kDef);
  const sgaG = one('sga_growth', null);
  // 배당
  const div = d.dividends || {};
  const dYears = Object.keys(div).filter(y => isNum(div[y].dps)).sort();
  let dpsLast = dYears.length ? div[dYears[dYears.length - 1]].dps : (isNum(d.div_yield) && price ? d.div_yield / 100 * price : 0);
  const payouts = dYears.slice(-3).map(y => { const e = r(y).ni && shares ? r(y).ni * 1e6 / shares : null; return e > 0 ? div[y].dps / e : null; }).filter(isNum);
  const payDef = payouts.length ? median(payouts) : (r(FY).ni > 0 && shares ? dpsLast / (r(FY).ni * 1e6 / shares) : 0);
  const payout = one('payout', clamp(payDef || 0, 0, 1));
  // 추정
  let prev = base, sga = hasGP ? (base.gp - base.op) : null, i = 0;
  const drivers = [];
  for (const y of fy) {
    const decay = Math.pow(0.6, i), mdecay = Math.pow(0.8, i);
    if (y === T && i > 0) {   // 리포트 방식: 명시 추정은 4년, 종료 연도 EPS는 마지막 추정 연도 × (1 + 장기 성장률)
      const g = pick('growth', y, 0.03);
      rows[y] = { rev: prev.rev * (1 + g), gp: isNum(prev.gp) ? prev.gp * (1 + g) : null, op: prev.op * (1 + g), ni: prev.ni * (1 + g), est: true, ext: true };
      drivers.push({ y, g, m: isNum(prev.gp) ? prev.gp / prev.rev : prev.op / prev.rev, sgr: null, ext: true });
      prev = rows[y]; i++; continue;
    }
    const g = pick('growth', y, 0.03 + (g1 - 0.03) * decay);
    const rev = prev.rev * (1 + g);
    let gp = null, op, m = null, sgr = null;
    if (hasGP && isNum(m1)) {
      m = pick('gpm', y, gpm5 + (m1 - gpm5) * mdecay);
      gp = rev * m;
      sgr = isNum(sgaG) ? sgaG : Math.max(0.02, 0.6 * g + 0.03);
      sgr = pick('sga_g', y, sgr);
      sga = sga * (1 + sgr);
      op = gp - sga;
    } else {
      m = pick('opm', y, opm5 + (o1 - opm5) * mdecay);
      op = rev * m;
    }
    const ni = pick('ni', y, op > 0 ? op * k : op);
    rows[y] = { rev, gp, op, ni, est: true };
    drivers.push({ y, g, m, sgr });
    prev = rows[y]; i++;
  }
  // 주당 지표·자본
  const allY = Object.keys(rows).map(Number).sort((a, b) => a - b);
  const eqLatest = d.bs_latest && d.bs_latest.equity;
  allY.forEach(y => {
    const o = rows[y];
    o.gpm = isNum(o.gp) && o.rev ? o.gp / o.rev : null;
    o.opm = o.rev ? o.op / o.rev : null;
    o.eps = shares && isNum(o.ni) ? o.ni * 1e6 / shares : null;
    o.noplat = isNum(o.op) ? o.op * (1 - TAX) : null;
    if (!o.est) o.dps = div[y] && isNum(div[y].dps) ? div[y].dps : null;
  });
  // 추정 DPS: 직전 DPS 이상, 배당성향 × EPS
  let dpsPrev = dpsLast || 0;
  allY.filter(y => rows[y].est).forEach(y => {
    const o = rows[y]; const ud = pick('dps', y, null);
    o.dps = isNum(ud) ? ud : Math.max(dpsPrev, payout * Math.max(o.eps || 0, 0));
    o.dps = Math.round(o.dps / 10) * 10; dpsPrev = o.dps;
  });
  // 자본(지배) — 과거는 PC 수집값, 추정은 최근 분기말 자본 + 남은 이익 − 배당
  allY.forEach(y => { const a = A[y] || {}; if (!rows[y].est) rows[y].equity = isNum(a.equity_parent) ? a.equity_parent : null; });
  if (isNum(eqLatest)) {
    let eq = eqLatest;
    const est = allY.filter(y => rows[y].est);
    est.forEach((y, j) => {
      const o = rows[y];
      const add = (j === 0 && cy && !man.cy && n > 0) ? (o.ni - ytd.ni) : (j === 0 && cy && n > 0 ? o.ni - ytd.ni : o.ni - (o.dps || 0) * (shares || 0) / 1e6);
      eq = eq + add; o.equity = eq;
    });
    if (!isNum(rows[FY].equity) && !cy) rows[FY].equity = eqLatest;
  }
  allY.forEach((y, j) => {
    const o = rows[y], p = rows[allY[j - 1]];
    o.roe = isNum(o.ni) && isNum(o.equity) ? o.ni / ((p && isNum(p.equity) ? (p.equity + o.equity) / 2 : o.equity)) : null;
  });
  // 과거 PER(연말 종가), 추정 PER(현재 주가)
  const pm = {}; if (d.prices && d.prices.months) d.prices.months.forEach((m, j) => pm[m] = d.prices.close[j]);
  allY.forEach(y => {
    const o = rows[y];
    o.price = o.est ? price : (pm[y + '-12'] || null);
    o.per = o.eps > 0 && o.price ? o.price / o.eps : null;
  });
  // ROIC = 영업이익×(1−24.2%) ÷ 평균(자본총계 + 순차입금)
  const ic = y => { const a = A[y] || {}; return isNum(a.equity_total) && isNum(a.debt) ? a.equity_total + a.debt - (a.cash || 0) - (a.st_fin || 0) : null; };
  yrs.forEach((y, j) => {
    const c = ic(y), p = j ? ic(yrs[j - 1]) : null;
    rows[y].ic = c;
    rows[y].roic = isNum(c) && isNum(rows[y].noplat) ? rows[y].noplat / (isNum(p) ? (c + p) / 2 : c) : null;
  });
  const roics = last(5).map(y => rows[y].roic).filter(isNum);
  const roic5 = roics.length >= 3 ? mean(roics) : null;
  // 종료 PER — 과거 연말 PER 절사평균의 85%(리포트: 과거 평균보다 약간 낮게), 비관 75%, 낙관 130%
  const hp = yrs.slice(-10).map(y => rows[y].per).filter(v => isNum(v) && v > 0 && v < 60).sort((a, b) => a - b);
  const tm = hp.length >= 4 ? mean(hp.slice(1, -1)) : hp.length ? mean(hp) : 10;
  const perBaseDef = clamp(Math.round(tm * 0.85 * 2) / 2, 5, 25);
  const per = {
    base: one('per_base', man.per && man.per.base || perBaseDef),
    bear: one('per_bear', man.per && man.per.bear || Math.round(perBaseDef * 0.75 * 2) / 2),
    bull: one('per_bull', man.per && man.per.bull || Math.round(perBaseDef * 1.3 * 2) / 2),
  };
  const bearEps = one('bear_eps', 0.6), bullEps = one('bull_eps', 1.15);
  const perSrc = ['per_base', 'per_bear', 'per_bull'].some(k => isNum(ov[k])) ? 'user' : man.per ? 'manual' : 'auto';
  const epsT = rows[T] ? rows[T].eps : null;
  const cumDiv = allY.filter(y => y > CY && y <= T).reduce((s, y) => s + (rows[y].dps || 0), 0);
  const years = 5;
  const sc = [['bear', '비관', bearEps], ['base', '기본', 1], ['bull', '낙관', bullEps]].map(([key, nm, mult]) => {
    const e = isNum(epsT) && epsT > 0 ? epsT * mult : null;   // 종료 연도 적자면 PER 방식 기대수익률을 내지 않는다
    const v = isNum(e) ? e * per[key] : null;
    const ret = price && isNum(v) ? Math.pow(Math.max(v + cumDiv, 1) / price, 1 / years) - 1 : null;
    return { key, nm, eps: e, per: per[key], value: v, div: cumDiv, ret, mult };
  });
  // 민감도: 추정 첫해 영업이익 = f(매출 증가율, 매출총이익률)
  const d1 = drivers[0];
  let sens = null;
  if (d1 && hasGP && isNum(d1.m)) {
    const sga1 = (base.gp - base.op) * (1 + d1.sgr);
    const gs = [-0.10, -0.05, 0, 0.05].map(x => d1.g + x), ms = [-0.01, 0, 0.01].map(x => d1.m + x);
    sens = { y: d1.y, gs, ms, grid: gs.map(g => ms.map(m => base.rev * (1 + g) * m - sga1)), base: rows[d1.y].op };
  } else if (d1) {
    const gs = [-0.10, -0.05, 0, 0.05].map(x => d1.g + x), ms = [-0.01, 0, 0.01].map(x => d1.m + x);
    sens = { y: d1.y, gs, ms, grid: gs.map(g => ms.map(m => base.rev * (1 + g) * m)), base: rows[d1.y].op, opm: true };
  }
  // 순현금(최근)
  const L = d.latest || {};
  const bl = d.bs_latest || {};
  const nc = isNum(L.debt) ? { v: (L.cash || 0) + (L.st_fin || 0) - L.debt, p: L.period } : isNum(bl.debt) ? { v: (bl.cash || 0) + (bl.st_fin || 0) - bl.debt, p: bl.period } : null;
  const mcap = d.mcap || (price && shares ? price * shares / 1e6 : null);
  const treasury = d.shares_dart && d.shares_dart.common_issued ? 1 - d.shares_dart.common / d.shares_dart.common_issued : null;
  return { FY, CY, T, yrs, allY, rows, ytd, cy, cyNote, n, drivers, gHist, gpm5, opm5, k, kDef, payout, per, perHist: hp, tm, sc, sens, cumDiv,
           roic5, nc, mcap, treasury, shares, price, hasGP, startY, epsT, g1, m1, perSrc };
}

// ---------------------------------------------------------------- SVG 차트 (막대 + 선, 오른쪽 축, 로그)
function chart({ labels, bars = [], lines = [], stack = false, h = 240, yFmt = v => v, y2Fmt = v => v, log = false, est = null, zero = true }) {
  const W = 680, P = { l: 52, r: lines.some(l => l.right) ? 48 : 12, t: 12, b: 26 }, iw = W - P.l - P.r, ih = h - P.t - P.b;
  const n = labels.length; if (!n) return '';
  const left = [], right = [];
  bars.forEach(b => b.v.forEach(v => isNum(v) && left.push(v)));
  if (stack) labels.forEach((_, i) => { let p = 0, q = 0; bars.forEach(b => { const v = b.v[i]; if (isNum(v)) v >= 0 ? p += v : q += v; }); left.push(p, q); });
  lines.forEach(l => l.v.forEach(v => isNum(v) && (l.right ? right : left).push(v)));
  const rng = (a, z) => { if (!a.length) return [0, 1]; let lo = Math.min(...a), hi = Math.max(...a); if (z) { lo = Math.min(lo, 0); hi = Math.max(hi, 0); } if (lo === hi) { hi += 1; lo -= z ? 0 : 1; } const pad = (hi - lo) * 0.06; return [z && lo === 0 ? 0 : lo - pad, hi + pad]; };
  let [a0, a1] = log ? [Math.log10(Math.max(1e-9, Math.min(...left))), Math.log10(Math.max(...left))] : rng(left, zero);
  if (log) { const pd = (a1 - a0) * 0.05 || 0.1; a0 -= pd; a1 += pd; }
  const [b0, b1] = rng(right, false);
  const Y = v => P.t + ih - ((log ? Math.log10(v) : v) - a0) / (a1 - a0) * ih;
  const Y2 = v => P.t + ih - (v - b0) / (b1 - b0) * ih;
  const bw = iw / n, X = i => P.l + bw * (i + 0.5);
  let s = `<svg viewBox="0 0 ${W} ${h}" role="img">`;
  // 눈금
  const ticks = [];
  if (log) { for (let e = Math.floor(a0); e <= Math.ceil(a1); e++) [1, 2, 5].forEach(m => { const v = m * 10 ** e; const lv = Math.log10(v); if (lv >= a0 && lv <= a1) ticks.push(v); }); }
  else { const st = niceStep((a1 - a0) / 4); for (let v = Math.ceil(a0 / st) * st; v <= a1; v += st) ticks.push(+v.toFixed(10)); }
  ticks.forEach(v => { const y = Y(v); s += `<line x1="${P.l}" x2="${W - P.r}" y1="${y}" y2="${y}" stroke="var(--line)" stroke-width="1"/><text x="${P.l - 6}" y="${y + 4}" text-anchor="end" font-size="11" fill="var(--ink-3)">${esc(yFmt(v))}</text>`; });
  if (right.length) { const st = niceStep((b1 - b0) / 4); for (let v = Math.ceil(b0 / st) * st; v <= b1; v += st) { s += `<text x="${W - P.r + 6}" y="${Y2(v) + 4}" font-size="11" fill="var(--ink-3)">${esc(y2Fmt(+v.toFixed(10)))}</text>`; } }
  if (est != null && est < n) s += `<rect x="${P.l + bw * est}" y="${P.t}" width="${bw * (n - est)}" height="${ih}" fill="var(--accent-soft)" opacity=".6"/>`;
  // 막대
  const nb = bars.length, gw = bw * 0.72, ww = stack ? gw : gw / Math.max(nb, 1);
  labels.forEach((_, i) => {
    let pos = 0, neg = 0;
    bars.forEach((b, j) => {
      const v = b.v[i]; if (!isNum(v)) return;
      let y0, y1;
      if (stack) { if (v >= 0) { y0 = Y(pos); pos += v; y1 = Y(pos); } else { y0 = Y(neg); neg += v; y1 = Y(neg); } }
      else { y0 = Y(0); y1 = Y(v); }
      const x = X(i) - gw / 2 + (stack ? 0 : ww * j);
      s += `<rect x="${x + 1}" y="${Math.min(y0, y1)}" width="${Math.max(ww - 2, 1)}" height="${Math.max(Math.abs(y1 - y0), 0.5)}" fill="${b.c}" rx="1"><title>${esc(labels[i])} ${esc(b.n)}: ${esc(yFmt(v))}</title></rect>`;
    });
  });
  if (!log && a0 < 0) s += `<line x1="${P.l}" x2="${W - P.r}" y1="${Y(0)}" y2="${Y(0)}" stroke="var(--ink-3)"/>`;
  // 선
  lines.forEach(l => {
    const f = l.right ? Y2 : Y; let pth = '', on = false;
    l.v.forEach((v, i) => { if (isNum(v) && (!log || v > 0 || l.right)) { pth += (on ? 'L' : 'M') + X(i).toFixed(1) + ' ' + f(v).toFixed(1); on = true; } else on = false; });
    s += `<path d="${pth}" fill="none" stroke="${l.c}" stroke-width="${l.w || 2}" ${l.dash ? 'stroke-dasharray="4 3"' : ''}/>`;
    if (!l.noDots && n <= 40) l.v.forEach((v, i) => { if (isNum(v)) s += `<circle cx="${X(i)}" cy="${f(v)}" r="2.6" fill="${l.c}"><title>${esc(labels[i])} ${esc(l.n)}: ${esc((l.right ? y2Fmt : yFmt)(v))}</title></circle>`; });
  });
  // x 라벨
  const every = Math.ceil(n / 14);
  labels.forEach((t, i) => { if (i % every === 0 || i === n - 1) s += `<text x="${X(i)}" y="${h - 8}" text-anchor="middle" font-size="11" fill="var(--ink-3)">${esc(t)}</text>`; });
  s += '</svg>';
  const lg = bars.map(b => [b.n, b.c]).concat(lines.map(l => [l.n + (l.right ? '(오른쪽)' : ''), l.c]));
  return `<div class="chart">${s}<div class="legend">${lg.map(([t, c]) => `<span><i style="background:${c}"></i>${esc(t)}</span>`).join('')}</div></div>`;
}
function niceStep(raw) { if (!(raw > 0)) return 1; const e = 10 ** Math.floor(Math.log10(raw)), f = raw / e; return (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * e; }
const fE = v => { const e = v / 100; return Math.abs(e) >= 10000 ? (e / 10000).toLocaleString('ko-KR', { maximumFractionDigits: 1 }) + '조' : Math.round(e).toLocaleString('ko-KR'); };  // 백만원 → 억원·조원 축
const fP = v => (v * 100).toFixed(0) + '%';

// ---------------------------------------------------------------- 원고/자동 문장
function txt(s) {   // 원고 문단: 빈 줄 = 문단, "- " = 목록, **굵게**
  if (!s) return '';
  const inline = t => esc(t).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/\[([^\]]+)\]\((https?:[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  return String(s).split(/\n\s*\n/).map(b => {
    const ls = b.split('\n');
    if (ls.every(l => /^\s*[-·]\s/.test(l))) return '<ul>' + ls.map(l => `<li>${inline(l.replace(/^\s*[-·]\s/, ''))}</li>`).join('') + '</ul>';
    return `<p>${inline(b)}</p>`;
  }).join('');
}
const autoP = s => s ? `<p class="auto-p"><span class="tag">자동</span>${s}</p>` : '';
const wait = s => `<div class="wait">자료 대기 · ${s}</div>`;
function secText(key, autoHtml, waitMsg) {
  const m = S.d.manual && S.d.manual.sections && S.d.manual.sections[key];
  const body = m ? txt(m) : synth(key);
  const auto = autoHtml ? (typeof autoHtml === 'string' ? autoHtml : autoHtml.html) : '';
  const autoPart = m ? (autoHtml && autoHtml.always ? autoHtml.html : '') : auto;
  if (body || autoPart) return (body || '') + (autoPart || '');
  return waitMsg ? wait(waitMsg) : '';
}
const always = html => ({ always: true, html });
function srcBox(title, text, url) {
  if (!text) return '';
  return `<details class="src"><summary>사업보고서 원문 발췌 · ${esc(title)}${url ? ` · <a href="${esc(url)}" target="_blank" rel="noopener">DART</a>` : ''}</summary><pre>${esc(text)}</pre></details>`;
}
const biz = k => (S.d.biz || []).find(b => b.k === k);
const bizBox = (k, t) => { const b = biz(k); return b ? srcBox(t || b.title, b.text, S.d.biz_src && S.d.biz_src[0] && S.d.biz_src[0].url) : ''; };
const firstSentences = (t, n = 2) => { if (!t) return ''; const c = t.replace(/\s*\|\s*/g, ' ').replace(/\s+/g, ' ').replace(/^[^가-힣A-Za-z]*/, ''); const m = c.split(/(?<=다\.)\s*/).filter(x => x.length > 8); return m.length ? m.slice(0, n).join(' ').slice(0, 480) : c.slice(0, 300); };

// ---------------------------------------------------------------- 자료 종합(리포트 툴의 '자료 → 해석' 단계)
// 원본 리포트는 장마다 정해진 자료(사업보고서·IR·언론·연관기업)를 읽어 문단을 썼다. 여기서는 업종 대시보드 파이프라인이
// 매일 만드는 같은 종류의 자료 해석(사업보고서 발췌, IR 판독·과거 IR 비교, 뉴스 해석, 고객·경쟁사 신호)을 장별로 배치한다.
const strip = t => String(t == null ? '' : t).replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
const SRCNAME = { deep: '사업보고서·IR·언론 종합', dart: '사업보고서', ir: 'IR 자료', news: '뉴스 해석', rel: '고객·경쟁사 뉴스', rev: '최근 분기 실적·뉴스' };
const srcP = (t, k) => t ? `<p>${esc(strip(t))} <span class="srcnote">[${SRCNAME[k] || k}]</span></p>` : '';
const srcL = (arr, k) => (arr && arr.length) ? `<ul>${arr.filter(Boolean).map(x => `<li>${esc(strip(x))}</li>`).join('')}</ul><div class="srcnote">[${SRCNAME[k] || k}]</div>` : '';
const sigList = (arr, lab) => arr.length ? `<ul class="news">${arr.slice(0, 6).map(n => `<li><span class="d">${esc(n.date)}</span>${n.who ? `<b>${esc(n.who)}</b> ` : ''}<a href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.title)}</a> <small>${esc(n.office || n.src || '')}</small>${n.read ? `<div class="note">해석: ${esc(strip(n.read))}</div>` : ''}</li>`).join('')}</ul><div class="srcnote">[${lab}]</div>` : '';
function synth(key) {
  const X = (S.d && S.d.src) || {}, D = X.deep || {}, C = X.ctx || {}, F = C.facts || {}, I = X.ira || {}, V = X.rev || {};
  const E = D.explain || {}, G = D.diagnosis || {}, O = D.outlook || {}, MO = D.moat || {};
  const sig = (sec, tone) => (C.signals || []).filter(n => (!sec || n.sec === sec) && (!tone || n.tone === tone));
  const revNews = imp => (V.news || []).filter(n => n.impact === imp);
  const ex = (E.sections || []);
  switch (key) {
    case 'intro': return srcP((F.overview || []).join(' '), 'dart') + srcP(D.products, 'deep');
    case 'founding': {
      const h = (S.d.biz || []).find(b => b.k === 'history'); const t = h ? h.text.replace(/\s*\|\s*/g, ' ') : '';
      const m = t.match(/[^.]*(경영진은|대표이사)[^.]*\./); const mm = t.match(/최대주주[^.]*\./);
      return (m ? srcP(m[0], 'dart') : '') + (mm ? srcP(mm[0], 'dart') : '');
    }
    case 'value_chain': return ex[0] ? `<p><b>${esc(ex[0].h)}</b> ${esc(strip(ex[0].p))} <span class="srcnote">[${SRCNAME.deep}]</span></p>` : '';
    case 'products': return ex.slice(1).map(x => `<p><b>${esc(x.h)}</b> ${esc(strip(x.p))}</p>`).join('') + (ex.length > 1 ? `<div class="srcnote">[${SRCNAME.deep}]</div>` : '') + srcL(F.products, 'dart');
    case 'customers': return srcP(D.customers, 'deep') + srcL(F.customers, 'dart') + sigList(sig('customers'), '고객사 뉴스');
    case 'subs': return srcL(F.channel, 'dart');
    case 'strategy': {
      let h = I.summary ? srcP(I.summary, 'ir') : '';
      if (I.strategy && I.strategy.length) h += `<ul>${I.strategy.map(x => `<li><b>${esc(x.h)}</b>: ${esc(strip(x.detail))} <i>달성 가능성 ${esc(x.odds || '')}</i> — ${esc(strip(x.why))}</li>`).join('')}</ul>`;
      if (I.change && I.change.length) h += `<p><b>과거 IR과 달라진 점</b>${I.prev ? `(${esc(I.prev)} 대비)` : ''}</p>` + srcL(I.change, 'ir');
      if (I.cross && I.cross.length) h += `<p><b>연관 기업 IR로 교차 검증</b></p><ul>${I.cross.map(x => `<li>${esc(x.who)}: ${esc(strip(x.check))} (${esc(x.verdict || '')})</li>`).join('')}</ul>`;
      return h + srcL(F.strategy, 'dart');
    }
    case 'market': return srcL(G.cycle, 'deep') + (C.check && C.check.verdict ? srcP(C.check.verdict.join(' — '), 'rel') : '');
    case 'downstream': return (C.check && C.check.notes ? srcL(C.check.notes, 'rel') : '') + sigList(sig('cycle').concat(sig('outlook')), '업황·전방 뉴스');
    case 'upstream': return srcP(D.sourcing, 'deep') + srcL(F.materials, 'dart') + sigList(sig('sourcing'), '원재료 뉴스');
    case 'competition': return srcP(D.competition, 'deep') + srcL(F.competition, 'dart') + sigList(sig('competition'), '경쟁사 뉴스');
    case 'switching': return MO.reason ? srcP(MO.reason, 'deep') : '';
    case 'cost_adv': return MO.sources && MO.sources.length ? `<p>경쟁우위의 원천으로 꼽히는 것: ${MO.sources.map(esc).join(', ')}. <span class="srcnote">[${SRCNAME.deep}]</span></p>` : '';
    case 'moat_sum': return '';
    case 'ytd': return V.trend ? srcL(V.trend, 'rev') + (V.eval ? srcP(V.eval.split('이전 분석')[0], 'rev') : '') : '';
    case 'drivers_future': {
      const L = (O.upside || []).map(x => '긍정 변수: ' + x).concat((O.risks || []).map(x => '부정 변수: ' + x)).concat((V.watch || []).map(x => '확인할 것: ' + x));
      return srcP(O.summary, 'deep') + srcL(L, 'deep');
    }
    case 'bull': return sigList(revNews('pos'), '뉴스 해석') + sigList(sig(null, '+').filter(n => n.rel !== 'self'), '고객·경쟁사·업종 긍정 신호');
    case 'bear': return sigList(revNews('neg'), '뉴스 해석') + sigList(sig(null, '-'), '고객·경쟁사·업종 부정 신호');
    case 'debate': return G.summary ? `<p><b>${esc(G.verdict || '')}</b> ${esc(strip(G.summary))} <span class="srcnote">[${SRCNAME.deep}]</span></p>` + (G.structural ? srcL(G.structural, 'deep') : '') : '';
    case 'judgment': return G.summary ? `<p>업황 판단: <b>${esc(G.verdict || '')}</b>. ${esc(strip(O.summary || ''))} <span class="srcnote">[${SRCNAME.deep}]</span></p>` : '';
    default: return '';
  }
}
function synthCover() {
  const X = (S.d && S.d.src) || {}, D = X.deep || {}, V = X.rev || {}, C = (X.ctx || {}).facts || {}, G = D.diagnosis || {}, O = D.outlook || {}, MO = D.moat || {};
  if (!D.products && !C.overview) return null;
  return {
    title: D.explain && D.explain.title ? `${D.explain.title}${G.verdict ? ' · ' + G.verdict : ''}` : null,
    overview: [strip(D.products || (C.overview || []).slice(0, 2).join(' ')), MO.reason ? '경쟁우위: ' + strip(MO.reason) : ''].filter(Boolean).join(' '),
    outlook: [V.title ? strip(V.title) + '.' : '', strip((V.trend || [])[0] || ''), strip(O.summary || '')].filter(Boolean).join(' '),
  };
}
function synthPoints(risk) {
  const D = ((S.d && S.d.src) || {}).deep || {}, O = D.outlook || {}, G = D.diagnosis || {};
  const arr = risk ? (O.risks || []) : (O.upside || []);
  return arr.map((h, i) => ({ h, body: '', check: risk ? '' : (G.check || [])[i] || '' }));
}

// ---------------------------------------------------------------- 표
function table(head, rows, opts = {}) {
  const estCol = opts.estFrom;
  return `<div class="tbl"><table class="t"><thead><tr>${head.map((h, i) => `<th class="${estCol != null && i >= estCol ? 'e' : ''}">${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr class="${r.cls || ''}">${r.c.map((c, i) => `<td class="${estCol != null && i >= estCol ? 'e' : ''}">${c}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}
const yl = (M, y) => M.rows[y] && M.rows[y].est ? y + 'E' : String(y);

// ---------------------------------------------------------------- 리포트
function render() {
  const d = S.d, M = S.M = buildModel(d, S.ov), man = d.manual || {};
  if (!M) { $('#out').innerHTML = `<div class="paper"><h1>${esc(d.name)}</h1>${wait('DART 재무 자료가 아직 수집되지 않은 회사입니다. PC에서 scripts\\dart_all.bat 을 실행하면 리포트가 만들어집니다.')}${synth('intro')}${synth('products')}${synth('strategy')}</div>`; return; }
  const R = M.rows, FY = M.FY, CY = M.CY, base = M.sc[1];
  const cyRow = R[CY], nxt = R[CY + 1];
  const name = d.name, Nm = eunNeun(name);
  const toc = [];
  const H2 = (id, t) => { toc.push([id, t, 0]); return `<h2 id="${id}">${esc(t)}</h2>`; };
  const H3 = (id, t) => { toc.push([id, t, 1]); return `<h3 class="sec" id="${id}">${esc(t)}</h3>`; };
  const A = d.annual || {};
  const hy = M.yrs.slice(-10).map(Number);
  const opChg = (a, b) => R[a] && R[b] && R[a].op ? R[b].op / R[a].op - 1 : null;

  // ---- 자동 문장 재료
  const rev10 = hy.length > 1 ? Math.pow(R[FY].rev / R[hy[0]].rev, 1 / (hy.length - 1)) - 1 : null;
  const ytdTxt = M.ytd ? `${CY}년 1~${M.n}분기 매출은 ${eok(M.ytd.rev)}억원으로 ${sg(M.ytd.rev / M.ytd.prev_rev - 1)}, 영업이익은 ${eok(M.ytd.op)}억원으로 ${M.ytd.prev_op > 0 ? sg(M.ytd.op / M.ytd.prev_op - 1) : '흑자 전환'} 변했습니다.` : '';
  const qk = Object.keys(d.quarterly || {}).sort();
  const lq = qk[qk.length - 1], Q = d.quarterly || {};
  const gpmQ = k => Q[k] && Q[k].rev && isNum(Q[k].gp) ? Q[k].gp / Q[k].rev : null;
  const opmQ = k => Q[k] && Q[k].rev ? Q[k].op / Q[k].rev : null;
  const prev4 = qk.slice(-5, -1);
  const gpmLqTxt = lq && isNum(gpmQ(lq)) ? `최근 분기(${lq}) 매출총이익률은 ${pct(gpmQ(lq))}로 직전 4개 분기 평균보다 ${pp(gpmQ(lq) - mean(prev4.map(gpmQ)))} ${gpmQ(lq) >= mean(prev4.map(gpmQ)) ? '높습니다' : '낮습니다'}.` : (lq ? `최근 분기(${lq}) 영업이익률은 ${pct(opmQ(lq))}입니다.` : '');
  const d1 = M.drivers[0];
  const fwdPer = nxt && nxt.per, cyPer = cyRow && cyRow.per;
  const histPerAvg = M.tm;
  const verdict = base.ret == null ? '' : base.ret >= 0.12 && M.sc[0].ret > -0.05 ? '장기 투자를 시작할 만한 가격입니다' : base.ret >= 0.07 ? '기대수익률이 시장 평균 수준이라 조건을 확인하며 나눠 사는 편이 맞습니다' : '기대수익률이 낮아 서두를 이유가 크지 않습니다';

  // ---- 표지
  let h = '';
  const SC = synthCover();
  const title = man.title || (SC && SC.title) || autoTitle(d, M);
  h += `<section class="paper" id="cover">
    <div class="kicker">${esc(d.industry_name)} · ${esc(d.group || '')} · ${esc(d.market || '')} ${esc(d.code)}</div>
    <h1>${esc(name)}<br><span style="font-size:.72em">${esc(title)}</span></h1>
    <div class="byline">${esc(name)} · ${esc(man.asof || d.built)} 기준 · ${man.cover ? '원고 + 자동 계산' : '자료 종합 + 자동 계산'}${man.cover ? '<span class="badge">원고</span>' : '<span class="badge auto">자동 생성</span>'} · 주가 ${esc(d.price_time || '')}</div>
    <div class="cover"><div>
      <h3>개요</h3>${man.cover && man.cover.overview ? txt(man.cover.overview) : (SC && SC.overview ? `<p>${esc(SC.overview)} <span class="srcnote">[사업보고서·IR·언론 종합]</span></p>` : '') + autoP(`${Nm} ${esc(d.industry_name)} 업종(${esc(d.group || '')})의 ${esc(d.market || '')} 상장사입니다. ${esc(firstSentences(biz('overview') && biz('overview').text, 2))} ${FY}년 매출은 ${eok(R[FY].rev)}억원, 영업이익률 ${pct(R[FY].opm)}이고${isNum(rev10) ? `, ${hy[0]}~${FY}년 매출은 연평균 ${sg(rev10, 1)} 변했습니다` : ''}.`)}
      <h3>전망</h3>${man.cover && man.cover.outlook ? txt(man.cover.outlook) : (SC && SC.outlook ? `<p>${esc(SC.outlook)} <span class="srcnote">[최근 실적·뉴스 해석]</span></p>` : '') + autoP(`${ytdTxt} ${gpmLqTxt} 기본 가정은 ${d1 ? `${d1.y}년 매출 ${sg(d1.g)}${M.hasGP ? `, 매출총이익률 ${pct(d1.m)}` : `, 영업이익률 ${pct(d1.m)}`}로 영업이익 ${eok(R[d1.y].op)}억원(${sg(opChg(d1.y - 1, d1.y))})` : ''}입니다.`)}
      <h3>투자의견</h3>${man.cover && man.cover.opinion ? txt(man.cover.opinion) : autoP(`${isNum(fwdPer) ? `주가는 ${CY + 1}년 추정 PER ${x1(fwdPer)}배로 과거 연말 PER 평균(${x1(histPerAvg)}배)보다 ${fwdPer < histPerAvg ? '낮습니다' : '높습니다'}. ` : ''}5년 기대수익률은 기본 연 ${pct(base.ret)}, 비관 ${pct(M.sc[0].ret)}, 낙관 ${pct(M.sc[2].ret)}로 ${verdict}.`)}
    </div><table class="stats"><tbody>${statRows(d, M).map(([a, b]) => `<tr><td>${a}</td><td>${b}</td></tr>`).join('')}</tbody></table></div>
    ${summaryTable(d, M)}
  </section>`;

  // ---- 1. 기업 개요
  let s1 = H2('s1', '기업 개요');
  s1 += H3('s1-intro', '회사 소개') + secText('intro', always(autoP(`${esc(firstSentences(biz('overview') && biz('overview').text, 3))}`) + bizBox('overview')), '이 회사는 사업보고서 본문을 아직 받지 못했습니다(다음 DART 수집 때 채워집니다).');
  s1 += H3('s1-founding', '창업 배경과 경영진') + secText('founding', d.dart_sections && d.dart_sections.executives ? always(srcBox('임원 현황', d.dart_sections.executives, d.dart_sections.url)) : null, '창업 배경·경영진은 사업보고서 임원 현황(PC 추가 수집) 후 채워집니다.');
  const histTxt = (d.dart_sections && d.dart_sections.history) || (biz('history') && biz('history').text);
  s1 += H3('s1-history', '연혁') + secText('history', histTxt ? always(srcBox('회사의 연혁', histTxt)) : null, '연혁 원문은 PC 추가 수집(scripts\\report_dart.bat) 후 표시됩니다.') + revChart(M, hy);
  s1 += H3('s1-holders', '주주 구성과 주주 친화도') + secText('holders', always(holdersBlock(d, M)));
  s1 += H3('s1-price', '장기 주가') + secText('price', always(priceBlock(d)));

  // ---- 2. 사업 구조
  let s2 = H2('s2', '사업 구조');
  s2 += H3('s2-chain', '가치사슬 내 사업 영역') + secText('value_chain', null, '고객 공정(가치사슬) 가운데 이 회사 제품이 들어가는 단계를 원고에서 그림·글로 설명합니다.');
  s2 += H3('s2-products', '제품군') + secText('products', always(bizBox('products')), '주요 제품별 쓰임새·기술을 전문가 수준으로 설명합니다.');
  s2 += H3('s2-mix', '매출 구성의 변화') + secText('mix', always(segBlock(d, M, hy)));
  s2 += H3('s2-cust', '고객') + secText('customers', always(bizBox('sales', '매출 및 수주상황(매출처)')), '');
  s2 += H3('s2-subs', '해외 법인과 자회사') + secText('subs', null, '연결 주석의 종속기업 요약재무정보(법인별 매출·순이익)를 원고에서 정리합니다.');
  s2 += H3('s2-essence', '이 사업의 본질') + secText('essence', always(essenceBlock(M, hy)));
  s2 += H3('s2-cost', '손익과 비용 구조') + secText('cost', always(costBlock(d, M, hy)));
  s2 += H3('s2-cap', '생산능력') + secText('capacity', always((d.biz_kpi && d.biz_kpi.utilization ? autoP(`사업보고서에 적힌 가동률은 ${d.biz_kpi.utilization.map(v => v + '%').join(', ')}입니다.`) : '') + bizBox('materials', '원재료 및 생산설비')));
  s2 += H3('s2-strategy', '회사의 전략') + secText('strategy', always(irBlock(d) + bizBox('rnd', '연구개발활동')));

  // ---- 3. 산업 구조
  let s3 = H2('s3', '산업 구조');
  s3 += H3('s3-market', '시장 규모와 성장') + secText('market', null, '시장 규모·성장률은 두 곳 이상 기관 수치로 씁니다.');
  s3 += H3('s3-down', '전방 산업') + secText('downstream', null, '고객사의 증설·생산 계획을 일정과 출처로 씁니다.');
  s3 += H3('s3-up', '후방 산업: 원재료') + secText('upstream', always(bizBox('materials', '주요 원재료 가격변동 추이')));
  s3 += H3('s3-comp', '경쟁 구도') + secText('competition', always(bizBox('etc', '산업의 특성·시장점유율')));

  // ---- 4. 해자
  let s4 = H2('s4', '해자');
  s4 += H3('s4-peers', '경쟁사 비교') + peersBlock(d, M) + secText('peers', null, '');
  s4 += H3('s4-switch', '전환 비용과 고객 승인') + secText('switching', null, '고객이 공급사를 바꾸기 어려운 이유(승인·수율·비용 비중)를 씁니다.');
  s4 += H3('s4-costadv', '원가 경쟁력') + secText('cost_adv', null, '원재료 조달·재생·내재화 등 원가 우위의 근거를 씁니다.');
  s4 += H3('s4-pricing', '규모와 가격 결정력') + secText('pricing', always(pricingBlock(d, M)));
  s4 += H3('s4-roic', 'ROIC로 본 경쟁력') + secText('roic', always(roicBlock(M, hy)));
  s4 += secText('moat_sum', autoP(moatSummary(d, M)));

  // ---- 5. 재무 분석
  let s5 = H2('s5', '재무 분석');
  s5 += H3('s5-capex', '설비 투자와 차입') + secText('capex', always(cfBlock(d, M, hy)));
  s5 += H3('s5-wc', '운전자본') + secText('wc', always(wcBlock(d, hy)));
  s5 += H3('s5-oneoff', '손상과 일회성 비용의 역사') + secText('oneoff', always(oneoffBlock(M, hy)));
  s5 += H3('s5-alloc', '자본 배분') + secText('alloc', always(allocBlock(d, M, hy)));

  // ---- 6. 실적 및 전망
  let s6 = H2('s6', '실적 및 전망');
  s6 += H3('s6-past', '과거 실적의 변화 요인') + secText('drivers_past', always(pastDrivers(M, hy)));
  s6 += H3('s6-analog', '과거 유사 충격 사례') + secText('analog', always(analogBlock(d)));
  s6 += H3('s6-ytd', `${CY}년 실적`) + secText('ytd', always(autoP(`${ytdTxt} ${gpmLqTxt} ${M.cyNote ? `연간 추정: ${M.cyNote} → 매출 ${eok(cyRow && cyRow.rev)}억원, 영업이익 ${eok(cyRow && cyRow.op)}억원, 지배순이익 ${eok(cyRow && cyRow.ni)}억원.` : ''}`) + quarterChart(d)));
  s6 += H3('s6-future', '향후 변화 요인') + secText('drivers_future', always(driverTable(M)), '');
  s6 += H3('s6-fc', '추정 실적') + forecastBlock(M) + secText('forecast', null, '');
  s6 += H3('s6-cons', '가이던스와 컨센서스 비교') + secText('consensus', consensusBlock(d, M), '컨센서스 기록(매일 자동 수집)과 증권사 목표주가 기사가 아직 없습니다.');

  // ---- 7. 시장의 시각
  const nb = newsBuckets(d);
  let s7 = H2('s7', '시장의 시각');
  s7 += H3('s7-bull', '긍정적인 시각') + secText('bull', nb.pos.length ? always(newsList(nb.pos, '긍정 신호 기사')) : null, '');
  s7 += H3('s7-bear', '부정적인 시각') + secText('bear', nb.neg.length ? always(newsList(nb.neg, '부정 신호 기사')) : null, '');
  s7 += H3('s7-debate', '업황 논쟁') + secText('debate', null, '업황 정점·저점 논쟁과 이 회사에 중요한 변수(가격이냐 물량이냐)를 씁니다.');
  s7 += H3('s7-retail', '개인 투자자와 외국 주주') + secText('retail', always(attentionBlock(d)));
  s7 += H3('s7-disc', '경쟁사 대비 할인·할증 이유') + secText('discount', always(autoP(discountTxt(d, M))));

  // ---- 8. 투자포인트, 9. 리스크
  let s8 = H2('s8', '투자포인트') + points(man.points && man.points.length ? man.points : synthPoints(false).concat(autoPoints(d, M).filter(p => p.h !== '두드러진 숫자 신호 없음')), autoPoints(d, M), false, !(man.points && man.points.length));
  let s9 = H2('s9', '리스크') + points(man.risks && man.risks.length ? man.risks : synthPoints(true).concat(autoRisks(d, M)), autoRisks(d, M), true, !(man.risks && man.risks.length));

  // ---- 10. 결론
  let s10 = H2('s10', '결론');
  s10 += H3('s10-judge', '장기 투자 판단') + secText('judgment', autoP(`${moatSummary(d, M)} ${isNum(fwdPer) ? `선행 PER은 ${x1(fwdPer)}배입니다.` : ''}`));
  s10 += H3('s10-er', '5년 기대수익률') + erBlock(M) + secText('er', null, '') + assumePanel(M);
  s10 += H3('s10-how', '투자 방법') + secText('how', autoP(howTxt(d, M)));

  // ---- 부록
  let ap = H2('ap', '부록: 수익모델');
  ap += H3('ap-annual', '연간실적') + annualTable(d, M);
  ap += H3('ap-q', '분기실적') + quarterTable(d);
  ap += H3('ap-bs', '재무상태표') + bsTable(d, hy);
  ap += H3('ap-cf', '현금흐름표') + cfTable(d, M, hy);
  ap += H3('ap-sens', `${M.sens ? M.sens.y : ''}E 영업이익 민감도`) + sensTable(M);
  ap += sourcesBlock(d);

  const secs = [s1, s2, s3, s4, s5, s6, s7, s8, s9, s10, ap].map(x => `<section class="paper">${x}</section>`).join('');
  $('#out').innerHTML = h + secs;
  $('#toc').innerHTML = `<a href="#cover"><b>${esc(name)}</b></a>` + toc.map(([id, t, l]) => `<a class="${l ? 'sub' : ''}" href="#${id}">${esc(t)}</a>`).join('');
  const chips = toc.filter(t => !t[2]).map(([id, t]) => `<a href="#${id}">${esc(t)}</a>`).join('');
  $('#out').insertAdjacentHTML('afterbegin', `<div class="chips">${chips}</div>`);
  bindAssume();
}

function autoTitle(d, M) {
  const R = M.rows, f = M.drivers[0];
  const opTrend = f && R[f.y] && R[M.startY] && R[M.startY].op > 0 ? R[f.y].op / R[M.startY].op - 1 : null;
  const word = opTrend == null ? '실적 점검' : opTrend > 0.15 ? '이익이 늘어나는 구간' : opTrend > 0 ? '완만한 이익 성장' : '이익 둔화 구간';
  return `${d.group || d.industry_name} · ${word}의 ${d.industry_name} 회사`;
}

function statRows(d, M) {
  const R = M.rows, L = d.latest, last = R[M.FY];
  const dps = last && last.dps;
  const yld = isNum(dps) && M.price ? dps / M.price : (isNum(d.div_yield) ? d.div_yield / 100 : null);
  const eq = d.bs_latest && d.bs_latest.equity;
  return [
    [`주가(${esc((d.price_time || '').slice(5, 10))})`, won(M.price)],
    ['시가총액(억원)', eok(M.mcap)],
    ['결산월', esc((d.manual && d.manual.fiscal_month) || 12)],
    [`순현금(${esc(M.nc ? M.nc.p : '')}, 억원)`, M.nc ? eok(M.nc.v) : '–'],
    ['자사주 비중', isNum(M.treasury) ? pct(M.treasury) : '–'],
    [`배당수익률(${M.FY} DPS)`, pct(yld)],
    [`평균 ROIC(${M.FY - 4}~${M.FY})`, M.roic5 != null ? pct(M.roic5) : '<span title="PC 추가 수집 후 계산">수집 대기</span>'],
    [`PER(${M.CY}E)`, x1(R[M.CY] && R[M.CY].per)],
    [`12개월 선행 PER(${M.CY + 1}E)`, x1(R[M.CY + 1] && R[M.CY + 1].per)],
    [`PBR(${esc((d.bs_latest || {}).period || '')})`, eq > 0 && M.mcap ? x1(M.mcap / eq) : '–'],
    ['기본 기대수익률(연)', `<b>${pct(M.sc[1].ret)}</b>`],
  ];
}

function summaryTable(d, M) {
  const R = M.rows;
  const ys = M.allY.filter(y => y >= M.FY - 4 && y <= M.CY + 2);
  const seg = (d.manual && d.manual.segments) || null;
  const rows = [
    { c: ['매출액', ...ys.map(y => eok(R[y].rev))] },
    ...(seg ? seg.map(s => ({ cls: 'ind', c: [esc(s.label), ...ys.map(y => isNum(s.values[y]) ? eok(s.values[y] * 100) : '–')] })) : []),
    { c: ['영업이익', ...ys.map(y => eok(R[y].op))] },
    { c: ['영업이익률', ...ys.map(y => pct(R[y].opm))] },
    { c: ['지배주주 순이익', ...ys.map(y => eok(R[y].ni))] },
    { c: ['EPS(원)', ...ys.map(y => won(R[y].eps))] },
    { c: ['DPS(원)', ...ys.map(y => won(R[y].dps))] },
    { c: ['ROE', ...ys.map(y => pct(R[y].roe))] },
    { c: ['PER(배)', ...ys.map(y => x1(R[y].per))] },
  ];
  const ef = ys.findIndex(y => R[y].est);
  return `<div style="margin-top:16px">${table(['억원', ...ys.map(y => yl(M, y))], rows, { estFrom: ef < 0 ? null : ef + 1 })}</div><div class="note">${R[M.CY] && R[M.CY].partial ? `${M.CY}E = ${esc(M.cyNote)}. ` : ''}추정 연도 PER은 현재 주가 기준, 과거는 연말 종가 ÷ EPS(현재 주식수 기준). 음영은 추정.</div>`;
}

function revChart(M, hy) {
  const R = M.rows, ys = hy.concat(M.allY.filter(y => R[y].est && y <= M.CY + 2));
  return chart({ labels: ys.map(y => yl(M, y)), bars: [{ n: '매출액(억원)', v: ys.map(y => R[y].rev), c: 'var(--s1)' }], lines: [{ n: '영업이익률', v: ys.map(y => R[y].opm), c: 'var(--s2)', right: true }], yFmt: fE, y2Fmt: fP, est: ys.findIndex(y => R[y].est) }) + `<div class="cap">연간 매출과 영업이익률(음영은 추정). 자료: DART 연결 재무제표, 수익모델</div>`;
}

function holdersBlock(d, M) {
  let s = '';
  const H = d.holders, m5 = d.major5 || [];
  const R = M.rows;
  const pays = M.yrs.slice(-5).map(y => R[y].dps && R[y].eps > 0 ? R[y].dps / R[y].eps : null).filter(isNum);
  const parts = [];
  if (H) parts.push(`최대주주 측(특수관계인 포함) 지분은 ${H.total}%(${H.year}년 말)입니다`);
  const ext = m5.filter(x => !H || !H.list.some(h => h.nm === x.nm));
  if (ext.length) parts.push(`5% 이상 대량보유 신고자는 ${ext.slice(0, 3).map(x => `${esc(x.nm)}(${x.pct}%, ${esc(x.date)})`).join(', ')} 등입니다`);
  if (isNum(M.treasury)) parts.push(`자사주는 발행주식의 ${pct(M.treasury)}입니다`);
  if (pays.length) parts.push(`최근 ${pays.length}년 평균 배당성향은 ${pct(mean(pays))}입니다`);
  if (parts.length) s += autoP(parts.join('. ') + '.');
  if (H && H.list.length) s += table(['주주', '관계', '지분율'], H.list.slice(0, 8).map(x => ({ c: [esc(x.nm), esc(x.rel), x.pct + '%'] })));
  if (!H) s += wait('최대주주·5% 주주·배당 이력은 PC에서 scripts\\report_dart.bat 실행 후 자동으로 채워집니다.');
  return s;
}

function priceBlock(d) {
  const p = d.prices; if (!p || !p.months || !p.months.length) return wait('월말 주가 자료가 없습니다.');
  const c = p.close, ms = p.months;
  let hi = 0, lo = 0; c.forEach((v, i) => { if (v > c[hi]) hi = i; if (v < c[lo]) lo = i; });
  let mdd = 0, pk = c[0], mddAt = 0; c.forEach((v, i) => { pk = Math.max(pk, v); const dd = v / pk - 1; if (dd < mdd) { mdd = dd; mddAt = i; } });
  const yrsN = (ms.length - 1) / 12, cagr = yrsN > 0 ? Math.pow(c[c.length - 1] / c[0], 1 / yrsN) - 1 : null;
  const cur = S.M.price || c[c.length - 1];
  return chart({ labels: ms, lines: [{ n: '월말 종가(원, 로그)', v: c, c: 'var(--s1)', noDots: true }], log: true, yFmt: v => v >= 1e4 ? (v / 1e4) + '만' : v.toLocaleString() }) +
    autoP(`${ms[0]} 이후 주가는 연 ${sg(cagr, 1)} 변했습니다. 최고가는 ${ms[hi]} ${won(c[hi])}원, 최저가는 ${ms[lo]} ${won(c[lo])}원이고, 가장 크게 빠진 구간은 ${ms[mddAt]}까지 고점 대비 ${pct(mdd, 0)}였습니다. 현재 주가는 최고가 대비 ${sg(cur / c[hi] - 1)}입니다.`) +
    `<div class="cap">월말 종가(로그 눈금). 주요 변동 원인은 원고에서 기사로 정리합니다.</div>`;
}

function segBlock(d, M, hy) {
  const seg = d.manual && d.manual.segments;
  if (!seg) return revChart(M, hy).replace('<div class="cap">', '<div class="cap">부문별 매출은 원고(config/report)에 넣으면 누적 막대로 나뉩니다. ');
  const R = M.rows, ys = Object.keys(seg[0].values).map(Number).sort((a, b) => a - b);
  const cs = ['var(--s1)', 'var(--s4)', 'var(--s3)', 'var(--s5)', 'var(--s6)'];
  return chart({ labels: ys.map(y => yl(M, y)), stack: true, bars: seg.map((s, i) => ({ n: s.label, v: ys.map(y => isNum(s.values[y]) ? s.values[y] * 100 : null), c: cs[i % cs.length] })), lines: [{ n: '영업이익률', v: ys.map(y => R[y] ? R[y].opm : null), c: 'var(--s2)', right: true }], yFmt: fE, y2Fmt: fP, est: ys.findIndex(y => R[y] && R[y].est) }) + `<div class="cap">부문별 매출(억원)과 영업이익률. 자료: ${esc(d.manual.segments_src || '사업보고서·회사 IR')}</div>`;
}

function opBridge(M, y) {   // 영업이익 변화 = 물량(매출 변화×전년 이익률) + 이익률(올해 매출×이익률 변화) [+ 판관비]
  const R = M.rows, a = R[y - 1], b = R[y];
  if (!a || !b) return null;
  if (M.hasGP && isNum(a.gp) && isNum(b.gp)) {
    const vol = (b.rev - a.rev) * a.gpm, mar = b.rev * (b.gpm - a.gpm), sga = -((b.gp - b.op) - (a.gp - a.op));
    return { d: b.op - a.op, vol, mar, sga };
  }
  return { d: b.op - a.op, vol: (b.rev - a.rev) * a.opm, mar: b.rev * (b.opm - a.opm), sga: 0 };
}

function essenceBlock(M, hy) {
  let sv = 0, sm = 0, ss = 0;
  hy.slice(1).forEach(y => { const b = opBridge(M, y); if (b) { sv += Math.abs(b.vol); sm += Math.abs(b.mar); ss += Math.abs(b.sga); } });
  const tot = sv + sm + ss; if (!tot) return '';
  const top = [['매출(물량·판가) 변화', sv], [M.hasGP ? '매출총이익률(원가) 변화' : '영업이익률 변화', sm], ['판관비(고정비) 변화', ss]].sort((a, b) => b[1] - a[1]);
  const gs = hy.map(y => M.rows[y].gpm).filter(isNum);
  return autoP(`${hy[0]}~${hy[hy.length - 1]}년 영업이익 변화량을 매출 효과·이익률 효과·판관비 효과로 나누면, ${top[0][0]}가 ${pct(top[0][1] / tot, 0)}, ${top[1][0]}가 ${pct(top[1][1] / tot, 0)}, ${top[2][0]}가 ${pct(top[2][1] / tot, 0)}를 설명합니다. 이 회사의 이익은 무엇보다 '${top[0][0]}'에 달려 있습니다.${gs.length > 3 ? ` 매출총이익률은 이 기간 ${pct(Math.min(...gs))}~${pct(Math.max(...gs))} 사이에서 움직였습니다.` : ''}`) +
    `<div class="note">계산: 매출 효과 = Δ매출 × 전년 매출총이익률, 이익률 효과 = 당해 매출 × Δ매출총이익률, 판관비 효과 = −Δ판관비 (연도별 절댓값 합).</div>`;
}

function costBlock(d, M, hy) {
  const R = M.rows, A = d.annual, f = M.FY, a = A[f] || {};
  const parts = [];
  if (M.hasGP) parts.push(`${f}년 매출원가율은 ${pct(1 - R[f].gpm)}, 판관비율은 ${pct((R[f].gp - R[f].op) / R[f].rev)}입니다`);
  const dep = hy.filter(y => isNum((A[y] || {}).dep));
  if (dep.length >= 2) parts.push(`감가상각비는 ${dep[0]}년 ${eok(A[dep[0]].dep)}억원에서 ${dep[dep.length - 1]}년 ${eok(A[dep[dep.length - 1]].dep)}억원으로 ${A[dep[dep.length - 1]].dep > A[dep[0]].dep * 1.5 ? '크게 늘어 고정비가 이미 들어와 있습니다 — 물량이 늘면 이익률이 빠르게 오를 수 있는 구조입니다' : '큰 변화가 없습니다'}`);
  let s = parts.length ? autoP(parts.join('. ') + '.') : '';
  if (M.hasGP) s += chart({ labels: hy.map(String), bars: [], lines: [{ n: '매출원가율', v: hy.map(y => 1 - R[y].gpm), c: 'var(--s1)' }, { n: '판관비율', v: hy.map(y => (R[y].gp - R[y].op) / R[y].rev), c: 'var(--s4)' }, { n: '영업이익률', v: hy.map(y => R[y].opm), c: 'var(--s2)' }], yFmt: fP, zero: false, h: 200 });
  return s;
}

function irBlock(d) {
  if (!d.ir || !d.ir.length) return '';
  return `<div class="note">최근 IR 자료 원문: ${d.ir.slice(0, 4).map(x => `<a href="${esc(x.pdf || x.page)}" target="_blank" rel="noopener">${esc(x.date)} ${esc((x.title || '').replace(d.name + ', ', ''))}</a>`).join(' · ')}</div>`;
}

function peersBlock(d, M) {
  const ps = (d.peers || []).map(p => ({ ...p, opm: p.rev ? p.op / p.rev : null, roe: p.equity > 0 && isNum(p.ni) ? p.ni / p.equity : null, per: p.ni > 0 && p.mcap ? p.mcap / p.ni : null }));
  if (ps.length < 2) return wait('같은 업종 비교 대상이 부족합니다.');
  const rows = ps.map(p => ({ cls: p.self ? 'self' : '', c: [esc(p.name), eok(p.mcap), eok(p.rev), pct(p.opm), eok(p.ni), pct(p.roe), x1(p.per), esc(p.fy || '')] }));
  const others = ps.filter(p => !p.self);
  const me = ps[0];
  const mo = median(others.map(p => p.opm)), mr = median(others.map(p => p.roe)), mp = median(others.map(p => p.per).filter(v => v < 80));
  const t = autoP(`비교 대상 ${others.length}곳의 중앙값과 비교하면 영업이익률은 ${pct(me.opm)} 대 ${pct(mo)}(${pp(me.opm - mo)}), ROE는 ${pct(me.roe)} 대 ${pct(mr)}, PER은 ${x1(me.per)}배 대 ${x1(mp)}배입니다. ${isNum(me.per) && isNum(mp) ? (me.per < mp ? (me.roe > mr ? 'ROE가 높은데도 PER이 낮아 할인돼 있습니다.' : '이익률·ROE가 낮은 만큼 PER도 낮습니다.') : (me.roe > mr ? '높은 수익성만큼 PER도 높습니다.' : '수익성에 비해 PER이 높아 기대가 먼저 반영돼 있습니다.')) : ''}`);
  return table(['회사', '시가총액', `매출`, '영업이익률', '지배순이익', 'ROE', 'PER', '사업연도'], rows) + `<div class="note">억원. 같은 업종 대시보드의 같은 그룹 회사(부족하면 같은 업종) 시가총액 순. ROE = 최근 사업연도 지배순이익 ÷ 최근 분기말 지배주주지분, PER = 현재 시가총액 ÷ 최근 사업연도 지배순이익.</div>` +
    chart({ labels: ps.map(p => p.name.length > 7 ? p.name.slice(0, 7) : p.name), bars: [{ n: '영업이익률', v: ps.map(p => p.opm), c: 'var(--s1)' }, { n: 'ROE', v: ps.map(p => p.roe), c: 'var(--s3)' }], yFmt: fP, h: 220 }) + t;
}

function pricingBlock(d, M) {
  const Q = d.quarterly || {}, ks = Object.keys(Q).sort();
  const g = ks.map(k => Q[k].rev && isNum(Q[k].gp) ? Q[k].gp / Q[k].rev : Q[k].rev ? Q[k].op / Q[k].rev : null).filter(isNum);
  const sd = std(g);
  if (sd == null) return '';
  const lab = M.hasGP ? '매출총이익률' : '영업이익률';
  return autoP(`${ks[0]}~${ks[ks.length - 1]} 분기 ${lab}의 표준편차는 ${(sd * 100).toFixed(1)}%p입니다. ${sd > 0.03 ? '원가·판가 변화가 이익률에 그대로 드러나 가격 결정력이 강하다고 보기 어렵습니다.' : sd > 0.015 ? '이익률이 어느 정도 흔들려 원가 전가에 시차가 있는 편입니다.' : '이익률이 안정적이어서 원가 변화를 판가로 넘기는 힘이 있는 편입니다.'}`);
}

function roicBlock(M, hy) {
  const R = M.rows, v = hy.map(y => R[y].roic);
  if (v.filter(isNum).length < 2) return wait('ROIC = 영업이익×(1−24.2%) ÷ 평균(자본총계+순차입금). 과거 재무상태표가 필요해 PC에서 scripts\\report_dart.bat 실행 후 계산됩니다.') + (hy.some(y => isNum(R[y].roe)) ? '' : '');
  const good = v.filter(x => isNum(x) && x > COST_OF_CAPITAL).length;
  return chart({ labels: hy.map(String), lines: [{ n: 'ROIC', v, c: 'var(--s1)' }, { n: '자본비용 8%', v: hy.map(() => COST_OF_CAPITAL), c: 'var(--ink-3)', dash: true, noDots: true }], yFmt: fP, zero: true, h: 200 }) +
    autoP(`${hy[0]}~${hy[hy.length - 1]}년 중 ${good}개 해에 ROIC가 자본비용(8% 가정)을 넘었고, 최근 5년 평균은 ${pct(M.roic5)}입니다.`) + `<div class="cap">ROIC = 영업이익×(1−24.2%) ÷ 평균 투하자본(자본총계 + 순차입금). 자료: 수익모델</div>`;
}

function moatSummary(d, M) {
  const ps = (d.peers || []).filter(p => !p.self && p.rev).map(p => p.op / p.rev);
  const me = M.rows[M.FY].opm, mo = median(ps);
  const r5 = M.roic5;
  const strong = (isNum(r5) ? r5 > 0.12 : M.rows[M.FY].roe > 0.12) && isNum(mo) && me > mo;
  const weak = (isNum(r5) ? r5 < COST_OF_CAPITAL : true) && isNum(mo) && me < mo;
  return `${eunNeun(d.name)} ${isNum(r5) ? `5년 평균 ROIC ${pct(r5)}` : `최근 영업이익률 ${pct(me)}`}${isNum(mo) ? `, 경쟁사 중앙값 대비 영업이익률 ${pp(me - mo)}` : ''}로 볼 때 ${strong ? '숫자로 확인되는 해자가 있는 편입니다' : weak ? '숫자로는 해자를 확인하기 어렵고 업황에 기대는 편입니다' : '강한 독점력은 아니지만 일정 수준의 경쟁력은 있는 편입니다'}.`;
}

function cfBlock(d, M, hy) {
  const A = d.annual || {};
  const ys = hy.filter(y => isNum((A[y] || {}).ocf));
  if (ys.length < 2) return wait('영업활동현금흐름·설비투자·순현금 10년 추이는 PC 추가 수집 후 표시됩니다.');
  const fcf = ys.map(y => A[y].ocf - (A[y].capex || 0));
  const nc = ys.map(y => isNum(A[y].debt) ? (A[y].cash || 0) + (A[y].st_fin || 0) - A[y].debt : null);
  const so = ys.reduce((s, y) => s + A[y].ocf, 0), sc = ys.reduce((s, y) => s + (A[y].capex || 0), 0);
  const negs = fcf.filter(v => v < 0).length;
  return chart({ labels: ys.map(String), bars: [{ n: '영업활동현금흐름', v: ys.map(y => A[y].ocf), c: 'var(--s1)' }, { n: '설비투자', v: ys.map(y => -(A[y].capex || 0)), c: 'var(--s6)' }], lines: [{ n: 'FCF', v: fcf, c: 'var(--s3)' }, { n: '순현금', v: nc, c: 'var(--s2)' }], yFmt: fE }) +
    autoP(`${ys[0]}~${ys[ys.length - 1]}년 영업활동현금흐름 합계는 ${eok(so)}억원, 설비투자는 ${eok(sc)}억원으로 ${so >= sc ? '번 돈 안에서 투자했습니다' : '투자가 번 돈보다 많았습니다'}. ${ys.length}년 중 ${negs}년은 FCF가 마이너스였고, 순현금은 ${ys[0]}년 ${eok(nc[0])}억원에서 ${ys[ys.length - 1]}년 ${eok(nc[nc.length - 1])}억원이 됐습니다.${M.nc ? ` 최근(${M.nc.p}) 순현금은 ${eok(M.nc.v)}억원입니다.` : ''}`) +
    `<div class="cap">FCF = 영업활동현금흐름 − 유형자산 취득. 순현금 = 현금성자산 + 단기금융상품 − 차입금·사채(리스부채 제외).</div>`;
}

function days(A, y) {
  const a = A[y] || {}; if (!a.rev) return {};
  const cogs = isNum(a.cogs) ? a.cogs : (isNum(a.gp) ? a.rev - a.gp : null);
  const o = { ar: isNum(a.ar) ? a.ar / a.rev * 365 : null, inv: isNum(a.inv) && cogs ? a.inv / cogs * 365 : null, ap: isNum(a.ap) && cogs ? a.ap / cogs * 365 : null };
  o.ccc = isNum(o.ar) && isNum(o.inv) && isNum(o.ap) ? o.ar + o.inv - o.ap : null;
  return o;
}
function wcBlock(d, hy) {
  const A = d.annual || {}, ys = hy.filter(y => isNum((A[y] || {}).ar));
  if (ys.length < 2) return wait('매출채권·재고·매입채무 회전일수는 PC 추가 수집 후 계산됩니다.');
  const D = ys.map(y => days(A, y)), l = D[D.length - 1];
  const minAr = Math.min(...D.map(x => x.ar).filter(isNum));
  return table(['일', ...ys.map(String)], [['매출채권 회전일수', 'ar'], ['재고자산 회전일수', 'inv'], ['매입채무 회전일수', 'ap'], ['현금전환주기', 'ccc']].map(([n, k]) => ({ c: [n, ...D.map(x => isNum(x[k]) ? Math.round(x[k]) : '–')] }))) +
    autoP(`${ys[ys.length - 1]}년 매출채권 회전일수는 ${Math.round(l.ar)}일${Math.round(l.ar) <= Math.round(minAr) ? '로 기간 중 가장 짧고' : ''}, 재고 회전일수는 ${isNum(l.inv) ? Math.round(l.inv) + '일' : '–'}, 현금전환주기는 ${isNum(l.ccc) ? Math.round(l.ccc) + '일' : '–'}입니다.`);
}

function oneoffBlock(M, hy) {
  const R = M.rows;
  const ev = hy.filter(y => R[y].op > 0 && isNum(R[y].ni) && (R[y].ni < 0 || R[y].ni / R[y].op < Math.min(0.4, M.kDef * 0.5)));
  const q4 = [];
  const Q = S.d.quarterly || {};
  Object.keys(Q).filter(k => k.endsWith('Q4')).forEach(k => { const y = k.slice(0, 4); const ks = [1, 2, 3].map(i => y + 'Q' + i).filter(x => Q[x]); if (ks.length === 3 && Q[k].rev) { const o4 = Q[k].op / Q[k].rev, o = mean(ks.map(x => Q[x].op / Q[x].rev)); if (o - o4 > 0.04) q4.push(`${k}(영업이익률 ${pct(o4)}, 1~3분기 평균 ${pct(o)})`); } });
  let t = ev.length ? `영업이익은 흑자인데 지배순이익이 크게 줄거나 적자였던 해는 ${ev.map(y => `${y}년(영업이익 ${eok(R[y].op)}억원 → 순이익 ${eok(R[y].ni)}억원)`).join(', ')}입니다. 손상·지분법손실·외화 손익 같은 영업 외 일회성 항목을 의심해 볼 해입니다.` : '최근 10년 중 영업이익 대비 순이익이 크게 꺾인 해는 없습니다.';
  if (q4.length) t += ` 4분기에 이익률이 크게 떨어지는 패턴(성과급·재고평가·손상 반영)이 ${q4.join(', ')}에 있었습니다.`;
  return autoP(t);
}

function allocBlock(d, M, hy) {
  const A = d.annual || {}, R = M.rows;
  const ys = hy.filter(y => isNum((A[y] || {}).div_paid));
  const niSum = ys.reduce((s, y) => s + (R[y].ni || 0), 0), dv = ys.reduce((s, y) => s + A[y].div_paid, 0);
  const bb = ys.reduce((s, y) => s + ((A[y] || {}).buyback || 0), 0);
  const cx = ys.reduce((s, y) => s + ((A[y] || {}).capex || 0), 0);
  if (ys.length < 3) return wait('배당금 지급·자사주 매입·설비투자 합계는 PC 추가 수집 후 계산됩니다.');
  return autoP(`${ys[0]}~${ys[ys.length - 1]}년 배당금 지급 합계는 ${eok(dv)}억원으로 같은 기간 지배순이익 합계(${eok(niSum)}억원)의 ${pct(niSum > 0 ? dv / niSum : null)}입니다.${bb ? ` 자사주 취득은 ${eok(bb)}억원이었습니다.` : ' 자사주 취득은 없었습니다.'} 같은 기간 설비투자는 ${eok(cx)}억원으로, 자본 배분은 '${cx > dv * 3 ? '본업 재투자 우선' : '주주 환원 비중이 큰 편'}'이었습니다.`);
}

function pastDrivers(M, hy) {
  const R = M.rows; const lines = [];
  hy.slice(1).forEach(y => {
    const b = opBridge(M, y); if (!b) return;
    const a = R[y - 1], c = R[y];
    const top = [['매출 변화', b.vol], [M.hasGP ? '매출총이익률 변화' : '이익률 변화', b.mar], ['판관비 변화', b.sga]].sort((p, q) => Math.abs(q[1]) - Math.abs(p[1]))[0];
    const mtxt = M.hasGP && isNum(a.gpm) ? `매출총이익률 ${pct(a.gpm)}→${pct(c.gpm)}` : `영업이익률 ${pct(a.opm)}→${pct(c.opm)}`;
    lines.push(`<li><b>${y}년</b>: 매출 ${sg(c.rev / a.rev - 1)}, 영업이익 ${a.op > 0 ? sg(c.op / a.op - 1) : (c.op > 0 ? '흑자 전환' : '적자')} (${mtxt}). 가장 큰 요인은 ${top[0]}(${eok(top[1])}억원).</li>`);
  });
  return lines.length ? `<p class="auto-p"><span class="tag">자동</span>연도별 영업이익 변화를 매출·이익률·판관비 효과로 나눈 결과입니다.</p><ul>${lines.join('')}</ul>` : '';
}

function analogBlock(d) {
  const sh = d.shocks || [];
  if (!sh.length) return autoP('수집된 분기(최근 몇 년) 안에서 매출총이익률이 3%p 넘게 떨어진 충격 구간은 없습니다.');
  return sh.map(s => table(['분기', ...s.path.map(p => p[0])], [{ c: ['매출총이익률', ...s.path.map(p => p[1] + '%')] }]) +
    autoP(`${s.start}(${s.start_gpm}%)부터 ${s.trough}(${s.trough_gpm}%)까지 매출총이익률이 ${s.drop}%p 떨어졌고, ${s.recovered ? `${s.recovered}에 원래 수준(1.5%p 이내)을 되찾아 회복까지 약 ${s.quarters}개 분기가 걸렸습니다.` : '아직 원래 수준을 되찾지 못했습니다.'}`)).join('') + `<div class="note">자동 탐지: 3개 분기 안에 매출총이익률이 3%p 이상 떨어진 구간. 원인(원재료·감산·판가)은 원고에서 씁니다.</div>`;
}

function quarterChart(d) {
  const Q = d.quarterly || {}, ks = Object.keys(Q).sort().slice(-12);
  if (!ks.length) return '';
  return chart({ labels: ks, bars: [{ n: '매출액', v: ks.map(k => Q[k].rev), c: 'var(--s1)' }], lines: [{ n: '매출총이익률', v: ks.map(k => Q[k].rev && isNum(Q[k].gp) ? Q[k].gp / Q[k].rev : null), c: 'var(--s4)', right: true }, { n: '영업이익률', v: ks.map(k => Q[k].rev ? Q[k].op / Q[k].rev : null), c: 'var(--s2)', right: true }], yFmt: fE, y2Fmt: fP }) + `<div class="cap">분기 매출(억원)과 이익률. 자료: DART 분기·반기·사업보고서</div>`;
}

function driverTable(M) {
  if (!M.drivers.length) return '';
  const man = (S.d.manual && S.d.manual.model) || {};
  const src = (k, y) => isNum(S.ov[k] && S.ov[k][y]) ? '직접 입력' : isNum(man[k] && man[k][y]) ? '원고' : '자동';
  return table(['가정', ...M.drivers.map(x => x.y + 'E')], [
    { c: ['매출 증가율', ...M.drivers.map(x => sg(x.g, 1) + `<br><small>${src('growth', x.y)}</small>`)] },
    { c: [M.hasGP ? '매출총이익률' : '영업이익률', ...M.drivers.map(x => x.ext ? '전년 유지<br><small>연장</small>' : pct(x.m) + `<br><small>${src(M.hasGP ? 'gpm' : 'opm', x.y)}</small>`)] },
    ...(M.hasGP ? [{ c: ['판관비 증가율', ...M.drivers.map(x => x.ext ? '–' : sg(x.sgr, 1))] }] : []),
  ]) + `<div class="note">자동 가정: 첫해 매출 증가율 = (올해 추정 증가율 + ${M.FY - 5}~${M.FY}년 연평균 ${sg(M.gHist, 1)})/2, 이후 해마다 차이의 40%씩 장기 3%로 수렴(업황 사이클이 쉬어 가는 해 반영). 매출총이익률 = 올해 이익률에서 출발해 해마다 차이의 20%씩 10년 평균(${pct(M.gpm5)}, 한 사이클의 정상 이익률)으로 수렴. 판관비 = 매출 증가율×0.6+3%(인건비·연구개발비 고정비 성격). 영업이익→지배순이익 전환율 ${pct(M.k, 0)}(5년 중앙값). ${M.T}년은 리포트처럼 ${M.T - 1}년 실적 × (1 + 장기 성장률 3%)로 연장해 5년 기대수익률의 종료 EPS로 씁니다. 결론 장의 가정 패널에서 바꿀 수 있습니다.</div>`;
}

function forecastBlock(M) {
  const R = M.rows, ys = [M.FY].concat(M.allY.filter(y => R[y].est));
  return table(['억원', ...ys.map(y => yl(M, y))], [
    { c: ['매출액', ...ys.map(y => eok(R[y].rev))] },
    ...(M.hasGP ? [{ c: ['매출총이익률', ...ys.map(y => pct(R[y].gpm))] }] : []),
    { c: ['영업이익', ...ys.map(y => eok(R[y].op))] },
    { c: ['영업이익률', ...ys.map(y => pct(R[y].opm))] },
    { c: ['지배순이익', ...ys.map(y => eok(R[y].ni))] },
    { c: ['EPS(원)', ...ys.map(y => won(R[y].eps))] },
  ], { estFrom: 2 }) + chart({ labels: M.allY.filter(y => y >= M.FY - 6).map(y => yl(M, y)), bars: [{ n: '매출액', v: M.allY.filter(y => y >= M.FY - 6).map(y => R[y].rev), c: 'var(--s1)' }], lines: [{ n: '영업이익', v: M.allY.filter(y => y >= M.FY - 6).map(y => R[y].op), c: 'var(--s2)' }], yFmt: fE, est: M.allY.filter(y => y >= M.FY - 6).findIndex(y => R[y].est) });
}

function consensusBlock(d, M) {
  const R = M.rows, parts = [];
  const c = d.manual && d.manual.consensus;
  if (c && c.length) parts.push(table(['출처', '연도', '영업이익(억원)', '우리 추정', '차이'], c.map(x => ({ c: [esc(x.src), esc(x.year), won(x.op), eok(R[x.year] && R[x.year].op), R[x.year] ? sg(R[x.year].op / (x.op * 100) - 1) : '–'] }))));
  // 1) 컨센서스 스냅숏(매일 쌓임) → 월별 변화와 주가 변화
  const H = (d.cons_hist || []).filter(r => r[1] && (r[1].cy || r[1].tp));
  if (H.length) {
    const byM = {}; H.forEach(r => { byM[r[0].slice(0, 7)] = r; });
    const rows = Object.values(byM); if (rows[rows.length - 1] !== H[H.length - 1]) rows.push(H[H.length - 1]);
    const f = rows[0][1], cyY = f.cy && f.cy.y;
    const pr = r => r[1].price || priceAt(d, r[0]);
    parts.push(table(['날짜', `${cyY || ''} 영업이익 컨센서스(억원)`, '다음 분기 영업이익(억원)', '목표주가 평균(원)', '주가(원)', '컨센서스 변화', '주가 변화'], rows.slice(-8).map(r => {
      const s = r[1], same = s.cy && s.cy.y === cyY;
      return { c: [esc(r[0]), s.cy ? won(s.cy.op) + (same ? '' : ` (${s.cy.y})`) : '–', s.nq ? `${won(s.nq.op)} (${esc(s.nq.q)})` : '–', won(s.tp), won(pr(r)),
        same && f.cy && f.cy.op ? sg(s.cy.op / f.cy.op - 1, 1) : '–', pr(rows[0]) && pr(r) ? sg(pr(r) / pr(rows[0]) - 1, 1) : '–'] };
    })));
    const last = H[H.length - 1][1];
    const my = last.cy && R[last.cy.y] && R[last.cy.y].op;
    let note = `네이버 금융(FnGuide) 컨센서스를 매일 기록합니다(${esc(H[0][0])}부터 ${H.length}일).`;
    if (isNum(my) && last.cy.op) note += ` 이 리포트 모델의 ${last.cy.y}년 영업이익 ${eok(my)}억원은 컨센서스 ${won(last.cy.op)}억원보다 ${sg(my / (last.cy.op * 100) - 1)} ${my >= last.cy.op * 100 ? '높습니다' : '낮습니다'}.`;
    if (rows.length > 1 && f.cy && last.cy && f.cy.y === last.cy.y && f.cy.op && pr(rows[0]) && pr(rows[rows.length - 1])) {
      const dc = last.cy.op / f.cy.op - 1, dp = pr(rows[rows.length - 1]) / pr(rows[0]) - 1;
      note += ` 같은 기간 컨센서스는 ${sg(dc, 1)}, 주가는 ${sg(dp, 1)} 움직여 ${Math.abs(dp - dc) < 0.05 ? '주가가 이익 추정 변화만큼 움직였습니다' : dp > dc ? '주가가 이익 추정보다 더 올랐습니다(기대가 먼저 반영)' : '주가가 이익 추정보다 덜 올랐거나 더 내렸습니다(이익 대비 할인 확대)'}.`;
    }
    parts.push(`<div class="note">${note}</div>`);
  }
  // 2) 증권사 목표주가 언급(뉴스) → 시장과 다른 의견 표시
  const T = d.tp_mentions || [];
  if (T.length) {
    const ref = (H.length && H[H.length - 1][1].tp) || median(T.map(x => x.tp));
    const odd = x => ref && Math.abs(x.tp / ref - 1) >= 0.25;
    parts.push(table(['날짜', '증권사', '목표주가(원)', ref ? '평균 대비' : '', '당시 주가 대비', '기사'], T.slice(0, 10).map(x => {
      const p = priceAt(d, x.date);
      return { c: [esc(x.date), esc(x.broker || '–'), won(x.tp) + (odd(x) ? ' <span class="tag">다른 의견</span>' : ''), ref ? sg(x.tp / ref - 1) : '', p ? sg(x.tp / p - 1) : '–',
        `<a href="${esc(x.url)}" target="_blank" rel="noopener">${esc((x.title || '').slice(0, 34))}</a>`] };
    })));
    const n = T.filter(odd).length;
    parts.push(`<div class="note">뉴스 제목·요약에 나온 증권사 목표주가입니다. ${ref ? `기준은 ${H.length && H[H.length - 1][1].tp ? '컨센서스 목표주가 평균' : '언급된 목표주가의 중앙값'} ${won(ref)}원이고, 25% 이상 벗어난 의견 ${n}건에 '다른 의견' 표시를 했습니다. 이런 리포트는 원고에서 근거(어느 가정이 다른지)를 깊게 분석합니다.` : ''}</div>`);
  }
  return parts.length ? always(parts.join('')) : null;
}
function priceAt(d, date) {
  const P = d.prices || {}, ms = P.months || [], cl = P.close || [];
  if (!date || !ms.length) return null;
  const k = date.slice(0, 7); const i = ms.indexOf(k);
  if (k >= ms[ms.length - 1]) return d.price || cl[cl.length - 1];
  return i >= 0 ? cl[i] : null;
}

const POSW = /(최대|사상\s*최|증가|상향|수주|흑자|호조|성장|신고가|매수|확대|돌파|개선|공급\s*시작|양산|승인|편입|상승|급등|순항)/;
const NEGW = /(감소|하향|적자|부진|우려|하락|손실|지연|급락|둔화|악화|리스크|소송|과잉|축소|매도|제재|중단)/;
function newsBuckets(d) {
  const all = (d.news || []).concat(d.news_hist || []);
  const seen = new Set(), pos = [], neg = [];
  all.forEach(n => { const k = n.title; if (!k || seen.has(k)) return; seen.add(k); const p = POSW.test(k), q = NEGW.test(k); if (p && !q) pos.push(n); else if (q && !p) neg.push(n); });
  return { pos: pos.slice(0, 8), neg: neg.slice(0, 8) };
}
function newsList(arr, label) {
  return `<p class="auto-p"><span class="tag">자동</span>제목의 단어로 분류한 ${label}입니다(최근순). 증권사·전문지 시각은 원고에서 정리합니다.</p><ul class="news">${arr.map(n => `<li><span class="d">${esc(n.date)}</span><a href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.title)}</a> <small>${esc(n.office || '')}</small></li>`).join('')}</ul>`;
}
function attentionBlock(d) {
  const m = d.news_months || {}, ks = Object.keys(m).sort().slice(-18);
  let s = ks.length > 2 ? chart({ labels: ks, bars: [{ n: '월별 기사 수', v: ks.map(k => m[k]), c: 'var(--s5)' }], yFmt: v => Math.round(v), h: 180 }) + `<div class="cap">네이버 금융 종목 뉴스 월별 건수(관심도 대용). 원본 리포트는 종목토론방 글 수를 썼습니다.</div>` : '';
  const ext = (d.major5 || []).filter(x => /capital|asset|fund|management|investment|llc|ltd|inc|lp|l\.p|그룹|자산운용|캐피탈|투자/i.test(x.nm));
  if (ext.length) s += autoP(`5% 이상 외부 주주: ${ext.slice(0, 4).map(x => `${esc(x.nm)} ${x.pct}%(${esc(x.date)}, ${esc(x.reason || '')})`).join(', ')}.`);
  return s;
}
function discountTxt(d, M) {
  const ps = (d.peers || []).filter(p => !p.self && p.ni > 0 && p.mcap).map(p => p.mcap / p.ni).filter(v => v < 80);
  const me = d.peers && d.peers[0] && d.peers[0].ni > 0 ? d.peers[0].mcap / d.peers[0].ni : null;
  const mp = median(ps);
  if (!isNum(me) || !isNum(mp)) return '';
  const dsc = me / mp - 1;
  return `최근 사업연도 이익 기준 PER은 ${x1(me)}배로 비교 대상 중앙값 ${x1(mp)}배보다 ${pct(Math.abs(dsc), 0)} ${dsc < 0 ? '낮습니다(할인)' : '높습니다(할증)'}. ${dsc < -0.2 ? '이익률·고객 집중·지배구조·주주환원 가운데 무엇이 할인의 원인인지 원고에서 따져 봅니다.' : ''}`;
}

function points(man, auto, risk, isAuto) {
  const arr = (man && man.length) ? man : auto;
  const tag = isAuto ? '<p class="auto-p"><span class="tag">자동</span>업종 대시보드의 전망·위험 해석(사업보고서·IR·뉴스)과 숫자 규칙(영업레버리지·밸류에이션·FCF·배당·민감도)을 합쳤습니다.</p>' : '';
  return tag + `<div class="pts">${arr.map(p => `<div class="pt ${risk ? 'risk' : ''}"><b>${esc(p.h)}</b>${txt(p.body)}${p.check ? `<div class="chk">확인할 지표: ${esc(p.check)}</div>` : ''}</div>`).join('')}</div>`;
}
function autoPoints(d, M) {
  const R = M.rows, out = [], A = d.annual || {};
  const f1 = M.drivers[0], f3 = M.drivers[2];
  if (f1 && f3 && R[M.startY].op > 0) {
    const rg = R[f3.y].rev / R[M.startY].rev - 1, og = R[f3.y].op / R[M.startY].op - 1;
    if (og > rg * 1.3 && og > 0) out.push({ h: '영업레버리지', body: `모델에서 ${M.startY}~${f3.y}년 매출이 ${sg(rg)} 늘 때 영업이익은 ${sg(og)} 늘어납니다. 고정비가 이미 들어와 있어 물량 증가가 이익으로 크게 이어지는 구조입니다.`, check: `분기 ${M.hasGP ? '매출총이익률' : '영업이익률'} ${pct(f1.m)} 이상 유지` });
  }
  if (isNum(R[M.CY + 1] && R[M.CY + 1].per) && isNum(M.tm) && R[M.CY + 1].per < M.tm * 0.8) out.push({ h: '과거보다 낮은 밸류에이션', body: `선행 PER ${x1(R[M.CY + 1].per)}배는 과거 연말 PER 평균 ${x1(M.tm)}배보다 ${pct(1 - R[M.CY + 1].per / M.tm, 0)} 낮습니다.`, check: '추정 이익 달성 여부(분기 실적)' });
  const fy = M.FY, a = A[fy] || {};
  if (isNum(a.ocf) && isNum(a.capex) && a.ocf - a.capex > 0 && isNum((A[fy - 1] || {}).ocf) && A[fy - 1].ocf - (A[fy - 1].capex || 0) < a.ocf - a.capex) out.push({ h: '잉여현금흐름 확대', body: `${fy}년 FCF가 ${eok(a.ocf - a.capex)}억원으로 늘었습니다. 대형 투자가 끝나면 배당·자사주 여력이 생깁니다.`, check: '배당 정책·밸류업 공시' });
  const pays = M.yrs.slice(-3).map(y => R[y].dps && R[y].eps > 0 ? R[y].dps / R[y].eps : null).filter(isNum);
  if (pays.length && mean(pays) < 0.15 && R[fy].ni > 0) out.push({ h: '주주 환원 확대 여지', body: `최근 배당성향이 ${pct(mean(pays))}로 낮습니다. 배당성향을 20%로만 올려도 ${M.CY + 1}년 DPS는 약 ${won(Math.round((R[M.CY + 1] ? R[M.CY + 1].eps : 0) * 0.2 / 10) * 10)}원이 됩니다.`, check: '배당성향, 자사주 매입·소각 공시' });
  if (d.biz_kpi && d.biz_kpi.utilization && d.biz_kpi.utilization[0] < 75) out.push({ h: '가동률 여유', body: `사업보고서상 가동률이 ${d.biz_kpi.utilization[0]}%여서 추가 투자 없이 물량을 늘릴 수 있습니다.`, check: '가동률, 감가상각비 대비 매출' });
  if (!out.length) out.push({ h: '두드러진 숫자 신호 없음', body: '자동 규칙(영업레버리지·저PER·FCF·배당성향·가동률)에 걸리는 포인트가 없습니다. 원고에서 정성적 포인트를 씁니다.' });
  return out;
}
function autoRisks(d, M) {
  const out = [], R = M.rows, Q = d.quarterly || {};
  const g = Object.keys(Q).map(k => Q[k].rev ? (isNum(Q[k].gp) ? Q[k].gp : Q[k].op) / Q[k].rev : null).filter(isNum);
  if (M.sens) { const lo = M.sens.grid[0][0]; out.push({ h: '업황·원가 민감도', body: `${M.sens.y}년 매출 증가율이 기본 가정보다 10%p 낮고 ${M.sens.opm ? '영업이익률' : '매출총이익률'}이 1%p 낮으면 영업이익은 ${eok(lo)}억원으로 기본 추정보다 ${pct(1 - lo / M.sens.base, 0)} 적습니다(부록 민감도).` }); }
  if (std(g) > 0.03) out.push({ h: '이익률 변동성', body: `분기 이익률 표준편차가 ${(std(g) * 100).toFixed(1)}%p로 큽니다. 원재료·판가 변화가 이익을 크게 흔듭니다.` });
  const A = d.annual || {}, f = M.FY, a = A[f] || {};
  if (isNum(a.debt) && isNum(a.dep) && R[f].op + a.dep > 0) { const nd = a.debt - (a.cash || 0) - (a.st_fin || 0); if (nd / (R[f].op + a.dep) > 2) out.push({ h: '차입 부담', body: `순차입금이 EBITDA의 ${(nd / (R[f].op + a.dep)).toFixed(1)}배입니다.` }); }
  const sales = biz('sales');
  if (sales && /10\s*%|주요\s*매출처|주요\s*고객/.test(sales.text)) out.push({ h: '고객 집중', body: '사업보고서에 매출 10% 이상 주요 고객이 언급돼 있습니다. 상위 고객의 발주 변화가 실적을 좌우합니다.' });
  out.push({ h: '비관 시나리오', body: `종료 연도(${M.T}년) EPS가 기본의 ${pct(M.sc[0].mult, 0)}로 줄고 PER이 ${x1(M.sc[0].per)}배가 되면 연 ${pct(M.sc[0].ret)}입니다. 종료 시점이 업황 하강기와 겹치는 경우입니다.` });
  return out;
}

function erBlock(M) {
  const sc = M.sc;
  if (!(M.epsT > 0)) return wait(`${M.T}년 추정 EPS가 ${won(M.epsT)}원(적자)이라 리포트 방식(종료 EPS × PER)의 기대수익률을 낼 수 없습니다. 흑자 전환 시점·정상 이익률을 원고나 가정 패널에 넣으면 계산됩니다.`);
  return `<div class="er">${sc.map(s => `<div><div class="l">${s.nm}</div><div class="v ${s.ret >= 0 ? 'pos' : 'neg'}">${pct(s.ret)}</div><div class="l">${M.T}년 EPS ${won(s.eps)}원 × PER ${x1(s.per)}배 = ${won(s.value)}원 + 누적 배당 ${won(s.div)}원</div></div>`).join('')}</div>` +
    table(['구분', '비관', '기본', '낙관'], [
      { c: [`${M.T}년 EPS(원)`, ...sc.map(s => won(s.eps))] },
      { c: ['종료 PER(배)', ...sc.map(s => x1(s.per))] },
      { c: [`${M.T}년 말 주당가치(원)`, ...sc.map(s => won(s.value))] },
      { c: ['누적 배당(원)', ...sc.map(s => won(s.div))] },
      { c: ['연환산 기대수익률', ...sc.map(s => `<b>${pct(s.ret)}</b>`)] },
    ]) + `<div class="note">연환산 기대수익률 = ((${M.T}년 EPS × 종료 PER + ${M.CY + 1}~${M.T}년 누적 DPS) ÷ 현재 주가 ${won(M.price)}원)^(1/5) − 1. ${M.perSrc === 'auto' ? `기본 종료 PER = 과거 연말 PER 절사평균(${x1(M.tm)}배)의 85%, 비관 = 기본의 75%, 낙관 = 기본의 130%` : `종료 PER은 ${M.perSrc === 'manual' ? '원고' : '직접 입력'} 가정(참고: 과거 연말 PER 절사평균 ${x1(M.tm)}배)`}. 비관 EPS = 기본의 ${pct(M.sc[0].mult, 0)}, 낙관 = ${pct(M.sc[2].mult, 0)}. 주식수 ${won(M.shares)}주 고정.</div>`;
}

function howTxt(d, M) {
  const b = M.sc[1].ret, w = M.sc[0].ret, f1 = M.drivers[0];
  const chk = f1 ? `${f1.y}년 분기 ${M.hasGP ? '매출총이익률' : '영업이익률'}이 ${pct(f1.m)} 이상 유지되는지` : '분기 실적';
  const hi = M.sc[2].per;
  if (b == null) return '';
  if (b >= 0.12) return `기본 기대수익률이 연 ${pct(b)}로 높고 비관 시나리오 손실(${pct(w)})이 ${w > -0.05 ? '작아' : '있어'} 장기 투자를 시작하기 나쁘지 않습니다. 다만 한 번에 사기보다 ${chk} 확인하며 나눠 사고, PER이 ${x1(hi)}배를 넘는 구간에서는 비중을 줄이는 접근이 맞습니다.`;
  if (b >= 0.07) return `기본 기대수익률 연 ${pct(b)}는 시장 평균 수준입니다. ${chk} 확인되기 전에는 소량만 담고, 주가가 내려 기대수익률이 연 12%를 넘는 가격(약 ${won(priceFor(M, 0.12))}원 이하)에서 비중을 늘리는 방법을 권합니다.`;
  return `기본 기대수익률이 연 ${pct(b)}로 낮습니다. 기대수익률이 연 12%가 되는 가격은 약 ${won(priceFor(M, 0.12))}원이므로 그 근처까지 기다리거나, 이익 추정이 올라가는 근거(${chk})를 확인한 뒤 접근합니다.`;
}
function priceFor(M, r) { const s = M.sc[1]; return isNum(s.value) ? (s.value + s.div) / Math.pow(1 + r, 5) : null; }

function assumePanel(M) {
  const ds = M.drivers;
  const v = (x, d = 1) => isNum(x) ? (x * 100).toFixed(d) : '';
  return `<div class="assume" id="assume"><h4>가정 바꾸기 — 바꾸면 리포트 전체(표지·추정·민감도·기대수익률)가 다시 계산됩니다</h4>
  <div class="tbl"><table class="t"><thead><tr><th>연도</th>${ds.map(x => `<th>${x.y}E</th>`).join('')}</tr></thead><tbody>
  <tr><td>매출 증가율(%)</td>${ds.map(x => `<td><input data-k="growth" data-y="${x.y}" value="${v(x.g)}" inputmode="decimal"></td>`).join('')}</tr>
  <tr><td>${M.hasGP ? '매출총이익률' : '영업이익률'}(%)</td>${ds.map(x => x.ext ? '<td>연장</td>' : `<td><input data-k="${M.hasGP ? 'gpm' : 'opm'}" data-y="${x.y}" value="${v(x.m)}" inputmode="decimal"></td>`).join('')}</tr>
  ${M.hasGP ? `<tr><td>판관비 증가율(%)</td>${ds.map(x => x.ext ? '<td>–</td>' : `<td><input data-k="sga_g" data-y="${x.y}" value="${v(x.sgr)}" inputmode="decimal"></td>`).join('')}</tr>` : ''}
  </tbody></table></div>
  <div class="tbl"><table class="t"><tbody><tr>
   <td>영업이익→순이익(%)</td><td><input data-k="ni_conv" value="${v(M.k, 0)}"></td>
   <td>배당성향(%)</td><td><input data-k="payout" value="${v(M.payout, 0)}"></td>
   <td>PER 비관/기본/낙관</td><td><input data-k="per_bear" value="${M.per.bear}"> <input data-k="per_base" value="${M.per.base}"> <input data-k="per_bull" value="${M.per.bull}"></td>
   <td>비관·낙관 EPS 배수(%)</td><td><input data-k="bear_eps" value="${v(M.sc[0].mult, 0)}"> <input data-k="bull_eps" value="${v(M.sc[2].mult, 0)}"></td>
  </tr></tbody></table></div>
  <div class="btns"><button type="button" id="reset">자동·원고 가정으로 되돌리기</button><span class="note">입력값은 이 브라우저에만 저장됩니다.</span></div></div>`;
}
function bindAssume() {
  document.querySelectorAll('#assume input').forEach(inp => inp.addEventListener('change', () => {
    const k = inp.dataset.k, y = inp.dataset.y, raw = parseFloat(inp.value);
    if (!isFinite(raw)) return;
    const val = /^per_/.test(k) ? raw : raw / 100;
    if (y) { S.ov[k] = S.ov[k] || {}; S.ov[k][y] = val; } else S.ov[k] = val;
    saveOv(); const yPos = window.scrollY; render(); window.scrollTo(0, yPos);
  }));
  const r = $('#reset'); if (r) r.onclick = () => { S.ov = {}; saveOv(); const yPos = window.scrollY; render(); window.scrollTo(0, yPos); };
}
function saveOv() { try { localStorage.setItem('report-ov-' + S.d.code, JSON.stringify(S.ov)); } catch (e) { /* 저장 불가 */ } }
function loadOv(code) { try { return JSON.parse(localStorage.getItem('report-ov-' + code) || '{}') || {}; } catch (e) { return {}; } }

function annualTable(d, M) {
  const R = M.rows, A = d.annual || {}, ys = M.allY.filter(y => y >= M.FY - 9);
  const g = (y, k) => (A[y] || {})[k];
  const rows = [
    ['매출액', y => eok(R[y].rev)],
    ['매출원가', y => eok(isNum(g(y, 'cogs')) ? g(y, 'cogs') : (isNum(R[y].gp) ? R[y].rev - R[y].gp : null)), 'ind'],
    ['매출총이익', y => eok(R[y].gp)],
    ['매출총이익률', y => pct(R[y].gpm), 'ind'],
    ['판매비와관리비', y => eok(isNum(R[y].gp) ? R[y].gp - R[y].op : null)],
    ['영업이익', y => eok(R[y].op)],
    ['영업이익률', y => pct(R[y].opm), 'ind'],
    ['세전이익', y => eok(g(y, 'pretax'))],
    ['당기순이익', y => eok(g(y, 'ni_total'))],
    ['지배주주 순이익', y => eok(R[y].ni)],
    ['EPS(원)', y => won(R[y].eps)],
    ['DPS(원)', y => won(R[y].dps)],
    ['주가(연말, 추정은 현재)', y => won(R[y].price)],
    ['PER', y => x1(R[y].per)],
    ['ROE', y => pct(R[y].roe)],
    ['ROIC', y => pct(R[y].roic)],
    ['NOPLAT', y => eok(R[y].noplat)],
  ];
  const ef = ys.findIndex(y => R[y].est);
  return table(['억원', ...ys.map(y => yl(M, y))], rows.map(([n, f, c]) => ({ cls: c || '', c: [n, ...ys.map(f)] })), { estFrom: ef < 0 ? null : ef + 1 }) +
    `<div class="note">주1) DART 연결 사업보고서${d.restated ? '. 연도 값은 다음 해 보고서의 재작성 전기 금액 우선' : ' (재작성 전기 금액은 PC 추가 수집 후 반영)'}. 주2) ROIC = 영업이익×(1−24.2%) ÷ 평균 투하자본(자본총계 + 순차입금). 과거 PER은 연말 종가, 추정 연도는 현재 주가. 주3) EPS는 현재 주식수 기준.</div>`;
}
function quarterTable(d) {
  const Q = d.quarterly || {}, ks = Object.keys(Q).sort().slice(-12);
  if (!ks.length) return wait('분기 자료가 없습니다.');
  const r = (n, f, c) => ({ cls: c || '', c: [n, ...ks.map(f)] });
  return table(['억원', ...ks], [
    r('매출액', k => eok(Q[k].rev)), r('매출원가', k => eok(isNum(Q[k].gp) ? Q[k].rev - Q[k].gp : null), 'ind'), r('매출총이익', k => eok(Q[k].gp)),
    r('매출총이익률', k => pct(Q[k].rev && isNum(Q[k].gp) ? Q[k].gp / Q[k].rev : null), 'ind'), r('판매비와관리비', k => eok(isNum(Q[k].gp) ? Q[k].gp - Q[k].op : null)),
    r('영업이익', k => eok(Q[k].op)), r('영업이익률', k => pct(Q[k].rev ? Q[k].op / Q[k].rev : null), 'ind'), r('지배주주 순이익', k => eok(Q[k].ni))]);
}
function bsTable(d, hy) {
  const A = d.annual || {}, ys = hy.filter(y => isNum((A[y] || {}).assets));
  if (ys.length < 2) {
    const b = d.bs_latest; if (!b) return wait('재무상태표는 PC 추가 수집 후 표시됩니다.');
    return table(['억원', b.period], [{ c: ['지배주주지분', eok(b.equity)] }, { c: ['현금성자산', eok(b.cash)] }, { c: ['단기금융상품', eok(b.st_fin)] }, { c: ['차입금', eok(b.debt)] }, { c: ['순현금', eok((b.cash || 0) + (b.st_fin || 0) - (b.debt || 0))] }]) + wait('10년 재무상태표·회전일수는 PC에서 scripts\\report_dart.bat 실행 후 표시됩니다.');
  }
  const L = d.latest;
  const cols = ys.map(String).concat(L && isNum(L.assets) ? [L.period] : []);
  const val = (c, k) => c === (L && L.period) ? L[k] : (A[c] || {})[k];
  const f = [['자산총계', 'assets'], ['현금성자산', 'cash', 1], ['단기금융상품', 'st_fin', 1], ['매출채권', 'ar', 1], ['재고자산', 'inv', 1], ['유형자산', 'ppe', 1], ['무형자산', 'intang', 1], ['사용권자산', 'rou', 1], ['관계기업투자', 'assoc', 1], ['부채총계', 'liab'], ['이자발생부채', 'debt', 1], ['매입채무', 'ap', 1], ['자본총계', 'equity_total'], ['지배주주지분', 'equity_parent', 1], ['비지배지분', 'minority', 1]];
  const rows = f.map(([n, k, ind]) => ({ cls: ind ? 'ind' : '', c: [n, ...cols.map(c => eok(val(c, k)))] }));
  rows.push({ c: ['순현금', ...cols.map(c => isNum(val(c, 'debt')) ? eok((val(c, 'cash') || 0) + (val(c, 'st_fin') || 0) - val(c, 'debt')) : '–')] });
  const D = cols.map(c => c === (L && L.period) ? {} : days(A, c));
  [['매출채권회전일수', 'ar'], ['재고자산회전일수', 'inv'], ['매입채무회전일수', 'ap'], ['현금전환주기', 'ccc']].forEach(([n, k]) => rows.push({ cls: 'ind', c: [n, ...D.map(x => isNum(x[k]) ? Math.round(x[k]) : '–')] }));
  return table(['억원 · 일', ...cols], rows) + `<div class="note">이자발생부채 = 차입금·사채(리스부채 제외). 순현금 = 현금성자산 + 단기금융상품 − 이자발생부채.</div>`;
}
function cfTable(d, M, hy) {
  const A = d.annual || {}, ys = hy.filter(y => isNum((A[y] || {}).ocf));
  if (ys.length < 2) return wait('현금흐름표는 PC 추가 수집 후 표시됩니다.');
  const g = (y, k) => (A[y] || {})[k];
  return table(['억원', ...ys.map(String)], [
    { c: ['영업활동현금흐름', ...ys.map(y => eok(g(y, 'ocf')))] }, { c: ['투자활동현금흐름', ...ys.map(y => eok(g(y, 'icf')))] },
    { cls: 'ind', c: ['유형자산 취득(CAPEX)', ...ys.map(y => eok(g(y, 'capex')))] }, { c: ['재무활동현금흐름', ...ys.map(y => eok(g(y, 'fincf')))] },
    { cls: 'ind', c: ['배당금 지급', ...ys.map(y => eok(g(y, 'div_paid')))] }, { cls: 'ind', c: ['자기주식 취득', ...ys.map(y => eok(g(y, 'buyback')))] },
    { c: ['감가상각비', ...ys.map(y => eok(g(y, 'dep')))] }, { c: ['NOPLAT', ...ys.map(y => eok(M.rows[y] && M.rows[y].noplat))] },
    { c: ['FCF', ...ys.map(y => eok(g(y, 'ocf') - (g(y, 'capex') || 0)))] }]) + `<div class="note">FCF = 영업활동현금흐름 − 유형자산 취득.</div>`;
}
function sensTable(M) {
  const s = M.sens; if (!s) return '';
  const lab = s.opm ? '영업이익률' : '매출총이익률';
  return table(['항목', ...s.ms.map(m => `${lab} ${pct(m)}`)], s.gs.map((g, i) => ({ c: [`매출 증가율 ${sg(g, 1)}`, ...s.grid[i].map((v, j) => i === 2 && j === 1 ? `<b>${eok(v)}</b>` : eok(v))] }))) +
    `<div class="note">억원. 기본 추정은 매출 ${sg(s.gs[2], 1)}, ${lab} ${pct(s.ms[1])}(영업이익 ${eok(s.base)}억원). 판관비는 기본 추정과 같다.</div>`;
}
function sourcesBlock(d) {
  const s = (d.biz_src || []).map(r => `<a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.nm)}</a>`);
  const man = d.manual && d.manual.sources ? d.manual.sources.map(x => typeof x === 'string' ? esc(x) : x.url ? `<a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.nm)}</a>` : esc(x.nm)) : [];
  return `<h3 class="sec">자료</h3><div class="note">DART: ${s.join(' · ') || '–'}${d.extra_fetched ? ` · 재무상태표·현금흐름·배당·주주 PC 수집 ${esc(d.extra_fetched)}` : ' · 재무상태표·현금흐름·배당·주주: PC 수집 전'}<br>${man.join(' · ')}</div>`;
}

// ---------------------------------------------------------------- 분석 방법(역엔지니어링)
async function renderMethod() {
  $('#toc').innerHTML = '';
  let md = '';
  try { md = await (await fetch('METHOD.md')).text(); } catch (e) { md = '불러오지 못했습니다.'; }
  const html = esc(md).split('\n').map(l => {
    if (/^# /.test(l)) return `<h1>${l.slice(2)}</h1>`;
    if (/^## /.test(l)) return `<h3>${l.slice(3)}</h3>`;
    if (/^\|/.test(l)) { if (/^\|[-| ]+\|$/.test(l)) return ''; return '<tr>' + l.split('|').slice(1, -1).map(c => `<td>${c.trim().replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')}</td>`).join('') + '</tr>'; }
    if (/^\s*- /.test(l)) return `<li>${l.replace(/^\s*- /, '').replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')}</li>`;
    if (/^\d+\. /.test(l)) return `<p>${l.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')}</p>`;
    return l.trim() ? `<p>${l.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')}</p>` : '';
  }).join('\n').replace(/(<tr>[\s\S]*?<\/tr>\n?)+/g, m => `<div class="tbl"><table>${m}</table></div>`).replace(/(<li>[\s\S]*?<\/li>\n?)+/g, m => `<ul>${m}</ul>`);
  $('#out').innerHTML = `<div class="paper method">${html}<p><a href="#${S.d ? S.d.code : '102710'}">← 리포트로 돌아가기</a></p></div>`;
}

// ---------------------------------------------------------------- 로드
async function loadCompany(code) {
  $('#out').innerHTML = '<div class="loading">불러오는 중…</div>';
  try {
    const d = await (await fetch(`data/c/${code}.json`)).json();
    S.d = d; S.ov = loadOv(code);
    document.title = `${d.name} 기업분석 리포트`;
    $('#q').value = `${d.name} (${d.code})`;
    render();
    live(d);
  } catch (e) { $('#out').innerHTML = `<div class="paper">${esc(code)} 리포트를 불러오지 못했습니다.</div>`; }
}
async function live(d) {
  try {
    const p = d.industry === 'cosmetics' ? '' : d.industry + '/';
    const q = await (await fetch(LIVE + p + 'quotes.json?t=' + Date.now())).json();
    const x = q && q.quotes && q.quotes[d.code];
    if (x && x.price && S.d === d && x.price !== d.price) { d.price = x.price; d.price_time = x.time; if (d.shares) d.mcap = x.price * d.shares / 1e6; const yPos = window.scrollY; render(); window.scrollTo(0, yPos); }
  } catch (e) { /* 스냅샷 사용 */ }
}
function route() {
  const h = decodeURIComponent(location.hash.slice(1));
  if (h === 'method') return renderMethod();
  const code = /^\d{6}$/.test(h) ? h : (S.list.companies.find(c => c.manual) || S.list.companies[0]).code;
  if (!S.d || S.d.code !== code) loadCompany(code);
  else if (!h.startsWith('s') && !h.startsWith('ap')) render();
}
async function init() {
  S.list = await (await fetch('data/list.json')).json();
  const cos = S.list.companies;
  const inds = [...new Map(cos.map(c => [c.ind, c.ind_name])).entries()];
  $('#ind').innerHTML += inds.map(([k, v]) => `<option value="${esc(k)}">${esc(v)}</option>`).join('');
  const fill = () => { const f = $('#ind').value; $('#cos').innerHTML = cos.filter(c => !f || c.ind === f).map(c => `<option value="${esc(c.name)} (${c.code})">${esc(c.ind_name)} · ${esc(c.group || '')}${c.manual ? ' · 원고' : ''}</option>`).join(''); };
  fill(); $('#ind').onchange = fill;
  $('#hint').textContent = `${S.list.n}개사 · 원고 ${cos.filter(c => c.manual).length}개 · 빌드 ${S.list.built}`;
  $('#q').addEventListener('change', () => { const m = $('#q').value.match(/(\d{6})/) || [null, (cos.find(c => c.name === $('#q').value.trim()) || {}).code]; if (m[1]) location.hash = m[1]; });
  window.addEventListener('hashchange', () => { const h = location.hash.slice(1); if (h === 'method' || /^\d{6}$/.test(h)) route(); });
  route();
}
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => S.d && render());
init();
})();
