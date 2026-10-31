# Grammar checker for lmcode

The normative grammar is `../../spec/grammar.ebnf` (W3C EBNF, subset documented in its
header). The inner grammar covers released 0.2.444 plus mainline slice-3 return writes.
The corpus gate is pinned in CI to C++ `aaa9088` / lmok `f13cc8f7` (799 bodies).
The differential probes `$return` capability first. On released 0.2.444, grammar-accepted
return writes rejected with the exact unsupported-dollar diagnostic are counted separately
as `compiler-baseline`, rather than static semantics or evidence of shipped return support.
This directory checks syntax against corpora and the real compiler
(`lmscript/dsl.ts` in the monorepo, run from a private npm prefix, never a global install).

- `ebnf_to_lark.py` — mechanical translator from the .ebnf subset to a Lark grammar. The
  translation is the claim: the spec file IS the checked grammar.
- `prelexer.py` — procedural handling for the two non-regular lexical forms (heredocs with
  tag matching, qw/qi/qf word validation), mirroring dsl.ts's own tokenizer, plus the `${}`
  splice stand-in for lmscript-wrapped bodies.
- `extract_blocks.py` — pulls `_lmcode_`/`_dsl_` block bodies out of .lms sources per the
  outer block rules.
- `parse_lib.py` — parser construction, verdicts, coverage accounting.
- `check_corpus.py` — parses every lmcode body in the conformance vectors, stdlib vectors,
  sample-suite, examples and lmok rules; requires zero failures; prints rule/terminal
  coverage.
- `mutate_diff.py` — differential accept/reject against the real compiler (`lmscript
  --check`, from `npm install --prefix /tmp/wp33-lmctl @lmctl-ai/lmctl@0.2.444`) on a
  token-level mutation corpus; every disagreement is classified grammar bug (fixed) or
  documented static-semantics difference (spec/grammar.md).

Run locally from the repository root with the private Python/compiler setup in
[scripts/ci](../../scripts/ci/README.md). Paths are explicit; missing or empty
corpora cannot pass. Set LMCODE_CPP and LMCODE_LMOK (or LMOK), and LMSCRIPT_BIN:

```sh
python3 tests/grammar/check_corpus.py --cpp-root "$LMCODE_CPP" --lmok-root "$LMCODE_LMOK"
python3 tests/grammar/mutate_diff.py            # requires the explicitly selected compiler
```

CI runs the corpus check on every push (`.github/workflows/grammar.yml`); the
differential stays manual/scheduled because it needs a private compiler install and takes
minutes.
