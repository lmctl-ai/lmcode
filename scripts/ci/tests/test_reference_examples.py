import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]

class ReferenceExamples(unittest.TestCase):
    def test_bad_return_type_in_the_document_is_caught(self):
        with tempfile.TemporaryDirectory(prefix='bad reference ', dir=ROOT) as directory:
            copied = Path(directory)
            for name in ('scripts/ci/check-reference-examples.py','scripts/ci/examples/reference.schema.json','spec/language.md'):
                target=copied/name
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(ROOT/name,target)
            doc=copied/'spec/language.md'
            text=doc.read_text(encoding='utf8')
            self.assertEqual(text.count('return x + amount;'),1)
            doc.write_text(text.replace('return x + amount;','return true;'),encoding='utf8')
            result=subprocess.run(['python3',str(copied/'scripts/ci/check-reference-examples.py')],env=os.environ,capture_output=True,timeout=60)
            self.assertNotEqual(result.returncode,0)
            self.assertIn(b'Reference example 6 failed',result.stderr)
