# Request and response pipeline

This page follows one call from a typed method to a typed result.

## Preparation

`PokerlostClient.make_request()` validates the supplied `PokerlostMethod`, makes a shallow immutable
copy, binds the executing client, creates default `PokerlostRequestOptions` when omitted, and asks
`PokerlostRequestBuilder` for a public envelope.

The builder validates:

- single lowerCamelCase `operation`;
- canonical sorted and duplicate-free `required_scopes`;
- strict method payload fields.

Protected metadata without `PokerlostAuthorizationMiddleware` fails before I/O.

## Middleware

The exact order is:

```text
retry
→ authorization
→ transport
```

Retry makes one call when `retry_policy` is absent. Authorization returns public requests unchanged.
For a protected request it selects state by audience and exact scopes, refreshes or acquires under a
per-key lock, then constructs a new immutable authorized envelope.

A transport authentication error invalidates matching state and propagates. The middleware does
not replay that operation. An authorization error propagates without token refresh.

## Transport

`HttpxSession` performs exactly:

```python
await http_client.post(
    api_server.operation_url(operation),
    json=request.model_dump(mode="json", by_alias=False),
    timeout=timeout,
)
```

HTTPX supplies JSON framing. The SDK supplies no caller-controlled header mapping, cookie state,
query authentication, or form serializer. The cookie policy rejects ambient response cookies.

## Response decoding

Both success and failure statuses must contain JSON matching `PokerlostResponse`:

```text
ok
result
error
error_message
retry_after
```

An `ok=true` response requires a 2xx status and validates `result` against the method's `returning`
type with the executing client in Pydantic context. An `ok=false` response becomes
`PokerlostAPIError`, `PokerlostAuthenticationError`, or `PokerlostAuthorizationError`.

Malformed JSON, invalid envelope combinations, invalid body delay, invalid typed results, and
success envelopes on non-2xx statuses become `PokerlostProtocolError`. Raw bodies and secrets are
not stored in public errors.

See `docs/api/transport.md`, `docs/api/retry.md`, and `docs/index.md`.
