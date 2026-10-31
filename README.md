# lmcode

Syntax tooling: [tree-sitter-lmcode status, pins and integration boundaries](spec/tree-sitter-lmcode.md).

lmcode is a small, strongly typed language that compiles to **DSLB v6** bytecode and runs
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
  pitfalls from the five existing ports), [spec/bytecode.md](spec/bytecode.md) (DSLB v6 byte
  layout, opcodes, verifier rules), [spec/conformance.md](spec/conformance.md) (the vectors).

## Quickstart

```sh
npm install --prefix /tmp/lmcode-tools @lmctl-ai/lmctl@0.2.444   # private install, not global
export PATH="/tmp/lmcode-tools/node_modules/.bin:$PATH"
git clone https://github.com/lmctl-ai/lmcode-cpp-sample
cd lmcode-cpp-sample && ./build.sh            # builds the reference host
cat > /tmp/hello.lms <<'EOF'
p = _lmcode_ cli="lmcode-cpp-sample";
print("hello from lmcode");
end _lmcode_
savedsl(p, "/tmp/hello.dslb");
EOF
export PATH="$PWD/build:$PATH"
lmscript /tmp/hello.lms && ./build/lmcode-cpp-sample --dsl /tmp/hello.dslb
# prints: hello from lmcode
# then:   {"ok": true, "result": {"balance": 0, "entries": 0, "note": "", "entries_called": 0}}
```

The full walkthrough with pinned outputs is [guides/writing-lmcode.md](guides/writing-lmcode.md).

## Documentation map

| Document | Contents |
|---|---|
| [spec/language.md](spec/language.md) | Language reference: lexis, types, statements, functions/inlining, `@NAME`/`implements` rule entries (R47–R49), errors, compile-time vs run-time |
| [spec/grammar.md](spec/grammar.md) + [spec/grammar.ebnf](spec/grammar.ebnf) | Formal grammar (W3C EBNF), machine-checked against the real compiler by [tests/grammar](tests/grammar/README.md) |
| [spec/schema.md](spec/schema.md) | Host schema format: types, functions, context, enums, conversions, operators, interfaces, the SHA-256 hash binding |
| [spec/bytecode.md](spec/bytecode.md) | DSLB v6 layout section by section, opcode table with widths and stack effects, entries section, verifier rules, loader errors |
| [spec/std.md](spec/std.md) + [spec/std-signatures.md](spec/std-signatures.md) | The standard catalog: ownership, byte-pinned locks, version history, and the generated 182-signature list |
| [spec/host-protocol.md](spec/host-protocol.md) | Host CLI flags, result/diagnostic records, exit codes, the planned `LMCODE_RETURN` frame |
| [spec/conformance.md](spec/conformance.md) | The conformance corpus and sample-suite: `.expect` protocols, vector counts, how to run them |
| [guides/implementing-a-runtime.md](guides/implementing-a-runtime.md) | Runtime porting guide: milestones, 15 cited pitfalls, per-language file map |
| [guides/writing-lmcode.md](guides/writing-lmcode.md) | Author tutorial with verified examples |
| [CONFORMANCE-AUDIT.md](CONFORMANCE-AUDIT.md) | Where the canonical corpora live and what a green run proves |

## The lmcode repository family

| Repo | Role | Status (2026-10-31) |
|---|---|---|
| [lmctl-ai/lmcode-cpp](https://github.com/lmctl-ai/lmcode-cpp) | Reference runtime (C++17, header-only `include/dslvm.hpp`); owns the canonical std schema and the conformance/sample corpora | Reference; current |
| [lmctl-ai/lmcode-rust](https://github.com/lmctl-ai/lmcode-rust) | Rust runtime (`dslvm` crate) | Experimental; passes the shared vectors |
| [lmctl-ai/lmcode-go](https://github.com/lmctl-ai/lmcode-go) | Go runtime (std-lib only) | Experimental; passes the shared vectors |
| [lmctl-ai/lmcode-java](https://github.com/lmctl-ai/lmcode-java) | Java 21 runtime (JVM + native-image) | Experimental; passes the shared vectors |
| [lmctl-ai/lmcode-csharp](https://github.com/lmctl-ai/lmcode-csharp) | .NET 8 runtime (NativeAOT supported) | Experimental; passes the shared vectors |
| lmcode-{cpp,c,go,rust,csharp,java,kotlin,scala}-sample | Teaching hosts: one shop/ledger domain each, sharing the pinned sample-suite | Green per port; synced by lock files |
| [lmctl-ai/lmok](https://github.com/lmctl-ai/lmok) | Production host: tree-sitter lint tool using lmcode rule entries | Active; v6 entries drive `lmok check` |

The compiler lives in the lmctl monorepo (`lmscript/dsl.ts`) and ships with
`@lmctl-ai/lmctl`; it is not part of this repository.

## Current vs planned

Everything in `spec/` describes the language as implemented by the published compiler
(0.2.444, DSLB v6), except clearly marked **planned** boxes: the block yielding the
program's return value, `load_schema`, `$return` and the `LMCODE_RETURN_BEGIN/END` frame,
and reverse templates are mid-design/implementation and are documented as planned until
they land on the compiler's main branch.

## CI and local verification

Pushes to main and pull requests run the suite on GitHub-hosted runners. No
self-hosted machine or globally installed lmctl is required. CI downloads
@lmctl-ai/lmctl with Node 24 into a fresh temporary npm prefix.

The compiler selector is the manual workflow input compiler_version, then the
repository variable LMCODE_COMPILER_VERSION, then scripts/ci/compiler-version
(currently 0.2.444, the published v6 baseline). To test a newer release or tag,
run the ci workflow manually and set compiler_version, for example staging.
A compiler that cannot satisfy the suite fails visibly; planned language
features must not be claimed as passing through skipped checks.

Run the same checks locally with Node 24, npm and Python 3:

```sh
source scripts/ci/install-compiler.sh
bash scripts/ci/run-suite.sh
```

To select a different published compiler:

```sh
COMPILER_VERSION=staging source scripts/ci/install-compiler.sh
bash scripts/ci/run-suite.sh
```

The cross-runtime workflow resolves a selected npm tag once to an exact version
and snapshots main revisions of the five runtime repos,
their matching sample repos, and lmcode-cpp's reference vectors before starting
its 25 native jobs (Linux x64/arm64, macOS x64/arm64, Windows x64). It runs runtime
tests, sends the same reference core/stdlib vectors to each runner, refreshes
samples with their own sync scripts, and recompiles/runs their sample suites.
Go uses a local module replacement in the disposable sample checkout so it
exercises the selected runtime revision. Refreshed lockfiles stay in the
disposable checkout; nothing is committed or pushed upstream.
The vectors and sample suite remain in lmcode-cpp; this workflow does not move
the canonical source or silently skip catalog incompatibilities.

For a single cross-runtime run after installing the compiler, supply disposable
checkouts and the language name (cpp, rust, go, java or csharp):

```sh
LANGUAGE=cpp RUNTIME_DIR=/path/to/lmcode-cpp \
REFERENCE_CPP_DIR=/path/to/reference-lmcode-cpp \
SAMPLE_DIR=/path/to/lmcode-cpp-sample bash scripts/ci/cross-runtime.sh
```

The [executable v6 example](scripts/ci/examples/v6.lms) and its adjacent schema
are compiled in CI, including a deliberately mistyped variant that must fail.
This tests the published compile-only form, not the planned block-return syntax.
The generated file must carry the DSLB v6 header; a v5-output control also fails.

The grammar of the language itself is specified formally in
[spec/grammar.ebnf](spec/grammar.ebnf) (W3C EBNF; the subset is documented in its header),
with prose and the static-semantics boundary in [spec/grammar.md](spec/grammar.md). The
grammar is normative and machine-checked: `tests/grammar/check_corpus.py` translates it to
a parser generator grammar (Lark) and parses every lmcode body in the conformance vectors,
stdlib vectors, sample suite and lmok rules with zero failures, and
`tests/grammar/mutate_diff.py` differentially tests accept/reject against the real compiler
on a token-mutation corpus. The [grammar workflow](.github/workflows/grammar.yml) runs both
in CI on changes to the grammar or its checker. The grammar is LALR(1)-clean (Lark strict
mode), so it doubles as the cross-check source for the tree-sitter grammar.

CI also extracts and compiles the seven current code examples in
[the language reference](spec/language.md), with an explicit declaration schema
for the illustrated host domain. The keyword inventory is data, not a test.
A corrupted return-type control proves that changes to the document are checked.
These are compile-only checks; the native sample matrix verifies host execution.
