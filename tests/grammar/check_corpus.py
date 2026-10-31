#!/usr/bin/env python3
"""Parse every lmcode program in the conformance and sample corpora with the grammar, and
report per-suite failures plus grammar coverage. Zero parse failures is the gate.

Corpora (paths overridable as argv, in order):
  1. lmcode-cpp conformance vectors + stdlib-vectors (raw .dsl bodies)
  2. lmcode-cpp sample-suite programs + examples (lmscript-wrapped; blocks extracted)
  3. lmok/rules/lmcode rule files (lmscript-wrapped; blocks extracted)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_lib import build_parser, parse_body, rule_inventory, tree_usage  # noqa: E402
from extract_blocks import extract_blocks  # noqa: E402

DEFAULT_ROOTS = [
    ('conformance', Path('/home/mma/repos/lmcode-team/lmcode-cpp/conformance/vectors'), 'raw'),
    ('stdlib-vectors', Path('/home/mma/repos/lmcode-team/lmcode-cpp/conformance/stdlib-vectors'), 'raw'),
    ('sample-suite', Path('/home/mma/repos/lmcode-team/lmcode-cpp/sample-suite/programs'), 'lms'),
    ('cpp-examples', Path('/home/mma/repos/lmcode-team/lmcode-cpp/examples'), 'lms'),
    ('lmok-rules', Path('/home/mma/repos/lmcode-team/lmok/rules/lmcode'), 'lms'),
]
EXTRA_LMS = [Path('/home/mma/repos/lmcode-team/lmcode-cpp/test.lms')]


def main():
    parser = build_parser()
    failures = []
    total_files = 0
    total_bodies = 0
    used_rules = set()
    used_terms = set()
    per_suite = {}
    for suite, directory, mode in DEFAULT_ROOTS:
        files = sorted(directory.glob('*.dsl' if mode == 'raw' else '*.lms'))
        suite_files = 0
        suite_bodies = 0
        for path in files:
            total_files += 1
            suite_files += 1
            if mode == 'raw':
                bodies = [(path.name, path.read_text())]
            else:
                try:
                    bodies = [(f'{path.name}#{n}', body) for n, (_m, body) in enumerate(extract_blocks(path.read_text()))]
                except ValueError as error:
                    failures.append((suite, path.name, f'extract: {error}'))
                    continue
            for label, body in bodies:
                total_bodies += 1
                suite_bodies += 1
                verdict = parse_body(parser, body, splice=True)
                if not verdict.ok:
                    failures.append((suite, label, verdict.error))
                else:
                    rules, terms = tree_usage(verdict.tree)
                    used_rules |= rules
                    used_terms |= terms
        per_suite[suite] = (suite_files, suite_bodies)
    for path in EXTRA_LMS:
        if not path.exists():
            continue
        total_files += 1
        try:
            bodies = [(f'{path.name}#{n}', body) for n, (_m, body) in enumerate(extract_blocks(path.read_text()))]
        except ValueError as error:
            failures.append(('extra', path.name, f'extract: {error}'))
            continue
        for label, body in bodies:
            total_bodies += 1
            verdict = parse_body(parser, body, splice=True)
            if not verdict.ok:
                failures.append(('extra', label, verdict.error))
            else:
                rules, terms = tree_usage(verdict.tree)
                used_rules |= rules
                used_terms |= terms

    all_rules, all_terms = rule_inventory()
    # Sentinels are exercised when the pre-lexer produced them (they are in the tree as tokens).
    print('== grammar corpus check ==')
    for suite, (nf, nb) in per_suite.items():
        print(f'{suite}: {nf} files, {nb} bodies')
    print(f'total: {total_files} files, {total_bodies} bodies, {len(failures)} failures')
    for suite, label, error in failures[:40]:
        print(f'FAIL {suite}/{label}: {str(error).splitlines()[0][:120]}')
    exercised_rules = used_rules & set(all_rules)
    print(f'coverage: {len(used_rules)} parser rules exercised of {len(all_rules)} declared')
    uncovered = sorted(set(all_rules) - used_rules)
    if uncovered:
        print(f'uncovered rules: {", ".join(uncovered)}')
    print(f'terminals exercised: {len(used_terms)} of {len(all_terms)} declared')
    unc_terms = sorted(set(all_terms) - used_terms)
    if unc_terms:
        print(f'uncovered terminals: {", ".join(unc_terms)}')
    if failures:
        print('RESULT: FAIL')
        return 1
    print('RESULT: OK (zero parse failures across the corpora)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
