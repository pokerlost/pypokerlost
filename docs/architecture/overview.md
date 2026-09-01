# Architecture overview

`pypokerlost` owns one private JSON operation-call protocol, one typed client pipeline, flat methods
and types, canonical errors, authorization middleware, retry middleware, and development-time
OpenAPI generation.

## Runtime flow

```text
PokerlostMethod
→ PokerlostClient
→ PokerlostRetryMiddleware
→ PokerlostAuthorizationMiddleware, when configured
→ PokerlostRequestBuilder
→ HttpxSession POST JSON transport
→ PokerlostResponse decoder
→ typed result or canonical error
```

The client always installs the retry layer outermost. Its policy remains inactive unless the call
provides `PokerlostRequestOptions.retry_policy`. Authorization is inside retry so every attempt can
obtain current token state without replaying an authentication failure.

## Runtime ownership

| Owner | Responsibility |
| --- | --- |
| `PokerlostMethod` | Strict payload fields, operation, exact required scopes, and result type. |
| `PokerlostClient` | Session ownership, request preparation, middleware composition, and context. |
| `PokerlostRequestOptions` | Optional per-call retry policy only. |
| `PokerlostAuthorizationMiddleware` | Token reuse, acquisition, refresh, storage coordination, and body injection. |
| `PokerlostRetryMiddleware` | Bounded opt-in retry from canonical exceptions. |
| `PokerlostRequestBuilder` | Public request envelope plus private call metadata binding. |
| `HttpxSession` | HTTPS target, POST JSON I/O, decoding, and result validation. |
| `PokerlostResponse` | The only response envelope. |
| `PokerlostApplication` | One client lifecycle and one synchronous entrypoint. |

## Public and protected calls

A public method has `required_scopes = ()`. It bypasses token storage and reaches transport as
`PokerlostRequest`. A protected method lists exact `PokerlostScope` values. Without authorization
middleware it fails locally; with middleware it reaches transport as `PokerlostAuthorizedRequest`.

Token acquisition and refresh are ordinary public calls through a dedicated auth-target client.
The dedicated client cannot contain authorization middleware, which prevents recursion.

## Protocol boundary

Business calls use `POST /<operationId>` and JSON bodies. Operation IDs are single lowerCamelCase
verbs; scope IDs are independent dotted lowerCamelCase strings. Project code does not provide a
generic HTTP metadata channel. Production targets require HTTPS.

The service side verifies access tokens locally through its own verifier adapter. The SDK does not
sign tokens, fetch keys, load credentials, decide roles, or provide production token persistence.

## Generator flow

```text
one or more OpenAPI 3.1 JSON documents
→ global operation and schema preflight
→ canonical envelope validation
→ explicit scope resolution
→ flat method/type rendering
→ manifest-safe write or check
```

OpenAPI shows body authorization through the request schema. Exact protected scopes remain in
route source and SDK method metadata because standard security schemes do not describe this private
body-token contract.

See `docs/index.md`.
