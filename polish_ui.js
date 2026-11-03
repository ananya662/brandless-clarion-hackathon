// UI checks for the polish pass: compact header, role guidance, refresh restore, double-click safety. Usage: BASE=... node tests/polish_ui.js
const { JSDOM } = require('jsdom'); const BASE = process.env.BASE || 'http://127.0.0.1:8011'; const sleep = ms => new Promise(r => setTimeout(r, ms));
let failed = 0; const check = (n, ok, x = '') => { console.log((ok ? 'PASS ' : 'FAIL ') + n + (ok ? '' : ' ' + x)); if (!ok) failed++; };
const login = async u => (await (await fetch(BASE + '/api/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username: u, password: 'demo123' }) })).json()).token;
const open = async (token, extra = {}) => { const html = await (await fetch(BASE + '/')).text();
  const dom = new JSDOM(html, { url: BASE + '/', runScripts: 'dangerously', pretendToBeVisual: true, beforeParse(w) { w.localStorage.setItem('t', token); for (const k in extra) w.localStorage.setItem(k, extra[k]); w.fetch = (u, o) => fetch(new URL(u, BASE).href, o); w.alert = m => { w.__alert = m }; w.confirm = () => true; } });
  await sleep(600); return dom.window; };
(async () => {
  const tA = await login('asha'); let w = await open(tA), d = w.document;
  check('header is compact after sign-in', d.body.classList.contains('in'));
  check('upload is a styled button, not the raw file input', !!d.querySelector('label.btnlike'));
  w.alert = m => { w.__alert = m }; d.querySelector('#tx').value = '   '; await w.create();
  check('empty draft gets a clear message', (w.__alert || '').includes('Paste or upload'));
  d.querySelector('#tx').value = 'Meet Nova Desk at INR 299/month.'; d.querySelector('#ti').value = 'Dbl';
  w.create().catch(() => {}); w.create().catch(() => {}); await sleep(1200);   // same action twice, immediately
  const list = await (await fetch(BASE + '/api/contents', { headers: { 'X-Token': tA } })).json();
  check('double click creates only one draft', list.filter(x => x.title === 'Dbl').length === 1, JSON.stringify(list.map(x => x.title)));
  const vid = list.find(x => x.title === 'Dbl').vid;
  w = await open(tA, { cur: String(vid), tab: 'c' });
  check('refresh restores the open draft', w.document.body.textContent.includes('Dbl') && w.document.querySelector('#ed').value.includes('Nova Desk'));
  w = await open(tA, { cur: '99999', tab: 'c' });
  check('stale restored draft falls back quietly to a new draft form', !!w.document.querySelector('#tx') && !w.__alert);
  w = await open(tA, { tab: 'i' });
  check('refresh restores the selected tab', w.document.body.textContent.includes('Governance insights'));
  const tR = await login('rina'); w = await open(tR); d = w.document;
  check('reviewer sees review-queue guidance and no New draft button', d.body.textContent.includes('Review queue') && ![...d.querySelectorAll('button')].some(b => b.textContent.trim() === '+ New draft'));
  const tM = await login('manoj'); w = await open(tM, { tab: 'c' });
  check('manager sees role-specific empty state', w.document.body.textContent.includes('Managers can also create drafts') || w.document.body.textContent.includes('Dbl'));
  console.log(failed ? `\n${failed} FAILED` : '\nPOLISH UI CHECKS PASSED'); process.exit(failed ? 1 : 0);
})();
