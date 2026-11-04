# Tree-sitter differential divergences

The differential gate lives in this shared specification repository at
`tests/grammar/tree_sitter_differential.py`. It exercises both pinned public
grammars against the published handwritten `lmscript --check` parser. The
grammar sources stay in their dedicated repositories; the full local corpus is
read-only and its source text is never copied into this repository.

Pins and source revisions are in `tests/grammar/tree-sitter-pins.json`. The
published CI oracle is `@lmctl-ai/lmctl@0.2.450`; grammar commits are
`tree-sitter-lmscript` `268fb894c981041bfed0233b6320178e100410e4` and
`tree-sitter-lmcode` `f7937605db4a07464a333d4ca900090b09baa44a`. The mono
language source pinned by both grammar repos is `a9df5a8b`; local mainline
verification used `bc5646d07cc59e6c940cc2312276ed0aa7bdcb6a`.

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
   published 0.2.450 oracle does not include that entire change. The grammar
   corpus's planned block-handle `out=` case and comment-bearing splice case are
   therefore expected compiler rejections at this npm pin. Body formatting is owned by lmscript and is classified separately below.
5. **`mainline-parser-change`** — the source compiler has removed a syntax form
   that the separately pinned Tree-sitter lmscript corpus still accepts. The
   current example is the old import-alias spelling (`Import aliases were
   removed; a source module declares its package`). This is an upstream grammar
   pin mismatch outside the body-format layering move.

6. **`lmscript-body-expansion`** — a successful high-level body-format seed is
   checked through the lmscript wrapper, while the standalone lmcode parser
   correctly rejects its unexpanded formatting syntax. Invalid format seeds must
   still be refused. The lmscript-owned companion parser checks template syntax;
   this classification does not grant formatting syntax to standalone lmcode.

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

Local f-string follow-up evidence at mono `bc5646d07cc59e6c940cc2312276ed0aa7bdcb6a`,
C++ `6ee3d62`, lmok corpus `128dc032`, and the grammar pins above: 1,164 documents
(388 seeds, including seven deterministic f-string inputs; 776 seeded mutations),
49 accepted valid sources, 834 agreeing verdicts and 330 documented divergences.
No compiler-oracle failures remained. The required grammar-corruption control is
in `tests/grammar/test_tree_sitter_differential.py`.
