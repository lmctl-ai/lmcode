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
