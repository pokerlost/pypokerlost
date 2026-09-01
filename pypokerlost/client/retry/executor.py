"""Single canonical retry execution path for PokerLost transport calls."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from random import uniform
from time import monotonic

from pypokerlost.exceptions import (
    ClientConnectionError,
    ClientDecodeError,
    ClientTimeoutError,
    PokerlostAPIError,
    PokerlostProtocolError,
)

from .retry_policy import PokerLostRetryPolicy

type _RetryableError = (
    ClientConnectionError
    | ClientTimeoutError
    | PokerlostAPIError
    | PokerlostProtocolError
    | ClientDecodeError
)


async def execute_with_retry[ResultT](
    attempt: Callable[[], Awaitable[ResultT]],
    policy: PokerLostRetryPolicy,
    budget_timeout_error: ClientTimeoutError,
    /,
) -> ResultT:
    """Execute one logical call under the canonical fixed transport policy."""
    try:
        try:
            async with asyncio.timeout(policy.total_budget_seconds):
                started_at = monotonic()
                for attempt_number in range(1, policy.max_attempts + 1):
                    try:
                        return await attempt()
                    except (
                        ClientConnectionError,
                        ClientTimeoutError,
                        PokerlostAPIError,
                        PokerlostProtocolError,
                        ClientDecodeError,
                    ) as error:
                        if (
                            not _is_retryable(error, policy)
                            or attempt_number == policy.max_attempts
                        ):
                            raise

                        delay = _next_delay(
                            error,
                            policy,
                            retry_number=attempt_number,
                            elapsed_seconds=monotonic() - started_at,
                        )
                        if delay is None:
                            raise
                        await asyncio.sleep(delay)

                raise AssertionError("Retry attempt loop completed without a result")
        except TimeoutError:
            raise budget_timeout_error from None
    finally:
        attempt = None  # type: ignore[assignment]
        budget_timeout_error = None  # type: ignore[assignment]


def _is_retryable(
    error: _RetryableError,
    policy: PokerLostRetryPolicy,
) -> bool:
    if isinstance(error, ClientConnectionError | ClientTimeoutError):
        return True
    return error.status_code in policy.retryable_status_codes


def _next_delay(
    error: _RetryableError,
    policy: PokerLostRetryPolicy,
    *,
    retry_number: int,
    elapsed_seconds: float,
) -> float | None:
    retry_after = (
        error.retry_after
        if isinstance(error, PokerlostAPIError | PokerlostProtocolError | ClientDecodeError)
        else None
    )
    if policy.respect_retry_after and retry_after is not None:
        delay = retry_after
    else:
        cap = min(
            policy.max_delay_seconds,
            policy.initial_delay_seconds * policy.backoff_multiplier ** (retry_number - 1),
        )
        delay = uniform(0.0, cap)

    remaining_budget = policy.total_budget_seconds - elapsed_seconds
    if remaining_budget <= 0.0 or delay > remaining_budget:
        return None
    return delay
