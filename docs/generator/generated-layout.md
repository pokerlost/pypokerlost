# Generated layout and ownership

One invocation produces one global flat method/type surface below an SDK package root.

## Layout

```text
pypokerlost/
├── methods/
│   ├── __init__.py
│   ├── get_me.py
│   └── get_balance.py
└── types/
    ├── __init__.py
    ├── account_response.py
    └── balance_response.py
```

Each generated operation owns one flat module and one class named directly from its operation ID.
Each generated public schema owns one focused flat module. No service directory or service prefix
is introduced.

Facades include both generated and hand-written public flat modules. A hand-written method can own
explicit scopes for a protected operation without becoming generator-owned.

## Global names

All input documents are checked together. Generation fails on collisions in:

- operation ID;
- generated method class;
- generated method module;
- public schema name;
- public schema module.

The source services must resolve real semantic collisions before generation.

## Manifest version three

The repository's canonical output uses:

```text
scripts/.generated_methods/flat.json
```

External output roots use a sibling `.pypokerlost-generated/flat.json`. The manifest records
generator version, source titles/versions/hashes, and the sorted generator-owned file list.

## Manual and stale files

Generated source begins with the exact generator header. A non-generated file at an expected type
target remains manual and is not overwritten. A non-generated method at an expected operation
target is parsed for direct operation, scope, and result metadata and remains hand-written when it
matches the OpenAPI contract.

The writer removes a stale source only when the previous manifest lists it and the file retains the
generator header. It does not infer ownership from a filename. Manual future-facing stubs therefore
remain intact.

`--check` compares every rendered file and the manifest without writing. Normal generation renders
and preflights the complete state before atomically replacing files.

See `docs/generator/usage.md`, `docs/generator/contract.md`, and `docs/index.md`.
