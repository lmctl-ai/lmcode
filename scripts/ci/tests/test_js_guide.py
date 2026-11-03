"""Mutate the documentation, then run the ordinary real compiler/SDK checker."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]

class JavaScriptGuide(unittest.TestCase):
    def check_changed(self, before, after):
        text = (ROOT/'guides/javascript-host.md').read_text(encoding='utf8')
        self.assertIn(before, text)
        with tempfile.TemporaryDirectory(prefix='js guide control ') as directory:
            document = Path(directory)/'guide.md'
            document.write_text(text.replace(before, after), encoding='utf8')
            return subprocess.run([sys.executable, str(ROOT/'scripts/ci/check-js-guide.py'),
                                   '--document', str(document)], env=os.environ, capture_output=True)

    def test_wrong_documented_stdout_is_caught(self):
        result = self.check_changed('"total":7,', '"total":8,')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'JavaScript guide output mismatch', result.stderr)

    def test_broken_host_callback_is_caught(self):
        result = self.check_changed('counter.value += amount;', 'counter.value += amount + 1n;')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'JavaScript guide output mismatch', result.stderr)

    def test_unclassified_example_cannot_be_silently_skipped(self):
        result = self.check_changed('## Canonical sync and checks', '```js\nthrow new Error("unqualified");\n```\n\n## Canonical sync and checks')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'classify every new example', result.stderr)
