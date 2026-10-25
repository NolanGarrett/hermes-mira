# Device-side preparation — no SDK/package claim

Official sources rechecked during this build:

- https://trymira.com/docs/api-reference
- https://trymira.com/docs/quickstart
- https://trymira.com/docs/phone-companion
- https://trymira.com/docs/packaging
- https://hermes-agent.nousresearch.com/docs/developer-guide/plugins/
- https://hermes-agent.nousresearch.com/docs/developer-guide/adding-platform-adapters/

All returned HTTP 200. The four checked official MIRA pages exposed no linked downloadable SDK archive/shared Rust/packager/validator candidate. This bounded result does not prove that no official export exists elsewhere. No guessed archive URL, community compiled WASM, custom validator, purchase or vendor contact was substituted.

## Acquire the real export

On an authorized iPhone: MIRA → Apps → Build a Mira App → Create → Instructions for making apps → Share full guide (or Copy full guide). The documented prerequisite is connected glasses. Whether onboarding can be skipped without glasses is unverified. Supply the complete export, not just a copied public API page.

Needed: Shared/companion.rs, other shared Rust modules (including documented Shared/content.rs), official unchanged example/build configuration, CompanionExample/package.py, official validate.py and redistribution/license terms. Do not invent further filenames/layout until inspecting the actual guide. Inspect provenance and source before execution. Compile the unchanged official example first, run its official validator, then integrate this companion and validate the actual final package.

Public low-level ABI alone is insufficient: exported app_init/app_render/app_event/app_stop/memory; imports from mira; live transcription methods 0x0001 start, 0x0002 stop and 0x0003 latest transcript. The official shared helper manages registration, framing, paging and ACK behavior; do not call underlying Bluetooth requests directly just because their numbers are public.

## Proposed bridge

`web/mira-binding.js` invokes only documented `miraCompanion.sendToApp(value)` and `miraCompanion.onFromApp(handler)` and uses the same Companion class as the browser. It is not a fabricated SDK. Device JSON messages are OUR proposed protocol, not vendor event envelopes:

    {"type":"page","stream":"ephemeral-id","seq":1,"state":"answer","lines":["ASCII text"],"page":1,"total":2}
    {"type":"ack","stream":"ephemeral-id","seq":1}
    {"type":"input","event":"hold-end","transcript":"final native transcript"}

Phone → app JSON max 3500 bytes; reverse max 4096. Latest state max 380 outward/379 inward; never use it for indispensable answer chunks. ACK only after handling a whole page. Acceptance of sendToApp is not handling. Call the real Rust companion tick each frame and honor its busy/retry behavior. The browser receiver is synthetic, not this official Rust implementation.

Input mapping documented by the API: tap 0, swipe forward 1 (previous), swipe backward 2 (next), hold start 10, hold end 12. System/sidebar gesture claims and stop-on-exit must use the actual Shared/content.rs API after export inspection. A JS unsubscribe does not stop a real microphone; no native mic implementation is present here.

Documented package constraints include single HTML under 2 MB, WASM at most 128 KB, WebAssembly 1.0, exactly one 64 KiB memory page including stack, no WASI/threads/SIMD/start section. Use official compiler flags/build config and validator, not guesses. This repository deliberately contains no MIRA manifest/WASM payload; web/index.html must not be uploaded as a MIRA app.

## Remaining physical checklist

Every item below is UNVERIFIED:

- [ ] Official example and integrated app compile; both real final HTML packages pass official validation.
- [ ] Import/install/sidebar launch on actual glasses; record SDK/app/firmware versions.
- [ ] Real ring/temple gestures, system overlay priority, hold release and app switching.
- [ ] Microphone permissions, native transcription finality, stop-on-exit and Bluetooth reconnect.
- [ ] Authorized private HTTPS transport from actual iPhone, with verified origin/admission behavior. No public ingress assumption.
- [ ] Runtime-only foreground pairing works inside actual MIRA; secure persistent sign-in separately established or explicitly unsupported.
- [ ] Fresh requests with iPhone locked and idle, not merely with the companion sheet closed.
- [ ] Recovery after iOS JS suspension/process loss without duplicate execution.
- [ ] Actual ordered delivery/ACK/backpressure under disconnect.
- [ ] Physical fonts, prescription-lens readability, contrast, battery and range.
- [ ] Custom spoken output if required; not implied by the microphone API.

Cookie non-persistence and MIRA's warning against tokens/passwords/personal data in ordinary companion storage prevent claiming durable sign-in. Native MIRA assistant background behavior does not prove a custom companion can execute while locked. Do not base a hardware purchase on those assumptions.
