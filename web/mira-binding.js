// Preparation seam using ONLY publicly documented companion methods.
// Not an SDK, installed app, secure sign-in or hardware validation.
import {Companion, validateWire} from './companion.js';

// backend must implement submit/status/recover/cancel, with credential isolation.
// Do NOT pass a privileged API key or store tokens using miraCompanion.storeSet.
export function bindMiraCompanion({bridge, backend, onChange, newId}) {
  if (!bridge || typeof bridge.sendToApp !== 'function' || typeof bridge.onFromApp !== 'function') throw Error('Official miraCompanion runtime is required');
  if (!backend) throw Error('An authenticated narrow backend is required; real MIRA networking remains unverified');
  const companion = new Companion(backend, m=>bridge.sendToApp(m), onChange, newId);
  let disposed = false;
  const unsubscribe = bridge.onFromApp(message=>{
    if (disposed) return;
    try {
      validateWire(message,'in');
      if (message.type === 'ack') companion.fromDevice(message);
      // These input/transcript envelopes are OUR proposed app protocol,
      // not vendor SDK event or transcription return-value formats.
      if (message.type === 'input' && ['tap','swipe-forward','swipe-backward','hold-start','hold-end','sidebar','app-exit','app-open'].includes(message.event)) {
        Promise.resolve(companion.event(message.event, typeof message.transcript === 'string' ? message.transcript : '')).catch(()=>{});
      }
    } catch { /* Malformed device input never becomes a backend request. */ }
  });
  return {companion, dispose(){ if(!disposed){disposed=true;companion.event('app-exit');if(typeof unsubscribe === 'function') unsubscribe();} }};
}
