#!/usr/bin/env python3
"""Exercise the installed compiler, including a real negative type-check control."""
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
    examples = root / 'scripts/ci/examples'
    shutil.copyfile(examples / 'probe.schema.json', tmp / 'probe.schema.json')
    original = (examples / 'v6.lms').read_text(encoding='utf8')
    source = tmp / 'probe.lms'
    binary = tmp / 'probe.dslb'
    def compile_source(text):
        source.write_text(text, encoding='utf8')
        return subprocess.run([compiler, '--no-preflight', str(source), str(binary)], capture_output=True, timeout=60)
    anchor = 'value = value + 1;'
    if original.count(anchor) != 1:
        raise SystemExit('Example changed: update the negative type-check control')
    bad = compile_source(original.replace(anchor, 'value = "wrong type";'))
    if bad.returncode != 2:
        raise SystemExit('Compiler negative control must fail with exit 2: ' + repr(bad))
    good = compile_source(original)
    if good.returncode:
        raise SystemExit('Published compiler cannot compile current v6 probe: ' + repr(good))
    data = binary.read_bytes()
    if data[:6] != b'DSLB\x00\x06':
        raise SystemExit('Compiler did not produce DSLB v6: ' + repr(data[:8]))
    print('PASS published compiler: positive v6 bytecode and negative type-check control')

version = subprocess.run([compiler, '--version'], capture_output=True, timeout=30)
catalog = subprocess.run([compiler, '--lmcode-signatures', str(root/'scripts/ci/examples/probe.schema.json')], capture_output=True, timeout=30)
if version.returncode or catalog.returncode:
    raise SystemExit('Compiler version/catalog inspection failed')
lines = catalog.stdout.splitlines()
if version.stdout.strip() == b'lmscript 0.2.444':
    if len(lines) != 181 or any(b'template_render' in line or b'lmcode_return_' in line for line in lines):
        raise SystemExit('Published 0.2.444 empty-host catalog differs from the documented 181-signature baseline')
print('PASS inspected compiler catalog:', len(lines), 'implicit signatures')
