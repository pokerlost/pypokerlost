# pypokerlost engineering rules

This file defines the normative rules for changing the SDK. Product boundaries live in
`SERVICE.md`; user guidance lives under `docs/`.

## Before every task

- Read `AGENTS.md`, `SERVICE.md`, and `docs/architecture/overview.md`.
- Inspect the implementation, affected call sites, current Git status, and diff.
- Treat the working tree and current implementation as authoritative.
- Preserve unrelated changes and never add compatibility aliases unless directly required.

## Architecture

- Runtime code lives directly under `pypokerlost/`; do not add a `src/` layout.
- Keep flat focused packages: `client/`, `errors/`, `methods/`, `middleware/`, `session/`, and
  `types/`.
- Do not recreate `contracts/`, service-named method/type directories, storage frameworks,
  provider graphs, plugin registries, service locators, or reflection-based dispatch.
- Runtime dependencies remain Pydantic and HTTPX unless a direct requirement changes them.
- One abstraction owns one concrete responsibility. Do not create forwarding-only wrappers or
  catch-all modules.

## Public API and naming

- Public facades and documented import paths are deliberate API.
- Project-prefixed identifiers use `Pokerlost` as one PascalCase word.
- The distribution and package remain named `pypokerlost`.
- Do not provide aliases for removed names or paths.
- `PokerlostMethod[ResultT]` declares `operation`, `required_scopes`, and `returning`.
- Operation IDs match `^[a-z][A-Za-z0-9]*$`; every business path is `/<operationId>` and every
  business call uses POST.
- Root, OpenAPI publication, and health probes are public bodyless GET infrastructure exceptions.
- Scope IDs match `^[a-z][A-Za-z0-9]*(\.[a-z][A-Za-z0-9]*)+$`; every segment uses lowerCamelCase.
- Operation IDs and scope IDs are independent values. Never derive one from the other.

## Body-only protocol

- Pokerlost APIs use a private JSON protocol over HTTPS. It is not OAuth2 wire-compatible.
- Public and token operations use `PokerlostRequest[PayloadT]` with only `payload`.
- Protected operations use `PokerlostAuthorizedRequest[PayloadT]` with exactly `authorization`
  and `payload`; the access token is only `authorization.access_token`.
- `getToken` carries client ID, client secret, exact scopes, and audience inside its JSON payload.
- `refreshToken` carries the refresh token, optional exact scopes, and audience inside its JSON
  payload.
- Project code does not expose, accept, merge, construct, or inspect caller-controlled HTTP
  headers, cookies, query authentication, or form authentication.
- The session uses HTTPX's `json=` API. It does not manually construct protocol framing.
- `PokerlostResponse[ResultT]` is the only response envelope. Its fields are `ok`, `result`,
  `error`, `error_message`, and `retry_after`.
- `retry_after` exists only in the response body and is finite, non-negative seconds.

## Client and session

- `PokerlostClient` owns one `PokerlostSession`, request construction, middleware composition, and
  current-client context.
- `PokerlostRequestOptions` contains only `retry_policy`.
- `PokerlostRequestBuilder` creates an immutable public request envelope and binds non-wire method
  and option metadata privately.
- `HttpxSession` owns the API target, HTTPX lifecycle, POST JSON I/O, envelope decoding, result
  validation, and canonical transport errors.
- Production targets require HTTPS. Plain HTTP is accepted only for loopback development.
- Both 2xx and non-2xx bodies are decoded as `PokerlostResponse`.
- Malformed bodies become `PokerlostProtocolError`; transport failures become the canonical
  connection or timeout errors.
- Exceptions retain only safe scalar metadata. They never retain raw bodies, credentials, tokens,
  or private keys.
- All network and lifecycle APIs are asynchronous. `PokerlostApplication.run()` is the sole
  synchronous event-loop owner.

## Middleware

- Middleware is the only SDK cross-cutting mechanism. It is explicit, typed, and flat.
- Ordering is retry outermost, authorization inside, then transport.
- A client is valid without authorization middleware only for public methods.
- Protected methods without authorization middleware fail locally before network I/O.
- Public methods never load token state and never acquire or attach a token.
- `PokerlostAuthorizationMiddleware` owns acquisition, refresh, exact-scope token selection,
  single-flight locking, storage calls, and body injection.
- Token calls use a dedicated auth-target `PokerlostClient` without authorization middleware.
- `PokerlostTokenStore` is a behavior-only protocol with `load`, `save`, and `invalidate`, keyed by
  audience plus the exact canonical scope tuple. The SDK ships no production persistence backend.
- A `401` or authentication error invalidates matching state and propagates without replaying the
  current operation. A `403` or insufficient-scope error neither refreshes nor retries.

## Retry

- Retry behavior exists only in `pypokerlost/middleware/retry.py`.
- `PokerlostRetryMiddleware` is always the outer middleware, but retry is disabled unless the call
  supplies `PokerlostRequestOptions(retry_policy=PokerlostRetryPolicy())`.
- The immutable policy has three total attempts, 0.2-second initial delay, 2.0-second maximum
  delay, multiplier 2.0, full jitter, and a five-second logical-call budget.
- Retryable failures are connection errors, timeout errors, and API statuses 408, 425, 429, 500,
  502, 503, and 504.
- Protocol errors, cancellation, authentication failures, authorization failures, and other
  statuses propagate immediately.
- A valid body `retry_after` overrides local jitter only when it fits the remaining budget.
- Exhaustion re-raises the last canonical underlying error.
- Transport retry is not business idempotency. The consumer owns stable operation identifiers,
  semantic payloads, target guarantees, transaction boundaries, and reconciliation.

## Types and sensitive data

- Wire/value models live as focused flat modules under `pypokerlost/types/`.
- `PokerlostScope` and `PokerlostOperation` are validated string values.
- `PokerlostToken` is data only; it does not fetch, refresh, sign, verify, or persist itself.
- Token state uses monotonic expiry and does not assume wall-clock timestamps.
- Secret-bearing fields serialize when required by the wire contract but remain hidden from repr
  and validation input output.
- Use `Callable[..., ReturnT]` or a meaningful `Protocol.__call__`; do not use an empty callable
  argument list.
- Use Pydantic validation, `ValueError`/`TypeError` at pure boundaries, and canonical SDK errors at
  runtime boundaries. Do not use assertions for production invariants.

## Generator

- `scripts/generate_methods.py` is development tooling and the single generator owner.
- The `file` command accepts one or more OpenAPI 3.1 JSON documents and validates them together
  before writing.
- Business operations must use POST, `/<operationId>`, required JSON request bodies, one canonical
  request envelope, and `PokerlostResponse`.
- OpenAPI service identity extensions are neither required nor consumed.
- Global operation, method class/module, public schema, and schema-module collisions fail before
  any write.
- Output is flat: `methods/<operation_module>.py` and `types/<type_module>.py`.
- Protected-operation scopes come from a checked explicit scope map or an existing hand-written
  method. Never infer scopes from operation names or descriptive prose.
- OpenAPI represents body authorization honestly through its request schema. It must not publish a
  misleading standard security scheme.
- The manifest removes only proven generator-owned stale files. Manual future-facing stubs remain
  outside generator ownership unless the generator created them.
- Generated modules import stable runtime facades only and never import generator internals.

## Documentation and tooling

- Keep `README.md` concise, `SERVICE.md` authoritative, and `docs/index.md` complete.
- Documentation is English, uses current public imports, and distinguishes SDK stubs from deployed
  service endpoints.
- Do not use relative inter-file Markdown links; reference repository paths in inline code.
- Use `uv`, Ruff, strict mypy, the repository Makefile, and the existing documentation checker.
- Before handoff, run applicable lock, format, lint, type, compile, documentation, generator,
  import, build, and diff checks. Report unavailable checks exactly.
- Never commit or push unless the current request explicitly authorizes it.
