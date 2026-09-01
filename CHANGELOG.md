# Changelog

## Unreleased

- Established shared OAuth scope, token, claims, principal, and authorization-context contracts.
- Moved credential and token lifecycle orchestration outside the SDK boundary.
- Added generic form request serialization for generated OpenAPI methods.
- Generated `OAuthTokenMethod` from the standard authService form and response contract.
- Replaced configurable retry variants with one fixed, explicit `PokerLostRetryPolicy`.
- Removed project-owned route metadata helpers in favor of standard OpenAPI primitives.
- Made empty generated type facades stable under the repository formatter and fixed-point checks.
