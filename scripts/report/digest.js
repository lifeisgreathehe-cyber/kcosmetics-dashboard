// 원고 작성용 요약: NODE_PATH=$(npm root -g) node scripts/report/digest.js 005930 000660 → 회사별 실적·엔진 추정(기대수익률)·업종 분석·뉴스를 한 줄 JSON으로
const { chromium } = require('playwright');
const http = require('http'), fs = require('fs'), path = require('path');
const ROOT = path.join(__dirname, '..', '..', 'docs');
const srv = http.createServer((q, r) => {
  let p = path.join(ROOT, decodeURIComponent(q.url.split('?')[0]));
  if (p.endsWith('/')) p += 'index.html';
  fs.readFile(p, (e, b) => { if (e) { r.writeHead(404); r.end(); } else { r.writeHead(200); r.end(b); } });
}).listen(8765);
(async () => {
  const b = await chromium.launch();
  const pg = await b.newPage();
  await pg.route('**/report.js', async rt => { const r = await rt.fetch(); let t = await r.text(); t = t.replace(/\ninit\(\);/, '\nwindow.S=S;init();'); rt.fulfill({ response: r, body: t }); });
  pg.on('pageerror', e => console.log('ERR', e.message));
  for (const code of process.argv.slice(2)) {
    await pg.goto(`http://localhost:8765/report/index.html#${code}`);
    await pg.waitForFunction(() => typeof S !== 'undefined' && S.d && S.d.code === location.hash.slice(1), null, { timeout: 20000 }).catch(() => {});
    const o = await pg.evaluate(() => {
      const d = S.d, M = S.M; const eok = v => v == null ? null : Math.round(v / 100);
      const A = d.annual || {}; const ys = Object.keys(A).sort().slice(-6);
      const Q = d.quarterly || {}; const qs = Object.keys(Q).sort().slice(-6);
      const out = { code: d.code, name: d.name, ind: d.industry, grp: d.group, price: d.price, mcap_eok: eok(d.mcap), div_yield: d.div_yield,
        annual_eok: ys.map(y => [y, eok(A[y].rev), eok(A[y].op), eok(A[y].ni)]),
        q_eok: qs.map(k => [k, eok(Q[k].rev), eok(Q[k].op), eok(Q[k].ni)]),
        holders: (d.holders || []).slice(0, 3), restated: !!d.restated };
      if (M) {
        out.model = { CY: M.CY, T: M.T, cy_op: eok(M.rows[M.CY] && M.rows[M.CY].op), cy_ni: eok(M.rows[M.CY] && M.rows[M.CY].ni),
          est: M.allY.filter(y => M.rows[y] && M.rows[y].est).map(y => [y, eok(M.rows[y].rev), eok(M.rows[y].op), Math.round(M.rows[y].eps || 0)]),
          per: M.per, tm: M.tm, ret: M.sc.map(s => s.ret == null ? null : +(s.ret * 100).toFixed(1)), k: M.k };
      }
      const s = d.src || {}, dp = s.deep || {};
      out.deep = { products: dp.products, competition: dp.competition, customers: dp.customers, sourcing: dp.sourcing,
        moat: dp.moat && dp.moat.reason, outlook: dp.outlook && dp.outlook.summary, up: dp.outlook && dp.outlook.upside, risk: dp.outlook && dp.outlook.risks,
        diag: dp.diagnosis || null };
      const rv = s.rev || {}; out.rev = { title: rv.title, trend: rv.trend, eval: rv.eval, watch: rv.watch };
      const ir = s.ir || {}; out.ir = { summary: ir.summary, strategy: ir.strategy, change: ir.change };
      out.news = (d.news || []).slice(0, 8).map(n => n.date + ' ' + n.title);
      out.peers = (d.peers || []).slice(0, 6).map(p => [p.name, Math.round((p.mcap || 0) / 100), p.rev && Math.round(p.op / p.rev * 1000) / 10]);
      return out;
    });
    console.log(JSON.stringify(o, (k, v) => typeof v === 'string' && v.length > 420 ? v.slice(0, 420) + '…' : v));
    console.log('-----');
  }
  await b.close(); srv.close();
})();
