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

Legacy direct clients keep that three-field key and existing serialized state; unset optional
fields are omitted from `model_dump()` and `model_dump_json()`. Their credentials are not isolated
between arbitrary origins. Owners must keep a separate persistent store/refresher namespace per
origin in legacy direct mode; shared persistent state requires the explicit environment namespace
migration below. Explicit [environment clients](api-server.md#explicit-environment-configuration)
opt into keys containing both `environment` and canonical `origin` as well. Bound authentication
must match the client target before token-store or HTTP activity.

Before opting in, the consuming owner must update storage namespaces, encryption/serialization
and acquisition/refresh code to use the full key. Persist `PokerlostStoredToken(key=key, ...)`
with the exact key used to acquire that state; every store load and refresh result must carry
matching provenance. This is a local persistence assertion owned by the adapter, not a verified
server token claim. Ignoring new key fields and returning legacy state fails locally rather than
sending its token. There is no automatic migration, fallback, acquisition or cross-origin reuse.
An explicitly bound state also cannot be returned to a different legacy key. CAS and invalidation
must address that same complete identity. These fields never enter `PokerlostToken`, operation
paths, request/response JSON or bearer-header values.

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
