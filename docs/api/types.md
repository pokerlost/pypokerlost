# Types and enums

Wire/value models remain flat under `pypokerlost.types`. Enum definitions live only under
`pypokerlost.enums`:

```python
from pypokerlost.enums import PokerlostScopes, PrincipalStatus, PrincipalType
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

`PokerlostStoredToken` contains repr-hidden token data, an absolute UTC expiry, and a positive CAS
version. It is a persistence contract, not an in-memory cache implementation.

`PokerlostResponse` rejects negative/non-finite delays, retry metadata on success, failure results,
and failures without a stable code.
