"""Isolated, synthetic native-gateway preview. Never imports active credentials.
Run using the Python interpreter belonging to the Hermes installation under test.
"""
import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import shutil
import signal
import sys
import tempfile

ROOT = Path(__file__).resolve().parent


def prepare(home, hermes_source, port=0):
    # Must run BEFORE importing Hermes. Explicit allowlist, no inherited provider keys,
    # BWS config, launch profile, custom endpoints, active plugins, or user HOME.
    path = os.environ.get("PATH", "/usr/bin:/bin")
    os.environ.clear()
    os.environ.update(PATH=path, HOME=str(home), HERMES_HOME=str(home),
                      TMPDIR=str(home), PYTHONIOENCODING="utf-8",
                      HERMES_ENABLE_PROJECT_PLUGINS="false")
    sys.path.insert(0, str(hermes_source))
    os.chdir(home)
    target = home / "plugins" / "hermes-mira"
    shutil.copytree(ROOT, target, ignore=shutil.ignore_patterns("node_modules", "evidence", "artifacts", "__pycache__", ".preview-*"))
    config = {
        "plugins": {"enabled": ["hermes-mira"], "isolation": "in_process"},
        "platforms": {"mira": {"enabled": True, "port": port, "timeout_seconds": 5,
            "allowed_users": ["synthetic-alice", "synthetic-bob"],
            "reply_to_mode": "all", "gateway_restart_notification": False}},
        "gateway": {"multiplex_profiles": False},
        "display": {"tool_progress": "off", "show_reasoning": False,
                    "platforms": {"mira": {"streaming": False}}},
        "streaming": {"enabled": False},
        "model": {"provider": "none", "default": "synthetic-no-model"},
        "memory": {"memory_enabled": False, "user_profile_enabled": False},
    }
    # JSON is valid YAML. Contains only synthetic/non-secret settings.
    (home / "config.yaml").write_text(json.dumps(config, indent=2))
    (home / "SOUL.md").write_text("Synthetic isolated integration identity. No production credentials or tools.\n")
    return config


def make_runner(config):
    from gateway.config import GatewayConfig, Platform
    from gateway.run import GatewayRunner
    from hermes_cli.plugins import get_plugin_manager
    from hermes_cli.version_info import get_version_info

    manager = get_plugin_manager()
    manager.discover_and_load()
    from gateway.platform_registry import platform_registry
    entry = platform_registry.get("mira")
    if not entry:
        raise RuntimeError("Native plugin discovery failed")

    class SyntheticRunner(GatewayRunner):
        """Only inference replaced. Actual native ingress/auth/session/egress retained."""
        async def _handle_message_with_agent(self, event, source, key, generation):
            entry = await self.async_session_store.get_or_create_session(source)
            history = self.session_store.load_transcript(entry.session_id)
            self.synthetic_calls.append({"id": event.message_id, "user": source.user_id,
                "session": entry.session_id, "key": key, "control": event.allow_gateway_control})
            text = event.text
            if text == "fixture:backend":
                raise RuntimeError("Synthetic backend failure")
            if text in {"fixture:delay", "fixture:timeout"}:
                await asyncio.sleep(3 if text.endswith("delay") else 8)
            if text == "fixture:approval":
                from tools.approval_gateway_wait import _await_gateway_decision
                adapter = self.adapters[Platform("mira")]
                loop = asyncio.get_running_loop()
                def notify(data):
                    future = asyncio.run_coroutine_threadsafe(
                        adapter.send_exec_approval(source.chat_id, data["command"], key), loop)
                    future.result(timeout=5)
                decision = await asyncio.to_thread(_await_gateway_decision, key, notify,
                    {"command": "SYNTHETIC-NO-EXECUTION", "pattern_key": "synthetic-preview"})
                if decision.get("choice") != "deny":
                    raise RuntimeError("Synthetic approval did not fail closed")
                answer = "SYNTHETIC approval denied. No tool was executed."
            elif text == "fixture:long":
                answer = "SYNTHETIC long answer. " + " ".join(f"Page item {i}: ordered UTF-8 café 漢字 🗺 safe fallback." for i in range(130))
            elif text == "fixture:followup":
                previous = [m["content"] for m in history if m.get("role") == "user"]
                answer = "SYNTHETIC remembered: " + (previous[-1] if previous else "no previous request")
            else:
                answer = "SYNTHETIC native gateway response: " + text
            self.session_store.append_to_transcript(entry.session_id, {"role": "user", "content": text})
            self.session_store.append_to_transcript(entry.session_id, {"role": "assistant", "content": answer})
            return answer

    gateway_config = GatewayConfig.from_dict(config)
    runner = SyntheticRunner(gateway_config)
    runner.synthetic_calls = []
    platform = Platform("mira")
    adapter = runner._create_adapter(platform, gateway_config.platforms[platform])
    if not adapter:
        raise RuntimeError("Native adapter factory failed")
    runner.adapters[platform] = adapter
    runner._wire_adapter_handlers(adapter)
    return runner, adapter, manager, get_version_info()


async def serve(args):
    with tempfile.TemporaryDirectory(prefix="mira-preview-", dir=ROOT.parent) as directory:
        home = Path(directory)
        config = prepare(home, Path(args.hermes_source).resolve(), args.port)
        logging.basicConfig(level=logging.CRITICAL)
        runner, adapter, manager, version = make_runner(config)
        try:
            await adapter.connect()
            # Only origin/socket/version, no generated grant/code in machine-readable output.
            print(json.dumps({"origin": adapter.origin, "operator_socket": str(adapter.socket_path),
                "synthetic": True, "native_plugin": True, "hermes_version": version.display_version}), flush=True)
            stop = asyncio.Event()
            for sig in (signal.SIGTERM, signal.SIGINT):
                asyncio.get_running_loop().add_signal_handler(sig, stop.set)
            await stop.wait()
        finally:
            await adapter.disconnect()
            manager.unload()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hermes-source", required=True, help="Installed Hermes source directory (read-only)")
    parser.add_argument("--port", type=int, default=8775)
    asyncio.run(serve(parser.parse_args()))
