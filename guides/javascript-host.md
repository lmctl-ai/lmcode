# Writing a JavaScript host

## Status and installation

[lmcode-js](https://github.com/lmctl-ai/lmcode-js) is a pure ESM runtime on Node.js
LTS (Node 22 and 24 are tested upstream). There is no native build or runtime
dependency. Clone that repository into a local `lmcode-js` directory alongside
the files below; import its source entry point directly. The package name is
reserved for a future npm release: this guide does not assume it is published.
Install the separate compiler, `@lmctl-ai/lmctl@0.2.456`, into an owned npm prefix
and put that prefix's `node_modules/.bin` on PATH. Nothing needs a global install.

At runtime revision `6bf09cd1073c8fb6d0e8077254ad50256d722040`, the canonical
gates pass 410 core, 271 standard, 9 return, 28 invocation and 29 malformed-metadata
cases, plus 123 sample cases. The first independent review found manifest-validation
defects; fixes landed in `21a3dea` and are included in this revision. They are no
longer pending. [Upstream CI](https://github.com/lmctl-ai/lmcode-js/actions/runs/41561796155)
passed Ubuntu/macOS/Windows on Node 22/24. This is conformance evidence, not a
promise that V8 cannot abort on fatal heap exhaustion; see Representation below.

The four labeled blocks below are executable documentation. The specification's
ordinary documentation gate compiles the program and runs this host with the real
SDK, comparing stdout/exit/stderr with the expected block. Setup commands belong
in prose, not inside these source blocks.

## Schema — counter.schema.json

The compiler and loader use these exact bytes. Standard declarations are supplied
by the compiler's implicit catalog and the SDK's `createRegistry()` respectively.

```json
{
  "dsl.schema": 2,
  "name": "js_counter",
  "types": {"Counter": {"methods": {"add": [{"params": ["int"], "returns": "int"}]}}},
  "functions": {"echo_bytes": [{"params": ["string"], "returns": "string"}]},
  "context": {"counter": "Counter"},
  "result": {"type": "Json", "nullable": false}
}
```

## Host — counter-host.mjs

This minimal adapter receives bytecode filenames as argv, never shell text. It
does not implement schema-discovery flags; the program below explicitly supplies
its schema and command. A general CLI should also implement the discovery options
in the [host protocol](../spec/host-protocol.md). The bundled Shop/Ledger host at
`lmcode-js/sample/main.mjs` is a full CLI example with entry dispatch and application
validation; it supports `--lmcode`, `--lmcode-schema` and `--lmcode-signatures`.

```js
import { readFileSync } from 'node:fs';
import {
  Context, InvocationResults, Program, createRegistry,
  failureFrame, resultContractFromSchema,
} from './lmcode-js/src/index.mjs';

function run(files) {
  let results;
  try { results = InvocationResults.fromCommand(files); }
  catch (error) { return failureFrame('cli', error); }

  const registry = createRegistry()
    .context('counter', 'Counter')
    .method('method Counter.add(int) -> int', (counter, amount) => {
      counter.value += amount;
      return counter.value;
    }, { dry: (counter, amount) => counter.value + amount })
    .fn('fn echo_bytes(string) -> string', bytes => Buffer.from(bytes), {
      rawStrings: true, dry: bytes => Buffer.from(bytes),
    });
  const context = new Context({ counter: { value: 0n } });
  context.setDry(results.dryMode());
  const schema = readFileSync(new URL('./counter.schema.json', import.meta.url));
  const contract = resultContractFromSchema(schema);
  for (const { file, index } of results.registrationsCopy()) {
    let phase = 'load';
    try {
      const program = Program.load(readFileSync(file), schema, registry);
      results.select(index, registry, contract);
      phase = 'run';
      program.run(context);
      // This schema declares no rule interfaces. A host with interfaces must
      // dispatch its selected program.entries via program.call before complete.
      results.complete(index);
    } catch (error) {
      results.fail(index, phase, error);
      break;
    }
  }
  // Global application validation belongs here, before the one terminal write.
  return results.writeFrame();
}

const output = run(process.argv.slice(2));
process.stdout.write(output.frame);
process.exitCode = output.code;
```

## Program — counter.lms

Run this file with the privately installed `lmscript` from the directory holding
the schema and host. `run_lmcode` owns bytecode transfer and private invocation
metadata; `$DSLFILE` is its argv placeholder, not shell interpolation.

```text
program = _lmcode_ schema="counter.schema.json";
$return.total = counter.add(7);
$return.byte_count = str_len(echo_bytes("é"));
$return.fraction = 0.1 + 0.2;
end _lmcode_
result = run_lmcode(program, {command: ["node", "counter-host.mjs", "$DSLFILE"]});
print(json_stringify(result));
```

## Expected stdout

The host emits one terminal `LMCODE_RETURN_BEGIN`/`LMCODE_RETURN_END` envelope.
`run_lmcode` consumes that frame and returns its typed value; printing it yields:

```text
{"ok":true,"result":{"total":7,"byte_count":2,"fraction":0.30000000000000004}}
```

## Registry, invocation and dry mode

`new Registry()` starts empty; `createRegistry()` registers all 206 standard
signatures, including the 24 result operations. Function callbacks receive their
declared arguments; method callbacks receive the host object first. The registry
and bound host objects must remain valid for the program's body and selected entries.

`InvocationResults.fromCommand(files)` reads version-1 metadata from the private
absolute `LMCODE_INVOCATION_FILE`. Its required boolean `dry`, mode and contiguous
part indices are validated before dispatch. Keep exact file occurrences: registration
order may differ from canonical part order. Without a descriptor, standalone calls
use real mode; one file is single and multiple occurrences form a builder.
`select()` binds each slot's owned `ResultSink`, `complete()` validates and seals it,
and `writeFrame()` produces one final envelope in add order. Failures latch their
phase and part association; dispatch stops and already-started work must drain.
Do not emit an unframed second result or frame each program separately.

The example sets `Context.setDry(results.dryMode())`. Ordinary host callbacks are
skipped in dry mode and return typed dummies. An explicit `{ dry: callback }`
preview runs instead of the real callback; the counter preview above does not
mutate shared state. Standard pure previews may still allocate. Dry mode is not a
sandbox for arbitrary host code, nor a memory or time budget. Upstream dry tests verify callback behavior; this repository's guide controls
verify the host wiring and real envelope.

## Representation and result ownership

VM integers are signed 64-bit **BigInt**, wrapping at integer boundaries. Keep
callback values as BigInt; `{ ints: 'number' }` is an explicit safe-integer bridge,
not a way to represent all int64 values. Floats use binary64 `number`. The result
boundary rejects unsafe JSON integers and nonfinite values. Its shortest-round-trip
formatter preserves `0.1 + 0.2` as `0.30000000000000004`; the legacy `%.15g` trace
formatter is a different contract.

VM strings are raw bytes stored as latin-1 JS code units, with byte lengths and
offsets. Default host callbacks receive UTF-8 text; `{ rawStrings: true }` bridges
to owned `Buffer` bytes, preserving NUL/invalid UTF-8. Do not apply JS Unicode
operations to internal VM strings. Unix paths preserve native bytes; Windows paths
require UTF-8, and native filesystem refusals remain host errors.

Result sinks own copies; later mutation of a source collection cannot alter a
completed result. Cycles/opaque handles and invalid UTF-8 are refused. There are
no implicit instruction deadlines, string-size ceilings, matcher-work budgets,
output caps or live-object quotas. Wire/platform representability and shared JSON
parser/template nesting rules still apply. Catchable allocation failures become
`RUN_HOST`; **fatal V8 OOM and OS termination cannot be caught by an in-process
synchronous SDK**. Hosts requiring abort containment need a supervised process
boundary. A green canonical corpus does not establish universal OOM containment.

## Canonical sync and checks

Keep `lmcode-cpp` as the corpus owner. In a disposable JS checkout, set
`LMCODE_CPP_DIR` to the selected reference revision, then run the SDK's
`scripts/sync-std.mjs`, `scripts/sync-vectors.mjs` and
`scripts/sync-sample-suite.mjs` with Node. The vector sync copies core, standard,
return and invocation directories; the sample suite goes in `sample-suite/corpus`.
The scripts record source commits and SHA-256 locks. `npm run verify:pins` checks
integrity, not freshness against a new upstream revision; sync explicitly first.

The cross-runtime matrix clean-installs with npm, runs unit/mutation/full conformance
and sample checks on all five platforms, and uses the same snapshotted reference
for every runtime. See [CI instructions](../scripts/ci/README.md) for that runner and
[conformance](../spec/conformance.md) for the canonical observation contract.
