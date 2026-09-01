# Request and response pipeline

This page follows one generated invocation through immutable request construction, optional retry,
transport, and the standard PokerLost response envelope.

## Captured method metadata

`Client.make_request()` reconstructs a deep semantic snapshot from explicitly supplied method
fields and binds that snapshot to the executing client. It then validates and captures:

```text
__api_method__
__http_method__
__request_content_type__
__returning__
```

Local validation failures occur before retry. Later caller mutation cannot change the in-flight
payload, path, media type, or declared result.

## Request options and construction

The caller may provide one frozen options value:

```python
from pypokerlost.client.request import RequestOptions

options = RequestOptions().with_headers({"Authorization": "Bearer <resolved-token>"})
result = await client(method, options=options)
```

Header names are case-insensitively unique and values reject CR/LF. Headers are hidden from repr,
serialization, errors, and sensitive traceback frames. A caller cannot replace the generated
`Content-Type` header.

`RequestBuilder` dumps explicitly supplied method fields with:

```python
method.model_dump(
    mode="json",
    by_alias=False,
    exclude_unset=True,
)
```

The frozen request contains the operation, HTTP method, authoritative content type, request data,
and immutable headers.

## Optional retry

When `RequestOptions.retry` is absent, `Client` executes the transport closure once. With
`PokerLostRetryPolicy()`, the one direct executor may make at most three attempts within its fixed
five-second logical budget. It retries only canonical connection/timeout failures and canonical
errors carrying a listed retryable status. See `docs/api/retry.md`.

Every attempt uses the same method snapshot and semantic payload. The SDK does not make a mutation
business-safe and never creates an idempotency key or fingerprint.

## Transport serialization

`HttpxSession` obtains the operation URL from `APIServer`. JSON methods use the configured strict
JSON encoder. Form methods use deterministic UTF-8
`application/x-www-form-urlencoded` serialization of the generated string or flat string-array
request schema. The serializer is selected by method metadata, never by an operation-name special
case.

HTTPX timeout failures become `ClientTimeoutError`; network, proxy, and remote-protocol failures
become `ClientConnectionError`; local configuration or serialization failures become
`ClientRequestError`. Cancellation propagates unchanged.

## Response envelope

`ResponseHandler` strictly validates:

```text
ok: bool
result: ResultT | None
error: str | None
error_message: str | None
```

A failed envelope becomes `PokerlostAPIError`. A successful envelope with a non-2xx status becomes
`PokerlostProtocolError`. Decode or declared-result validation failures become `ClientDecodeError`.
The generated `oauth.token` method follows the same path and returns `OAuthTokenResponse` inside
this envelope.

Raw bodies, headers, credentials, and token values are not attached to public exceptions or their
traceback-local state.

See `docs/index.md`.
