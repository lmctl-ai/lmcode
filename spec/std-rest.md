# lmcode std module `rest` — REST endpoints and stateless CLI over stdio

Status: **part of the default `lmcode_std_v3` catalog** (226 signatures + 10 standard interfaces).
Canonical fragment declarations: [`std/rest/lmcode-rest.schema.json`](../std/rest/lmcode-rest.schema.json) (20 signatures + 10 interfaces). Shared conformance suite: [`tests/rest-suite/`](../tests/rest-suite/README.md).

A program declares routes either via **path-annotated std interface entries** (`@"/users/:id" fn ... implements RestGet`, `@"POST /users" fn ... implements RestHandler`, `@"status" fn ... implements CliCommand`, `@"--verbose" fn ... implements CliOption`) or via `rest_route(method, path, annotation)`, and the runtime either serves **HTTP/1.1 messages over its standard streams** (`rest_serve()`) or dispatches a single **stateless CLI command** (`rest_cli(args)`).

```text
program = _lmcode_ schema="host.schema.json";

@"/users/:id"
fn get_user(x: RestExchange) -> void implements RestGet {
  x.json("{\"id\":\"" + x.param("id") + "\"}");
}

@"/users"
fn create_user(x: RestExchange) -> void implements RestPost {
  x.set("last", x.body());
  x.status(201);
}

rest_config("session", "global");
rest_serve();
end _lmcode_
```

## Standard Interfaces & Declarations

```text
interface RestGet(exchange: RestExchange) -> void
interface RestPost(exchange: RestExchange) -> void
interface RestPut(exchange: RestExchange) -> void
interface RestDelete(exchange: RestExchange) -> void
interface RestPatch(exchange: RestExchange) -> void
interface RestHead(exchange: RestExchange) -> void
interface RestOptions(exchange: RestExchange) -> void
interface RestHandler(exchange: RestExchange) -> void
interface CliCommand(exchange: RestExchange) -> void
interface CliOption(exchange: RestExchange) -> void

fn rest_cli(StrList) -> string                     # stateless single-command CLI execution returning response body
fn rest_config(string, string) -> void             # configure server/session key-value settings before serving
fn rest_route(string, string, string) -> void      # method, path template, annotation
fn rest_serve() -> void                            # after the body ends, serve stdin -> stdout until EOF or rest_stop()
fn rest_stop() -> void                             # end serving after the current response is written

# request (read-only)
method RestExchange.method() -> string             # upper-case verb
method RestExchange.path() -> string               # percent-decoded request path, without the query
method RestExchange.query(string) -> string        # first value of a query key; "" when absent
method RestExchange.has_query(string) -> bool
method RestExchange.param(string) -> string        # path parameter; "" for an unknown name
method RestExchange.header(string) -> string       # case-insensitive; repeated headers joined by ", "; "" when absent
method RestExchange.has_header(string) -> bool
method RestExchange.body() -> string               # raw request body bytes

# response (defaults: 200, no headers, empty body)
method RestExchange.status(int) -> void            # 200..599
method RestExchange.set_header(string, string) -> void
method RestExchange.send(string) -> void           # replace the body (raw bytes)
method RestExchange.json(string) -> void           # replace the body and set Content-Type: application/json

# server-wide shared string state (see "State")
method RestExchange.get(string) -> string          # "" when absent
method RestExchange.set(string, string) -> void
method RestExchange.increment(string) -> int       # separate integer counters, first value 1
```

Everything is strings and ints on purpose: JSON stays in the existing `json_parse` / `Json.to_json` std
(`x.json(json_parse(x.body()).to_json())`), so the module has no dependency on the collection arena and every
runtime can implement it identically. `x.json(s)` does not validate `s` (as in lmmock); build output with
the strict `Json` helpers when validity matters.

## Lifecycle

1. The host registers the module in its registry, loads the program, and runs it through the module's
   controller (`RestRuntime.run(program, context)` or the language's spelling). The controller binds the
   program so the std functions can reach its entries, and owns the input and output streams
   (default: the process's stdin and stdout).
2. The program **body** calls `rest_route` any number of times and then `rest_serve()`.
3. `rest_serve` validates, **before any byte is read**:
   * at least one route is registered;
   * every route's annotation names exactly one entry whose interface is
     `interface RestHandler(RestExchange) -> void`; annotations are unique among `RestHandler` entries
     (entries implementing other interfaces are ignored);
   * route shapes are valid and unique (below).
   A failure is `RUN_HOST` with a pinned message. `rest_serve` does not block: it records that serving was requested.
   A second `rest_serve` fails (`rest: rest_serve already called`); `rest_route` after `rest_serve` fails
   (`rest: routes are frozen once rest_serve has been called`), including from inside a handler.
4. When the body returns normally the controller **serves**: it reads requests from the input stream one at a
   time and, for each, writes exactly one response to the output stream before reading the next. Handlers therefore run
   strictly one at a time and never nest inside the body's VM run. A body that did not call `rest_serve`
   (or called `rest_stop` first) simply ends and nothing is read.
5. Serving ends — and the controller's `run` returns — when the input reaches EOF, when a handler (or the body) has called
   `rest_stop()` and its response is written, or after a *framing error* (below). Bytes after that point are not read
   and never answered. A request truncated by EOF is dropped without a response.

Host options (not visible to lmcode): `input`/`output` streams, `maxBodyBytes` (default 1 MiB) and an
`onHandlerError(entryName, message)` callback (default: one line on **stderr**). While serving, stdout belongs to the
protocol: hosts must send `print` and diagnostics to stderr.

### Pinned details

* `rest_serve` checks in this order: already called (`rest: rest_serve already called`), no program bound
  (`rest: no program is bound (run the program through the controller)`), then the route/annotation checks above.
* Whitespace in route paths, header names and request targets means ASCII only (bytes `0x00–0x20`, `0x7f`); bytes such as `0xA0`
  (UTF-8 `à` = `C3 A0`) are ordinary. Header *values* are trimmed of spaces and tabs only.
* Percent-escape validation of the request path and then the query runs **before** routing: an invalid escape is 400 even when no route would match.
* `increment` is an `int`: two's-complement int64 wraparound like all lmcode ints.
* `onHandlerError` receives the entry's function name and the VM error message.

## Route templates

`rest_route(METHOD, PATH, ANNOTATION)`:

* `METHOD` is one of `GET POST PUT PATCH DELETE HEAD OPTIONS` (upper case).
* `PATH` starts with `/`, contains no whitespace, control characters, `?` or `#`, and is split on `/` into
  segments. Only the **last** segment may be empty (`/files/`); `//` inside is invalid.
* A segment is a **literal**, `{name}` (one non-empty segment) or `{name...}` (the remainder: every remaining
  segment joined by `/`, at least one segment — possibly the empty last one). `name` is
  `[A-Za-z_][A-Za-z0-9_]*`, unique within the route; `{name...}` is only valid as the last segment; `{`/`}` anywhere
  else in a segment is invalid.
* Invalid → `rest: invalid route METHOD PATH: REASON`. Two routes with the same method and the same *shape*
  (parameter names ignored) → `rest: duplicate route METHOD PATH`. Unknown annotation →
  `rest: route METHOD PATH references missing annotation @NAME`. Wrong interface →
  `rest: entry NAME must implement RestHandler(RestExchange) -> void`. Duplicate annotation →
  `rest: duplicate annotation @NAME`. No route → `rest: no routes registered`.

Matching works on the raw request path split on `/`; literals are compared with the percent-decoded
segment, parameters capture the decoded segment (`%2F` stays inside its segment). There is no path cleaning,
no redirect and no trailing-slash folding: `/health/` is not `/health`. Among routes of the same method the
most specific wins, comparing segment by segment: literal beats `{name}` beats `{name...}`; the first
difference decides.

* No route matches the path under any method → **404**.
* Some route matches the path but not the method → **405** with `Allow`: the matching routes' methods,
  `HEAD` added when `GET` is present, sorted, joined by `, `.
* `HEAD` with no `HEAD` route falls back to the `GET` route; the body is not sent (headers, including
  `Content-Length`, are those of the `GET` response). `OPTIONS` is never implicit.

## HTTP subset (message framing over stdio)

The streams carry a sequence of HTTP/1.1 messages, framed exactly like HTTP keep-alive: a request is a head
(`METHOD SP target SP HTTP/1.0|1.1`, headers, blank line) followed by `Content-Length` body bytes; each response is
a status line, headers, blank line and `Content-Length` body bytes. There is no `Connection` header in either
direction (the stream is the connection) and no pipelining concerns: responses are written in request order.
The target must start with `/` (query after `?`; a fragment is not allowed). Names are case-insensitive.

*Per-request* errors answer and **keep serving**: invalid percent escape in the path or query (**400**), no route (404), method
not allowed (405). *Framing* errors cannot be resynchronised, so the module answers once and **ends serving**:
a malformed request line, header or `Content-Length`, a non-`/` target (**400**); header section over 16 KiB
(**431**, detected before the head ends); `Content-Length` over `maxBodyBytes` (**413**, from the header, body unread);
`Transfer-Encoding` on a request (**501**). Query strings are `k=v` pairs separated by `&`, the first occurrence of a key
wins, `+` is a space, `%XX` is decoded (lmcode strings are bytes: decoded bytes are not required to be UTF-8).

Responses: status line `HTTP/1.1 CODE REASON`, the exchange's headers, then `Content-Length` (the length of the body, also for `HEAD`).
`Content-Type` defaults to `text/plain; charset=utf-8` when the body is non-empty and none was set;
`x.json` sets `application/json`. 204 and 304 never carry a body. `set_header` replaces a header of the same
name (case-insensitively); it rejects an empty name, whitespace, `:`, CR or LF in a name, CR or LF in a value, and the
reserved names `Content-Length`, `Connection` and `Transfer-Encoding`. `status` outside 200–599 is a
`RUN_HOST` error. Raw bytes in `send` are written verbatim.

Generated errors are JSON with `Content-Type: application/json`: 400 `{"error":"bad request"}`, 404
`{"error":"not found"}`, 405 `{"error":"method not allowed"}`, 413 `{"error":"payload too large"}`, 431
`{"error":"request header too large"}`, 500 `{"error":"internal error"}`, 501 `{"error":"not implemented"}`.
A handler that raises any run-time error yields 500 with that fixed body — the VM message goes to
`onHandlerError` only — and the server keeps serving.

## State

`get`/`set`/`increment` give handlers server-wide string and counter state (the lmmock model); keys of the
two maps are independent. State lives as long as the controller object. Handlers are strictly sequential, so no locking is observable.

## Runtime requirements

Each runtime provides (names follow the language's conventions):

| Piece | Responsibility |
|---|---|
| `registerRest(registry, options)` → controller | registers the 18 signatures; **not** called by the default registry constructor |
| `controller.run(program, context)` | binds the program, runs the body, then serves the streams until serving ends (may be async in the language) |
| `controller.dispatch(request)` | transport-independent core: `{method, target, headers, body}` → `{status, headers, body}`; this is what unit tests and the transport both use |
| stream pump | the framing above over the host-supplied input/output (default stdin/stdout), standard library only |
| `controller.stop()` | ends serving as `rest_stop()` does |

`signatures()` of a registry with the module registered = default std signatures + exactly the 18 above;
`scripts/…` sync tooling pins `std/rest/lmcode-rest.schema.json` and the suite by SHA-256 (`rest.lock`,
`rest-suite.lock`).

## Conformance

[`tests/rest-suite/`](../tests/rest-suite/README.md) holds the shared program (`app.lms` → `app.dslb`, built
by the published compiler), its host schema and `scenarios.json`:

* `stream` — 33 sequential exchanges written to **one** input stream and compared with the **one** output stream, ending
  with `rest_stop()` from a handler followed by a request that must stay unanswered;
* `fatal` — 4 framing errors, each on a fresh stream followed by a valid request: exactly one (error) response, then the end;
* `silent` — 3 inputs (empty, truncated head, truncated body) that produce no output and end cleanly.

Each runtime replays the suite through in-memory streams (unit level) **and** through its real process stdin/stdout
(integration level, via a tiny serve CLI/test host), plus its own unit tests for the router, the head/body parser and the
exchange validation rules.
