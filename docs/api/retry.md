# Transport retry

PokerLost services use one immutable SDK policy:

```python
from pypokerlost.client.request import RequestOptions
from pypokerlost.client.retry import PokerLostRetryPolicy

options = RequestOptions(retry=PokerLostRetryPolicy())
result = await client(method, options=options)
```

Retry is disabled when `RequestOptions.retry` is `None`. The policy constructor has no configuration
arguments and has these fixed values:

```text
max attempts: 3, including the first attempt
initial full-jitter cap: 0.2 seconds
maximum local cap: 2.0 seconds
backoff multiplier: 2.0
retryable statuses: 408, 425, 429, 500, 502, 503, 504
respect Retry-After: yes
logical-call budget: 5.0 seconds
```

The client retries connection and timeout failures and canonical response/protocol/decode errors
that carry a listed status. Other status codes, local request failures, ordinary decode failures,
and caller cancellation propagate immediately. A valid `Retry-After` delta or HTTP date is used
only when it fits the remaining fixed budget. Exhaustion preserves the final canonical exception.

The delay after retry number `n` is uniformly sampled from zero through:

```text
min(2.0, 0.2 * 2.0 ** (n - 1))
```

Transport retry does not make a mutation replay-safe. A service opts in only when the target
contract guarantees the same business operation identifier, semantic payload, and target
operation can be replayed. The SDK never creates idempotency or workflow state, and a database
transaction must not remain open during remote I/O or retry delay.

See `docs/architecture/request-response-pipeline.md` for the execution path.

See `docs/index.md`.
