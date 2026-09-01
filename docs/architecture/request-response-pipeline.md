# Request and response pipeline

This page follows one immutable method invocation through outbound middleware, transport, the
universal PokerLost response envelope, and optional bounded retry.

## Method snapshot and metadata

`Client.make_request()` dumps only explicitly supplied method fields in Python mode, validates a
fresh instance of the same method type, and binds that deep semantic snapshot to the executing
client. The caller's method remains unchanged, and later mutation of caller-owned input cannot
change the in-flight payload or a later attempt.

Before middleware starts, `RequestBuilder.describe()` validates `__api_method__` as an
`APIOperation` and `__http_method__` as a supported `HTTPMethod`, and the client captures the
declared result type. The built-in terminal receives these captured values and does not read method
metadata again. Local method validation and metadata failures therefore never enter the middleware
or retry chain, and retries cannot change endpoint, HTTP method, or expected result type.

## Per-call options and middleware

The caller may supply one frozen `RequestOptions` through the top-level client call:

```python
result = await client(
    method,
    request_timeout=10,
    options=options,
)
```

The client builds its chain from the immutable constructor tuple. The first component is
outermost. Every component receives a new frozen `APIMiddlewareContext` containing only the
validated operation, HTTP method, and current options. `APIMiddlewareCallNext` captures the one
method snapshot, so public middleware cannot substitute a method or mutate its operation, body, or
declared result type.

The canonical authenticated order is:

```text
Client(method, options)
→ RetryMiddleware
→ BearerTokenMiddleware
→ session terminal
```

`RetryMiddleware` removes the policy from options before entering the inner chain. A duplicate
`RetryMiddleware` therefore cannot multiply attempts. Without an explicit policy, the chain passes
through exactly once.

## Bearer and token acquisition

`BearerTokenMiddleware` rejects an existing `Authorization` header, then asks its provider for a
token. A usable token comes from a monotonic process-local cache. A miss or near-expiry entry starts
or joins one shielded single-flight acquisition.

The provider's focused internal path is:

```text
ClientCredentialsTokenProvider
→ POST /oauth.token with form fields and HTTP Basic
→ private HttpxSession specialization
→ ResponseHandler
→ ApplicationResponse result validation
→ AccessToken cache entry
```

Only `grant_type`, sorted exact `scope`, and `resource` enter the form. Credentials remain in the
HTTP Basic header and are absent from the body. The success and failure responses use the same
`ApplicationResponse` decoder and canonical SDK exceptions as ordinary operations.

The provider makes one acquisition attempt itself. When retry is explicitly enabled and
`RetryMiddleware` is outside bearer middleware, a retryable acquisition failure repeats as part of
the same bounded outer call. There is no provider-internal default retry and no automatic replay
after `401` or `403`.

## Request boundary

After middleware delegates, `RequestBuilder` prepares data from the captured method snapshot with:

```python
method.model_dump(
    mode="json",
    by_alias=False,
    exclude_unset=True,
)
```

This preserves omitted fields versus explicitly supplied `None`. The builder produces a frozen,
extra-forbid `Request` with only:

```python
method: APIOperation
http_method: HTTPMethod
data: dict[str, JSONValue]
headers: tuple[tuple[str, str], ...]
```

It adds `Content-Type: application/json` and `Accept: application/json` unless current options
replace those names case-insensitively. Data and headers are excluded from public repr output;
headers are also excluded from serialization.

`RequestBuilder` does not know the API server, construct a URL, call a JSON codec, produce bytes,
or perform I/O.

## HTTP transport

`HttpxSession` owns the concrete transport work:

1. build a `Request`;
2. obtain the operation URL from `APIServer`;
3. serialize `Request.data` with the configured `json_dumps`;
4. require the encoder to return `str` and encode it as UTF-8;
5. send through its lazily created `httpx.AsyncClient`;
6. parse a safe numeric `Retry-After` delay when present;
7. pass response text, status, and that delay to `ResponseHandler`.

The default encoder rejects non-finite values. `HttpxSession` is restartable: `close()` releases
its current HTTPX client, while a later request or `start()` creates a new one.

HTTPX timeout failures become `ClientTimeoutError`. Network, proxy, and remote-protocol failures
become `ClientConnectionError`. Local protocol, unsupported transport, invalid URL, stream, and
request-configuration failures become non-retryable `ClientRequestError`; they are not mislabeled
as a connection failure. Method snapshot and metadata-preparation failures use the same safe class;
the original validation traceback is discarded so it cannot retain a sensitive request object.
Raw HTTPX exceptions are replaced rather than attached as causes.

## Universal response envelope

`ResponseHandler` decodes and strictly validates the four-field `ApplicationResponse` shape:

```python
ok: bool
result: ResultT | None
error: str | None
error_message: str | None
```

This includes `/oauth.token`; there is no raw OAuth2 success or error response path.

Interpretation order is:

1. decoder failure becomes `ClientDecodeError`;
2. invalid envelope becomes `ClientDecodeError`;
3. every valid failed envelope becomes `PokerlostAPIError`, regardless of HTTP status;
4. a successful envelope with a non-2xx status becomes `PokerlostProtocolError`;
5. the result is encoded to strict JSON and validated against the method's `__returning__` type;
6. result encoding or validation failure becomes `ClientDecodeError`.

Declared result validation receives `{"client": method.client}` as Pydantic context. Returned and
nested `PokerlostType` objects therefore resolve the client that executed the method. Scalars,
collections, and supported aliases also remain valid result types.

Raw request and response bodies, headers, cookies, credentials, access tokens, and external
exceptions containing transport input are never attached to public SDK failures. Sensitive
transport and decoder frames clear those references before propagation, so traceback-local capture
does not retain them either.

## Retry unwind

When the inner chain raises, explicit retry handles only connection and timeout errors plus
`PokerlostAPIError` or `ClientDecodeError` carrying status `408`, `425`, `429`, `500`, `502`, `503`,
or `504`. A malformed retryable-status response may therefore be attempted again; a decode failure
on an ordinary `2xx` response may not.

`401`, `403`, `404`, `409`, `410`, `422`, `PokerlostProtocolError`, local failures, and caller
cancellation pass out immediately. Before another attempt, middleware applies validated
`Retry-After` or full-jitter exponential backoff within the configured maximum and optional total
budget. The final canonical exception is preserved.

Every new attempt re-enters bearer middleware but reuses the same deep method snapshot and semantic
payload. The SDK does not establish business idempotency: mutation replay still requires the same
caller-owned business key, a target-side replay-safe contract, and reconciliation after ambiguous
outcomes. A consuming service must not keep a database transaction open across token acquisition,
remote I/O, or backoff sleep.

The exact policy matrix and delay formula live in `docs/api/middleware.md`.

## Ownership boundaries

| Component | Owns | Does not own |
|---|---|---|
| `Client` | Method snapshot, immutable chain, options entry, lifecycle | Business idempotency, database transactions |
| `APIMiddleware` | Safe context, option derivation, optional lifecycle | Method/body/result mutation, HTTPX objects |
| `RequestBuilder` | Metadata validation, JSON-mode dump, headers, `Request` | URL, codecs, bytes, HTTP |
| `HttpxSession` | API target, URL, JSON codecs, Retry-After, HTTPX lifecycle and I/O | Full client, middleware policy, storage |
| `ResponseHandler` | Decode, envelope validation, error mapping, result validation | HTTP resources, storage, routing |

See `docs/api/transport.md` for public transport constructors and `docs/api/middleware.md` for
authentication and retry configuration.

See `docs/index.md`.
