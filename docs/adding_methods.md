# Adding typed methods

Concrete methods extend `PokerlostMethod` directly. Namespace directories may organize files but do
not introduce service-specific bases.

This guide covers manual method authoring. To generate methods deterministically from a supported
OpenAPI 3.1 JSON contract, see [Generating typed methods](generating_methods.md).

## Define the result and method

```python
from uuid import UUID

from pydantic import BaseModel

from pypokerlost.methods import PokerlostMethod


class GetAccountResult(BaseModel):
    account_id: UUID
    username: str


class GetAccountMethod(PokerlostMethod[GetAccountResult]):
    __api_method__ = "accounts.get"
    __returning__ = GetAccountResult

    account_id: UUID
```

Use the authoritative RPC contract to:

1. define the result model;
2. set `__api_method__` to a non-empty `namespace.method` operation;
3. set `__returning__` explicitly;
4. declare alias-free `snake_case` request fields;
5. override `__http_method__` only when the contract differs from `POST`.

Unknown fields are rejected. Unset fields are omitted from JSON; an explicitly supplied `None`
remains JSON `null`. Nested Pydantic models, enums, UUIDs, dates, tuples, and custom field
serializers are handled by Pydantic JSON mode.

A method remains a pure request description and never accesses storage implicitly; application
code may use `client.storage` explicitly outside the RPC pipeline.

## Execute the method

```python
async with Application(Client()) as client:
    implicit_result = await GetAccountMethod(account_id=account_id)
    explicit_result = await client(
        GetAccountMethod(account_id=account_id),
    )
```

Outside a managed scope, use `await client(method)`, `await client.make_request(method)`, or
`await method.as_(client)`.

## OpenAPI security

OAuth2 scopes belong to the consuming service's OpenAPI configuration, not method transport
execution. When useful, describe them with service-defined strings:

```python
from pypokerlost.openapi import RPCOpenAPIExtra

extra = RPCOpenAPIExtra(
    security_scheme="OAuth2PasswordBearer",
    scopes=("accounts:read",),
).as_dict()
```

The service remains responsible for declaring its security scheme, OAuth2 flow, and token URL.

## Checklist

- The result and request fields match the authoritative contract.
- The operation follows `namespace.method`; `__returning__` is explicit.
- Optional fields distinguish omission from explicit `None` correctly.
- The method extends `PokerlostMethod` directly and contains no execution policy.
- Focused package exports and documentation are updated without compatibility aliases.
- Formatting, linting, mypy, build, compile, and a focused smoke check pass.
