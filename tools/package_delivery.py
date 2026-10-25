"""Build clean source/evidence ZIPs; inspect members and exercise the extracted distribution."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--hermes-source',required=True)
parser.add_argument('--hermes-python',required=True)
parser.add_argument('--chrome',required=True)
parser.add_argument('--private-marker',action='append',default=[],help='Non-secret private string to exclude; never put a credential in arguments')
args=parser.parse_args()
artifacts=ROOT/'artifacts';artifacts.mkdir(exist_ok=True)
evidence=ROOT/'evidence';evidence.mkdir(exist_ok=True)
assert json.loads((evidence/'acceptance.json').read_text())['passed'], 'Run acceptance first'
known=[v.encode() for k,v in os.environ.items() if re.search(r'(TOKEN|SECRET|PASSWORD|API_KEY)',k,re.I) and len(v)>=16]
patterns=[rb'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----',rb'gh[pousr]_[A-Za-z0-9]{25,}',rb'sk-[A-Za-z0-9]{24,}']
markers=[x.lower().encode() for x in args.private_marker]

def scan(name,data):
    assert not any(secret in data for secret in known), 'Known environment secret found; value suppressed'
    assert not any(marker in data.lower() for marker in markers), 'Private marker found; value suppressed'
    assert not any(re.search(pattern,data) for pattern in patterns), 'Credential pattern found; value suppressed'

root_files={'README.md','LICENSE','LICENSE-NOTICE.md','.gitignore','plugin.yaml','__init__.py','adapter.py','preview.py','package.json','package-lock.json'}
source=[]
for path in ROOT.rglob('*'):
    if not path.is_file():continue
    rel=path.relative_to(ROOT)
    if '__pycache__' in rel.parts or path.suffix=='.pyc':continue
    if len(rel.parts)==1 and rel.name in root_files or rel.parts[0] in {'web','docs','tests','tools'}:
        assert not path.is_symlink(), 'Symlink not distributable'
        scan(str(rel),path.read_bytes());source.append(path)
source.sort()
source_zip=artifacts/'hermes-mira-source.zip'
with zipfile.ZipFile(source_zip,'w',zipfile.ZIP_DEFLATED) as archive:
    for path in source:archive.write(path,'hermes-mira/'+path.relative_to(ROOT).as_posix())
with zipfile.ZipFile(source_zip) as archive:
    assert archive.testzip() is None
    for name in archive.namelist():scan(name,archive.read(name))

# A real extraction, clean npm dependency install and COMPLETE synthetic acceptance.
with tempfile.TemporaryDirectory(prefix='mira-dist-smoke-',dir=ROOT.parent) as directory:
    tmp=Path(directory)
    with zipfile.ZipFile(source_zip) as archive:archive.extractall(tmp)
    extracted=tmp/'hermes-mira'
    (tmp/'home').mkdir()
    env={k:v for k,v in os.environ.items() if k in ('PATH','LANG','SSL_CERT_FILE','SSL_CERT_DIR')}
    env.update(HOME=str(tmp/'home'),TMPDIR=str(tmp),npm_config_cache=str(tmp/'npm-cache'))
    commands=[['npm','ci','--ignore-scripts'],
              ['python',str(extracted/'tools'/'acceptance.py'),'--hermes-source',args.hermes_source,
               '--hermes-python',args.hermes_python,'--chrome',args.chrome]]
    smoke=[];logs=[]
    for command in commands:
        result=subprocess.run(command,cwd=extracted,env=env,text=True,capture_output=True,timeout=240)
        log=result.stdout+result.stderr
        for private,replacement in ((str(tmp),'<extracted>'),(args.hermes_source,'<hermes>')):
            log=log.replace(private,replacement)
        scan('extracted-smoke.log',log.encode());logs.append(log)
        smoke.append({'step':'npm-ci' if command[0]=='npm' else 'full-extracted-acceptance','exit_code':result.returncode})
        if result.returncode:
            (evidence/'extracted-smoke.log').write_text('\n'.join(logs))
            raise RuntimeError('Extracted distribution failed; see sanitized smoke log')
    extracted_result=json.loads((extracted/'evidence'/'acceptance.json').read_text())
    assert extracted_result['passed']
    assert json.loads((extracted/'evidence'/'browser-cleanup.json').read_text())['listener_closed']
(evidence/'extracted-smoke.log').write_text('\n'.join(logs))

receipt={'passed':True,'source_files':len(source),'source_zip_integrity':True,
         'extracted_smoke':smoke,'extracted_full_acceptance':extracted_result,
         'source_and_zip_privacy_scan':True,'known_secret_values_compared':len(known),
         'private_markers_compared':len(markers),'synthetic_fixture_tokens_allowed':True,
         'limits':'Known-value and shape/marker checks, not universal DLP; dependencies not vendored.',
         'sdk_package_produced':False,'public_release':False}
(evidence/'packaging.json').write_text(json.dumps(receipt,indent=2))
evidence_names={
 'acceptance.json','native-tests.json','browser-tests.json','browser-cleanup.json',
 'host-isolation.json','compatibility.json','official-sources.json','packaging.json',
 'compatibility.log','javascript.log','native.log','host-isolation.log','browser.log',
 'extracted-smoke.log','browser-desktop.png','browser-mobile.png'}
evidence_zip=artifacts/'hermes-mira-evidence.zip'
with zipfile.ZipFile(evidence_zip,'w',zipfile.ZIP_DEFLATED) as archive:
    for name in sorted(evidence_names):
        path=evidence/name
        assert path.exists(), 'Missing required evidence: '+name
        scan(name,path.read_bytes());archive.write(path,'hermes-mira-evidence/'+name)
with zipfile.ZipFile(evidence_zip) as archive:
    assert archive.testzip() is None
    for name in archive.namelist():scan(name,archive.read(name))
manifest={'artifacts':[{'file':path.name,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
                       for path in (source_zip,evidence_zip)],
          'source_files':len(source),'evidence_files':len(evidence_names),
          'extracted_tests_passed':True,'zip_integrity_passed':True,'privacy_scan_passed':True}
(artifacts/'manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest,indent=2))
