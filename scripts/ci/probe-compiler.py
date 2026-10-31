#!/usr/bin/env python3
"""Exercise the installed compiler, including a real negative type-check control."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
compiler = os.environ['LMSCRIPT_BIN']
# Python CreateProcess cannot execute npm's extensionless Bash shim on Windows.
if os.name == 'nt' and not compiler.lower().endswith(('.exe', '.cmd', '.bat')):
    compiler += '.cmd'
with tempfile.TemporaryDirectory(prefix='compiler probe ', dir=root) as tmp:
    tmp = Path(tmp)
    schema = tmp / 'schema.json'
    schema.write_text(json.dumps({'dsl.schema': 2, 'name': 'ci_probe', 'types': {}, 'functions': {}, 'context': {}}), encoding='utf8')
    source = tmp / 'probe.lms'
    binary = tmp / 'probe.dslb'
    def compile_body(body):
        source.write_text('p = _lmcode_ schema=' + json.dumps(str(schema)) + ';\n' + body + '\nend _lmcode_\nsavedsl(p, ARGV[0]);\n', encoding='utf8')
        return subprocess.run([compiler, '--no-preflight', str(source), str(binary)], capture_output=True, timeout=60)
    bad = compile_body('let value = 1; value = "wrong type";')
    if bad.returncode != 2:
        raise SystemExit('Compiler negative control must fail with exit 2: ' + repr(bad))
    good = compile_body('let value = 42;')
    if good.returncode:
        raise SystemExit('Published compiler cannot compile current v6 probe: ' + repr(good))
    data = binary.read_bytes()
    if data[:6] != b'DSLB\x00\x06':
        raise SystemExit('Compiler did not produce DSLB v6: ' + repr(data[:8]))
    print('PASS published compiler: positive v6 bytecode and negative type-check control')
