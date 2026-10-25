import {Companion,HttpBackend,validateWire} from './companion.js';
const $ = id=>document.getElementById(id);
const backend = new HttpBackend();
const ctx = $('glass').getContext('2d');
let sequence = 0, stream = null, companion;
function draw(frame) {
  ctx.fillStyle='#050705';ctx.fillRect(0,0,640,480);
  ctx.fillStyle='#b7d8bc';ctx.font='18px monospace';
  ctx.fillText(`MIRA / ${frame.state.toUpperCase()}`,24,32);
  ctx.font='24px monospace';frame.lines.forEach((line,i)=>ctx.fillText(line,24,72+i*30));
  ctx.font='16px monospace';ctx.fillText(`${frame.page} / ${frame.total}    SIMULATED`,24,458);
  $('page').textContent=`${frame.page} / ${frame.total}`;
  $('accessible').textContent=frame.lines.join('\n');
}
async function send(frame) {
  validateWire(frame,'out');
  await Promise.resolve(); // shared Companion has finished construction before ACK
  if ($('device').checked) throw Error('SIMULATED disconnected');
  if (stream !== frame.stream) {stream=frame.stream;sequence=0;}
  if (frame.seq === sequence+1) {draw(frame);sequence=frame.seq;}
  if (frame.seq === sequence) companion.fromDevice({type:'ack',stream,seq:sequence});
}
companion = new Companion(backend,send,({state,message})=>{
  $('state').textContent=state;$('status').textContent=message;
});
const transcript = ()=>$('fixture').value || $('text').value;
const run = fn=>Promise.resolve().then(fn).catch(()=>companion.set('error','Operation unavailable. Re-pair or recover; do not blindly resubmit.'));
$('pair').onclick=()=>run(async()=>{
  const code=$('code').value;$('code').value='';
  const result=await backend.pair(code);
  $('auth').textContent=`Paired in memory for ${result.expires_in} seconds. Reload requires re-pairing.`;
  await companion.restore();
});
$('revoke').onclick=()=>run(async()=>{
  await backend.revoke();$('auth').textContent='Revoked. Foreground re-pair required.';
  companion.set('disconnected','Access revoked. Existing work is not rolled back.');
});
$('submit').onclick=()=>run(()=>companion.submit(transcript()));
for(const button of document.querySelectorAll('[data-event]'))button.onclick=()=>run(()=>companion.event(button.dataset.event,transcript()));
$('cancel').onclick=()=>run(()=>companion.cancel());
$('recover').onclick=()=>run(()=>companion.reconnect());
$('phone').onchange=()=>{backend.online=!$('phone').checked;if(!backend.online)companion.set('disconnected','SIMULATED phone offline. Request identity retained.');};
$('device').onchange=()=>{if(!$('device').checked)run(()=>companion.channel.retry());};
const timer=setInterval(()=>run(()=>companion.poll()),200);
addEventListener('pagehide',()=>{clearInterval(timer);companion.event('app-exit');backend.token=null;});
document.addEventListener('visibilitychange',()=>{if(document.hidden)companion.event('app-exit');});
// No local/session storage, cookies, privileged key, microphone or Bluetooth APIs.
