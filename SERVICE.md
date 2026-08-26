# pypokerlost

SERVICE_NAME: pypokerlost  
SERVICE_SLUG: pypokerlost  
DISTRIBUTION_NAME: pypokerlost  
PACKAGE_NAME: pypokerlost  
REPOSITORY_ROOT: pokerlost  
PACKAGE_ROOT: pypokerlost

## Purpose

`pypokerlost` is the asynchronous Python SDK core for PokerLost services. Its intended ergonomics
combine a central Pyrogram-like `Client` with aiogram-like typed RPC method objects. These projects
are references only and are not dependencies.

The current package provides the mechanism needed to execute typed ordinary methods and manage raw
content streams. It contains no concrete PokerLost operations yet.

## Current product surface

Ordinary methods support explicit execution:

```python
await client.make_request(method)
await client(method)
await method.execute(client)
```

Ambient task-local execution is opt-in:

```python
with client.as_current():
    result = await method
```

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
```

Network configuration remains in `httpx.AsyncClient`. `Client.close()` delegates to its session;
the broader ownership and lifecycle policy is not yet a product contract.

## Responsibilities

- `Client`: session facade and task-local current-client scope.
- method bases: immutable Pydantic request values plus declarative operation/result metadata.
- `BaseSession`: shared ordinary and streaming execution flow.
- `RequestBuilder`: method-to-request translation.
- `ResponseHandler`: application-envelope validation and declared-result decoding.
- `HttpxSession`: thin I/O adapter over a caller-configured `httpx.AsyncClient`.
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
processing, or a test suite.

Runtime dependencies remain `pydantic` and `httpx`; changes to dependency declarations require a
direct task requirement.

## Deferred decisions

Real service contracts will determine:

- service URL and multi-service routing shape;
- authentication state and token-refresh responsibility;
- session/client ownership and sharing;
- client start/stop, async context, reentrancy, and WebSocket lifecycle;
- timeout, headers, proxy, TLS, pool, retry, and environment behavior;
- omitted-field versus explicit-`null` encoding;
- HTTP-status semantics and streaming error bodies;
- endpoint wrappers and a possible synchronous facade.

These areas are not promises or prohibitions in the current SDK.
