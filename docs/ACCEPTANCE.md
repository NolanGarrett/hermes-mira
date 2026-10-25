# Acceptance and self-review

## Delivered boundary

Usable, local host developer preview: a registered native platform adapter and the shared companion run through the installed gateway framework. The original verification run made no production installation, source-core changes, real credential persistence, commits, pushes or public release. Public source publication and MIT licensing were subsequently authorized; they do not broaden the runtime or hardware assurance below. Temporary test listeners are stopped. No official MIRA package or full end-to-end hardware support is claimed.

Tested framework: Hermes 0.22.0, build e06df9c2eae6901f4c88f464e0ae6e753c0428b8; Python 3.14.7, aiohttp 3.14.3, Node 26.7.0, playwright-core 1.64.1 with existing Chromium. Older compatibility was not established; the enforced 0.22.0 floor is conservative.

## Executed evidence

- 14 shared JavaScript tests pass: wire UTF-8 budgets, glyph fallback, pagination, ACK order/retries, bounded queue, simulated input release, lost receipt, unknown outcome, admission serialization, credential shape/routing exclusion, documented bridge double, reserved-ticket recovery, stale-response protection and cancel-during-ticket race.
- 12 installed-framework integration tests pass: real plugin discovery/adapter factory/lifecycle; native GatewayRunner authorization/session/egress; synthetic same-session followup; missing/invalid auth; code reuse/expiry; grant expiry/revocation; native allowlist removal; Origin/Host/CSRF/schema rejection; identity/session/profile/control attacks; replay/conflict single-dispatch; timeout/cancel/backend error; restart/retention unknown outcome; long Unicode; local socket and cleanup; reserved-ticket cancellation.
- Actual native plugin-host isolation negative test passes. Host policy refuses register_platform; plugin never downgrades it.
- Chromium passes 13 scenario groups through the actual addon, with all seven states observed: listening, submitting, working, answer, cancelled, disconnected, error. Includes followup, phone/device disconnect, delayed response, timeout recovery, native stop, approval denial, reload/re-pair, long pages, revocation and mobile layout. No uncaught page errors, persistent browser storage or cookies.
- Synthetic approval case uses the real native pending approval wait/queue and resolves deny. No real command is executed. It is not merely a fabricated denial string.
- Desktop/mobile screenshots were visually inspected: readable full-size canvas, no clipped lines or horizontal page overflow, visible simulation labels, cleared code field, no secret/reasoning/tool payload displayed. Mobile canvas scales down; physical lens readability is not established.
- Exact source/archive scan, extracted-distribution smoke tests and ZIP integrity are recorded by `packaging.json` in the evidence archive. Those are packaging gates, not an open-source license or universal secret-scan guarantee.

Machine-readable primary receipts: `acceptance.json`, `native-tests.json`, `browser-tests.json`, `browser-cleanup.json`, `host-isolation.json`, `compatibility.json`, `official-sources.json`. The evidence archive carries these plus logs and screenshots, not full vendor documentation dumps.

## Requirement-by-requirement review

| Requirement | Outcome |
|---|---|
| Real plugin manifest/register/context/platform adapter; installed discovery/lifecycle; diagnostics | PASS locally. Tested native framework, conservative version floor, explicit in-process limitation and actual host-isolation refusal. |
| Normal gateway, server-bound principal/profile/conversation, native auth/session attacks | PASS locally with synthetic inference. One standalone profile; multiplex/profile routes rejected. No recursive API call. Real-model/followup/tool turn remains unmet. |
| Narrow authenticated private transport, revocable admission, expiry, origin/CSRF, limits/errors | PASS loopback preview. Local operator admission + native allowlist; runtime-only credentials; no public or phone-reachable deployment. |
| Shared JS harness/MIRA seam, 640x480, events/states/followup/disconnect, lifecycle | PASS software simulation. Exact documented JS API names, synthetic bridge double. Real mic/native transcription/hardware execution unverified. |
| Ordered handling ACKs, byte budgets, Unicode/long text, duplicate/body conflict, restart/cleanup | PASS local transport and shared logic. Gateway acceptance not completion; no blind replay or API-server durability claim. Physical shared-helper ACK behavior still unverified. |
| Fail closed unavailable approvals; no ring approval grant; no raw output | PASS deterministic native approval queue fixture. Existing upstream tool policy unchanged; no proactive/media delivery. |
| Bounded official API/SDK recheck and genuine official validation only | PASS research boundary. Four MIRA pages rechecked; SDK/export still unavailable. No fake WASM/validator/package produced. |
| Auth/error/timeout/cancel/reconnect/delay/ordered pages/restart/security tests | PASS independently runnable software suites, actual installed framework and actual browser, synthetic inference explicitly labeled. |
| Standalone sanitized distribution, exact instructions, license distinction, remaining gates | PASS developer-preview deliverable. Extracted archive smoke-tested; no active installation. Original code subsequently licensed MIT; SDK redistribution rights remain separate. |

## Explicit unmet acceptance

1. Native-plugin live-model turn, model followup and real read-only tool-backed turn were not executed. The supplied isolated launcher deliberately uses synthetic inference. API-server access is a different execution path and must not be reused recursively to claim native-platform qualification. No real profile secrets were copied and no active plugin was installed. An authorized isolated live qualification remains needed; this does not establish that new credentials or production installation are necessary.
2. Official full SDK/shared modules/example/build configuration/packager/validator and redistribution terms are unavailable. Compile/official validation/importable MIRA package are therefore unmet, not replaced by these tests.
3. No actual glasses/ring/iPhone. Real capture/transcription, rendering, transport origin/private network path, foreground pairing inside MIRA, locked/idle execution, suspension recovery, persistent credential support, lens readability and battery/Bluetooth remain unverified.
4. Public source publication and MIT licensing are now owner-authorized. No production deployment, app-store/catalog publication, official SDK redistribution, or hardware support certification is included.

These gaps do not prevent running the host preview. They do prevent calling it complete MIRA support, a hardware alpha, production-ready phone access, or a purchase justification for unattended operation.
