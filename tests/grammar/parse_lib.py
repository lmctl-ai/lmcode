#!/usr/bin/env python3
"""Shared parser plumbing: build the Lark parser from spec/grammar.ebnf via
ebnf_to_lark.py, parse a prepared lmcode body, and account rule/terminal coverage."""
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ebnf_to_lark import split_rules, strip_comments, translate  # noqa: E402
from prelexer import prelex  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
EBNF = ROOT / 'spec' / 'grammar.ebnf'


def grammar_source():
    return EBNF.read_text()


def rule_inventory():
    """(parser rules, checkable terminals) as declared in PARTS A+B of the .ebnf.
    Documentary terminals (structure shown, produced by the pre-lexer) and the two %ignore
    forms are excluded from the coverage denominator."""
    text = grammar_source().split('(* checker: end *)')[0]
    documentary = set(re.findall(r'\(\*\s*checker:\s*documentary\s*\*\)\s*([A-Za-z_][A-Za-z0-9_]*)\s*::=', text))
    names = [n for n, _ in split_rules(strip_comments(text))]
    rules = sorted({n for n in names if not n.isupper()})
    terms = sorted({n for n in names if n.isupper()} - documentary - {'S', 'COMMENT', 'ESCAPE'})
    return rules, terms


def build_parser():
    from lark import Lark
    grammar = translate(grammar_source())
    return Lark(grammar, start='program', parser='lalr', lexer='basic', propagate_positions=False)


class Verdict:
    def __init__(self, ok, error=None, tree=None):
        self.ok = ok
        self.error = error
        self.tree = tree


def parse_body(parser, text, splice=False):
    """Parse one lmcode body. Returns Verdict. ok=False means the grammar rejects it
    (lex or parse failure); the pre-lexer reports an unterminated heredoc the same way."""
    prepared, counts, unterminated = prelex(text, splice=splice)
    if unterminated or counts['qw_broken']:
        return Verdict(False, 'unterminated heredoc or invalid qw/qi/qf literal (pre-lexer)')
    try:
        tree = parser.parse(prepared)
        return Verdict(True, tree=tree)
    except Exception as error:  # lark raises LarkError subclasses; verdict is what matters
        return Verdict(False, f'{type(error).__name__}: {error}')


def tree_usage(tree):
    """(rule names used, terminal types used) in one parse tree."""
    from lark import Tree, Token
    rules = set()
    terms = set()
    stack = [tree]
    while stack:
        node = stack.pop()
        if isinstance(node, Tree):
            rules.add(str(node.data))
            stack.extend(node.children)
        elif isinstance(node, Token):
            terms.add(node.type)
    return rules, terms
