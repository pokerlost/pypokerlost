# Methods

Every method is a flat `PokerlostMethod[ResultT]` subclass with direct metadata:

```python
from typing import ClassVar

from pypokerlost.enums import PokerlostScopes
from pypokerlost.methods import PokerlostMethod
from pypokerlost.types import PokerlostOperation


class GetMe(PokerlostMethod[str]):
    operation = PokerlostOperation("getMe")
    __scopes__: ClassVar[tuple[PokerlostScopes, ...] | None] = (
        PokerlostScopes.ACCOUNTS_SELF_GET_ME,
    )
    returning = str
```

No access-token scopes are represented only by `None`. Protected methods use a non-empty,
duplicate-free tuple in canonical order. Empty or missing metadata fails locally before I/O.
Every member comes from the explicit SDK-owned `PokerlostScopes` catalog; OpenAPI generation
validates protected route metadata against that catalog.

Current auth contracts are `GetToken`, `RefreshToken`, `GetJwks`, `ProvisionHuman`,
`SetPrincipalStatus`, `ReplacePrincipalScopes`, and `IssueLoginGrant`. The current service foundations implement none of these business operations. They remain typed
network stubs and never return synthetic results. `ProvisionHuman` accepts explicit `initial_scopes`; `ReplacePrincipalScopes` replaces an
exact scope set. No authorization-role operation exists.
