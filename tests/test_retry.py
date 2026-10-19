"""Bounded retry budgets, error classification, cancellation and refresh ownership."""

from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError, replace

import pytest

from pypokerlost.client import PokerlostRequestOptions
from pypokerlost.errors import (
    PokerlostAPIError,
    PokerlostAuthenticationError,
    PokerlostAuthorizationError,
    PokerlostConnectionError,
    PokerlostProtocolError,
    PokerlostTimeoutError,
)
from pypokerlost.middleware import PokerlostRetryMiddleware, PokerlostRetryPolicy
from pypokerlost.middleware._call import (
    PokerlostCall,
    claim_reactive_refresh,
    reactive_refresh_scope,
)


def api_error(status: int, *, retry_after: float | None = None) -> PokerlostAPIError:
    return PokerlostAPIError(
        operation="technicalProbe",
        status_code=status,
        error="TECHNICAL_ERROR",
        error_message=None,
        retry_after=retry_after,
    )


def retry_call(call: PokerlostCall) -> PokerlostCall:
    return replace(call, options=PokerlostRequestOptions(PokerlostRetryPolicy()))


def test_retry_policy_is_fixed_and_request_options_are_typed() -> None:
    policy = PokerlostRetryPolicy()
    assert (policy.max_attempts, policy.total_budget) == (3, 5.0)
    assert (policy.initial_delay, policy.max_delay, policy.backoff_multiplier) == (0.2, 2.0, 2.0)
    assert policy.retryable_statuses == frozenset({408, 425, 429, 500, 502, 503, 504})
    with pytest.raises(TypeError):
        PokerlostRetryPolicy(max_attempts=4)
    with pytest.raises(FrozenInstanceError):
        policy.max_attempts = 4
    assert PokerlostRequestOptions(policy).retry_policy is policy
    with pytest.raises(TypeError, match="retry_policy"):
        PokerlostRequestOptions(object())


def test_no_opt_in_means_one_attempt_without_sleep(call: PokerlostCall) -> None:
    calls: list[PokerlostCall] = []
    error = PokerlostConnectionError(operation="technicalProbe")

    async def fail(current: PokerlostCall) -> int:
        calls.append(current)
        raise error

    async def no_sleep(delay: float) -> None:
        pytest.fail("No retry was requested")

    async def exercise() -> None:
        with pytest.raises(PokerlostConnectionError) as caught:
            await PokerlostRetryMiddleware(sleep=no_sleep)(call, fail)
        assert caught.value is error

    asyncio.run(exercise())
    assert calls == [call]


@pytest.mark.parametrize(
    "error",
    [
        PokerlostConnectionError(operation="technicalProbe"),
        PokerlostTimeoutError(operation="technicalProbe"),
        PokerlostProtocolError(operation="technicalProbe", status_code=502),
        api_error(429),
    ],
)
def test_retryable_errors_back_off_and_return_the_typed_result(
    call: PokerlostCall, error: Exception
) -> None:
    call = retry_call(call)
    attempts: list[PokerlostCall] = []
    delays: list[float] = []

    async def execute(current: PokerlostCall) -> int:
        attempts.append(current)
        if len(attempts) < 3:
            raise error
        return 17

    async def sleep(delay: float) -> None:
        delays.append(delay)

    async def exercise() -> None:
        retry = PokerlostRetryMiddleware(clock=lambda: 0.0, jitter=lambda: 0.5, sleep=sleep)
        assert await retry(call, execute) == 17

    asyncio.run(exercise())
    assert attempts == [call] * 3
    assert delays == [0.1, 0.2]


@pytest.mark.parametrize("status", [408, 425, 429, 500, 502, 503, 504])
def test_attempt_limit_preserves_the_last_error(call: PokerlostCall, status: int) -> None:
    attempts = 0
    error = api_error(status)

    async def fail(current: PokerlostCall) -> int:
        nonlocal attempts
        attempts += 1
        raise error

    async def sleep(delay: float) -> None:
        assert delay == 0.0

    async def exercise() -> None:
        retry = PokerlostRetryMiddleware(clock=lambda: 0.0, jitter=lambda: 0.0, sleep=sleep)
        with pytest.raises(PokerlostAPIError) as caught:
            await retry(retry_call(call), fail)
        assert caught.value is error

    asyncio.run(exercise())
    assert attempts == 3


@pytest.mark.parametrize(
    "error",
    [
        api_error(409),
        api_error(422),
        PokerlostProtocolError(operation="technicalProbe", status_code=200),
        PokerlostAuthenticationError(
            operation="technicalProbe",
            status_code=503,
            error="AUTH",
            error_message=None,
            retry_after=None,
        ),
        PokerlostAuthorizationError(
            operation="technicalProbe",
            status_code=503,
            error="SCOPE",
            error_message=None,
            retry_after=None,
        ),
        RuntimeError("consumer error"),
    ],
)
def test_permanent_failures_are_never_retried(call: PokerlostCall, error: Exception) -> None:
    attempts = 0

    async def fail(current: PokerlostCall) -> int:
        nonlocal attempts
        attempts += 1
        raise error

    async def no_sleep(delay: float) -> None:
        pytest.fail("A permanent failure must not sleep")

    async def exercise() -> None:
        with pytest.raises(type(error)) as caught:
            await PokerlostRetryMiddleware(sleep=no_sleep)(retry_call(call), fail)
        assert caught.value is error

    asyncio.run(exercise())
    assert attempts == 1


def test_body_retry_after_takes_precedence_over_jitter(call: PokerlostCall) -> None:
    attempts = 0
    delays: list[float] = []

    async def execute(current: PokerlostCall) -> int:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise api_error(429, retry_after=0.75)
        return 11

    async def sleep(delay: float) -> None:
        delays.append(delay)

    async def exercise() -> None:
        retry = PokerlostRetryMiddleware(
            clock=lambda: 0.0,
            jitter=lambda: pytest.fail("retry_after takes precedence"),
            sleep=sleep,
        )
        assert await retry(retry_call(call), execute) == 11

    asyncio.run(exercise())
    assert delays == [0.75]


@pytest.mark.parametrize("times", [[0.0, 0.0, 5.1], [0.0, 0.0, 4.9], [0.0, 0.0, 0.0, 5.1]])
def test_budget_exhaustion_preserves_previous_failure(
    call: PokerlostCall, times: list[float]
) -> None:
    clock = iter(times)
    error = PokerlostConnectionError(operation="technicalProbe")
    attempts = 0
    delays: list[float] = []

    async def fail(current: PokerlostCall) -> int:
        nonlocal attempts
        attempts += 1
        raise error

    async def sleep(delay: float) -> None:
        delays.append(delay)

    async def exercise() -> None:
        retry = PokerlostRetryMiddleware(clock=lambda: next(clock), jitter=lambda: 1.0, sleep=sleep)
        with pytest.raises(PokerlostConnectionError) as caught:
            await retry(retry_call(call), fail)
        assert caught.value is error

    asyncio.run(exercise())
    assert attempts == 1
    assert delays == ([0.2] if len(times) == 4 else [])


def test_exhausted_budget_prevents_the_first_io(call: PokerlostCall) -> None:
    clock = iter([0.0, 5.1])

    async def forbidden(current: PokerlostCall) -> int:
        pytest.fail("Budget expired before I/O")

    async def exercise() -> None:
        with pytest.raises(PokerlostTimeoutError):
            await PokerlostRetryMiddleware(clock=lambda: next(clock))(retry_call(call), forbidden)

    asyncio.run(exercise())


@pytest.mark.parametrize("previous_failure", [False, True])
def test_async_budget_cancels_a_stalled_attempt(
    call: PokerlostCall, previous_failure: bool
) -> None:
    clock = iter([0.0, 0.0, 0.0, 4.999] if previous_failure else [0.0, 4.999])
    attempts = 0
    cancelled: list[int] = []
    original = PokerlostConnectionError(operation="technicalProbe")

    async def execute(current: PokerlostCall) -> int:
        nonlocal attempts
        attempts += 1
        if previous_failure and attempts == 1:
            raise original
        try:
            await asyncio.Event().wait()
            pytest.fail("Stalled attempt must be cancelled")
        finally:
            cancelled.append(attempts)

    async def sleep(delay: float) -> None:
        assert delay == 0.0

    async def exercise() -> None:
        retry = PokerlostRetryMiddleware(clock=lambda: next(clock), jitter=lambda: 0.0, sleep=sleep)
        expected = PokerlostConnectionError if previous_failure else PokerlostTimeoutError
        with pytest.raises(expected) as error:
            await retry(retry_call(call), execute)
        if previous_failure:
            assert error.value is original

    asyncio.run(exercise())
    assert cancelled == [2 if previous_failure else 1]


def test_caller_cancellation_is_immediate(call: PokerlostCall) -> None:
    async def cancel(current: PokerlostCall) -> int:
        raise asyncio.CancelledError

    async def exercise() -> None:
        with pytest.raises(asyncio.CancelledError):
            await PokerlostRetryMiddleware()(retry_call(call), cancel)

    asyncio.run(exercise())


def test_backoff_cap_remains_bounded() -> None:
    retry = PokerlostRetryMiddleware(jitter=lambda: 0.5)
    policy = PokerlostRetryPolicy()
    error = PokerlostConnectionError(operation="technicalProbe")
    assert retry._next_delay(error, policy, retry_number=1) == 0.1
    assert retry._next_delay(error, policy, retry_number=2) == 0.2
    assert retry._next_delay(error, policy, retry_number=10) == 1.0


def test_refresh_claims_are_nested_and_task_local() -> None:
    with pytest.raises(RuntimeError, match="not initialized"):
        claim_reactive_refresh()
    with reactive_refresh_scope():
        assert claim_reactive_refresh() is True
        with reactive_refresh_scope():
            assert claim_reactive_refresh() is True
            assert claim_reactive_refresh() is False
        assert claim_reactive_refresh() is False

    async def one_call() -> tuple[bool, bool]:
        with reactive_refresh_scope():
            first = claim_reactive_refresh()
            await asyncio.sleep(0)
            return first, claim_reactive_refresh()

    async def exercise() -> None:
        assert await asyncio.gather(one_call(), one_call()) == [(True, False), (True, False)]

    asyncio.run(exercise())
    with pytest.raises(RuntimeError, match="not initialized"):
        claim_reactive_refresh()
