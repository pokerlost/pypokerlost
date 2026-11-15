# Generator architecture

The generator validates all OpenAPI 3.1 documents together before any write:

```text
documents
→ protected-operation discovery
→ conditional standard OAuth2 validation
→ scope membership validation against SDK PokerlostScopes
→ global business operation/schema/module preflight
→ exact operation security validation
→ flat method/type rendering
→ manifest-safe write or --check
```

A document with no protected operations may omit `components.securitySchemes`; each of its methods
receives `__scopes__ = None`. If at least one operation declares security, the document must expose
the supported standard OAuth2 client-credentials scheme. Each protected operation has exactly one
requirement referring only to that scheme and at least one scope. Empty lists, unknown or ambiguous
schemes, unknown scopes, duplicates, and OR alternatives fail.

`src/pypokerlost/enums/pokerlost_scopes.py` is an explicit SDK-owned catalog, not generated output.
Every extracted scope must already have an exact member. Generated methods import those members and
annotate metadata as a `ClassVar`. Every handwritten concrete method is parsed to validate explicit
non-empty-or-`None` metadata; full payload/result compatibility is also checked when its endpoint
appears. Handwritten files never override OpenAPI.

Generated ownership is recorded by the existing manifest only for files actually rendered from
implemented operations. Non-generated stubs and the shared scope catalog are not silently
overwritten or deleted, and `--check` compares the entire expected fixed point.

## Implementation boundaries

`scripts/generate_methods.py` remains the compatible import facade, direct script and
CLI owner. It loads source documents, inspects handwritten modules, controls manifest
ownership, and performs the final checked writes. Its repository-relative manifest
paths remain local to that facade.

The optional `src/pypokerlost_generator/` package contains pure implementation modules:

- `models.py`: immutable intermediate records, canonical SDK metadata and name conversion.
- `schema.py`: input validation, reference/allOf resolution and global operation/type collection.
- `rendering.py`: deterministic Python annotations, imports, types, methods and facades.

These modules do not fetch contracts or write generated files. The established facade
re-exports their symbols explicitly so existing `scripts.generate_methods` callers
continue to work. The wheel includes the package and maps the same script to
`pypokerlost_generator.__main__`; there is no runtime path injection or fallback import.
Committed golden fixtures exercise supported allOf, nullable and enum shapes, protected
scope metadata, failure envelopes, and byte-identical direct-script output.
