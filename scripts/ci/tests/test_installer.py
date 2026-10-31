import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]

class Installer(unittest.TestCase):
    def test_private_prefix_and_selector(self):
        with tempfile.TemporaryDirectory(prefix='ci installer ') as directory:
            temp = Path(directory)
            mock = temp / 'npm'
            mock.write_text('''#!/usr/bin/env python3
import json,os,pathlib,sys
args=sys.argv[1:]
pathlib.Path(os.environ['NPM_ARGS']).write_text(json.dumps(args))
prefix=pathlib.Path(args[args.index('--prefix')+1]); bins=prefix/'node_modules/.bin'; bins.mkdir(parents=True)
f=bins/'lmscript'; f.write_text('#!/bin/sh\\necho lmscript 0.2.444\\n'); f.chmod(0o755)
''')
            mock.chmod(0o755)
            env = dict(os.environ, PATH=str(temp)+os.pathsep+os.environ['PATH'], RUNNER_TEMP=str(temp), NPM_ARGS=str(temp/'args'), GITHUB_ENV=str(temp/'env'), GITHUB_PATH=str(temp/'path'))
            for selector in ('staging','0.2.444'):
                env['COMPILER_VERSION'] = selector
                result = subprocess.run(['bash', str(ROOT/'scripts/ci/install-compiler.sh')], env=env, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                args = json.loads((temp/'args').read_text())
                self.assertNotIn('-g', args)
                self.assertEqual(args[-1], '@lmctl-ai/lmctl@'+selector)
                self.assertTrue(Path(args[args.index('--prefix')+1]).is_relative_to(temp))
                self.assertIn('LMSCRIPT_BIN=', (temp/'env').read_text())
            (temp/'args').unlink()
            env['COMPILER_VERSION'] = '--global'
            bad = subprocess.run(['bash', str(ROOT/'scripts/ci/install-compiler.sh')], env=env, capture_output=True)
            self.assertEqual(bad.returncode,2)
            self.assertFalse((temp/'args').exists(), 'invalid selector must not invoke npm')

    def test_probe_rejects_a_v5_compiler(self):
        with tempfile.TemporaryDirectory(prefix='wrong compiler ') as directory:
            fake = Path(directory)/'compiler'
            fake.write_text("#!/usr/bin/env python3\nimport pathlib,sys\nsource=pathlib.Path(sys.argv[-2]).read_text()\nif 'wrong type' in source: sys.exit(2)\npathlib.Path(sys.argv[-1]).write_bytes(b'DSLB\\x00\\x05')\n")
            fake.chmod(0o755)
            result = subprocess.run(['python3',str(ROOT/'scripts/ci/probe-compiler.py')],env=dict(os.environ,LMSCRIPT_BIN=str(fake)),capture_output=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn(b'did not produce DSLB v6',result.stderr)
