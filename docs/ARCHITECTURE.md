# pypokerlost Architecture

This document explains the initial SDK structure and runtime flow. Normative engineering rules live
in [`../AGENTS.md`](../AGENTS.md); concrete SDK purpose and scope live in
[`../SERVICE.md`](../SERVICE.md).

## Design goal

The SDK keeps the ergonomics of awaitable aiogram-style method objects without turning `Client` into
a generated collection of endpoint methods.

The public model is:

```text
typed method object
→ explicit Client or task-local current Client
→ Client orchestration
→ Transport
→ HTTP
→ typed response parsing
```

There are no concrete API methods in the initial foundation.

## Supported execution flows

### Explicit execution

```text
await client.make_request(method)
→ Client validates lifecycle
→ method builds TransportRequest
→ Transport executes HTTP request
→ Client validates HTTP status
→ method parses TransportResponse
→ typed result
```

### Callable-client execution

```text
await client(method)
→ Client.__call__
→ Client.make_request
→ same explicit execution flow
```

`Client.__call__()` adds no separate behavior and owns no endpoint registry.

### Implicit current-client execution

```text
async with client
→ ContextVar token installs client
→ await method
→ Method.__await__
→ current-client resolver
→ Client.make_request
→ typed result
→ context exit resets the exact token
```

The current client is task-local. Nested scopes restore the prior client. A method stores only its
request data and class-level operation metadata; it never stores a client reference.

Calling `await method` without an installed client fails immediately with `ClientContextError`.
Client construction is never implicit.

### Streaming execution

```text
client.stream_content(stream_method)
→ asynchronous context manager
→ stream method builds TransportRequest
→ Transport opens response stream
→ Client validates HTTP status
→ ContentStream yields byte chunks
→ context exit closes the response
```

Streaming does not buffer the full response. The stream remains explicit because an awaitable method
cannot safely express a resource lifetime by itself.

## Initial package structure

```text
pypokerlost/
├── __init__.py
├── py.typed
├── client/
│   ├── __init__.py
│   ├── client.py
│   └── current_client.py
├── methods/
│   ├── __init__.py
│   ├── method.py
│   └── stream_method.py
├── transport/
│   ├── __init__.py
│   ├── transport.py
│   ├── httpx_transport.py
│   ├── transport_request.py
│   ├── transport_response.py
│   └── content_stream.py
├── errors/
│   ├── __init__.py
│   ├── pokerlost_error.py
│   ├── client_context_error.py
│   ├── client_closed_error.py
│   ├── transport_error.py
│   ├── unexpected_status_error.py
│   └── response_decode_error.py
└── types/
    ├── __init__.py
    └── json_value.py
```

The exact split may be reduced when implementation proves a file unnecessary, but responsibilities
must remain separated and the package root must stay small.

## Component boundaries

| Component | Responsibility |
| --- | --- |
| `client` | Public orchestration, lifecycle, current-client scope, explicit execution, and stream ownership. |
| `methods` | Strict immutable ordinary and streaming request models plus extension contracts for future API methods. |
| `transport` | HTTP-independent request/response values, transport protocol, `httpx` adapter, and stream wrapper. |
| `errors` | Stable SDK exception hierarchy with safe diagnostic metadata. |
| `types` | Focused shared typing values such as recursive JSON-compatible data. |
| package root | Small stable facade and installed distribution version. |

## Client

`Client` owns orchestration rather than API surface generation.

Its public network API is limited to:

```python
await client.make_request(method)
await client(method)

async with client.stream_content(stream_method) as content:
    ...
```

The client:

- normalizes and retains the base URL;
- owns or receives a transport;
- rejects use after close;
- delegates request construction to method objects;
- delegates HTTP execution to transport;
- checks status before result parsing;
- delegates ordinary response parsing back to the method contract;
- exposes deterministic close and async-context behavior;
- installs itself into current-client context only through explicit scope entry.

The client does not know concrete endpoint names and does not expose dynamic methods.

## Current-client context

A dedicated `ContextVar` stores `Client | None`.

Context installation returns a token. Every exit resets that token in `finally`, which preserves
nested scopes and prevents leaked state after exceptions.

This mechanism provides only:

```python
result = await method
```

It does not provide hidden client construction, process-wide configuration, environment lookup, or a
global singleton.

Because Python context is copied into child tasks, callers remain responsible for deciding whether a
spawned task should inherit the current client. The SDK does not add custom task-local registries.

## Method model

`Method[ResultT]` is:

- generic in its result;
- strict and immutable;
- awaitable;
- independent of transport implementation details beyond the SDK's own `TransportRequest` and
  `TransportResponse` values;
- responsible for its stable operation name, request serialization, and typed response parsing.

The normal default path is derived from an RPC operation:

```text
accounts.create → /accounts.create
```

A concrete method can override request construction for a confirmed exceptional endpoint.

`StreamMethod` shares request-construction semantics but is not awaitable. It is opened only through
`Client.stream_content()`.

## Transport

`Transport` is a small async contract with separate ordinary-request and stream-opening operations.
Its public values are SDK-owned types, not `httpx.Request` or `httpx.Response`.

`HttpxTransport` is the first production adapter. It handles:

- base URL and relative-path joining;
- headers and query/body forwarding;
- timeout configuration;
- ordinary HTTP execution;
- live content streaming;
- translation of known `httpx` failures into `TransportError`;
- deterministic closing.

The adapter preserves original exceptions as causes and does not catch cancellation.

## Response parsing

The client validates transport success and then invokes method-level parsing.

The foundation intentionally does not define the final PokerLost `ApplicationResponse` envelope
because its exact fields and error semantics have not been supplied here. This prevents an invented
contract from becoming public API.

Once the envelope is authoritative, it may be introduced as a focused shared decoder or typed generic
model without changing the execution forms.

## Error model

The hierarchy starts at `PokerLostError` and distinguishes:

- missing current client;
- use of a closed client;
- HTTP transport failure;
- unexpected HTTP status;
- response decoding failure.

Errors may include operation and status metadata. Response excerpts must be bounded and safe.
Authorization values, cookies, tokens, and full payloads must never be placed in messages or logs.

## Lifecycle and ownership

Object construction performs no network I/O.

`Client.close()` is asynchronous and idempotent. If the client creates its transport, it closes it.
If a transport is injected, ownership is explicit.

`async with client:` combines current-client installation with deterministic client cleanup.
`client.as_current()` installs only context when a caller manages lifecycle elsewhere.

A content stream is owned by its `async with` block and closes even after early exit.

## Concurrency

- Current-client resolution uses `ContextVar`.
- Method instances are immutable and safe to reuse as values, subject to endpoint semantics.
- Transport implementation must support concurrent requests according to its documented client
  limits.
- No mutable request headers or payload mappings are shared with caller code.
- Cancellation propagates normally.
- No implicit retries occur.

## Future method layout

Concrete methods are added only after their contracts are known.

A simple method can use suffix-based files:

```text
pypokerlost/methods/accounts/create_account_method.py
pypokerlost/methods/accounts/create_account_result.py
```

A larger operation can use an operation package:

```text
pypokerlost/methods/accounts/create_account/
├── method.py
└── result.py
```

The package would define `CreateAccountMethod` and `CreateAccountResult`. Endpoint-specific
convenience methods are never added to `Client`.

## Deliberately unfinished

The initial SDK foundation intentionally contains no:

- concrete API operations;
- final application response-envelope model;
- authentication or token-refresh policy;
- retry policy;
- WebSocket transport, subscriptions, reconnection, or `@event` decorator;
- synchronous client;
- service runtime, database, migration, Docker, or Helm configuration.

These are added only when their contracts and ownership are explicit.
