#!/usr/bin/env python3
"""Compile the current language reference's code, not merely copied fixtures.

This is a compile-only contract: the schema declares the example host domain;
no host implementation or runtime-output behavior is claimed here. Native host
execution is exercised separately by the cross-runtime sample matrix.
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
        binary = tmp/(str(index)+'.dslb')
        if 'program = _lmcode_' in body:
            full = body.replace('"host.schema.json"',json.dumps(str(schema))) + '\nsavedsl(program,ARGV[0]);\n'
        else:
            full = 'program = _lmcode_ schema='+json.dumps(str(schema))+';\n'+body+'\nend _lmcode_\nsavedsl(program,ARGV[0]);\n'
        source.write_text(full,encoding='utf8')
        result = subprocess.run([compiler,'--no-preflight',str(source),str(binary)],capture_output=True,timeout=60)
        return result,binary
    bad,_ = compile_text('let broken = missing_reference_test;', 'negative')
    if bad.returncode != 2: raise SystemExit('Reference compiler rejection control did not fail with exit 2')
    for index,body in enumerate(programs,1):
        result,binary = compile_text(body,index)
        if result.returncode != 0:
            raise SystemExit('Reference example '+str(index)+' failed: '+result.stderr.decode('utf8',errors='replace'))
        if binary.read_bytes()[:6] != b'DSLB\x00\x06': raise SystemExit('Reference example did not produce v6 bytecode')
        print('PASS current language reference example',index)
    print('PASS 7 compiled reference examples; keyword inventory is non-executable data')
