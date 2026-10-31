import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[3]

class TutorialOutput(unittest.TestCase):
    def test_wrong_documented_stdout_is_caught(self):
        with tempfile.TemporaryDirectory() as directory:
            doc=Path(directory)/'tutorial.md'
            text=(ROOT/'guides/writing-lmcode.md').read_text(encoding='utf8')
            needle='\nhello from lmcode: 7\n'
            self.assertEqual(text.count(needle),1)
            doc.write_text(text.replace(needle,'\nhello from lmcode: 8\n'),encoding='utf8')
            result=subprocess.run([sys.executable,str(ROOT/'scripts/ci/check-tutorial.py'),'--document',str(doc),'--case','1','--sample-root',os.environ['LMCODE_SAMPLE']],capture_output=True,timeout=60)
            self.assertNotEqual(result.returncode,0)
            self.assertIn(b'Tutorial case 1 output mismatch',result.stderr)
