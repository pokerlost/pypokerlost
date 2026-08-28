# Project non-goals

`pypokerlost` deliberately remains a reusable typed API operation SDK rather than a home for
service business logic, authorization policy, or unrelated infrastructure.

## Service ownership

The SDK does not own:

- PokerLost service business logic or domain workflows;
- service databases, ORM models, repositories, or direct database access;
- accounts or authentication implementations;
- an OAuth2 scope policy, role policy, token server, token refresh flow, or credential storage;
- concrete service-specific method packages in the core repository.

## Transport and execution

The current SDK does not provide:

- automatic service discovery or service routing;
- a generic retry or request replay framework;
- streaming, WebSocket, or event APIs;
- multiple transport protocols;
- dynamic endpoint lookup or an endpoint-specific `Client` facade;
- runtime OpenAPI generation.

The repository `Dockerfile` builds artifacts only; a runtime application container, deployment
configuration, and publishing automation are outside its responsibility.

## Storage boundary

Client storage is explicit JSON-compatible application state. The SDK does not automatically save
requests or responses and does not provide predefined keys, encryption, transactions, queues,
pub/sub, expiration workers, or a bundled external persistence backend.

These are current product boundaries, not promises about a future roadmap. See
[Project status](status.md) for the implemented surface and [`SERVICE.md`](../../SERVICE.md) for
the authoritative product boundary.

[Documentation index](../index.md)
