# Generator architecture

The development-time generator validates one or more Pokerlost OpenAPI documents as a single
global input and produces flat SDK sources.

## Pipeline

```text
OpenAPI JSON documents
→ parse every document
→ preflight global public names
→ validate business operations and envelopes
→ collect reachable public schemas
→ resolve exact method scopes
→ render all files in memory
→ compare or write manifest-owned files
```

No output file changes before global operation and schema preflight succeeds.

## Validation

Generated business operations must use POST, path `/<operationId>`, a required JSON body, one of
the two canonical request envelopes, and a JSON `PokerlostResponse` for every numeric 2xx response.
OpenAPI parameters and non-empty operation security declarations are rejected. Public
infrastructure GET routes are skipped.

Operation, method class/module, public schema name, and schema-module collisions are checked across
all documents. The generator does not add a service prefix to resolve collisions.

## Scope source

The request schema tells the generator whether an operation is public or protected. It does not
tell the generator the exact scope tuple. Protected scopes must come from either:

- an existing hand-written flat method with literal `operation` and `required_scopes`; or
- an explicit checked JSON scope map supplied with `--scope-map`.

Descriptions and operation names are never parsed to guess scopes.

## Rendering and ownership

Every generated operation gets one `methods/<module>.py`; every generated public type gets one
`types/<module>.py`. Facades are regenerated from generated and hand-written flat modules. The
version-three manifest records all source contracts and the exact generator-owned file list.

Stale files are removed only when prior manifest ownership and the generator header both prove
ownership. Manual stubs are not overwritten or removed.

## Runtime boundary

The generator is tooling under `scripts/`. Generated code imports stable runtime facades only. It
does not instantiate clients, middleware, sessions, token stores, or service verifiers.

See `docs/generator/contract.md`, `docs/generator/generated-layout.md`, and `docs/index.md`.
