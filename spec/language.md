# lmcode — language reference

**Execution amendment:** opaque program construction, explicit `run_lmcode` and
`lmcode_build` supersede prior block-end execution/export forms. Their language
implementation is R4–R5 (in progress until adopted on mono main); examples below
that document the released 0.2.444 baseline are historical syntax, not a new
compatibility API. The C++ R1 invocation-envelope/optional-result contract is
[normative here](host-protocol.md). R8 coordinates final runnable examples.

Status: released compiler 0.2.444 baseline, with mainline return additions explicitly marked. This is the reference for people who **write** lmcode source — the language inside
`_lmcode_ ... end _lmcode_` blocks. It is not a tutorial, and it does not cover how runtimes load or
execute the compiled output; the wire format and loader rules live in `spec/bytecode.md`, the test
contract in `spec/conformance.md`, the schema document format in `spec/schema.md`, the host CLI
protocol in `spec/host-protocol.md`, and the standard catalog in `spec/std.md`.

Normative sources:

- Living language spec: `lmscript/durable-memory/design/dsl-language.md` in the lmscript mono tree.
- Requirements (the R-numbers cited below): `lmscript/durable-memory/requirements/dsl-bytecode.md`
  (R01–R49), `requirements/lmcode-literals.md`, `requirements/lmcode-std.md`,
  `requirements/lmcode-std-v3.md`, `requirements/dsl-heredoc.md`.
- Compiler (canonical where the prose spec is ambiguous): `lmscript/dsl.ts`
  (`parseDslSchema`, `tokenize`, `Compiler`, `encodeDsl`, `DSL_VERSION = 6`).
- Literals design: `lmscript/durable-memory/design/lmcode-literals.md` (its header still says
  PROPOSED, but the compiler implements it and the sample suite pins it as `lmcode-literals-v1`;
  this document follows the compiler).
- Standard catalog: `lmcode-cpp/std/lmcode-std.schema.json` (canonical; compiler and SDK byte pins
  must be compared by revision, see [std.md](std.md#ownership-and-drift-pinning)) and the generated inventory
  `lmscript/durable-memory/lmcode-std-reference.md`.
- Heredoc rules: `lmscript/durable-memory/requirements/dsl-heredoc.md` (R01–R07).

Where the prose spec and `dsl.ts` disagree, `dsl.ts` wins and the disagreement is noted inline.

## 1. Program model (R05, R12, R13, R26)

An lmcode program is **one chunk of statements** that a host program runs as a callback inside a
context the host hands it. The host owns the process, the objects and their lifetime; the chunk may
read context objects, call their methods and the host functions, and create local variables. The
released 0.2.444 chunk has no lmscript return value: its effects are the calls it makes.
Mainline slice 3 additionally writes a separate invocation-owned return sink (§2). The compiler only verifies and compiles
the chunk (R05); a native runtime (`lmcode-cpp`, `-rust`, `-go`, `-java`, `-csharp`, `-js`) executes it. One block compiles
to one bytecode file (R26).

The language is strongly and statically typed; its named types come from a schema the host supplies
(§9). It is deliberately not lmscript-compatible. Every expression has exactly one static type,
every call is resolved at compile time, and the compiler rejects a program before any effect runs.

## 2. The `_lmcode_` block boundary (R01, R42, R43)

lmcode source lives in a data-embedding block of an lmscript file:

```text
program = _lmcode_ schema="host.schema.json";
  let x = 1;
  # ... body lines ...
end _lmcode_
```

- The opener line is `NAME = _lmcode_ OPTIONS;` — the `;` is mandatory. Options are string-literal
  `key=value` pairs. Exactly one of `schema="FILE"` (a schema file, resolved like an import) or
  `cli="PROGRAM [WORD...]"` (R42: the schema is what `PROGRAM WORD... --lmcode-schema --json` prints;
  the words are fixed subcommands of a multi-schema host) is required. `install="github:OWNER/REPO@TAG"`
  (R43) may accompany a `cli=` with a bare program name: a program missing from PATH is downloaded
  from that pinned release, checksum-verified, into the tool cache.
- The closer is a line exactly `end _lmcode_` at column 1. Blank lines and whole-line `#` comment
  lines are dropped by the block reader before the lmcode lexer sees them (heredoc bodies are
  exempt — they are preserved raw, §3.4).
- `_dsl_` is an accepted alias with identical meaning and identical diagnostics (the diagnostic
  prefix is always `_lmcode_`).
- The block value is opaque to lmscript (`type()` is `dsl` (the current literal type name); it has no text, keys or methods, R02).
  `savedsl(dsl, path)` writes the compiled bytecode atomically (R03); `dsl_cli(dsl)` returns the
  argv prefix `[absolute program path, WORD...]` of a `cli=` block's host (R43), so a script runs
  exactly the binary its bytecode is bound to.

### Mainline return writes and planned block execution

Compiler mainline slice 3 accepts write-only `$return = expr;`, `$return.name = expr;`,
and `$return[stringExpr] = expr;`. Root writes replace the owned JSON value; field writes
require a null/object root and replace or append one top-level key. Reads and nested
paths are rejected. Values are int, float, bool, string, `Json`, typed string/int/float
lists or maps, or the special complete RHS `null`. The C++ sink deep-copies values and
validates JSON numbers/UTF-8. Body and selected entries share the sink.

The C++/lmok sink and terminal frame (slices 1 and 8) and reverse-template extraction
(slice 5) are landed; cross-port adoption (slice 2) is in progress. These additions are
absent from the released **0.2.444** compiler used by this tutorial/CI baseline. The public
[host contract](host-protocol.md#return-sink-and-frame-contract) specifies ownership,
accepted values, number validation and failure silence.

Executing blocks `_lmcode_ HANDLE [out=EXPR];` and the `load_schema(...)` descriptor API
(slice 4) are landed in mono main at `0bc80277` (2026-10-31); they are absent from the released 0.2.444 compiler, and execution additionally needs a host that emits the terminal frame (the C++ SDK main does — verified end to end against `0bc80277` in the wp40 review; the samples do not yet, slice 6). `savedsl`, `dsl_cli` and `_dsl_`
remain the release compatibility path. Return writes do not imply automatic host execution.

## 3. Lexical rules

### 3.1 Comments and whitespace

`#` starts a comment that runs to the end of the line — anywhere in ordinary code, and also inside
a qw/qi/qf payload (§3.5). Inside a `"..."` string literal and inside a heredoc body it is data
(§3.3, §3.4). Spaces, tabs and carriage returns separate tokens and are otherwise ignored.

Identifiers match `[A-Za-z_][A-Za-z0-9_]*`. Keywords are:

```text
let if else true false for in range fn return switch case default while break continue implements
```

`qw`, `qi`, `qf`, `json` and `range`-like conveniences are **not** keywords; see §3.5 and §3.7 for
how they are recognized contextually. Punctuators: `=> == != <= >= && || ( ) { } ; , : . ! = < > + - * / % @`
and the heredoc opener `<<`. There is no shift operator; `<<` is reserved for heredocs
(`dsl-heredoc` R07). A `->` (as in a `fn` return type) is lexed as `-` then `>`.

### 3.2 Numbers

- Int literals are decimal digits: `0`, `-3`, `200`. No exponent, no suffix, no hex. An int literal
  may be at most 2^53 = 9007199254740992, the largest integer lmscript represents
  exactly (`dsl.ts` `MAX_INT_LITERAL`); the run-time `int` is a full 64-bit two's complement value
  (§4). A `-` directly before a number literal is the literal's sign, so `-9007199254740992` is one
  constant, not an operation.
- Float literals are `digits.digits` only: `1.0`, `-0.5`, `10.25`. No `1.`, no `.5`, no exponent,
  no suffix. (`qf(...)` words and `json` heredocs do accept exponent spellings, §3.5/§3.7.)
- Anything else (`1e3`, `0x10`, `1.`) is a located compile error
  (`malformed number ... (int: digits; float: digits.digits; no exponent, no suffix)`).

### 3.3 String literals

`"..."` on a single line, UTF-8 source. The only escapes are `\n \t \r \" \\`; any other backslash
sequence is a compile error. A string literal ends on its own line. Values are byte sequences: at
run time a string may hold host-provided NUL bytes or invalid UTF-8, even though source literals
are always UTF-8.

### 3.4 Heredoc string literals (`dsl-heredoc` R01–R07)

`<<TAG` (raw) and `<<~TAG` (raw, dedented) are multi-line string literals:

```text
let page = <<~HTML;
  <html>
    <body>${not_a_splice}</body>
  </html>
HTML
```

- `TAG` matches `[A-Za-z_][A-Za-z0-9_]*` and immediately follows `<<`/`<<~`. Quoted tags are
  rejected; there is no interpolating variant. The opening line is ordinary code (arguments,
  delimiters and the statement's `;` may stay on it); the body begins on the next physical line.
  Several heredocs on one code line queue their bodies in opener order.
- A plain body ends at a line exactly equal to `TAG` at column 1. A `<<~` closer may additionally
  be indented with spaces/tabs (nothing else on the line). The closing line and the opening line's
  newline are excluded; every body line contributes its text plus LF — an immediate closer yields
  the empty string. LF, CRLF and CR sources all normalize to LF.
- Bodies are raw: no escapes and no `${...}` interpolation, and the outer block reader drops
  nothing inside a body (blank lines, `#` lines and even `end _lmcode_`-looking text are data).
- `<<~` strips the minimum leading-whitespace count shared by the nonblank body lines; blank lines
  do not count and become empty. The removed indentation must be one uniform kind (all spaces or
  all tabs) within and across lines; mixed removed indentation is a located compile error.

### 3.5 Quote-list literals: `qw`, `qi`, `qf` (lmcode-literals R01/R02)

```text
let names  = qw(alpha beta gamma);      # StrList
let ids    = qi(-9223372036854775808 0 9223372036854775807);   # IntList
let ratios = qf(2 1.5 1e-3 -0);         # FloatList
```

- Recognized when `qw`, `qi` or `qf` is immediately followed by `(` and the name is **not** bound
  as a local, parameter, user function, schema function or context variable — an existing binding
  wins and the form is an ordinary call (sample-suite `205-literal-bindings` pins this; a member
  call `x.qw(...)` is never a literal). They are contextual primaries, not keywords.
- Words are separated by ASCII whitespace, newlines included, so a literal may span lines; `#`
  starts a comment to end of line. No quoting, escapes or nesting; `${` and `<<` sequences are
  rejected. A `qw` word is any run of non-control text without parentheses, quotes or backslash
  (commas are ordinary word bytes). An empty form yields a typed empty list.
- `qi` words must match `-?(0|[1-9][0-9]*)` within **signed int64 range** (parsed as arbitrary
  precision, then emitted as i64) — note this is wider than the ±2^53 limit for ordinary int
  literals. `qf` words must be finite JSON numbers, exponents included; integral tokens still emit
  float constants (`2` → `2.0`), never ints.
- Lowering: the list constructor (`str_list()`/`int_list()`/`float_list()`) followed by one `.add`
  per word in source order. The lowering refers to the standard catalog directly, bypassing lexical
  bindings of those names.

### 3.6 Map literals: `%(...)` (lmcode-literals R03)

```text
let config = %(name => "demo", mode => "fast",);   # StrMap; trailing comma allowed
let rates  = %(low => 1.25, high => 2.5);          # FloatMap
let counts = %("a" => 1, (key_fn(2)) => 3);        # IntMap; computed string keys parenthesized
let empty  = %();                                  # empty literal is StrMap
```

A bare identifier before `=>` is a literal string key; quoted strings and parenthesized string
expressions give other keys. Key then value are each evaluated exactly once, left to right. Values
must be homogeneous — string, int or float; the value type is inferred from the first entry and the
first differing value is a located error (no implicit widening). The result is `StrMap`, `IntMap`
or `FloatMap` accordingly. Duplicate keys overwrite the value without changing first-insertion
order. `%(` is recognized only where an expression can start; it is never fused with an infix `%`,
so `5%(2)` remains modulo (sample-suite `203-map-literals` pins both). Lowering is the map
constructor plus one `.set` per entry.

### 3.7 JSON heredoc literals (lmcode-literals R04/R05)

`json <<TAG` (or `json <<~TAG`) is a raw heredoc whose body is JSONC — strict JSON plus `//` and
non-nesting `/* */` comments and one trailing comma before `]` or `}`:

```text
let document = json <<~DOC;
  {
    // comments are allowed
    "limit": 9223372036854775807,
    "flags": [true, false, null,],
  }
DOC
```

The body is validated at **check time** (even when other `${}` fields defer compilation) and
normalized to a compact string constant that is passed to the standard `json_parse(string) -> Json`
(§10). Number and string token spellings and object key order survive into the compact form;
integer lexemes must fit signed int64; the maximum container nesting is 256. Source errors map back
to physical body positions. `json` is contextual like `qw`: a local, parameter, user function,
schema function or context variable named `json` wins, and `x.json <<T` is never a literal.

## 4. Types

| Type | Values | Literals | Notes |
|------|--------|----------|-------|
| `int` | 64-bit two's complement integer | `0`, `-3` | source literals ±2^53 (§3.2); arithmetic wraps on overflow — no trap (R34); division/remainder by zero are run-time errors, by a literal zero a compile error |
| `float` | IEEE-754 binary64 | `1.0`, `-0.5` | division and arithmetic follow IEEE; inf and NaN are ordinary values |
| `string` | byte sequences | `"..."`, `f"..."`, heredocs | may contain NUL/invalid UTF-8 at run time |
| `bool` | `true`, `false` | `true`, `false` | |
| `void` | no value | none | return types only; a void result cannot be stored or used as a value |
| object types | host handles | none | declared by the schema (§9); methods only, no fields; cannot be compared with `==`/`!=`; do not outlive the run |
| enum types | named constants | `Status.OPTIMAL` | declared by the schema; distinct static types (below) |
| `Json` | parsed JSON | `json` heredoc | the **only dynamically-shaped type**; standard, immutable (§10) |

There are no implicit conversions between primitive types. The explicit conversions are built-ins,
not schema names: `float(i)` widens an int (the only widening), `int(f)` narrows a float (truncate
toward zero, saturate at the i64 endpoints, NaN → 0), and `str(x)` renders one int (decimal), float
(`%.15g`), bool (`true`/`false`) or enum (its constant name) as text. Mixed int/float operands are a
compile error naming both types with the hint `(no implicit conversion: widen the int with
float(i))`. Separately, a schema may declare one-step conversions into object types and operator
mappings (§9); those never apply between primitives and never chain.

Enums: constants are written `Type.VALUE` and remain distinct from strings. Same-enum `==`/`!=` and
`str(enum)` are allowed; enum ordering, string-to-enum conversion and mixed enum/string equality
are not. On the wire an enum constant is its name string and there are no run-time enum checks —
the static type system is the whole guarantee.

There is no `any`, no null value in the core language, and no list/map type constructor in the type
system: lists, maps and other collections are schema object types with methods (R31), iterated
through `for (x in xs)` (§6) or indexed with `at(i)`.

## 5. Expressions and operators

Precedence, loosest first:

| Level | Operators | Operand rule |
|-------|-----------|--------------|
| 1 | `a \|\| b` | both bool; short-circuit |
| 2 | `a && b` | both bool; short-circuit |
| 3 | `==`, `!=` | same primitive or same enum type; objects cannot be compared |
| 4 | `<`, `<=`, `>`, `>=` | both int or both float; result bool |
| 5 | `+`, `-` | both int or both float; `+` on two strings concatenates (the right side must already be a string) |
| 6 | `*`, `/`, `%` | both int or both float; `%` is two ints only (no float remainder) |
| 7 | `!a`, `-a` | bool negation; numeric negation |
| 8 | `obj.method(args)` | postfix, chains allowed |
| 9 | primary: literal, local, context name, host call `fn(args)`, built-ins `float`/`str`/math, `qw`/`qi`/`qf`, `%(...)`, `json` heredoc, `( expr )` |

The instruction set is typed: the compiler picks `ADD_I` vs `ADD_F` from the operand types and the
VM performs no type checks (R34). Semantics pinned by the opcodes (`spec/bytecode.md`):

- Int arithmetic wraps in two's complement; `INT64_MIN / -1` wraps, `-INT64_MIN` is `INT64_MIN`,
  `INT64_MIN % -1` is 0. Int `/` truncates toward zero; `%` takes the dividend's sign. A zero
  divisor is a run-time error (`int division by zero` / `int modulo by zero`); a **literal** zero
  divisor is a compile error.
- Float arithmetic is IEEE binary64 round-to-nearest ties-to-even, without fused multiply-add,
  fast-math or flush-to-zero.
- `+` concatenates two strings with no size cap; use `str(x)` to convert a non-string right side.
- `&&`/`||` short-circuit; both sides must be bool. `!` needs a bool.
- Receiver and arguments of any call or operator are evaluated once, left to right; schema-declared
  conversions are emitted after the source expressions have been evaluated.

Lmscript can expand higher-level body constructs before this language is compiled;
see [the wrapper guide](../guides/lmscript-body-expansion.md).

### Built-in math (S4, R27/R34)

The compiler resolves these exact primitive signatures without host imports; the names are reserved
against host function declarations. All arguments evaluate once, left to right.

| Functions | Signatures | Semantics |
|-----------|-----------|-----------|
| `sin`, `cos`, `pow` | float args → float | platform libm; conformance allows `1e-12 * max(\|expected\|, 1e-300)` relative tolerance (see `spec/conformance.md`) |
| `sqrt`, `floor` | float → float | IEEE; `sqrt` of negative is NaN |
| `abs` | float → float; int → int | clears float sign; `abs(INT64_MIN)` wraps to itself |
| `min`, `max`, `clamp` | float or int pairs/triples | float min/max propagate NaN from either operand and choose the first operand on ties, including signed zero; clamp is `min(max(x, lo), hi)` even with reversed bounds |
| `lerp` | float ×3 → float | `a + (b − a) * t`, no clamping |
| `ease`, `ease_in`, `ease_out` | float → float | smoothstep / quadratic curves on `clamp(x, 0.0, 1.0)` |
| `int` | float → int | truncate toward zero, saturate at i64 endpoints, NaN → 0 |

All functions other than sin/cos/pow are exact binary64 (or integer) operations. NaN payload and
sign are unspecified.

## 6. Statements

| Form | Rule |
|------|------|
| `let x = expr;` | declares a local; type inferred from the initializer (no type annotations, no uninitialized declarations); void refused; redeclaration in the same block refused |
| `x = expr;` | assigns a declared local with exactly the same type; context objects are read-only |
| `name(args);` | a host/user function or method call; a non-void result is discarded. Any other expression statement is an error ("has no effect") |
| `if (c) { ... } else if (c) { ... } else { ... }` | `c` is bool; every branch is a braced block; blocks scope their `let`s |
| `while (c) { ... }` | `c` is bool, reevaluated each iteration (R38) |
| `for (i in range(start, end)) { ... }` | int bounds, step 1, end excluded (below) |
| `for (x in xs) { ... }` | iterate a schema collection object (below) |
| `switch (expr) { case VALUE: { ... } default: { ... } }` | int, string or enum (below) |
| `break;` / `continue;` | innermost enclosing `while`/`for`; a static error outside a loop; cannot cross a function boundary |
| `return expr;` | only as the final top-level statement of a value-returning `fn` (§7); an error everywhere else, including the chunk body |

Every simple statement ends with `;`. The bodies of `if`, `while`, `for` and switch arms are braced
blocks with no trailing semicolon. A block containing nothing but `fn` definitions is legal (R49);
a genuinely empty body is the compile error `the DSL body is empty`.

Name visibility: locals may not be named after context variables, host-declared functions, type or
enum names, keywords or the built-ins (`float`, `str`, the math names). **Implicit standard-catalog
names may be shadowed** by locals, parameters, user functions and loop variables (lmcode-std R05 /
issue 120): only names the host schema declares explicitly retain the no-shadowing rule.

### Range loops (S3)

`for (i in range(start, end)) { ... }` evaluates the two int bounds exactly once, left to right,
**before** binding the loop variable. The range has step 1 and excludes `end`; `end <= start` is an
empty loop. `i` is a fresh, read-only loop-local int: assignment to it or redeclaration inside the
body is a compile error. It may shadow an ordinary outer local (the bounds still read the outer
binding), but never a schema name or built-in. Loop-body locals are re-initialized on every
iteration; outer locals may be updated. Loops nest without a language depth cap. `range` is
reserved for the for header and is not a callable value. The counter cannot overflow: its last body
value is `end − 1`, correct even at the i64 endpoints.

### Collection loops (R36)

`for (x in xs) { ... }` requires `xs` to have a schema object type declaring exactly one
`len() -> int` and one `at(int) -> T` method with non-void `T`. The compiler evaluates `xs` once,
snapshots `len()` before the body runs, and loads `xs.at(i)` into a scoped, read-only `x` at the
top of each iteration (`i` counts from 0). No list type or iteration opcode exists; the form lowers
to the range loop plus method calls.

### While loops and control transfer (R38)

`while` may not terminate; termination and resource use are the author's responsibility — the
language and VM impose no iteration, time or memory budget (R34). `break` exits and `continue`
starts the next iteration of the innermost enclosing loop of any kind. A `switch` arm is not a loop
boundary, so `break` inside an arm targets the surrounding loop; `break` is not a switch statement.

### Switch (R37)

`switch (expr)` accepts int, string and enum expressions, evaluated once. Case values are integer
literals (optionally negative), string literals, or constants of the switched enum (`Mode.READY`);
they must be unique. There is no fallthrough and no `break` between arms. `default` occurs at most
once and must be last. A switch needs at least one arm; a default-only switch is valid. An enum
switch without `default` must cover every enum member.

## 7. Functions and compile-time inlining (R35)

```text
fn shifted(x: int, amount: int) -> int {
  return x + amount;
}
```

- Definitions are top-level only and are collected before the body is compiled, so a call may
  appear before its definition. Parameter and return types are primitives, schema object types or
  enum types; `void` is permitted only as the return type.
- Calls are checked for exact arity and exact parameter types. Unlike host calls, user-function
  calls never apply schema-declared conversions.
- A value-returning function has exactly one `return expr;`, as its final top-level statement;
  conditional or early returns are compile errors (write them with a local). A `void` function has
  no return statement.
- A function cannot recurse, directly or mutually — the compiler reports
  `recursive user functions are not allowed (cycle: A -> ... -> A)`. This is pinned end-to-end by
  the sample-suite compile-error case `recursive-inline.lms` (see `spec/conformance.md`): there is
  no recursive call stack in the bytecode, so recursion cannot ever be admitted.
- Functions cannot nest, cannot capture the caller's locals, and are not values (no references, no
  function-typed variables). They may read context objects and call schema functions/methods and
  other user functions.
- Function names must not collide with host functions, context names, schema type/enum names,
  built-ins, keywords or other user functions (implicit std names excepted, §6).

Inlining is purely a compiler operation: each call site expands the callee body with fresh local
slots for parameters and locals, and arguments are compiled once, left to right. No function name,
call instruction or runtime call stack reaches the bytecode. Consequences:

- Unused, unannotated functions are type-checked (once, without expanding their callees) and emit
  no code.
- Output grows with the number and size of call sites; nested branching call chains multiply
  exponentially (ten levels of two calls emit 1024 leaf bodies). Use loops for repeated work.
- Errors inside a function identify the function's own source line; expanded instructions carry
  line-table entries pointing at the definition.

## 8. Rule entries: `@NAME` and `implements` (R47, R48, R49)

A top-level function may be declared as a **rule** — a host-dispatched callback, SonarQube-style:

```text
@PAIR
fn no_password_key(n: Node) -> void implements Rule {
  if (n.kind() == "pair" && n.text() == "password") { out.report("password key", 1); }
}
```

- `@NAME` is allowed only directly before a top-level `fn`. The name is any identifier, keyword
  spellings included (`@if` is legal — tree-sitter anonymous node kinds are keyword spellings); it
  is never resolved and duplicates across functions are allowed (many rules may subscribe to the
  same node kind). Any other position for `@` is a located compile error.
- `implements NAME` is required on an annotated function (`annotated rule 'NAME' requires an
  implements interface`, pinned by the sample-suite `rule-annotation-without-implements.lms`
  compile-error case) and optional otherwise. `NAME` must be one of the schema's `interfaces`
  (R48; see `spec/schema.md`), and the function's signature — parameter count, parameter types in
  order, return type — must match the interface exactly, with no conversions (`rule-method-mismatch.lms`
  pins a mismatch). `implements` is a keyword everywhere else.
- An annotated rule compiles to a separate **entry** in the bytecode file, in source order, even if
  the body never calls it. Entries are independent mini-programs sharing the file's constant,
  import and context pools; the host enumerates them and invokes them through the SDK's
  `call(entry, args)` with the arguments it chooses. A non-void entry returns its single final
  value to the host; a value rule still follows the one-final-`return` rule.
- The chunk body and the entries are distinct: the host runs the body as the program's main effect,
  and dispatches entries separately. A body call to a rule's name is ordinary inlining and does not
  touch the entry table; a plain or `implements`-only function is never an entry. There is no
  CALL/RET instruction and no runtime call stack (R49). The wire-level entry rules are in
  `spec/bytecode.md`.

## 9. How the schema drives what a program can call

Every name a chunk can refer to comes from exactly one of:

1. the **host schema** (`dsl.schema` 2; full format in `spec/schema.md`): `types` (object types
   with methods), `functions` (host functions), `context` (host-owned context objects, read-only),
   `enums`, `conversions`, per-type `operators`, and `interfaces` for rules (R48);
2. the **implicit standard catalog** (§10), merged into the effective schema by default;
3. the **language built-ins**: `float`, `str`, and the math functions of §5.

Calls resolve statically. For an overloaded host function or method, an exact parameter-tuple match
wins; otherwise a candidate may use at most one schema-declared conversion per argument, and all
such candidates compete equally — more than one is an ambiguity error listing them, not a ranking.
Return types never select an overload. Conversions target object types and cannot chain. A schema
`operators` map (`+`, `-`, `*`, `neg`, `r+`, `r-`, `r*`) maps arithmetic on object types to
existing methods, so `expr + 2` compiles to an ordinary resolved method call; relational operators
stay numeric-to-bool.

The binding is cryptographic: the compiler hashes the exact schema bytes (SHA-256) into the
bytecode header, and the runtime refuses a mismatch before anything executes. Every call the
compiler emitted becomes a canonical-signature import (`fn NAME(T1, T2) -> R`,
`method Type.name(T1) -> R`) that the loader resolves against the host registry by full signature
at load time — so a program can only ever invoke what the host declares. The import table holds at
most 65535 distinct callees (`too many distinct callees`); locals per region and operand depth are
likewise capped by the u16 format fields at 65535, with compile errors naming the limit.

## 10. The standard library (overview)

Every block type-checks against the implicit **lmcode std** catalog: the compiler merges the
canonical, digest-pinned declarations (`lmcode-std.schema.json`, catalog version 3) into the
effective schema before resolving types (lmcode-std R01–R09). A host schema that redeclares a
standard signature identically is deduplicated; a *different* signature under a standard name is a
located schema error. New method names on standard types are allowed as host extensions. The full
reference — every signature, semantics and error text — is `spec/std.md`; the groups:

| Group | Contents | Scale (release 0.2.444) |
|-------|----------|----------------------|
| string | `str_len`, `str_contains`, `str_find`, `str_replace`, `str_split`, case/trim/prefix/suffix tests, `str_to_int`/`str_to_float` and inverse checks, `str_repeat`, `str_match`, plus `template_render` | 18 signatures |
| math | `math_abs/ceil/floor/max/min/pow/round/sqrt`, each with int and float overloads | 16 signatures (8 names) |
| encoding | strict byte codecs `str_base64_encode/decode`, `str_hex_encode/decode` | 4 signatures |
| file | `file_read`, `file_write`, `file_append`, `file_exists`, `file_lines` (raw bytes; located `FUNCTION: PATH: reason` errors) | 5 signatures |
| collections | typed lists/maps: `IntList`, `FloatList`, `StrList` (+`join`), insertion-ordered `IntMap`, `FloatMap`, `StrMap` (with `keys`/`values` snapshots) | 58 signatures |
| containers | `Int/Float/Str` × `Stack`, `Queue`, `PQ` (priority queue: min priority first, insertion-order ties) | 69 signatures |
| json | `json_parse(string) -> Json` (strict JSON; the heredoc of §3.7 lowers to it) and the immutable `Json` navigation: `kind/len/at/get/has/keys/as_*`, `to_json` | 12 signatures |

The released 0.2.444 bundle has 181 signatures. C++ main `aaa9088` has **206**,
including 24 `lmcode_return_*` overloads for the mainline write-only return sink.
The [generated inventory](std-signatures.md) describes that mainline catalog; see
[std.md](std.md) for revision/digest differences and return helper semantics. Do not
assume byte-identical compiler and SDK catalog pins from the shared v3 name.
Standard objects live in a per-run arena with a shared 65,536-object limit;
`qw`/`qi`/`qf`, `%(...)` and `json` literals lower to constructors and methods.

Testing helpers (`print`, `assert_close`) are **not** part of the catalog: they stay explicit host
declarations (lmcode-std R02), which is why the conformance and sample hosts register them
themselves.

## 11. Compile-time vs run-time

- **`${expr}` splices (R15).** Inside a block, `${expr}` is a pre-process step: the lmscript value
  becomes an lmcode literal before compilation, so the compiler type-checks the result and a splice
  cannot change the program's structure. Strings and bools become their literals; a number becomes
  an int literal when integral within ±2^53 (larger integral values are errors), otherwise an exact
  `digits.digits` float literal. Nonempty lists of strings or numbers
  become `qw`/`qi`/`qf` literals; maps with homogeneous string/int/float values become
  `%()` literals (an empty map is accepted). Lists/maps are limited to 10,000 elements/entries.
  Numeric mixtures promote to float when needed; string/number mixtures are rejected.
  Empty lists, bool or nested collections, null, and numbers requiring an
  exponent are rejected at the field. String-list words must obey the quote-word restrictions
  (no whitespace, quotes, parentheses, backslash, comment marker, interpolation/heredoc
  openers, control characters or invalid surrogate values). lmscript has one number type, so `${3.0}` is the int `3` — write `float(${n})` where a
  float is required.
- **Check time.** A block whose fields are all literal is fully compiled at `lmctl script --check`;
  a computed `${}` field defers compilation to evaluation. `json` heredoc bodies are validated at
  check time even when other fields defer. A `cli=` schema query runs in every mode, `--check`
  included, because the schema is needed to check the body (it is cached per process, R42).
- **Run time.** The compiled bytecode is data-independent of the script's evaluation: host values,
  context objects and entry arguments arrive at run time. There are no dynamic type checks in the
  VM (R34); the remaining run-time failures are the ones in §12. There is no instruction, memory or
  time budget — non-termination and resource use are the author's (and the host's) responsibility.

## 12. Errors and diagnostics

**Compile errors** are located: `error:FILE:LINE:COL: _lmcode_: MESSAGE` at the body position,
mapped back through `${}` substitutions; exit code 2, before any effect, and reported in untaken
branches too (the whole chunk is checked, not just reachable lines). Messages name what was
expected and found, e.g. `method Response.status expects int for argument 1; found string`,
`undefined name 'foo' (locals are declared with let; the schema provides: req, res, now_date)`,
`if condition must be bool; found string`. Schema files that are themselves malformed fail with
`schema FILE: ...` errors. (One cosmetic caveat: the current "expression statement" error text
reads `only calls, let, assignment and if are statements` — the list is stale; `while`, `for`,
`switch`, `break` and `continue` are statements too. The message is a wording bug in `dsl.ts`, not
a language rule.)

**Load errors** (bad bytes, schema-hash mismatch, unbound imports, verifier failures) are raised by
the runtime before anything executes; they carry codes `LOAD_BAD_BYTECODE`,
`LOAD_SCHEMA_MISMATCH`, `LOAD_UNBOUND` and have no source location. The full taxonomy is
`spec/bytecode.md` §"Loader error codes".

**Run-time errors** keep the code and gain the faulting instruction's source position (S5):

- `RUN_ERROR` — a VM-detected failure: division or modulo by zero, reading an unassigned local,
  `method T.M called on a X`, a non-bool condition, and similar.
- `RUN_HOST` — a host function or method threw, std contract violations (e.g. `Json.get: missing
  key`, `IntStack.pop: empty`), or host-side API misuse such as a wrong argument count to
  `call(entry, ...)`.
- `APP_FAIL` — the host's own application failure; exit code 4.

When the region's line table covers the faulting pc, the message becomes `dsl line N:C: MESSAGE`
(one-based; a column of 0 means unavailable and the message is `dsl line N: MESSAGE`). An empty
line table is valid and yields the unlocated message. CLI hosts print exactly one JSON result line
(`{"ok": true, "result": ...}` or `{"ok": false, "phase": ..., "code": ..., "message": ...}`), with
exit codes 2 compile / 3 host load-or-run / 4 application (R26/S0′); the full CLI protocol — flags,
records, exit codes — is `spec/host-protocol.md`.

## 13. Language ↔ bytecode version map

The compiler emits DSLB **v6** (`DSL_VERSION = 6`; first published in `@lmctl-ai/lmctl` 0.2.444;
0.2.442/0.2.443 accept the rule syntax but still write v5). v6 added the rule-entry table (R47–R49)
without any new opcode; v5 added structured `while`; the literal forms of §3.5–§3.7 are pure
compiler lowerings onto existing instructions. The opcode surface each construct compiles to is
documented per instruction in `spec/bytecode.md`.
