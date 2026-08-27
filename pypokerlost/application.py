from __future__ import annotations

import asyncio
import signal
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from types import TracebackType

from pypokerlost.client import Client
from pypokerlost.exceptions import ApplicationStateError
from pypokerlost.lifecycle import ApplicationLifecycle, default_application_lifecycle
from pypokerlost.lifecycle.signal_controller import SignalController


class Application:
    """Coordinate automatic lifecycle for one client."""

    def __init__(
        self,
        client: Client,
        *,
        lifecycle: ApplicationLifecycle = default_application_lifecycle,
    ) -> None:
        self._client = client
        self._lifecycle = lifecycle
        self._is_running = False
        self._context_stack: AsyncExitStack | None = None

    @property
    def client(self) -> Client:
        return self._client

    @property
    def is_running(self) -> bool:
        return self._is_running

    async def __aenter__(self) -> Client:
        if self._is_running:
            raise ApplicationStateError
        self._is_running = True

        try:
            async with AsyncExitStack() as entry_stack:
                client = await entry_stack.enter_async_context(self._client)
                await entry_stack.enter_async_context(self._lifecycle(self))
                self._context_stack = entry_stack.pop_all()
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
        context_stack = self._context_stack
        if context_stack is None:
            return
        try:
            try:
                async with context_stack:
                    if exc_value is not None:
                        raise exc_value.with_traceback(traceback)
            except BaseException as propagated_error:
                if propagated_error is not exc_value:
                    raise
        finally:
            self._context_stack = None
            self._is_running = False

    async def run_async[ResultT](
        self,
        entrypoint: Callable[[Client], Awaitable[ResultT]],
    ) -> ResultT:
        async with self as client:
            return await entrypoint(client)

    def run[ResultT](
        self,
        entrypoint: Callable[[Client], Awaitable[ResultT]],
    ) -> ResultT | None:
        return asyncio.run(self._run_with_signals(entrypoint))

    async def _run_with_signals[ResultT](
        self,
        entrypoint: Callable[[Client], Awaitable[ResultT]],
    ) -> ResultT | None:
        async with SignalController() as signals:
            entrypoint_task: asyncio.Task[ResultT] = asyncio.create_task(self.run_async(entrypoint))
            signal_task: asyncio.Task[signal.Signals] = asyncio.create_task(signals.wait())

            try:
                completed_tasks, _ = await asyncio.wait(
                    (entrypoint_task, signal_task),
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if entrypoint_task in completed_tasks:
                    signal_task.cancel()
                    await asyncio.gather(signal_task, return_exceptions=True)
                    return await entrypoint_task

                await signal_task
                was_already_cancelling = entrypoint_task.cancelling() > 0
                cancellation_requested = entrypoint_task.cancel()
                try:
                    await entrypoint_task
                except asyncio.CancelledError:
                    if was_already_cancelling or not cancellation_requested:
                        raise
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
