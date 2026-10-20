# Changelog

Notable SDK and generator changes are recorded here; publication requires a separate decision.

## 0.3.0.dev0 (unreleased)

- Add `make version`, `release-check` and standalone Docker `ci-local` with source identities,
  artifact checksums and native installed-generator acceptance. No public SDK contract changes
  are introduced by this delivery-tooling update.

- Preserve the existing candidate package version and independent generator/manifest versions.
- Fix schema references inside map values, outer nullable multi-type results and safe failures when
  canonical Pydantic schemas cannot be inspected.
- Run the source protocol/lifecycle/generator suite once and accept the exact built wheel
  separately. Fresh statement/branch coverage below 100% warns; test/build/report errors fail.
- Exclude local metadata from built archives independently of Git ignore handling.

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
