# pypokerlost

SERVICE_NAME: pypokerlost  
SERVICE_SLUG: pypokerlost  
DISTRIBUTION_NAME: pypokerlost  
PACKAGE_NAME: pypokerlost  
REPOSITORY_ROOT: pokerlost  
PACKAGE_ROOT: pypokerlost

## Purpose

`pypokerlost` is the official asynchronous Python SDK foundation for PokerLost services.

The SDK provides a small typed client, transport abstraction, awaitable API method model, and
task-local current-client context. It is intentionally modeled after the ergonomic parts of
aiogram while refusing to grow endpoint-specific methods on the client itself.

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
- Provide typed transport request, transport response, and content-stream contracts.
- Provide an injectable transport abstraction and a production `httpx` implementation.
- Provide deterministic client and stream lifecycle management.
- Provide a focused exception hierarchy and safe transport/status/decoding error mapping.
- Provide package metadata, typing markers, documentation, development commands, and unit tests that
  make future API method implementation mechanical.

## Service-specific rules

- Never add concrete endpoint methods directly to `Client`.
- Never implement dynamic endpoint dispatch with `Client.__getattr__`.
- Concrete API operations are represented by method objects, not client attributes.
- `Client.__call__()` is only shorthand for `Client.make_request()`.
- `Method.__await__()` may resolve only a context-local client; it may not construct a client or read
  environment configuration.
- There is no process-wide default client.
- No concrete API method is added until its operation name, request fields, result contract, HTTP
  behavior, and response-envelope behavior are known.
- The exact server `ApplicationResponse` envelope must not be invented in the base SDK.
- No automatic retry behavior is added until idempotency and retry rules are defined.
- Authentication is not guessed. The foundation may support explicit headers, but token refresh and
  credential storage are out of scope until specified.
- WebSocket/event subscriptions, an `@event` decorator, reconnection, and subscription state are
  deferred to a later architecture task.
- The Dart client is a separate future project and does not shape this package's public API unless a
  cross-language contract is explicitly adopted.
- This repository contains no FastAPI application, persistence layer, database migration, Docker
  image, Helm chart, or service runtime.
