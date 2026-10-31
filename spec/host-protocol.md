# Host CLI protocol

Status: current for the flag, result-record and exit-code surface. The terminal return frame
(`LMCODE_RETURN_BEGIN/END`) at the end of this document is **planned, not implemented** — no
shipped host or compiler emits or consumes it.

A host is a native program that loads DSLB bytecode and runs it. The compiler never runs programs;
the host never compiles them. They meet twice: at compile time the host prints its schema (the
R42 query), and at run time the host executes the bytecode file it is handed and reports on stdout
with one JSON record per program.

Normative sources:

- Host flag standard and schema query: `lmscript/durable-memory/requirements/dsl-bytecode.md`
  R42/R45; the compiler side is `lmscript/lmscript.ts` `queryHostSchema` (see
  `spec/schema.md` §"Where the compiler gets the schema").
- Result-record and exit-code convention (S0′, R26):
  `lmscript/durable-memory/design/dsl-language.md` §8; the SDK helpers are
  `lmcode-cpp/include/dslvm.hpp` (`report_ok`, `report_error`, `report_app_failure`).
- Reference host: `lmcode-cpp-sample/src/main.cpp`; a larger multi-command host:
  `lmok/cpp/main.cpp`. The end-to-end contract is pinned by `lmcode-cpp/sample-suite/CONTRACT.md`
  (see `spec/conformance.md`).
- Loader error codes and located run errors: `spec/bytecode.md`.
- Planned return frame: the 2026-10-30 consensus design
  `lmcode-return-and-reverse-templates-consensus.md` (§"Wire contract", §"Return semantics").

## Flags

Every lmcode host CLI offers these flags. A host with several schemas exposes one subcommand per
schema and every DSL flag sits after it: `lmor cpsat --dsl F`, `lmor cpsat --dsl-schema --json`
(R42). stdout is the protocol channel and is written as LF bytes on every platform (the sample
hosts set `_O_BINARY` on Windows).

| Invocation | Behavior | Exit |
|---|---|---|
| `HOST --dsl FILE [FILE …]` | Load each bytecode file against the embedded schema and registry, then run it. One result record per program (below); a failing program ends the run. | 0, 3 or 4 |
| `HOST --dsl-schema --json` | Print the exact embedded `dsl.schema` JSON bytes and nothing else. This output is what the compiler compiles against and hashes. | 0 |
| `HOST --dsl-schema` | A human-readable summary. The form is host-chosen: lmok prints its registry's canonical signature list; `lmcode-cpp-sample` prints the same exact schema bytes as `--json`. | 0 |
| `HOST --dsl-signatures` | Print the registry's canonical signatures, one per line, sorted: `context NAME: Type`, `fn NAME(T1, T2) -> R`, `method Type.name(T1) -> R`. Interfaces are never listed (a registry never implements one, R48). This is the drift check against `lmscript --dsl-signatures SCHEMA`. | 0 |
| `HOST --version` | Print the release version as the first stdout line with exactly one `MAJOR.MINOR.PATCH[-PRE][+BUILD]` token (`lmcode-cpp-sample 0.2.0`); `v0.3.0` and `0.3.0` are the same version, a `+BUILD` suffix is ignored (R45). Required of any host installed with `install=…@latest`, recommended for every host. | 0 |
| `HOST --notices` | Print the embedded third-party license notices (lmok ships `notices_embedded.hpp` for this). Observed in lmok; **not** part of the R42 flag standard and absent from the sample hosts — treat it as a convention for published binaries, not a conformance requirement. | 0 |

Anything else — no arguments, unknown options, missing values — is a usage error: exit 2 with the
JSON record `{"ok": false, "phase": "cli", "code": "CLI_USAGE", "message": "usage: …"}` on stdout
in the SDK-helper style (the sample contract pins that exact shape; lmok prints its longer usage
text on stderr for its non-DSL subcommands instead — usage handling is host-defined once the
result-record rule is met for `--dsl` runs).

## The result record (one JSON line per program)

Every `--dsl` execution prints, on stdout:

1. the program's **trace lines** first — whatever the host's output functions write (the sample
   hosts' `print(string)`, lmok's `println`), one line each, in execution order; then
2. exactly one **result record** line plus LF, as the last line:

```json
{"ok": true, "result": {"balance": 750, "entries": 3, "note": "", "entries_called": 4}}
{"ok": false, "phase": "load", "code": "LOAD_SCHEMA_MISMATCH", "message": "sample schema mismatch"}
{"ok": false, "phase": "run", "code": "RUN_ERROR", "message": "dsl line 4:2: int division by zero", "line": 4, "column": 2}
{"ok": false, "phase": "app", "code": "APP_FAIL", "message": "ledger: negative balance"}
```

- `{"ok": true, "result": …}` — the program loaded and ran; `result` is host JSON (the sample
  hosts compose the object shown; `report_ok()` with no argument writes `"result": null`).
- `{"ok": false, "phase": "load"|"run"|"app", "code": …, "message": …}` — `phase` is where the
  failure happened; `code` is one of the SDK codes `LOAD_BAD_BYTECODE`, `LOAD_SCHEMA_MISMATCH`,
  `LOAD_UNBOUND` (load), `RUN_ERROR`, `RUN_HOST` (run) or `APP_FAIL` (app). A located run error
  (S5) adds numeric `"line"` and, when known, `"column"` fields, and its `message` carries the
  `dsl line N:C: ` prefix. Load errors have no location.
- The record is the *last* stdout line. The sample suite compares exact stdout bytes and requires
  an empty stderr for every case (`spec/conformance.md`).
- With several `--dsl` files the host prints one record per program, in argument order, and stops
  at the first failure (lmok's behavior; the sample hosts take exactly one file).
- The host's own application validation is distinct from a VM failure and runs after it: the
  sample hosts report a negative final ledger balance as `phase: "app"`, `APP_FAIL`, exit 4.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success (`--dsl` run completed; every inspection flag answered). |
| 2 | The caller's fault: a compile error in lmscript (the compiler owns this code; hosts never see the source), or a host CLI usage error (`phase` `cli`, `CLI_USAGE`). |
| 3 | Host load or run failure: the record's `phase` is `load` or `run`. |
| 4 | Application failure after VM success: `phase` `app`, `APP_FAIL`. |

The convention is the SDK's (`report_error` returns 4 for `APP_FAIL`, 3 otherwise; `report_ok`
returns 0) and the R26 allocation: 2 compile / 3 host / 4 application. `spec/bytecode.md` §"Loader
error codes and result convention" has the code taxonomy.

## Planned, not current: the `LMCODE_RETURN_BEGIN/END` terminal frame

The 2026-10-30 consensus design (`lmcode-return-and-reverse-templates-consensus.md`) adds a way
for a program to hand a JSON **value** back to lmscript (`$return` writes, lowered to new
`lmcode_return_*` standard imports). None of this is implemented; the block value stays opaque and
the chunk returns nothing (`spec/language.md` §2). The wire part, quoted here so hosts can plan
for it:

- On success a CLI prints its traces and `{"ok", "result"}` record as today, then exactly
  `LMCODE_RETURN_BEGIN\n<compact JSON value>\nLMCODE_RETURN_END\n`. The frame is **always**
  printed on success (a `null` payload when the program wrote nothing) and is **terminal**:
  `END` plus LF is the final stdout, marker lines are reserved in preceding stdout, and escaped
  marker/newline text inside JSON strings is ordinary data.
- The frame is emitted only after host dispatch *and* application validation succeed. Exit 2/3/4
  are unchanged; any nonzero exit or signal defeats the frame, and a failed invocation emits none.
  A CLI may process multiple programs with one frame each; lmscript invokes exactly one and
  requires exactly one.
- Numeric contract: mathematical integers must fit ±9007199254740991 (integral float values and
  exponent-form tokens included); fractional finite values are binary64. Float serialization uses
  the **shortest round-trip** representation — explicitly *not* the host's `str(float)`/`%.15g`
  machinery (`0.1+0.2` prints `0.30000000000000004`, never `0.3`). The consumer validates raw
  number tokens before JSON decoding (a plain `JSON.parse` that collapses `9007199254740992` and
  `9007199254740993` is a protocol bug), rejects nonfinite and unsafe-integral values, and treats
  underflow of a nonzero token to zero as an error. Duplicate object keys in protocol JSON are
  invalid.
- The same consensus retires `savedsl`, `dsl_cli` and the `_dsl_` spelling at the eventual
  cutover; until then nothing in this section changes any current behavior.
