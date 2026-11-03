import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('ci_matrix', Path(__file__).resolve().parents[1]/'matrix.py')
matrix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(matrix)

class Matrix(unittest.TestCase):
    def test_tag_is_resolved_once_to_a_concrete_version(self):
        with patch.dict(os.environ,COMPILER_VERSION='staging'), patch.object(matrix.subprocess,'check_output',return_value='"0.2.444"') as npm:
            self.assertEqual(matrix.compiler_version(),'0.2.444')
            self.assertIn('@lmctl-ai/lmctl@staging',npm.call_args.args[0])
    def test_ambiguous_or_invalid_resolution_fails(self):
        for result in ('["0.2.443","0.2.444"]','null','"staging"'):
            with self.subTest(result=result), patch.object(matrix.subprocess,'check_output',return_value=result):
                with self.assertRaises(ValueError): matrix.compiler_version()

    def test_javascript_uses_its_bundled_sample_on_all_five_platforms(self):
        import contextlib
        import io
        import json
        repos = []
        def ref(repo):
            repos.append(repo)
            return ('b' if repo == 'lmcode-js' else 'a') * 40
        output = io.StringIO()
        with patch.object(matrix, 'revision', side_effect=ref), patch.object(matrix, 'compiler_version', return_value='0.2.456'), patch.dict(os.environ, GITHUB_OUTPUT=''), contextlib.redirect_stdout(output):
            matrix.main()
        rows = json.loads(next(line[7:] for line in output.getvalue().splitlines() if line.startswith('matrix=')))['include']
        js = [row for row in rows if row['language'] == 'js']
        self.assertEqual(len(js), 5, 'JavaScript must participate in every native platform')
        self.assertEqual(len(rows), 30)
        self.assertEqual({row['platform'] for row in js}, {'linux-x64', 'linux-arm64', 'macos-arm64', 'macos-x64', 'windows-x64'})
        self.assertTrue(all(row['sample_sha'] == row['runtime_sha'] == 'b'*40 for row in js))
        self.assertNotIn('lmcode-js-sample', repos, 'JS sample is bundled, not a separate repository')
