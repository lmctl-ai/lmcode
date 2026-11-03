import sys
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tests/grammar'))
from parse_lib import build_parser,parse_body,grammar_source
from ebnf_to_lark import translate
from lark import Lark

class CurrentGrammar(unittest.TestCase):
    def test_contextual_lalr_construction(self):
        # FSTRING_TEXT intentionally overlaps global whitespace: those bytes are
        # f-string content in this parser state, but trivia everywhere else.
        # Contextual lexing is the same mode used by parse_lib.build_parser().
        Lark(translate(grammar_source()),start="program",parser="lalr",lexer="contextual")
    def test_return_lowering_now_on_compiler_main(self):
        parser=build_parser()
        for source in ('$return = 1;', '$return = null;', '$ return.name = "value";', '$return["key"] = true;'):
            with self.subTest(source=source): self.assertTrue(parse_body(parser,source).ok)
    def test_return_reads_and_nested_targets_are_not_grammar(self):
        parser=build_parser()
        for source in ('let x = $return;', '$return.a.b = 1;', '$return["x"]["y"] = 1;'):
            with self.subTest(source=source): self.assertFalse(parse_body(parser,source).ok)
        self.assertTrue(parse_body(parser,'let null = 1; let x = null + 1;').ok)
