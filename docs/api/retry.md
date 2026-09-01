# Transport retry

Retry is one flat middleware with one immutable policy.

## Opt-in

```python
from pypokerlost import PokerlostRequestOptions
from pypokerlost.middleware import PokerlostRetryPolicy

options = PokerlostRequestOptions(
    retry_policy=PokerlostRetryPolicy(),
)
result = await client(method, options=options)
```

When `retry_policy` is `None`, the outer middleware makes exactly one downstream call.

## Fixed policy

```text
attempts: 3, including the first
initial delay cap: 0.2 seconds
maximum delay cap: 2.0 seconds
multiplier: 2.0
jitter: full
logical-call budget: 5.0 seconds
retryable statuses: 408, 425, 429, 500, 502, 503, 504
```

Connection and timeout errors are retryable. `PokerlostAPIError` is retryable only for a listed
status. Authentication, authorization, protocol, configuration, and cancellation failures
propagate immediately.

## Body retry delay

`PokerlostResponse.retry_after` is optional finite non-negative seconds. A failed envelope carries
it into `PokerlostAPIError.retry_after`. When present it replaces computed jitter.

The middleware retries only when the complete delay fits the remaining logical-call budget. It
does not sleep early or partially when it cannot fit. Invalid delay values are protocol failures
and are not retried.

Exhaustion re-raises the last canonical connection, timeout, or API error. No wrapper exhaustion
error is introduced.

## Business boundary

Transport retry does not establish mutation safety. A replayable mutation must retain the same
operation, business operation ID, semantic payload, and target, and the target contract must make
that replay safe. The middleware never generates or changes a business operation ID.

Database transactions must not span remote attempts or delays.

See `docs/architecture/request-response-pipeline.md` and `docs/index.md`.
