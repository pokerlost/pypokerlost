# Supported generator contract

The generator accepts OpenAPI 3.1 JSON documents with SemVer `info.version`, paths, and schemas. A
document with no protected operations may omit `components.securitySchemes`. If at least one
operation declares security, the document must contain one supported OAuth2 scheme using only
`clientCredentials`, exact `tokenUrl: /getToken`, and a dotted lowerCamelCase scope-description
map. Vendor extensions and document-level security are rejected.

Business operations use `POST /<singleLowerCamelCaseOperation>`, a required JSON
`PokerlostRequest` containing only `payload`, and `PokerlostResponse` for every documented status.
Recognized bodyless infrastructure GET operations are skipped.

An operation without a security requirement has no access-token scopes and generates
`__scopes__ = None`. Protected operation security is exactly one mapping from the supported scheme
to a non-empty list of known exact scopes. Mixed requirements, OR alternatives, empty protected
lists, unknown or ambiguous schemes, and unknown scopes are invalid.

All documents are checked for global operation, class, module, and schema collisions. Output stays
flat. Canonical SDK types are reused; other reachable schemas are rendered within the supported
JSON Schema subset. Secrets are repr-hidden.

`pypokerlost/enums/pokerlost_scopes.py` is the explicit shared SDK contract. The generator validates
every extracted protected scope against this catalog and never derives, rewrites, or claims
manifest ownership of it. It does not infer planned scopes or operations from incomplete service
documents.

Handwritten method compatibility requires direct `operation`, `returning`, payload fields, and the
canonical annotated `__scopes__`. Missing or empty metadata fails; a handwritten declaration is
never an alternative source of protected route metadata. A future-facing stub stays outside
generator ownership until the corresponding route exists and the whole contract is compatible.
