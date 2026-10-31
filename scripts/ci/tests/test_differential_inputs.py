import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[3]

class DifferentialInputs(unittest.TestCase):
    def fixture(self, base):
        vectors=base/'conformance/vectors';vectors.mkdir(parents=True)
        (base/'conformance/stdlib-vectors').mkdir(parents=True)
        (base/'sample-suite/programs').mkdir(parents=True)
        (vectors/'schema.json').write_text('{}')
        (vectors/'case.dsl').write_text('let value = 1;')
        compiler=base/'compiler'
        compiler.write_text('#!/bin/sh\necho "error:probe.lms:2:1: _lmcode_: schema rejected" >&2\nexit 2\n')
        compiler.chmod(0o755)
        return dict(os.environ,LMCODE_CPP=str(base),LMSCRIPT_BIN=str(compiler))
    def test_rejecting_all_inputs_is_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            env=self.fixture(Path(directory))
            result=subprocess.run([sys.executable,str(ROOT/'tests/grammar/mutate_diff.py'),'--limit','1','--per-program','2'],env=env,capture_output=True)
            self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn(b'baseline',result.stdout+result.stderr)
    def test_empty_seed_set_is_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);env=self.fixture(base)
            (base/'conformance/vectors/case.dsl').unlink()
            result=subprocess.run([sys.executable,str(ROOT/'tests/grammar/mutate_diff.py')],env=env,capture_output=True)
            self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn(b'empty',result.stdout+result.stderr)
