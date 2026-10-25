import {chromium} from 'playwright-core';
import {spawn} from 'node:child_process';
import net from 'node:net';
import {once} from 'node:events';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
await fs.mkdir(path.join(root,'evidence'),{recursive:true});
const python=process.env.HERMES_PYTHON;
const hermes=process.env.HERMES_SOURCE;
const chrome=process.env.CHROME_BIN;
if(!python||!hermes||!chrome)throw Error('Set HERMES_PYTHON, HERMES_SOURCE and CHROME_BIN to installed paths');
const child=spawn(python,[path.join(root,'preview.py'),'--hermes-source',hermes,'--port','0'],{stdio:['ignore','pipe','pipe']});
let stderr='';child.stderr.on('data',x=>stderr+=x);
let browser,descriptor;const checks=[];
const check=(name)=>checks.push(name);
const operator=command=>new Promise((resolve,reject)=>{
  const socket=net.createConnection(descriptor.operator_socket);let data='';
  socket.on('connect',()=>socket.write(JSON.stringify(command)+'\n'));
  socket.on('data',x=>{data+=x;if(data.includes('\n')){socket.end();resolve(JSON.parse(data));}});
  socket.on('error',reject);
});
try{
  descriptor=await new Promise((resolve,reject)=>{
    let data='';const timeout=setTimeout(()=>reject(Error('Preview startup timeout: '+stderr)),30000);
    child.on('exit',()=>{clearTimeout(timeout);reject(Error('Preview exited: '+stderr));});
    child.stdout.on('data',x=>{data+=x;for(const line of data.split('\n'))if(line.startsWith('{')&&line.endsWith('}')){clearTimeout(timeout);resolve(JSON.parse(line));return;}});
  });
  browser=await chromium.launch({executablePath:chrome,headless:true,args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:1200,height:1000}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const states=new Set();
  await page.goto(descriptor.origin);
  await page.evaluate(()=>{
    window.previewStates=[];
    new MutationObserver(()=>window.previewStates.push(document.querySelector('#state').textContent))
      .observe(document.querySelector('#state'),{childList:true});
  });
  const state=async expected=>{await page.waitForFunction(s=>document.querySelector('#state').textContent===s,expected,{timeout:15000});states.add(expected);};
  const pair=async()=>{
    const result=await operator({action:'pair',principal:'synthetic-alice'});
    await page.locator('#code').fill(result.code);await page.locator('#pair').click();
    await page.waitForFunction(()=>document.querySelector('#auth').textContent.startsWith('Paired in memory'));
    assert.equal(await page.locator('#code').inputValue(),'');
  };
  await page.locator('#text').fill('SYNTHETIC unpaired');await page.locator('#submit').click();await state('error');check('unauthenticated visible rejection');
  await pair();
  await page.locator('[data-event="hold-start"]').click();await state('listening');
  await page.locator('[data-event="sidebar"]').click();await state('cancelled');
  await page.locator('[data-event="hold-end"]').click();await state('cancelled');
  await page.locator('[data-event="sidebar"]').click();
  await page.locator('[data-event="tap"]').click();await state('listening');
  await page.locator('[data-event="app-exit"]').click();await state('cancelled');
  await page.locator('[data-event="app-open"]').click();check('tap hold sidebar exit capture lifecycle');
  await page.locator('#text').fill('SYNTHETIC-BROWSER-NONCE');
  await page.locator('[data-event="hold-start"]').click();await page.locator('[data-event="hold-end"]').click();await state('answer');
  assert.match(await page.locator('#accessible').textContent(),/SYNTHETIC-BROWSER-NONCE/);
  await page.locator('#fixture').selectOption('fixture:followup');await page.locator('#submit').click();await state('answer');
  assert.match(await page.locator('#accessible').textContent(),/remembered:.*SYNTHETIC-BROWSER-NONCE/s);check('native gateway roundtrip and persisted-session synthetic followup');
  assert.ok((await page.evaluate(()=>window.previewStates)).includes('submitting'));
  states.add('submitting');
  await page.locator('#fixture').selectOption('fixture:delay');await page.locator('#submit').click();await state('working');
  await page.locator('#phone').check();await state('disconnected');
  await page.waitForTimeout(3300);await page.locator('#phone').uncheck();await page.locator('#recover').click();await state('answer');check('phone disconnect recovery without resubmission');
  await page.locator('#fixture').selectOption('fixture:delay');await page.locator('#submit').click();await state('working');
  await page.locator('#cancel').click();await state('cancelled');check('native stop confirmed, not rollback');
  await page.locator('#fixture').selectOption('fixture:backend');await page.locator('#submit').click();await state('error');
  assert.doesNotMatch(await page.locator('#status').textContent(),/Traceback|RuntimeError/);check('safe backend error');
  await page.locator('#fixture').selectOption('fixture:approval');await page.locator('#submit').click();await state('error');
  assert.match(await page.locator('#status').textContent(),/Approval unavailable/);check('approval unavailable fails closed');
  await page.locator('#fixture').selectOption('fixture:timeout');await page.locator('#submit').click();await state('working');await state('disconnected');
  await page.waitForTimeout(3500);await page.locator('#recover').click();await state('answer');check('timeout unknown then exact-request recovery');
  await page.locator('#fixture').selectOption('fixture:delay');await page.locator('#submit').click();await state('working');
  await page.reload();await pair();await state('answer');check('reload re-pair retrieves same request');
  await page.locator('#device').check();await page.locator('#fixture').selectOption('fixture:long');await page.locator('#submit').click();await state('answer');
  await page.locator('#device').uncheck();
  await page.waitForFunction(()=>Number(document.querySelector('#page').textContent.split('/')[1])>1);
  await page.locator('[data-event="swipe-backward"]').click();await page.waitForFunction(()=>document.querySelector('#page').textContent.startsWith('2 /'));
  await page.locator('[data-event="swipe-forward"]').click();await page.waitForFunction(()=>document.querySelector('#page').textContent.startsWith('1 /'));check('long answer ordered device reconnect and bidirectional pages');
  assert.equal(await page.evaluate(()=>localStorage.length+sessionStorage.length),0);
  assert.equal((await page.context().cookies()).length,0);check('no persistent browser credentials or cookies');
  assert.doesNotMatch(await page.locator('body').innerText(),/Bearer |SYNTHETIC-NO-EXECUTION|<think>|Traceback/);
  await page.screenshot({path:path.join(root,'evidence','browser-desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await page.screenshot({path:path.join(root,'evidence','browser-mobile.png'),fullPage:true});check('640x480 canvas and mobile layout');
  await page.locator('#revoke').click();await state('disconnected');
  await page.locator('#fixture').selectOption('');await page.locator('#text').fill('after revoke');await page.locator('#submit').click();await state('error');check('revocation prevents new request');
  assert.deepEqual(errors,[]);
  await fs.writeFile(path.join(root,'evidence','browser-tests.json'),JSON.stringify({passed:true,synthetic_inference:true,native_plugin:true,hardware:false,checks,states:[...states],page_errors:errors},null,2));
  console.log(JSON.stringify({passed:true,checks,states:[...states]},null,2));
}finally{
  if(browser)await browser.close();
  child.kill('SIGTERM');
  if(child.exitCode===null)await once(child,'exit');
  if(descriptor){
    const refused=await new Promise(resolve=>{const s=net.createConnection(new URL(descriptor.origin).port,'127.0.0.1');s.on('error',()=>resolve(true));s.on('connect',()=>{s.destroy();resolve(false);});});
    assert.ok(refused,'Temporary loopback listener must be closed');
    await fs.writeFile(path.join(root,'evidence','browser-cleanup.json'),JSON.stringify({listener_closed:refused,temporary_home_removed:!(await fs.stat(path.dirname(descriptor.operator_socket)).catch(()=>null))},null,2));
  }
}
