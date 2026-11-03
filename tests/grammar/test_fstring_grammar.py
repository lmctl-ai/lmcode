#!/usr/bin/env python3
"""Pin the formatted-string subset accepted by the normative grammar."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_lib import build_parser, parse_body


class FormattedStringGrammarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = build_parser()

    def test_accepts_nested_expression_escape_and_literal_braces(self):
        source = 'let n = 7; let text = f"{{value}}={str((n + 1) * 2)}\\n";'
        self.assertTrue(parse_body(self.parser, source).ok)

    def test_rejects_nested_formatted_string(self):
        source = 'let text = f"{f\\"inner\\"}";'
        self.assertFalse(parse_body(self.parser, source).ok)

    def test_rejects_nested_formatted_string_inside_call(self):
        source = 'let text = f"{str(f"inner")}";'
        self.assertFalse(parse_body(self.parser, source).ok)

    def test_rejects_unclosed_field(self):
        source = 'let text = f"{str(1)";'
        self.assertFalse(parse_body(self.parser, source).ok)

    def test_rejects_format_specifier(self):
        source = 'let text = f"{str(1):04}";'
        self.assertFalse(parse_body(self.parser, source).ok)

    def test_rejects_unknown_escape(self):
        source = 'let text = f"\\q";'
        self.assertFalse(parse_body(self.parser, source).ok)


if __name__ == '__main__':
    unittest.main()
