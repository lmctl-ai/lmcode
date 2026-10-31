#!/usr/bin/env python3
"""Exercise the published compiler's explicit lmcode execution model."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
compiler = os.environ['LMSCRIPT_BIN']
if os.name == 'nt' and not compiler.lower().endswith(('.exe', '.cmd', '.bat')):
    compiler += '.cmd'
with tempfile.TemporaryDirectory(prefix='compiler probe ', dir=root) as directory:
    tmp = Path(directory)
    shutil.copyfile(root / 'scripts/ci/examples/probe.schema.json', tmp / 'probe.schema.json')
    original = (root / 'scripts/ci/examples/v6.lms').read_text(encoding='utf8')
    source = tmp / 'probe.lms'
    source.write_text(original, encoding='utf8')
    result = subprocess.run([compiler, '--check', str(source)], capture_output=True)
    if result.returncode:
        raise SystemExit('Published compiler cannot type-check the lmcode execution probe: ' + repr(result))
    anchor = 'value = value + 1;'
    if original.count(anchor) != 1:
        raise SystemExit('Example changed: update the negative type-check control')
    source.write_text(original.replace(anchor, 'value = "wrong type";'), encoding='utf8')
    bad = subprocess.run([compiler, '--check', str(source)], capture_output=True)
    if bad.returncode != 2:
        raise SystemExit('Compiler negative control must fail with exit 2: ' + repr(bad))
    print('PASS published compiler: explicit run_lmcode API and negative type-check control')

version = subprocess.run([compiler, '--version'], capture_output=True)
catalog = subprocess.run([compiler, '--lmcode-signatures', str(root/'scripts/ci/examples/probe.schema.json')], capture_output=True)
if version.returncode or catalog.returncode:
    raise SystemExit('Compiler version/catalog inspection failed')
print('PASS inspected compiler catalog:', len(catalog.stdout.splitlines()), 'implicit signatures')
