# Request and response pipeline

This page follows one method from validated request fields through HTTP transport to a declared,
client-bound result.

## Method preparation

`Client.make_request()` makes an isolated copy of the caller's `PokerlostMethod` and binds that
copy to the executing client. It then snapshots the configured middleware and builds the chain with
the first configured component outermost.

After middleware delegates, `RequestBuilder` validates `__api_method__` as an `APIOperation` and
`__http_method__` as a supported `HTTPMethod`. It prepares request data exactly once with:

```python
method.model_dump(
    mode="json",
    by_alias=False,
    exclude_unset=True,
)
```

This preserves the distinction between an omitted field and an explicitly supplied `None`.

## Request boundary

`RequestBuilder` produces a frozen, extra-forbid `Request` with only these fields:

```python
method: APIOperation
http_method: HTTPMethod
data: dict[str, JSONValue]
headers: tuple[tuple[str, str], ...]
```

It adds `Content-Type: application/json` and `Accept: application/json` unless custom headers
replace those names case-insensitively. `RequestOptions` is the only typed per-request extension;
it carries validated, immutable, ordered string headers.

`RequestBuilder` does not know the API server, construct a URL, call a JSON codec, produce bytes,
or perform I/O.

## HTTP transport

`HttpxSession` owns the concrete transport work:

1. build a `Request`;
2. obtain the operation URL from `APIServer`;
3. serialize `Request.data` with the configured `json_dumps`;
4. require the encoder to return `str` and encode it as UTF-8;
5. send the request through its lazily created `httpx.AsyncClient`;
6. pass response text and status to `ResponseHandler`.

The default encoder rejects non-finite values. `HttpxSession` is restartable: `close()` releases
its current HTTPX client, while a later request or `start()` creates a new one. This session-level
`close()` is distinct from the client-level `Client.stop()` operation.

HTTPX timeout failures become `ClientTimeoutError`; other HTTPX transport failures become
`ClientConnectionError`. Their causes are sanitized built-in exceptions that do not retain HTTPX
request objects, payloads, or headers.

## Response envelope

`ResponseHandler` first decodes and strictly validates this frozen, extra-forbid envelope:

```python
ok: bool
result: ResultT | None
error: str | None
error_message: str | None
```

A successful envelope cannot contain error metadata. A failed envelope cannot contain a non-null
result and must contain both error fields.

Interpretation order matters:

1. decoder failure becomes `ClientDecodeError`;
2. invalid envelope becomes `ClientDecodeError`;
3. every valid failed envelope becomes `PokerlostAPIError`, regardless of HTTP status;
4. a successful envelope with a non-2xx status becomes `PokerlostProtocolError`;
5. the result is encoded to strict JSON and validated against the method's `__returning__` type;
6. result encoding or validation failure becomes `ClientDecodeError`.

The declared result validation uses:

```python
validation_context = {"client": method.client}
```

Consequently, returned and nested `PokerlostType` objects can resolve the same client that executed
the method. Scalar, collection, and alias result types are also supported when declared by the
method.

## Ownership boundaries

| Component | Owns | Does not own |
|---|---|---|
| `RequestBuilder` | Metadata validation, JSON-mode model dump, headers, `Request` | URL, codecs, bytes, HTTP |
| `HttpxSession` | API target, URL, JSON codecs, UTF-8, HTTPX lifecycle and I/O | Full `Client`, middleware, storage |
| `ResponseHandler` | Decode, envelope validation, error mapping, result validation | HTTP resources, storage, routing |

Raw request bodies, raw response bodies, headers, cookies, and external exceptions containing
transport input are not attached to public SDK failures.

See `docs/api/transport.md` for public imports and constructors and `docs/api/middleware.md` for
request-option propagation.

See `docs/index.md`.
