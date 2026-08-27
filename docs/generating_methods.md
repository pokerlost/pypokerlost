# Generating typed methods

`scripts/generate_methods.py` generates deterministic method modules from a supported Pokerlost
OpenAPI 3.1 JSON contract. It is development tooling, not part of the installed runtime API.

For hand-written methods or contracts outside the supported subset, use the mechanical guidance in
[Adding typed methods](adding_methods.md).

## Prerequisites

Use Python 3.13 or newer and the locked project development environment:

```bash
uv lock --check
uv sync --locked --all-groups
```

The existing development group provides Typer for the CLI and aiofiles for asynchronous local file
I/O. `httpx` and Pydantic remain runtime dependencies already used by the SDK. The generator adds no
runtime dependency and accepts JSON only; YAML input is not supported.

## Generate from a file

Pass a raw OpenAPI JSON document to the `file` command:

```bash
uv run python scripts/generate_methods.py file path/to/openapi.json \
  --output pypokerlost/methods
```

The default output root is `pypokerlost/methods`. The service identifier from
`x-pokerlost-service.id` determines the generated subpackage below that root.

## Generate from a service

The `service` command fetches `GET /openapi.get` from the supplied base URL with a direct,
development-time `httpx.AsyncClient`:

```bash
uv run python scripts/generate_methods.py service http://localhost:8080 \
  --output pypokerlost/methods \
  --timeout 10
```

The endpoint must return the OpenAPI document in the fixed application envelope, for example:

```json
{
  "ok": true,
  "result": {
    "openapi": "3.1.0",
    "info": {"title": "Accounts API", "version": "1.0.0"},
    "paths": {
      "/accounts.ping": {
        "post": {
          "operationId": "accounts.ping",
          "responses": {
            "200": {
              "description": "Success",
              "content": {
                "application/json": {
                  "schema": {
                    "type": "object",
                    "additionalProperties": false,
                    "required": ["ok", "result", "error", "error_message"],
                    "properties": {
                      "ok": {"type": "boolean"},
                      "result": {"type": "string"},
                      "error": {"type": ["string", "null"]},
                      "error_message": {"type": ["string", "null"]}
                    }
                  }
                }
              }
            }
          }
        }
      }
    },
    "x-pokerlost-service": {"id": "accounts"}
  },
  "error": null,
  "error_message": null
}
```

Service mode validates that response through the public
`ApplicationResponse[OpenAPIDocument]` contract. It does not instantiate `Client`, a session,
middleware, storage, an application lifecycle, or a response handler.

File and service commands differ only in contract acquisition. Both continue through the same
validated `OpenAPIDocument`, local reference resolver, operation/schema representation, renderer,
manifest and version policy, and safe writer. Equal contracts therefore produce byte-identical
generated output.

## Check and overwrite policy

Use `--check` to compare deterministic output and manifest state without writing:

```bash
uv run python scripts/generate_methods.py file path/to/openapi.json \
  --output pypokerlost/methods \
  --check
```

The check fails when an expected file is missing or changed, a previously owned file is stale, or
the manifest differs. Generated source contains no timestamp; operations, files, imports, and
exports have stable ordering. Every generated Python module contains exactly one
`from __future__ import annotations` in the valid position before ordinary imports.

Each canonical output root and service pair owns one manifest under
`scripts/.generated_methods/<output-sha256>/`. Repository-local outputs use a tagged, normalized
repository-relative identity, so the manifest path remains stable across checkout locations.
External outputs use a tagged canonical absolute identity. The directory name is a SHA-256 identity
and does not expose either path in manifest metadata. Two different `--output` roots therefore have
independent version history and owned-file state, even for the same service. Each manifest records
the generator version, OpenAPI version, canonical source SHA-256, service identifier, output
package, and owned files. Manifest-owned paths must be normalized relative Python paths inside that
service's output subpackage. Normal generation overwrites only files carrying the generator header
and removes stale files only when the previous manifest owns them. An unrelated manual file is
neither overwritten nor removed.

An older unscoped `scripts/.generated_methods/<service>.json` manifest cannot be safely attributed
to a particular output root. When no scoped manifest exists, generation reports that legacy state
instead of silently bypassing its version history. After reviewing the intended output, use
`--force` once to migrate its ownership and version history to the chosen output-scoped state. The
legacy manifest is removed only after the generated files and new scoped manifest are written
successfully.

`--force` deliberately permits overwriting a conflicting target and bypassing contract-version
guards:

```bash
uv run python scripts/generate_methods.py file path/to/openapi.json \
  --output pypokerlost/methods \
  --force
```

Use it only after reviewing the target and contract history.

## Version policy

OpenAPI `info.version` must use Semantic Versioning (`MAJOR.MINOR.PATCH`). When canonical contract
content changes, its version precedence must increase. A downgrade or content change at the same
version fails unless `--force` is explicitly supplied.

The generator has one SemVer version covering generated source layout and the CLI:

- `MAJOR` denotes an incompatible generated layout, generated public API, manifest format, or CLI
  change.
- `MINOR` denotes backward-compatible support for an additional OpenAPI capability or an optional
  CLI feature.
- `PATCH` denotes a generator bug fix or internal refactor that preserves the generated public and
  CLI contracts.

Print the current generator version with:

```bash
uv run python scripts/generate_methods.py --version
```

## Supported contract subset

The generator consumes OpenAPI 3.1.x JSON with one `x-pokerlost-service.id`. A generated operation
must have a lowercase `namespace.method` `operationId`, a matching `/namespace.method` path, and a
supported HTTP method (`GET`, `POST`, `PUT`, `PATCH`, or `DELETE`). Deprecated and system paths are
not generated.

The supported schema subset includes:

- chained local component references for schemas, request bodies, and responses;
- typed JSON object request bodies, named nested object models, arrays, and typed or JSON-value
  dictionaries;
- strings, integers, numbers, booleans, and `null`;
- UUID, date, date-time, and time string formats;
- scalar, `Literal`-compatible enums and constants; nullable unions; `anyOf`; `oneOf`; and
  object-only `allOf` composition;
- required fields, defaults, and supported numeric, string, and array constraints;
- compatible JSON 2xx responses using the fixed `ApplicationResponse` envelope.

Typed object schemas declare `additionalProperties: false`, matching the generated models' strict
unknown-field policy. A request body must declare typed properties; a free-form request object is
rejected. The success envelope has exactly the public `ApplicationResponse` fields, requires its
publicly required fields, and forbids additional properties.

Document and operation metadata are parsed before operation selection. JSON Schemas are validated
against the strict supported subset only when a selected operation reaches them through its request
body, JSON 2xx success response, or local component references. Unused component schemas and
non-success response schemas therefore do not constrain generation; an unsupported schema still
fails with its component or operation location as soon as generated code depends on it.

This reachability rule does not make inaccurate service OpenAPI acceptable. A service that maps
FastAPI request validation failures to `ApplicationResponse[None]` must explicitly publish that
same reusable envelope as its `422` response metadata instead of advertising FastAPI's default
validation-error body.

Length and item-count bounds are non-negative, and regular-expression patterns must be accepted by
Pydantic's regex engine. Supported constraints remain active on direct fields, nested array items,
typed dictionary values, scalar results, and referenced scalar aliases. Constraints applied to the
wrong schema kind fail before files are written. UUID, date, date-time, and time formats remain
supported, but combining those converted value types with `minLength`, `maxLength`, or `pattern` is
rejected instead of applying a string constraint after conversion. Cyclic pure aliases and cyclic
`allOf` composition fail with a generation error; recursive object models remain supported.

External references, OpenAPI parameters, free-form request bodies, inline nested object schemas,
incompatible success schemas, semantic schema keywords outside the supported subset, unsupported
HTTP operations or media types, invalid RPC operation identifiers, and generated naming collisions
fail with a focused generation error. Standard descriptive metadata and `x-*` extensions do not
alter generated methods. Other unsupported constructs also fail explicitly; the generator does
not guess a representation.

## Runtime boundary

The generator reuses stable public SDK vocabulary through focused facades:

- `ApplicationResponse` from `pypokerlost.contracts` validates service publication;
- `JSONValue`, `HTTPMethod`, and `RPCOperation` from `pypokerlost.types` define shared value
  contracts;
- generated methods import `PokerlostMethod` from `pypokerlost.methods`.

OpenAPI document models, local reference resolution, schema and source rendering, naming,
generated-file and manifest models, source hashing, safe writing, CLI settings, and generator
version policy intentionally remain in `scripts/generate_methods.py`. Generated modules never
import `scripts`, Typer, aiofiles, generator models, or private SDK modules.
