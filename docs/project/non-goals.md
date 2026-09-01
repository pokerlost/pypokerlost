# Project non-goals

`pypokerlost` deliberately remains a reusable typed API operation SDK rather than a home for
service business logic, authorization policy, or unrelated infrastructure.

## Service ownership

The SDK does not own:

- PokerLost service business logic or domain workflows;
- service databases, ORM models, repositories, or direct database access;
- accounts or authentication implementations;
- an OAuth2 scope policy, role policy, token server, credential ownership, or token lifecycle
  storage;
- business idempotency keys, payload fingerprints, workflow, outbox, or reconciliation state;
- concrete service-specific method packages in the core repository.

## Transport and execution

The current SDK does not provide:

- automatic service discovery or service routing;
- globally enabled retry or automatic replay after `401` or `403`;
- proof that a mutation is replay-safe from its HTTP method;
- streaming, WebSocket, or event APIs;
- multiple transport protocols;
- dynamic endpoint lookup or an endpoint-specific `Client` facade;
- runtime OpenAPI generation.

The repository `Dockerfile` builds artifacts only; a runtime application container, deployment
configuration, and publishing automation are outside its responsibility.

The SDK's explicit `PokerLostRetryPolicy` owns bounded transport attempts only. The consumer owns the same
business operation identifier and semantic payload across mutation attempts, target-side
idempotency guarantees, database transaction boundaries, and reconciliation after an ambiguous
outcome.

## Storage boundary

Client storage is explicit JSON-compatible application state. The SDK does not automatically save
requests or responses and does not provide predefined keys, encryption, transactions, queues,
pub/sub, expiration workers, or a bundled external persistence backend.

These are current product boundaries, not promises about a future roadmap. See
`docs/project/status.md` for the implemented surface and `SERVICE.md` for the authoritative product
boundary.

See `docs/index.md`.
