"""Canonical opt-in Pokerlost retry middleware and policy."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from random import random
from time import monotonic

from pypokerlost.errors import (
    PokerlostAPIError,
    PokerlostAuthenticationError,
    PokerlostAuthorizationError,
    PokerlostConnectionError,
    PokerlostProtocolError,
    PokerlostTimeoutError,
)

from ._call import PokerlostCall, reactive_refresh_scope
from .base import PokerlostCallNext

type _RetryableError = (
    PokerlostConnectionError | PokerlostTimeoutError | PokerlostProtocolError | PokerlostAPIError
)


@dataclass(frozen=True, slots=True)
class PokerlostRetryPolicy:
    """One immutable fixed policy shared by every Pokerlost service."""

    max_attempts: int = field(default=3, init=False)
    initial_delay: float = field(default=0.2, init=False)
    max_delay: float = field(default=2.0, init=False)
    backoff_multiplier: float = field(default=2.0, init=False)
    total_budget: float = field(default=5.0, init=False)
    retryable_statuses: frozenset[int] = field(
        default=frozenset({408, 425, 429, 500, 502, 503, 504}),
        init=False,
    )


class PokerlostRetryMiddleware:
    """Retry only failures enabled by the call's explicit policy."""

    def __init__(
        self,
        *,
        clock: Callable[..., float] = monotonic,
        jitter: Callable[..., float] = random,
        sleep: Callable[..., Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._clock = clock
        self._jitter = jitter
        self._sleep = sleep

    async def __call__[ResultT](
        self,
        call: PokerlostCall,
        call_next: PokerlostCallNext[ResultT],
        /,
    ) -> ResultT:
        with reactive_refresh_scope():
            policy = call.options.retry_policy
            if policy is None:
                return await call_next(call)

            started_at = self._clock()
            last_error: _RetryableError | None = None
            for attempt_number in range(1, policy.max_attempts + 1):
                remaining = policy.total_budget - (self._clock() - started_at)
                if remaining <= 0.0:
                    if last_error is not None:
                        raise last_error from None
                    raise PokerlostTimeoutError(operation=str(call.method.operation))
                attempt_timed_out = False
                try:
                    async with asyncio.timeout(remaining):
                        return await call_next(call)
                except asyncio.CancelledError:
                    raise
                except TimeoutError:
                    attempt_timed_out = True
                except (
                    PokerlostConnectionError,
                    PokerlostTimeoutError,
                    PokerlostProtocolError,
                    PokerlostAPIError,
                ) as error:
                    last_error = error
                    if (
                        not self._is_retryable(error, policy)
                        or attempt_number == policy.max_attempts
                    ):
                        raise
                    delay = self._next_delay(error, policy, retry_number=attempt_number)
                    remaining = policy.total_budget - (self._clock() - started_at)
                    if remaining <= 0.0 or delay >= remaining:
                        raise
                    await self._sleep(delay)
                if attempt_timed_out:
                    if last_error is not None:
                        raise last_error from None
                    raise PokerlostTimeoutError(operation=str(call.method.operation))

            if last_error is not None:
                raise last_error
            raise PokerlostTimeoutError(operation=str(call.method.operation))

    @staticmethod
    def _is_retryable(error: _RetryableError, policy: PokerlostRetryPolicy) -> bool:
        if isinstance(error, PokerlostAuthenticationError | PokerlostAuthorizationError):
            return False
        if isinstance(error, PokerlostConnectionError | PokerlostTimeoutError):
            return True
        return error.status_code in policy.retryable_statuses

    def _next_delay(
        self,
        error: _RetryableError,
        policy: PokerlostRetryPolicy,
        *,
        retry_number: int,
    ) -> float:
        if isinstance(error, PokerlostAPIError) and error.retry_after is not None:
            return error.retry_after
        cap = min(
            policy.max_delay,
            policy.initial_delay * policy.backoff_multiplier ** (retry_number - 1),
        )
        return self._jitter() * cap
