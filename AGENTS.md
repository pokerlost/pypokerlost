# pypokerlost engineering rules

This file defines the normative rules for changing the SDK. Product boundaries live in
`SERVICE.md`; user guidance lives under `docs/`.

## Before every task

- Read `AGENTS.md`, `SERVICE.md`, and `docs/architecture/overview.md`.
- Inspect implementation, call sites, Git status, and diffs before editing.
- Preserve unrelated changes and never add compatibility aliases unless explicitly required.

## Architecture

- Runtime code lives only under `src/pypokerlost/`; public imports remain `pypokerlost`.
- Keep flat focused `client/`, `enums/`, `errors/`, `methods/`, `middleware/`, `session/`, and
  `types/` packages. Never create service-named subpackages or `contracts/`.
- Every public enum class lives under the flat `pypokerlost/enums/` package.
- Runtime dependencies remain Pydantic and HTTPX unless a direct requirement changes them.

## Protocol

- Business calls use `POST /<operation>` with one pure `PokerlostRequest` JSON body.
- Protected calls carry their token only as `Authorization: Bearer <access-token>`.
- Explicit gateway targets also carry `x-pokerlost-serviceId`; this is routing, not a credential.
- Service identifiers are exact `ServiceId` members, independent of authorization audiences/scopes.
- Only the HTTP transport converts the internal typed token field into that header.
- No caller-facing or internal generic headers map is allowed.
- Every normal response, including authentication failure, uses `PokerlostResponse`.
- `retry_after` exists only in the response body and is finite, non-negative seconds.
- Production targets use HTTPS; loopback HTTP is allowed for development.

## Methods and scopes

- Operations match `^[a-z][A-Za-z0-9]*$`; business paths are exactly `/<operation>`.
- Every concrete method directly declares
  `__scopes__: ClassVar[tuple[PokerlostScopes, ...] | None]`.
- `None` means no access-token scope requirement. A non-empty tuple means exact required scopes.
- An empty tuple, duplicate, unknown member, non-canonical order, or missing declaration is a local
  configuration error before network I/O.
- Scope values contain dotted lowerCamelCase segments. Authorization is scope-only; the SDK has no
  authorization role model.

## Client and authentication

- `PokerlostClient.__call__` is the sole client execution method. Do not add `make_request` or
  metadata-returning variants.
- The current-client context supports `await Method(...)` without mutating method instances.
- `PokerlostRequestOptions` contains only an optional `PokerlostRetryPolicy`.
- `PokerlostRequest` is pure wire data. One private immutable call object owns method, wire request,
  options, exact scopes, and the optional internal access token.
- Authentication middleware accepts only persistent/shared `PokerlostTokenStore` and
  service-owned `PokerlostTokenRefresher` ports.
- The SDK never stores client credentials, automatically calls `GetToken`, owns a process cache,
  starts background refresh, or provides production persistence.
- Stored state uses an absolute timezone-aware UTC expiry and positive CAS version.
- Missing state fails locally. Only exact `POKERLOST_ACCESS_TOKEN_EXPIRED` can trigger one refresh;
  the exact request can be replayed once. Neither local expiry metadata nor any other error triggers
  refresh.

## Retry and errors

- Retry behavior lives only in `pypokerlost/middleware/retry.py` and is opt-in per call.
- The fixed policy is three attempts, delays from 0.2 to 2 seconds, multiplier 2, full jitter, and a
  five-second logical-call budget.
- Retryable statuses are 408, 425, 429, 500, 502, 503, and 504.
- A protocol error retains safe status metadata so malformed 502/503/504 responses can retry.
- Cancellation, malformed ordinary 2xx, authentication, authorization, 409, and 422 do not retry.
- Exceptions retain safe scalar metadata only and never retain raw bodies, credentials, or tokens.
- Do not use runtime assertions or pretend Python secret strings can be securely zeroed.

## Generator

- `scripts/generate_methods.py` is the single OpenAPI generator owner.
- One invocation accepts every service OpenAPI 3.1 document and validates global operation, method,
  module, and schema uniqueness before writing.
- `pypokerlost/enums/pokerlost_scopes.py` is the explicit SDK-owned shared scope catalog. The
  generator validates extracted scopes against it; it never synthesizes or overwrites the catalog.
- A document with no protected operations may omit `components.securitySchemes`; its public
  methods receive `__scopes__ = None`.
- If an operation is protected, its standard OAuth2 client-credentials scheme and security
  requirement are mandatory. The exact scope list must be non-empty and every value must exist in
  `PokerlostScopes`. Empty, unknown, ambiguous, OR/mixed, vendor-extension, and scope-map contracts
  fail.
- The manifest owns only files actually generated from implemented OpenAPI operations. Explicit
  future-facing method stubs stay outside generator ownership until a compatible route exists.

## Verification

- Add focused technical and regression tests for changed SDK protocol, generator, packaging, or lifecycle behavior. Do not add unimplemented business tests.
- Do not add task-specific checker scripts. Make and pre-commit targets remain thin wrappers around
  canonical tools, documentation validation, or the generator's first-class check mode.
- Use `uv`, Ruff, strict mypy, build checks, compile checks, and `git diff --check`.
- Never commit or push unless the user explicitly authorizes it.
