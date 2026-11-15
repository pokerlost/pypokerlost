"""Canonical opt-in Pokerlost retry middleware and policy."""

from __future__ import annotations

import asyncio
import math
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
    """Immutable bounded retry settings with the established safe defaults."""

    max_attempts: int = 3
    initial_delay: float = 0.2
    max_delay: float = 2.0
    backoff_multiplier: float = 2.0
    total_budget: float = 5.0
    retryable_statuses: frozenset[int] = field(
        default=frozenset({408, 425, 429, 500, 502, 503, 504}),
        init=False,
    )

    def __post_init__(self) -> None:
        if type(self.max_attempts) is not int or not 1 <= self.max_attempts <= 10:
            raise ValueError("max_attempts must be an integer from 1 to 10")
        for name, lower, upper in (
            ("initial_delay", 0.0, 60.0),
            ("max_delay", 0.0, 60.0),
            ("backoff_multiplier", 1.0, 10.0),
            ("total_budget", 0.0, 300.0),
        ):
            value = getattr(self, name)
            if (
                type(value) is bool
                or not isinstance(value, int | float)
                or not lower <= value <= upper
                or not math.isfinite(value)
                or (name == "total_budget" and value == 0)
            ):
                raise ValueError(f"{name} must be finite and within its supported range")
        if self.initial_delay > self.max_delay:
            raise ValueError("initial_delay must not exceed max_delay")


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
                        or not call.options.retry_safe
                        or attempt_number == policy.max_attempts
                    ):
                        raise
                    delay = self._next_delay(error, policy, retry_number=attempt_number)
                    remaining = policy.total_budget - (self._clock() - started_at)
                    if remaining <= 0.0 or delay >= remaining:
                        raise
                    try:
                        async with asyncio.timeout(remaining):
                            await self._sleep(delay)
                    except TimeoutError:
                        raise error from None
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
