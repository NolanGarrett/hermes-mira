# Hermes MIRA — isolated developer preview

An unofficial, out-of-tree native Hermes platform plugin plus a shared JavaScript companion and browser harness. This is runnable host software, not a compiled or installable MIRA glasses app. No endorsement by either upstream project is implied.

**Developer preview — not production-ready or hardware-validated.** The plugin is real; inference in the supplied demo is synthetic. No real-model turn through this native addon, official MIRA package validation, or glasses/iPhone test has been completed. Do not buy hardware on the strength of this browser demo.

Repository: [NolanGarrett/hermes-mira](https://github.com/NolanGarrett/hermes-mira). Original addon code is [MIT-licensed](LICENSE); vendor SDK assets are not included. The npm package remains `private: true` to prevent accidental npm publication, independently of GitHub visibility.

Read the [capability matrix](docs/CAPABILITIES.md), [test evidence and limitations](docs/ACCEPTANCE.md), [security model](docs/SECURITY.md), and [SDK/hardware checklist](docs/DEVICE-PREPARATION.md) before integration.

## What works

`plugin.yaml` → real native plugin discovery → `register(ctx)` / `ctx.register_platform` → `MiraAdapter(BasePlatformAdapter)` → normal `GatewayRunner` authorization, sessions and final delivery. There is no second model client, recursive API-server request, core fork or monkeypatch.

The preview launcher replaces only inference with an explicitly SYNTHETIC runner subclass. Native ingress, allowlisting, session storage, stop handling and delivery remain real. The companion uses the same implementation in the Chromium harness and proposed `miraCompanion` binding. Real live-model inference through this addon has NOT been tested.

## Requirements and compatibility

- A separately installed Hermes source tree and its Python environment, with `aiohttp`. Tested Hermes version and build commit are recorded in `evidence/compatibility.json` in the evidence distribution.
- Enforced compatibility floor: Hermes 0.22.0. This is a conservative supported baseline, NOT a claim that 0.22.0 was the first historical version with plugins. Only the recorded build was exercised. Run the diagnostic on your installation.
- Node 20+ for shared logic tests; `playwright-core` 1.64.1 and an existing Chromium executable for browser tests. Tested Python 3.14.7. No browser/SDK auto-install occurs.
- Unix-domain sockets are required for local operator admission. Windows-native hosting is not supported by this preview.
- One standalone profile per gateway. Multiplexed/cross-profile routing and non-loopback binds fail closed.
- Platform plugins currently require in-process execution. If an existing profile uses `plugins.isolation: host`, keep it: this plugin is incompatible. The negative test proves that native host isolation refuses registration. Never disable an operator's isolation policy just to load this addon.

## Exact isolated launch / install

Clone the source (or extract the source archive), then set paths to your existing installation:

    git clone https://github.com/NolanGarrett/hermes-mira.git
    cd hermes-mira

    export HERMES_SOURCE=/path/to/installed/hermes-agent
    export HERMES_PYTHON="$HERMES_SOURCE/.venv/bin/python"
    export CHROME_BIN=/path/to/existing/chromium
    npm ci --ignore-scripts
    "$HERMES_PYTHON" tools/diagnose.py --hermes-source "$HERMES_SOURCE"
    "$HERMES_PYTHON" preview.py --hermes-source "$HERMES_SOURCE" --port 8775

This is also the tested install-in-an-isolated-home path. The launcher creates a fresh `mira-preview-*` directory next to the source directory, clears inherited environment credentials before importing Hermes, sets HOME/HERMES_HOME there, copies the addon into `plugins/hermes-mira`, writes synthetic config/identity, discovers it through the installed plugin manager, constructs the native gateway and binds ONLY 127.0.0.1. No active profile is loaded, installed into, or changed. The source parent must be writable. A random port can be selected with `--port 0`.

The launcher prints one JSON line containing the actual origin and `operator_socket` path. In a second terminal, from this source directory:

    python tools/pairing.py /exact/printed/mira-operator.sock pair synthetic-alice

Open the printed loopback origin. Enter the displayed single-use code in the password field and click Pair foreground. Do not redirect pairing output to a file, paste a privileged API key, or store the code/token. Codes last 60 seconds; session grants last at most 900 seconds in runtime memory. Reloading needs another foreground pairing. A re-pair revokes the prior grant and recovers the same in-memory conversation/request while that server is alive.

`synthetic-alice` and `synthetic-bob` are fixture principals, not real accounts. A local code cannot bypass the native gateway allowlist. Operator revocation:

    python tools/pairing.py /exact/printed/mira-operator.sock revoke synthetic-alice

Ctrl-C shuts down the listener, clears grants and removes the temporary home. To uninstall this preview, stop it and remove the extracted source folder if desired. No production service, scheduler or gateway entry was created. After a hard kill, first verify no prior process is running before removing its leftover temporary home/socket. Preserve any unknown-outcome evidence before cleanup.

## Demonstration

1. Pair, type `SYNTHETIC-DEMO-42`, Hold start, then Hold end. Observe submitting → working → answer.
2. Select Continuity followup and Submit typed: the fixture retrieves the previous prompt from the SAME native session transcript.
3. Select Long Unicode answer. Use swipe backward for next, swipe forward for previous. Rendering uses bounded ASCII fallback on a 640×480 canvas, not assumed physical glyph support.
4. Select Delayed response, submit, turn Phone offline on/off, then Reconnect / recover. The existing request is recovered without submitting it again.
5. Try Backend failure, Unavailable approval, Long delay and Cancel / stop. The preview timeout is 5 seconds; the 8-second fixture demonstrates unknown outcome followed by late recovery. Stop is not a rollback.
6. Sidebar and Exit release simulated listening and suppress hidden submissions. Typed text is the only tested input source. There is no real microphone capture.

Fault-selector commands are interpreted ONLY by `preview.py`; the plugin itself contains no fixture agent. Do not treat them as special commands in a real gateway.

## Tests

    npm test
    "$HERMES_PYTHON" tests/native.py --hermes-source "$HERMES_SOURCE"
    "$HERMES_PYTHON" tests/host_isolation.py --hermes-source "$HERMES_SOURCE"
    HERMES_PYTHON="$HERMES_PYTHON" HERMES_SOURCE="$HERMES_SOURCE" CHROME_BIN="$CHROME_BIN" npm run test:browser

Or run all checks and save sanitized machine-readable evidence/logs:

    python tools/acceptance.py --hermes-source "$HERMES_SOURCE" --hermes-python "$HERMES_PYTHON" --chrome "$CHROME_BIN"

No live inference credentials are copied into the isolated homes. These tests are not real-model or hardware proof. The browser suite starts and stops its own temporary server and checks that its port closes.

## Native integration configuration (future live qualification)

The runtime addon is the root `plugin.yaml`, `__init__.py`, `adapter.py` and `web/`. A normal standalone gateway supplies message and authorization callbacks before `connect()`. Configure `platforms.mira.enabled`, `port`, `allowed_users` (explicit principal IDs), `reply_to_mode: all`, `gateway_restart_notification: false`, and per-platform `display.platforms.mira.streaming: false`. `plugins.enabled` must explicitly contain `hermes-mira`. The preview supplies and verifies this configuration in a fresh home; it does NOT modify your normal gateway.

The HTTP client cannot select a profile, chat, native session or user. Principals come only from local operator admission, conversation IDs are generated server-side, and all events re-enter native authorization. Existing profile tool permissions still apply; this addon is not a new tool sandbox. Approval prompts are denied. Normal tools that do not require approval are not globally disabled by the addon.

Do not deploy/expose this preview as a phone endpoint. Real phone connectivity needs a separately reviewed private HTTPS/origin and authenticated transport design; the loopback URL on a phone points to the phone, not this host. No tunnel, firewall or public ingress is configured here.

## Layout and remaining gates

- `adapter.py`: native transport, admission, request correlation and final-only projection.
- `web/companion.js`: shared state, HTTP client, UTF-8 limits, pagination and ordered application ACKs.
- `web/mira-binding.js`: documented public JS bridge seam; synthetic double tested, no real device claim.
- `preview.py`: isolated installation and synthetic inference fixture; not production startup.
- `tests/`, `tools/`: real framework, JS, browser, diagnostics, packaging and cleanup checks.
- `docs/CAPABILITIES.md`, `docs/SECURITY.md`, `docs/DEVICE-PREPARATION.md`, `docs/ACCEPTANCE.md`: exact assurance boundary and outstanding gates.

No official SDK assets, MIRA WASM, packager, validator or importable MIRA HTML are included. Actual SDK compilation, official validation, real mic/STT, ring/glasses/iPhone behavior, locked/idle execution, secure persistent sign-in and a native-plugin live-model/tool turn remain unverified. Earlier API demos do not establish this plugin's live behavior.

## License and release

Original addon code is released under the [MIT License](LICENSE). No SDK or third-party example is relicensed. See [LICENSE-NOTICE.md](LICENSE-NOTICE.md) for provenance and dependency boundaries. Public source availability does not establish production readiness, vendor endorsement, or MIRA compatibility on hardware.

### Remaining work

1. Qualify a real model turn, followup and harmless read-only tool call through this native plugin in an authorized isolated environment. The existing synthetic tests are not that proof.
2. Obtain the official MIRA SDK export and terms; compile the unchanged official example, then the integrated app, and run the official validator on both.
3. Design and test private phone-reachable HTTPS/origin handling and client authentication. The current loopback-only transport deliberately does not support this.
4. Validate actual ring/microphone/display behavior, foreground pairing, locked/idle requests and suspension recovery with hardware. Secure persistent sign-in remains unresolved.

Keep contributions scoped and run the tests above. Do not commit credentials, private transcripts, local Hermes configuration, vendor SDK files without redistribution permission, or unverified hardware claims. No production installation or network changes are part of the preview launcher.
