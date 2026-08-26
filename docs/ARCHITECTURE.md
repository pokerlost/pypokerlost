# pypokerlost architecture

Normative engineering rules live in [`../AGENTS.md`](../AGENTS.md); current product purpose and
scope live in [`../SERVICE.md`](../SERVICE.md).

## Design goal

The current architecture fixes component interaction while leaving unknown product policy open.
Its ergonomic direction combines a central Pyrogram-like client, aiogram-like immutable typed RPC
objects, and an application-level lifecycle owner.

```text
Client.make_request(method)
→ BaseSession.make_request(method)
→ RequestBuilder.build(method)
→ BaseSession.execute(prepared_request)
→ ResponseHandler.handle(method, prepared_request.operation, raw_response)
→ ResultT
```

Streaming follows the shorter resource-owning path:

```text
Client.stream_content(method)
→ BaseSession.stream_content(method)
→ RequestBuilder.build(method)
→ BaseSession.open_stream(prepared_request)
→ ContentStream
```

No session, request, response, or HTTP-adapter API receives `Client`. There is no replacement
context bag, service locator, auth hook, or dependency container in the pipeline.

## Package shape

```text
pypokerlost/
├── __init__.py
├── application.py
├── exceptions.py
├── py.typed
├── client/
│   ├── __init__.py
│   ├── client.py
│   ├── context.py
│   └── session/
│       ├── __init__.py
│       ├── base.py
│       ├── httpx.py
│       ├── request.py
│       ├── response.py
│       └── stream.py
├── methods/
│   ├── __init__.py
│   └── base.py
├── contracts/
│   ├── __init__.py
│   ├── response_model.py
│   └── application_response.py
├── openapi/
│   ├── __init__.py
│   └── rpc.py
└── types/
    ├── __init__.py
    └── json.py
```

The important boundary is that the HTTP pipeline lives with the session, method bases remain
transport-independent, and fixed wire contracts remain separate from runtime code. The tree is not
a target file count.

## Responsibilities

| Component | Current responsibility |
| --- | --- |
| `Application` | Own one client's automatic lifecycle and task-local execution scope. |
| `Client` | Own one supplied session, enforce lifecycle state, and delegate calls. |
| method bases | Immutable typed request values and declarative operation/result metadata. |
| `BaseSession` | Coordinate request building, concrete I/O, response handling, and stream scope. |
| `RequestBuilder` | Serialize a method once into an explicit-operation request with byte content. |
| `ResponseHandler` | Validate the fixed JSON envelope, then the declared result type. |
| `HttpxSession` | Own and adapt a caller-configured `httpx.AsyncClient`. |
| `ContentStream` | Expose live byte iteration and one idempotent close path. |
| `contracts` | Hold authoritative shared wire models. |
| `openapi` | Produce the small plain-data `x-pokerlost` marker. |

## Application lifecycle

Construction is explicit:

```python
http_client = httpx.AsyncClient(base_url="https://accounts.internal")
session = HttpxSession(http_client)
client = Client(session)
application = Application(client)
```

`Application` owns exactly that client. Its lifecycle order is:

```text
enter application
→ await client.start()
→ install client in the task-local ContextVar
→ run the entrypoint or direct async scope
→ await client.stop()
→ reset the exact ContextVar token
```

Startup must succeed before context installation. If installation fails, the client is stopped and
the original failure is re-raised. Exit always attempts terminal stop and resets the stored token
in `finally`, including when the entrypoint or stop fails. A second concurrent or reentrant entry of
the same application raises `ApplicationStateError`. Entrypoint failures propagate after cleanup.

`Application.run_async(entrypoint)` is exactly an async application scope around
`await entrypoint(application.client)`. `Application.run(entrypoint)` invokes it with
`asyncio.run()`; direct `async with application` is also supported.

## Client lifecycle and current context

`Client` owns one supplied `BaseSession`. `start()` calls `session.start()` once and is idempotent
while started. `stop()` calls `session.close()` once, is idempotent, and permanently closes the
client. Requests and streams before startup raise `ClientNotStartedError`; after stop they raise
`ClientClosedError`. There is no lazy startup and no `Client` async context manager.

Manual lifecycle remains possible:

```python
await client.start()
try:
    result = await client(method)
finally:
    await client.stop()
```

`client.as_current()` is limited to token-based `ContextVar` handling and never changes lifecycle:

```python
with client.as_current():
    result = await method
```

The context manager resets the exact token in `finally`, so nested scopes restore the preceding
client.

## Method objects

`BaseMethod`, `Method[ResultT]`, and `StreamMethod` share one frozen Pydantic base with forbidden
extra fields. A concrete ordinary operation declares class metadata and request fields:

```python
class GetAccount(Method[Account]):
    __api_method__ = "accounts.get"
    __http_method__ = "POST"
    __returning__ = Account

    account_id: UUID
```

`__api_method__` follows `namespace.method`, and the request path becomes `/accounts.get`.
`__http_method__` defaults to `POST`; concrete methods override it only when their contract needs a
different verb.
Metadata mistakes produce a clear error on first execution. Model construction does not run regex
checks, inspect aliases through Pydantic internals, or use subclass/post-init hooks.

`Method.execute(client=None)` resolves an explicit client or the task-local current client and
delegates to `Client.make_request()`. Awaiting a method delegates to `execute()`. `StreamMethod`
stays non-awaitable because its body requires a resource-owning context manager.

## Request path

`RequestBuilder.build(method)` reads `__api_method__` and `__http_method__` once, rejects missing or
invalid string metadata, and produces:

```python
@dataclass(frozen=True, slots=True)
class PreparedRequest:
    operation: str
    http_method: str
    path: str
    content: bytes
```

The builder derives `path` as `f"/{operation}"`, serializes the method exactly once with normal
alias-free Pydantic JSON serialization, and encodes it as UTF-8 bytes. The operation remains an
explicit value and is never reconstructed from the path. `PreparedRequest` carries no base URL,
auth, timeout, routing, retry, or `httpx` state.

Omitted-field versus explicit-`null` behavior will be chosen from real operation contracts. The
current builder does not establish an SDK-wide sentinel or exclusion policy.

## Session and HTTP I/O

`BaseSession` implements the shared ordinary flow:

```text
build request
→ execute through concrete adapter
→ handle response
```

Its pipeline methods receive only method and prepared-request values. `BaseSession.start()` is a
default no-op because HTTP clients normally initialize lazily. Concrete adapters implement
`execute(request)`, `open_stream(request)`, and `close()` without access to `Client`.

`HttpxSession` receives an existing `httpx.AsyncClient`. The caller configures `base_url`, timeout,
headers, proxies, TLS, limits, transport, and environment behavior through httpx. The adapter sends
prepared byte content, preserves caller-configured default headers while setting JSON content type,
opens live streams, and maps known transport failures to `TransportError` with the original cause.
It owns and closes the supplied HTTP client. Cancellation is not converted.

## Response path

`RawResponse` is a transport-neutral buffered response. `ResponseHandler` first validates every
body through one reusable adapter for `ApplicationResponse[JsonValue]`. This stage validates only
the fixed envelope and a JSON-compatible result value.

A valid failed envelope becomes one `ApplicationError`, preserving `error`, `error_message`, the
operation, and HTTP status as diagnostic metadata. For a valid success, a separate `TypeAdapter`
created from the concrete method's `__returning__` validates the result. An envelope-level `None`
succeeds only when that declared result annotation accepts `None`. Pydantic validation failures at
either boundary become `ResponseDecodeError`.
The current handler does not turn HTTP status/envelope combinations into a platform-wide policy
matrix.

Public errors may expose stable operation/status metadata but do not contain request bodies,
authorization values, or raw/full response bodies.

## Streaming

`BaseSession.stream_content(method)` builds a request, asks the concrete session to open a
live `ContentStream`, yields it, and closes it in `finally`. This covers normal completion, early
break, and caller exceptions without buffering a successful body.

The SDK currently assigns no application-envelope format to stream failures. That protocol waits
for the first authoritative streaming endpoint.

## Fixed wire and OpenAPI contracts

`ResponseModel` retains:

```python
ConfigDict(
    extra="forbid",
    frozen=True,
    hide_input_in_errors=True,
    validate_default=True,
)
```

`ApplicationResponse` retains its four fields, defaults, and validator:

```python
ok: bool
result: ResultT | None = None
error: str | None = None
error_message: str | None = None
```

`AccessRole` contains `public`, `user`, `support`, `master`, and `auto`.
`rpc_openapi_extra(access=...)` preserves the caller's iterable and returns:

```python
{
    "x-pokerlost": {
        "access": [role.value for role in access],
    },
}
```

It imports no FastAPI code and performs no authorization-policy validation.

## Auth and configuration boundary

Authentication is not implemented. The pipeline has no auth provider, token state, refresh logic,
authorization injection, middleware callback, or special handling for auth operations. Future
accountsService and authService operations are ordinary typed method and result classes.

There is no SDK settings subsystem, environment loading, URL routing map, or duplicated HTTP
configuration. `Application` accepts only a `Client`; `Client` accepts only a `BaseSession`; and
`HttpxSession` accepts the caller-configured `httpx.AsyncClient` it owns.

## Deferred decisions

The first real accountsService and authService methods will provide evidence for:

- one-service or multi-service client routing and URL mapping;
- auth state, authorization placement, and token refresh;
- any future SDK-level timeout, header, proxy, TLS, pool, retry, or environment policy;
- request omitted/`null` semantics;
- HTTP-status interpretation and streaming error bodies;
- endpoint wrappers, a synchronous SDK facade, WebSocket/update behavior, and other convenience
  APIs.

These are deferred product decisions, not constraints imposed by the current mechanism. Ownership,
client lifecycle, application scope, and the absence of lower-layer `Client` dependencies are fixed
current decisions.
