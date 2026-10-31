# Host schema format — `dsl.schema` 2

Status: current. Every lmcode block is compiled against one host schema: a JSON document that
declares the object types, methods, functions, context variables, enums, conversions, operators
and rule interfaces the chunk may use. The schema is the whole contract between the host and the
compiler (`dsl.ts` resolves every name from it), and its exact bytes are the identity the compiled
bytecode is bound to (§"Binding").

Normative sources:

- Parser and validator (canonical for behavior): `lmscript/dsl.ts` `parseDslSchema` in the
  lmscript mono tree; the implicit-standard merge is `lmscript/dsl-std.ts` `mergeLmcodeStd`.
- Living language spec, schema section: `lmscript/durable-memory/design/dsl-language.md` §6.
- Requirements (R-numbers cited below): `lmscript/durable-memory/requirements/dsl-bytecode.md`
  (R42–R45, R48) and `requirements/lmcode-std.md` (the implicit standard catalog).
- Real schemas cited below: `lmcode-cpp/sample-suite/host.schema.json` (the domain declarations of
  the canonical shop sample hosts) and the conformance schema emitted by
  `lmscript/scripts/generate-dsl-conformance.ts` as `conformance/vectors/schema.json`.
- How the schema drives source-level checking is `spec/language.md` §9; the bytecode side of the
  binding is `spec/bytecode.md` §"Header".

Where the prose spec and `dsl.ts` disagree, `dsl.ts` wins and the disagreement is noted inline.

## Document shape

```json
{
  "dsl.schema": 2,
  "name": "sample_shop_v1",
  "types": { "Money": { "operators": { "+": "plus" },
                        "methods": { "plus": [{ "params": ["Money"], "returns": "Money" }] } } },
  "functions": { "money": [{ "params": ["int"], "returns": "Money" },
                           { "params": ["float"], "returns": "Money" }] },
  "context": { "shop": "Shop", "ledger": "Ledger" },
  "enums": { "Currency": ["USD", "EUR"] },
  "conversions": [{ "from": "int", "to": "Money", "via": "money" }],
  "interfaces": { "Score": { "params": [{ "name": "m", "type": "Money" }], "returns": "int" } }
}
```

(Trimmed from `lmcode-cpp/sample-suite/host.schema.json`, whose `Money`/`Shop`/`Ledger` types and
`Adjuster`/`Score` interfaces the whole sample suite runs against.)

Rules applied by `parseDslSchema`, in the order it applies them. Every violation is a compile-time
error with the prefix `schema LABEL: ` (LABEL is the schema file or the `cli=…` source; inside an
`_lmcode_` block it becomes the located `error:FILE:LINE:COL: _lmcode_: schema …: …` diagnostic,
exit 2, before any effect):

- The top level is an object with `"dsl.schema": 2` exactly (`"dsl.schema" must be 2; found …`;
  schema 1 and singleton signature objects are refused) and a `name` that is an identifier string
  (`[A-Za-z_][A-Za-z0-9_]*`). Unknown top-level keys are refused with a message listing the known
  ones: `dsl.schema, name, types, functions, context, enums, conversions, interfaces`.
- `types`, `functions`, `context` and `enums` must be objects when present; `conversions` must be a
  list; `interfaces` must be an object. Every name anywhere is an identifier; keywords, primitives,
  `void` and `self` are reserved.
- A **type name** in any signature position is one of the primitives `int`, `float`, `string`,
  `bool`, a declared object type, or a declared enum type. `void` is legal only as a return type.
  An undeclared name fails with `…: type "T" is not declared (primitives: int, float, string,
  bool; types: …)`.

## types, functions: methods, overloads, `self`

- `types` maps an object-type name to `{ "methods": {…}, "operators": {…} }` (both keys optional,
  no others). `functions` maps a host-function name to its overloads.
- Every function or method entry is an **array of overload signatures**, even for one signature:
  `[{ "params": [TYPE…], "returns": TYPE }, …]`. An omitted `returns` is `void`. At most 255
  parameters (the bytecode's `u8 argc`; `…: at most 255 parameters`). Two overloads of one name
  with the same parameter tuple are refused (`…: duplicate overload parameter types`); return types
  never distinguish overloads.
- A method return of `"self"` means its receiver type and is valid only on methods
  (`"self" is only valid on methods`). It expands to the receiver type in canonical signatures and
  imports (`method Expr.set(int) -> Expr`); the identity check from the early draft is withdrawn
  (R34).
- Function names must not collide with the language built-ins (`float`, `str`, the math names of
  `spec/language.md` §5; `… is a DSL built-in conversion`) or keywords. Context names must not
  collide with functions or enums, and a context variable is always an object type
  (`context NAME: context variables are host objects; T is not an object`) — primitives and enums
  cannot be context variables.
- A type name must not redefine a primitive; an enum name must be distinct from types, primitives,
  `void`, `self` and keywords, and its values are a non-empty list of unique identifier strings.

## Overload resolution, conversions, operators

Call resolution is entirely compile-time (`dsl.ts` `resolve`):

1. An exact parameter-tuple match among the same-arity overloads wins. Two exact matches are a
   compile error (`… is ambiguous: …`) — already impossible for schema declarations.
2. Otherwise a candidate may convert each argument through at most one declared conversion. All
   such candidates compete equally: more than one is an error listing them
   (`… is ambiguous for (int): (Money) -> Money, …`), never a ranking by conversion count.
3. Otherwise the error names the expected and found types.

`conversions` entries are `{ "from": TYPE, "to": TYPE, "via": "name" }` where `to` is an object
type, `from` ≠ `to`, the pair is unique, and `via` is either a zero-argument method `Type.method`
on the `from` object type returning `to`, or a unary host function taking `from` and returning
`to` (each must match exactly one declaration). Conversions never chain: a conversion target may
not also be a source (`conversion A -> B: conversion chains are forbidden`). They apply to schema
calls and operator mapping, never between primitives and never to user-function calls.

A type's `operators` map (`+`, `-`, `*`, `neg`, `r+`, `r-`, `r*` — the only accepted keys) maps
arithmetic on that object type to its own existing methods of arity one (`neg`: zero;
`operator "OP" method "M" must have 1 parameter(s)`). `r+`/`r-`/`r*` cover primitive-left
expressions (`2 * v`); a reversed subtraction method implements argument minus receiver. A missing
receiver operator may be reached through one declared receiver conversion, and when an object has
more than one conversion into operator-enabled types the compiler reports ambiguity before
selecting anything. Compiled operators are ordinary resolved method calls — `expr + 2` on the
conformance schema's `Thing` imports `method Thing.plus(Thing) -> Thing` — and relational
operators stay numeric-to-bool with no schema mapping. Receiver and arguments are evaluated once,
left to right; declared conversions are emitted after the source expressions, with a converted
receiver before converted arguments.

## enums

`enums` maps an enum name to its constant list. Constants are written `Type.VALUE` in source and
remain a distinct static type: same-enum `==`/`!=` and `str(enum)` are allowed; ordering,
string-to-enum conversion and mixed enum/string equality are not. On the wire an enum constant is
its name string (PUSH_STR) and host enum results are ordinary strings; there are no run-time enum
checks.

## interfaces (R48)

`interfaces` is an optional map of an interface name to **one** signature:

```json
"interfaces": {
  "Step": { "params": [{ "name": "x", "type": "int" }], "returns": "int" },
  "Visit": { "params": [{ "name": "t", "type": "Thing" }], "returns": "void" }
}
```

(from the conformance schema, which also declares `Flag`, `Mix`, `Pick` and `State`). An interface
is SAM by construction — it *is* one signature — with named parameters for readability. Types
resolve by the same rules as function signatures; `void` is allowed as the return type, `"self"`
is refused, an omitted `returns` is `void`, at most 255 parameters. Parameter names are unique and
not keywords; the interface name must be distinct from every type, enum, function, context name,
built-in, primitive, `void`, `self` and keyword. Every malformed entry is a `schema FILE:` error
naming the interface and parameter.

A top-level `@NAME fn … implements NAME` rule binds to one of these; the function's signature must
match the interface exactly, with no conversions (see `spec/language.md` §8). Interfaces are
compiler-facing metadata: they appear in **no canonical signature, no import and no bytecode
section** — a host registry never implements one, so `--dsl-signatures` never lists one — but
being schema bytes they join the SHA-256 binding (below), so adding an interface invalidates
previously compiled bytecode (accepted: no compatibility promise, R48). The compiler's inspection
views therefore show them: `lmscript --dsl-schema SCHEMA` (no `--json`) prints
`interface NAME(n: Type, …) -> R` lines after the signatures, and the `--json` document carries an
`interfaces` key (`{NAME: {params: [{name, type}…], returns}}`). On the wire an entry's interface
constant is the canonical text `interface NAME(T1, …) -> R` — parameter names are never
serialized.

## The implicit standard merge: effective vs raw schema

Before any type is resolved, `parseDslSchema` merges the bundled, digest-pinned **lmcode std**
catalog into the host document (`dsl-std.ts` `mergeLmcodeStd`; the `includeStd` option defaults to
true and normal block compilation never opts out). This produces the **effective schema** the
checker works against:

- Standard functions and standard-type methods the host does not declare are added; a host
  declaration identical to a canonical standard signature (including a method `returns: "self"`
  normalized to its owning type, or an omitted `returns` normalized to `void`) is deduplicated.
- A **different** signature under a standard name fails: `schema LABEL: lmcode std conflict for
  function NAME: host fn NAME(…) -> …; standard fn NAME(…) -> …` (or `method TYPE.NAME`). New
  method names on standard types remain legal host extensions. A standard type name redeclared as
  an enum, or a standard function name used as a host context variable, is the same kind of
  conflict.
- Host types, functions, enums, conversions and operators pass through unchanged. Only the
  host-declared names are remembered for the no-shadowing rule: implicit standard names may be
  shadowed by locals, parameters, user functions and loop variables (lmcode-std R05 / issue 120;
  see `spec/language.md` §6).

The catalog, its versioning and its drift pins are specified in `spec/std.md`.

## Binding: the SHA-256 of the exact bytes

`parseDslSchema` retains the original byte string as `schema.bytes`; the merge above does not
touch it. `encodeDsl` writes `sha256(schema.bytes)` into the bytecode header, and the loader
recomputes the hash over the schema bytes the host supplies and refuses a mismatch before anything
runs (`LOAD_SCHEMA_MISMATCH`; `spec/bytecode.md` §"Header"). Consequences:

- The hash covers the **raw host schema bytes only** — the exact file the compiler was given,
  whitespace and key order included. Any byte change to the host schema file (even a semantically
  neutral reformat) invalidates previously compiled bytecode. The normalized inspection JSON is
  explicitly *not* a replacement for the raw bytes (lmcode-std R06).
- The implicit std merge is **not** part of the hash: a change to the compiler's bundled standard
  catalog does not by itself change the identity of an already compiled program (the merged bytes
  a host prints as its schema are a different document and hash differently — see
  `sample-suite/CONTRACT.md`, whose `sample.dsl.json` is the merged form while `host.schema.json`
  holds the domain-only declarations).
- A host never parses its schema for loading; identity is by hash alone. What the host registers
  is checked separately, by diffing the registry's canonical signatures against the schema
  (§"Inspection").

## Where the compiler gets the schema (R42–R45)

An `_lmcode_` block names its schema in exactly one of two ways (`schema=` and `cli=` are mutually
exclusive; one is required):

- `schema="FILE"` — a schema file resolved like an import and read at check time.
- `cli="PROGRAM [WORD…]"` — the schema is what `PROGRAM WORD… --dsl-schema --json` prints, byte
  for byte. The words are fixed subcommands of a multi-schema host (`cli="lmor cpsat"`); each must
  match `[A-Za-z0-9._-]+` (no quoting, no shell). A bare program name is searched on `PATH`
  (absolute entries only); a name with a path separator resolves like an import. The query runs in
  every mode, `--check` included, because the schema is needed to check the body; it is cached per
  process by the binary's identity (real path, size, mtime, inode) plus the words and the flag
  (`lmscript.ts` `queryHostSchema`: 20 s timeout; a missing program, a failed or timed-out query
  and an invalid schema are located compile errors, exit 2).
- `install="github:OWNER/REPO@TAG"` (R43) may accompany a `cli=` with a bare program name: a
  program missing from `PATH` is downloaded from that pinned release's `PROGRAM-OS-ARCH` asset —
  SHA-256 verified against the release's `SHA256SUMS`, `ASSET.sha256`, or the digest on the
  release page (a mismatch fails; installed unverified, with a loud warning, only when none
  exists) — into the tool cache
  (`$LMSCRIPT_TOOL_CACHE` or `${XDG_CACHE_HOME:-~/.cache}/lmscript/tools`, under
  `github/OWNER/REPO/TAG/`). `PATH` wins over the cache. `TAG` may be `latest` (R45): the newest
  release, with staleness decided by the host's own `--version` (see `spec/host-protocol.md`) and
  a six-hour default check interval during real runs; check/lint/dry-run/help never use the
  network for `@latest`. `dsl_cli(dsl)` returns the argv prefix `[absolute program path, WORD…]`
  of a `cli=` block's host, so a script runs exactly the binary its bytecode is bound to. The
  attended form is `lmscript install "github:OWNER/REPO[@TAG]"` (R46; only it defaults an omitted
  tag to `@latest`).

## Inspection commands (compiler side)

`lmscript --dsl-signatures SCHEMA [--without-std]` prints the sorted canonical signatures of the
**effective** schema, one per line: `context NAME: Type`, `fn NAME(T1, T2) -> R`,
`method Type.name(T1) -> R`. `lmscript --dsl-schema SCHEMA [--without-std] [--json]` prints a
human summary (the same signature lines, then the `interface NAME(n: Type) -> R` lines) or, with
`--json`, a normalized schema document (`dslSchemaDocument` in `dsl.ts`: sorted keys, `self`
expanded to the owner type, omitted `returns` materialized as `void`; the document is an
inspection view, never the hashed bytes). `--without-std` filters the canonical standard
signatures out of either view, even when the source file declares them explicitly; host extensions
remain, and an emptied standard type disappears from the summary. Repeated or unknown options,
extra paths, or `--json` on `--dsl-signatures` are usage errors, exit 2. A host test diffs its
registry's `signatures()` against this output; the sample suite's `protocol.py` derives the
expected list independently from the schema, so a missing or extra registration fails even when no
program calls it (see `spec/conformance.md`).
