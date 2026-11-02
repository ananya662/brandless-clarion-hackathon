// UI check for the evaluation tab and the evidence-check line on findings. Usage: BASE=http://127.0.0.1:8011 node tests/eval_ui.js
const { JSDOM } = require('jsdom'); const BASE = process.env.BASE || 'http://127.0.0.1:8011'; const sleep = ms => new Promise(r => setTimeout(r, ms));
let failed = 0; const check = (n, ok, x = '') => { console.log((ok ? 'PASS ' : 'FAIL ') + n + (ok ? '' : ' ' + x)); if (!ok) failed++; };
(async () => {
  const lg = await (await fetch(BASE + '/api/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username: 'asha', password: 'demo123' }) })).json();
  const dom = new JSDOM(await (await fetch(BASE + '/')).text(), { url: BASE + '/', runScripts: 'dangerously', pretendToBeVisual: true,
    beforeParse(w) { w.localStorage.setItem('t', lg.token); w.fetch = (u, o) => fetch(new URL(u, BASE).href, o); w.alert = () => {}; } });
  const w = dom.window, d = w.document; await sleep(500);
  const btn = t => [...d.querySelectorAll('button')].find(b => b.textContent.trim() === t);
  btn('Evaluation').click(); await sleep(700);
  check('evaluation shows 30 labelled drafts', d.body.textContent.includes('30 labelled fictional drafts') && d.querySelectorAll('table tr').length === 31);
  check('metrics and the honest miss are visible', d.body.textContent.includes('Precision') && d.body.textContent.includes('False positives on clean drafts') && d.body.textContent.includes('MISS') && d.body.textContent.includes('Customers see twice the revenue.'));
  btn('Content').click(); await sleep(400); w.newForm(); d.querySelector('#tx').value = 'Every customer will double revenue in 90 days. Nova Desk rocks.'; d.querySelector('#ti').value = 'E';
  await w.create(); await sleep(700);
  check('findings show the evidence check', d.body.textContent.includes('Evidence check: VERIFIED') && d.body.textContent.includes('Evidence check: PARTIAL'));
  check('partial support is flagged for a human', d.body.textContent.includes('NEEDS HUMAN CHECK'));
  console.log(failed ? `\n${failed} FAILED` : '\nEVAL UI CHECKS PASSED'); process.exit(failed ? 1 : 0);
})();
