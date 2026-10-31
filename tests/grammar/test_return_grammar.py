"""Return lvalues extend mainline syntax without adding general indexing or reads."""
import unittest
from parse_lib import build_parser, parse_body
from mutate_diff import classify


class ReturnGrammarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = build_parser()

    def test_write_forms(self):
        for source in ('$return = 1;', '$ return = 1;', 'let null = 1;', '$return = null;', '$return.name = null;',
                       '$return["key"] = true;', '$return[key] = value;',
                       'fn f() -> int { $return.x = 1; return 2; }'):
            with self.subTest(source=source):
                self.assertTrue(parse_body(self.parser, source).ok)

    def test_reads_nested_paths_and_general_indexing_are_not_syntax(self):
        for source in ('let x = $return;', '$return.x.y = 1;',
                       '$return["x"]["y"] = 1;', 'let x = xs[0];',
                       '$return =;', '$return["x" = 1;'):
            with self.subTest(source=source):
                self.assertFalse(parse_body(self.parser, source).ok)


class BaselineClassificationTests(unittest.TestCase):
    def test_known_release_gap_requires_capability_probe(self):
        message = 'error:probe.lms:2:1: _lmcode_: unexpected character "$"'
        self.assertEqual(classify(message), 'GRAMMAR-REVIEW')
        self.assertEqual(classify(message, return_baseline=True), 'compiler-baseline')
        self.assertEqual(classify('unexpected character "?"', return_baseline=True), 'GRAMMAR-REVIEW')


if __name__ == '__main__':
    unittest.main()
