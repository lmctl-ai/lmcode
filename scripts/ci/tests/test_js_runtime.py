"""Exercise the actual matrix shell runner with an owned fake SDK/toolchain."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]

class JavaScriptRuntime(unittest.TestCase):
    def run_cell(self, failure=''):
        with tempfile.TemporaryDirectory(prefix='lmcode js matrix ') as tmp:
            work = Path(tmp)
            runtime, reference = work/'runtime', work/'reference'
            for tree in (runtime, reference):
                for suite in ('vectors', 'stdlib-vectors', 'return-vectors', 'invocation-vectors'):
                    (tree/'conformance'/suite).mkdir(parents=True)
            (work/'bin').mkdir()
            log = work/'calls'
            for tool in ('node', 'npm', 'compiler'):
                script = work/'bin'/tool
                script.write_text('#!/bin/sh\nprintf "%s %s\\n" "'+tool+'" "$*" >> "$CALL_LOG"\n'
                                  'if [ "'+tool+' $*" = "$FAIL_CALL" ]; then echo "FAIL JS canonical conformance" >&2; exit 73; fi\n')
                script.chmod(0o755)
            env = dict(os.environ, LANGUAGE='js', RUNTIME_DIR=str(runtime), SAMPLE_DIR=str(runtime),
                       REFERENCE_CPP_DIR=str(reference), LMSCRIPT_BIN=str(work/'bin/compiler'),
                       PATH=str(work/'bin')+os.pathsep+os.environ['PATH'], CALL_LOG=str(log), FAIL_CALL=failure)
            result = subprocess.run(['bash', str(ROOT/'scripts/ci/cross-runtime.sh')], env=env, capture_output=True, text=True)
            return result, log.read_text() if log.exists() else ''

    def test_real_runner_installs_syncs_and_tests_javascript(self):
        result, calls = self.run_cell()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('PASS cross-runtime js', result.stdout)
        for call in ('npm ci', 'npm test', 'npm run mutation', 'npm run conformance',
                     'npm run verify:pins', 'npm run sample-suite', 'node scripts/sync-std.mjs',
                     'node scripts/sync-vectors.mjs', 'node scripts/sync-sample-suite.mjs'):
            self.assertIn(call+'\n', calls)

    def test_canonical_failure_is_a_failed_matrix_cell(self):
        result, calls = self.run_cell('npm run conformance')
        self.assertEqual(result.returncode, 73, result.stderr)
        self.assertIn('FAIL JS canonical conformance', result.stderr)
        self.assertNotIn('PASS cross-runtime js', result.stdout)
        self.assertNotIn('npm run sample-suite', calls, 'failure must stop subsequent gates')
