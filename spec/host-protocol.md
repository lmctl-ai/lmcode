# Native host protocol and invocation envelopes

Status: the C++ reference implements amendment R1. Compiler result metadata (R2),
other runtime collectors (R3), explicit execution/builders (R4–R5), and real host
adapters (R6–R7) land separately. No release during mixed protocols. Earlier
bare-payload/per-program framing is superseded, with no compatibility fallback.
Public execution examples become runnable only with coherent compiler/SDK/host pins.

## Host options

`HOST --lmcode-schema [--json]` discovers the host's schema; JSON mode prints its
exact bytes. `HOST --lmcode-signatures` prints sorted canonical signatures.
`HOST --lmcode FILE` executes compiled lmcode. Standard multi-program adapters
accept repeated `--lmcode FILE` pairs; custom roles may use other file flags.
Retired options are errors, never aliases. Introspection returns before reading
invocation execution metadata. Internal `.dslb` filenames and DSLB v6 stay unchanged.

The SDK is a library: loading/running/calling a program never prints an envelope
implicitly. The adapter owns execution, entry selection, application validation,
drainage and the one terminal write. Bytecode remains trusted host code.

## Private invocation metadata

LMScript's execution owner supplies an absolute `LMCODE_INVOCATION_FILE` in the
child environment, replacing an inherited value. It names private UTF-8 JSON:

```json
{"version":1,"mode":"builder","parts":[{"index":0,"file":"/private/part-0.dslb"},{"index":1,"file":"/private/part-1.dslb"}]}
```

Only version, mode and parts are permitted. Mode is single or builder. Parts is
nonempty, with only index/file members; indices are contiguous zero-based add
order. Single mode requires one part. File strings are absolute on the executing
OS, unique, UTF-8 and NUL-free. Safe integral JSON number tokens denote indices
and version; booleans/fractions/unsafe numbers do not.

The host supplies parsed file occurrences unchanged. They must be a complete
permutation of manifest files: reject missing/extra/duplicate registrations before
dispatch. Match exact strings, without path normalization, shell parsing, content
deduplication or raw argv-position inference. A parser may reorder role options;
the metadata still determines canonical indices. It does not supply schema or
result contracts: those remain authoritative host-owned metadata.

Without the environment descriptor, standalone CLI occurrences define equivalent
metadata: one is single, several are builder mode in CLI occurrence order. Duplicate
filenames are legal in that standalone form, each a distinct slot. Preserve the
occurrence list instead of a filename map. A one-slot builder needs the explicit
mode, even when its program returns a list.

This is execution correlation, not a host-side builder or an input-value ABI.
There is no public manifest option, script path getter, export or debug flag.
Each language execution uses fresh metadata; native callers must not forward a
stale descriptor to a nested execution. The C++ reader does not mutate its
process environment. The language owner retains files until the child closes,
then cleans them after drainage; R4–R5 implement that lifecycle.

## Optional per-program result contract

Schema 2 may declare:

```json
{"dsl.schema":2,"name":"scores","types":{},"functions":{},"context":{},"result":{"type":"IntMap","nullable":false}}
```

Type is required and is exactly null, bool, int, float, string, Json, StrList,
IntList, FloatList, StrMap, IntMap or FloatMap (JSON string spellings). Only nullable
is optional; it defaults false and must be boolean. Type null forbids the nullable
key, even false. Unknown result keys/types are schema errors. No declaration
permits any valid JSON, including null. There are no handle, enum, record, union
or general JSON Schema declarations here.

Known scalar/collection writes match the contract; int fits float and
IntList/IntMap fit FloatList/FloatMap without converting values. No string/number,
bool/number or collection coercion is introduced. Json is JSON-wide: it permits
supported JSON-native shapes without conversion. A Json input with unknown shape
defers narrower checks to runtime. Runtime JSON integer shapes are safe
mathematical integers, independent of decimal/exponent spelling.

Field writes require a map/Json result and retain homogeneous map element checks.
Root nullable permits root null, not null elements of homogeneous maps/lists.
Json may contain nested nulls. Initial/reset null is unfinished construction state,
allowing the first field write into a nonnullable map; explicit null and completion
validate. An unwritten nonnullable result fails at completion, not by a static
proof of all host-selected paths.

Copies validate atomically on writes and at completion. Failure leaves the prior
sink unchanged. Contract mismatch is RUN_HOST with the literal form
`lmcode return: result type mismatch at PATH: expected T; got K`; PATH is a JSON
Pointer (empty at root), escaping slash/tilde. Contract schema errors use the native
LOAD_BAD_SCHEMA code; this is not a new bytecode-verifier instruction/error branch.
The original schema bytes remain the hash authority; standard merging retains the
host-owned result metadata. The contract applies to each slot, never its aggregate.

The 24 existing `lmcode_return_*` signatures remain unchanged. Writes do not exit
the program or replace entry HALT values. Values are deep owned copies, independent
of source mutation and VM arenas. Existing strict UTF-8, cycle/handle refusal, safe
integer/raw-token checks, finite numbers, nonzero-underflow refusal and negative
zero normalization remain in force. Binary64 uses the closest shortest-round-trip
decimal (ties to even), formatted
like C++ `to_chars(general)`: fixed notation for decimal exponents -4 through 5,
scientific notation otherwise, lowercase `e`, explicit exponent sign and at least
two exponent digits. Negative zero is `0`; no redundant `.0` is emitted.
Strings use `\b`, `\f`, `\n`, `\r`, `\t`, `\"` and `\\`; remaining control
characters use lowercase `\u00xx`. Unicode text remains UTF-8.
Malformed invocation metadata uses the reference byte-parser diagnostic (including
byte offsets) and result-number validation preserves JSON pointer paths.
The mirrored [boundary fixtures](../tests/fixtures/invocation-boundaries/) pin
full success and failure frame bytes; refresh them with
`scripts/sync-invocation-boundaries.py` and `LMCODE_CPP` set to the reference.
For example, `0.1 + 0.2` is **0.30000000000000004**, not a legacy precision-limited display value.

## Per-slot native lifecycle

C++ `InvocationResults::from_command(parsed_files)` creates the collector;
`registrations()` returns parser-order `(file,index)` records. For each program:

1. Load against the authoritative host schema and parse its ResultContract.
2. `select(index,registry,contract)` binds that slot's fresh sink before its body.
3. Run the body and the host's selected entries with their actual arguments.
4. Reselect active slots for interleaving without resetting their state/contract.
5. `complete(index)` validates, snapshots and seals the slot.

A sealed sink refuses writes, reset, selection and second completion. A completion
validation error latches its slot/run failure before rethrowing. Selecting another
contract for an active slot is an error. Next invocation creates new sinks. Keep
registry/collector lifetimes and access synchronized: serialize collector calls;
parallel VM work needs separate slots/registries and must drain before writing.
Registry copies share their standard runtime and are not independent containers.

Execution order may differ from add order, and host state may remain shared.
Results always use canonical add indices. Two programs writing the same field
remain separate objects. Successful aggregation requires all slots completed;
a skipped slot is not silently null. A completed no-write slot yields null only
when its contract permits it.

`fail(index_or_none,phase,error)` latches the first observed failure and association.
Stop starting work after failure, drain already-started work and retain that first
failure; effects already performed are not rolled back. Active work may be selected
again for drainage, but new slots cannot start. Global application validation must
finish before `write_frame(out)`; report its failure with no slot index. The collector
cannot validate domain state that the host has not supplied.

`write_frame(out)` finalizes once and returns 0/2/3/4. Global
`failure_frame(out,phase,error)` covers errors before collector creation; return
its status immediately. Sink-only frame and unframed report helpers are removed.

## Exactly one terminal envelope

Single success:

```text
LMCODE_RETURN_BEGIN
{"ok":true,"result":0.30000000000000004}
LMCODE_RETURN_END
```

Builder success (including a one-slot builder):

```text
LMCODE_RETURN_BEGIN
{"ok":true,"result":[{"score":7},null],"parts":2}
LMCODE_RETURN_END
```

Builder-only parts is required, equals the submitted count, and equals result
length. A single program returning a list omits parts; a one-slot builder returning
that list yields a nested result array with parts:1. Success keys are ok,result,parts.

Controlled failure is flat, with no result, parts or partial-success array:

```text
LMCODE_RETURN_BEGIN
{"ok":false,"phase":"run","code":"RUN_HOST","message":"entry refused","line":4,"column":2,"part":1}
LMCODE_RETURN_END
```

Phase/code/message are required strings; phase is cli/load/run/app. Optional line
and column are positive safe integers; column requires line. Optional part is a
safe integer in `[0, submitted_count)`, builder-only, for a known failing slot
(including load/contract failure). Global and single failures omit it. Failure
keys are ok,phase,code,message,line,column,part; no additional keys are permitted.

Use strict UTF-8, no BOM, compact one-line JSON, LF delimiters and exactly one LF
after END, final on stdout. Reject duplicate keys, malformed/bad-count/type frames
and trailing bytes. Escaped marker/newline data inside a JSON string is ordinary
data. Needed traces/findings/SARIF diagnostics precede the frame; domain summaries
use a tagged host_summary diagnostic, not a second unframed ok/result record.
Stdout/stderr diagnostics are forwarded, never guessed as results.

| Child outcome | Execution consumer action |
| --- | --- |
| Exit 0, valid success | Return the whole envelope; caller reads r.result |
| Exit 2/cli, 3/load-or-run, 4/app, valid failure | Return failure data without latching an LMScript error |
| Missing/duplicate/bad frame, unknown exit, count/type or exit/envelope disagreement | Located runtime failure with diagnostics; no guessed result or retry |
| Spawn failure, crash or broken output without valid frame | Located runtime failure, no fabricated envelope |
| Caller cancellation | Discard any frame; preserve existing signal outcome (including 130/143) |

Flush once framed. After a write begins/fails, do not append a second frame;
use stderr best-effort and a nonzero status. No frame is promised after process
death. Streams preserve LF (binary stdout on Windows); native adapters supply
UTF-8 argv. There are no execution deadlines, retries or output/event caps.

## Conformance and adoption

C++ `conformance/invocation-vectors` provides exact native success/failure bytes:
two distinct programs, duplicate programs, one-slot builders, single-list payloads,
null/nested values and reversed dispatch with shared state. Private slot paths
include spaces/Unicode. Contract/metadata/sealing/first-failure and real compiled
mutations are part of the C++ local gates. Typed compiler fixtures remain R2.

The original untyped return bytes/HALT/source locations remain unchanged. Their
new envelope goldens are generated from authored values/errors, not observed
stdout. Native frame expectations for compiler core fixtures are a deterministic
SDK-owned stage after compiler generation. Runtime ports and samples must adopt
these exact semantics with coherent pins in their assigned R3/R6/R7 lanes.

## Dry host invocation marker (H0)

Version-1 invocation metadata has a required boolean `dry`, independent of `mode`:

```json
{"version":1,"mode":"builder","dry":true,"parts":[{"index":0,"file":"/private/part-0.dslb"}]}
```

The producer always writes true or false. Collectors reject a missing or nonboolean
field as a CLI failure; it never silently means real execution. Without a manifest,
a standalone host defaults to real. The selected mode applies to every builder slot.

A successful dry envelope appends `dry:true` after the existing keys:

```text
LMCODE_RETURN_BEGIN
{"ok":true,"result":0,"dry":true}
LMCODE_RETURN_END
```

A dry failure similarly appends the marker after existing failure keys, including
`part` when present. Real envelopes omit `dry`. Consumers require true for a dry
invocation and reject the marker on real invocations. This marker identifies the
invocation mode; it does not claim arbitrary host code had no effects.
