#!/usr/bin/env python3
"""Type-check the current language reference against the published compiler.

Opaque lmcode programs execute through run_lmcode; block-end bytecode export
is not part of this contract. Native host execution is exercised by the
cross-runtime matrix.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
text = (ROOT/'spec/language.md').read_text(encoding='utf8')
blocks = re.findall(r'^```text\n(.*?)^```', text, re.M|re.S)
# The keyword inventory is data. All other current fenced blocks must compile.
keywords = 'let if else true false for in range fn return switch case default while break continue implements'
programs = [b for b in blocks if b.strip() != keywords]
if len(blocks) != 8 or len(programs) != 7:
    raise SystemExit('Reference examples changed: classify new blocks explicitly before claiming verification')
compiler = os.environ['LMSCRIPT_BIN']
if os.name == 'nt' and not compiler.lower().endswith(('.cmd','.bat','.exe')): compiler += '.cmd'
with tempfile.TemporaryDirectory(prefix='reference examples ', dir=ROOT) as directory:
    tmp = Path(directory)
    schema = tmp/'reference.schema.json'
    shutil.copyfile(ROOT/'scripts/ci/examples/reference.schema.json',schema)
    def compile_text(body, index):
        source = tmp/(str(index)+'.lms')
        if 'program = _lmcode_' in body:
            full = body.replace('"host.schema.json"',json.dumps(str(schema))) + '\nresult = run_lmcode(program);\n'
        else:
            full = 'program = _lmcode_ schema='+json.dumps(str(schema))+';\n'+body+'\nend _lmcode_\nresult = run_lmcode(program);\n'
        source.write_text(full,encoding='utf8')
        result = subprocess.run([compiler,'--check',str(source)],capture_output=True)
        return result
    bad = compile_text('let broken = missing_reference_test;', 'negative')
    if bad.returncode != 2: raise SystemExit('Reference compiler rejection control did not fail with exit 2')
    for index,body in enumerate(programs,1):
        result = compile_text(body,index)
        if result.returncode != 0:
            raise SystemExit('Reference example '+str(index)+' failed: '+result.stderr.decode('utf8',errors='replace'))
        print('PASS current language reference example',index)
    print('PASS 7 type-checked reference examples; keyword inventory is non-executable data')
