# pypokerlost

`pypokerlost` is the generic asynchronous Python SDK core for Pokerlost RPC APIs. It provides typed
method objects, a central client, a pluggable asynchronous session, generic client-owned
JSON-compatible state storage, a fixed response envelope, and an application lifecycle coordinator.

## Product surface

Methods execute with `await client(method)`, `await client.make_request(method)`, or
`await method.as_(client)`. Inside an active `Application` or `Client` scope, `await method` resolves
the task-local current client. Explicit execution uses an isolated method copy and never mutates the
caller's reusable method instance.

`Client()` uses a lazy, restartable `HttpxSession` and a `MemoryStorage` by default. Callers may
inject any `BaseSession` and `BaseStorage`. The fixed default gateway is
`APIServer.from_base("http://localhost:8080/api")`; an operation such as `accounts.get` maps to
`http://localhost:8080/api/accounts.get`.

Caller-defined middleware is an ordered, client-owned collection. Constructor input is copied,
`add_middleware()` appends one component, and every request executes against an immutable snapshot
with the first configured component outermost.

`Application` owns one client and one user-supplied async-context-manager lifecycle. `run()` owns an
event loop and performs graceful supported `SIGINT`/`SIGTERM` cancellation and cleanup;
`run_async()` uses a caller-owned loop without process-signal ownership. The client starts storage
before its session and closes the session before storage.

The repository also provides one development-only OpenAPI 3.1 JSON method generator. File and
service sources share one deterministic pipeline and produce ordinary SDK method modules that use
public package contracts. Generation tooling remains outside the runtime package and is not a
runtime SDK facility.

## Fixed decisions

- `PokerlostMethod[ResultT]` is the only production method base.
- The operation string is the complete RPC identity; no service metadata or routing exists.
- Requests contain only operation, HTTP method, URL, and immutable UTF-8 content.
- Pydantic JSON-mode serialization is the sole request normalization layer.
- Storage is generic client-owned `JSONValue` state and remains outside the RPC transport pipeline.
- Storage accepts optional positive finite relative TTL; expired entries behave as missing entries.
- `ApplicationResponseHandler` interprets the fixed `ApplicationResponse` envelope and validates
  the declared result type.
- Every valid failed envelope raises `PokerlostAPIError`; its stable `error` code identifies the
  business failure. Successful envelopes paired with non-2xx status raise
  `PokerlostProtocolError`.
- `RPCOpenAPIExtra` emits generic OpenAPI security requirements using service-defined scope strings.

## Non-goals

The core contains no concrete RPC methods, accounts/auth implementation, service-specific bases,
service or role enums, authentication, token handling, service routing, retries, streaming,
endpoint-specific client facade, runtime OpenAPI generation, settings system, predefined storage
keys, default or sliding TTL, expiration workers, transactions, queues, pub/sub, encryption,
external persistence implementation, or compatibility aliases.
