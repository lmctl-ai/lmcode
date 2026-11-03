#!/usr/bin/env python3
"""Run the tutorial's lmcode programs through run_lmcode and compare exact output."""
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
    # Current --check never starts a host for schema discovery. Warm only this
    # owned cache via explicit real discovery, exactly as the tutorial requires.
    env['LMSCRIPT_TOOL_CACHE'] = str(work/'schema-cache')
    discovery = work/'discover.lms'
    discovery.write_text('host = load_schema(cli="lmcode-cpp-sample");\n', encoding='utf8')
    discovered = subprocess.run([compiler, str(discovery)], cwd=work, env=env, capture_output=True)
    if (discovered.returncode, discovered.stdout, discovered.stderr) != (0, b'', b''):
        raise SystemExit('Tutorial explicit schema discovery failed: '+repr(discovered))

    for offset in range(0,30,2):
        case=offset//2+1
        if args.case is not None and args.case!=case: continue
        body,expected=blocks[offset].strip(),blocks[offset+1].strip()
        source=work/(str(case)+'.lms')
        source.write_text(body+'\n',encoding='utf8')
        if expected.startswith('error:'):
            check=subprocess.run([compiler,'--check',str(source)],env=env,capture_output=True)
            if check.returncode!=2 or not same_diagnostic(check.stderr.decode('utf8'),expected) or check.stdout:
                raise SystemExit('Tutorial case '+str(case)+' compile diagnostic mismatch: '+repr(check))
        else:
            check=subprocess.run([compiler,'--check',str(source)],env=env,capture_output=True)
            if check.returncode or check.stdout or check.stderr:
                raise SystemExit('Tutorial check failed: '+repr(check))
            run=subprocess.run([compiler,str(source)],env=env,capture_output=True)
            if (run.returncode,run.stdout,run.stderr)!=(0,(expected+'\n').encode('utf8'),b''):
                raise SystemExit('Tutorial case '+str(case)+' output mismatch: '+repr(run))
        print('PASS tutorial case',case)
    if args.case is None:
        (work/'mismatch.schema.json').write_text(json.dumps({
            'dsl.schema':2,'name':'tutorial_schema_mismatch','types':{},'functions':{},'context':{}
        }),encoding='utf8')
        mismatch=work/'schema-mismatch.lms'
        mismatch.write_text('''program = _lmcode_ schema="mismatch.schema.json";
let value = 1;
end _lmcode_
result = run_lmcode(program, {command: ["lmcode-cpp-sample", "--lmcode", "$DSLFILE"]});
print(json_stringify(result));
''',encoding='utf8')
        result=subprocess.run([compiler,str(mismatch)],env=env,capture_output=True)
        expected=(blocks[30].strip()+'\n').encode('utf8')
        if (result.returncode,result.stdout,result.stderr)!=(0,expected,b''):
            raise SystemExit('Tutorial schema-mismatch example differs: '+repr(result))
        print('PASS 15 tutorial programs and the schema-hash mismatch example')
    elif not 1<=args.case<=15: ap.error('--case must be 1..15')
