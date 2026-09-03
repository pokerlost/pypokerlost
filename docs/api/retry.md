# Retry

Retry is opt-in:

```python
from pypokerlost.client import PokerlostRequestOptions
from pypokerlost.middleware import PokerlostRetryPolicy

options = PokerlostRequestOptions(retry_policy=PokerlostRetryPolicy())
result = await client(Method(...), options=options)
```

The immutable policy permits three total attempts, starts at 0.2 seconds, caps at 2 seconds, uses a
2.0 multiplier with full jitter, and limits the logical call to five seconds. Retryable statuses
are 408, 425, 429, 500, 502, 503, and 504. Connection and timeout failures are retryable.

`retry_after` flows only from `PokerlostResponse` to `PokerlostAPIError` and then this middleware.
Malformed 502/503/504 responses retry by `PokerlostProtocolError.status_code`; malformed ordinary
2xx responses do not. Authentication, authorization, 409, 422, and caller cancellation propagate.

Generic retry encloses authentication so its five-second budget covers token loading, one reactive
refresh, the single replay, and every transport attempt. A task-local claim prevents later retry
attempts from opening a second refresh window. Transport retry does not establish business
idempotency.
