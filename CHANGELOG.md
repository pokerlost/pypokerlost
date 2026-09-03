# Changelog

## Unreleased

- Move protected access tokens from JSON bodies to the standard `Authorization: Bearer` header.
- Make `PokerlostRequest` a pure wire envelope and `PokerlostClient.__call__` the only client
  execution method.
- Keep `PokerlostScopes` as the explicit SDK-owned shared catalog and validate generated method
  `__scopes__` metadata against it; `None` is public and empty tuples are invalid.
- Allow OpenAPI documents with no protected operations to omit an unused OAuth2 security scheme;
  protected operations still require standard OAuth2 security metadata.
- Remove authorization-role contracts and replace principal assignment with exact scope replacement.
- Replace credential-owning automatic token lifecycle behavior with shared UTC/versioned store and
  injected refresher ports plus one exact expired-token replay.
- Preserve body-only `retry_after`, safe protocol status metadata, and malformed gateway retry.
