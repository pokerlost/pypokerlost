# pypokerlost

SERVICE_NAME: pypokerlost  
SERVICE_SLUG: pypokerlost  
DISTRIBUTION_NAME: pypokerlost  
PACKAGE_NAME: pypokerlost  
REPOSITORY_ROOT: pokerlost  
PACKAGE_ROOT: pypokerlost

## Purpose

`pypokerlost` is the official asynchronous Python SDK foundation for PokerLost services.

The SDK provides a small typed client, a session abstraction, declarative awaitable API method
models, centralized HTTP request and response policy, shared platform contracts, and a task-local
current-client context. It takes only the useful responsibility boundaries from aiogram while
refusing to grow endpoint-specific methods on the client itself or depend on aiogram.

The initial repository is a working library foundation for future typed methods. It does not define
any concrete PokerLost API operation yet.

## Responsibilities

- Provide an asynchronous `Client` with exactly two explicit network entry points:
  `make_request()` and `stream_content()`.
- Support explicit ordinary method execution through both
  `await client.make_request(method)` and `await client(method)`.
- Support implicit ordinary method execution through `await method` while a current client is
  installed in task-local context.
- Provide strict immutable base models for future ordinary and streaming methods.
- Require each ordinary method to declare its result type explicitly without runtime generic
  introspection.
- Provide a single `RequestBuilder` that turns method descriptions into immutable
  `PreparedRequest` values.
- Provide an injectable `BaseSession` template-method abstraction and a production `HttpxSession`.
- Provide immutable `RawResponse` values and resource-safe `ContentStream` values without exposing
  `httpx` public types.
- Decode every ordinary JSON result centrally through `ResponseHandler` and the shared
  `ApplicationResponse[ResultT]` envelope.
- Preserve stable application error codes in `ApplicationError`, including for valid non-2xx
  application failures.
- Provide the shared `x-pokerlost` OpenAPI extension through FastAPI-independent enums and
  `rpc_openapi_extra()`.
- Provide deterministic client and stream lifecycle management.
- Provide a focused exception hierarchy and safe application/transport/status/decoding error
  mapping.
- Provide package metadata, typing markers, documentation, and development commands that make
  future API method implementation mechanical.

## Fixed platform contracts

`ApplicationResponse[ResultT]` is the only handled JSON operation envelope. It is defined once in
`pypokerlost.contracts` and imported by concrete services rather than copied into each service. Its
four fields are frozen:

```python
ok: bool
result: ResultT | None = None
error: str | None = None
error_message: str | None = None
```

Its existing service-template validator is authoritative: success forbids error metadata; failure
forbids a result and requires both error fields. A successful empty result remains valid. The SDK
also preserves the service-template `ResponseModel` configuration without aliases or functional
changes.

`rpc_openapi_extra()` is the single producer of shared operation metadata under `x-pokerlost`. The
extension starts at contract version `1`, declares deterministic access roles and success/error
response kinds, and remains plain JSON-compatible data with no FastAPI dependency. It describes a
contract; it does not perform authorization, token acquisition, service discovery, or remote calls.

## Service-specific rules

- Never add concrete endpoint methods directly to `Client`.
- Never implement dynamic endpoint dispatch through client attributes.
- Concrete API operations are represented by method objects, not client attributes.
- `Client.__call__()` is only shorthand for `Client.make_request()`.
- `Method.__await__()` may resolve only a context-local client; it may not construct a client or read
  environment configuration.
- Method objects are immutable descriptions of operation metadata and input data. They neither
  build HTTP requests nor parse responses.
- Every concrete ordinary method declares `operation`, `http_method`, and `result_type` explicitly.
- `RequestBuilder` owns uniform path and body construction; `ResponseHandler` owns all envelope and
  HTTP-status interpretation.
- `Client` is a thin facade for lifecycle, current-client context, and delegation to `BaseSession`.
- The obsolete `Transport` and `HttpxTransport` APIs are replaced by `BaseSession` and
  `HttpxSession`; no compatibility aliases or parallel layers are retained.
- `base_url`, headers, and timeout belong to `HttpxSession`, not `Client`. A caller supplies either
  HTTP configuration for a client-created session or an injected session, never both.
- There is no process-wide default client.
- No concrete API method is added until its operation name, request fields, result contract, and
  exceptional HTTP behavior are authoritative. The common request and response protocol is already
  fixed by this SDK.
- Valid `ok=False` envelopes always become `ApplicationError`, regardless of HTTP status. Invalid
  non-2xx bodies and valid `ok=True` non-2xx responses become `UnexpectedStatusError`; invalid 2xx
  bodies become `ResponseDecodeError`.
- No automatic retry behavior is added until idempotency and retry rules are defined.
- Authentication is not guessed. The foundation may support explicit headers, but token refresh and
  credential storage are out of scope until specified.
- WebSocket/event subscriptions, an `@event` decorator, reconnection, and subscription state are
  deferred to a later architecture task.
- The Dart client is a separate future project and does not shape this package's public API unless a
  cross-language contract is explicitly adopted.
- This repository contains no FastAPI application, persistence layer, database migration, Docker
  image, Helm chart, or service runtime.
