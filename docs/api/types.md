# Types

The flat `pypokerlost.types` facade owns canonical wire and value models.

## Core imports

```python
from pypokerlost.types import (
    PokerlostAuthorization,
    PokerlostAuthorizationContext,
    PokerlostAuthorizedRequest,
    PokerlostClientCredentials,
    PokerlostOperation,
    PokerlostRequest,
    PokerlostResponse,
    PokerlostScope,
    PokerlostToken,
    PokerlostTokenState,
)
```

`PokerlostOperation` validates `^[a-z][A-Za-z0-9]*$`. `PokerlostScope` validates at least two dotted
lowerCamelCase segments. Scope helpers provide canonical sorting, duplicate rejection, and the
internal space-delimited claim representation.

## Request and response models

```python
class PokerlostRequest[PayloadT](BaseModel):
    payload: PayloadT


class PokerlostAuthorizedRequest[PayloadT](BaseModel):
    authorization: PokerlostAuthorization
    payload: PayloadT


class PokerlostResponse[ResultT](BaseModel):
    ok: bool
    result: ResultT | None = None
    error: str | None = None
    error_message: str | None = None
    retry_after: float | None = None
```

Impossible success/failure combinations are rejected. A body retry delay must be finite and
non-negative.

## Token models

```python
class PokerlostToken(BaseModel):
    access_token: str
    refresh_token: str | None = None
    expires_in: int
    scopes: tuple[PokerlostScope, ...]
    audience: str


class PokerlostTokenState(BaseModel):
    token: PokerlostToken
    expires_at: float
```

Token and credential secrets are repr-hidden and validation input is hidden. They still serialize
because the JSON protocol requires them. Token models perform no network, persistence, signing, or
verification.

## Other exports

The facade also exports:

- `PokerlostType` and `MutablePokerlostType` for API objects with private client binding;
- `PokerlostAccessTokenClaims` for validated internal claim data;
- `PrincipalType`, `PrincipalStatus`, and `AuthorizationRole`;
- `GetTokenRequest`, `RefreshTokenRequest`, and focused request/response types used by current auth
  method stubs;
- `JSONScalar` and `JSONValue`.

There are no service namespaces, generic HTTP types, storage types, or compatibility contract
facades.

See `docs/architecture/types-and-methods.md` and `docs/index.md`.
