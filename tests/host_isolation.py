"""Verify real host-isolation refusal; never relax an existing profile's policy."""
import argparse
import json
import logging
from pathlib import Path
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
(ROOT/'evidence').mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT))
from preview import prepare
parser=argparse.ArgumentParser()
parser.add_argument('--hermes-source',required=True)
args=parser.parse_args()
with tempfile.TemporaryDirectory(prefix='mira-isolation-test-',dir=ROOT.parent) as directory:
    home=Path(directory)
    config=prepare(home,Path(args.hermes_source).resolve())
    config['plugins']['isolation']='host'
    (home/'config.yaml').write_text(json.dumps(config))
    logging.basicConfig(level=logging.CRITICAL)
    from hermes_cli.plugins import get_plugin_manager
    from gateway.platform_registry import platform_registry
    manager=get_plugin_manager()
    try:
        manager.discover_and_load()
        entry=platform_registry.get('mira')
        plugins=[p for p in manager.list_plugins() if p.get('name')=='hermes-mira']
        assert entry is None, 'Host isolation must not silently load an in-process platform'
        assert plugins and 'register_platform' in str(plugins), plugins
        receipt={'passed':True,'configured_isolation':'host','platform_registered':False,
                 'reason':'Actual native plugin host refused register_platform; no downgrade performed.'}
        (ROOT/'evidence'/'host-isolation.json').write_text(json.dumps(receipt,indent=2))
        print(json.dumps(receipt))
    finally:
        manager.unload()
