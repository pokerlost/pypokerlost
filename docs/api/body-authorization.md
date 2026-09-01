# Body authorization and token lifecycle

Pokerlost access tokens, client credentials, and refresh tokens travel only inside JSON payloads.
The transport is private to Pokerlost and does not expose a standard HTTP authentication scheme.

## Public imports

```python
from pypokerlost.methods import GetToken, RefreshToken
from pypokerlost.middleware import PokerlostAuthorizationMiddleware, PokerlostTokenStore
from pypokerlost.types import (
    PokerlostAuthorization,
    PokerlostAuthorizationContext,
    PokerlostClientCredentials,
    PokerlostScope,
    PokerlostToken,
    PokerlostTokenState,
)
```

`PokerlostAuthorization` contains only repr-hidden `access_token`. `PokerlostToken` contains a
repr-hidden access token, optional repr-hidden refresh token, positive `expires_in`, canonical exact
scopes, and audience. It is data only.

`PokerlostAuthorizationContext` represents the result of successful local service verification.
It contains principal identity, client identity, audience, exact scopes, and either human or
service bindings. It grants no role bypass.

## Middleware construction

```python
PokerlostAuthorizationMiddleware(
    *,
    auth_client: PokerlostClient,
    token_store: PokerlostTokenStore,
    credentials: PokerlostClientCredentials,
    audience: str,
    refresh_skew: float = 30.0,
    clock: Callable[..., float] = monotonic,
)
```

The auth client must not contain authorization middleware. It performs ordinary public `getToken`
or `refreshToken` calls and therefore cannot recurse into token acquisition.

## Token store port

The consumer implements only these async behaviors:

```python
class PokerlostTokenStore(Protocol):
    async def load(
        self,
        *,
        audience: str,
        scopes: tuple[PokerlostScope, ...],
    ) -> PokerlostTokenState | None: ...

    async def save(
        self,
        state: PokerlostTokenState,
        *,
        audience: str,
        scopes: tuple[PokerlostScope, ...],
    ) -> None: ...

    async def invalidate(
        self,
        *,
        audience: str,
        scopes: tuple[PokerlostScope, ...],
    ) -> None: ...
```

The key is audience plus the exact sorted scope tuple. The SDK ships no production persistence
implementation. `PokerlostTokenState.expires_at` is a process-local monotonic instant.

## Protected-call flow

For non-empty method scopes the middleware:

1. Loads exact-key state and reuses it only beyond the refresh skew.
2. Acquires one per-key lock when new state is needed.
3. Reloads state after the lock.
4. Calls `RefreshToken` when usable refresh material exists; otherwise calls `GetToken` with the
   configured credentials.
5. Validates returned audience and exact scopes.
6. Saves monotonic state.
7. Creates `PokerlostAuthorizedRequest` with `authorization.access_token`.
8. Calls downstream transport.

Concurrent acquisitions for one key collapse into one auth call. Public methods bypass every token
store operation.

An authentication error invalidates the matching key and propagates without replaying the current
call. An authorization error does not invalidate, refresh, or retry.

See `docs/api/transport.md`, `docs/api/retry.md`, and `docs/index.md`.
