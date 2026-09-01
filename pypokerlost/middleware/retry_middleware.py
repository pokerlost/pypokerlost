"""Explicit bounded retry middleware for replay-safe API calls."""

from __future__ import annotations

import asyncio
from random import uniform
from time import monotonic

from pypokerlost.client.retry import RetryPolicy
from pypokerlost.exceptions import (
    ClientConnectionError,
    ClientDecodeError,
    ClientTimeoutError,
    PokerlostAPIError,
)

from .base_middleware import APIMiddleware, APIMiddlewareCallNext
from .context import APIMiddlewareContext

type _RetryableError = (
    ClientConnectionError | ClientTimeoutError | PokerlostAPIError | ClientDecodeError
)


class RetryMiddleware(APIMiddleware):
    """Repeat only failures enabled by an explicit per-call policy."""

    async def __call__[ResultT](
        self,
        call_next: APIMiddlewareCallNext[ResultT],
        context: APIMiddlewareContext,
    ) -> ResultT:
        policy = context.options.retry
        if policy is None or policy.max_attempts == 1:
            return await call_next()

        attempt_options = context.options.model_copy(update={"retry": None})
        started_at = monotonic()
        for attempt in range(1, policy.max_attempts + 1):
            try:
                return await call_next(options=attempt_options)
            except (
                ClientConnectionError,
                ClientTimeoutError,
                PokerlostAPIError,
                ClientDecodeError,
            ) as error:
                if not self._is_retryable(error, policy) or attempt == policy.max_attempts:
                    raise

                delay = self._next_delay(
                    error,
                    policy,
                    retry_number=attempt,
                    elapsed=monotonic() - started_at,
                )
                if delay is None:
                    raise
                await asyncio.sleep(delay)

        raise AssertionError("Retry attempt loop completed without a result")

    def _is_retryable(
        self,
        error: _RetryableError,
        policy: RetryPolicy,
    ) -> bool:
        if isinstance(error, ClientConnectionError | ClientTimeoutError):
            return True
        return error.status_code in policy.retryable_statuses

    def _next_delay(
        self,
        error: _RetryableError,
        policy: RetryPolicy,
        *,
        retry_number: int,
        elapsed: float,
    ) -> float | None:
        retry_after = (
            error.retry_after if isinstance(error, PokerlostAPIError | ClientDecodeError) else None
        )
        if policy.respect_retry_after and retry_after is not None:
            if retry_after > policy.max_delay:
                return None
            delay = retry_after
        else:
            cap = min(
                policy.max_delay,
                policy.initial_delay * policy.backoff_multiplier ** (retry_number - 1),
            )
            delay = uniform(0.0, cap)

        if policy.total_budget is None:
            return delay
        remaining_budget = policy.total_budget - elapsed
        if remaining_budget <= 0.0 or delay > remaining_budget:
            return None
        return delay
