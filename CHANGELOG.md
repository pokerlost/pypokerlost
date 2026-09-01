# Changelog

## Unreleased

- Replaced the previous transport with the private body-only Pokerlost JSON protocol.
- Renamed project-owned public identifiers to consistent `Pokerlost*` casing without aliases.
- Added canonical public and protected request envelopes and the five-field `PokerlostResponse`.
- Moved retry into flat middleware with explicit `retry_policy` opt-in and body `retry_after`.
- Added authorization middleware with exact-scope token selection, single-flight acquisition,
  refresh support, body injection, and no automatic authentication-failure replay.
- Added body-only `GetToken` and `RefreshToken` methods plus typed future-facing auth stubs.
- Flattened generated methods and types and removed service-named compatibility packages.
- Updated generation to validate multiple OpenAPI documents together and reject global
  operation/type collisions before writing.
- Removed generic caller metadata, form serialization, response side channels, and client-local
  storage abstractions.
