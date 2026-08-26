# pypokerlost

SERVICE_NAME: pypokerlost  
SERVICE_SLUG: pypokerlost  
DISTRIBUTION_NAME: pypokerlost  
PACKAGE_NAME: pypokerlost  
REPOSITORY_ROOT: pokerlost  
PACKAGE_ROOT: pypokerlost

## Purpose

`pypokerlost` is the asynchronous Python SDK core for PokerLost services. Its intended ergonomics
combine a central Pyrogram-like `Client`, aiogram-like typed RPC method objects, and a separate
`Application` composition root. These projects are references only and are not dependencies.

The current package provides explicit client lifecycle, automatic application scope, typed ordinary
method execution, and resource-scoped raw content streaming. It contains no concrete PokerLost
operations yet.

## Current product surface

Ordinary methods support explicit execution:

```python
await client.make_request(method)
await client(method)
await method.execute(client)
```

`Application` normally owns startup, task-local current-client installation, and guaranteed stop:

```python
application.run(main)
result = await application.run_async(main)

async with application:
    result = await method
```

`run()` uses `asyncio.run()`; `run_async()` supports an already-running loop. The same application
cannot be entered concurrently or reentrantly.

Streaming remains explicitly resource-scoped:

```python
async with client.stream_content(stream_method) as content:
    async for chunk in content:
        ...
```

`StreamMethod` is not awaitable. `Client` currently has no endpoint-specific methods or dynamic
endpoint lookup.

The low-level HTTP assembly is explicit:

```python
http_client = httpx.AsyncClient(base_url="http://localhost:8000")
client = Client(HttpxSession(http_client))
application = Application(client)
```

Network configuration remains in `httpx.AsyncClient`; the SDK has no settings or environment
loading. `Client` owns its supplied session, and `HttpxSession` owns and closes its supplied HTTP
client. Manual lifecycle uses `await client.start()` and terminal, idempotent
`await client.stop()`.

## Responsibilities

- `Application`: automatic client lifecycle and task-local current-client scope.
- `Client`: lifecycle-aware facade owning one supplied session.
- method bases: immutable Pydantic request values plus declarative operation/result metadata.
- `BaseSession`: shared ordinary and streaming execution flow without access to `Client`.
- `RequestBuilder`: one-time method serialization to an explicit-operation request with byte
  content.
- `ResponseHandler`: reusable JSON-value envelope validation followed by typed result decoding.
- `HttpxSession`: owning I/O adapter over a caller-configured `httpx.AsyncClient`.
- `ContentStream`: live byte iteration and explicit resource closing.
- `contracts`, `openapi`, and `exceptions.py`: shared wire, metadata, and failure values.

## Fixed contracts

`ResponseModel` keeps `extra="forbid"`, `frozen=True`, `hide_input_in_errors=True`, and
`validate_default=True`.

`ApplicationResponse[ResultT]` keeps the established fields `ok`, `result`, `error`, and
`error_message`, their defaults, and its validator. Success forbids error metadata; failure forbids
a result and requires both error fields.

RPC operation identifiers follow `namespace.method`, producing the relative path
`/{namespace}.{method}`. Ordinary methods declare their result type and are executed by a session;
the `Client` does not need a registry of concrete endpoints.

`AccessRole` provides `public`, `user`, `support`, `master`, and `auto`. The shared
`rpc_openapi_extra()` helper emits only `x-pokerlost.access` as plain JSON-compatible metadata and
does not enforce authorization policy.

## Current scope

The next feature work should add one authoritative accountsService method and one authoritative
authService method with their real request/result models and errors. The current package does not
include those methods, client endpoint wrappers, authentication, routing, retries, WebSocket
processing, SDK settings, or a test suite. There are no speculative auth hooks or context bags in
the execution pipeline; future accounts and auth operations remain ordinary typed methods.

Runtime dependencies remain `pydantic` and `httpx`; changes to dependency declarations require a
direct task requirement.

## Deferred decisions

Real service contracts will determine:

- service URL and multi-service routing shape;
- authentication state and token-refresh responsibility;
- any future SDK-level timeout, header, proxy, TLS, pool, retry, or environment policy;
- omitted-field versus explicit-`null` encoding;
- HTTP-status semantics and streaming error bodies;
- endpoint wrappers, a possible synchronous SDK facade, and WebSocket/update behavior.

These areas are not promises in the current SDK. Client/session/HTTP-client ownership and
`Application`/`Client` lifecycle are fixed current behavior rather than deferred decisions.
