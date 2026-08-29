# Generated layout and ownership

One generator invocation owns a service-specific method package and type package below a single SDK
output root.

## Package layout

With the default `--output pypokerlost` and service ID `exampleService`, output has this shape:

```text
pypokerlost/
├── methods/
│   └── example_service/
│       ├── __init__.py
│       └── echo_method.py
└── types/
    └── example_service/
        ├── __init__.py
        └── _types.py
```

The service ID is converted to lowercase `snake_case` and validated as a Python package name.
`methods/<service_package>/` contains one focused `PokerlostMethod` module per operation plus its
public facade. `types/<service_package>/_types.py` contains referenced `PokerlostType` models and
generated aliases; the adjacent facade exports the service's public type names.

The types package is generated even when an operation does not reference a named API type. Files
are ordered deterministically and contain a header identifying the generator, generator version,
service, OpenAPI version, and canonical source hash.

## Reserved service packages

Service package names that collide with hand-maintained SDK modules are rejected. The exact
reserved set is:

```text
api_base
base
json
operation
storage_key
storage_ttl
```

Generated type and method class names are also checked against runtime imports and against each
other before files are written.

## Manifest v2

Each canonical output root and service package has one version-two manifest at:

```text
scripts/.generated_methods/<output-sha256>/<service_package>.json
```

Repository-local roots are identified by a tagged repository-relative canonical path. External
roots are identified by a tagged canonical absolute path. Only the SHA-256 of that identity appears
in the directory name, so distinct `--output` roots have independent ownership and contract-version
history.

The manifest records:

- `manifest_version`, currently `2`;
- `generator_version`;
- OpenAPI `info.version` as `openapi_version`;
- the canonical OpenAPI `source_sha256`;
- `service_id` and derived `service_package`;
- the complete sorted `files` ownership list.

Every owned file is a normalized relative `.py` path below exactly one of:

```text
methods/<service_package>/
types/<service_package>/
```

A manifest must own files in both namespaces. Absolute paths, parent traversal, duplicate paths,
unsorted ownership, and ownership outside the service package are invalid.

## Existing and manual files

Normal generation handles an expected target as follows:

- a missing file may be created;
- an existing file may be replaced when its first line is the exact generator header;
- an existing file without that header is treated as manual or conflicting and blocks generation;
- explicit `--force` permits replacement of that conflicting expected target.

Unrelated files outside the expected generated paths are not overwritten or removed. Because
`--force` can replace a manual file at an expected target, use it only after reviewing the complete
output path.

## Stale generated files

A file becomes stale when it belongs to the previous manifest but is absent from the newly rendered
file set. The writer removes it only when both conditions hold:

1. the previous manifest proves ownership;
2. the file still begins with the exact generator header.

Changing or removing the header makes deletion fail, including under `--force`. Missing stale files
need no cleanup, and unowned extra files are left in place.

`--check` reports an existing stale manifest-owned file without removing it. It also reports missing
or changed expected source and missing or changed manifest content.

## Version policy

Without `--force`, OpenAPI `info.version` cannot decrease relative to the stored manifest. If the
canonical source hash changes, version precedence must increase. A version increase with unchanged
content is allowed, as is unchanged content at the same version.

The current generator version is `1.1.0`. Generator versioning follows SemVer: `MAJOR` covers an
incompatible generated layout, generated public API, manifest format, or CLI change; `MINOR` covers
backward-compatible OpenAPI or optional CLI capability; `PATCH` covers fixes that preserve those
contracts.

## Previous-layout migration

A detected previous methods-only manifest or generated layout is not mixed silently with the
current methods/types split. Review the requested SDK root and perform one intentional generation
with `--force` to migrate.

Migration normalizes proven previous ownership into SDK-root-relative paths, writes the current
sources and scoped manifest, and then removes obsolete manifest state. Generated source is removed
only when prior ownership and the generator header both prove that deletion is safe. Unowned stale
source is never inferred to be disposable.

See `docs/generator/usage.md` for invocation details and `docs/generator/contract.md` for accepted
input.

See `docs/index.md`.
