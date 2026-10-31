#!/usr/bin/env python3
"""Differential accept/reject testing: this grammar (Lark, from spec/grammar.ebnf) against
the real compiler (the standalone `lmscript` binary from a private npm prefix install).

For each seed body, each mutation operator produces one mutant; both sides answer
accept/reject. A disagreement is either a grammar bug (fixed on sight) or a documented
static-semantics difference (the grammar is a syntax checker; name resolution, typing,
schema checks and the call-only statement rule live in dsl.ts, not in the EBNF -- they are
listed in spec/grammar.md under "static semantics, not grammar").

Compiler verdict: `lmscript --check` on `program = _lmcode_ schema=<conformance schema>;
<body> end _lmcode_` in a scratch directory. exit 0 = accept, exit 2 = reject. Mutated
bodies that fail the OUTER lmscript language (e.g. a mutation garbling the wrapper) are
reported separately, not as grammar disagreements.

Usage: mutate_diff.py [--seed N] [--per-program N] [--limit N] [--json OUT]
"""
import argparse
import json
import os
import random
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_lib import build_parser, parse_body  # noqa: E402
from prelexer import find_heredocs, substitute_splices  # noqa: E402
from extract_blocks import extract_blocks  # noqa: E402

LMSCRIPT = os.environ.get('LMSCRIPT_BIN', '/tmp/wp33-lmctl/node_modules/.bin/lmscript')
CPP = os.environ.get('LMCODE_CPP', '/home/mma/repos/lmcode-team/lmcode-cpp')
SCHEMA = os.environ.get('LMCODE_CONFORMANCE_SCHEMA', str(Path(CPP) / 'conformance/vectors/schema.json'))

TOKEN_RE = re.compile(r'''
    "(?:[^"\\\n]|\\.)*"          # string
  | [0-9]+\.[0-9]+                # float
  | [0-9]+                        # int
  | [A-Za-z_][A-Za-z0-9_]*        # ident/keyword
  | =>|==|!=|<=|>=|&&|\|\|        # two-char puncts
  | \S                            # any other single char
''', re.X)


def tokens_of(text):
    return TOKEN_RE.findall(text)


def splice_text(body):
    """The text BOTH sides see for suite bodies: splices substituted outside heredocs."""
    lines = body.split('\n')
    regions, _ok = find_heredocs(lines)
    skip = set()
    for start, end in regions:
        skip.update(range(start + 1, end + 1))
    return substitute_splices(body, skip)


KEYWORD_SWAP = {'let': 'iff', 'if': 'iff', 'return': 'ret', 'while': 'until', 'for': 'each',
                'switch': 'select', 'case': 'when', 'default': 'otherwise', 'break': 'stop',
                'continue': 'skip', 'in': 'of', 'fn': 'fun', 'implements': 'impls'}


def mutants(body, rng, per_program):
    """Yield (label, mutant_text). All operators work on the token stream and rejoin with
    single spaces, which never changes lmcode's meaning (whitespace is insignificant)."""
    toks = tokens_of(body)
    if len(toks) < 4:
        return
    out = []
    for _ in range(per_program):
        choice = rng.randrange(8)
        t = list(toks)
        i = rng.randrange(len(t))
        if choice == 0:  # delete a token
            label = f'delete {t[i]!r}'
            del t[i]
        elif choice == 1:  # swap adjacent tokens
            j = min(i + 1, len(t) - 1)
            label = f'swap {t[i]!r} {t[j]!r}'
            t[i], t[j] = t[j], t[i]
        elif choice == 2:  # keyword -> wrong keyword
            word_idxs = [k for k, w in enumerate(t) if w in KEYWORD_SWAP]
            if not word_idxs:
                continue
            i = rng.choice(word_idxs)
            label = f'keyword {t[i]}->{KEYWORD_SWAP[t[i]]}'
            t[i] = KEYWORD_SWAP[t[i]]
        elif choice == 3:  # unbalance: remove one brace/paren
            brace_idxs = [k for k, w in enumerate(t) if w in '{}()']
            if not brace_idxs:
                continue
            i = rng.choice(brace_idxs)
            label = f'unbalance remove {t[i]!r}'
            del t[i]
        elif choice == 4:  # drop a semicolon
            semi = [k for k, w in enumerate(t) if w == ';']
            if not semi:
                continue
            i = rng.choice(semi)
            label = 'drop ;'
            del t[i]
        elif choice == 5:  # duplicate an operator
            op_idxs = [k for k, w in enumerate(t) if w in '+-*/%=<>!']
            if not op_idxs:
                continue
            i = rng.choice(op_idxs)
            label = f'duplicate operator {t[i]!r}'
            t.insert(i, t[i])
        elif choice == 6:  # a bare number as a statement (valid syntax, not a call)
            label = 'insert bare number statement'
            t.insert(i, '42')
            t.insert(i + 1, ';')
        elif choice == 7:  # undeclared name as a statement call
            label = 'call undeclared name'
            t.insert(i, 'definitely_undefined_name_xyz')
            t.insert(i + 1, '(')
            t.insert(i + 2, ')')
            t.insert(i + 3, ';')
        out.append((label, ' '.join(t)))
    return out


def compiler_verdict(body, workdir):
    """(accept, message). exit 2 = reject (compile error); anything else non-zero is
    reported as an outer-layer failure, not a grammar verdict."""
    source = ('program = _lmcode_ schema=' + json.dumps(SCHEMA) + ';\n'
              + body + '\nend _lmcode_\n')
    path = Path(workdir) / 'probe.lms'
    path.write_text(source)
    result = subprocess.run([LMSCRIPT, '--check', str(path)], capture_output=True, text=True,
                            env={'PATH': os.environ['PATH'], 'HOME': workdir}, timeout=60)
    if result.returncode == 0:
        return True, ''
    text = (result.stderr + result.stdout).strip()
    if result.returncode != 2 or '_lmcode_:' not in text:
        return None, text.splitlines()[0] if text else f'exit {result.returncode}'
    return False, text.splitlines()[0]


# Compiler messages that are static semantics (name resolution, typing, schema and effect
# rules), NOT grammar. Everything else gets human review via the disagreement list.
STATIC_PATTERNS = [
    'undefined name', 'undefined variable', 'has no method', 'expects', 'conflicts with',
    'cannot assign',
    'no overload', 'ambiguous', 'already declared', 'read-only', 'cannot be redeclared',
    'has no effect', 'keyword', 'built-in', 'shadow', 'unknown type', 'unknown value',
    'unknown interface', 'not declared', 'no implicit conversion', 'return', 'implements',
    'duplicate', 'void', 'foreach', 'range ', 'range(', 'switch', 'must be', 'cannot',
    'not allowed', 'is not', 'exceeds', 'does not declare', 'never', 'only allowed',
    'requires', 'unknown escape', 'malformed number', 'literal', 'enum', 'interfaces',
    'reserved', 'already', 'schema', 'interface',
]


def classify(message):
    for pattern in STATIC_PATTERNS:
        if pattern in message:
            return 'static-semantics'
    return 'GRAMMAR-REVIEW'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, default=20261030)
    ap.add_argument('--per-program', type=int, default=6)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--json', default='')
    args = ap.parse_args()

    cpp = Path(CPP)
    seeds = []
    for path in sorted((cpp / 'conformance/vectors').glob('*.dsl')) + sorted((cpp / 'conformance/stdlib-vectors').glob('*.dsl')):
        seeds.append((path.name, path.read_text()))
    for path in sorted((cpp / 'sample-suite/programs').glob('*.lms'))[:40]:
        for n, (_m, body) in enumerate(extract_blocks(path.read_text())):
            seeds.append((f'{path.name}#{n}', splice_text(body)))
    if args.limit:
        seeds = seeds[:args.limit]

    rng = random.Random(args.seed)
    parser = build_parser()
    worklist = []
    for name, body in seeds:
        for label, mutant in mutants(body, rng, args.per_program):
            worklist.append((name, label, mutant))

    print(f'{len(seeds)} seed programs, {len(worklist)} mutants')
    agreements = 0
    disagreements = []
    outer_failures = 0

    def judge(item):
        name, label, mutant = item
        mine = parse_body(parser, mutant)
        with tempfile.TemporaryDirectory(prefix='wp33-diff-') as workdir:
            compiler_ok, message = compiler_verdict(mutant, workdir)
        return name, label, mine.ok, mine.error, compiler_ok, message

    with ThreadPoolExecutor(max_workers=8) as pool:
        for name, label, mine_ok, mine_err, compiler_ok, message in pool.map(judge, worklist):
            if compiler_ok is None:
                outer_failures += 1
                continue
            if mine_ok == compiler_ok:
                agreements += 1
                continue
            cls = classify(message)
            disagreements.append({'seed': name, 'mutation': label,
                                  'grammar': 'accept' if mine_ok else 'reject',
                                  'compiler': 'accept' if compiler_ok else 'reject',
                                  'class': cls, 'compiler_message': message[:160]})

    print(f'agreements: {agreements}; outer-layer failures (not verdicts): {outer_failures}')
    bugs = [d for d in disagreements if d['class'] == 'GRAMMAR-REVIEW']
    static = [d for d in disagreements if d['class'] == 'static-semantics']
    print(f'disagreements: {len(disagreements)} ({len(bugs)} grammar-review, {len(static)} static-semantics)')
    for d in bugs[:20]:
        print(f"  GRAMMAR-REVIEW {d['seed']} [{d['mutation']}]: grammar={d['grammar']} compiler={d['compiler']} -- {d['compiler_message']}")
    if args.json:
        Path(args.json).write_text(json.dumps({'seed': args.seed, 'per_program': args.per_program,
                                               'programs': len(seeds), 'mutants': len(worklist),
                                               'agreements': agreements, 'outer_failures': outer_failures,
                                               'disagreements': disagreements}, indent=1))
    print('RESULT: ' + ('FAIL (grammar-review disagreements need fixes or reclassification)' if bugs else 'OK'))
    return 1 if bugs else 0


if __name__ == '__main__':
    sys.exit(main())
