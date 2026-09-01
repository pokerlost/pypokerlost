"""Canonical opt-in retry policy for PokerLost transport calls."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class PokerLostRetryPolicy:
    """Fixed bounded policy enabled explicitly for one replay-safe call."""

    max_attempts: int = field(default=3, init=False)
    initial_delay_seconds: float = field(default=0.2, init=False)
    max_delay_seconds: float = field(default=2.0, init=False)
    backoff_multiplier: float = field(default=2.0, init=False)
    retryable_status_codes: frozenset[int] = field(
        default=frozenset({408, 425, 429, 500, 502, 503, 504}),
        init=False,
    )
    respect_retry_after: bool = field(default=True, init=False)
    total_budget_seconds: float = field(default=5.0, init=False)
