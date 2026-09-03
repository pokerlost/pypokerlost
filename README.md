# pypokerlost

Typed asynchronous SDK for Pokerlost's JSON protocol with standard bearer-header authentication,
one response envelope, an explicit shared scope catalog, and bounded opt-in retry.

## Requirements

- Python 3.14 or newer
- [`uv`](https://docs.astral.sh/uv/)

## Installation

```bash
uv sync --locked --all-groups
```

## Public call

```python
from uuid import UUID

from pypokerlost import PokerlostClient
from pypokerlost.client import PokerlostAPIServer
from pypokerlost.enums import PokerlostScopes
from pypokerlost.methods import GetToken


async def get_service_token() -> None:
    async with PokerlostClient(
        server=PokerlostAPIServer("https://auth.example.internal"),
    ) as client:
        token = await client(
            GetToken(
                client_id=UUID("2f64e790-0cf0-4de2-8fb2-5d8cf169ee42"),
                client_secret="loaded-by-the-consumer",
                scopes=(PokerlostScopes.ACCOUNTS_SELF_GET_ME,),
                audience="accountsService",
            )
        )
        print(token.expires_in)
```

`GetToken.__scopes__` is `None`: credentials remain in its typed request payload, but it neither
loads token state nor sends `Authorization`. Protected methods declare a non-empty exact scope
tuple whose members belong to the SDK-owned `PokerlostScopes` catalog.
`PokerlostAuthenticationMiddleware` loads an already persisted token and the transport adds the
bearer header without changing the JSON body.

See `docs/index.md`. Run `make check` for the regular gate and `make check-full` before release.
