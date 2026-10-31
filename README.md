# lmcode

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

CI also extracts and compiles the seven current code examples in
[the language reference](spec/language.md), with an explicit declaration schema
for the illustrated host domain. The keyword inventory is data, not a test.
A corrupted return-type control proves that changes to the document are checked.
These are compile-only checks; the native sample matrix verifies host execution.
