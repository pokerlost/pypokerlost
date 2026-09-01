# Supported generator contract

This page is the authoritative prose contract for the OpenAPI subset accepted by
`scripts/generate_methods.py`.

## Document requirements

Input is an OpenAPI JSON document. YAML is not supported. The document must provide:

- an `openapi` value in exact `MAJOR.MINOR.PATCH` form and within `3.1.x`;
- a non-empty `info.title`;
- an `info.version` in exact `MAJOR.MINOR.PATCH` form;
- a `paths` object;
- one `x-pokerlost-service` object containing only an `id` field.

The service ID must match:

```text
^[A-Za-z][A-Za-z0-9_-]*$
```

The service extension has this shape inside the complete document:

```json
{
  "x-pokerlost-service": {
    "id": "exampleService"
  }
}
```

If `jsonSchemaDialect` is present, it must be either the JSON Schema Draft 2020-12 dialect or the
OpenAPI 3.1 base dialect.

## API operations

A generated `operationId` must match the runtime `APIOperation` contract:

```text
^[a-z][A-Za-z0-9]*\.[a-z][A-Za-z0-9]*$
```

The identifier has exactly two segments and one dot. Both segments begin with a lowercase ASCII
letter and otherwise contain only ASCII letters or digits. Ordinary lowerCamelCase is supported;
underscores, hyphens, extra dots, missing dots, and uppercase initials are rejected.

Every non-root operation path must equal `/` followed by that complete operation ID. The root path
`/` is the sole path exception, but its operation ID must still satisfy `APIOperation`. The supported
HTTP methods are `GET`, `POST`, `PUT`, `PATCH`, and `DELETE`. Duplicate operation IDs and generated
Python naming collisions are errors.

Path-level and operation-level OpenAPI parameters are not supported. All operation IDs and paths
are validated before the system path `/` and active OpenAPI publication path are excluded from
method generation. Both modes use the validated `--openapi-operation` selector, which defaults to
`openapi.get`; service mode also uses it to build the fetch path, while file mode performs no fetch.
Operations marked `deprecated: true` are skipped. At least one non-system, non-deprecated API
operation must remain.

## Request bodies

An operation may omit `requestBody`, in which case its method class has no request fields. A present
request body must:

- be inline or use a local `#/components/requestBodies/<Name>` reference;
- contain exactly one of `application/json` or `application/x-www-form-urlencoded`;
- define a schema for that declared media type;
- resolve to an object-shaped schema with declared fields or an explicitly closed empty object.

Free-form request bodies are rejected. A request object with properties must set
`additionalProperties` to `false`. A closed empty request uses `additionalProperties: false` with
no properties. The OpenAPI `requestBody.required` value is accepted but does not change generated
method fields.
Form request properties are limited to strings or flat arrays of strings so generic URL encoding is
deterministic and matches the declared wire shape.

## Successful responses

Only digit-only status keys from `200` through `299` are success responses. Wildcard keys such as
`2XX`, `default`, and non-2xx responses are not used to select the generated result.

Every numeric 2xx response must:

- be inline or use a local `#/components/responses/<Name>` reference;
- contain only the `application/json` media type;
- define an `application/json` schema;
- use the same canonical schema as every other numeric 2xx response for that operation.

At least one such response is required. Its schema must be a closed object with exactly these
properties:

```text
ok
result
error
error_message
```

`additionalProperties` must be `false`. The `required` list must include `ok`; it may also mark any
of the other envelope fields as required. `ok` must be boolean. `error` and `error_message` must
each permit only `string`, `null`, or both. The generator removes the envelope-level `null` branch
from `result` before rendering the declared method result type.

## JSON Schema subset

Reachable schemas support:

- `string`, `integer`, `number`, `boolean`, `null`, `array`, and `object` types;
- type arrays and nullable types;
- `anyOf` and `oneOf` unions;
- non-null object composition through `allOf`;
- local schema references;
- arrays with an `items` schema;
- open JSON dictionaries and schema-valued `additionalProperties` dictionaries;
- scalar `enum` and `const` values containing strings, integers, booleans, or `null`;
- string formats `uuid`, `date`, `date-time`, and `time`;
- `minimum`, `maximum`, `exclusiveMinimum`, and `exclusiveMaximum`;
- `minLength`, `maxLength`, and `pattern`;
- `minItems` and `maxItems`;
- required fields, JSON-compatible defaults, and descriptions.

Object schemas with properties must set `additionalProperties: false`. Nested and returned object
models with declared properties must be named component schemas; inline object models in those
positions are not supported. Arrays must define `items`.

`anyOf`, `oneOf`, and `allOf` cannot be combined on one schema and cannot be empty. `allOf` is
limited to compatible object composition. Empty literal sets, incompatible literal values, and
unsupported semantic siblings are rejected. Formatted strings cannot also declare length or
pattern constraints. Length and item limits must be non-negative, and patterns must be accepted by
Pydantic's regular-expression engine.

## Generated identifiers

Reachable component names used as generated types must be PascalCase Python class names. Object
property names must be lowercase `snake_case`, cannot start with an underscore, and cannot collide
with the public Pydantic or `PokerlostType` model API. Required property names must be unique and
must identify declared properties.

The service ID is converted to `snake_case` for its package. Generation fails if the result is not a
valid Python package name or collides with a reserved core package; see
`docs/generator/generated-layout.md`.

## References and reachability

Only single-component local references are supported:

```text
#/components/schemas/<Name>
#/components/requestBodies/<Name>
#/components/responses/<Name>
```

External references, empty component names, and reference names containing another `/` are
rejected. Pure reference cycles and cyclic object composition are unsupported. Recursive named
object relationships remain supported.

Component schema, request-body, and response values are normally validated strictly only when a
selected request or numeric 2xx response makes them reachable. Canonical shared component names
are the deliberate exception: when present, they are checked against the SDK-owned shape even if
unused. Other unused schemas and non-success response schemas remain opaque JSON.

Recognized descriptive metadata does not affect generated code. Extension fields beginning with
`x-` are generally accepted and ignored, but request-body and response reference objects still
forbid siblings other than `description`. Security metadata may be present where OpenAPI permits
it, but the generator does not interpret it or emit authorization policy.

## Shared contracts

Canonical component names for OAuth scopes, token results, decoded claims, verified authorization
contexts, and their shared enums are mapped to public `pypokerlost` imports. Each component schema
must semantically match the SDK-owned schema. The comparison normalizes only framework spelling of
absent default values and numerically equal JSON Schema bounds; a same-named structurally
incompatible component fails generation.

This is a small built-in closed mapping. It uses no plugin registry, runtime import reflection,
Python-import extension, or route metadata.

See `docs/generator/usage.md` to run the generator and `docs/architecture/generator.md` for the
processing model.

See `docs/index.md`.
