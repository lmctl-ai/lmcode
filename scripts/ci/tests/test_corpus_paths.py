import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]

class CorpusPaths(unittest.TestCase):
    def test_explicit_empty_roots_cannot_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            result=subprocess.run([sys.executable,str(ROOT/'tests/grammar/check_corpus.py'),'--cpp-root',directory,'--lmok-root',directory],capture_output=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
            self.assertEqual(result.returncode,2,result.stdout+result.stderr)
            self.assertIn(b'missing corpus',result.stderr)
    def test_selected_sources_and_syntax_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            for name in ('conformance/vectors','conformance/stdlib-vectors','sample-suite/programs','examples','rules/lmcode'):
                target=base/name;target.mkdir(parents=True)
                if name.startswith('conformance'):
                    (target/'case.dsl').write_text('let value = 1;')
                else:
                    (target/'case.lms').write_text('program = _lmcode_ schema="unused";\nlet value = 1;\nend _lmcode_\n')
            command=[sys.executable,str(ROOT/'tests/grammar/check_corpus.py'),'--cpp-root',str(base),'--lmok-root',str(base)]
            ok=subprocess.run(command,capture_output=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
            self.assertEqual(ok.returncode,0,ok.stdout+ok.stderr)
            self.assertIn(b'5 bodies',ok.stdout)
            (base/'conformance/vectors/case.dsl').write_text('let = ;')
            bad=subprocess.run(command,capture_output=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
            self.assertEqual(bad.returncode,1,bad.stdout+bad.stderr)
            self.assertIn(b'FAIL conformance/case.dsl',bad.stdout)
