# Header authentication

Protected Pokerlost operations use one standard header:

```http
Authorization: Bearer <access-token>
```

The public SDK surface is:

```python
from pypokerlost.middleware import (
    PokerlostAuthenticationMiddleware,
    PokerlostTokenRefresher,
    PokerlostTokenStore,
)
from pypokerlost.types import PokerlostStoredToken, PokerlostTokenKey
```

`PokerlostTokenStore` loads, saves with an expected CAS version, and invalidates exact token state.
`PokerlostTokenRefresher` is implemented by the consuming service and coordinates refresh across
replicas. The key contains client identity, exact service-name audience, and the canonical non-empty
scope tuple. Stored expiry is an absolute timezone-aware UTC `datetime`; version is positive.

The SDK never owns credentials or automatic initial acquisition. A consuming service explicitly
calls `GetToken`, validates the response, encrypts token material, and persists it. When state is
missing, a protected call raises `PokerlostAuthenticationStateError` before I/O.

`expires_at` remains persistent coordination metadata; observing it locally does not itself trigger
a refresh. Only when the target returns exactly `POKERLOST_ACCESS_TOKEN_EXPIRED` does middleware
invalidate the observed version, refresh once, and replay the identical wire request once. Invalid
tokens, insufficient scopes, arbitrary 401/403 responses, and a second expiration never trigger
refresh.

Public methods have `__scopes__ is None`; they do not touch either port and send no bearer header.
An empty scope tuple is always a programming error.
