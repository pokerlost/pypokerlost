# Adding Pokerlost methods

This is the authoritative mechanical guide for adding concrete accountsService and authService
operations after their service contracts are available. The current package contains only the
generic method foundation and the two abstract service-specific bases; the examples below are
documentation-only and are not shipped endpoints.

Read [`../AGENTS.md`](../AGENTS.md), [`../SERVICE.md`](../SERVICE.md), and
[`ARCHITECTURE.md`](ARCHITECTURE.md) before implementing a method. An authoritative service
contract must determine every operation name, request field, result field, and HTTP-method
override. Do not infer product behavior from an example in this guide.

## File placement and naming

Keep a future operation and its declared result type in the matching service package. Use explicit
artifact suffixes and snake_case filenames:

```text
pypokerlost/methods/accounts/
├── get_account_method.py
└── get_account_response.py

pypokerlost/methods/auth/
├── login_method.py
└── login_response.py
```

Do not create endpoint wrappers on `Client`, dynamically generated attributes, registry entries,
or a generated-method package. One concrete operation is one ordinary typed method class.

## Select the service base

The service bases supply only `__service__`:

```python
class AccountsMethod[ResultT](PokerlostMethod[ResultT]):
    __service__ = ServiceName.ACCOUNTS


class AuthMethod[ResultT](PokerlostMethod[ResultT]):
    __service__ = ServiceName.AUTH
```

Use `AccountsMethod` for an accountsService contract and `AuthMethod` for an authService contract.
Do not repeat or override `__service__` in a concrete method, infer it from the operation prefix, or
make service identity choose a host or authentication behavior.

## Define the result type

Add the result model from the authoritative service schema before defining the method. Keep its
fields and validation rules explicit. Reuse the existing SDK model boundaries where appropriate;
do not introduce another response envelope or change `ResponseModel` and `ApplicationResponse` as
part of an ordinary method addition.

`ApplicationResponse` remains the one wire envelope for every handled JSON operation:

```python
ok: bool
result: ResultT | None = None
error: str | None = None
error_message: str | None = None
```

The envelope may accept `result=None` for a successful response. The concrete method's
`__returning__` annotation decides whether that value is valid at the typed result boundary.

## Define the method

An accountsService method follows this shape:

```python
from uuid import UUID

from pypokerlost.methods.accounts import AccountsMethod

from .get_account_response import AccountResponse


class GetAccountMethod(AccountsMethod[AccountResponse]):
    __api_method__ = "accounts.get"
    __returning__ = AccountResponse

    account_id: UUID
```

An authService method follows the corresponding auth base:

```python
from pypokerlost.methods.auth import AuthMethod

from .login_response import LoginResponse


class LoginMethod(AuthMethod[LoginResponse]):
    __api_method__ = "auth.login"
    __returning__ = LoginResponse

    email: str
    password: str
```

For each concrete method:

1. Inherit exactly one matching service base.
2. Set `__api_method__` to the authoritative non-empty `namespace.method` operation identifier.
3. Set `__returning__` directly to the declared runtime result type.
4. Declare request fields as normal strict Pydantic fields with precise annotations.
5. Keep the inherited `__http_method__ = "POST"` unless the service contract explicitly requires
   another non-empty HTTP method.
6. Keep request construction, response decoding, I/O, authentication, routing, and retry behavior
   out of the method class.

Do not inspect generic bases, MRO state, or Pydantic internals to discover result metadata. Do not
add a metaclass, `Client.__getattr__`, another current-client mechanism, or a third client-resolution
path. Task-local current-client storage is the existing focused lifecycle mechanism in
`client/current_client.py`, not method-specific behavior.

## Request serialization contract

`RpcRequestBuilder` serializes the method's public Pydantic fields with
`model_dump(mode="json", by_alias=False, exclude_unset=True)`. Therefore:

- an omitted optional field is absent from the request body;
- an explicitly supplied `None` remains JSON `null`;
- aliases are not used on the wire;
- the private bound client never enters the body;
- unsupported values raise `TypeError` rather than being stringified.

Preserve this distinction when translating a service schema into Python defaults. Do not add
per-method serialization or manually constructed request dictionaries.

## Focused exports

Export the new public operation and result from its service package facade, for example
`pypokerlost.methods.accounts`. Keep that `__init__.py` explicit. The generic
`pypokerlost.methods` facade exports `PokerlostMethod`, `AccountsMethod`, and `AuthMethod`; do not
turn it into an export dump of every concrete endpoint. Add a package-root export only when a later
direct requirement deliberately expands the root API.

The service bases themselves remain available from both focused paths:

```python
from pypokerlost.methods import AccountsMethod, AuthMethod
from pypokerlost.methods.accounts import AccountsMethod
from pypokerlost.methods.auth import AuthMethod
```

## Invocation and lifecycle

A concrete method can be awaited directly while an application or client scope supplies the
task-local current client:

```python
async def main(client: Client) -> None:
    account = await GetAccountMethod(account_id=account_id)


application.run(main)
result = await application.run_async(main)

async with application:
    account = await GetAccountMethod(account_id=account_id)

async with client:
    account = await GetAccountMethod(account_id=account_id)
```

It also supports the established explicit forms anywhere:

```python
result = await client(method)
result = await client.make_request(method)
result = await method.as_(client)
```

Explicit binding overrides the ambient current client. Calling `method.as_(None)` clears that
binding and restores ambient fallback; without either source, implicit awaiting raises
`ClientContextError`. Nested scopes restore their previous client, concurrent tasks retain
independent context, and child tasks inherit the client current when they are created. A background
task must not outlive the application/client scope whose session it uses.

Do not add a parallel endpoint method such as `client.login()`. The application's only user
lifecycle extension is one async context-manager callable:

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifecycle(application: Application) -> AsyncIterator[None]:
    await WarmupMethod()
    try:
        yield
    finally:
        await FlushMethod()
```

The managed client is current during lifecycle setup, the entrypoint, and lifecycle teardown.
`Application.run()` temporarily integrates supported `SIGINT`/`SIGTERM` handlers, cancels and
awaits the application task through cleanup, and returns `None` for a handled signal.
`Application.run_async()` never installs signal handlers. Unsupported platforms or threads proceed
normally without signal integration, and user tasks must cooperate with normal asyncio
cancellation.

## OpenAPI metadata

When the authoritative operation contract also requires service-side OpenAPI metadata, describe it
with `RpcOpenApiExtra` and ordered `AccessRole` values. This metadata is separate from runtime
method execution: it does not authorize callers, select a host, fetch or parse OpenAPI, or generate
method classes.

## Completion checklist for a future method task

- The request and result types match an authoritative accountsService or authService contract.
- The class inherits the matching service base and does not redeclare `__service__`.
- `__api_method__`, `__returning__`, request fields, and any HTTP override are explicit.
- Omitted fields and explicit `None` retain their distinct wire behavior.
- Focused service-package exports and documentation are updated without compatibility aliases.
- No endpoint-specific `Client` wrapper, authentication placeholder, retry, streaming, routing,
  generator, registry, or additional ambient-client mechanism is introduced.
- Formatting, linting, strict typing, build, import, and task-specific smoke checks pass.
