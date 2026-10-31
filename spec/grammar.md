# The lmcode language — grammar companion

Status: EXPERIMENTAL. Normative grammar: [`grammar.ebnf`](grammar.ebnf) (W3C EBNF, the
subset documented in its header). Authoritative implementation: `lmscript/dsl.ts` in
github.com/lmctlhq/lmctl-mono using lmcode bytecode (DSLB v6): the lmctl 0.2.444 baseline plus mainline
slice-3 `$return` writes, cross-checked against lmcode-cpp `aaa9088` return vectors. This document explains
the grammar and lists what it deliberately does NOT say. Verification: `tests/grammar/`
(the EBNF is machine-checked against the real compiler; see the README there).

lmcode is a small, strongly typed, one-chunk language: a host program hands the chunk a
context of objects and functions and runs it as a callback. Released 0.2.444 exposes
host-call effects; mainline also supports writes to an invocation return sink. It ships inside an lmscript `_lmcode_` block
(`_dsl_` remains an accepted alias) or standalone to the compiler.

## The grammar by section

**Lexical (Part A).** Whitespace (space, tab, CR) and `#` comments to end-of-line are
skipped between tokens; newlines are insignificant except that a string literal ends on
its line, heredocs are line-oriented, and qw/qi/qf lists separate words on whitespace.
Identifiers are `[A-Za-z_][A-Za-z0-9_]*`. Integers are plain digits (bounded by 2^53 —
see static semantics). Floats are exactly `digits.digits`: no exponent, no suffix, and
never a bare `.` side. Strings are double-quoted with exactly five escapes
(`\n \t \r \" \\`). Heredocs (`<<TAG` raw, `<<~TAG` dedenting) close on a line whose text
is the tag (dedent form allows leading indentation); the opener line may carry more code
after the tag. `qw(...)`/`qi(...)`/`qf(...)` are flat word-list literals for
string/int/float collections, and `%(...)` is a map literal with `=>` entries.
`json <<TAG ... TAG` is a normalized JSON document literal.

**Structure.** A program is a sequence of top-level items: function definitions
(optionally annotated) and statements. A function is
`@NAME? fn name(param: Type, ...) -> Type (implements Iface)? { ... }`; the annotation is
entry metadata for host dispatch and its name is never resolved (a keyword spelling names
an anonymous node kind). Statements: `let` declaration, assignment, `if`/`else if`/`else`
with mandatory braced blocks, `for (i in range(a, b))` and `for (x in xs)` loops, `while`,
`switch` with braced arms, `break;`/`continue;`, and expression statements. A
value-returning function ends in exactly one top-level `return expr;`.

**Expressions** descend through the usual ladder — `||`, `&&`, `==`/`!=`, the four
relational operators, `+`/`-`, `*`/`/`/`%`, unary `!`/`-`, then postfix method calls
(`obj.m(args)`, chains allowed), then primaries: literals, parenthesized expressions,
names, calls, and the collection literals. `&&` and `||` short-circuit. There is no
ternary, no assignment expression, and no general indexing operator (collections are schema
objects with `at(i)`). The mainline write-only `$return[stringExpr]` target is the sole
indexing exception; it cannot be read. There is no lambda. A minus directly before a number literal is the literal's
sign — `-0.5` is one constant.

**The outer block (Part C).** In lmscript the chunk lives in a data block:
`program = _lmcode_ schema="file.dsl.json";`, body lines, then `end _lmcode_` at column 1
(spelling must match the opener; `_dsl_` aliases `_lmcode_`). The schema option is
required and literal; `cli="PROGRAM [WORD...]"` reads the schema from the program itself
(`PROGRAM WORD... --lmcode-schema --json`) and is mutually exclusive with `schema=`;
`install="github:OWNER/REPO@TAG"` (only with a bare `cli` name) pins where a missing host
binary is fetched from. `load_schema` does not exist at lmctl 0.2.444 — the header forms
are exactly `schema=`, `cli=`, `install=`. `${ }` fields are pre-process substitutions of
lmscript values as lmcode literals (string, int within ±2^53, `digits.digits` float, bool, or
a qw/qi/qf/`%()` collection) spliced before the inner lexer runs; a computed field defers
compilation to run time. Blank lines and whole-line `#` comments are dropped before the
inner grammar sees the body.

**Mainline return writes.** `$return = expr;`, `$return.name = expr;` and
`$return[stringExpr] = expr;` are included in the grammar for slice 3. A literal `null`
is also accepted as the complete RHS. Released **0.2.444 rejects these forms**; the
corpus parse check uses mainline return vectors, while differential checks using
0.2.444 establish only the shared baseline. The harness probes return support and reports
its exact unsupported-dollar disagreements separately as `compiler-baseline`. Executing blocks and `load_schema`
are landed in mono main at `0bc80277` (2026-10-31); they are absent from the released 0.2.444 compiler, and execution additionally needs a host that emits the terminal frame (the C++ SDK main does — verified end to end against `0bc80277` in the wp40 review; the samples do not yet, slice 6). See the public [return contract](host-protocol.md#return-sink-and-frame-contract).

## Static semantics, not grammar

The EBNF accepts a slightly larger language than the compiler; each gap is a deliberate
split, checked by `dsl.ts` and listed here (the differential harness in `tests/grammar/`
classifies compiler rejections against exactly this list):

- **Return writes (mainline).** Targets are root or one-level keys only. The index
  expression must be string; nested paths and reads are rejected. Values are bool,
  string, int, float, `Json`, or typed `StrList`/`IntList`/`FloatList`/`StrMap`/`IntMap`/`FloatMap`,
  plus the special null RHS; other opaque objects are rejected. Sink serialization and numeric validation follow the
  [host contract](host-protocol.md#return-sink-and-frame-contract).
- **Types.** Every expression has exactly one static type; no implicit conversions
  between primitives (`float(i)` widens, `int(f)` narrows, `str(x)` stringifies).
  `void` is a return type only. Mixed `int`/`float` operands are errors naming both types.
- **Name resolution against the host schema.** A bare name is a declared local, then a
  context object, then (with a call) a host function or user function or built-in;
  anything else is `undefined name 'x' (… the schema provides: …)`. A name may not shadow
  a schema name or built-in. Method calls type-check against the receiver's schema type
  (overload resolution: exact match first, then one declared conversion; ambiguity is a
  compile error).
- **Enum constants.** `Mode.READY` is an enum constant only when `Mode` is a schema enum
  and `READY` one of its values; otherwise the dotted form is a method call and must be
  called. Enum values have no methods and cannot be compared across types.
- **The call-only statement rule.** An expression statement must be a call; anything else
  "has no effect". A non-void call result is discarded.
- **`let` discipline.** One declaration per name per block; the type is inferred from the
  initializer; schema names cannot be shadowed; void initializers refused.
- **Loop rules.** `for` counters and `foreach` variables are read-only; `range` bounds are
  ints evaluated once; a `foreach` collection needs exactly `len() -> int` and
  `at(int) -> T`. `break`/`continue` target the innermost loop and cannot cross a function
  boundary.
- **Switch.** The expression is int, string or enum; case values are literals of that
  type (enum constants for enums), unique, `default` at most once and last; enum switches
  without a default cover every member.
- **Functions.** No recursion or mutual recursion (the expansion cycle is a compile
  error), no nesting, no capturing caller locals, no functions as values. An annotated
  rule requires `implements`, the interface must exist in the schema, and the signature
  must match it exactly — parameter types in order and return type, no conversions.
- **Inlining limits.** User calls are compiler-inlined: code and local slots grow per call
  site (a call inside a loop is emitted once with that loop body; deep branching call
  graphs multiply output — the spec's own warning is "use loops for repeated work"), and
  the format caps locals/imported callees/stack depth at 65535 each (compiler errors, not
  grammar).
- **Literal bounds.** Int literals and `${}` integers stay within ±2^53 (what lmscript
  represents exactly); `qi` words are int64-range signed decimals; `qf` words are finite
  JSON numbers. A literal zero divisor is a check error (a computed one is a run-time
  error).

## Keywords and reserved words (from the compiler)

Reserved words — `dsl.ts` `KEYWORDS`, never usable as identifiers (except as annotation
names, which are never resolved):

| keyword | role |
| --- | --- |
| `let` | local declaration |
| `if` `else` | conditional (mandatory braced blocks) |
| `true` `false` | boolean literals |
| `for` `in` `range` | loops (`range` is reserved everywhere, not only in headers) |
| `fn` `return` | function definition and its single final return |
| `switch` `case` `default` | switch |
| `while` | loop |
| `break` `continue` | loop control |
| `implements` | rule-interface binding |

Contextually special but NOT reserved: `void` and `self` (type positions / method returns
in schemas), the built-ins `str` and `float` (callable; not declarable as variables or
schema names), the math built-ins `int abs min max clamp lerp ease ease_in ease_out sin
cos sqrt floor pow` (callable with exact primitive signatures; reserved against schema
function declarations), `json` (a literal marker only when directly followed by a
heredoc — elsewhere an ordinary name; the corpus calls `json(4)`), `qw` `qi` `qf`
(collection literals only as `qw(` etc. not after `.` or `fn`), `end` (only in the outer
block closer), and the block markers `_lmcode_` / `_dsl_` themselves.

Mainline return writes add `$`, `[` and `]` punctuators and the contextual null RHS.

Punctuators: `=> == != <= >= && || ( ) { } ; , : . ! = < > + - * / % @`. The function
arrow `->` is two tokens in the compiler (`-` then `>`), and this grammar writes it the
same way — whitespace between them is accepted, exactly as the compiler accepts
`fn f() - > int {}`. No expression context can produce `-` directly followed by `>`.

## For parser writers (the tree-sitter cross-check)

The grammar is **LALR(1)** — `lark` in strict mode reports no conflicts — so it is
LR/GLR-friendly by construction. The awkard bits are lexical, not syntactic:

- Heredocs need tag-equality between opener and closer (not expressible in EBNF or a plain
  regular terminal): both this checker and `dsl.ts` handle them procedurally. A tree-sitter
  grammar needs an external scanner for the same reason.
- `qw(`/`qi(`/`qf(` switch lexical mode (word lists until the balanced `)`), and only when
  the previous token is not `.` or `fn` — a one-token lookbehind.
- `json` + heredoc is one literal only when `json` is not a declared name.
- `%(` opens a map literal in primary position while `%` is the modulo operator; the
  compiler lexes them as two tokens and lets the parser's state decide, which is what this
  grammar does too.
