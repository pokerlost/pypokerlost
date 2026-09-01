# Types and methods

Methods describe operation calls; types describe reusable values and wire objects. Both namespaces
are flat.

## Method contract

```python
from pypokerlost import PokerlostMethod
from pypokerlost.types import PokerlostOperation, PokerlostScope


class GetBalance(PokerlostMethod[int]):
    operation = PokerlostOperation("getBalance")
    required_scopes = (PokerlostScope("accounts.self.read"),)
    returning = int

    account_id: str
```

The class name has no redundant suffix. The operation is independent of the required scope. Empty
`required_scopes` means public at the transport layer; a non-empty tuple means body authorization
is mandatory.

## Flat layout

```text
pypokerlost/
├── methods/
│   ├── get_token.py
│   ├── refresh_token.py
│   └── get_balance.py
└── types/
    ├── pokerlost_response.py
    ├── pokerlost_token.py
    └── account_response.py
```

Service directories and shared-contract forwarding packages are not part of the layout. Focused
facades expose public names from `pypokerlost.methods` and `pypokerlost.types`.

## Typed values

`PokerlostType` is the immutable API-object base with optional private client binding.
`MutablePokerlostType` is its explicit mutable variant. Canonical request, response, token, scope,
authorization, credentials, context, and claims models are focused flat types rather than
`PokerlostType` compatibility objects.

Secret-bearing wire fields remain serializable but are hidden from repr and validation input
output. Models are strict, frozen where appropriate, validate defaults, and reject unknown fields.

## Binding

`await client(method)` executes a copied method bound to that client. `await method.emit(client)` is
the explicit method form. Direct `await method` resolves an explicitly bound client first, then the
task-local current client, and otherwise raises a configuration error.

Result validation passes the executing client through Pydantic context so nested `PokerlostType`
objects can resolve the same client without serializing it.

See `docs/api/methods.md`, `docs/api/types.md`, and `docs/index.md`.
