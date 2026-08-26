# pypokerlost architecture

Normative engineering rules live in [`../AGENTS.md`](../AGENTS.md); current product purpose and
scope live in [`../SERVICE.md`](../SERVICE.md).

## Design goal

The current architecture fixes component interaction while leaving unknown product policy open.
Its ergonomic direction combines a central Pyrogram-like client with aiogram-like immutable typed
RPC objects.

```text
typed Method
→ explicit or task-local Client
→ BaseSession(client, method)
→ RequestBuilder(client, method)
→ concrete session I/O
→ ResponseHandler(client, method, response)
→ typed result
```

Passing `Client` through the pipeline leaves a narrow extension point for future auth or routing
state without putting HTTP logic in methods or changing their public execution forms.

## Package shape

```text
pypokerlost/
├── __init__.py
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
├── exceptions.py
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
| `Client` | Hold a supplied session, delegate calls, and manage explicit current-client context. |
| method bases | Immutable typed request values and declarative operation/result metadata. |
| `BaseSession` | Coordinate request building, concrete I/O, response handling, and stream scope. |
| `RequestBuilder` | Produce a transport-neutral request from `Client` and a method. |
| `ResponseHandler` | Validate `ApplicationResponse` against the declared result type. |
| `HttpxSession` | Adapt a caller-configured `httpx.AsyncClient` to session I/O hooks. |
| `ContentStream` | Expose live byte iteration and one idempotent close path. |
| `contracts` | Hold authoritative shared wire models. |
| `openapi` | Produce the small plain-data `x-pokerlost` marker. |

## Client and current context

Construction is explicit:

```python
http_client = httpx.AsyncClient(base_url="https://accounts.internal")
session = HttpxSession(http_client)
client = Client(session)
```

`Client` passes itself into both ordinary and streaming session calls:

```python
await session.make_request(client, method)
session.stream_content(client, stream_method)
```

The session may ignore the client today. Keeping it in the call chain allows a later explicit
decision to use client-owned runtime state without coupling method objects to the client.

Ambient execution is limited to token-based `ContextVar` handling:

```python
with client.as_current():
    result = await method
```

The context manager resets the exact token in `finally`, so nested scopes restore the preceding
client. The current architecture assigns no `async with client` behavior.

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

`RequestBuilder.build(client, method)` produces a small immutable `PreparedRequest`. It derives the
relative path from method metadata and uses ordinary Pydantic JSON-mode serialization. It does not
resolve base URLs, add auth, or carry retry/routing policy.

Omitted-field versus explicit-`null` behavior will be chosen from real operation contracts. The
current builder does not establish an SDK-wide sentinel or exclusion policy.

## Session and HTTP I/O

`BaseSession` implements an overridable Template Method flow:

```text
build request
→ execute through concrete adapter
→ handle response
```

Its pipeline methods receive `Client`, are not marked `@final`, and use ordinary concrete
`RequestBuilder` and `ResponseHandler` collaborators. Alternative sessions can override behavior
when a real second scenario appears.

`HttpxSession` receives an existing `httpx.AsyncClient`. The caller configures `base_url`, timeout,
headers, proxies, TLS, limits, transport, and environment behavior through httpx. The adapter sends
prepared requests, opens streams, maps transport failures to the SDK exception, and delegates
closing to the supplied HTTP client. Whether that closing behavior should represent ownership or a
shared-session arrangement remains open.

## Response path

`RawResponse` is a transport-neutral buffered response. `ResponseHandler` constructs the
`ApplicationResponse` adapter from the method's declared result type and validates the response
body. Pydantic validation failures become `ResponseDecodeError`.

A valid failed envelope becomes one `ApplicationError`, preserving `error`, `error_message`, the
operation, and HTTP status as diagnostic metadata. A valid successful envelope returns `result`.
An envelope-level `None` result remains valid, then succeeds only when the method's declared result
annotation accepts `None`.
The current handler does not turn HTTP status/envelope combinations into a platform-wide policy
matrix.

Public errors may expose stable operation/status metadata but do not contain request bodies,
authorization values, or raw/full response bodies.

## Streaming

`BaseSession.stream_content(client, method)` builds a request, asks the concrete session to open a
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

## Deferred decisions

The first real accountsService and authService methods will provide evidence for:

- one-service or multi-service client routing and URL mapping;
- auth state, authorization placement, and token refresh;
- session and HTTP-client ownership or sharing;
- start/stop, async context, reentrancy, and WebSocket lifecycle;
- timeout, headers, proxy, TLS, pool, retry, and environment policy;
- request omitted/`null` semantics;
- HTTP-status interpretation and streaming error bodies;
- endpoint wrappers, a synchronous facade, and other convenience APIs.

These are deferred product decisions, not constraints imposed by the current mechanism.
