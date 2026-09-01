"""Canonical opt-in Pokerlost retry middleware and policy."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from random import random
from time import monotonic
from typing import cast

from pypokerlost.errors import (
    PokerlostAPIError,
    PokerlostAuthenticationError,
    PokerlostAuthorizationError,
    PokerlostConnectionError,
    PokerlostTimeoutError,
)

from .base import PokerlostCallNext, PokerlostMiddlewareRequest


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
        request: PokerlostMiddlewareRequest,
        call_next: PokerlostCallNext[ResultT],
        /,
    ) -> ResultT:
        last_error: PokerlostConnectionError | PokerlostTimeoutError | PokerlostAPIError | None = (
            None
        )
        try:
            policy = request.options.retry_policy
            if policy is None:
                return await call_next(request)

            started_at = self._clock()
            for attempt_number in range(1, policy.max_attempts + 1):
                remaining = policy.total_budget - (self._clock() - started_at)
                if remaining <= 0.0:
                    if last_error is not None:
                        raise last_error from None
                    raise PokerlostTimeoutError(operation=request.method.operation)
                try:
                    async with asyncio.timeout(remaining):
                        return await call_next(request)
                except asyncio.CancelledError:
                    raise
                except TimeoutError:
                    if last_error is not None:
                        raise last_error from None
                    raise PokerlostTimeoutError(operation=request.method.operation) from None
                except (
                    PokerlostConnectionError,
                    PokerlostTimeoutError,
                    PokerlostAPIError,
                ) as error:
                    last_error = error
                    if not self._is_retryable(error, policy):
                        raise
                    if attempt_number == policy.max_attempts:
                        raise
                    delay = self._next_delay(error, policy, retry_number=attempt_number)
                    remaining = policy.total_budget - (self._clock() - started_at)
                    if remaining <= 0.0 or delay >= remaining:
                        raise
                    await self._sleep(delay)

            if last_error is not None:
                raise last_error
            raise PokerlostTimeoutError(operation=request.method.operation)
        finally:
            request = cast("PokerlostMiddlewareRequest", None)
            call_next = cast("PokerlostCallNext[ResultT]", None)
            last_error = None

    def _is_retryable(
        self,
        error: PokerlostConnectionError | PokerlostTimeoutError | PokerlostAPIError,
        policy: PokerlostRetryPolicy,
    ) -> bool:
        if isinstance(error, PokerlostAuthenticationError | PokerlostAuthorizationError):
            return False
        if isinstance(error, PokerlostConnectionError | PokerlostTimeoutError):
            return True
        return error.status_code in policy.retryable_statuses

    def _next_delay(
        self,
        error: PokerlostConnectionError | PokerlostTimeoutError | PokerlostAPIError,
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
