"""Run bounded synthetic acceptance with explicit installed dependencies and sanitized env."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--hermes-source',required=True)
parser.add_argument('--hermes-python',required=True)
parser.add_argument('--chrome',required=True)
args=parser.parse_args()
env={k:v for k,v in os.environ.items() if k in ('PATH','HOME','TMPDIR','LANG','SSL_CERT_FILE','SSL_CERT_DIR')}
env.update(HERMES_SOURCE=str(Path(args.hermes_source).resolve()),
           HERMES_PYTHON=str(Path(args.hermes_python).absolute()),CHROME_BIN=str(Path(args.chrome).absolute()))
(ROOT/'evidence').mkdir(exist_ok=True)
commands=[
 ('compatibility',[env['HERMES_PYTHON'],'tools/diagnose.py','--hermes-source',env['HERMES_SOURCE']]),
 ('javascript',['node','--test','tests/companion.test.js']),
 ('native',[env['HERMES_PYTHON'],'tests/native.py','--hermes-source',env['HERMES_SOURCE']]),
 ('host-isolation',[env['HERMES_PYTHON'],'tests/host_isolation.py','--hermes-source',env['HERMES_SOURCE']]),
 ('browser',['node','tests/browser.mjs']),
]
results=[]
for name,command in commands:
    result=subprocess.run(command,cwd=ROOT,env=env,text=True,capture_output=True,timeout=180)
    output=result.stdout+result.stderr
    # Strip machine-specific paths from distributable test logs; never record environment.
    for value,replacement in ((str(ROOT),'<source>'),(env['HERMES_SOURCE'],'<hermes>')):
        output=output.replace(value,replacement)
    (ROOT/'evidence'/f'{name}.log').write_text(output)
    record={'check':name,'exit_code':result.returncode,'passed':result.returncode==0}
    if name=='javascript':
        count=re.search(r'(?:ℹ |# )tests (\d+)',output)
        if count:record['tests_run']=int(count.group(1))
    results.append(record)
    print(json.dumps(record),flush=True)
    if result.returncode:
        print(output)
        break
receipt={'passed':len(results)==len(commands) and all(r['passed'] for r in results),
         'results':results,'inference':'synthetic','native_gateway':True,
         'live_model_tested':False,'hardware_tested':False}
(ROOT/'evidence'/'acceptance.json').write_text(json.dumps(receipt,indent=2))
sys.exit(0 if receipt['passed'] else 1)
