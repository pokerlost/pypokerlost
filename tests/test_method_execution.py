from __future__ import annotations

import asyncio

import pytest
from pydantic import Field, ValidationError

from pypokerlost import Client, ClientContextError, ResponseDecodeError
from pypokerlost.transport.transport_response import TransportResponse
from tests.helpers import (
    CountingMethod,
    DummyMethod,
    DummyResult,
    FakeTransport,
    success_response,
)


@pytest.mark.asyncio
async def test_make_request_returns_typed_parsed_result() -> None:
    transport = FakeTransport(response=success_response("explicit"))
    client = Client(base_url="https://example.test", transport=transport)

    result = await client.make_request(DummyMethod(request_value="request"))

    assert result == DummyResult(value="explicit")
    assert transport.execute_calls[0][1] == "tests.echo"


@pytest.mark.asyncio
async def test_callable_client_delegates_to_request_execution() -> None:
    transport = FakeTransport(response=success_response("callable"))
    client = Client(base_url="https://example.test", transport=transport)
    method = DummyMethod(request_value="request")

    result = await client(method)

    assert result == DummyResult(value="callable")
    assert [call[0] for call in transport.execute_calls] == [method.build_request()]


@pytest.mark.asyncio
async def test_await_method_uses_client_from_active_async_scope() -> None:
    transport = FakeTransport(response=success_response("implicit"))
    client = Client(base_url="https://example.test", transport=transport)

    async with client:
        result = await DummyMethod(request_value="request")

    assert result == DummyResult(value="implicit")
    assert len(transport.execute_calls) == 1


@pytest.mark.asyncio
async def test_await_method_without_current_client_fails() -> None:
    with pytest.raises(ClientContextError, match=r"client|Client"):
        await DummyMethod(request_value="request")


@pytest.mark.asyncio
async def test_method_execute_accepts_an_explicit_client() -> None:
    transport = FakeTransport(response=success_response("execute"))
    client = Client(base_url="https://example.test", transport=transport)

    result = await DummyMethod(request_value="request").execute(client)

    assert result == DummyResult(value="execute")


@pytest.mark.asyncio
async def test_nested_current_client_scopes_restore_previous_client() -> None:
    outer_transport = FakeTransport(response=success_response("outer"))
    inner_transport = FakeTransport(response=success_response("inner"))
    outer = Client(base_url="https://outer.example", transport=outer_transport)
    inner = Client(base_url="https://inner.example", transport=inner_transport)
    method = DummyMethod(request_value="request")

    with outer.as_current():
        assert await method == DummyResult(value="outer")
        with inner.as_current():
            assert await method == DummyResult(value="inner")
        assert await method == DummyResult(value="outer")

    with pytest.raises(ClientContextError):
        await method


@pytest.mark.asyncio
async def test_nested_async_client_scopes_restore_previous_client() -> None:
    outer = Client(
        base_url="https://outer.example",
        transport=FakeTransport(response=success_response("outer")),
    )
    inner = Client(
        base_url="https://inner.example",
        transport=FakeTransport(response=success_response("inner")),
    )
    method = DummyMethod(request_value="request")

    async with outer:
        assert await method == DummyResult(value="outer")
        async with inner:
            assert await method == DummyResult(value="inner")
        assert await method == DummyResult(value="outer")

    with pytest.raises(ClientContextError):
        await method


@pytest.mark.asyncio
async def test_nested_scopes_of_same_client_close_only_after_outer_exit() -> None:
    client = Client(
        base_url="https://example.test",
        transport=FakeTransport(response=success_response("same client")),
    )
    method = DummyMethod(request_value="request")

    async with client:
        async with client:
            assert await method == DummyResult(value="same client")
        assert not client.is_closed
        assert await method == DummyResult(value="same client")

    assert client.is_closed


@pytest.mark.asyncio
async def test_concurrent_scopes_of_same_client_close_after_last_exit() -> None:
    client = Client(
        base_url="https://example.test",
        transport=FakeTransport(response=success_response("concurrent")),
    )
    first_entered = asyncio.Event()
    second_entered = asyncio.Event()
    first_exited = asyncio.Event()
    second_result: DummyResult | None = None

    async def first_scope() -> None:
        async with client:
            first_entered.set()
            await second_entered.wait()
        first_exited.set()

    async def second_scope() -> None:
        nonlocal second_result
        async with client:
            second_entered.set()
            await first_entered.wait()
            await first_exited.wait()
            assert not client.is_closed
            second_result = await DummyMethod(request_value="request")

    await asyncio.gather(first_scope(), second_scope())

    assert second_result == DummyResult(value="concurrent")
    assert client.is_closed


@pytest.mark.asyncio
async def test_current_client_is_task_local() -> None:
    first = Client(
        base_url="https://first.example",
        transport=FakeTransport(response=success_response("first")),
    )
    second = Client(
        base_url="https://second.example",
        transport=FakeTransport(response=success_response("second")),
    )

    async def execute_in_scope(client: Client) -> DummyResult:
        with client.as_current():
            await asyncio.sleep(0)
            return await DummyMethod(request_value="request")

    first_result, second_result = await asyncio.gather(
        execute_in_scope(first),
        execute_in_scope(second),
    )

    assert first_result == DummyResult(value="first")
    assert second_result == DummyResult(value="second")


@pytest.mark.asyncio
async def test_explicit_execution_does_not_install_or_require_context() -> None:
    transport = FakeTransport(response=success_response("explicit"))
    client = Client(base_url="https://example.test", transport=transport)
    method = DummyMethod(request_value="request")

    assert await client.make_request(method) == DummyResult(value="explicit")
    with pytest.raises(ClientContextError):
        await method


def test_method_models_are_strict_and_frozen() -> None:
    with pytest.raises(ValidationError):
        DummyMethod(request_value="request", unexpected=True)  # type: ignore[call-arg]

    with pytest.raises(ValidationError):
        DummyMethod(request_value=1)  # type: ignore[arg-type]

    method = DummyMethod(request_value="request")
    with pytest.raises(ValidationError):
        method.request_value = "changed"  # type: ignore[misc]


def test_default_request_uses_rpc_operation_path_and_field_names() -> None:
    method = DummyMethod(request_value="payload")

    request = method.build_request()

    assert request.method == "POST"
    assert request.path == "/tests.echo"
    assert request.json == {"request_value": "payload"}


def test_concrete_method_requires_a_valid_stable_operation() -> None:
    with pytest.raises(TypeError, match=r"namespace\.method"):

        class InvalidOperationMethod(DummyMethod):
            operation = "invalid-operation"


def test_method_fields_must_not_define_aliases() -> None:
    with pytest.raises(TypeError, match="alias"):

        class AliasedMethod(DummyMethod):
            aliased_field: str = Field(alias="aliasedField")


@pytest.mark.asyncio
async def test_method_response_parser_is_invoked_exactly_once() -> None:
    CountingMethod.parse_calls = 0
    transport = FakeTransport(response=success_response("parsed"))
    client = Client(base_url="https://example.test", transport=transport)

    result = await client.make_request(CountingMethod(request_value="request"))

    assert result == DummyResult(value="parsed")
    assert CountingMethod.parse_calls == 1


@pytest.mark.asyncio
async def test_programming_errors_from_response_parser_are_not_wrapped() -> None:
    class BrokenMethod(DummyMethod):
        def parse_response(self, response: TransportResponse) -> DummyResult:
            del response
            raise RuntimeError("parser bug")

    client = Client(
        base_url="https://example.test",
        transport=FakeTransport(response=success_response("unused")),
    )

    with pytest.raises(RuntimeError, match="parser bug"):
        await client.make_request(BrokenMethod(request_value="request"))


@pytest.mark.asyncio
async def test_response_decode_error_remains_distinguishable() -> None:
    class DecodeFailureMethod(DummyMethod):
        def parse_response(self, response: TransportResponse) -> DummyResult:
            raise ResponseDecodeError(
                operation=self.operation,
                status_code=response.status_code,
                detail="invalid test payload",
            )

    client = Client(
        base_url="https://example.test",
        transport=FakeTransport(response=success_response("unused")),
    )

    with pytest.raises(ResponseDecodeError) as captured:
        await client.make_request(DecodeFailureMethod(request_value="request"))

    assert captured.value.operation == "tests.echo"
    assert captured.value.status_code == 200
