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
exports have stable ordering.

Each service owns one manifest under `scripts/.generated_methods/`. It records the generator
version, OpenAPI version, canonical source SHA-256, service identifier, output package, and owned
files. Manifest-owned paths must be normalized relative Python paths inside that service's output
subpackage. Normal generation overwrites only files carrying the generator header and removes
stale files only when the previous manifest owns them. An unrelated manual file is neither
overwritten nor removed.

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

- local component references for schemas, request bodies, and responses;
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

Length and item-count bounds are non-negative, and regular-expression patterns must be accepted by
Pydantic's regex engine. Constraints applied to the wrong schema kind fail before files are written.

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
