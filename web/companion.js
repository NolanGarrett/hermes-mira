// Shared host-side logic: browser harness and future MIRA companion use this file.
// No SDK stub, persistent credentials/storage, microphone or Bluetooth implementation.
export const bytes = value => new TextEncoder().encode(JSON.stringify(value)).length;
export function validateWire(value, direction) {
  const limits = {out:3500, in:4096, latestOut:380, latestIn:379};
  const limit = limits[direction];
  if (!limit) throw Error('Unknown wire direction');
  if (!value || typeof value !== 'object' || bytes(value) > limit) throw Error(`JSON exceeds ${limit} byte wire limit`);
  return value;
}
export function ascii(text) {
  return String(text).replace(/[“”]/g, '"').replace(/[‘’]/g, "'")
    .replace(/[–—]/g, '-').replace(/…/g, '...').replace(/→/g, '->')
    .normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^\x20-\x7e\n]/gu, '?');
}
export function pages(text) {
  const safe = ascii(text); const lines = [];
  for (const paragraph of safe.split('\n')) {
    let line = '';
    for (let word of paragraph.split(/\s+/).filter(Boolean)) {
      if (line && line.length + word.length + 1 > 40) { lines.push(line); line = ''; }
      while (word.length > 40) { lines.push(word.slice(0, 40)); word = word.slice(40); }
      if (word) line += (line ? ' ' : '') + word;
    }
    lines.push(line);
  }
  const result = []; for (let i = 0; i < lines.length; i += 12) result.push(lines.slice(i, i + 12));
  return result.length ? result : [['(No answer)']];
}

// sendToApp acceptance is NOT a device acknowledgement. Only a matching
// application ACK releases the next ordered frame. Retries preserve identity.
export class PageChannel {
  constructor(send, stream = crypto.randomUUID()) {
    this.send = send; this.stream = stream; this.seq = 0; this.queue = []; this.pending = null; this.error = null;
  }
  enqueue(frame) {
    if (this.queue.length >= 32) throw Error('Device queue full; reconnect before further input');
    const message = validateWire({...frame, type:'page', stream:this.stream, seq:this.seq + 1}, 'out');
    this.seq++;
    this.queue.push(message); this.pump(); return message;
  }
  pump() {
    if (this.pending || !this.queue.length) return;
    this.pending = this.queue.shift(); this.retry();
  }
  async retry() {
    if (!this.pending) return;
    try { await this.send(this.pending); this.error = null; }
    catch { this.error = 'Device transport disconnected; pending page retained'; }
  }
  ack(message) {
    validateWire(message, 'in');
    if (message.type === 'ack' && message.stream === this.stream && message.seq === this.pending?.seq) {
      this.pending = null; this.pump();
    }
  }
}

export class HttpBackend {
  constructor(fetcher = (...args)=>globalThis.fetch(...args)) {
    this.fetcher = fetcher; this.online = true; this.token = null; this.boot = null;
  }
  async pair(code) {
    const result = await this.call('/api/pair', 'POST', {code});
    this.token = result.token; this.boot = result.boot;
    return {expires_in:result.expires_in};
  }
  async revoke() {
    try { return await this.call('/api/revoke', 'POST', {}); }
    finally { this.token = null; }
  }
  ticket() { return this.call('/api/ticket', 'POST', {}); }
  current() { return this.call('/api/current'); }
  async call(path, method = 'GET', body) {
    if (!this.online) throw Error('SIMULATED phone network disconnected');
    const ctrl = new AbortController(); const timer = setTimeout(()=>ctrl.abort(), 10000);
    try {
      const r = await this.fetcher(path, {method, signal:ctrl.signal, cache:'no-store',
        headers:{'Content-Type':'application/json','X-Mira-Client':'1',
          ...(this.token ? {Authorization:`Bearer ${this.token}`} : {})}, ...(body ? {body:JSON.stringify(body)} : {})});
      if (!r.ok) {
        const error = Error(r.status === 401 || r.status === 403 ? 'Authentication failed; foreground re-pair required' : `Backend HTTP ${r.status}`);
        error.definite = r.status >= 400 && r.status < 500 && r.status !== 408;
        throw error;
      }
      return await r.json();
    } finally { clearTimeout(timer); }
  }
  submit(requestId, text) { return this.call('/api/requests', 'POST', {request_id:requestId, text}); }
  status(id) { return this.call(`/api/requests/${id}`); }
  recover(id) { return this.call(`/api/requests/${id}/recover`, 'POST', {}); }
  cancel(id) { return this.call(`/api/requests/${id}/stop`, 'POST', {}); }
}

export class Companion {
  constructor(backend, send, onChange = ()=>{}, newId = ()=>crypto.randomUUID()) {
    this.backend = backend; this.onChange = onChange; this.newId = newId;
    this.state = 'cancelled'; this.message = 'Ready. Hold or tap, then enter a typed request.';
    this.active = null; this.answerPages = []; this.page = 0; this.visible = true; this.overlay = false;
    this.revision = 0;
    this.channel = new PageChannel(send); this.publish();
  }
  publish() {
    const lines = this.state === 'answer' ? this.answerPages[this.page] : pages(this.message)[0];
    try {
      this.channel.enqueue({state:this.state, lines, page:this.state === 'answer' ? this.page + 1 : 1, total:this.state === 'answer' ? this.answerPages.length || 1 : 1});
    } catch {
      this.state = 'disconnected'; this.message = 'Device queue full. Reconnect before further input.';
    }
    this.onChange({state:this.state, message:this.message, requestId:this.active});
  }
  set(state, message) {
    if (this.state === state && this.message === message) return;
    this.state = state; this.message = message; this.publish();
  }
  async event(event, transcript = '', options = {}) {
    if (event === 'app-open') { this.visible = true; this.overlay = false; this.publish(); return; }
    if (event === 'app-exit' || event === 'sidebar') {
      if (event === 'app-exit') this.visible = false; else this.overlay = !this.overlay;
      if (this.state === 'listening') this.set('cancelled', 'Capture stopped: app hidden. No transcript submitted.');
      return;
    }
    if (event === 'hold-end') {
      if (this.state === 'listening' && !this.overlay && this.visible) await this.submit(transcript, options);
      return; // Always consume hold-end, including a start ignored under overlay.
    }
    if (this.overlay || !this.visible) return;
    if (event === 'hold-start' || event === 'tap') {
      if (!this.active) this.set('listening', 'SIMULATED microphone. Type the transcript, then end hold.');
    }
    if (event === 'swipe-forward' || event === 'swipe-backward') {
      if (this.state === 'answer') {
        this.page = Math.max(0, Math.min(this.answerPages.length - 1, this.page + (event === 'swipe-forward' ? -1 : 1)));
        this.publish();
      }
    }
  }
  fromDevice(value) { validateWire(value, 'in'); if (value.type === 'ack') this.channel.ack(value); }
  async submit(text, options = {}) {
    if (this.active || this.admitting || this.overlay || !this.visible) return;
    if (!text.trim()) { this.set('error', 'No transcript. Typed input is required; real STT is unverified.'); return; }
    if (new TextEncoder().encode(text).length > 4096) { this.set('error', 'Request exceeds 4096 UTF-8 bytes.'); return; }
    this.revision++;
    this.admitting = true; this.cancelBeforeAdmission = false; this.answerPages = []; this.page = 0;
    this.set('submitting', 'Submitting once. Retaining request identity for recovery.');
    try {
      this.active = this.backend.ticket ? (await this.backend.ticket()).request_id : this.newId();
      const id = this.active;
      const result = this.cancelBeforeAdmission
        ? await this.backend.cancel(id) : await this.backend.submit(id, text, options);
      if (this.active === id) this.apply(result);
    }
    catch (e) {
      if (e.definite) { this.active = null; this.set('error', e.message); }
      else this.set('disconnected', 'Submission receipt lost. Outcome unknown; reconnect, do not resubmit.');
    } finally { this.admitting = false; }
  }
  apply(result) {
    if (result.state === 'reserved') {
      this.set('disconnected', 'Unused ticket recovered; no text submitted. Cancel to release it.');
    } else if (result.state === 'answer') {
      this.answerPages = pages(result.answer); this.page = 0; this.active = null; this.set('answer', 'Final answer');
    } else if (result.state === 'cancelled' || result.state === 'error') {
      this.active = null; this.set(result.state, result.message || result.state);
    } else if (result.state === 'disconnected') {
      this.set('disconnected', result.message || 'Connection unavailable. Recover this request.');
    } else if (result.state === 'unknown') {
      this.set('disconnected', 'Outcome unknown. Submission held; no automatic retry or new request.');
    } else this.set('working', result.message || 'Working. Only final answer will be displayed.');
  }
  async poll() {
    if (!this.active || this.state === 'disconnected') return;
    const id = this.active;
    try { const result = await this.backend.status(id); if (this.active === id) this.apply(result); }
    catch { if (this.active === id) this.set('disconnected', 'Status connection lost or timed out. Reconnect to the same request.'); }
  }
  async reconnect() {
    await this.channel.retry(); if (!this.active) { await this.restore(); return; }
    const id = this.active;
    try { const result = await this.backend.recover(id); if (this.active === id) this.apply(result); }
    catch { if (this.active === id) this.set('disconnected', 'Recovery unavailable. Request retained; do not resubmit.'); }
  }
  async cancel() {
    if (!this.active) { this.cancelBeforeAdmission = true; this.set('cancelled','Cancelled before submission.'); return; }
    const id = this.active;
    try { const result = await this.backend.cancel(id); if (this.active === id) this.apply(result); }
    catch { if (this.active === id) this.set('disconnected','Stop unconfirmed. Reconnect for exact run status.'); }
  }
  async restore() {
    if (this.admitting) return;
    const revision = this.revision;
    try {
      const result = await this.backend.current();
      if (this.revision !== revision) return;
      if (result.current) { this.active = result.current.request_id; this.apply(result.current); }
      else this.set('cancelled', 'Paired. No request to recover. After server restart reconcile prior unknown work before retyping.');
    } catch { if (this.revision === revision) this.set('error', 'Recovery requires foreground pairing.'); }
  }
}
