# Outbound middleware, service authentication, and retry

The `pypokerlost.middleware` facade owns the single outbound method-call pipeline, including
secret-safe bearer authentication and explicit bounded retry.

## Public middleware contract

Import the complete public contract from one focused facade:

```python
from pypokerlost.middleware import (
    APIMiddleware,
    APIMiddlewareCallNext,
    APIMiddlewareContext,
    BearerTokenMiddleware,
    RetryMiddleware,
)
```

A custom component implements this asynchronous call signature:

```python
from pypokerlost.middleware import (
    APIMiddleware,
    APIMiddlewareCallNext,
    APIMiddlewareContext,
)


class TraceHeaderMiddleware(APIMiddleware):
    async def __call__[ResultT](
        self,
        call_next: APIMiddlewareCallNext[ResultT],
        context: APIMiddlewareContext,
    ) -> ResultT:
        options = context.options.with_headers({"X-Trace-ID": "trace-123"})
        return await call_next(options=options)
```

`APIMiddlewareContext` is a frozen, strict model containing only `operation`, `http_method`, and
the current immutable `RequestOptions`. Middleware cannot access or replace the method, request
body, declared result type, client, session, or an HTTPX object. `APIMiddlewareCallNext` executes
the one method snapshot captured by `Client`.

Omitting `options` when calling `call_next` inherits the current options. Supplying options
replaces them for the remaining inner chain; use `with_headers()` to preserve unrelated headers.
Middleware may short-circuit by returning a compatible result, and its exceptions and caller
cancellation propagate normally.

`APIMiddleware` also defines asynchronous `start()` and `close()` hooks plus async-context
behavior. Default hooks do nothing. The client owns these hooks as described in
`docs/architecture/client-lifecycle.md`.

## Registration and ordering

Pass the complete ordered middleware sequence when constructing a client:

```python
from pypokerlost import Client
from pypokerlost.middleware import BearerTokenMiddleware, RetryMiddleware

client = Client(
    session=session,
    middleware=(
        RetryMiddleware(),
        BearerTokenMiddleware(token_provider),
    ),
)
```

The client copies the sequence into an immutable tuple. There is no post-construction middleware
registration API. The first component is outermost:

```text
RetryMiddleware(
    BearerTokenMiddleware(
        session
    )
)
```

This order makes each retry attempt pass through bearer resolution. A usable token normally comes
from the provider's process-local cache; a missing or near-expiry token is acquired before that
attempt reaches the protected operation.

`RetryMiddleware` consumes the retry policy before invoking the inner chain. Configuring it more
than once therefore does not multiply the number of attempts, but one outer instance is the
canonical and clearest composition.

## Client-credentials authentication

The authentication facade is:

```python
from pypokerlost.client.auth import (
    AccessToken,
    AccessTokenProvider,
    ClientCredentials,
    ClientCredentialsTokenProvider,
)
```

The focused constructors are:

```text
ClientCredentials(
    *,
    client_id: UUID,
    client_secret: SecretStr,
)

ClientCredentialsTokenProvider(
    *,
    api_server: APIServer,
    credentials: ClientCredentials,
    scopes: frozenset[str],
    resource: str,
    refresh_skew: float = 30.0,
    timeout: int = DEFAULT_TIMEOUT,
)

BearerTokenMiddleware(token_provider: AccessTokenProvider)
RetryMiddleware()
```

Scopes must be a non-empty exact set accepted by the OAuth2 scope grammar. The provider sorts them
deterministically. `resource` must be a stable `urn:pokerlost:service:<serviceIdentity>` value;
refresh skew is finite from 0 through 3600 seconds, and timeout is an integer from 1 through 300
seconds. Client secrets must be non-empty UTF-8 `SecretStr` values; access tokens are non-empty
visible ASCII stored as `SecretStr`.

The following import-valid composition contains no credential value:

```python
from uuid import UUID

from pydantic import SecretStr

from pypokerlost import Client
from pypokerlost.client.api_server import APIServer
from pypokerlost.client.auth import ClientCredentials, ClientCredentialsTokenProvider
from pypokerlost.client.session import HttpxSession
from pypokerlost.middleware import BearerTokenMiddleware, RetryMiddleware


def create_auth_service_client(client_secret: SecretStr) -> Client:
    api_server = APIServer.from_base("https://auth.pokerlost.example")
    credentials = ClientCredentials(
        client_id=UUID("00000000-0000-0000-0000-000000000000"),
        client_secret=client_secret,
    )
    token_provider = ClientCredentialsTokenProvider(
        api_server=api_server,
        credentials=credentials,
        scopes=frozenset(
            {
                "auth.internal.provision_human",
            },
        ),
        resource="urn:pokerlost:service:authService",
        refresh_skew=30.0,
        timeout=10,
    )
    return Client(
        session=HttpxSession(api_server=api_server, timeout=10),
        middleware=(
            RetryMiddleware(),
            BearerTokenMiddleware(token_provider),
        ),
    )
```

The provider sends exactly one focused SDK-internal request for each acquisition attempt:

```text
POST /oauth.token
Content-Type: application/x-www-form-urlencoded
HTTP authentication: Basic over base64(client_id:client_secret)

grant_type=client_credentials
scope=<sorted exact scopes separated by spaces>
resource=<target service identity>
```

The form never contains `client_id` or `client_secret`. The provider uses an internal specialization
of the existing `HttpxSession` transport because the token request is form-encoded instead of a
generated JSON method. Consumer services do not construct a second HTTP client or decode the
response themselves.

`/oauth.token` uses the same four-field PokerLost `ApplicationResponse` envelope as every other
operation. The provider reuses `ResponseHandler`, validates a successful result with a non-empty
secret access token, literal `bearer` token type, positive `expires_in`, and canonical sorted scope
string, and requires the granted scopes to equal the requested scopes. The token exists only as
`ApplicationResponse.result.access_token`. A handled failed envelope raises the canonical
`PokerlostAPIError`; protocol and decode failures retain their usual SDK types. The provider does
not accept a raw OAuth2 token response.

## Token cache and lifecycle

`ClientCredentialsTokenProvider` keeps one process-memory cache. It derives expiry from
`expires_in` and monotonic time captured before acquisition, so request latency never extends the
server-issued lifetime. A token already expired when received is rejected; a cached token becomes
unusable when it reaches the configured non-negative refresh skew. The provider does not parse
JWTs or use wall-clock claims.

Concurrent cache misses share one acquisition task under a lock. Each waiter uses cancellation
shielding, so cancelling one caller does not cancel the acquisition needed by other callers. A
failed acquisition does not populate or poison the cache, and a later call can try again.

`BearerTokenMiddleware.start()` starts the provider. Its `close()` marks the provider closed,
cancels and awaits an in-flight acquisition, clears cached token and task references, and closes
the dedicated token session. Calling `get_access_token()` after close raises `ClientStateError`
until `start()` is called again.

Service principals have no refresh token. Refresh is an on-demand acquisition near expiry, not a
periodic background task. Neither the provider nor bearer middleware automatically replays a
protected operation after `401` or `403`.

`ClientCredentials`, `AccessToken`, request headers, and token response fields exclude secret
values from repr and validation output. Exceptions contain safe operation, status, and application
error metadata only. Callers must not log middleware contexts, credentials, authorization headers,
or raw token request and response data.

## Bearer behavior

For each attempt, `BearerTokenMiddleware` obtains an `AccessToken` and derives new immutable
options containing `Authorization: Bearer ...`. It rejects any caller-supplied `Authorization`
header case-insensitively with `MiddlewareConfigurationError` and never overwrites existing
credentials. The error does not include the header or token value.

Bearer middleware performs header enrichment only. It does not inspect JWT claims, select scopes,
make authorization decisions, handle `401`/`403`, or initiate an unbounded replay.

## Explicit retry policy

Import retry policy and request options from their focused facades:

```python
from pypokerlost.client.request import RequestOptions
from pypokerlost.client.retry import RetryPolicy
```

Retry is disabled when `RequestOptions.retry` is `None`, even when the client contains
`RetryMiddleware`. Opt in on one replay-safe call:

```python
result = await client(
    method,
    options=RequestOptions(
        retry=RetryPolicy(
            max_attempts=3,
            initial_delay=0.2,
            max_delay=2.0,
            backoff_multiplier=2.0,
            total_budget=10.0,
            respect_retry_after=True,
        ),
    ),
)
```

`max_attempts` includes the first attempt. `RetryPolicy` is frozen, strict, extra-forbid, and
bounded: attempts are from 1 through 10; delays are finite and from 0 through 60 seconds;
`initial_delay` cannot exceed `max_delay`; the multiplier is from 1 through 100; an optional total
budget is positive and no more than 600 seconds. The budget starts before the first attempt and
covers elapsed attempts and backoff when deciding whether another attempt may start; it does not
cancel an already in-flight transport request.

## Retry classification

| Condition | Without policy | With explicit policy |
|---|---|---|
| `ClientConnectionError` or `ClientTimeoutError` | One attempt | Retried within bounds. |
| Local transport/request `ClientRequestError` | One attempt | Not retried. |
| Status `408`, `425`, `429`, `500`, `502`, `503`, or `504` on `PokerlostAPIError` | One attempt | Retried within bounds. |
| Malformed response with one of those statuses (`ClientDecodeError`) | One attempt | Retried within bounds. |
| `401`, `403`, `404`, `409`, `410`, or `422` | One attempt | Not retried. |
| Business conflict or validation reported as `409` or `422` | One attempt | Not retried. |
| `PokerlostProtocolError` | One attempt | Not retried. |
| `ClientDecodeError` on an ordinary `2xx` response | One attempt | Not retried. |
| Local validation, serialization, or middleware configuration error | One attempt | Not retried. |
| Caller cancellation | Propagates immediately | Propagates immediately. |

A valid failed `503` envelope and a malformed `503` response are both retryable after explicit
opt-in. The final attempt re-raises the canonical last SDK exception; there is no generic
retry-exhausted wrapper.

The provider itself has no hidden retry loop. Without a per-call policy, token acquisition makes
one attempt. With `RetryMiddleware` outermost, a retryable acquisition failure can repeat as part
of the same bounded protected call under the matrix above.

## Delay calculation and Retry-After

After retry number `n`, the local full-jitter cap is:

```text
min(max_delay, initial_delay * backoff_multiplier ** (n - 1))
```

The actual delay is sampled uniformly from `0` through that cap. `HttpxSession` also validates
`Retry-After` delta-seconds and HTTP-date forms. When `respect_retry_after` is true, a valid server
delay replaces local jitter. An invalid value falls back to jitter.

If the server delay exceeds `max_delay`, or any chosen delay exceeds the remaining total budget,
middleware does not retry early and re-raises the current canonical exception. Setting
`respect_retry_after=False` always uses local full jitter. Backoff sleeps are cancellable.

## Business idempotency boundary

Transport retry does not prove business replay safety. HTTP method alone is insufficient. A
mutation may opt in only when every attempt uses the same `business_operation_id`, the same
semantic payload, and a target contract that persists idempotency before exposing an ambiguous
outcome.

The client's deep method snapshot keeps one invocation's payload stable across attempts, but the
SDK does not generate or store business identifiers, payload fingerprints, workflow state, outbox
state, or reconciliation state. The consuming service owns those records and must reconcile an
ambiguous remote result; retry is not reconciliation.

A request-owned database transaction must not remain open during token acquisition, a remote SDK
call, or retry backoff. Persist local intent in a short transaction, leave that transaction, make
the remote call, and use the service's established persistence/reconciliation seam for the
outcome.

See `docs/api/client.md` for construction and `docs/architecture/request-response-pipeline.md` for
the complete execution order.

See `docs/index.md`.
