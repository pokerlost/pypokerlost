# Supported generator contract

`scripts/generate_methods.py` accepts the OpenAPI subset used by the private Pokerlost JSON
protocol.

## Documents

Each source must be OpenAPI `3.1.x` JSON with:

- non-empty `info.title`;
- SemVer `info.version`;
- a `paths` object;
- optional `components.schemas`.

YAML and vendor extensions are rejected. Service identity metadata is neither required nor
accepted. Component security schemes and non-empty document or operation security declarations are
rejected because authorization is represented by the request body.

## Operations

Business operation IDs match:

```text
^[a-z][A-Za-z0-9]*$
```

They use POST, and their path is exactly `/<operationId>`. Path-level and operation-level OpenAPI
parameters are rejected.

Public infrastructure GET routes are skipped when their path is `/` or their operation is one of
the recognized root, OpenAPI, liveness, readiness, or health names. Other non-POST routes are
rejected.

The complete input set must have globally unique operation IDs, generated class names, and method
module names. Validation fails before writing; the generator never adds service prefixes.

## Request bodies

Every business operation has `requestBody.required=true` and exactly `application/json` content.
The schema is a closed object matching exactly one envelope.

Public:

```json
{
  "type": "object",
  "properties": {
    "payload": {}
  },
  "required": ["payload"],
  "additionalProperties": false
}
```

Protected:

```json
{
  "type": "object",
  "properties": {
    "authorization": {
      "type": "object",
      "properties": {
        "access_token": {"type": "string"}
      },
      "required": ["access_token"],
      "additionalProperties": false
    },
    "payload": {}
  },
  "required": ["authorization", "payload"],
  "additionalProperties": false
}
```

The generator uses this distinction only to require empty or non-empty method scope metadata. It
does not infer exact scopes from OpenAPI descriptions.

## Responses

Every numeric 2xx response contains exactly `application/json`, and all numeric 2xx responses for
one operation resolve to the same schema. The closed envelope has exactly:

```text
ok
result
error
error_message
retry_after
```

Only `ok` is required by the OpenAPI schema. `ok` is boolean; error fields are string or null; body
retry delay is number, integer, or null. Runtime `PokerlostResponse` validation enforces the success
and failure combinations.

## Schema subset

Reachable schemas support JSON scalar types, null unions, arrays, closed objects, dictionaries,
local component references, `anyOf`, `oneOf`, object `allOf`, scalar enums, UUID and temporal string
formats, standard numeric/string/item constraints, defaults, and descriptions.

Declared object fields use lowercase `snake_case`, cannot begin with an underscore, and cannot
collide with the public Pydantic or `PokerlostType` API. Named generated types use PascalCase and
globally unique flat module names.

Only local `#/components/schemas/<Name>` references are accepted. Missing, external, malformed, or
recursive envelope references fail validation.

## Canonical and sensitive types

SDK-owned canonical type names resolve to `pypokerlost.types` rather than duplicate generated
models. A non-canonical schema with the same public name or module as another source fails global
preflight.

Known sensitive field names such as token, credential, password, login-grant, and key material are
rendered repr-hidden. Generated models also hide validation input.

## Scope verification

For a protected operation, generation requires one of:

- a hand-written method whose literal `operation` and `required_scopes` agree with the body schema;
- an explicit JSON scope-map entry.

A public method must have an empty scope tuple. If both sources exist, they must agree exactly.

OpenAPI cannot express exact scopes for body-token authorization with a standard security scheme.
Cross-repository verification therefore compares the service route's `Security(..., scopes=[...])`
declaration with `PokerlostMethod.required_scopes`.

See `docs/generator/usage.md`, `docs/architecture/generator.md`, and `docs/index.md`.
