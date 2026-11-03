#!/usr/bin/env python3
"""Qualify the labeled JavaScript guide blocks through the real compiler/SDK."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--document', type=Path, default=ROOT/'guides/javascript-host.md')
args = parser.parse_args()
runtime = Path(os.environ['LMCODE_JS']).resolve()
compiler = os.environ['LMSCRIPT_BIN']
blocks = re.findall(r'^```(json|js|text)\n(.*?)^```', args.document.read_text(encoding='utf8'), re.M | re.S)
if [kind for kind, _ in blocks] != ['json', 'js', 'text', 'text']:
    raise SystemExit('JavaScript guide layout changed: classify every new example')
with tempfile.TemporaryDirectory(prefix='js guide ', dir=ROOT) as directory:
    work = Path(directory)
    (work/'counter.schema.json').write_text(blocks[0][1], encoding='utf8')
    host = blocks[1][1].replace('./lmcode-js/src/index.mjs', (runtime/'src/index.mjs').as_uri())
    (work/'counter-host.mjs').write_text(host, encoding='utf8')
    source = work/'counter.lms'
    source.write_text(blocks[2][1], encoding='utf8')
    env = dict(os.environ)
    # A test or parent invocation must not leak private correlation into a new one.
    env.pop('LMCODE_INVOCATION_FILE', None)
    check = subprocess.run([compiler, '--check', str(source)], cwd=work, env=env, capture_output=True)
    if (check.returncode, check.stdout, check.stderr) != (0, b'', b''):
        raise SystemExit('JavaScript guide compilation failed: '+repr(check))
    run = subprocess.run([compiler, str(source)], cwd=work, env=env, capture_output=True)
    expected = (blocks[3][1].strip()+'\n').encode('utf8')
    if (run.returncode, run.stdout, run.stderr) != (0, expected, b''):
        raise SystemExit('JavaScript guide output mismatch: '+repr(run))
print('PASS JavaScript schema, host, compiled program and exact stdout')
