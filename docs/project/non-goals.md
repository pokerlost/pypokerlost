# Project non-goals

`pypokerlost` is a typed protocol SDK, not a service business platform.

## Service ownership

The SDK does not own:

- service domain workflows, databases, ORM models, repositories, or migrations;
- account or authentication service implementations;
- client credential loading or production secret storage;
- access-token signing, verification, key publication, or rotation;
- route-side audience/scope policy or role expansion;
- production token-store persistence;
- business operation ID creation, mutation safety, workflow persistence, outboxes, or
  reconciliation.

## Transport boundary

The SDK does not provide:

- caller-controlled generic HTTP metadata;
- form, query, cookie, or alternate authentication transports;
- automatic service discovery, service routing, or an endpoint-specific client facade;
- globally enabled retry or replay of the failed operation after authentication failure;
- proof that an operation is safe to replay;
- streaming, WebSocket, event, or alternate transport protocols;
- runtime OpenAPI generation.

## Middleware boundary

`PokerlostTokenStore` is a port, not a bundled backend. Consumers own persistence, encryption,
credential sources, and deployment policy. Authorization middleware coordinates token calls but
does not authorize service routes.

Retry middleware owns bounded transport attempts only. Consumers retain the exact business
operation ID, semantic payload, target contract, database transaction boundaries, and ambiguous
outcome recovery.

See `SERVICE.md`, `docs/project/status.md`, and `docs/index.md`.
