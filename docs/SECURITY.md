# Security and recovery

## Trust boundary

The Unix operator socket is local administrative authority, protected by filesystem mode 0600. Same-UID/root access is already trusted; this is not protection against a compromised host or same-origin XSS. No HTTP route can request a principal, profile or chat. A high-entropy, one-use 60-second pairing code binds a native-allowlisted principal to a server-created conversation. Grant secrets are returned once and held in browser runtime memory; the server stores digests and expiry, not tokens. Codes/grants are not files, URLs, cookies, web storage or logs. This is foreground experimental pairing, NOT secure persistent MIRA authentication.

Native authorization is checked during local code issuance, redemption, every authenticated request and again during normal gateway dispatch. Allowlist removal revokes access. A new pair revokes previous grants for that principal. Browser reload requires foreground pairing. The plugin never sets `trusted_inbound`, `authorization_is_upstream`, `internal=True`, or `enforces_own_access_policy` to bypass native gates.

This preview supports one standalone profile only. Client routing fields are rejected. Cross-profile/multiplex configuration refuses startup. Distinct admitted principals get distinct native sessions. Text cannot issue gateway control commands: `allow_gateway_control=False`; only the server's exact-request stop endpoint creates a native `/stop` event. Ring input is not an owner override phrase or general approval grant.

## Network and bounds

Only 127.0.0.1 is bindable. The Host header must match the actual listener; Origin and custom-header checks guard API calls. Same-origin GET may omit Origin only with same-origin Fetch Metadata. Cross-site requests and query parameters are refused. No CORS, forwarding headers or remote host override is provided. Static harness files have no credentials and are publicly readable on the loopback listener; all data-bearing APIs require a code or grant. Pairing is limited to 10 attempts per rolling minute, globally.

HTTP body: 8192 bytes, JSON parse deadline: 3 seconds, text: 4096 UTF-8 bytes, final answer: 65536 UTF-8 bytes. At most 32 in-flight HTTP handlers, 8 local operator handlers (2-second read deadline), 16 principals, 64 retained request tickets, one unresolved request per principal. Admission refuses at capacity rather than evicting uncertain work. Boundaries are not a general-purpose DoS defense against a trusted local host administrator.

Terminal/reserved tickets expire after 30 minutes; unresolved/unknown work is not silently evicted. Native timeout default is 120 seconds, capped at 300; the synthetic preview deliberately uses 5 seconds. A half-second sweep expires grants/codes and marks late work unknown. Shutdown closes loopback and socket listeners and adapter tasks; tests read back listener closure. Native session transcripts are owned by Hermes, not duplicated in a new addon database.

## Request lifecycle

1. An authenticated client reserves an unpredictable, server-issued ticket tied to its principal and this server generation.
2. Submit associates the exact text digest once, BEFORE native dispatch. Same ticket/body returns status; changed body conflicts. Unknown/foreign/cancelled tickets cannot execute.
3. `handle_message` acceptance is not inference completion. Only a correlated, native final send with `notify=True` is retained; processing completion confirms terminal presentation.
4. Lost HTTP receipt: retain request ID, use status/recover, never POST a new request. Lost ticket receipt: `/api/current` recovers the reserved ticket; Cancel frees it without executing text.
5. Timeout: unknown, not failed. Keep admission locked. A late native terminal result may still be recovered. Do not assume no effects occurred.
6. Stop: issue native `/stop` once for the exact principal/session. Wait for processing completion. Cancellation does not roll back previous tool effects. No premature 'cancelled' response is returned while processing remains unresolved.
7. Re-pair/reload: same running adapter maps the principal back to the same conversation and latest request. No credential or transcript goes into persistent web storage.
8. Adapter restart: every grant expires, new conversations are generated, old ticket status is unknown and old submissions are rejected. NO automatic resume/re-execution and no API-server idempotency claim. Operator must reconcile the prior outcome through the native gateway/session history before manually starting equivalent new work. There is no durable addon job engine. A freshly typed new request is a new instruction, not a recovered old one.

## Output and approvals

Only intended final text enters the companion. Tool events, commentary, unsolicited/proactive sends, raw error fallbacks, images and attachments are not delivered. The egress gate requires exact request ID + chat match + final notification metadata. Common explicit reasoning tags and credential shapes are removed defensively; this is NOT universal DLP, and a model can place sensitive content in its final answer. Use an appropriately trusted principal/profile and normal upstream policies. No arbitrary field/response blob is serialized to the browser.

The adapter's native approval hook resolves pending approvals as deny; the synthetic test exercises the actual pending queue without executing any tool. No approval-grant endpoint exists. Clarify/interactive tool support is not claimed. Existing trusted tool permissions remain the profile's responsibility; denial of prompted approvals does not sandbox already-permitted tools.

## Ordered MIRA channel

All indispensable messages use `sendToApp`, never latest/snapshot replacement channels. UTF-8 JSON limits: 3500 bytes outward, 4096 inward; optional latest budget validators are 380/379 bytes but that channel is not used. Promise resolution means transport acceptance ONLY. An exact stream/sequence application ACK advances the next frame. Retry uses the same sequence; the receiver accepts the next sequence and re-ACKs its last handled duplicate. At most 32 queued frames plus one pending frame. Overflow becomes a visible disconnected state, not silent answer-chunk loss.

The browser implements a simulated receiver. The MIRA JS binding is tested with a synthetic bridge double; the official Rust shared helper and physical ACK behavior are still required. Capture lifecycle is simulated: overlay/exit/pagehide ends listening, but this is not a tested native microphone stop.

## Privacy and release

The standalone source archive excludes private contracts, personal identities, installation addresses, old POC records, dependency trees, caches and isolated homes. Evidence contains only synthetic prompts/status and public-source citations. Packaging scans source/evidence and ZIP members for private markers, credential patterns and long known environment-secret values without printing those values. No scanner can guarantee absence of all secrets. Review again before any public release or adding real-user evidence.
