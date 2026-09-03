# Request and response pipeline

`PokerlostClient.__call__` verifies the supplied object is a `PokerlostMethod`, reads direct concrete
`operation`, `returning`, and `__scopes__` metadata, and builds one `PokerlostRequest(payload=method)`.
It neither serializes the method for revalidation nor binds a client to it.

One private immutable call combines that wire model with per-call options and a typed optional
access token. Public calls move directly through retry to transport. Protected calls first load
exact persistent state. The transport alone converts the token to a bearer header.

HTTPX sends the pure envelope with `json=`. Responses are decoded once into `PokerlostResponse`.
Failures become typed errors with safe scalar metadata. Success results are validated from the
decoded value. Raw response bodies and headers never enter exceptions.

Malformed transient gateway responses preserve only the status and can retry. A canonical expired
failure bubbles outside generic retry, triggers one refresh, rebuilds only the internal token field,
and replays the same method/envelope once.
