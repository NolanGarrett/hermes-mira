# Capability matrix

| Capability | Status | Evidence / limitation |
|---|---|---|
| Native plugin discovery, registration and adapter lifecycle | VERIFIED LOCALLY | Installed PluginManager/PlatformRegistry/BasePlatformAdapter; native suite |
| Normal gateway ingress, allowlist, separate sessions and final egress | VERIFIED LOCALLY | Actual GatewayRunner; only inference method replaced by clearly synthetic fixture |
| Same-session followup | VERIFIED LOCALLY | Synthetic nonce recovered from native session transcript; not model memory proof |
| Isolated home installation / cleanup | VERIFIED LOCALLY | Preview installs into a fresh fake-identity home; listener closure and removal checked |
| In-process-only constraint | VERIFIED LOCALLY | Native host-isolation test refuses register_platform, no downgrade |
| Foreground expiring/revocable pairing | VERIFIED LOCALLY | Local operator socket, one-use code, memory-only grant, native allowlist recheck |
| Cross-user/session/profile and gateway-command rejection | VERIFIED LOCALLY | Foreign tickets hidden, routing fields rejected, slash controls disabled, multiplex refused |
| Correlation, duplicates, conflicts, lost receipt, timeout and restart | VERIFIED LOCALLY | Same ticket/body single dispatch; old/expired ID refuses replay; unknown outcomes hold admission |
| Approval fail-closed | VERIFIED LOCALLY | Real native pending approval wait resolves deny with synthetic non-executed command |
| Shared 640x480 companion/harness and browser states | VERIFIED LOCALLY | Chromium exercises actual addon; all required states, desktop/mobile screenshots |
| Unicode fallback, byte budgets and ordered application ACKs | VERIFIED LOCALLY | Shared JS tests and synthetic receiver; no vendor/hardware transport proof |
| Documented miraCompanion.sendToApp/onFromApp seam | DOCUMENTED ONLY | Binding uses actual documented method names; synthetic double tested |
| WASM ABI and BLE transcription methods | DOCUMENTED ONLY | Official API exports app_init/app_render/app_event/app_stop/memory; methods 0x0001/2/3 |
| Official SDK, unchanged example, packager, validator | BLOCKED | Public docs rechecked; full exported guide/assets absent |
| Compiled / installable MIRA package | BLOCKED | No official assets, compile, validator result or package; browser HTML is not importable |
| Native-plugin real-model turn, followup, read-only tool | BLOCKED | Not executed: the supplied isolated launcher deliberately uses synthetic inference. An authorized isolated live qualification is still needed; missing credentials in that test process do not establish that no authorized provider is available. No other transport's live evidence is substituted. |
| Native mic/STT, real ring and glasses UI | HARDWARE REQUIRED | Typed input and simulated events only |
| Actual iPhone private network path | HARDWARE REQUIRED | Loopback is not reachable from a phone as this host; remote HTTPS/origin integration not implemented |
| Secure persistent companion authentication | BLOCKED | Ordinary MIRA storage is not appropriate for credentials; only experimental foreground runtime pairing implemented |
| Locked/idle/background fresh requests and recovery | HARDWARE REQUIRED | Companion JS can pause; native assistant marketing is not custom-app proof |
| Real font readability, prescription lenses, battery, Bluetooth | HARDWARE REQUIRED | No physical setup tested |
| Custom speech output | BLOCKED | Not implemented or established by this work |
| Multiplex, remote hosting, cron/proactive delivery, media | BLOCKED | Intentionally outside preview support; fail closed rather than silently route |
| Original-code license | VERIFIED LOCALLY | Owner-authorized MIT license included; third-party dependencies retain their own terms. No vendor SDK assets bundled. |
| Public source scope | DOCUMENTED ONLY | Public developer-preview source is not a production release or hardware-compatibility certification; see README for remaining gates. |

The host developer preview is usable independently. This matrix does not claim full glasses-to-model support or recommend a purchase for unattended phone operation.
