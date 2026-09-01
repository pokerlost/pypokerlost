"""Pokerlost application lifecycle orchestration."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from types import TracebackType

from pypokerlost.client import PokerlostClient
from pypokerlost.errors import PokerlostConfigurationError
from pypokerlost.lifecycle import (
    PokerlostApplicationLifecycle,
    default_pokerlost_application_lifecycle,
)
from pypokerlost.lifecycle.signal_controller import SignalController


class PokerlostApplication:
    """Coordinate automatic lifecycle for one Pokerlost client."""

    def __init__(
        self,
        client: PokerlostClient,
        *,
        lifecycle: PokerlostApplicationLifecycle = default_pokerlost_application_lifecycle,
    ) -> None:
        self._client = client
        self._lifecycle = lifecycle
        self._is_running = False
        self._context_stack: AsyncExitStack | None = None

    @property
    def client(self) -> PokerlostClient:
        return self._client

    @property
    def is_running(self) -> bool:
        return self._is_running

    async def __aenter__(self) -> PokerlostClient:
        if self._is_running:
            raise PokerlostConfigurationError("PokerlostApplication is already running")
        self._is_running = True
        try:
            async with AsyncExitStack() as stack:
                client = await stack.enter_async_context(self._client)
                await stack.enter_async_context(self._lifecycle(self))
                self._context_stack = stack.pop_all()
        except BaseException:
            self._context_stack = None
            self._is_running = False
            raise
        return client

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        stack = self._context_stack
        self._context_stack = None
        self._is_running = False
        if stack is not None:
            await stack.aclose()

    async def run_async[ResultT](
        self,
        entrypoint: Callable[[PokerlostClient], Awaitable[ResultT]],
    ) -> ResultT:
        async with self as client:
            return await entrypoint(client)

    def run[ResultT](
        self,
        entrypoint: Callable[[PokerlostClient], Awaitable[ResultT]],
    ) -> ResultT | None:
        return asyncio.run(self._run_with_signals(entrypoint))

    async def _run_with_signals[ResultT](
        self,
        entrypoint: Callable[[PokerlostClient], Awaitable[ResultT]],
    ) -> ResultT | None:
        async with SignalController() as signals:
            entrypoint_task = asyncio.create_task(self.run_async(entrypoint))
            signal_task = asyncio.create_task(signals.wait())
            try:
                completed, _ = await asyncio.wait(
                    (entrypoint_task, signal_task),
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if entrypoint_task in completed:
                    signal_task.cancel()
                    await asyncio.gather(signal_task, return_exceptions=True)
                    return await entrypoint_task
                await signal_task
                entrypoint_task.cancel()
                try:
                    await entrypoint_task
                except asyncio.CancelledError:
                    return None
                return None
            finally:
                if not entrypoint_task.done():
                    entrypoint_task.cancel()
                if not signal_task.done():
                    signal_task.cancel()
                await asyncio.gather(
                    entrypoint_task,
                    signal_task,
                    return_exceptions=True,
                )
