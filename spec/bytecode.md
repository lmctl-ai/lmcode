# lmcode bytecode (DSLB v6) — bytecode file format

Status: current. DSLB v6 is the only format version any shipped runtime reads. It is emitted by the
`_lmcode_` / `_dsl_` compiler (`lmscript/dsl.ts` in the lmscript mono tree, published as npm
`@lmctl-ai/lmctl` ≥ 0.2.444) and read by the C++ (`lmcode-cpp`), Rust (`lmcode-rust`) and Go
(`lmcode-go`) SDKs. v6 is an intentional break with v5 (R49): rule entries were appended after the
body line table. There is no backward compatibility; every other version is refused at load.

Normative sources:

- Encoder and opcode table: `lmscript/dsl.ts` (`encodeDsl`, `OP`, `DSL_VERSION = 6`,
  `measureStack`).
- Living language spec, wire-format section: `lmscript/durable-memory/design/dsl-language.md` §7.
- Requirements (R-numbers cited below): `lmscript/durable-memory/requirements/dsl-bytecode.md`
  (R26, R30–R35, R38, R47–R49) and `lmscript/durable-memory/design/dsl-language.md`.
- Reference loader/verifier (canonical for behavior): `lmcode-cpp/include/dslvm.hpp`
  (`Program::load`, `verify_region`, `verify_stack`).
- Sibling loaders, cross-checked against the C++ one: `lmcode-rust/dslvm/src/lib.rs`,
  `lmcode-go/loader.go`. Known divergences are listed at the end.

Conventions: all multi-byte integers are big-endian with fixed widths (Java `DataOutput` style,
R30). No padding, no alignment. `i32`/`i64` are two's complement; `f64` is IEEE-754 binary64.
Strings on the wire are length-prefixed raw bytes; the compiler only ever writes UTF-8.

## File layout

Sections appear in this exact order; each is read exactly once, and the file must end after the
last entry (trailing bytes are an error).

| # | Section | Layout |
|---|---------|--------|
| 1 | header | `u8[4]` magic `DSLB`, `u16` version (6), `u8[32]` SHA-256 of the schema file bytes |
| 2 | constants | `u32 count`, then per constant: `u8 tag` (1 = string), `u32 byte_length`, `u8[byte_length]` payload |
| 3 | imports | `u16 count`, then `u32 constant_index` per import |
| 4 | context | `u16 count`, then per variable: `u32 name_constant`, `u32 type_constant` |
| 5 | body region | locals, max_stack, code, line table (see below) |
| 6 | entries | `u16 entry_count`, then per entry: `u32 name_constant`, `u32 annotation_constant`, `u32 interface_constant`, `u16 nparams`, then a region (locals, max_stack, code, line table) |

A **region** (the body, or one entry) is:

| Field | Layout |
|-------|--------|
| locals | `u16 count`, then per local: `u32 type_name_constant`, `u8 hidden` (0 or 1; 1 marks a compiler-owned loop slot) |
| max_stack | `u16`, the operand-stack depth the compiler measured (a reservation hint; nothing is checked against it, R34) |
| code | `u32 byte_length`, then the instruction bytes; the last instruction is HALT |
| line table | `u32 count`, then per record: `u32 pc`, `u32 line`, `u16 column`; sorted by pc, may be empty |

### Header

The 38-byte header binds the file to its schema: the SHA-256 is computed over the exact schema
file bytes the compiler was given (`dsl.ts` hashes `schema.bytes`; the loader recomputes the hash
over the schema bytes the host supplies and refuses a mismatch). The host never parses the schema;
identity is by hash alone.

### Constants

One pool per file, shared by the body and all entries (R49). It carries string literals, canonical
import signatures, context names and types, local type names, and entry name/annotation/interface
text. The compiler deduplicates on first use. Tag 1 is the only defined tag ("string"); any other
tag is a load error. Constant indexes elsewhere in the file are `u32` except where noted.

### Imports

Each import is a `u32` index into the constant pool whose text is a canonical signature:

- `fn NAME(T1, T2) -> R` — a host function
- `method Type.name(T1, T2) -> R` — a method on a schema object type

The loader resolves each import against the host registry by the full signature text, at load time
(R30's link-time resolution). Several imports may share a name (overloads are distinct signatures).
The import table holds at most 65535 entries (compiler error `too many distinct callees`).

### Context

Each entry names a context variable and its object type, both as constant indexes. The loader
checks the host declares that name with that type. Context variables are always host objects (the
schema refuses primitive or enum context types).

### Entries (v6, R47–R49)

An entry is a compiled rule method: a top-level `@NAME fn ... implements Interface` definition in
the source. Entries are independent mini-programs that share the file's constant, import and
context pools but carry their own locals, max_stack, code and line table. PCs and jump
displacements are relative to the entry's own code region. Entries appear in source order; a file
without annotated rules writes `u16 0`.

Per entry, in order:

1. `u32` constant index of the function name (unique across the file; `duplicate entry name 'NAME'`)
2. `u32` constant index of the annotation (the `@NAME` text, without `@`; empty string when absent
   from the source is not possible — entries exist only for annotated functions)
3. `u32` constant index of the canonical interface text `interface NAME(T1, ...) -> R`
   (parameter names are not serialized)
4. `u16 nparams` — the interface's parameter count
5. the region (locals, max_stack, code, line table) as above

Parameter locals occupy slots `0..nparams-1`, are unhidden, and slot `i`'s type must equal the
interface's parameter type `i`. The host stores call arguments into these slots before execution.
An entry's HALT must leave exactly 0 values on the operand stack for a `-> void` interface and
exactly 1 otherwise (the result). Entries are invoked through the SDK's `call(entry, ...)`; there
is no CALL/RET instruction and no runtime call stack (R49). Body calls to a rule's name are
ordinary compiler inlining and do not touch the entry table.

## Instruction set

One-byte opcode, then big-endian operands. Jump displacements are `i32` relative to the position
immediately after the displacement field (i.e. relative to the end of the instruction). Stack
effects are the deltas the compiler's `measureStack` and the loaders' stack verifier compute;
`argc` is the operand's argument count, `R` is 1 when the resolved import returns non-void and 0
for void.

### v1 core

| Byte | Op | Operand bytes | Stack | Meaning |
|------|----|---------------|-------|---------|
| 0x01 | PUSH_INT | 8 (`i64`) | +1 | push int (64-bit two's complement) |
| 0x02 | PUSH_STR | 4 (`u32` constant) | +1 | push string constant |
| 0x03 | PUSH_BOOL | 1 (`u8`, 0 or 1) | +1 | push bool |
| 0x04 | LOAD_LOCAL | 2 (`u16` slot) | +1 | push local; reading a slot before its store is a run-time error |
| 0x05 | STORE_LOCAL | 2 (`u16` slot) | −1 | pop into local |
| 0x06 | LOAD_CTX | 2 (`u16` context index) | +1 | push the context object the host bound under that name |
| 0x07 | CALL_FN | 3 (`u16` import, `u8` argc) | −argc + R | call host function |
| 0x08 | CALL_METHOD | 3 (`u16` import, `u8` argc) | −(argc+1) + R | call method; receiver is below the arguments |
| 0x09 | EQ | 0 | −1 | same-kind equality, pushes bool |
| 0x0A | NE | 0 | −1 | same-kind inequality, pushes bool |
| 0x0B | NOT | 0 | 0 | bool negation |
| 0x0C | JUMP | 4 (`i32`) | 0 | unconditional forward jump |
| 0x0D | JUMP_IF_FALSE | 4 (`i32`) | −1 | pop bool; jump when false |
| 0x0E | JUMP_IF_TRUE | 4 (`i32`) | −1 | pop bool; jump when true |
| 0x0F | DUP | 0 | +1 | duplicate the top value |
| 0x10 | POP | 0 | −1 | discard the top value |
| 0x11 | HALT | 0 | 0 | end of the region; must be the last instruction |

### v2 (floats, typed arithmetic and ordering)

| Byte | Op | Operand bytes | Stack | Meaning |
|------|----|---------------|-------|---------|
| 0x12 | PUSH_FLOAT | 8 (`f64`) | +1 | push IEEE-754 binary64 |
| 0x13–0x16 | ADD_I / SUB_I / MUL_I / DIV_I | 0 | −1 | int arithmetic, wrapping two's complement (no overflow trap, R34; `INT64_MIN / -1` wraps); `/` truncates toward zero; zero divisor is a run-time error |
| 0x17–0x1A | ADD_F / SUB_F / MUL_F / DIV_F | 0 | −1 | float arithmetic (IEEE; inf and NaN allowed) |
| 0x1B / 0x1C | NEG_I / NEG_F | 0 | 0 | negation (negating `INT64_MIN` wraps to itself) |
| 0x1D–0x20 | LT_I / LE_I / GT_I / GE_I | 0 | −1 | int ordering, pushes bool |
| 0x21–0x24 | LT_F / LE_F / GT_F / GE_F | 0 | −1 | float ordering, pushes bool |
| 0x25 | I2F | 0 | 0 | `float(i)` widening |

### v3 (strings)

| Byte | Op | Operand bytes | Stack | Meaning |
|------|----|---------------|-------|---------|
| 0x26 | CONCAT | 0 | −1 | pop two strings, push concatenation (no size cap, R34) |
| 0x27 / 0x28 / 0x29 | I2S / F2S / B2S | 0 | 0 | `str(x)` for int (decimal), float (`%.15g`), bool (`true`/`false`) |

### v4 (loops and math)

| Byte | Op | Operand bytes | Stack | Meaning |
|------|----|---------------|-------|---------|
| 0x2F | FOR_RANGE | 8 (`u16` counter slot, `u16` end slot, `i32` exit) | −2 | pop end then start; snapshot both into compiler-owned hidden int slots; exit when start ≥ end |
| 0x31 | FOR_NEXT | 6 (`u16` end slot, `i32` back) | 0 | advance the paired counter; branch back while counter < end |
| 0x32 | MATH | 1 (`u8` function id) | 1 − argc(id) | portable primitive math; ids below |
| 0x33 | MOD_I | 0 | −1 | int remainder, dividend's sign (`INT64_MIN % -1` is 0); zero divisor is a run-time error |

### v5 (structured while, R38)

| Byte | Op | Operand bytes | Stack | Meaning |
|------|----|---------------|-------|---------|
| 0x34 | WHILE_BEGIN | 0 | 0 | marks the paired loop head, before condition evaluation |
| 0x35 | WHILE_TEST | 4 (`i32` exit) | −1 | pop bool; exit the loop when false |
| 0x36 | LOOP_BACK | 4 (`i32` back) | 0 | the only backward edge; targets its paired WHILE_BEGIN |

Bytes not listed (0x00, 0x2A–0x2E, 0x30, 0x37–0xFF) are not opcodes; the verifier rejects them
(`unknown opcode N at offset M`).

### MATH function ids (operand of 0x32)

The ids are shared by the compiler and both native SDK generations (`dsl.ts` `MATH_FUNCTIONS`,
`dslvm.hpp` `MathFn`):

| Id | Function | Args → result | | Id | Function | Args → result |
|----|----------|---------------|---|----|----------|---------------|
| 0 | sin | float → float | | 9 | lerp | float ×3 → float |
| 1 | cos | float → float | | 10 | ease | float → float |
| 2 | sqrt | float → float | | 11 | ease_in | float → float |
| 3 | abs | float → float | | 12 | ease_out | float → float |
| 4 | floor | float → float | | 13 | int | float → int (truncate toward zero, saturate at i64 endpoints, NaN → 0) |
| 5 | pow | float ×2 → float | | 14 | abs | int → int (INT64_MIN wraps to itself) |
| 6 | min | float ×2 → float | | 15 | min | int ×2 → int |
| 7 | max | float ×2 → float | | 16 | max | int ×2 → int |
| 8 | clamp | float ×3 → float | | 17 | clamp | int ×3 → int |

sin/cos/pow use the platform libm; the shared vectors allow a relative tolerance of
`1e-12 * max(|expected|, 1e-300)` for those (see `spec/conformance.md`). All other functions are
exact. An id above 17 is refused at load (`unknown MATH function F at offset N`).

## Loader verification

`Program::load` parses, binds and verifies before anything executes (`dslvm.hpp:452`). Every
failure throws with one of the load error codes below; nothing runs. The checks, in the order the
C++ loader applies them:

Header and pools:

1. Magic is `DSLB`; else `not a DSL bytecode file: bad magic (expected 'DSLB')`.
2. Version is 6; else `unsupported bytecode version N (this runtime reads version 6)`.
3. The schema hash matches SHA-256 of the host's schema bytes; else LOAD_SCHEMA_MISMATCH
   `schema mismatch: bytecode was compiled against schema sha256 HEX, the given schema has sha256 HEX`.
4. Constants: tag is 1; else `constant I has unknown tag T (1 = string)`.
5. Every constant index is in range; else `WHAT: constant index I out of range (N constants)`,
   where WHAT is `import`, `context name`, `context type`, `local type`, `entry name`,
   `entry annotation`, `entry interface` or `entry local type`.
6. Every import resolves against the host registry by full canonical signature; else LOAD_UNBOUND
   `import 'CANONICAL' is not provided by the host`, with the suffix ` (the host declares ...)` when
   the host registers that name with other signatures (e.g. `import 'fn twice(float) -> int' is not
   provided by the host (the host declares fn twice(int) -> int)`).
7. Every context variable is declared by the host with the same type; else LOAD_UNBOUND
   `context variable 'NAME' is not declared by the host` or
   `context variable 'NAME' is declared as T by the bytecode, the host provides U`.
8. Local hidden flags are 0 or 1; else `local I hidden flag must be 0 or 1` (entry form:
   `entry 'NAME': local J hidden flag must be 0 or 1`).
9. Line tables are sorted by pc; else `line table is not sorted by pc at entry I` (`I` is the
   record's row index; the same text serves the body and entry tables; entry tables prefix
   `entry 'NAME': `).
10. Entry names are unique; else `duplicate entry name 'NAME'`.
11. Entry interface text parses as `interface NAME(T1, ...) -> R` with a non-empty return type;
    else `entry 'NAME': interface 'IFACE' is not an interface signature`.
12. `nparams ≤ nlocals`; else `entry 'NAME': nparams N exceeds nlocals M`.
13. `nparams` equals the interface's parameter count; else
    `entry 'NAME' declares N parameter(s); interface I(T1, ...) -> R has M`.
14. Parameter local `i` (1-based in messages) has the interface's type `i` and is unhidden; else
    `entry 'NAME' parameter I has type T; the interface expects U` or
    `entry 'NAME' parameter I is hidden`.
15. After the last entry the file is exhausted; else `bytecode has N trailing byte(s) after the entries`.
16. Any short read anywhere is `bytecode is truncated: wanted N byte(s) at offset M, file has K`.
    Counts never drive allocation before the bytes are read: a count larger than the remaining
    bytes surfaces as this truncation error, never as a reservation (R49 WP11).

Instruction verification (`verify_region`, applied to the body and to each entry with the entry
errors prefixed `entry 'NAME': `):

- Every byte decodes as a known opcode with its operands present; unknown opcodes are
  `unknown opcode N at offset M`.
- Indexes: PUSH_STR's constant, LOAD_LOCAL/STORE_LOCAL's slot, LOAD_CTX's context index and the
  call imports are in range (`WHAT index I out of range (N entries)`).
- CALL_FN must name a function import and CALL_METHOD a method import
  (`CALL_FN at offset N names import I, which is a method` / `CALL_METHOD ... which is a function`),
  and the `argc` operand must equal the import's arity
  (`CALL_FN at offset N passes A argument(s), the import takes P`).
- PUSH_BOOL's operand is 0 or 1.
- MATH's id is at most 17.
- JUMP, JUMP_IF_FALSE, JUMP_IF_TRUE and WHILE_TEST are forward-only
  (`jump at offset N goes backwards (only paired LOOP_BACK may jump backward)`; WHILE_TEST:
  `WHILE_TEST at offset N exits backwards`). LOOP_BACK is the only backward edge.
- Every jump target lands on an instruction start
  (`jump at offset N targets M, not an instruction start`; the stack pass reports the same
  condition as `control flow targets M, not an instruction start`).
- Loop pairing. FOR_RANGE's counter and end slots are distinct hidden int locals, not shared with
  any other range loop in the region (`FOR_RANGE counter slot S must be a hidden int local`,
  `FOR_RANGE counter and end slots must be distinct`,
  `FOR_RANGE slot S is already owned by another range loop`). Its exit displacement is forward
  (`FOR_RANGE at offset N exits backwards`) and lands immediately after its paired FOR_NEXT
  (`FOR_RANGE at offset N must exit immediately after its FOR_NEXT`), in the same lexical region
  (`FOR_RANGE at offset N exits to an invalid loop region`). FOR_NEXT pairs with the innermost open
  FOR_RANGE (`FOR_NEXT at offset N has no matching FOR_RANGE`), encodes the same end slot
  (`FOR_NEXT at offset N names end slot S, expected E`), and returns to just after its FOR_RANGE
  (`FOR_NEXT at offset N must return to its FOR_RANGE body`). WHILE_TEST pairs with the innermost
  open WHILE_BEGIN (`WHILE_TEST at offset N has no matching WHILE_BEGIN`), at most one per head
  (`WHILE_BEGIN at offset N has more than one WHILE_TEST`), and exits immediately after its paired
  LOOP_BACK (`WHILE_TEST at offset N must exit immediately after its LOOP_BACK`). LOOP_BACK pairs
  with the innermost open WHILE_BEGIN (`LOOP_BACK at offset N has no matching WHILE_BEGIN`), which
  must have its WHILE_TEST (`WHILE_BEGIN at offset N has no WHILE_TEST`), and targets that head
  exactly (`LOOP_BACK at offset N does not target its paired WHILE_BEGIN`). An unclosed opener at
  end of code is `unclosed FOR_RANGE at offset N` / `unclosed WHILE_BEGIN at offset N`.
- HALT only at region depth 0 (`HALT inside loop`) and as the last instruction
  (`code does not end with HALT`).
- Ordinary jumps stay in their lexical loop region; the one permitted crossing is a break to the
  innermost loop's exit in the parent region
  (`jump at offset N crosses a loop boundary (only a break to the innermost loop exit is allowed)`).
  A jump inside a while head may not skip its WHILE_TEST (`jump at offset N skips its WHILE_TEST`).
- STORE_LOCAL writes no loop counter/end slot (`STORE_LOCAL at offset N writes a read-only range
  slot S`) and no hidden local at all, in the body or any entry
  (`STORE_LOCAL at offset N writes compiler-owned loop local S`).
- Line table pcs are inside the code (`line table entry points at pc N, beyond the code`).

Stack verification (`verify_stack`): a dataflow pass assigns an operand depth to every reachable
instruction start. It refuses underflow (`operand stack underflow at offset N`), inconsistent
joins (`inconsistent operand stack depth at control-flow join N: A versus B`), fall-through past
the last instruction (`control flow falls past the end of code`), and a WHILE_TEST whose depth is
not the loop-head depth plus one (`WHILE_TEST must leave the loop-head stack depth at offset N`).
For the body this pass runs only when the region contains a loop; for entries it is unconditional
and additionally requires every reachable HALT to leave exactly 0 values for a void interface or 1
otherwise (`HALT leaves N values`). (Compiler side, `measureStack` computes the recorded
`max_stack` by the same deltas; values above 65535 are a compile error.)

## Loader error codes and result convention

`dslvm::Error` carries a `code` string:

| Code | Raised when |
|------|-------------|
| LOAD_BAD_BYTECODE | malformed file: magic, version, truncation, structure, verifier |
| LOAD_SCHEMA_MISMATCH | the schema hash in the header differs from the given schema's |
| LOAD_UNBOUND | an import or context declaration is not provided by the host registry |
| RUN_ERROR | VM run-time failure (stack underflow, division/modulo by zero, wrong value kind, unbound context at run time, …) |
| RUN_HOST | a host closure threw (a plain message), or a host-side API misuse such as `call` with the wrong argument count |
| APP_FAIL | the host's own application failure (exit 4) |

Run-time messages defined by the VM (`dslvm.hpp` `execute`): `stack underflow`,
`local slot S read before assignment`, `context variable 'NAME' was not provided by the host for
this run`, `method T.M called on a X`, `cannot compare A with B`, `int operator applied to A and B`,
`float operator applied to A and B`, `int division by zero`, `int modulo by zero`,
`int negation applied to A`, `float negation applied to A`, `float() applied to A`,
`string + applied to A and B`, `str(int) applied to A`, `str(float) applied to A`,
`str(bool) applied to A`, `! applied to a A`, `condition is a X, not a bool`,
`jump before the code start`, `jump target N is outside the code`, `unknown opcode N`
(unreachable after a successful load). Entry-call API errors are RUN_HOST:
`call entry index I out of range (N entries)` and
`call entry 'NAME' expects N argument(s); found M`.

Located errors (S5): when the region's line table covers the faulting pc, the message becomes
`dsl line N:C: MESSAGE`; a table column of 0 (unavailable, including source columns beyond 65535)
yields `dsl line N: MESSAGE`. The SDK JSON helpers add `"line"` and `"column"` fields. Load errors
have no location.

The invocation envelope is a native host protocol, independent of VM/HALT
results. Amendment R1 replaces unframed report helpers with per-slot collection
and one success/failure frame per command; builder payloads retain add order.
See [the normative wire and exit contract](host-protocol.md#exactly-one-terminal-envelope).
No bytecode version, opcode, import count or encoded source-location change is
implied; controlled host failures preserve the existing VM diagnostic literals.

## Version policy

The version field is a `u16`. The only accepted value is 6 (`dsl.ts` `DSL_VERSION`, `dslvm.hpp`
`dslvm::VERSION`). A v6 loader refuses v5 and every other version with
`unsupported bytecode version N (this runtime reads version 6)`. There is no backward
compatibility promise (R30, R49: "a format break by decision"); the SDK's version equals the
bytecode version it reads. The sample-suite pins this with mutation case `093-v5-refused` (see
`spec/conformance.md`).

## Compiler-side format invariants

Guaranteed by `encodeDsl` for compiler-emitted files (loaders still verify them): imports ≤ 65535,
locals per region ≤ 65535, entries ≤ 65535, `max_stack` ≤ 65535; constants are deduplicated;
the body code ends with HALT; entry parameters occupy the first `nparams` local slots unhidden;
interface text ends with `-> void` or a value type, which decides the entry's HALT depth check.
A schema signature may declare at most 255 parameters (so `u8 argc` suffices).

## Known divergences between the loaders

`dsl.ts` + `dslvm.hpp` are canonical; the conformance vectors accept the Rust/Go wordings through
substring matching. Differences found while cross-checking `lmcode-rust/dslvm/src/lib.rs` and
`lmcode-go/loader.go` against them:

- **UTF-8 constants.** Rust validates UTF-8 at load for constants used structurally (imports,
  context names/types, local types, entry metadata): `WHAT: constant I is not valid UTF-8`.
  C++ and Go never validate; string values are raw bytes in all three. (Already flagged in the
  requirements findings as a spec gap; this document records C++/Go behavior as canonical.)
- **Entry HALT-depth message.** C++: `entry 'NAME': HALT leaves N values`. Rust and Go:
  `entry 'NAME': HALT leaves N values, interface returns T`. Both contain the R49-pinned shape as a
  prefix substring.
- **HALT inside a loop.** C++ and Go: `HALT inside loop`. Rust: `HALT at offset N is inside loop`.
- **Loop-boundary jump.** C++ and Go: `jump at offset N crosses a loop boundary (only a break to
  the innermost loop exit is allowed)`. Rust omits the parenthetical.
- **FOR_RANGE exit check.** C++ and Go: `FOR_RANGE at offset N exits to an invalid loop region`.
  Rust: `FOR_RANGE at offset N exits to M, not an instruction start`.
- **Entry check order.** C++ refuses `nparams > nlocals` before comparing `nparams` with the
  interface's parameter count; Rust and Go compare the interface count first. Only files that are
  invalid in both ways observe a different first error.
- **Dry mode.** `Context::set_dry` (preflight PLAN) exists only in the C++ SDK; the Rust and Go
  `call`/`run` have no dry path (R49 WP11).
