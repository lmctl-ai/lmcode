# lmcode tree-sitter syntax tooling

Status: S2 grammar implemented; schema-semantic differential testing (S3), lmok
registration/facts (S4), and injection/offset rebasing (S5) remain separate work.

The public MIT grammar is [lmctl-ai/tree-sitter-lmcode](https://github.com/lmctl-ai/tree-sitter-lmcode).
Its maintainer/sync owner is the lmctl lmscript team. It commits grammar.js, the
queued-heredoc external scanner and generated C; native consumers compile
src/parser.c together with src/scanner.c. No runtime SDK or sample layout changes
are required. lmcode-cpp remains the source of its existing canonical suites.

Initial grammar revision: 2218b71355589e6289c19ad5994b9719d77e92f8. It was checked
against mono a9df5a8b793ddc90f572d5c5be5800ba8dc448dc, lmok
f13cc8f7df75f87d631adfbcb99ba4b291e34272, and lmcode-cpp
df286aced04cca0767d61a1468867fbb3c20a6db. SOURCE-PINS.json and the fixture manifest
record source/body hashes and original line numbers.

Coverage: 38 tree-sitter corpus cases, 127 pinned real bodies (mono examples,
lmok rules and C++ sample programs), 21 malformed inputs, incremental UTF-8 edits,
and six production-copy failure controls. Actions runs generation freshness,
scanner compilation and the suites on Ubuntu/macOS. The initial successful run is
[41171799460](https://github.com/lmctl-ai/tree-sitter-lmcode/actions/runs/41171799460).

The grammar recognizes typed functions, annotations/implements, control flow,
qw/qi/qf, map entries, queued raw/dedented heredocs, parsed LMScript splices, and
write-only return assignments. $return lowering is present in the pinned mono
source. The EBNF's 0.2.444 snapshot predates that addition; this tooling note does
not silently redefine that older version. Executing block results, schema handles
and reverse-template semantics are not certified by parsing a body.

A clean tree is not a type/schema check. The grammar's DIVERGENCES.md documents
binding-sensitive literal forms, semantic validation, version skew and the
bounded external-scanner serialization state. Heredoc bodies are named extras
paired with their expression-position openers in FIFO order. The outer lmscript
parser and lmok injection must retain/rebase byte ranges; this repo does not
substitute a combined parser or tree-sitter-based bytecode compiler.
