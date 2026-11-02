const { JSDOM } = require('jsdom'); const BASE=process.env.BASE||'http://127.0.0.1:8011'; const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{const html=await (await fetch(BASE+'/')).text();
const dom=new JSDOM(html,{url:BASE+'/',runScripts:'dangerously',pretendToBeVisual:true,beforeParse(w){w.fetch=(u,o)=>fetch(new URL(u,BASE).href,o);w.alert=m=>{w.__a=m}}});
const w=dom.window,d=w.document;await sleep(500);
console.log('login page shows demo creds:',d.body.textContent.includes('demo123')&&d.body.textContent.includes('manoj'));
d.querySelector('#lu').value='asha';d.querySelector('#lp').value='nope';w.login();await sleep(400);console.log('wrong password message:',w.__a);
d.querySelectorAll('tr')[2].click();console.log('row click fills form:',d.querySelector('#lu').value,d.querySelector('#lp').value);
w.login();await sleep(600);console.log('signed in header:',d.querySelector('#who').textContent.trim());
d.querySelector('#who button').click();await sleep(400);console.log('after sign out shows login:',!!d.querySelector('#lu'));process.exit(0)})();
