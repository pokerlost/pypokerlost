# Transport

Every business call uses `POST /<operation>` and JSON. The only wire request envelope is:

```json
{"payload": {}}
```

It contains no method binding, options, access token, generic headers, or middleware metadata.
Private execution state lives in one immutable internal call. For protected operations only,
`HttpxSession` converts its typed token field to `Authorization: Bearer ...`; it never exposes a
generic header map.

Every decoded response uses:

```json
{
  "ok": false,
  "result": null,
  "error": "POKERLOST_ACCESS_TOKEN_EXPIRED",
  "error_message": "The access token has expired.",
  "retry_after": null
}
```

Both 2xx and non-2xx bodies follow this envelope. A malformed body becomes
`PokerlostProtocolError` with safe HTTP status metadata but no raw body. Typed results are validated
directly from the already decoded value; the client performs no JSON dump/revalidation round trip.
