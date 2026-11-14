# Types and enums

Wire/value models remain flat under `pypokerlost.types`. Enum definitions live only under
`pypokerlost.enums`:

```python
from pypokerlost.enums import PokerlostErrorCode, PokerlostScopes, PrincipalStatus, PrincipalType
from pypokerlost.types import (
    PokerlostAccessTokenClaims,
    PokerlostAudience,
    PokerlostAuthorizationContext,
    PokerlostRequest,
    PokerlostResponse,
    PokerlostStoredToken,
    PokerlostToken,
    PokerlostTokenKey,
)
```

`PokerlostAudience` accepts an exact single-segment service name such as `authService` or
`accountsService`; it is intentionally not an enum. Tokens, claims, contexts, keys, and method
fields use members of the explicit SDK-owned `PokerlostScopes` catalog. Access-token claims contain
no authorization role and use the exact audience plus plural `scopes`.

`PokerlostAudience.for_service(ServiceId.ACCOUNTS)` explicitly selects the established
`accountsService` audience. It requires a `ServiceId` member; it does not infer an audience
from a gateway target, scope or deployment name. The regular audience constructor still
accepts other canonical service names, such as `futureService`.

`PokerlostErrorCode` owns only the four shared authentication/authorization codes:
authentication required, invalid or expired access token, and insufficient scope.
`PokerlostResponse.error` and `PokerlostAPIError.error` remain strings so service-owned
and future error codes preserve their wire values.

The static [SDK contract](sdk_contract.json) exports service IDs, common errors, shared
scopes, explicit audience mappings and envelope schemas. Its [SHA-256 digest](sdk_contract.json.sha256)
identifies the exact bytes. The catalog includes planned `pokerService` and future-facing
scopes; membership does not establish an implemented service, endpoint or readiness.
Consumers validate service IDs case-sensitively and handle unsupported values explicitly.

The exported JSON Schemas describe field shapes, not every runtime invariant.
`PokerlostResponse` also requires success to omit failure metadata, failure to have a
nonempty error and no result, and `retry_after` to be finite and nonnegative.
Keep these semantic checks when implementing a consumer; the common error-code schema
does not restrict the response's open string error field.

`PokerlostStoredToken` contains repr-hidden token data, an absolute UTC expiry, and a positive CAS
version. It is a persistence contract, not an in-memory cache implementation.

`PokerlostResponse` rejects negative/non-finite delays, retry metadata on success, failure results,
and failures without a stable code.
