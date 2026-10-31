# Writing lmcode programs — a tutorial

Status: current for compiler `@lmctl-ai/lmctl` **0.2.444** (DSLB v6) and the `lmcode-cpp-sample`
reference host. This is the tutorial for people who **write** lmcode programs; it teaches by
example and cites the specs instead of repeating them:

- Language rules (types, operators, statements, functions, rule entries): `spec/language.md`.
- What a host schema can declare: `spec/schema.md`.
- Host CLI flags, result records, exit codes: `spec/host-protocol.md`.
- The standard catalog (`str_*`, `math_*`, collections, `Json`, …): `spec/std.md`.
- The test corpus every example pattern comes from: `spec/conformance.md` and the sample suite
  (`lmcode-cpp/sample-suite/`, programs `001`–`069`).

**The 13 runnable lmcode examples were compiled with `lmscript` 0.2.444 and run against
`lmcode-cpp-sample`; their stdout below is pinned verbatim. The two compile-error examples
are intentional refusal controls.** Paths in
diagnostics (`/tmp/lmtut/…`) are the scratch directory the examples were verified in — yours will
differ. The undefined-name diagnostic below is abbreviated: its scope inventory follows
the host/catalog; runtime stdout examples are exact.

## 1. What you need

Two things: the **compiler** and a **host**. An lmcode program never runs standalone — it is one
chunk of statements that a host program runs as a callback inside a context the host owns
(`spec/language.md` §1). The compiler turns your source into a `.dslb` bytecode file; the host
loads and executes that file. The two never swap jobs.

**The compiler** ships as the npm package `@lmctl-ai/lmctl` (Node 24 required). Install it into a
prefix and put its `bin` on your PATH:

```sh
npm install --prefix ~/.local/lmctl @lmctl-ai/lmctl@0.2.444
export PATH="$HOME/.local/lmctl/node_modules/.bin:$PATH"
```

That gives you the `lmscript` binary, which compiles `_lmcode_` blocks (this tutorial's examples
were verified with exactly this install, in a different prefix).

**The reference host** is `lmcode-cpp-sample`, a small shop application (C++17, Make, Python 3 —
nothing else). Clone it and build:

```sh
git clone https://github.com/lmctl-ai/lmcode-cpp-sample
cd lmcode-cpp-sample && make
export PATH="$PWD/build:$PATH"
```

Sanity check — every lmcode host answers these flags (`spec/host-protocol.md` §"Flags"):

```sh
lmcode-cpp-sample --dsl-schema --json   # the exact schema bytes the compiler compiles against
lmcode-cpp-sample --dsl-signatures      # every callable signature, one per line
```

## 2. Your first program

lmcode source lives inside an `_lmcode_` block in an lmscript (`.lms`) file — the block boundary
rules are `spec/language.md` §2. Save this as `hello.lms`:

```text
program = _lmcode_ cli="lmcode-cpp-sample";
let n = 7;
print("hello from lmcode: " + str(n));
end _lmcode_
savedsl(program, ARGV[0]);
```

- `cli="lmcode-cpp-sample"` tells the compiler to ask the host binary on your PATH for its schema
  (the `--dsl-schema --json` query, R42 in `spec/schema.md`), so the program is always compiled
  against the exact host that will run it.
- `print` and the context objects below are declared by the host's schema; `str` is a language
  built-in (`spec/language.md` §4).
- `savedsl(program, ARGV[0])` writes the compiled bytecode to the path you pass as the script's
  first argument.

Compile it (two steps: a check, then the real run that produces the `.dslb`):

```sh
lmscript --check hello.lms        # silent, exit 0: the block type-checks
lmscript hello.lms hello.dslb     # writes hello.dslb
```

Run it through the host:

```sh
lmcode-cpp-sample --dsl hello.dslb
```

Output — pinned verbatim:

```text
hello from lmcode: 7
{"ok": true, "result": {"balance": 0, "entries": 0, "note": "", "entries_called": 0}}
LMCODE_RETURN_BEGIN
null
LMCODE_RETURN_END
```

The first line is the program's trace (whatever `print` wrote). The JSON **result record**
reports success plus the host's own summary (here the shop's final ledger state). Current
C++ sample main then emits a terminal return frame. These programs make no return-sink
writes, so its value is `null`; the published compiler still treats the block as opaque. The record format and exit codes are `spec/host-protocol.md` §"The result
record"; this run exited 0.

Instead of `cli=`, a block may name a schema **file** with `schema="FILE"` (resolved like an
import). The file must be the host's exact schema bytes — for the sample hosts that is
`sample-suite/sample.dsl.json` (the domain declarations merged with the standard catalog;
`host.schema.json` holds the domain only, see `spec/conformance.md` §"The sample suite"). With a
copy of that file next to your script:

```text
program = _lmcode_ schema="sample.dsl.json";
print("hello via schema file");
end _lmcode_
savedsl(program, ARGV[0]);
```

Output — pinned verbatim (compiled and run exactly as above):

```text
hello via schema file
{"ok": true, "result": {"balance": 0, "entries": 0, "note": "", "entries_called": 0}}
LMCODE_RETURN_BEGIN
null
LMCODE_RETURN_END
```

Both forms bind the bytecode to the schema's SHA-256, so a program compiled one way cannot run
against a different schema — see §6 below.

## 3. The core language, by example

The full rules live in `spec/language.md` §3–§7; each example below names the section it
illustrates.

### Types and arithmetic (§4, §5)

`int` is 64-bit two's complement, `float` is IEEE binary64, and there are **no implicit
conversions** — widen with `float(i)`, narrow with `int(f)`, render with `str(x)`:

```text
program = _lmcode_ cli="lmcode-cpp-sample";
let cents = 1299;
let rate = 0.075;
let with_tax = float(cents) * (1.0 + rate);
print("cents " + str(cents) + " with tax " + str(with_tax));
print("int math " + str((7 + 3) * 2 / 4));
end _lmcode_
savedsl(program, ARGV[0]);
```

Output — pinned verbatim:

```text
cents 1299 with tax 1396.425
int math 5
{"ok": true, "result": {"balance": 0, "entries": 0, "note": "", "entries_called": 0}}
LMCODE_RETURN_BEGIN
null
LMCODE_RETURN_END
```

### Wrapping int64 (§4, §5)

Int arithmetic **wraps** on overflow — no trap. Note that source literals are capped at ±2^53
(§3.2), so `INT64_MAX` is built from smaller literals here:

```text
program = _lmcode_ cli="lmcode-cpp-sample";
let hi = 9007199254740991 * 1024 + 1023;   # INT64_MAX
print(str(hi));
print(str(hi + 1));
end _lmcode_
savedsl(program, ARGV[0]);
```

Output — pinned verbatim:

```text
9223372036854775807
-9223372036854775808
{"ok": true, "result": {"balance": 0, "entries": 0, "note": "", "entries_called": 0}}
LMCODE_RETURN_BEGIN
null
LMCODE_RETURN_END
```

The one arithmetic failure is a zero divisor: a *literal* zero is a compile error, a computed zero
is a run-time error — shown in §6.

### Strings (§3.3, §10)

`+` concatenates strings (the right side must already be a string — use `str(x)`). Functions like
`str_upper`/`str_len`/`str_replace` come from the standard catalog, not the language
(`spec/std.md`):

```text
program = _lmcode_ cli="lmcode-cpp-sample";
let name = str_upper("lmcode");
print(name + " has " + str(str_len(name)) + " chars");
print(str_replace("a-b-c", "-", "+"));
end _lmcode_
savedsl(program, ARGV[0]);
```

Output — pinned verbatim:

```text
LMCODE has 6 chars
a+b+c
{"ok": true, "result": {"balance": 0, "entries": 0, "note": "", "entries_called": 0}}
LMCODE_RETURN_BEGIN
null
LMCODE_RETURN_END
```

### Lists and maps: `qw()` and `%(...)` (§3.5, §3.6, §6)

Quote-word literals build lists, `%(...)` builds maps, and any object with `len()`/`at(int)` —
standard lists included — iterates with `for (x in xs)`:

```text
program = _lmcode_ cli="lmcode-cpp-sample";
let names = qw(alpha beta gamma);
print(names.join(","));
let stock = %(apples => 3, pears => 5);
print("pears " + str(stock.get("pears")));
for (n in names) {
  print("name " + n);
}
end _lmcode_
savedsl(program, ARGV[0]);
```

Output — pinned verbatim:

```text
alpha,beta,gamma
pears 5
name alpha
name beta
name gamma
{"ok": true, "result": {"balance": 0, "entries": 0, "note": "", "entries_called": 0}}
LMCODE_RETURN_BEGIN
null
LMCODE_RETURN_END
```

(`qi(...)` and `qf(...)` are the int and float word-literal forms; `json <<TAG` heredocs build
`Json` values — §3.7, and the std example below.)

### Control flow: `if` / `while` / `for` / `switch` (§6)

```text
program = _lmcode_ cli="lmcode-cpp-sample";
let total = 0;
for (i in range(1, 5)) {
  total = total + i;
}
while (total < 12) {
  total = total + 3;
}
if (total >= 12) { print("total " + str(total)); }
switch (total) {
  case 12: { print("twelve"); }
  case 13: { print("thirteen"); }
  default: { print("other"); }
}
end _lmcode_
savedsl(program, ARGV[0]);
```

Output — pinned verbatim:

```text
total 13
thirteen
{"ok": true, "result": {"balance": 0, "entries": 0, "note": "", "entries_called": 0}}
LMCODE_RETURN_BEGIN
null
LMCODE_RETURN_END
```

`range(start, end)` counts up by 1 and excludes `end`; `switch` takes int, string or enum
expressions and has no fallthrough (§6).

### Functions — and why there is no recursion (§7)

User functions are typed and **inlined at compile time**; a value-returning function has exactly
one `return`, as its final statement:

```text
program = _lmcode_ cli="lmcode-cpp-sample";
fn fee_cents(amount: int, pct: int) -> int {
  return amount * pct / 100;
}
let price = 1299;
print("fee " + str(fee_cents(price, 8)));
end _lmcode_
savedsl(program, ARGV[0]);
```

Output — pinned verbatim:

```text
fee 103
{"ok": true, "result": {"balance": 0, "entries": 0, "note": "", "entries_called": 0}}
LMCODE_RETURN_BEGIN
null
LMCODE_RETURN_END
```

Because calls are inlined, recursion is impossible — there is no call stack in the bytecode. The
compiler rejects it at check time (`--check` output pinned verbatim, exit 2):

```text
program = _lmcode_ cli="lmcode-cpp-sample";
fn recur(x: int) -> int {
  return recur(x);
}
print(str(recur(1)));
end _lmcode_
savedsl(program, ARGV[0]);
```

```text
error:/tmp/lmtut/recursion-error.lms:3:10: _lmcode_: recursive user functions are not allowed (cycle: recur -> recur)
```

Inlining also means output grows with call sites — use loops for repeated work (§7).

### The standard library (§10, `spec/std.md`)

Every block type-checks against the implicit standard catalog: string, math, encoding, file,
collections, containers and json groups — 182 signatures. One per group here; the full reference
is `spec/std.md` / `spec/std-signatures.md`:

```text
program = _lmcode_ cli="lmcode-cpp-sample";
let parts = str_split("a,b,c", ",");
print(str(parts.len()) + " parts, second is " + parts.at(1));
print("floor " + str(math_floor(3.7)) + " pow " + str(math_pow(2, 10)));
let cfg = json <<~CFG;
  { "limit": 3, "mode": "fast" }
CFG
print("limit " + str(cfg.get("limit").as_int()));
end _lmcode_
savedsl(program, ARGV[0]);
```

Output — pinned verbatim:

```text
3 parts, second is b
floor 3 pow 1024
limit 3
{"ok": true, "result": {"balance": 0, "entries": 0, "note": "", "entries_called": 0}}
LMCODE_RETURN_BEGIN
null
LMCODE_RETURN_END
```

## 4. Talking to the host

Everything a program can name beyond the language and the standard catalog comes from the host's
schema (`spec/language.md` §9, `spec/schema.md`). The sample shop schema declares context objects
`shop` and `ledger` (host-owned, read-only), object types `Money`/`Shop`/`Ledger`/`Items`, the
`Currency` enum, host functions like `money` and `fee`, an `operators` map for `Money`, and one
conversion `int → Money` (`sample-suite/host.schema.json`).

```text
program = _lmcode_ cli="lmcode-cpp-sample";
let m = shop.price(1250);
let pair = m * 2;
ledger.record(pair - money(500));
print("unit " + str(m.amount()) + " " + str(m.currency()));
print("balance " + str(ledger.balance().amount()));
print("plus 250 " + str((m + 250).amount()));
switch (shop.currency()) {
  case Currency.USD: { print("dollars"); }
  case Currency.EUR: { print("euros"); }
}
end _lmcode_
savedsl(program, ARGV[0]);
```

Output — pinned verbatim:

```text
unit 1250 USD
balance 2000
plus 250 1500
dollars
{"ok": true, "result": {"balance": 2000, "entries": 1, "note": "", "entries_called": 0}}
LMCODE_RETURN_BEGIN
null
LMCODE_RETURN_END
```

What just happened, per the schema rules in `spec/schema.md`:

- `m * 2` is not arithmetic on an object — the schema's `operators` map sends it to the method
  `Money.times(int)`. `pair - money(500)` maps to `Money.minus(Money)`.
- `m + 250` type-checks only because the schema declares the conversion `int → Money` via
  `money(int)`: `250` is converted, then `Money.plus(Money)` runs. Conversions never chain and
  never apply between primitives.
- `str(m.currency())` renders the enum constant's name; the `switch` on `shop.currency()` is an
  **enum switch** — the cases are `Currency.USD` / `Currency.EUR` constants, not strings
  (`spec/language.md` §4).
- The result record now shows the host's ledger state changed: `balance` 2000 (cents), `entries`
  1. Context objects are how a program leaves effects behind.

## 5. Rule entries: `@annotation` + `implements`

A top-level function annotated with `@NAME` and declared `implements Interface` compiles to a
separate **entry** the host can dispatch after the body runs — SonarQube-style rules
(`spec/language.md` §8). The sample schema declares two interfaces, `Adjuster` (void) and `Score`
(returns int); the sample hosts call every `@item` entry once per shop item and every `@total`
entry once with the shop total (`spec/conformance.md` §"Dispatch rules"):

```text
program = _lmcode_ cli="lmcode-cpp-sample";
@item
fn tag_item(m: Money) -> void implements Adjuster {
  print("item costs " + str(m.amount()));
}
@total
fn score_total(m: Money) -> int implements Score {
  return m.amount() / 100;
}
print("body ran");
end _lmcode_
savedsl(program, ARGV[0]);
```

Output — pinned verbatim:

```text
body ran
item costs 125
item costs 250
item costs 375
entry score_total = 7
{"ok": true, "result": {"balance": 0, "entries": 0, "note": "", "entries_called": 4}}
LMCODE_RETURN_BEGIN
null
LMCODE_RETURN_END
```

The body ran first (`body ran`), then the host dispatched the entries in source order: the `@item`
rule once per item, the `@total` rule once. A non-void entry's result prints as
`entry NAME = VALUE`, and the result record reports `entries_called: 4`. The signature must match
the interface exactly — a mismatch is a compile error (the sample suite pins both failure modes in
`compile-errors/`).

## 6. Errors: compile, run, and the schema binding

The taxonomy with every code is `spec/language.md` §12; the three failures you will actually meet:

**Compile errors** are located — `error:FILE:LINE:COL: _lmcode_: MESSAGE` — and exit 2 before
anything runs. The recursion error in §3 is one; the everyday one is an undefined name (`--check`
output abbreviated as noted above, exit 2):

```text
program = _lmcode_ cli="lmcode-cpp-sample";
print(str(undeclared_name));
end _lmcode_
savedsl(program, ARGV[0]);
```

```text
error:/tmp/lmtut/undefined-error.lms:2:11: _lmcode_: undefined name 'undeclared_name' (locals are declared with let; the schema provides: …, template_render, …; built-ins: float, str, sin, cos, sqrt, abs, floor, pow, min, max, clamp, lerp, ease, ease_in, ease_out, int)
```

Column 11 is where `undeclared_name` starts on line 2. The diagnostic category, location, and
the `schema provides:`/`built-ins:` sections are stable; the enumerated names (including
`template_render`) follow the effective host catalog and may change with the host revision.

**Run-time errors** exit 3 with a `RUN_ERROR` (VM-detected) or `RUN_HOST` (host threw) record. A
computed zero divisor is the classic (output pinned verbatim):

```text
program = _lmcode_ cli="lmcode-cpp-sample";
let zero = 0;
print(str(1 / zero));
end _lmcode_
savedsl(program, ARGV[0]);
```

```text
{"ok": false, "phase": "run", "code": "RUN_ERROR", "message": "dsl line 3:13: int division by zero", "line": 3, "column": 13}
```

`dsl line 3:13` is the `/` on the third body line. (A *literal* `1 / 0` would not get this far —
it is a compile error, §5.)

A third failure class is the host's own **application failure**: it runs after VM success and
exits 4. The sample hosts treat a negative final ledger balance as one (output pinned verbatim):

```text
program = _lmcode_ cli="lmcode-cpp-sample";
ledger.record(money(-100));
print("recorded a refund with no sale");
end _lmcode_
savedsl(program, ARGV[0]);
```

```text
recorded a refund with no sale
{"ok": false, "phase": "app", "code": "APP_FAIL", "message": "ledger: negative balance"}
```

**Schema-hash mismatch** is a *load* error, exit 3, raised before anything executes: the compiler
hashes the exact schema bytes into the bytecode header and the loader refuses a mismatch
(`spec/schema.md` §"Binding"). Flipping one byte inside the hash field of `hello.dslb` (this is
sample-suite case `091`) gives, pinned verbatim:

```text
{"ok": false, "phase": "load", "code": "LOAD_SCHEMA_MISMATCH", "message": "sample schema mismatch"}
```

The practical upshot: any change to the host's schema — even a semantically neutral reformat of
the file — invalidates previously compiled bytecode. Recompile after a host upgrade; using `cli=`
makes that automatic since check and compile always query the current host.

## 7. Current and planned features

The published 0.2.444 compiler remains a compile-only surface: `savedsl`, `dsl_cli`, and the
`_dsl_` spelling are the current compatibility path. On compiler/host main, `$return` lowering,
reverse extraction, and the C++/lmok sink/frame are landed (slices 3, 5, and 8); sink setup (slice 1) is landed and cross-port adoption
(slice 2) is in progress. `load_schema(...)` and executing blocks with
`_lmcode_ HANDLE [out=EXPR];` (slice 4) are landed in mono main at `0bc80277` (2026-10-31); they are absent from the released 0.2.444 compiler, and execution additionally needs a host that emits the terminal frame (the C++ SDK main does — verified end to end against `0bc80277` in the wp40 review; the samples do not yet, slice 6). Do not write programs against
those forms with the released 0.2.444 compiler this tutorial pins.

This tutorial covers exactly the **current 0.2.444 surface**: compile a block, write bytecode
with `savedsl`, run it with `host --dsl file.dslb`.

## Where to go next

- Browse the sample suite programs `001`–`069` (`lmcode-cpp/sample-suite/programs/`) — every
  language feature above appears there with a pinned expectation file.
- `spec/std.md` for the standard catalog; `spec/std-signatures.md` for the flat signature list.
- Writing a host instead of a program? `guides/implementing-a-runtime.md` and the host protocol
  spec.
