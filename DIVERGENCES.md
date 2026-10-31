# Tree-sitter differential divergences

The differential gate lives in this shared specification repository at
`tests/grammar/tree_sitter_differential.py`. It exercises both pinned public
grammars against the published handwritten `lmscript --check` parser. The
grammar sources stay in their dedicated repositories; the full local corpus is
read-only and its source text is never copied into this repository.

Pins and source revisions are in `tests/grammar/tree-sitter-pins.json`. The
published oracle is `@lmctl-ai/lmctl@0.2.448`; grammar commits are
`tree-sitter-lmscript` `ff301218f388f30fcf40cd63d235070c162aa283` and
`tree-sitter-lmcode` `c9d5021cc98982f558937298e4add9a4f79c574a`. The mono
language source pinned by both grammar repos is `a9df5a8b`; the current mono
main checked for S3 is `0bc8027738be53d02c185d84851d46e7e8cd3819`.

## Accepted differences

The gate classifies only the cases below. A tree-sitter rejection of a source
the compiler accepts, or an unclassified compiler rejection of grammar-accepted
source, remains a hard failure.

1. **`checker-only`** — the grammar recognizes syntax but the handwritten
   checker rejects names, types, overloads, schema bindings, control-flow
   semantics, or effects. These are intentionally outside a syntax grammar.
2. **`embedded-body`** — the outer LMScript grammar exposes `_lmcode_` and other
   data-block bodies as opaque ranges. The compiler validates those bodies; the
   differential runs the lmcode grammar separately on extracted `_lmcode_` /
   `_dsl_` bodies and their syntax mutations.
3. **`external-schema`** — a `cli=` block cannot obtain its host schema because
   that host binary is not part of the grammar check environment. The source
   still participates in Tree-sitter parsing. For lmok rules, the gate prepends
   a tiny `lmok --lmcode-schema --json` shim that prints the checked-in
   `schema/lmok.host.json`; it does not run lmok or evaluate a rule. The
   `c-cross-file` fixture uses `install=...@latest`, which check mode refuses
   to fetch when that release is not cached.
4. **`published-baseline`** — the selected npm compiler predates a feature
   already on mono main. In particular, mainline `$return` lowering, returned
   frames, immutable executable descriptors (`load_schema`, `out=`), and
   reverse-template functions are on mono main as of the pin above, while the
   published 0.2.448 oracle does not include that entire change. The grammar
   corpus's planned block-handle `out=` case and comment-bearing splice case are
   therefore expected compiler rejections at this npm pin. These are parser-
   version differences, not claims that the feature is planned on mono.

The operator's requested lmcode additions are syntax-safe in both grammars;
their implementation status follows mono main, not the npm oracle. New grammar
syntax must be added to its matching corpus before changing these categories.

## Mainline additions at the source pin

| Addition | Mono main status | Pinned npm oracle |
|---|---|---|
| `$return`, `$return.name`, `$return[expr]` lowering | Landed in compiler slice 3; frame execution/decoding is present at `0bc80277` | Not in 0.2.448 |
| `_lmcode_` returns a value; `load_schema(...)`; `out=...`; `LMCODE_RETURN_BEGIN/END` | Landed at `0bc80277` (`lmcode-execution.ts`, `lmcode-frame.ts`) | Not in 0.2.448 |
| Structural and text reverse-template extraction | Landed before `0bc80277` (`template_extract*`) | Not in 0.2.448 |

The Tree-sitter grammars cover the current mono syntax. The differential does not
claim the released npm compiler has those additions; updating the npm pin is an
explicit later source change after a release contains them.

## Corpus boundary

Local `--live` runs enumerate tracked `.lms` sources in mono `lmscript/examples`,
skills-scripts, lmcode-cpp `sample-suite`, and lmok `rules`, then make one seeded
malformed variant per source. Public Actions cannot read the mono or skills-scripts
private repositories. It checks the pinned public C++/lmok corpora plus both
grammar repositories' committed syntax corpora, with two seeded malformed
variants per source and a 500-document minimum. The workflow does not publish
private source text or depend on private-repository credentials.

Local S3 evidence at mono `0bc8027738be53d02c185d84851d46e7e8cd3819`, skills-scripts
`76713bdd9d746438acc3c061d26f69dfa3c736d4`, C++ `6ee3d62`, and lmok `128dc032`:
1006 documents (503 seeds, 503 seeded mutations), 190 accepted valid sources,
699 agreeing compiler/grammar verdicts, and 307 divergences classified above.
No compiler-oracle failures remained. The required grammar-corruption control
is in `tests/grammar/test_tree_sitter_differential.py`.
