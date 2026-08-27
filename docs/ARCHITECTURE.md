# Architecture

This document describes internal ownership and runtime flow. Public startup and usage belong in
[`getting_started.md`](getting_started.md); method authoring belongs in
[`adding_methods.md`](adding_methods.md); repository code generation belongs in
[`generating_methods.md`](generating_methods.md).

## Boundaries

| Component                    | Responsibility                                                                                                                                                                    |
|------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `Application`                | Own one client lifecycle, one user lifecycle, and signal-aware synchronous execution.                                                                                             |
| `Client`                     | Own one session, one storage, and a mutable ordered middleware list; copy and bind explicitly executed methods; snapshot middleware per request; and manage current-client scope. |
| `BaseMiddleware`             | Define the single RPC wrapper contract used by client-built request chains.                                                                                                       |
| `RPCRequestOptions`          | Carry immutable, copy-owned headers through one middleware-chain execution.                                                                                                       |
| `PokerlostMethod`            | Hold finite strict request fields and require operation and result metadata.                                                                                                      |
| `RPCRequestBuilder`          | Serialize a method once and build an immutable transport request.                                                                                                                 |
| `BaseSession`                | Resolve timeout and define pluggable asynchronous execution.                                                                                                                      |
| `HttpxSession`               | Own restartable HTTPX resources and concrete HTTP I/O.                                                                                                                            |
| `BaseResponseHandler`        | Define response-protocol interpretation.                                                                                                                                          |
| `ApplicationResponseHandler` | Decode the fixed envelope and validate the declared result.                                                                                                                       |
| `RPCOpenAPIExtra`            | Produce generic service-side OAuth2 security metadata.                                                                                                                            |

Lower request, response, and session layers do not import `Client`. Typed `RPCRequestOptions` is the
only per-request transport extension; there is no service identity, routing layer, auth state,
retry middleware, response wrapper, or arbitrary execution context.

## Execution flow

```text
PokerlostMethod
→ Client.make_request (copy and explicit binding)
→ immutable middleware snapshot and reverse-built chain
→ BaseSession
→ RPCRequestBuilder
→ HttpxSession HTTP I/O
→ BaseResponseHandler
→ ApplicationResponseHandler
→ declared ResultT
```

`Client.__call__()` delegates to `Client.make_request()`. Awaiting a method resolves an explicitly
bound client first, then the one task-local `ContextVar`; absence raises `ClientContextError`.
`Client(..., middleware=None)` copies supplied constructor components into client-owned mutable
state. `add_middleware()` is append-only: constructor components remain first and each addition
becomes the new innermost configured wrapper. `client.middleware` exposes a tuple snapshot.

Every `make_request()` call snapshots the current list before reverse-building its chain. The first
configured component is outermost, and an addition made during execution cannot alter that
in-flight chain. Middleware wraps only bound method session execution. Its handler is polymorphic:
an alternate method is copied, bound to the same client, and executed through only the remaining
chain. A handler call without explicit options inherits the current immutable options.
Client async-context exit resets the exact context token before closing its resources, so nested
scopes restore the outer client and concurrent tasks remain isolated.

## Request boundary

`RPCRequestBuilder.build()` reads `__api_method__` and `__http_method__` once, requires a lowercase
`namespace.method` operation, and accepts only `GET`, `POST`, `PUT`, `PATCH`, or `DELETE`. It calls
`method.model_dump(mode="json", by_alias=False, exclude_unset=True)` once, calls the configured
`json_dumps` once, requires a string, and UTF-8 encodes it once. The default encoder rejects
non-finite floats.

`RPCRequest` is frozen and contains only:

```python
operation: str
http_method: str
url: str
content: bytes
headers: tuple[tuple[str, str], ...]
```

The operation is the complete RPC identity and is appended to the one configured `APIServer` base.
Every `APIServer` constructor path validates an absolute HTTP(S) URL template. The builder combines
its JSON defaults with validated per-request headers, using case-insensitive replacement, and never
stores headers in exception metadata.

`HttpxSession.start()` publishes a newly constructed `httpx.AsyncClient` before any suspension
point. `close()` first detaches the current client and then awaits `aclose()`, so concurrent lazy
startup cannot overwrite ownership or leak an earlier client.

## Response boundary

`ApplicationResponseHandler`:

1. decodes content with configured `json_loads`;
2. strictly validates `ApplicationResponse[JSONValue]`;
3. raises `PokerlostAPIError` for every valid failed envelope;
4. raises `PokerlostProtocolError` for a successful envelope with non-2xx status;
5. safely re-encodes the validated `JSONValue` result and validates it with strict
   `TypeAdapter(method.__returning__).validate_json(...)` semantics and
   `context={"client": method.client}`.

Decode, encoding, and validation failures become `ClientDecodeError`. Transport failures and
timeouts retain their distinct safe exception categories. Caught boundary exceptions are replaced
with safe built-in causes after leaving their handling blocks, so neither `__cause__` nor
`__context__` retains a request, raw body, validation input, or security-sensitive header.

## Lifecycle

Application entry rejects overlapping use, enters the client, then enters the user lifecycle.
Reverse exit leaves the user lifecycle, resets the current-client context, closes client resources,
and clears application state. Setup failure and cancellation unwind entered resources, and
sequential reuse remains supported. Like a regular async context manager, the user lifecycle may
suppress an exception from the managed body; `run_async()` returns `None` when that prevents the
entrypoint from producing a result.

`Application.run()` uses `asyncio.run()` and temporarily installs supported loop handlers for
`SIGINT` and `SIGTERM`. A handled signal cancels and awaits the application task so cleanup finishes.
The handled path completes application cleanup before removing installed signal handlers.
`run_async()` owns no process signal handlers.

## OpenAPI metadata

`RPCOpenAPIExtra` validates a non-empty security-scheme name, ordered unique non-empty scope strings,
and `contract_version >= 1`. Each `as_dict()` call creates a fresh standard `security` structure and
an `x-pokerlost` contract-version extension. It neither declares OAuth2 flows nor participates in
runtime execution.

## Repository tooling

The repository `Dockerfile` has a build stage and a scratch artifact-export stage. It builds the
wheel and source distribution and is not part of SDK runtime architecture: it defines no process,
network port, lifecycle, publishing step, or runtime container.

`scripts/generate_methods.py` is the single development-time OpenAPI generation pipeline. Local
JSON and service `/openapi.get` inputs converge on the same validated document, resolver, renderer,
manifest policy, and safe writer. It validates strict schema rules only for schemas reachable from
selected request bodies and successful responses; unused framework-owned components remain opaque
JSON. Manifest history is isolated by canonical output root. The script reuses stable public SDK
contracts through focused facades but does not import runtime infrastructure or move code-generation
implementation into `pypokerlost`. Generated modules depend only on public runtime facades and
declared runtime dependencies; neither the generator nor its tooling dependencies participate in
SDK execution.

## Documentation ownership

- `README.md` owns local source-build prerequisites, commands, artifact location, and links.
- `getting_started.md` owns user-facing startup and invocation guidance.
- `building.md` owns local and Docker artifact-build guidance.
- `middleware.md`, `storage.md`, and `adding_methods.md` own their focused user guides.
- `generating_methods.md` owns development-time OpenAPI generation and version policy.
- `ARCHITECTURE.md` remains the normative internal ownership document.
