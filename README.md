# lmcode

[![Cross-runtime conformance](https://github.com/lmctl-ai/lmcode/actions/workflows/cross-runtime.yml/badge.svg)](https://github.com/lmctl-ai/lmcode/actions/workflows/cross-runtime.yml)
[![JavaScript runtime CI](https://github.com/lmctl-ai/lmcode-js/actions/workflows/ci.yml/badge.svg)](https://github.com/lmctl-ai/lmcode-js/actions/workflows/ci.yml)

Syntax tooling: [tree-sitter-lmcode status, pins and integration boundaries](spec/tree-sitter-lmcode.md).

lmcode is a small, strongly typed language that compiles to **lmcode bytecode (DSLB v6)** and runs
inside a host program: the host declares its API as a JSON schema, the compiler type-checks
a chunk against that schema, and a per-language runtime SDK loads, verifies and executes the
bytecode with the host's objects. Programs are authored inside lmscript `_lmcode_` blocks;
the compiler ships in the published `@lmctl-ai/lmctl` package (0.2.444+, v6).

This repository is the public specification of the whole system: the language, the host
schema format, the bytecode, the standard library, the host CLI protocol, and the
conformance contract every runtime must pass.

## Who this is for

- **lmcode authors** — writing chunks: [guides/writing-lmcode.md](guides/writing-lmcode.md)
  (tutorial, every example verified against the published compiler and the C++ sample host),
  then [spec/language.md](spec/language.md) (full reference).
- **Host authors** — embedding lmcode in a program: [spec/schema.md](spec/schema.md) (the
  `dsl.schema: 2` format), [spec/host-protocol.md](spec/host-protocol.md) (CLI flags, result
  records, exit codes).
- **Runtime implementers** — porting the SDK to a new language:
  [guides/implementing-a-runtime.md](guides/implementing-a-runtime.md) (ordered milestones,
  pitfalls and the six current runtime implementations), [spec/bytecode.md](spec/bytecode.md) (DSLB v6 byte
  layout, opcodes, verifier rules), [spec/conformance.md](spec/conformance.md) (the vectors).

## Quickstart

For C++, follow the [verified author tutorial](guides/writing-lmcode.md): privately
install the pinned compiler, build the reference sample and run its checked programs.
For a host without a native build, use the [JavaScript host guide](guides/javascript-host.md)
with Node LTS. Both guides keep schema, host and compiler versions explicit; the
JavaScript example exercises BigInt, byte strings and the terminal result envelope.

## Documentation map

| Document | Contents |
|---|---|
| [spec/language.md](spec/language.md) | Language reference: lexis, types, statements, functions/inlining, `@NAME`/`implements` rule entries (R47–R49), errors, compile-time vs run-time |
| [spec/grammar.md](spec/grammar.md) + [spec/grammar.ebnf](spec/grammar.ebnf) | Formal grammar (W3C EBNF), machine-checked against the real compiler by [tests/grammar](tests/grammar/README.md) |
| [spec/schema.md](spec/schema.md) | Host schema format: types, functions, context, enums, conversions, operators, interfaces, the SHA-256 hash binding |
| [spec/bytecode.md](spec/bytecode.md) | DSLB v6 layout section by section, opcode table with widths and stack effects, entries section, verifier rules, loader errors |
| [spec/std.md](spec/std.md) + [spec/std-signatures.md](spec/std-signatures.md) | The standard catalog: ownership, byte-pinned locks, version history, and the generated 206-signature mainline list (181 in release 0.2.444) |
| [spec/host-protocol.md](spec/host-protocol.md) | Host CLI flags, result/diagnostic records, exit codes, the adopted `LMCODE_RETURN` frame and legacy host behavior |
| [spec/conformance.md](spec/conformance.md) | The conformance corpus and sample-suite: `.expect` protocols, vector counts, how to run them |
| [guides/implementing-a-runtime.md](guides/implementing-a-runtime.md) | Runtime porting guide: milestones, 15 cited pitfalls, per-language file map |
| [guides/javascript-host.md](guides/javascript-host.md) | JavaScript host SDK: registry, BigInt/byte strings, invocation metadata, dry mode and owned results |
| [guides/writing-lmcode.md](guides/writing-lmcode.md) | Author tutorial with verified examples |
| [CONFORMANCE-AUDIT.md](CONFORMANCE-AUDIT.md) | Where the canonical corpora live and what a green run proves |

## The lmcode repository family

| Repo | Role | Status (checked 2026-11-03) |
|---|---|---|
| [lmctl-ai/lmcode-cpp](https://github.com/lmctl-ai/lmcode-cpp) | Reference runtime (C++17, header-only `include/dslvm.hpp`); owns the canonical std schema and the conformance/sample corpora | Reference; current |
| [lmctl-ai/lmcode-rust](https://github.com/lmctl-ai/lmcode-rust) | Rust runtime (`dslvm` crate) | Experimental; passes the shared vectors |
| [lmctl-ai/lmcode-go](https://github.com/lmctl-ai/lmcode-go) | Go runtime (std-lib only) | Experimental; passes the shared vectors |
| [lmctl-ai/lmcode-java](https://github.com/lmctl-ai/lmcode-java) | Java 21 runtime (JVM + native-image) | Experimental; passes the shared vectors |
| [lmctl-ai/lmcode-csharp](https://github.com/lmctl-ai/lmcode-csharp) | .NET 8 runtime (NativeAOT supported) | Experimental; passes the shared vectors |
| [lmctl-ai/lmcode-js](https://github.com/lmctl-ai/lmcode-js) | Pure ESM JavaScript runtime on Node LTS; bundled Shop/Ledger CLI; [host guide](guides/javascript-host.md) | Experimental; all canonical suites pass; wp171 manifest fixes landed; fatal V8 OOM containment requires an external process boundary |
| lmcode-{cpp,c,go,rust,csharp,java,kotlin,scala}-sample | Eight separate teaching hosts; JS additionally bundles its host in the runtime repo, sharing the pinned sample-suite | Green per port; synced by lock files |
| [lmctl-ai/lmok](https://github.com/lmctl-ai/lmok) | Production host: tree-sitter lint tool using lmcode rule entries | Active; v6 entries drive `lmok check` |

The compiler lives in the lmctl monorepo (`lmscript/dsl.ts`) and ships with
`@lmctl-ai/lmctl`; it is not part of this repository.

## Current vs planned

The tutorial is verified with **mono main 7a1829a1** and the renamed hosts.
CI now pins **0.2.456**, including the mandatory invocation dry marker; historical
0.2.444 and 0.2.450 producers cannot drive all current host protocols. Mainline features are identified separately; DSLB v6 and catalog
name v3 alone do not guarantee a compatible compiler/runtime pair.

| Component / baseline | Return support |
|---|---|
| Published `@lmctl-ai/lmctl@0.2.444` | Compile-only blocks; no `$return` lowering or executing-block API |
| C++ `aaa9088`, lmok `f13cc8f7` mainline | Invocation sink and terminal frame adopted (slices 1 and 8) |
| Compiler source `aa6fecb5` (slices 3 and 5) | `$return` lowering and reverse-template extraction landed; see [host contract](spec/host-protocol.md#return-sink-and-frame-contract) |
| Cross-port sink adoption (slice 2) | Landed in all six runtimes; eight separate samples plus the bundled JS host emit the frame |
| Executing blocks, `load_schema`, `out=` (slice 4) | Landed in mono main (`0bc80277`); not in released 0.2.444; needs a frame-emitting host (C++ SDK main: yes, verified; samples: adopted) |

The [standard catalog](spec/std.md) names the 181-signature release and 206-signature
C++ main catalogs and records their differing byte pins. The grammar includes mainline
return writes; the release compiler differential covers the shared baseline only.

The S3 grammar differential gate is in this shared specification repository at
[`tests/grammar/tree_sitter_differential.py`](tests/grammar/README.md), not in either
grammar repo. This keeps the two grammar pins and the npm compiler oracle together.
It checks both Tree-sitter grammars against `@lmctl-ai/lmctl@0.2.448` and publishes
only the public corpus in Actions. `DIVERGENCES.md` records the release/mainline and
syntax-versus-checker boundaries; it does not turn grammar rejections of compiler-
accepted source into accepted differences.

## CI and local verification

[CI instructions](scripts/ci/README.md) describe private npm compiler installation,
local checks and selecting a newer version or tag. Pushes to main, pull requests
and manual runs use GitHub-hosted runners with Node 24; no global lmctl is needed.
The selector is workflow input compiler_version, then LMCODE_COMPILER_VERSION,
then scripts/ci/compiler-version (0.2.456).

CI compiles the documented language examples, parses the reference corpora with
the formal and Tree-sitter grammars, checks generated standard signatures, and runs
failing controls. The local S3 mode also includes tracked mono and skills-scripts
sources; public Actions cannot read those private repositories, so their text is
never copied into this repo.
The separate cross-runtime workflow snapshots runtime/sample main revisions and
one resolved compiler version for six runtimes across five native platforms (30 cells).
JavaScript uses npm ci and its bundled sample; it has no separate sample repository.
It retains the existing C++ corpus home, refreshes disposable samples and reports
incompatibilities without skipping them. Publication is not part of these workflows.

## Historical literal names

The documentation calls the language lmcode. `--lmcode`, `--lmcode-schema` and `--lmcode-signatures` are current host flag literals; `DSLB` is the bytecode magic and `DSLB v6` is the current format name; `.dslb` is the current bytecode filename extension; `_dsl_` is the historical block spelling; `dsl.schema` is the current schema JSON key. Other code-formatted API names, paths, manifest names and diagnostic text retain their current literal spellings.
