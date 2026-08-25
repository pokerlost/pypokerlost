# pypokerlost Architecture

This document explains the initial SDK structure and runtime flow. Normative engineering rules live
in [`../AGENTS.md`](../AGENTS.md); concrete SDK purpose and scope live in
[`../SERVICE.md`](../SERVICE.md).

## Design goal

The SDK keeps the ergonomics of awaitable aiogram-style method objects without turning `Client` into
a generated collection of endpoint methods. It adopts aiogram's useful responsibility boundaries,
not its middleware system, binding model, Telegram serialization, upload abstractions, retry
behavior, dependency, or complete session API.

The public model is:

```text
typed method object
→ explicit Client or task-local current Client
→ thin Client facade
→ BaseSession template-method flow
→ centralized request building and response handling
→ typed result or resource-safe content stream
```

There are no concrete API methods in the initial foundation.

## Supported execution flows

### Explicit execution

```text
await client.make_request(method)
→ Client validates lifecycle
→ Client delegates to BaseSession.make_request(method)
→ RequestBuilder builds PreparedRequest
→ HttpxSession._execute returns RawResponse
→ ResponseHandler decodes ApplicationResponse[ResultT]
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
→ Client validates lifecycle
→ BaseSession.stream_content(stream_method)
→ RequestBuilder builds PreparedRequest
→ HttpxSession._open_stream opens the live response
→ ResponseHandler validates a non-success stream response
→ ContentStream yields byte chunks
→ context exit closes the response
```

Streaming does not buffer the full response. The stream remains explicit because an awaitable method
cannot safely express a resource lifetime by itself.

## Target package structure

```text
pypokerlost/
├── __init__.py
├── py.typed
├── client/
│   ├── client.py
│   └── current_client.py
├── methods/
│   ├── base_method.py
│   ├── method.py
│   └── stream_method.py
├── session/
│   ├── base_session.py
│   ├── httpx_session.py
│   ├── prepared_request.py
│   ├── raw_response.py
│   └── content_stream.py
├── request/
│   └── request_builder.py
├── response/
│   └── response_handler.py
├── contracts/
│   ├── response_model.py
│   └── application_response.py
├── openapi/
│   ├── access_role.py
│   ├── response_kind.py
│   └── rpc_openapi_extra.py
├── errors/
│   ├── pokerlost_error.py
│   ├── client_context_error.py
│   ├── client_closed_error.py
│   ├── application_error.py
│   ├── transport_error.py
│   ├── unexpected_status_error.py
│   └── response_decode_error.py
└── types/
    ├── http_method.py
    └── json_value.py
```

The exact number of packages may be reduced when implementation proves a directory unnecessary, but
these responsibilities must remain separated and the package root must stay small. The old
`transport/` API is removed rather than kept beside `session/`.

## Component boundaries

| Component | Responsibility |
| --- | --- |
| `client` | Public facade, lifecycle, current-client scope, and delegation. |
| `methods` | Strict immutable operation descriptions with explicit metadata and input data. |
| `session` | Shared execution algorithm, concrete `httpx` I/O, immutable boundary values, and live stream ownership. |
| `request` | Single uniform conversion from method models to `PreparedRequest`. |
| `response` | Single policy for combining HTTP status, envelope validity, and `ok`. |
| `contracts` | Frozen shared service/SDK wire models. |
| `openapi` | FastAPI-independent shared `x-pokerlost` metadata. |
| `errors` | Stable SDK exception hierarchy with safe diagnostic metadata. |
| `types` | Focused shared values such as `HttpMethod` and recursive JSON-compatible data. |
| package root | Small stable facade and installed distribution version. |

## Client

`Client` is a facade rather than an HTTP orchestrator or API surface generator.

Its public network API is limited to:

```python
await client.make_request(method)
await client(method)

async with client.stream_content(stream_method) as content:
    ...
```

The client:

- owns or receives a session;
- rejects use after close;
- delegates ordinary and streaming execution directly to that session;
- exposes deterministic close and async-context behavior;
- installs itself into current-client context only through explicit scope entry.

The client does not build requests, decode envelopes, inspect HTTP status, read stream error bodies,
know concrete endpoint names, expose dynamic methods, or retain a second copy of session HTTP
configuration.

Construction has two mutually exclusive forms:

```python
Client(
    base_url="https://accounts.internal",
    default_headers={...},
)
```

or:

```python
Client(
    session=custom_session,
    owns_session=False,
)
```

When a session is injected, `base_url`, default headers, and timeout are rejected. Those values
belong to `HttpxSession`; therefore `Client` cannot report a URL different from the URL actually
used for I/O.

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

## Method models

`BaseMethod` is the shared strict, frozen Pydantic v2 base. It defines class-level declarative
metadata:

```python
class BaseMethod(BaseModel, ABC):
    operation: ClassVar[str]
    http_method: ClassVar[HttpMethod] = HttpMethod.POST
```

Both ordinary and streaming methods inherit the same operation validation. `StreamMethod` does not
declare an abstract `operation` property that concrete classes replace with a string.

`Method[ResultT]` is:

- generic in its result;
- awaitable;
- independent of session implementation details;
- required to declare `result_type` explicitly as a class-level runtime Pydantic type token.

For example:

```python
class CreateAccountMethod(Method[CreateAccountResult]):
    operation = "accounts.create"
    result_type = CreateAccountResult
    http_method = HttpMethod.POST

    email: str
    password: str
```

The local `ClassVar[Any]` annotation for `result_type` is permitted because it is a runtime type
token. It is not public request or response data. The SDK never infers it from `__orig_bases__`,
`__pydantic_generic_metadata__`, or similar runtime implementation details.

The normal default path is derived from an RPC operation:

```text
accounts.create → /accounts.create
```

Method objects hold only operation metadata and immutable input fields. They do not implement
`build_request()`, `parse_response()`, arbitrary headers, or endpoint-specific HTTP behavior.
`StreamMethod` is not awaitable and is opened only through `Client.stream_content()`.

## Request building

`RequestBuilder` is one concrete class, not a protocol hierarchy. It accepts any `BaseMethod` and
builds an immutable `PreparedRequest`. It is the only owner of:

- RPC path derivation;
- `HttpMethod` selection;
- alias-free Pydantic serialization;
- consistent handling of method fields and `None`;
- the standard JSON-over-HTTP request shape.

This prevents future accounts and auth methods from silently choosing different paths,
serialization, headers, aliases, or body rules. If a future authoritative endpoint requires a new
HTTP shape, its declarative contract is designed explicitly rather than implemented as an arbitrary
method override.

## Sessions

`BaseSession` replaces the former transport abstraction; it is not a wrapper above it. It owns the
common template-method algorithm:

```text
make_request(method)
→ RequestBuilder.build(method)
→ _execute(prepared_request)
→ ResponseHandler.handle(method, raw_response)
→ ResultT
```

Its streaming counterpart builds the same `PreparedRequest`, calls `_open_stream()`, and uses the
same response policy for non-2xx error bodies. There is no parallel `Transport` API, compatibility
alias, session protocol, factory, registry, or middleware manager.

`HttpxSession` is the production adapter. It handles:

- base URL and relative-path joining;
- ownership of base URL, default headers, and timeout;
- headers and request data forwarding without mutating caller mappings;
- timeout configuration;
- ordinary HTTP execution into an immutable `RawResponse`;
- live content streaming;
- translation of known `httpx` failures into `TransportError`;
- deterministic closing.

`PreparedRequest`, `RawResponse`, and `ContentStream` are SDK-owned boundary values; public session
contracts do not expose `httpx.Request` or `httpx.Response`. The adapter preserves original
exceptions as causes and does not catch cancellation.

## Fixed application response contract

`ResponseModel` and `ApplicationResponse` are shared platform wire contracts in
`pypokerlost.contracts`. Services import them from the SDK instead of maintaining copies tied to a
particular FastAPI project layout.

`ResponseModel` preserves the existing service-template configuration without functional changes:

```python
class ResponseModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        validate_default=True,
    )
```

`ApplicationResponse` is frozen at exactly four fields, their existing defaults, and the existing
single validator:

```python
class ApplicationResponse[ResultT](ResponseModel):
    ok: bool = Field(description="Whether the operation completed successfully.")
    result: ResultT | None = Field(default=None, description="Typed successful result.")
    error: str | None = Field(default=None, description="Stable machine-readable error code.")
    error_message: str | None = Field(default=None, description="Safe public error message.")

    @model_validator(mode="after")
    def validate_envelope(self) -> Self:
        if self.ok:
            if self.error is not None or self.error_message is not None:
                raise ValueError("Successful responses cannot contain error metadata")
            return self
        if self.result is not None:
            raise ValueError("Failed responses cannot contain a result")
        if self.error is None or self.error_message is None:
            raise ValueError("Failed responses require error metadata")
        return self
```

No aliases, additional fields, automatic population, reinterpretation, or extra validators are
allowed. In particular, `ok=True, result=None` is valid for an operation with no result.

## Central response policy

`ResponseHandler` is one concrete policy class. Concrete methods do not parse responses, and the
session does not expose Pydantic validation failures. For an ordinary method it parameterizes
`ApplicationResponse` with the method's explicit `result_type`, decodes the body, and combines the
envelope state with HTTP status exactly as follows:

| HTTP status | Envelope | Behavior |
| --- | --- | --- |
| 2xx | valid, `ok=True` | Return `result`. |
| any | valid, `ok=False` | Raise `ApplicationError`. |
| non-2xx | valid, `ok=True` | Raise `UnexpectedStatusError`; the service or proxy violated the protocol. |
| 2xx | invalid | Raise `ResponseDecodeError`. |
| non-2xx | invalid | Raise `UnexpectedStatusError` with a bounded safe body excerpt. |

This ordering preserves stable application codes such as `account_not_found` even when the service
uses HTTP 404. HTML proxy pages, empty responses, malformed JSON, and successful envelopes paired
with failure statuses remain protocol failures. Pydantic `ValidationError` never leaks through the
SDK boundary.

No `Client`, `RawResponse`, or `ContentStream` helper independently defines an `is_success` policy.
The combination of status and envelope belongs only to `ResponseHandler`.

For streaming, a 2xx response is yielded live without pre-buffering. For a non-2xx response the
session and handler:

1. read only a bounded error body;
2. attempt to decode `ApplicationResponse[None]`;
3. raise `ApplicationError` for a valid `ok=False` envelope;
4. raise `UnexpectedStatusError` for invalid content or `ok=True`;
5. close the response in every path.

## Shared OpenAPI metadata

`rpc_openapi_extra()` is a pure SDK helper with no FastAPI import. Its related enums are fixed:

```python
class AccessRole(StrEnum):
    PUBLIC = "public"
    USER = "user"
    SUPPORT = "support"
    MASTER = "master"
    AUTO = "auto"


class ResponseKind(StrEnum):
    APPLICATION_RESPONSE = "application_response"
    CONTENT_STREAM = "content_stream"
```

The helper signature is:

```python
def rpc_openapi_extra(
    *,
    access: tuple[AccessRole, ...],
    success_response: ResponseKind = ResponseKind.APPLICATION_RESPONSE,
) -> dict[str, JsonValue]: ...
```

An ordinary operation produces this stable shape:

```python
{
    "x-pokerlost": {
        "contract_version": 1,
        "access": {
            "any_of": ["auto", "master"],
        },
        "response": {
            "success": "application_response",
            "error": "application_response",
        },
    },
}
```

A stream declares `"success": "content_stream"` while retaining
`"error": "application_response"`. Empty access is invalid, duplicate roles fail fast, `public`
cannot be combined with another role, output order is deterministic, and every call returns a new
fully JSON-compatible dictionary.

The extension does not duplicate `operationId`, path, request bodies, or response schemas already
owned by the OpenAPI operation. It contains no Python class references. It describes access and
response contracts only; it performs no authorization, token acquisition, service discovery, or
cross-service call.

## Error model

The hierarchy starts at `PokerLostError` and distinguishes:

- missing current client;
- use of a closed client;
- HTTP transport failure;
- valid application failure;
- unexpected HTTP status;
- response decoding failure.

`ApplicationError` retains exactly the useful application metadata:

```python
error: str
error_message: str
operation: str
status_code: int
```

One stable exception with an `error` code is sufficient. Error-code-specific Python subclasses are
introduced only after a concrete practical need.

Errors may include operation and status metadata. Response excerpts must be bounded and safe.
Authorization values, cookies, tokens, and full payloads must never be placed in messages or logs.

## Lifecycle and ownership

Object construction performs no network I/O.

`Client.close()` is asynchronous and idempotent. If the client creates its session, it closes it.
An injected session remains caller-owned unless `owns_session=True` is passed explicitly.

`async with client:` combines current-client installation with deterministic client cleanup.
`client.as_current()` installs only context when a caller manages lifecycle elsewhere.

A content stream is owned by its `async with` block and closes even after early exit.

## Concurrency

- Current-client resolution uses `ContextVar`.
- Method instances are immutable and safe to reuse as values, subject to endpoint semantics.
- Session implementation must support concurrent requests according to its documented client
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
- authentication or token-refresh policy;
- retry policy;
- WebSocket sessions, subscriptions, reconnection, or `@event` decorator;
- synchronous client;
- service runtime, database, migration, Docker, or Helm configuration.

These are added only when their contracts and ownership are explicit.
