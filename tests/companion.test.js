import test from 'node:test';
import assert from 'node:assert/strict';
import {Companion,PageChannel,HttpBackend,bytes,validateWire,ascii,pages} from '../web/companion.js';
import {bindMiraCompanion} from '../web/mira-binding.js';
const tick=()=>new Promise(r=>setImmediate(r));
function setup(backend={}) {
  const sent=[];let c;
  c=new Companion({submit:async()=>({state:'working'}),status:async()=>({state:'answer',answer:'synthetic answer'}),recover:async()=>({state:'answer',answer:'recovered'}),cancel:async()=>({state:'cancelled'}),...backend},async m=>{await tick();sent.push(m);c.fromDevice({type:'ack',stream:m.stream,seq:m.seq});},()=>{},()=> 'synthetic-request');
  return {c,sent};
}
test('all four documented byte budgets count JSON UTF-8, not characters',()=>{
  for(const [direction,limit] of Object.entries({out:3500,in:4096,latestOut:380,latestIn:379})){
    const exact={x:'a'.repeat(limit-8)};
    assert.equal(bytes(exact),limit);validateWire(exact,direction);
    assert.throws(()=>validateWire({x:exact.x+'a'},direction));
    assert.throws(()=>validateWire({x:'é'.repeat(limit)},direction));
  }
  assert.throws(()=>validateWire({},'typo'));
});
test('unsupported glyphs and long words remain bounded ASCII pages',()=>{
  assert.equal(ascii('Café — 漢字 🗺'),'Cafe - ?? ?');
  const result=pages(('abc '.repeat(1000))+'x'.repeat(200));
  assert.ok(result.length>1);
  for(const lines of result){assert.ok(lines.length<=12);for(const line of lines){assert.ok(line.length<=40);assert.match(line,/^[\x20-\x7e]*$/);}}
});
test('transport acceptance is not handling; only exact ordered ACK releases next',async()=>{
  const sent=[];const channel=new PageChannel(async x=>sent.push(x),'synthetic-stream');
  channel.enqueue({lines:['one']});channel.enqueue({lines:['two']});await tick();
  assert.equal(sent.length,1);
  channel.ack({type:'ack',stream:'wrong',seq:1});assert.equal(sent.length,1);
  channel.ack({type:'ack',stream:'synthetic-stream',seq:2});assert.equal(sent.length,1);
  await channel.retry();assert.equal(sent[1].seq,1);
  channel.ack({type:'ack',stream:'synthetic-stream',seq:1});await tick();assert.equal(sent[2].seq,2);
  channel.ack({type:'ack',stream:'synthetic-stream',seq:1});assert.equal(channel.pending.seq,2);
});
test('bounded queue, failed validation consumes no sequence, disconnected retry preserves ID',async()=>{
  let offline=true;const sent=[];const channel=new PageChannel(async x=>{if(offline)throw Error();sent.push(x);},'bounded');
  assert.throws(()=>channel.enqueue({x:'a'.repeat(3500)}));assert.equal(channel.seq,0);
  for(let i=0;i<33;i++)channel.enqueue({lines:[String(i)]});
  assert.throws(()=>channel.enqueue({lines:['overflow']}));assert.equal(channel.seq,33);
  await tick();assert.ok(channel.error);offline=false;await channel.retry();assert.equal(sent[0].seq,1);
});
test('hold-end, sidebar, hidden typed submission and app exit stop simulated capture',async()=>{
  let calls=0;const {c}=setup({submit:async()=>{calls++;return{state:'working'};}});
  await c.event('hold-start');assert.equal(c.state,'listening');
  await c.event('sidebar');await c.event('hold-end','hidden');await c.submit('hidden typed');assert.equal(calls,0);
  await c.event('sidebar');await c.event('tap');await c.event('app-exit');assert.equal(c.state,'cancelled');
  await c.event('hold-end','hidden');assert.equal(calls,0);
  await c.event('app-open');await c.event('hold-start');await c.event('hold-end','visible');assert.equal(calls,1);
});
test('lost submit receipt locks admission and recovers, never resends',async()=>{
  let calls=0;const {c}=setup({submit:async()=>{calls++;throw Error('lost receipt');}});
  await c.submit('one');assert.equal(c.state,'disconnected');
  await c.submit('two');assert.equal(calls,1);
  await c.reconnect();assert.equal(c.state,'answer');assert.equal(calls,1);
});
test('unknown server outcome holds request through reconnect',async()=>{
  const {c}=setup({submit:async()=>({state:'unknown'}),recover:async()=>({state:'unknown'})});
  await c.submit('one');await c.reconnect();assert.equal(c.active,'synthetic-request');assert.equal(c.state,'disconnected');
});
test('pending ticket issuance serializes submits and rejects oversize before network',async()=>{
  let tickets=0,calls=0;const {c}=setup({ticket:async()=>{tickets++;await tick();return{request_id:'ticket'};},submit:async()=>{calls++;return{state:'working'};}});
  await c.submit('é'.repeat(2049));assert.equal(tickets,0);
  await Promise.all([c.submit('one'),c.submit('two')]);assert.equal(tickets,1);assert.equal(calls,1);
});
test('cancel, poll failure, ordered navigation and followup use same companion',async()=>{
  const {c}=setup({submit:async()=>({state:'answer',answer:'word '.repeat(1000)})});
  await c.submit('long');assert.equal(c.state,'answer');
  await c.event('swipe-backward');assert.equal(c.page,1);
  await c.event('swipe-forward');assert.equal(c.page,0);
  await c.cancel();assert.equal(c.state,'cancelled');
  c.active='request';c.backend.status=async()=>{throw Error();};await c.poll();assert.equal(c.state,'disconnected');
});
test('HTTP credential stays runtime-only and client cannot append routing fields',async()=>{
  const calls=[];const b=new HttpBackend(async(path,init)=>{calls.push({path,init});return{ok:true,json:async()=>({token:'SYNTHETIC-TEST-TOKEN',expires_in:900,boot:'synthetic'})};});
  assert.deepEqual(await b.pair('SYNTHETIC-TEST-CODE'),{expires_in:900});
  await b.submit('ticket','hello',{profile:'forged'});
  assert.equal(calls[1].init.headers.Authorization,'Bearer SYNTHETIC-TEST-TOKEN');
  assert.deepEqual(JSON.parse(calls[1].init.body),{request_id:'ticket',text:'hello'});
  await b.revoke();assert.equal(b.token,null);
});
test('documented MIRA bridge names bind SAME class; dispose stops capture/unsubscribes',async()=>{
  let receive,unsubscribed=false;const sent=[];
  const bound=bindMiraCompanion({bridge:{sendToApp:async x=>sent.push(x),onFromApp:fn=>{receive=fn;return()=>{unsubscribed=true;};}},backend:{submit:async()=>({state:'answer',answer:'synthetic'})}});
  assert.ok(bound.companion instanceof Companion);
  receive({type:'input',event:'hold-start'});assert.equal(bound.companion.state,'listening');
  bound.dispose();assert.ok(unsubscribed);assert.equal(bound.companion.state,'cancelled');
  receive({type:'input',event:'hold-end',transcript:'must not submit'});await tick();assert.equal(bound.companion.active,null);
  assert.ok(sent.length); // Synthetic bridge double, NOT hardware evidence.
});
test('reserved-ticket recovery is visible, cancellable and never auto-submits',async()=>{
  const {c}=setup({current:async()=>({current:{request_id:'ticket',state:'reserved'}})});
  await c.restore();assert.equal(c.active,'ticket');assert.equal(c.state,'disconnected');
  await c.cancel();assert.equal(c.active,null);
});
test('late old poll cannot overwrite a newer active request',async()=>{
  let release;const {c}=setup({status:()=>new Promise(r=>release=r)});
  c.active='old';c.state='working';const pending=c.poll();
  c.active='new';release({state:'answer',answer:'stale'});await pending;
  assert.equal(c.active,'new');assert.equal(c.state,'working');
});
test('cancel while reserving a ticket prevents text submission',async()=>{
  let release,submitted=0,cancelled=0;
  const {c}=setup({ticket:()=>new Promise(r=>release=r),
    submit:async()=>{submitted++;return{state:'working'};},
    cancel:async()=>{cancelled++;return{state:'cancelled'};}});
  const pending=c.submit('do not send');await c.cancel();
  release({request_id:'reserved'});await pending;
  assert.equal(submitted,0);assert.equal(cancelled,1);assert.equal(c.active,null);
});
