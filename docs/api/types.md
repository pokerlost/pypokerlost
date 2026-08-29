# Types

The public type facade provides the bases and semantic aliases used by handwritten and generated
PokerLost contracts.

## Typed API object bases

Import the object bases from either the package root or the focused types facade:

```python
from pypokerlost import MutablePokerlostType, PokerlostType

# Equivalent focused import:
from pypokerlost.types import MutablePokerlostType, PokerlostType
```

`PokerlostType` is a frozen Pydantic model for returned and nested API objects. It allows additional
response fields for forward compatibility, validates defaults, rejects non-finite numbers, and
keeps an optional client in a private, non-serialized binding.

```python
from pypokerlost import PokerlostType


class Account(PokerlostType):
    account_id: int
    display_name: str
```

`MutablePokerlostType` deliberately permits field assignment while preserving the remaining base
configuration and client-binding behavior.

## Client binding

Both bases expose:

- `as_(client)`, which sets the private binding and returns the same object;
- `client`, which returns the explicit or validation-context binding, if present;
- `resolve_client()`, which falls back to the task-local current client and otherwise raises
  `ClientContextError`.

Passing `None` to `as_()` clears the explicit binding. Private binding state never appears in
`model_dump()` output.

## Semantic aliases

The focused facade exports these aliases:

```python
from pypokerlost.types import (
    APIBase,
    HTTPMethod,
    JSONDumps,
    JSONLoads,
    JSONScalar,
    JSONValue,
    APIOperation,
    StorageKey,
    StorageTTL,
)
```

| Alias | Contract |
|---|---|
| `APIBase` | Strict HTTP(S) URL string without user information, a query, or a fragment; normalized without a trailing slash. |
| `HTTPMethod` | `"GET"`, `"POST"`, `"PUT"`, `"PATCH"`, or `"DELETE"`. |
| `APIOperation` | Exactly `namespace.someOperation`: two ASCII alphanumeric segments with lowercase initials and exactly one dot. |
| `JSONDumps` | Callable JSON encoder returning `str`. |
| `JSONLoads` | Callable dynamic JSON decoder. |
| `JSONScalar` | Boolean, integer, finite float, string, or `None`. |
| `JSONValue` | Exact built-in JSON scalars, lists, and string-keyed dictionaries. |
| `StorageKey` | Strict non-empty string containing at least one non-whitespace character. |
| `StorageTTL` | Strict `int`, `float`, `timedelta`, or `None`; accepted values normalize to positive finite seconds. |

`HTTPMethod` is a literal type, not an enum. The current runtime public type surface defines no
project-owned enum classes.

## JSON boundaries

`JSONValue` rejects container subclasses, non-string dictionary keys, non-finite floats, and other
Python objects. This keeps request normalization and storage behavior within the JSON-compatible
contract.

`StorageTTL` rejects booleans even though `bool` is an `int` subclass in Python. Zero, negative,
infinite, and NaN lifetimes are invalid. See `docs/api/storage.md` for boundary exception behavior.

See `docs/architecture/types-and-methods.md` for generated placement and validation context
propagation.

See `docs/index.md`.
