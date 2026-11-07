# lmcode std module `rest` — an embedded REST server

Status: **new, opt-in module** `lmcode_std_rest_v1` (not part of the default `lmcode_std_v3`
catalog, whose 206-signature pin is unchanged). Canonical declarations:
[`std/rest/lmcode-rest.schema.json`](../std/rest/lmcode-rest.schema.json) (20 signatures + one
interface). Shared conformance suite: [`tests/rest-suite/`](../tests/rest-suite/README.md).

A program starts an HTTP server, binds routes to **annotated SAM entries** (the `@NAME fn ... implements
RestHandler` rule mechanism of [language.md §8](language.md)), and every request is answered by running
the bound entry. The module follows the registration style of
[lmmock](https://github.com/lmctl-ai/lmmock) (`route(method, path, annotation)`), generalised from a Go-only
host to a standard module every runtime can provide.

```text
program = _lmcode_ schema="host.schema.json";

@user
fn get_user(x: RestExchange) -> void implements RestHandler {
  x.json("{\"id\":\"" + x.param("id") + "\"}");
}

@create
fn create_user(x: RestExchange) -> void implements RestHandler {
  x.set("last", x.body());
  x.status(201);
}

rest_route("GET",  "/users/{id}", "user");
rest_route("POST", "/users",      "create");
rest_listen(8080);
end _lmcode_
```

## Why a separate, opt-in module

The default catalog is merged into **every** `_lmcode_` block. A listener is a network capability, so it is
not in that implicit surface: a lint rule or a data transform cannot open a port by accident. A host opts in by
declaring the module in its schema (merge `std/rest/lmcode-rest.schema.json` into the host schema; the std
merge deduplicates identical `Json`-free declarations) **and** registering it in the runtime
(`registerRest` / `register_rest` / …). A runtime that does not register the module refuses programs that
import it with the ordinary `LOAD_UNBOUND`. No compiler change and no bytecode revision is needed: routes
bind through the existing identifier annotation, and the published 0.2.456 compiler compiles the suite.

## Declarations

```text
interface RestHandler(exchange: RestExchange) -> void

fn rest_route(string, string, string) -> void      # method, path template, annotation
fn rest_listen(int) -> int                         # 127.0.0.1:PORT  (0 = ephemeral); returns the bound port
fn rest_listen(string, int) -> int                 # HOST:PORT
fn rest_stop() -> void
fn rest_port() -> int                              # bound port; 0 while not listening

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
   program so the std functions can reach its entries.
2. The program **body** calls `rest_route` any number of times and then `rest_listen`.
3. `rest_listen` validates, **before opening a socket**:
   * at least one route is registered;
   * every route's annotation names exactly one entry whose interface is
     `interface RestHandler(RestExchange) -> void`; annotations are unique among `RestHandler` entries
     (entries implementing other interfaces are ignored);
   * route shapes are valid and unique (below).
   A failure is `RUN_HOST` with a pinned message and nothing is bound. `HOST` must be an IP literal or
   `localhost` (= `127.0.0.1`); a port outside 0–65535 is `rest: port N out of range 0..65535`; a bind failure is
   `rest: cannot listen on HOST:PORT: REASON` (REASON is platform text, e.g. `EADDRINUSE`). A second `rest_listen` while
   listening fails (`rest: server already listening`); `rest_route` after `rest_listen` fails
   (`rest: routes are frozen once the server is listening`); `rest_route` from inside a handler fails the same way.
4. The body continues and returns normally; the server keeps serving in the background. Requests that arrive
   while the body is still running wait until it finishes.
5. Each request runs its entry with a fresh `RestExchange`. Handler invocations are **serialized** (one VM
   run at a time per registry), in the order requests finished parsing. An implementation may run handlers
   concurrently only with isolated registries/arenas and atomic state; the observable contract is the same.
6. `rest_stop()` (from the body, a handler, or the host's `close()`) stops accepting connections after the
   in-flight response is flushed; `rest_port()` then returns 0. The same registry may listen again.

Host options (not visible to lmcode): `maxBodyBytes` (default 1 MiB), `readTimeoutMs` (10 000) and an
`onHandlerError(entryName, message)` callback (default: one line on stderr).

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

## HTTP subset

HTTP/1.1 over TCP, one request per connection (`Connection: close` on every response). Request line
`METHOD SP target SP HTTP/1.0|1.1`; the target must start with `/` (query after `?`; a fragment is not
allowed). Header section ≤ 16 KiB else **431**; names are case-insensitive. A body is read by
`Content-Length` (≤ `maxBodyBytes` else **413**, decided from the header before the body is read);
`Transfer-Encoding` on a request is **501**. A malformed request line, header, `Content-Length`, an
invalid percent escape in the path or query, or a non-`/` target is **400**. A request not completed within
`readTimeoutMs` is dropped (a 408 is optional). Query strings are `k=v` pairs separated by `&`, the first
occurrence of a key wins, `+` is a space, `%XX` is decoded (lmcode strings are bytes: decoded bytes are
not required to be UTF-8).

Responses: status line `HTTP/1.1 CODE REASON`, the exchange's headers, `Content-Length`, `Connection: close`.
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
two maps are independent. State lives as long as the controller object and survives `rest_stop`/`rest_listen`.
With serialized handlers no extra locking is observable; a concurrent implementation must make each call atomic.

## Runtime requirements

Each runtime provides (names follow the language's conventions):

| Piece | Responsibility |
|---|---|
| `registerRest(registry, options)` → controller | registers the 20 signatures; **not** called by the default registry constructor |
| `controller.run(program, context)` | binds the program, runs its body under the dispatch lock |
| `controller.dispatch(request)` | transport-independent core: `{method, target, headers, body}` → `{status, headers, body}`; this is what unit tests and the transport both use |
| transport | an HTTP/1.1 listener implementing the subset above using the language's standard library only |
| `controller.port`, `controller.close()` / `wait()` | observe and stop the server |

`signatures()` of a registry with the module registered = default std signatures + exactly the 20 above;
`scripts/…` sync tooling pins `std/rest/lmcode-rest.schema.json` and the suite by SHA-256 (`rest.lock`,
`rest-suite.lock`).

## Conformance

[`tests/rest-suite/`](../tests/rest-suite/README.md) holds the shared program (`app.lms` → `app.dslb`, built
by the published compiler), its host schema and `scenarios.json`: 37 sequential HTTP exchanges every runtime
must reproduce byte for byte (status, selected headers, body, `Content-Length`, connection closing),
ending with `rest_stop()` from a handler and a refused connection. Each runtime additionally keeps unit
tests for the router, the request parser and the exchange validation rules.
