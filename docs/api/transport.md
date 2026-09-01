# Body-only transport

Every Pokerlost business operation is `POST /<operationId>` with JSON input and a
`PokerlostResponse` JSON output. The operation ID is a single lowerCamelCase verb name.

## Public call

```json
{
  "payload": {
    "username": "alice"
  }
}
```

The exact model is `PokerlostRequest[PayloadT]`.

## Protected call

```json
{
  "authorization": {
    "access_token": "<secret>"
  },
  "payload": {
    "account_id": "7f864ce5-a4f0-4ff1-b5b7-bd958a961447"
  }
}
```

The exact model is `PokerlostAuthorizedRequest[PayloadT]`. The token has no prefix and exists in no
other request location.

## Token acquisition

`GetToken` sends:

```json
{
  "payload": {
    "client_id": "service-client-id",
    "client_secret": "<secret>",
    "scopes": [
      "auth.internal.provisionHuman"
    ],
    "audience": "authService"
  }
}
```

`RefreshToken` sends:

```json
{
  "payload": {
    "refresh_token": "<secret>",
    "scopes": null,
    "audience": "accountsService"
  }
}
```

Both methods are public at the transport layer. Refresh does not require an access token.

## Success response

```json
{
  "ok": true,
  "result": {
    "account_id": "7f864ce5-a4f0-4ff1-b5b7-bd958a961447"
  },
  "error": null,
  "error_message": null,
  "retry_after": null
}
```

## Retryable failure

```json
{
  "ok": false,
  "result": null,
  "error": "SERVICE_TEMPORARILY_UNAVAILABLE",
  "error_message": "Try again later.",
  "retry_after": 1.5
}
```

Success requires `result` or null and no failure metadata. Failure requires a stable error code,
requires `result=null`, and may contain a sanitized message and body retry delay.

## HTTP boundary

HTTPX's `json=` call supplies the media framing. Project code does not construct or accept generic
header mappings, authentication headers, content negotiation, cookie authentication, query tokens,
or form bodies. Normal response data is decoded from the body for both 2xx and non-2xx statuses.

`HttpxSession(*, api_server=..., timeout=10.0)` requires a positive attempt timeout. Production
targets require HTTPS; loopback development may use HTTP.

See `docs/api/client.md`, `docs/api/body-authorization.md`, and `docs/index.md`.
