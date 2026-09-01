# Authorization contracts

The SDK owns shared authorization data shapes, not credentials, token orchestration, signing, or
verification.

## Scope identifiers

Use the focused type facade:

```python
from pypokerlost.types import (
    OAuthScope,
    format_oauth_scope_string,
    parse_oauth_scope_string,
)
```

An `OAuthScope` has at least two dot-separated lowerCamelCase segments. Each segment starts with a
lowercase ASCII letter and then contains ASCII letters or digits. Underscores, hyphens, empty
segments, whitespace, and wildcards are invalid.

`parse_oauth_scope_string()` accepts one non-empty, duplicate-free, space-delimited string and
returns a sorted tuple. `format_oauth_scope_string()` validates a non-empty iterable, rejects
duplicates, and returns the canonical lexicographically sorted string.

## Shared models

Import shared wire models and enums from one facade:

```python
from pypokerlost.contracts.authorization import (
    AccessTokenClaims,
    AuthorizationContext,
    AuthorizationRole,
    OAuthTokenResponse,
    OAuthTokenType,
    PrincipalStatus,
    PrincipalType,
)
```

`OAuthTokenResponse` is the strict frozen result of the generated `oauth.token` method. Token
values are hidden from repr and validation errors. A service token may omit `refresh_token`; when
absent, that field is omitted from model serialization without changing the surrounding response
envelope.

`AccessTokenClaims` validates decoded claim data and uses `iss`, `sub`, `aud`, `iat`, `nbf`, `exp`,
and `jti` as serialization aliases. Numeric dates serialize as integer JWT NumericDate values.
Human identity requires `account_id` and `session_id`; service identity requires `service_slug`.
The model performs no cryptographic or network work.

`AuthorizationContext` contains the verified principal identity, audience, and a canonical immutable
tuple of exact scopes. It has no role-based bypass property. Each resource service creates this
value only after its own verification adapter has validated the presented token.

## Ownership boundary

A consuming service decides when it needs a token, which credentials and scopes it owns, and how it
stores lifecycle state. Its application handler calls a service-owned port, whose adapter invokes
the ordinary generated `oauth.token` method. The SDK only constructs the declared form request,
sends it, and decodes `Response[OAuthTokenResponse]`.

See `docs/api/transport.md` for generic headers and form serialization.

See `docs/index.md`.
