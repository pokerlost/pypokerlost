# Retry

Retry is opt-in:

```python
from pypokerlost.client import PokerlostRequestOptions
from pypokerlost.middleware import PokerlostRetryPolicy

# Only for an operation whose owner guarantees that repeating the request is safe.
options = PokerlostRequestOptions(retry_policy=PokerlostRetryPolicy(), retry_safe=True)
result = await client(Method(...), options=options)
```

The immutable policy defaults to three total attempts, starts at 0.2 seconds, caps at 2 seconds,
uses a 2.0 multiplier with full jitter, and limits the logical call to five seconds. Retryable statuses
are 408, 425, 429, 500, 502, 503, and 504. Connection and timeout failures are retryable.

Constructor settings are validated before I/O: `max_attempts` is an integer from 1 to 10,
`initial_delay` and `max_delay` are finite seconds from 0 to 60 with initial delay no larger
than the cap, `backoff_multiplier` is finite from 1 to 10, and `total_budget` is finite seconds
greater than zero and at most 300. Booleans are invalid numeric settings. These limits bound
accidental retry amplification; the default status catalog stays fixed.

`retry_safe` defaults to `False` and must be a boolean. A policy alone applies its budget to one
attempt and never replays an ambiguous business effect. Set `retry_safe=True` only after the
operation owner has established idempotency or an equivalent safe replay contract. This flag
does not create an idempotency key or change the request body or headers. Existing callers that
previously supplied only a policy must explicitly attest safe replay to retain multiple attempts.

`retry_after` flows only from `PokerlostResponse` to `PokerlostAPIError` and then this middleware.
Malformed 502/503/504 responses retry by `PokerlostProtocolError.status_code`; malformed ordinary
2xx responses do not. Authentication, authorization, 409, 422, and caller cancellation propagate.

Generic retry encloses authentication so its five-second budget covers token loading, one reactive
refresh, the single replay, every transport attempt, and backoff waits. A task-local claim prevents later retry
attempts from opening a second refresh window. Transport retry does not establish business
idempotency.

The exact expired-token response may still trigger one authentication replay because services
must reject it before handler entry. Persistent refresh coordination belongs to the injected
service-owned refresher: lease, re-read shared state, CAS save, and version-checked invalidation.
The SDK contract tests exercise concurrent clients with a synthetic port; they do not certify
a production or cross-process store implementation.
