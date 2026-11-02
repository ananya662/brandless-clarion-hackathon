// UI check for guideline import (manager). Usage: BASE=http://127.0.0.1:8011 node tests/import_ui.js
const { JSDOM } = require('jsdom'); const BASE = process.env.BASE || 'http://127.0.0.1:8011'; const sleep = ms => new Promise(r => setTimeout(r, ms));
let failed = 0; const check = (n, ok, x = '') => { console.log((ok ? 'PASS ' : 'FAIL ') + n + (ok ? '' : ' ' + x)); if (!ok) failed++; };
(async () => {
  const lg = await (await fetch(BASE + '/api/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username: 'manoj', password: 'demo123' }) })).json();
  const html = await (await fetch(BASE + '/')).text();
  const dom = new JSDOM(html, { url: BASE + '/', runScripts: 'dangerously', pretendToBeVisual: true,
    beforeParse(w) { w.localStorage.setItem('t', lg.token); w.fetch = (u, o) => fetch(new URL(u, BASE).href, o); w.alert = m => { w.__alert = m }; w.confirm = () => true; } });
  const w = dom.window, d = w.document; await sleep(500);
  const btn = t => [...d.querySelectorAll('button')].find(b => b.textContent.trim() === t);
  btn('Sources').click(); await sleep(500);
  check('manager sees import section', !!d.querySelector('#gt') && !!btn('Analyse guideline'));
  btn('Load sample guideline').click(); check('sample guideline loads', d.querySelector('#gt').value.includes('NovaDesk'));
  btn('Analyse guideline').click(); await sleep(700);
  check('proposals are listed with warnings', d.querySelector('#props').textContent.includes('Needs attention') && d.querySelector('#props').textContent.includes('Vague wording'), d.querySelector('#props').textContent.slice(0, 200));
  const before = d.querySelectorAll('table tr').length;
  btn('Accept all without warnings').click(); await sleep(900);
  check('clean rules become active sources', d.querySelectorAll('table tr').length > before && d.body.textContent.includes('from Sample brand guide'));
  check('flagged proposals stay pending for a human', d.querySelector('#props').textContent.includes('Needs attention'));
  console.log(failed ? `\n${failed} FAILED` : '\nIMPORT UI CHECKS PASSED'); process.exit(failed ? 1 : 0);
})();
