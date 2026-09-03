# Quickstart

An initial token is an explicit orchestration step:

```python
from uuid import UUID

from pypokerlost import PokerlostClient
from pypokerlost.client import PokerlostAPIServer
from pypokerlost.enums import PokerlostScopes
from pypokerlost.methods import GetToken


async with PokerlostClient(
    server=PokerlostAPIServer("https://auth.example.internal"),
) as auth_client:
    token = await auth_client(
        GetToken(
            client_id=UUID("2f64e790-0cf0-4de2-8fb2-5d8cf169ee42"),
            client_secret="loaded-by-the-consumer",
            scopes=(PokerlostScopes.ACCOUNTS_SELF_GET_ME,),
            audience="accountsService",
        )
    )
```

The consumer validates the result and persists encrypted `PokerlostStoredToken` state through its
shared store implementation. It then composes a protected target client:

```python
from pypokerlost import PokerlostClient
from pypokerlost.middleware import PokerlostAuthenticationMiddleware

authentication = PokerlostAuthenticationMiddleware(
    token_store=token_store,
    token_refresher=token_refresher,
    client_id="2f64e790-0cf0-4de2-8fb2-5d8cf169ee42",
    audience="accountsService",
)
business_client = PokerlostClient(
    server=accounts_server,
    middleware=(authentication,),
)
```

The SDK never receives the client secret in middleware and never calls `GetToken` automatically.
Public methods bypass token state. Protected methods load exact UTC/versioned state and send the
token only in the bearer header.

Retry remains disabled unless the call supplies `PokerlostRequestOptions` with
`PokerlostRetryPolicy()`.
