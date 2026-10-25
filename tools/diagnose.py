"""Passive compatibility probes in a fresh isolated home; no live runtime changes."""
import argparse
import inspect
import json
import logging
from pathlib import Path
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
(ROOT/'evidence').mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT))
from preview import prepare, make_runner
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--hermes-source',required=True)
args=parser.parse_args()
with tempfile.TemporaryDirectory(prefix='mira-diagnostic-',dir=ROOT.parent) as directory:
    config=prepare(Path(directory),Path(args.hermes_source).resolve())
    logging.basicConfig(level=logging.CRITICAL)
    from gateway.platforms.base import BasePlatformAdapter
    from gateway.platforms.event import MessageEvent
    from hermes_cli.plugins import PluginContext
    from hermes_cli.plugin_isolation import HOST_UNSUPPORTED_CTX_METHODS
    import aiohttp
    features={
        'register_platform':hasattr(PluginContext,'register_platform'),
        'server_source_builder':hasattr(BasePlatformAdapter,'build_source'),
        'authorization_callback':hasattr(BasePlatformAdapter,'set_authorization_check'),
        'native_dispatch':hasattr(BasePlatformAdapter,'handle_message'),
        'completion_hook':hasattr(BasePlatformAdapter,'on_processing_complete'),
        'disable_gateway_control':'allow_gateway_control' in inspect.signature(MessageEvent).parameters,
        'in_process_required':'register_platform' in HOST_UNSUPPORTED_CTX_METHODS,
    }
    runner,adapter,manager,version=make_runner(config)
    receipt={'compatible':all(features.values()),'features':features,'tested_version':version.display_version,
             'tested_commit':version.commit,'python':sys.version.split()[0],'aiohttp':aiohttp.__version__,
             'minimum_enforced_version':'0.22.0','earliest_historical_support':'not established',
             'live_inference':False,'listener_started':False}
    manager.unload()
    (ROOT/'evidence'/'compatibility.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt,indent=2))
    if not receipt['compatible']:sys.exit(1)
