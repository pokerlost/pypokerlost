# Generated layout and ownership

The explicit scope catalog lives beside one global flat generated method/type surface:

```text
src/pypokerlost/
├── enums/
│   └── pokerlost_scopes.py  # explicit SDK-owned catalog
├── methods/
│   ├── get_me.py
│   └── get_balance.py
└── types/
    ├── account_response.py
    └── balance_response.py
```

The generator writes only method/type modules and the corresponding flat facades. It never creates
service directories or prefixes to hide collisions, and it never rewrites the SDK-owned scope
catalog. The version-four manifest records input hashes and only files actually generated from
implemented operations. Stale files are removed only when both the manifest and generated header
prove ownership.

Manual future-facing stubs remain outside ownership. When an endpoint later appears, its direct
metadata and payload/result contract must exactly match OpenAPI or generation fails.
