# Architecture overview

`pypokerlost` owns one typed call pipeline, flat SDK contracts, standard bearer-header injection,
canonical errors, bounded retry, narrow reactive refresh, and development-time OpenAPI generation.

```text
PokerlostMethod
→ direct __scopes__ validation
→ PokerlostAuthenticationMiddleware for protected calls
→ PokerlostRetryMiddleware when opted in
→ one private immutable call
→ HttpxSession JSON + optional Authorization Bearer
→ PokerlostResponse decoder
→ typed result or safe canonical error
```

A public method has `__scopes__ is None` and bypasses token state. A protected method has a
non-empty exact tuple of SDK-owned `PokerlostScopes` members. Missing or empty metadata is never
normalized to public.

Generic retry encloses authentication so its one logical-call budget includes persistent shared
UTC/versioned state loading and one service-owned refresh. A task-local claim remains consumed
across retry attempts. Authentication never loads credentials or automatically acquires an initial
token. Exact expiration can replay the unchanged request once because services must reject expired
tokens before handler entry.

Implemented OpenAPI operations are the only generator source. The shared scope catalog is an
explicit SDK contract:

```text
service-local Scopes
→ protected route Security(... scopes=[...])
→ standard OAuth2 OpenAPI security
→ generator validates against SDK PokerlostScopes
→ method.__scopes__
```

When a document has no protected operations, `components.securitySchemes` may be absent and every
generated method is public. Once a protected operation exists, the supported standard OAuth2
scheme and a non-empty exact requirement are mandatory. No scope map, vendor extension,
role-derived bypass, or body authorization contract exists.
