# Types and methods

This page explains the distinct roles of typed API objects, mutable API objects, API methods, and
their generated package layout.

## PokerlostType

`PokerlostType` is the immutable Pydantic base for structured PokerLost API objects. Its model
configuration allows unknown response fields for forward compatibility, uses enum values, validates
defaults, supports field-name population, rejects non-finite numbers, and keeps public fields
frozen.

The model owns one private optional client binding. That binding is excluded from model fields,
serialization, and the wire contract. It can be supplied explicitly with `.as_(client)` or through
Pydantic validation context.

`MutablePokerlostType` is the deliberate mutable subtype. It changes only the frozen setting; it
retains the same API-object validation and client-binding behavior.

## PokerlostMethod

`PokerlostMethod[ResultT]` is the single API method base. It inherits client resolution from
`PokerlostType` but overrides request-facing configuration to be strict and extra-forbid. Concrete
methods declare only:

- request fields;
- `__api_method__`, the exact two-segment `namespace.someOperation` API operation;
- `__http_method__`, which defaults to `"POST"`;
- `__returning__`, the declared result type.

The operation is the full operation identity. Methods carry no service-routing metadata and do not
create endpoint-specific `Client` methods.

The tracked authService package contains `OAuthTokenMethod`. The following remains an illustration
of the shape generated for another structured result:

```python
from pypokerlost import PokerlostMethod, PokerlostType


class AccountResult(PokerlostType):
    account_id: int


class GetAccountMethod(PokerlostMethod[AccountResult]):
    __api_method__ = "support.getAccount"
    __returning__ = AccountResult

    account_id: int
```

See `docs/api/methods.md` for invocation forms.

## Generated placement

One service generation keeps request contracts separate from returned and nested data objects:

```text
pypokerlost/
├── methods/
│   └── <service_package>/
│       └── ... request method modules
└── types/
    └── <service_package>/
        └── ... API object and alias modules
```

Generated method modules import `PokerlostMethod` from `pypokerlost.methods`. Generated API object
modules import `PokerlostType` from `pypokerlost.types`. A declared result may be a structured API
object, a scalar, a collection, or a generated alias supported by Pydantic validation.

## Binding and execution

There are two distinct binding paths:

- `.as_(client)` mutates only the private binding on that exact object and returns it;
- `client(method)` and `client.make_request(method)` execute a copied method bound to that client.

Therefore an unbound method remains reusable after explicit client execution. Awaiting a method
directly calls `resolve_client()`, which prefers its explicit or validation-context binding and then
the task-local current client. Without either, it raises `ClientContextError`.

`ResponseHandler` validates `__returning__` with the executing method's client in Pydantic context.
Pydantic propagates that context through nested typed models, allowing returned `PokerlostType`
objects to resolve the same client without serializing it.

See `docs/api/types.md` for public semantic aliases and `docs/architecture/client-lifecycle.md` for
task-local context ownership.

See `docs/index.md`.
