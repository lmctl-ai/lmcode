# Conformance coverage and current source of truth

The corpus still lives in the existing repositories. This page is an inventory,
not a new copy or a migration of canonical test data.

| Surface | Current home | What a green result proves |
| --- | --- | --- |
| Core DSLB v6: 397 vectors | [C++ reference corpus](https://github.com/lmctl-ai/lmcode-cpp/tree/main/conformance/vectors) | execution traces, rule entries, located runtime failures, malformed container/operand/loop refusal |
| Standard library: 268 vectors | [C++ standard corpus](https://github.com/lmctl-ai/lmcode-cpp/tree/main/conformance/stdlib-vectors) | catalog operations and selected value/error partitions |
| Native host integration | [shared sample suite](https://github.com/lmctl-ai/lmcode-cpp/tree/main/sample-suite) | byte-exact process output, exits, schema/signature protocol and source-wrapper reproduction |
| Compiler/checker and outer-language behavior | [mono DSL tests](https://github.com/lmctlhq/lmctl-mono/tree/main/lmscript/tests) | typing/schema rejection, splices/deferred checking, source mapping and check/dry-run behavior |

The core generator remains [in mono](https://github.com/lmctlhq/lmctl-mono/blob/main/lmscript/scripts/generate-dsl-conformance.ts).
SDK ports copy committed corpus files with their existing sync scripts and digest
locks. Run the SDK's test.lms with its documented compiler/toolchains; run the
C++ reference's make test conformance to execute both vector directories. Porting
a runtime means implementing the host stub and expectation protocol in the
manifest, rather than changing expected answers to match that runtime.

## Added boundary partitions

The expansion from 73 to 397 core cases adds 301 executable partitions and 23
malformed-wire cases. Host-bound operands prevent constant folding from bypassing
runtime arithmetic. Independent signed-i64 BigInt oracles distinguish overflow
wrapping from JS-number rounding. Cases cover sign/zero/int32/2^53 boundaries,
integer and float comparisons, bool truth tables, float arithmetic, empty/reversed
ranges, break/continue positions, switch no-fallthrough, UTF-8/escapes and inlined
local isolation. Hostile vectors change decoded operands/container fields rather
than finding opcode-looking bytes inside constants.

The original corpus already exercised all 44 defined opcodes and 18 MATH IDs;
new counts are not a claim that more opcodes were needed. Import audits reach all
182 standard signatures and 45 host signatures. Import reachability does not
prove the full semantic contract of every operation. The effective schema has
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

Returned block values and ResultSink terminal-frame integration are concurrent
work in progress and are not certified by this extension. Outer-language reverse
templating is separate from DSLB instruction conformance. No new bytecode version,
return protocol, schema format, canonical repository move or compatibility layer
is introduced by this audit.
