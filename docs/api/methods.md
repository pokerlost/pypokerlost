# Methods

`PokerlostMethod[ResultT]` is the strict base for flat typed operation calls.

## Public imports

```python
from pypokerlost import PokerlostMethod
from pypokerlost.methods import (
    AssignPrincipalRole,
    GetJwks,
    GetToken,
    IssueLoginGrant,
    ProvisionHuman,
    RefreshToken,
    SetPrincipalStatus,
)
```

Methods are imported directly from `pypokerlost.methods`; there are no service subpackages and no
redundant class suffix.

## Metadata

```python
from pypokerlost import PokerlostMethod
from pypokerlost.types import PokerlostOperation, PokerlostScope


class GetMe(PokerlostMethod[str]):
    operation = PokerlostOperation("getMe")
    required_scopes = (PokerlostScope("accounts.self.read"),)
    returning = str
```

The operation must be one single lowerCamelCase identifier. Every business invocation is POST to
that operation's root path. Public methods declare `required_scopes = ()`; protected methods
declare the exact canonical tuple.

Payload fields are ordinary strict Pydantic fields on the method. The request builder serializes
the entire method as `payload`; method metadata is class-level and never appears in JSON.

## Current auth methods

| Class | Operation | Transport scopes | Server status in this foundation |
| --- | --- | --- | --- |
| `GetToken` | `getToken` | public | Implemented by authService. |
| `RefreshToken` | `refreshToken` | public | Future-facing SDK stub. |
| `GetJwks` | `getJwks` | public | Future-facing SDK stub. |
| `ProvisionHuman` | `provisionHuman` | `auth.internal.provisionHuman` | Future-facing SDK stub. |
| `SetPrincipalStatus` | `setPrincipalStatus` | `auth.internal.setPrincipalStatus` | Future-facing SDK stub. |
| `AssignPrincipalRole` | `assignPrincipalRole` | `auth.internal.assignPrincipalRole` | Future-facing SDK stub. |
| `IssueLoginGrant` | `issueLoginGrant` | `auth.internal.issueLoginGrant` | Future-facing SDK stub. |

A stub performs a normal SDK call. It never returns a synthetic result and does not mean that the
server route, persistence, or workflow already exists.

## Invocation

```python
result = await client(method)
result = await client.make_request(method)
result = await method.emit(client)
```

Inside an active client context, an unbound method can also be awaited directly. Without an
explicit or current client, direct awaiting fails locally.

See `docs/api/types.md`, `docs/generator/generated-layout.md`, and `docs/index.md`.
