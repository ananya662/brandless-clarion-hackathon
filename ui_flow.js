// End-to-end UI check of the suggestion workflow using jsdom against a running server.
// Usage: BASE=http://127.0.0.1:8011 NODE_PATH=<path with jsdom> node tests/ui_flow.js
const { JSDOM } = require('jsdom');
const BASE = process.env.BASE || 'http://127.0.0.1:8011';
const sleep = ms => new Promise(r => setTimeout(r, ms));
let failed = 0;
const check = (name, ok, extra = '') => { console.log((ok ? 'PASS ' : 'FAIL ') + name + (ok ? '' : ' ' + extra)); if (!ok) failed++; };
(async () => {
  const lg = await (await fetch(BASE + '/api/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username: 'asha', password: 'demo123' }) })).json();
  const H = { 'X-Token': lg.token };
  const html = await (await fetch(BASE + '/')).text();
  const dom = new JSDOM(html, { url: BASE + '/', runScripts: 'dangerously', pretendToBeVisual: true,
    beforeParse(w) { w.localStorage.setItem('t', lg.token); w.fetch = (u, o) => fetch(new URL(u, BASE).href, o); w.alert = m => { w.__alert = m }; w.prompt = () => 'reason'; w.URL.createObjectURL = () => 'blob:x'; } });
  const w = dom.window, d = w.document; await sleep(400);
  const btn = (root, t) => [...root.querySelectorAll('button')].find(b => b.textContent.trim() === t);
  const cardWith = s => [...d.querySelectorAll('.card')].find(c => c.textContent.includes(s) && btn(c, 'Accept'));
  w.newForm(); d.querySelector('#tx').value = 'NovaDesk starts at INR 299/month and guarantees 2x revenue in 7 days.';
  d.querySelector('#ti').value = 'T'; await w.create(); await sleep(500);
  check('v1 shows price finding', d.body.textContent.includes('Draft says INR 299'));
  btn(cardWith('INR 299'), 'Apply suggestion to text').click();
  check('Apply puts exact replacement in editor', d.querySelector('#ed').value.includes('INR 499/month') && !d.querySelector('#ed').value.includes('INR 299'), d.querySelector('#ed').value);
  btn(cardWith('Draft says INR 299'), 'Accept').click(); await sleep(600);   // re-renders the panel
  check('Unsaved applied text survives Accept (re-render)', d.querySelector('#ed').value.includes('INR 499/month'), d.querySelector('#ed').value);
  const before = await (await fetch(BASE + '/api/contents', { headers: H })).json();
  check('Nothing saved before explicit save', before[0].n === 1, JSON.stringify(before[0]));
  btn(d, 'Save as new version and re-run review').click(); await sleep(800);
  const after = await (await fetch(BASE + '/api/contents', { headers: H })).json();
  check('Explicit save created v2', after[0].n === 2, JSON.stringify(after[0]));
  const v2 = await (await fetch(BASE + '/api/versions/' + after[0].vid, { headers: H })).json();
  check('v2 saved text has INR 499 and no INR 299', v2.version.text.includes('INR 499/month') && !v2.version.text.includes('INR 299'), v2.version.text);
  check('v2 has no price-mismatch finding', !v2.findings.some(f => f.rule === 'fact'), JSON.stringify(v2.findings.map(f => f.rule)));
  check('v2 still flags revenue guarantee', v2.findings.some(f => f.rule === 'claim' && f.state === 'not_verifiable'));
  const v1 = await (await fetch(BASE + '/api/versions/' + v2.history[0].id, { headers: H })).json();
  check('v1 history and findings still accessible', v1.version.text.includes('INR 299') && v1.findings.some(f => f.rule === 'fact'));
  console.log(failed ? `\n${failed} FAILED` : '\nALL UI CHECKS PASSED'); process.exit(failed ? 1 : 0);
})();
