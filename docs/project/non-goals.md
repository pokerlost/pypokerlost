# Project non-goals

`pypokerlost` is a typed protocol SDK, not a service business platform.

It does not own service domains, databases, migrations, client credential loading, initial token
acquisition, production token storage, encryption keys, cross-process lease implementation, JWT
signing or verification, route policy, account workflows, or deployment configuration.

It provides no generic HTTP metadata, form/query/cookie authentication, service discovery,
endpoint facade, global retry, streaming transport, runtime OpenAPI generation, or business
idempotency claim.

Authentication middleware is a narrow consumer of persistence/refresher ports. It may recover one
canonical expiration, but services own safe pre-handler rejection and business transaction
boundaries. Retry owns bounded transport attempts only.

Authorization is based exclusively on exact scopes; no authorization role abstraction exists.
