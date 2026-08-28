# Methods

`PokerlostMethod[ResultT]` is the public base for strict typed API method objects.

## Import

The class is available from the package root and the focused method facade:

```python
from pypokerlost import PokerlostMethod

# Equivalent focused import:
from pypokerlost.methods import PokerlostMethod
```

The core repository intentionally contains no concrete service methods. Generated methods appear
under `pypokerlost.methods.<service_package>` in consuming SDK output.

## Defining a method

A concrete method declares request fields and three pieces of metadata. This example is
illustrative; these classes are not shipped by the core repository:

```python
from pypokerlost import PokerlostMethod, PokerlostType


class AccountResult(PokerlostType):
    account_id: int
    display_name: str


class GetAccountMethod(PokerlostMethod[AccountResult]):
    __api_method__ = "accounts.get"
    __returning__ = AccountResult

    account_id: int
```

`__http_method__` defaults to `"POST"`. A method may explicitly set it to one of `"GET"`,
`"POST"`, `"PUT"`, `"PATCH"`, or `"DELETE"` when its contract requires another method.

`__api_method__` is the full operation identity and must be a lowercase dotted `APIOperation`, such as
`accounts.get`. `__returning__` supplies the runtime type passed to Pydantic result validation; it
may be a `PokerlostType`, scalar, collection, or supported alias.

Method input models are strict and reject unknown fields. Request serialization uses field names,
excludes omitted fields, and preserves an explicitly supplied `None`.

## Invocation

Execute explicitly through a client when possible:

```text
method = GetAccountMethod(account_id=42)

result = await client(method)
result = await client.make_request(method)
```

Both client forms copy and bind the executing method, leaving `method` reusable.

Bind the exact instance when direct method awaiting is desirable:

```text
result = await method.as_(client)
```

Inside an active `Client` or `Application` context, an unbound method resolves the task-local
current client:

```python
async def execute_current(method):
    async with client:
        return await method
```

Without an explicit or current client, direct awaiting raises `ClientContextError`. Calling
`method.as_(None)` clears an explicit binding.

## Result client context

Before transport, the client binds an isolated method copy. `ResponseHandler` later validates
`__returning__` with that bound client in Pydantic context. Returned and nested `PokerlostType`
objects can therefore call `resolve_client()` and obtain the same client.

See [transport objects](transport.md) for request construction and response validation and
[generated layout](../generator/generated-layout.md) for generator-owned packages.

[Documentation index](../index.md)
