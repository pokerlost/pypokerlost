# Generator architecture

The development-time generator turns one validated PokerLost OpenAPI contract into deterministic
method and type packages without participating in SDK runtime execution.

## Pipeline

Both contract sources converge immediately on the same pipeline:

```text
raw OpenAPI JSON file ─────────┐
                              ├─> OpenAPIDocument
service /<openapi-operation> ──┘          │
                                         ▼
                     canonical source hash
                                │
                                ▼
                    reachable-schema resolver
                                │
                                ▼
                       operation model
                                │
                                ▼
                    deterministic renderer
                         │             │
                         ▼             ▼
                 methods/<service>/ types/<service>/
                         └──────┬──────┘
                                ▼
                    manifest and safe writer
```

File mode parses a raw JSON document. Service mode validates `--openapi-operation` as an
`APIOperation`, defaults it to `openapi.get`, and fetches `/<openapi-operation>` with a directly
scoped `httpx.AsyncClient`. It then validates the returned `Response[OpenAPIDocument]`. File mode
accepts the same optional value only as the exact system-route selector, allowing a captured custom
publication contract to generate identically without performing a fetch. Acquisition is the only
difference between the modes; contract resolution, rendering, ownership, and writing are shared.

## Validation phases

The document model validates OpenAPI versioning, service identity, paths, supported operations, and
the structural fields used by generation. Component schemas, request bodies, and responses remain
JSON values until a selected operation makes them reachable.

This delayed boundary prevents unused framework-owned components and non-success responses from
blocking generation. Once reachable, a node is validated against the supported subset and failures
identify its component or operation location. The complete supported subset is defined in
`docs/generator/contract.md`.

## Reference resolution

The resolver accepts local component references for schemas, request bodies, and responses. It
follows reference chains, rejects missing or external targets, and detects pure reference cycles.
Object composition is normalized before rendering; recursive named object relationships remain
available to generated Pydantic models.

## Operation model and rendering

Each selected API operation is reduced to a transport method, API operation name, request object
schema, result schema, generated class name, and module name. Operations and all rendered imports,
exports, fields, constraints, and files use stable ordering.

The renderer emits:

- one strict `PokerlostMethod` subclass per API operation;
- referenced API object classes based on `PokerlostType`;
- PEP 695 aliases for generated non-model types;
- focused `__init__.py` facades for each service method and type package.

Generated source includes no timestamps. Its header records the generator version, service ID,
OpenAPI contract version, and canonical contract SHA-256, so equal validated inputs produce equal
files.

## Ownership and updates

One generation targets an SDK package root containing both `methods/` and `types/`. A version-two
manifest scopes ownership to the canonical output root and service package. Before writing, the
pipeline applies contract-version policy, checks conflicting targets, and identifies stale files
from previous manifest ownership.

Writes use temporary files followed by atomic replacement. Stale source is removed only when the
previous manifest proves ownership and the file still carries the generator header. Details of the
layout, manual-file protection, and migration policy are in
`docs/generator/generated-layout.md`.

## Runtime boundary

The generator lives under `scripts/` and is development tooling. It reuses focused public SDK
contracts such as `Response`, `HTTPMethod`, `APIOperation`, `PokerlostMethod`, and `PokerlostType`,
but it does not instantiate `Client`, `Application`, sessions, middleware, storage, request
builders, or response handlers.

Generated modules depend only on the runtime package and declared runtime dependencies. They never
import generator models, Typer, aiofiles, or private SDK implementation names.

See `docs/index.md`.
