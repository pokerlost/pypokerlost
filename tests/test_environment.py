"""Environment selection and credential partitioning regressions (manual execution)."""

from __future__ import annotations

import pytest

from pypokerlost import Environment, PokerlostClient, PokerlostEnvironmentConfig
from pypokerlost.client import PokerlostAPIServer
from pypokerlost.errors import PokerlostConfigurationError


def test_unconfigured_remote_fails_before_session_creation() -> None:
    config = PokerlostEnvironmentConfig(Environment.MAIN, {})
    assert not config.configured
    with pytest.raises(PokerlostConfigurationError, match="not_configured"):
        PokerlostClient.for_environment(config)


def test_input_mapping_cannot_change_a_selected_target() -> None:
    endpoints = {Environment.LOCAL: "http://127.0.0.1:18080"}
    config = PokerlostEnvironmentConfig(Environment.LOCAL, endpoints)
    endpoints[Environment.LOCAL] = "http://127.0.0.1:9999"
    assert config.server().base_url == "http://127.0.0.1:18080"
    assert (
        PokerlostClient.for_environment(config).session
        is not PokerlostClient.for_environment(config).session
    )


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://127.0.0.1:18080",
        "https://user:secret@host.invalid",
        "https://host.invalid/api",
        "https://host.invalid:invalid",
        "https://host.invalid\n",
    ],
)
def test_main_rejects_unsafe_origins(endpoint: str) -> None:
    with pytest.raises(PokerlostConfigurationError, match="Invalid environment"):
        PokerlostEnvironmentConfig(Environment.MAIN, {Environment.MAIN: endpoint})


def test_direct_target_api_stays_available() -> None:
    target = PokerlostAPIServer("https://EXAMPLE.invalid:443/")
    assert target.base_url == "https://example.invalid"
    assert target.environment is None
