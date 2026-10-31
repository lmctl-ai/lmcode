# Host CLI protocol

Status: the host option family is current as of 2026-10-31. Compiler mono main
`7a1829a1` and the five SDKs/eight samples use the renamed flags below with no
aliases or fallback. DSLB magic and internal `.dslb` filenames are unchanged.
Use a compiler built from that mainline or a later release containing the rename;
older published compilers such as 0.2.444 cannot discover or execute these hosts.
The five SDKs provide invocation sinks and the eight samples emit terminal frames.
`load_schema` and executing blocks landed at mono `0bc80277`.

A host is a native program that loads lmcode bytecode (`DSLB` magic) and runs it. The compiler never runs programs;
the host never compiles them. They meet twice: at compile time the host prints its schema (the
R42 query), and at run time the host executes the bytecode file it is handed and reports on stdout
with a host-defined sequence of trace, result, and (when supported) return-frame records.

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
- Return sink/frame: the normative contract is included below. Hosts retaining the legacy
  result-only contract must identify that compatibility mode.

## Flags

The previous flag family is rejected as unknown input before file loading or
network effects. There are no compatibility aliases.

Every lmcode host CLI offers these flags. A host with several schemas exposes one subcommand per
schema and every lmcode flag sits after it: `lmor cpsat --lmcode F`, `lmor cpsat --lmcode-schema --json`
(R42). stdout is the protocol channel and is written as LF bytes on every platform (the sample
hosts set `_O_BINARY` on Windows).

| Invocation | Behavior | Exit |
|---|---|---|
| `HOST --lmcode FILE [FILE …]` | Host-specific arity applies. The C++ sample accepts exactly one file. lmok validates and loads all supplied files before running the first, then stops at the first failure. | 0, 3 or 4 |
| `HOST --lmcode-schema --json` | Print the exact embedded `dsl.schema` JSON bytes and nothing else. This output is what the compiler compiles against and hashes. | 0 |
| `HOST --lmcode-schema` | A human-readable summary. The form is host-chosen: lmok prints its registry's canonical signature list; `lmcode-cpp-sample` prints the same exact schema bytes as `--json`. | 0 |
| `HOST --lmcode-signatures` | Print the registry's canonical signatures, one per line, sorted: `context NAME: Type`, `fn NAME(T1, T2) -> R`, `method Type.name(T1) -> R`. Interfaces are never listed (a registry never implements one, R48). This is the drift check against `lmscript --lmcode-signatures SCHEMA`. | 0 |
| `HOST --version` | Print the release version as the first stdout line with exactly one `MAJOR.MINOR.PATCH[-PRE][+BUILD]` token (`lmcode-cpp-sample 0.2.0`); `v0.3.0` and `0.3.0` are the same version, a `+BUILD` suffix is ignored (R45). Required of any host installed with `install=…@latest`, recommended for every host. | 0 |
| `HOST --notices` | Print the embedded third-party license notices (lmok ships `notices_embedded.hpp` for this). Observed in lmok; **not** part of the R42 flag standard and absent from the sample hosts — treat it as a convention for published binaries, not a conformance requirement. | 0 |

Anything else — no arguments, unknown options, missing values — is a usage error: exit 2 with the
JSON record `{"ok": false, "phase": "cli", "code": "CLI_USAGE", "message": "usage: …"}` on stdout
in the SDK-helper style where that host uses the helper. lmok prints its longer usage text on
stderr for missing/invalid `--lmcode` arguments and for its non-lmcode subcommands; this is a host CLI
usage path, not a result-record claim.

## The result record (one JSON line per program)

Every `--lmcode` execution prints, on stdout, a result record after its trace lines. Return-capable
hosts append the terminal frame described below, so that frame—not the result record—is the final
stdout line:

1. the program's **trace lines** first — whatever the host's output functions write (the sample
   hosts' `print(string)`, lmok's `println`), one line each, in execution order; then
2. exactly one **result record** line plus LF (the final protocol line for legacy hosts):

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
- The record is the last line before any return frame. Legacy hosts without return support make it
  the last stdout line. The sample suite compares exact stdout bytes and requires an empty stderr
  for every case (`spec/conformance.md`).
- With several `--lmcode` files, a batching host must document ordering and preloading. lmok loads
  all files before running the first and then stops at the first failure; the sample hosts accept
  exactly one file. A missing `--lmcode` value is a CLI usage error (lmok prints usage on stderr).
- The host's own application validation is distinct from a VM failure and runs after it: the
  sample hosts report a negative final ledger balance as `phase: "app"`, `APP_FAIL`, exit 4.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success (`--lmcode` run completed; every inspection flag answered). |
| 2 | The caller's fault: a compile error in lmscript (the compiler owns this code; hosts never see the source), or a host CLI usage error (`phase` `cli`, `CLI_USAGE`). |
| 3 | Host load or run failure: the record's `phase` is `load` or `run`. |
| 4 | Application failure after VM success: `phase` `app`, `APP_FAIL`. |

The convention is the SDK's (`report_error` returns 4 for `APP_FAIL`, 3 otherwise; `report_ok`
returns 0) and the R26 allocation: 2 compile / 3 host / 4 application. `spec/bytecode.md` §"Loader
error codes and result convention" has the code taxonomy.

## Return sink and frame contract

The compiler main line lowers `$return` writes to `lmcode_return_*` imports, and the C++/lmok hosts
provide the invocation sink and terminal frame. The published 0.2.444 compiler lacks `$return` lowering, but frame behavior is selected by
the host: lmok emits it even for programs compiled with that release. The C++ sample at
`be54c73` retains legacy result-only behavior. Block execution and `load_schema`
are landed in mono main at `0bc80277` (2026-10-31); they are absent from the released 0.2.444 compiler, and execution additionally needs a host that emits the terminal frame (the C++ SDK main does — verified end to end against `0bc80277` in the wp40 review; the samples do not yet, slice 6).

- On success a return-capable CLI prints its traces and `{"ok", "result"}` record as today, then exactly
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
- Sink lifecycle is per logical invocation: bind the sink and reset it once before the body, retain
  the same root through the selected entry calls, then reset it before the next program. A body
  and its entries therefore share ownership; an entry does not receive a fresh root. Failed
  invocations emit no frame and leave no stale value for the next invocation.
- `lmcode_return_set(value)` owns and replaces the root; `lmcode_return_null()` resets it to null. Field writes
  (`lmcode_return_put`/`put_null`) require the current root to be null or an object; attempting a
  field write after a scalar or list root is an error. A typed map is copied as a JSON object
  and accepts subsequent field writes. Object keys are UTF-8 strings; writing
  an existing key replaces its value without changing insertion order, while a new key appends.
  A root field value is copied into the sink, so later VM/arena mutation cannot change the frame.
- The lmcode-facing overloads accept null, bool, string, int, float, `Json`, and the homogeneous
  `StrList`/`IntList`/`FloatList`/`StrMap`/`IntMap`/`FloatMap` values registered by the host.
  `Json` may contain recursive JSON arrays/objects; lmcode list/map values remain homogeneous and
  may be empty when constructed with a typed constructor. Mixed/nested structures use `Json`;
  unsupported opaque objects are rejected by the type checker. Numeric validation follows the rules above. Reverse-template extraction uses the same
  sink ownership and failure rules.
- `savedsl`, `dsl_cli`, and the `_dsl_` spelling remain compatibility names until the eventual
  cutover; this section does not claim block execution or schema loading.
