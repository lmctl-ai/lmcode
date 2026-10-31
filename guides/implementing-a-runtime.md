# Implementing an lmcode runtime — milestones, pitfalls, and the five ports

Status: current. This guide is for a developer implementing a new lmcode bytecode runtime in
another language (the `lmcode-<lang>` pattern: C++, Rust, Go, Java and C# exist today). It does
not restate the format or protocol; it orders the work, names the gate that proves each step, and
collects the mistakes the five existing ports already made so the sixth does not repeat them.

Normative sources (read these first; this guide cites, not copies):

- Bytecode format, instruction set, verifier rules and error texts: `spec/bytecode.md`.
- The two test corpora and the `.expect` protocols: `spec/conformance.md`.
- Host CLI flags, result records and exit codes: `spec/host-protocol.md`.
- Schema format and the SHA-256 binding: `spec/schema.md`.
- The standard catalog, its ownership and `std.lock`: `spec/std.md`.
- Reference implementation: `lmcode-cpp` (`include/dslvm.hpp` is canonical for behavior).

Conventions below distinguish two core sets. The compiler-side C01 generator at source `aa6fecb5` writes 82
vectors, including 9 return vectors. The expanded canonical runtime corpus in `lmcode-cpp` revision
`aaa9088a542d43daf81aefb9b024fbb971825f3f` contains 406 vectors; its separate return gate has 9
fixtures. The stdlib corpus has 268 vectors. The sample suite has 114 cases (77 exit 0, 36 exit 3,
one exit 4). Counts are pinned by each manifest and must always be reported with its corpus revision;
do not replace the 406-vector runtime count with the 82-vector C01 count.

## Milestones, in order

Each milestone says what "done" means and which gate proves it. The order is deliberate: later
gates assume earlier ones, and every port landed in roughly this sequence (see the per-repo
durable-memory files cited in the last section).

### 1. Loader: header, sections, entries

Parse the file layout of `spec/bytecode.md` §"File layout": the 38-byte header (magic `DSLB`,
version 6, schema SHA-256), constants, imports, context, body region, then the v6 entry table.
Big-endian fixed widths, no padding; strings are length-prefixed raw bytes. Recompute the schema
SHA-256 over the bytes the host supplies and refuse a mismatch (`LOAD_SCHEMA_MISMATCH`). Enforce
the section order, refuse trailing bytes, and never allocate from an untrusted count before the
bytes are read (pitfall P1).

Done: valid v6 files load; every malformed file fails with one of the pinned load messages and
code `LOAD_BAD_BYTECODE` / `LOAD_SCHEMA_MISMATCH` / `LOAD_UNBOUND` — nothing executes after a
failed load.

Gate: the `load_error` core vectors (C01 requires ≥ 8 of them; today they include truncation,
trailing bytes, v5-refused, huge counts, duplicate entry names, hidden-local stores) plus the
sample-suite mutation cases `090`–`093`.

### 2. Structural verifier

Implement `verify_region` (per region: opcode decoding, index ranges, call arity, jump direction
and targets, loop pairing, hidden-slot protection, HALT placement) and `verify_stack` (the
dataflow depth pass) exactly as `spec/bytecode.md` §"Loader verification" enumerates them, in that
order — hosts dispatching on the *first* error observe the order. Entries are verified with the
same passes plus the entry-specific checks (parameter locals, HALT depth; milestone 6).

Done: the verifier rejects everything the C++ verifier rejects, with messages that contain the
pinned substrings. Do not "improve" the rules: the five-way fuzz corpus of 2,753 mutated files
found zero legitimate disagreement after the WP11 fixes (see P8, P9), so any divergence from
`dslvm.hpp` is a port bug until the spec says otherwise.

Gate: all `load_error` core vectors pass; the error text contains the vector's substring.

### 3. The stack VM

Typed opcodes: type selection is the compiler's decision, baked into the opcode (`ADD_I` vs
`ADD_F`); the VM still checks value kinds defensively and fails with the pinned `RUN_ERROR`
messages (`int operator applied to A and B`, …) because bytecode is verified, not trusted
(`lmcode-cpp/durable-memory/02-architecture-and-decisions.md`). Semantics that bite: two's
complement wrapping with no overflow trap (P4), truncation-toward-zero division, `%.15g` float
formatting in `str(float)` and traces (P2), byte strings (P5), located errors via the line table
(`dsl line N:C: ` prefix, column 0 means absent).

Done: the `trace` and `runtime_error`/`runtime_error_at` core vectors pass, including the
located-error cases and the mutated empty-line-table vector.

Gate: 82/82 compiler-generated C01 vectors once entries (milestone 6) are in, plus the expanded
406-vector canonical runtime corpus and the separate 9-fixture return gate; before entries land,
run the non-entry subset. Return sink/frame behavior is landed for slices 1, 3, 5 and 8 (slice 2 is
in progress); block execution and `load_schema` (slice 4) are landed in mono main at `0bc80277` (2026-10-31); they are absent from the released 0.2.444 compiler, and execution additionally needs a host that emits the terminal frame (the C++ SDK main does — verified end to end against `0bc80277` in the wp40 review; the samples do not yet, slice 6).

### 4. Standard library registration

Copy the catalog bytes from the named `lmcode-cpp` revision and pin them in a `std.lock`
recording `schema=`, `version=` and `sha256=` (`spec/std.md` §"Ownership and drift pinning").
Compare the compiler pin separately: current compiler/C++ serialization differs even though
the signature sets match. Do not infer compatibility from the shared v3 name. Add
a `scripts/sync-std.sh`-style script that copies from the canonical repo and verifies the digest.
Register the catalog by default in the registry constructor and provide the explicit opt-out —
the five existing spellings are in the per-language table below; a new runtime needs its own pair
(e.g. `Registry()` / `Registry(StdMode::Disabled)`). Registration is idempotent; testing helpers
(`print`, `assert_close`) are **not** std and stay host-registered. Collection handles live in a
per-run arena with a 65,536-object budget (P7). One catalog group per milestone-sized commit;
`template_render` is registered by all five ports at the named revisions in
[std.md](../spec/std.md#template_render-status); verify a new port independently.

Done: `--dsl-signatures`-equivalent output matches `lmscript --dsl-signatures` on the merged
schema; the std.lock digest verifies.

Gate: 268/268 stdlib vectors, including the `runtime_error_exact` (full message after stripping
the `dsl line N:C: ` prefix) and `runtime_error_file` kinds.

### 5. Host Registry

The registry binds canonical signature text (`fn NAME(T1, T2) -> R`, `method Type.name(T1) -> R`)
to host callbacks; overloads are distinct signatures, duplicate parameter tuples are refused.
Imports resolve against the registry **at load time** by full signature text, so a missing or
differently-typed declaration is `LOAD_UNBOUND` with the pinned message (including the
` (the host declares ...)` suffix when the name exists with other signatures). Bound callbacks
are captured at load and the registry must outlive the loaded program and stay unchanged while it
runs (`lmcode-cpp/durable-memory/02-architecture-and-decisions.md`;
`lmcode-csharp/durable-memory/02-decisions.md`).

Done: a program importing a declared-but-wrong signature fails at load, not at call.

Gate: the `schema-extra.json` unbound-import core vector; the sample suite's `protocol.py`, which
derives the expected signature list independently from the schema so a missing **or extra**
registration fails even when no program calls it.

### 6. entries() and call() (R49)

Expose the entry table as immutable source-order metadata (`entries()`) and `call(entry, …)`,
which stores arguments into parameter locals `0..nparams-1` and runs the entry's region on the
same execute path as the body — fresh locals per call, no prior `run()` required, no runtime call
stack (P11 for the HALT-depth rule). Wrong arity is `RUN_HOST` with exactly
`call entry 'NAME' expects N argument(s); found M`; a bad index is
`call entry index I out of range (N entries)`.

Done: call-before-run works, a body error does not poison a later entry call, and entry failures
carry entry line-table locations.

Gate: the `entries`, `call`, `call_error` and `call_error_at` core vectors (C01 minimums:
entries ≥ 1, call ≥ 8, call_error ≥ 1, call_error_at ≥ 1; every `call*` vector runs the body
first, and `call-body-trace` pins it).

### 7. The CLI protocol

Implement the flags and result records of `spec/host-protocol.md`: `--dsl FILE`, `--dsl-schema
[--json]` (only the `--json` form promises the exact embedded schema bytes; the bare summary is
host-chosen), `--dsl-signatures` (sorted canonical signatures,
never interfaces), `--version`; usage errors exit 2 (the sample uses `CLI_USAGE` JSON; lmok
uses stderr usage). Legacy hosts finish with the result record; return-capable hosts append
the terminal return frame after successful dispatch and application validation. Exit codes are 0/2/3/4. stdout is LF bytes on every
platform (the C++ sample sets `_O_BINARY` on Windows).

Done: trace lines then a result record and, for return-capable hosts, the success frame;
failed invocations have no frame. The sample protocol requires empty stderr and exits per the table.

Gate: the sample suite's `protocol.py` plus its CLI discovery checks — a port that only runs
bytecode cases is not conforming (`spec/conformance.md` §"Running the suite").

### 8. Conformance runner

Port `lmcode-cpp/conformance/run.cpp`: the manifest's host stub (contexts `t`, `root`, `xs`; the
stub host functions), the `.expect` line grammars, and the runner-side argument conversion (P10).
Print `ok - NAME (kind)` and `PASS n/n vectors`. Support `LMCODE_TRACE=1` trace dumps so
`scripts/diff-stdlib.py`-style byte comparison works against other ports.

Done: byte-level agreement with the `.expect` semantics — not with C++ internals — including the
`~ ` approximate float lines (tolerance `1e-12 * max(|expected|, 1e-300)`, last token finite;
`spec/conformance.md` §"The .expect protocols").

Gate: **406/406 canonical core and 268/268 stdlib vectors**, plus the 9 return-vectors fixtures,
run by your own runner from your own repo, with
`vectors.lock`-style integrity pins on the copied corpus.

### 9. A sample host against the sample-suite

Port the canonical shop host (`lmcode-cpp-sample/src/main.cpp`, `shop.cpp`) as
`lmcode-<lang>-sample`: contexts `shop` and `ledger`, int64-cents money, entry dispatch per
`CONTRACT.md` (every `@item` entry once per item, every `@total` once, others never), the
`entries_called` result field, APP_FAIL on a negative ledger, the canonical load-message rewrites
(`invalid sample bytecode`, `sample schema mismatch`, `sample import mismatch`).

Done: exact stdout bytes and exit code per case, empty stderr, fresh `SAMPLE_TMP` per case.

Gate: `python3 sample-suite/run-suite.py /path/to/lmcode-<lang>-sample` passes all 114 cases,
which includes manifest hash validation, `check-compile-errors.py` and `protocol.py` before any
case runs.

## Pitfalls from the five ports

Each pitfall is real: it was either found by the WP11 fuzz/differential review
(`reports/wp11-differential-review-T1Fable.md`, fixed by `reports/wp11fix-T1Fable.md`), recorded
in a port's durable-memory, or pinned by a spec divergence note. Citations are repo paths relative
to the named repo.

**P1 — Never allocate from an untrusted count.** Rust's loader did
`Vec::with_capacity(nlines as usize)` from the on-wire count; a `0xFFFFFFFF` line count reserved
51.5 GB and **aborted the process** (`memory allocation of 51539607540 bytes failed`, uncatchable
SIGABRT — a corrupt file killed the whole host). 17 mutants triggered it. The fix was `Vec::new()`
at every reservation site, and the spec now states the rule: a count larger than the remaining
bytes must surface as the truncation error, never as a reservation. New vector
`load-entry-lines-huge` pins it. (reports/wp11-differential-review-T1Fable.md F1;
reports/wp11fix-T1Fable.md; spec/bytecode.md §"Loader verification" item 16.)

**P2 — `%.15g` is the trace format, never a round-trip format.** `str(float)` (F2S), trace lines
and `assert_close` diagnostics use exactly C `%.15g` semantics including `inf`/`-inf`/`nan`/`-0`
spellings; Go re-implements it deterministically as `FormatG15` and Java as
`Formatting.formatG15` (lmcode-go/durable-memory/02-decisions.md;
lmcode-csharp/durable-memory/02-decisions.md; lmcode-cpp/include/dslvm.hpp:326). But `%.15g` does
**not** round-trip: `0.1+0.2` prints `0.3`, a different binary64. Any protocol boundary that must
preserve values — the landed `LMCODE_RETURN_BEGIN/END` frame is the concrete case — requires the
language's shortest-round-trip formatter (C++17 `std::to_chars`, Go `strconv.FormatFloat(v,'g',-1,64)`,
Rust `{:?}`/ryu, Java `Double.toString`; C# `G17` needs a parse-back check, it is not shortest).
Reusing F2S machinery for frame/result text is the WP25 F1 finding.
(reports/wp25-consensus-review-T1Kimi.md F1; spec/host-protocol.md §"Planned, not current".)

**P3 — int64 at the JSON boundary.** VM integers are full int64; JSON tooling in most languages
silently collapses values past 2^53 (`9007199254740992` vs `…93` parse identically under JS
`JSON.parse`). The host-protocol numeric contract requires raw-token validation before JSON
decoding for that reason, and lmcode-java's entry work caught exactly this: "a separate failing
control caught lossy int64 JSON call arguments; only the new argument-reader path requests exact
numbers". (spec/host-protocol.md; reports/wp25-consensus-review-T1Kimi.md F2;
lmcode-java/durable-memory/06-v6-entry-table.md.)

**P4 — Wrapping arithmetic needs explicit guards in most languages.** `INT64_MIN / -1` wraps to
`INT64_MIN`, `INT64_MIN % -1` is 0, negating `INT64_MIN` wraps to itself, and zero divisors are
`RUN_ERROR` (spec/bytecode.md v2 table). In Go the native results already match but the VM guards
them explicitly to make wraparound visible; in C# you must use `unchecked` or .NET throws
`OverflowException`; in Java `long` wraps natively. Get this wrong and the wrapping-power and
`INT64_MIN` stdlib vectors fail. (spec/bytecode.md; lmcode-go/durable-memory/02-decisions.md and
04-gotchas.md; lmcode-csharp/durable-memory/02-decisions.md.)

**P5 — Strings are raw bytes; do not let your language's string type near them.** Lengths,
offsets, slicing, case mapping and trim are all byte operations; NUL and invalid UTF-8 survive
constants, concatenation, equality and callbacks. Concrete traps the ports hit: Go — never
`range` over a VM string (that decodes runes); C# — never round-trip through UTF-16 `string`
(`VmString` owns a defensive byte copy; schema identifiers alone are decoded strict UTF-8);
Rust — `Value::as_str()` validates and reports failure as `RUN_HOST`, `as_bytes()` is the safe
accessor; Java — `VmString` is immutable bytes, `String` only via explicit conversion.
(spec/bytecode.md §"Conventions" and §"Known divergences";
lmcode-cpp/durable-memory/06-stdlib-catalog.md §"Byte-string rule";
lmcode-go/durable-memory/02-decisions.md; lmcode-csharp/durable-memory/02-decisions.md and
04-gotchas.md; lmcode-java/durable-memory/02-api.md.)

**P6 — The UTF-8 validation divergence is recorded, not a license to add checks.** Rust validates
UTF-8 at load for structurally used constants (imports, context names/types, entry metadata):
`WHAT: constant I is not valid UTF-8`. C++ and Go never validate, and the spec records C++/Go
behavior as canonical; the conformance vectors accept Rust's wording via substring matching.
Decide which side your port is on and expect the divergence list to grow a row.
(spec/bytecode.md §"Known divergences between the loaders".)

**P7 — Collection handles die with the run.** Std collections live in a shared per-run arena with
a 65,536-object budget (`"<Type> object limit exceeded (65536)"`, `RUN_HOST`), cleared at the
start and end of every run including exceptional exits; handles from run N must be invalid in run
N+1 and must never cross registries mid-run — overlapping runs on shared state are rejected by a
guard, not "handled". C# models this as context-local `ObjRef` indexes ("the host must not mix
handles between contexts"); C++ invalidates every handle on arena `reset()`, permitted only
between runs. `clear()` empties a collection without freeing its arena slot or invalidating the
receiver. (lmcode-cpp/durable-memory/06-stdlib-catalog.md §"Collection lifetime and native
adapters"; lmcode-go/durable-memory/02-decisions.md;
lmcode-csharp/durable-memory/02-decisions.md; lmcode-java/durable-memory/03-limits.md.)

**P8 — Error texts are pinned; "close enough" fails vectors.** Core vectors substring-match, but
`runtime_error_exact` stdlib vectors pin the **complete** message after stripping only the
`dsl line N:C: ` prefix (collection bounds, missing-key, assertion messages). Known
message-shape drift the spec already tolerates between C++ and Rust — entry HALT depth
(`HALT leaves N values` vs `…, interface returns T`), `HALT inside loop` vs
`HALT at offset N is inside loop`, the loop-boundary parenthetical, the FOR_RANGE exit message,
and the nparams-vs-interface check order — is enumerated in the spec; anything beyond that list is
drift you introduced. When the same file is invalid in two ways, ports may report different first
errors only where the spec says so. (spec/conformance.md §"The stdlib catalog vectors";
spec/bytecode.md §"Known divergences between the loaders";
reports/wp11-differential-review-T1Fable.md F4.)

**P9 — The WP11 loader rulings are load-bearing for new ports.** Three behaviors were decided by
fuzzing and are now spec: (a) duplicate entry names are refused (`duplicate entry name 'NAME'`),
because hosts dispatch entries by name; (b) a hidden local is compiler-owned in **every** region
and `STORE_LOCAL` to any hidden local is refused — the stricter Rust reading won over the other
four; (c) dry mode (`Context::set_dry`) is a C++-only host feature, so a new port does not owe one.
Vectors `load-entry-dup-name` and `load-entry-hidden-store` pin (a) and (b).
(reports/wp11-differential-review-T1Fable.md F2/F3/F7; reports/wp11fix-T1Fable.md §"Decisions per
finding"; spec/bytecode.md.)

**P10 — The conformance runner, not the SDK, converts JSON call arguments — strictly.** Before
the WP11 fix, `increment [1.5]` for an `int` parameter was silently truncated to 1 by the C++
runner, passed through as a float by Rust (`RUN_ERROR int operator applied to float`), and threw
an uncaught `ArithmeticException` in Java; Rust's runner also ignored the `type` field of object
arguments. All five runners now refuse any JSON kind that does not match the declared parameter
type (`conformance: bad call args: …`). Port the runner's conversion as carefully as the VM.
(reports/wp11-differential-review-T1Fable.md F5; reports/wp11fix-T1Fable.md;
lmcode-rust/conformance/src/main.rs.)

**P11 — Entry HALT-depth verification is unconditional for entries.** The body runs the stack
pass only when the region contains a loop; entries always run it, and every reachable HALT must
leave exactly 0 values for a `-> void` interface, exactly 1 otherwise (`HALT leaves N values`).
The compiler side uses the interface's return type to decide, and the loader re-checks — the fuzz
corpus's depth+2 mutants (`ADD_I` → `DUP`) are caught by this check alone. (spec/bytecode.md
§"Loader verification"; lmcode-csharp/durable-memory/07-v6-entry-table.md;
lmcode-java/durable-memory/06-v6-entry-table.md.)

**P12 — Displacement arithmetic is relative to the *end* of the instruction.** Jump displacements
are relative to the position immediately after the operand field (spec/bytecode.md §"Instruction
set"). In a sequential reader it is easy to add the displacement to the position *before* reading
it; C#'s gotchas record the rule: read the relative displacement first, then add the reader
position, which must point after the operand. A one-instruction-off jump still lands on an
instruction start often enough to pass smoke tests and fail the jump-target vectors.
(spec/bytecode.md; lmcode-csharp/durable-memory/04-gotchas.md.)

**P13 — The schema hash covers exact bytes, so byte hygiene is part of the port.** Whitespace or
line-ending changes to the schema change its SHA-256 and invalidate previously compiled bytecode;
`.gitattributes` pins LF across conformance files, and Windows checkouts must not CRLF-mangle
them. Go's sync script normalizes MSYS2/Git-for-Windows `sha256sum` output (` *` binary markers,
`\r\n`) before hashing so digest checks are platform-independent — expect the same class of issue
in any new port's lock scripts. (spec/schema.md §"Binding"; lmcode-go/durable-memory/04-gotchas.md;
lmcode-rust/durable-memory/04-gotchas.md.)

**P14 — The corpus has one intentional fixture repair; do not "fix" it back.** The mono
generator's `runtime-empty-lines-fallback` mutation truncates the v6 entry count; the canonical
corpus preserves the two-byte zero-entry tail in that one vector, and every port's `vectors.lock`
records the exception. Regenerating with the unmodified generator yields 69/70 with a correct
loader and must not be used to weaken a loader. (lmcode-rust/durable-memory/07-rule-entries.md;
lmcode-csharp/durable-memory/07-v6-entry-table.md.)

**P15 — No VM resource budgets is a spec decision, not an oversight.** There is no instruction
cap, stack cap or string cap in the VM (`max_stack` is a reservation hint); resource policy
belongs to the host process. Java's runtime adds its own defaults (10M instructions, 4 GiB
cumulative allocation per run) as host policy — a port may do likewise, but the conformance
vectors never require it and a port must not reject valid programs that a reference runtime
accepts. (lmcode-cpp/durable-memory/02-architecture-and-decisions.md;
lmcode-cpp/durable-memory/04-gotchas-and-limits.md; lmcode-java/durable-memory/03-limits.md.)

## The five ports: where everything lives

Paths verified against the clones on 2026-10-30. "Sample" columns point at the sibling
`lmcode-<lang>-sample` repos.

| Port | Loader / VM / verifier | Std catalog | Conformance runner | Sample host |
|---|---|---|---|---|
| C++ (`lmcode-cpp`) | `include/dslvm.hpp` — the whole SDK (loader, verifier, VM, registry, JSON result helpers) is one header-only file; `Program::load` at `dslvm.hpp:452` is canonical | `stdlib/*.hpp` aggregated by `stdlib/std.hpp`; canonical schema `std/lmcode-std.schema.json` + root `std.lock`; `Registry()` defaults to std, `Registry(StdMode::Disabled)` opts out | `conformance/run.cpp` (the reference runner; `make conformance`) | `lmcode-cpp-sample/src/main.cpp`, `shop.cpp` |
| Rust (`lmcode-rust`) | `dslvm/src/lib.rs` (single-file crate: `Program::load` at :422, `Registry` at :220, VM, verifier); `dslvm/src/sha256.rs` is a dependency-free SHA-256 | `dslvm/src/stdlib.rs` + `dslvm/src/stdlib/*.rs` (one module per group); `Registry::new()` / `Registry::new_without_std()` | `conformance/src/main.rs` (crate `dsl-conformance`; `cargo run -p dsl-conformance -- conformance/vectors`) | `lmcode-rust-sample/src/main.rs`, `shop.rs` |
| Go (`lmcode-go`) | root package `lmcode`: `loader.go`, `vm.go`, `registry.go`, `value.go`, `errors.go` | `std_*.go` in the root package (default `NewRegistry()`; `NewRegistryWithoutStd()` opts out; `RegisterStd` idempotent) — kept in the core package to avoid a core↔catalog import cycle; `stdlib/` is a compatibility forwarding package with the group `*.schema-fragment.json` files | `conformance/conformance.go` (package `conformance`) + `cmd/conformance/main.go`; `go test ./...` runs both vector sets and the lock checks | `lmcode-go-sample/main.go`, `host.go` |
| Java (`lmcode-java`) | single package `io.lmctl.lmcode` under `src/main/java`: `Program.java` (load + entry API), `Reader.java`, `Verifier.java`, `Execution.java` (VM), `Registry.java`, `Value.java`, `VmString.java`, `VmException.java`, `Formatting.java` (`formatG15`) | `Stdlib.java` + `Std{String,Math,Collections,Containers,File,Json,Testing}.java`; `Registry()` defaults to std, `Registry(false)` opts out; `PinVerifier.java` checks the canonical bytes | `ConformanceRunner.java` (`main` takes vector directories); `EntryChecks.java` covers the entry refusals; wired into `pom.xml` test phase | `lmcode-java-sample/src/main/java/io/lmctl/sample/Main.java`, `Shop.java` |
| C# (`lmcode-csharp`) | `src/LmCode/`: `Program.cs`, `Reader` inside Program, `Verifier.cs`, `Execution.cs`, `Registry.cs`, `Values.cs`, `Errors.cs`; csproj enables AOT/trim analyzers | `src/LmCode/Stdlib/*.cs` (`StandardCatalog.cs` aggregates; `new Registry()` / `new Registry(includeStd: false)`; `Std.RegisterStd` idempotent) | `conformance/LmCode.Conformance/Program.cs` (console project) | `lmcode-csharp-sample/src/Program.cs`, `Shop.cs`, `Conversions.cs` |

Default-registration spellings summarized (source: `lmcode-cpp/durable-memory/06-stdlib-catalog.md`
§"Default registration and opt-out", updated for the Go/Java current API): C++ `Registry()` /
`Registry(StdMode::Disabled)`; Rust `Registry::new()` / `Registry::new_without_std()`; Go
`NewRegistry()` / `NewRegistryWithoutStd()`; Java `Registry()` / `Registry(false)`; C#
`new Registry()` / `new Registry(includeStd: false)`.

## What this guide could not verify

- **Cross-port return-sink parity.** `template_render` registration is verified for all five
  ports at the revisions in [std.md](../spec/std.md#template_render-status). That does not
  establish return-sink parity (slice 2 remains in progress); target the current 206-signature
  C++ catalog and verify each port's revision and return gate separately.
- **Kotlin/Scala sample repos.** `lmcode-kotlin-sample` and `lmcode-scala-sample` clones exist in
  the team workspace, but there is no corresponding `lmcode-kotlin` / `lmcode-scala` runtime repo
  there; whether they bind the Java SDK or something else was not determined from the sources
  read for this guide.
