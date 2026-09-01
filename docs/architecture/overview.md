# Architecture overview

`pypokerlost` owns generic typed PokerLost transport, generated method and API-object conventions,
shared cross-service wire/value contracts, canonical transport exceptions, and one explicit retry
policy. Service business logic and token lifecycle orchestration stay outside the SDK.

## Runtime flow

```text
generated PokerlostMethod
→ Client method snapshot
→ RequestBuilder metadata and request construction
→ optional PokerLostRetryPolicy executor
→ HttpxSession transport
→ ResponseHandler
→ Response result validation
```

`Client` validates and captures the operation, HTTP method, request content type, and declared result
type once. It reuses the same deep method snapshot for every transport attempt. `RequestOptions`
contains only immutable generic headers and an optional canonical retry policy.

`RequestBuilder` produces a transport-independent frozen request. `HttpxSession` owns the target
URL, JSON or form serialization, UTF-8 bytes, HTTPX lifecycle and I/O, `Retry-After` parsing, and
response decoding. `ResponseHandler` preserves the fixed `ok`, `result`, `error`, and
`error_message` envelope.

## Runtime ownership

| Owner | Responsibility |
|---|---|
| `PokerlostMethod` | Strict request fields and immutable transport metadata. |
| `Client` | Method snapshot, session/storage ownership, direct retry entry, and task-local context. |
| `RequestOptions` | Secret-safe immutable caller headers and optional retry opt-in. |
| `RequestBuilder` | Metadata validation, request data, authoritative media type, and headers. |
| `PokerLostRetryPolicy` | Fixed bounded transport attempt classification and delays. |
| `HttpxSession` | API target, serialization, HTTP resources and I/O. |
| `ResponseHandler` | Envelope decoding, canonical errors, and declared result validation. |
| `contracts.authorization` | Shared token, claims, principal, and verified-context data shapes. |
| `Application` | One client lifecycle and optional caller lifecycle. |

## Authorization boundary

The SDK knows the wire shape of `OAuthTokenResponse`, decoded access-token claims, verified
authorization contexts, exact scope identifiers, and generated `oauth.token` transport metadata.
It does not decide when a token is needed, own credentials, orchestrate token lifecycle state, sign
or verify JWTs, fetch keys, expand roles, or make authorization decisions.

A consuming service owns this direction:

```text
application handler
→ service-owned application port
→ service-owned pypokerlost adapter
→ generated oauth.token method
```

## Generator flow

```text
OpenAPI 3.1 JSON
→ standard paths/requestBody/responses/components
→ exact shared-schema reuse
→ methods/<service>/ and types/<service>/
```

The only required project extension is top-level `x-pokerlost-service.id`. The generator uses no
route-level custom metadata. See `docs/architecture/generator.md`.

## Dependency direction

Request, response, and session modules do not import `Client`. Shared contracts do not import
transport. The generator is development tooling and imports only stable public runtime contracts.
Storage remains a client-owned sibling of transport.

See `docs/index.md`.
