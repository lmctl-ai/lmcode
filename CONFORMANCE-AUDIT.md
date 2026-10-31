# Conformance coverage and current source of truth

The corpus still lives in the existing repositories. This page is an inventory,
not a new copy or a migration of canonical test data.

| Surface | Current home | What a green result proves |
| --- | --- | --- |
| Core DSLB v6: 406 vectors (82 compiler C01 plus 324 boundary/rejection cases) | [C++ reference corpus](https://github.com/lmctl-ai/lmcode-cpp/tree/main/conformance/vectors) | execution traces, rule entries, located runtime failures, malformed container/operand/loop refusal |
| Standard library: 268 vectors | [C++ standard corpus](https://github.com/lmctl-ai/lmcode-cpp/tree/main/conformance/stdlib-vectors) | catalog operations and selected value/error partitions |
| Native host integration: 114 cases (77 exit 0, 36 exit 3, 1 exit 4) + 23 compiler rejects | [shared sample suite](https://github.com/lmctl-ai/lmcode-cpp/tree/main/sample-suite) | byte-exact process output, exits, schema/signature protocol and source-wrapper reproduction |
| Compiler/checker and outer-language behavior | [mono DSL tests](https://github.com/lmctlhq/lmctl-mono/tree/main/lmscript/tests) | typing/schema rejection, splices/deferred checking, source mapping and check/dry-run behavior |

The core generator remains [in mono](https://github.com/lmctlhq/lmctl-mono/blob/main/lmscript/scripts/generate-dsl-conformance.ts).
SDK ports copy committed corpus files with their existing sync scripts and digest
locks. Run the SDK's test.lms with its documented compiler/toolchains; run the
C++ reference's make test conformance to execute both vector directories. Porting
a runtime means implementing the host stub and expectation protocol in the
manifest, rather than changing expected answers to match that runtime.

## Added boundary partitions

The boundary-only expansion grew the historical 73-vector baseline to 397 cases
(301 executable partitions and 23 malformed-wire cases). Nine concurrent return cases
bring the current canonical total to 406: 82 compiler C01 plus 324 boundary/rejection cases. Host-bound operands prevent constant folding from bypassing
runtime arithmetic. Independent signed-i64 BigInt oracles distinguish overflow
wrapping from JS-number rounding. Cases cover sign/zero/int32/2^53 boundaries,
integer and float comparisons, bool truth tables, float arithmetic, empty/reversed
ranges, break/continue positions, switch no-fallthrough, UTF-8/escapes and inlined
local isolation. Hostile vectors change decoded operands/container fields rather
than finding opcode-looking bytes inside constants.

The original corpus already exercised all 44 defined opcodes and 18 MATH IDs;
new counts are not a claim that more opcodes were needed. At audit baseline, import audits reached
182 standard signatures and 45 host signatures. Concurrent ResultSink work adds
24 standard imports in the reference SDK; shared sample adoption is still pending
and its audit correctly rejects those unexercised imports. They are not counted
as sample-ready by this extension. Import reachability does not prove the full
semantic contract of every operation. The effective schema has
overlapping declarations; these category counts must not simply be added.

Production-copy controls must fail: omitted vector families, missing i64 wrap,
wrong remainder/bool oracle, unchanged hostile bytes, and independent native
ADD_I/MOD_I implementation changes. Determinism/signature tests complement native
execution; neither replaces it.

## Remaining limits

Not every verifier rejection branch has a unique vector. Native registry/API and
filesystem errors need native/CLI tests; they are not imaginary bytecode opcodes.
The sample suite tests process/host integration separately from VM semantics.
A green corpus does not establish platform-independent performance limits,
thread safety, resource usage, or arbitrary application policy.

The nine return vectors and separate nine-fixture return gate now cover ResultSink
payload/frame behavior. All five core runners pass 406/406 locally with the
merged sink observers; terminal-frame adoption by application CLIs remains a
separate integration step. Executing blocks and immutable `load_schema` descriptors
landed in mono main at `0bc80277`; the pinned released compiler 0.2.444 predates
that addition. Their discovery/process/cancellation behavior is covered by the
mono execution/frame tests, not certified by this VM-only extension. Outer-language reverse
templating is separate from DSLB instruction conformance. No new bytecode version,
return protocol, schema format, canonical repository move or compatibility layer
is introduced by this audit.

## Optional result observations in conformance/3

A trailing .expect record beginning with sink contains a JSON object whose json
and frame members are strings. Parse that record before unescaping ordinary trace
lines. Compare the exact owned sink JSON after the body and selected entry; partial
writes remain observable when execution fails. Compare frame bytes independently:
only successful completion of both phases permits the terminal frame. Failed
invocations require an empty frame. Bind one fresh invocation sink before the body;
retain it across entry calls and keep it out of per-region arenas.

The nine return cases catch missing writes, lost body state, misplaced error
locations, discarded partial state and frames emitted before entry completion.
The entry's HALT return value is separate from the invocation sink. This extends
test observations without changing DSLB v6 or relocating the canonical corpus.
