from __future__ import annotations

import asyncio
import signal
import threading
from types import TracebackType
from typing import Self

DEFAULT_SHUTDOWN_SIGNALS: tuple[signal.Signals, ...] = (
    signal.SIGINT,
    signal.SIGTERM,
)


class SignalController:
    """Temporarily translate supported process signals into an async event."""

    def __init__(
        self,
        shutdown_signals: tuple[signal.Signals, ...] = DEFAULT_SHUTDOWN_SIGNALS,
    ) -> None:
        self._shutdown_signals = shutdown_signals
        self._loop: asyncio.AbstractEventLoop | None = None
        self._event = asyncio.Event()
        self._registered_signals: set[signal.Signals] = set()
        self._received_signal: signal.Signals | None = None

    async def __aenter__(self) -> Self:
        loop = asyncio.get_running_loop()
        self._loop = loop
        if threading.current_thread() is not threading.main_thread():
            return self

        for shutdown_signal in self._shutdown_signals:
            try:
                loop.add_signal_handler(
                    shutdown_signal,
                    self._handle_signal,
                    shutdown_signal,
                )
            except NotImplementedError:
                continue
            self._registered_signals.add(shutdown_signal)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        loop = self._loop
        try:
            if loop is not None:
                for registered_signal in self._registered_signals:
                    loop.remove_signal_handler(registered_signal)
        finally:
            self._registered_signals.clear()
            self._loop = None

    async def wait(self) -> signal.Signals:
        await self._event.wait()
        received_signal = self._received_signal
        if received_signal is None:
            raise RuntimeError("Shutdown event was set without a signal")
        return received_signal

    def _handle_signal(self, received_signal: signal.Signals) -> None:
        if self._received_signal is None:
            self._received_signal = received_signal
            self._event.set()
