#!/usr/bin/env python3
"""Run the tutorial's actual source blocks and compare its verbatim output blocks."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]
ap=argparse.ArgumentParser()
ap.add_argument('--sample-root',type=Path,default=os.environ.get('LMCODE_SAMPLE'))
ap.add_argument('--document',type=Path,default=ROOT/'guides/writing-lmcode.md')
ap.add_argument('--case',type=int,help='one numbered case for a diagnostic/control; CI runs all')
args=ap.parse_args()
if args.sample_root is None: ap.error('provide --sample-root or LMCODE_SAMPLE')
sample=args.sample_root.resolve()
host=sample/'build/lmcode-cpp-sample'
if os.name=='nt': host=host.with_suffix('.exe')
if not host.is_file(): ap.error('build the reference sample host first: '+str(host))
compiler=os.environ['LMSCRIPT_BIN']
if os.name=='nt' and not compiler.lower().endswith(('.cmd','.bat','.exe')): compiler+='.cmd'
env=dict(os.environ,PATH=str(host.parent)+os.pathsep+os.environ['PATH'])
blocks=re.findall(r'^```text\n(.*?)^```',args.document.read_text(encoding='utf8'),re.M|re.S)
if len(blocks)!=31 or any('_lmcode_' not in blocks[i] for i in range(0,30,2)):
    raise SystemExit('Tutorial block layout changed: classify new examples before claiming verification')
def diagnostic(text):
    return re.sub(r'^error:.*?\.lms:', 'error:SOURCE:',text.strip(),flags=re.M)
def same_diagnostic(actual, expected):
    actual,expected=diagnostic(actual),diagnostic(expected)
    if 'schema provides: …' in expected:
        pattern=r'(schema provides: )(.*?)(; built-ins:)'
        found=re.search(pattern,actual)
        if not found or 'template_render' not in found.group(2): return False
        actual=re.sub(pattern,r'\1<scope>\3',actual)
        expected=re.sub(pattern,r'\1<scope>\3',expected)
    return actual==expected
with tempfile.TemporaryDirectory(prefix='tutorial ',dir=ROOT) as directory:
    work=Path(directory)
    shutil.copyfile(sample/'sample-suite/sample.dsl.json',work/'sample.dsl.json')
    first_binary=None
    for offset in range(0,30,2):
        case=offset//2+1
        if args.case is not None and args.case!=case: continue
        body,expected=blocks[offset].strip(),blocks[offset+1].strip()
        source=work/(str(case)+'.lms');binary=work/(str(case)+'.dslb')
        source.write_text(body+'\n',encoding='utf8')
        check=subprocess.run([compiler,'--check',str(source)],env=env,capture_output=True,timeout=60)
        if expected.startswith('error:'):
            if check.returncode!=2 or not same_diagnostic(check.stderr.decode('utf8'),expected) or check.stdout:
                raise SystemExit('Tutorial case '+str(case)+' compile diagnostic mismatch: '+repr(check))
        else:
            if check.returncode or check.stdout or check.stderr: raise SystemExit('Tutorial check failed: '+repr(check))
            built=subprocess.run([compiler,'--no-preflight',str(source),str(binary)],env=env,capture_output=True,timeout=60)
            if built.returncode: raise SystemExit('Tutorial compilation failed: '+repr(built))
            if first_binary is None: first_binary=binary
            record=json.loads(expected.splitlines()[-1])
            code=0 if record.get('ok') else (4 if record.get('phase')=='app' else 3)
            run=subprocess.run([str(host),'--dsl',str(binary)],env=env,capture_output=True,timeout=30)
            if (run.returncode,run.stdout,run.stderr)!=(code,(expected+'\n').encode('utf8'),b''):
                raise SystemExit('Tutorial case '+str(case)+' output mismatch: '+repr(run))
        print('PASS tutorial case',case)
    if args.case is None:
        data=bytearray(first_binary.read_bytes());data[6]^=1
        corrupt=work/'schema-mismatch.dslb';corrupt.write_bytes(data)
        result=subprocess.run([str(host),'--dsl',str(corrupt)],env=env,capture_output=True,timeout=30)
        if (result.returncode,result.stdout,result.stderr)!=(3,(blocks[30].strip()+'\n').encode('utf8'),b''):
            raise SystemExit('Tutorial schema-mismatch example differs: '+repr(result))
        print('PASS 15 tutorial programs and the schema-hash mismatch example')
    elif not 1<=args.case<=15: ap.error('--case must be 1..15')
