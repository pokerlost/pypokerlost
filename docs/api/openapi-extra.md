# OpenAPI extra metadata

`OpenAPIExtra` builds the small PokerLost-specific, non-security extension used in PokerLost
OpenAPI contracts.

## Import and field

Import it from the package root:

```python
from pypokerlost import OpenAPIExtra
```

The model has one public field:

```python
extra = OpenAPIExtra(contract_version=1)
```

`contract_version` is a strict integer greater than or equal to `1` and defaults to `1`. The model
is frozen, strict, and rejects extra fields.

## Exact output

`as_dict()` returns a fresh mapping on every call:

```python
metadata = OpenAPIExtra().as_dict()
```

The exact default value is:

```json
{
  "x-pokerlost": {
    "contract_version": 1
  }
}
```

The class emits no security requirement, authorization scheme, scopes, credentials, or token
metadata. Those policies belong to consuming services and are not interpreted by the SDK.

For generator contract metadata, see the [supported contract](../generator/contract.md). For the
runtime boundary, see the [architecture overview](../architecture/overview.md).

[Documentation index](../index.md)
