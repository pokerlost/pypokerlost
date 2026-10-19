"""Real client/application ownership and process-local signal handling."""

from __future__ import annotations

import asyncio
import signal
import subprocess
import sys
from collections.abc import AsyncIterator, Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest

from pypokerlost import PokerlostApplication, PokerlostClient
from pypokerlost.client.current_client import get_current_client
from pypokerlost.errors import PokerlostConfigurationError
from pypokerlost.lifecycle.signal_controller import SignalController

type Transport = Callable[[Callable[[httpx.Request], httpx.Response]], list[httpx.Request]]


def test_application_owns_one_client_and_unwinds_in_reverse_order(transport: Transport) -> None:
    requests = transport(lambda request: pytest.fail("Lifecycle does not send requests"))
    events: list[str] = []

    @asynccontextmanager
    async def lifecycle(application: PokerlostApplication) -> AsyncIterator[None]:
        assert application.is_running
        assert get_current_client() is application.client
        events.append("entered")
        try:
            yield
        finally:
            events.append("closed")

    async def exercise() -> None:
        client = PokerlostClient()
        application = PokerlostApplication(client, lifecycle=lifecycle)
        assert application.client is client
        assert not application.is_running
        async with application as entered:
            assert entered is client
            assert application.is_running
            with pytest.raises(PokerlostConfigurationError, match="already running"):
                await application.__aenter__()
        assert not application.is_running
        assert client.session._http_client is None
        await application.__aexit__(None, None, None)
        with pytest.raises(PokerlostConfigurationError):
            get_current_client()

    asyncio.run(exercise())
    assert events == ["entered", "closed"]
    assert requests == []


@pytest.mark.parametrize("failure", ["startup", "shutdown", "body"])
def test_application_failure_keeps_resource_cleanup_and_can_restart(
    transport: Transport, failure: str
) -> None:
    transport(lambda request: pytest.fail("Lifecycle does not send requests"))
    failed = False

    @asynccontextmanager
    async def lifecycle(application: PokerlostApplication) -> AsyncIterator[None]:
        nonlocal failed
        if not failed and failure == "startup":
            failed = True
            raise OSError("synthetic lifecycle failure")
        try:
            yield
        finally:
            if not failed and failure == "shutdown":
                failed = True
                raise OSError("synthetic lifecycle failure")

    async def exercise() -> None:
        client = PokerlostClient()
        application = PokerlostApplication(client, lifecycle=lifecycle)
        with pytest.raises(OSError, match="synthetic lifecycle failure"):
            async with application:
                if failure == "body":
                    raise OSError("synthetic lifecycle failure")
        assert not application.is_running
        assert client.session._http_client is None
        with pytest.raises(PokerlostConfigurationError):
            get_current_client()
        async with application:
            assert application.is_running

    asyncio.run(exercise())


def test_application_cancellation_during_partial_startup_closes_client(
    transport: Transport,
) -> None:
    transport(lambda request: pytest.fail("Lifecycle does not send requests"))

    async def exercise() -> None:
        entered = asyncio.Event()

        @asynccontextmanager
        async def lifecycle(application: PokerlostApplication) -> AsyncIterator[None]:
            entered.set()
            await asyncio.Event().wait()
            yield

        client = PokerlostClient()
        application = PokerlostApplication(client, lifecycle=lifecycle)
        task = asyncio.create_task(application.__aenter__())
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not application.is_running
        assert client.session._http_client is None

    asyncio.run(exercise())


def test_default_application_lifecycle_returns_entrypoint_result(transport: Transport) -> None:
    transport(lambda request: pytest.fail("Entrypoint does not send requests"))

    async def exercise() -> None:
        client = PokerlostClient()
        application = PokerlostApplication(client)

        async def entrypoint(entered: PokerlostClient) -> int:
            assert entered is client
            assert application.is_running
            return 17

        assert await application.run_async(entrypoint) == 17
        assert not application.is_running
        assert client.session._http_client is None

    asyncio.run(exercise())


def test_signal_event_keeps_the_first_signal_and_cleanup_is_repeatable() -> None:
    async def exercise() -> None:
        controller = SignalController(())
        async with controller:
            assert controller._loop is asyncio.get_running_loop()
            controller._handle_signal(signal.SIGTERM)
            controller._handle_signal(signal.SIGINT)
            assert await controller.wait() is signal.SIGTERM
        assert controller._loop is None
        assert controller._registered_signals == set()
        await controller.__aexit__(None, None, None)

    asyncio.run(exercise())


def test_worker_thread_uses_no_process_signal_registration() -> None:
    async def exercise() -> None:
        controller = SignalController()
        async with controller:
            assert controller._registered_signals == set()
            assert controller._loop is not None
        assert controller._loop is None

    with ThreadPoolExecutor(max_workers=1) as executor:
        executor.submit(asyncio.run, exercise()).result(timeout=5)


def test_unsupported_signal_registration_is_an_explicit_platform_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def exercise() -> None:
        attempted: list[signal.Signals] = []

        def unsupported(sig: signal.Signals, *args: object) -> None:
            attempted.append(sig)
            raise NotImplementedError

        monkeypatch.setattr(asyncio.get_running_loop(), "add_signal_handler", unsupported)
        async with SignalController() as controller:
            assert controller._registered_signals == set()
        assert attempted == [signal.SIGINT, signal.SIGTERM]

    asyncio.run(exercise())


PROCESS_CODE = r"""
import asyncio
import json
import os
import signal
import sys
from pypokerlost import PokerlostApplication, PokerlostClient
from pypokerlost.client.current_client import get_current_client
from pypokerlost.errors import PokerlostConfigurationError

mode = sys.argv[1]
client = PokerlostClient()
application = PokerlostApplication(client)
events = []
async def entrypoint(entered):
    assert entered is client
    assert application.is_running
    events.append("entered")
    if mode == "normal":
        return 17
    if mode == "error":
        raise ValueError("synthetic entrypoint failure")
    if mode != "callerCancel":
        asyncio.get_running_loop().call_soon(os.kill, os.getpid(), signal.SIGTERM)
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        events.append("cancelled")
        if mode == "suppress":
            return 9
        raise
    finally:
        events.append("entrypoint closed")
if mode == "callerCancel":
    async def cancel_caller():
        task = asyncio.create_task(application._run_with_signals(entrypoint))
        while "entered" not in events:
            await asyncio.sleep(0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            events.append("caller cancelled")
        else:
            raise AssertionError("Caller cancellation must propagate")
    asyncio.run(cancel_caller())
    result = None
elif mode == "error":
    try:
        application.run(entrypoint)
    except ValueError as error:
        assert str(error) == "synthetic entrypoint failure"
        result = "expected error"
    else:
        raise AssertionError("Entrypoint failure must propagate")
else:
    result = application.run(entrypoint)
assert not application.is_running
assert client.session._http_client is None
try:
    get_current_client()
except PokerlostConfigurationError:
    pass
else:
    raise AssertionError("Current client leaked")
print(json.dumps({"result": result, "events": events}))
"""


@pytest.mark.parametrize("mode", ["normal", "signal", "suppress", "error", "callerCancel"])
def test_process_signals_and_entrypoint_outcomes(tmp_path: Path, mode: str) -> None:
    import json

    result = subprocess.run(
        [sys.executable, "-c", PROCESS_CODE, mode],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert observed["result"] == (
        17 if mode == "normal" else "expected error" if mode == "error" else None
    )
    assert observed["events"][0] == "entered"
    if mode in {"signal", "suppress", "callerCancel"}:
        assert "cancelled" in observed["events"]
        assert "entrypoint closed" in observed["events"]
    if mode == "callerCancel":
        assert "caller cancelled" in observed["events"]
