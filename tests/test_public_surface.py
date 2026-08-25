from __future__ import annotations

from importlib.metadata import version

import pytest

import pypokerlost
from pypokerlost import (
    Client,
    ClientClosedError,
    ClientContextError,
    Method,
    PokerLostError,
    ResponseDecodeError,
    StreamMethod,
    TransportError,
    UnexpectedStatusError,
)
from tests.helpers import FakeTransport


def test_distribution_version_is_resolved_from_installed_metadata() -> None:
    assert pypokerlost.__version__ == version("pypokerlost")


def test_package_root_exposes_the_intentional_public_facade() -> None:
    public_values = (
        Client,
        Method,
        StreamMethod,
        PokerLostError,
        ClientContextError,
        ClientClosedError,
        TransportError,
        UnexpectedStatusError,
        ResponseDecodeError,
    )

    assert all(value.__module__.startswith("pypokerlost") for value in public_values)
    assert not hasattr(pypokerlost, "version")


@pytest.mark.asyncio
async def test_client_has_no_endpoint_methods_or_dynamic_endpoint_fallback() -> None:
    client = Client(base_url="https://example.test", transport=FakeTransport())

    assert "__getattr__" not in Client.__dict__
    assert not hasattr(Client, "get_balance")
    assert not hasattr(Client, "create_account")
    endpoint_name = "invented_endpoint"
    with pytest.raises(AttributeError):
        getattr(client, endpoint_name)

    await client.close()
