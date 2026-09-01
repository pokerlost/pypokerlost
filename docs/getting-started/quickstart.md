# Quickstart

Create a target-specific `PokerlostClient` and execute one typed body-only method.

## Public token call

```python
from __future__ import annotations

import asyncio

from pypokerlost import PokerlostClient
from pypokerlost.client import PokerlostAPIServer
from pypokerlost.methods import GetToken
from pypokerlost.session import HttpxSession


async def main() -> None:
    auth_session = HttpxSession(
        api_server=PokerlostAPIServer("https://auth.example.internal"),
    )
    async with PokerlostClient(session=auth_session) as auth_client:
        token = await auth_client(
            GetToken(
                client_id="service-client-id",
                client_secret="loaded-by-the-consumer",
                scopes=("accounts.self.read",),
                audience="accountsService",
            )
        )
        print(token.expires_in)


asyncio.run(main())
```

The call sends `POST /getToken` with a `PokerlostRequest` JSON body. Credentials are fields inside
`payload`; the project creates no authentication header or form body.

## Protected client composition

The consumer provides a `PokerlostTokenStore` implementation and loads its credentials outside the
SDK:

```python
from pypokerlost import PokerlostClient
from pypokerlost.middleware import PokerlostAuthorizationMiddleware
from pypokerlost.types import PokerlostClientCredentials

authorization = PokerlostAuthorizationMiddleware(
    auth_client=auth_client,
    token_store=token_store,
    credentials=PokerlostClientCredentials(
        client_id=client_id,
        client_secret=client_secret,
    ),
    audience="accountsService",
)
business_client = PokerlostClient(
    session=business_session,
    middleware=(authorization,),
)
```

The middleware reads exact scopes from each method. Public calls bypass it. Protected calls acquire
or reuse a token and send it only in `authorization.access_token` inside the JSON body.

Retry remains disabled until one call passes a `PokerlostRequestOptions` containing
`PokerlostRetryPolicy()`.

See `docs/api/body-authorization.md`, `docs/api/retry.md`, and `docs/index.md`.
