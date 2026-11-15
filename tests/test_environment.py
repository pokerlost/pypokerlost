"""Environment selection and credential partitioning regressions."""

from __future__ import annotations

import httpx
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


@pytest.mark.parametrize(
    ("endpoint", "expected"),
    [
        ("https://EXAMPLE.invalid:443/", "https://example.invalid"),
        ("https://example.invalid:8443/", "https://example.invalid:8443"),
        ("https://[::1]:443/", "https://[::1]"),
    ],
)
def test_environment_uses_canonical_origin(endpoint: str, expected: str) -> None:
    config = PokerlostEnvironmentConfig(Environment.TEST, {Environment.TEST: endpoint})
    assert config.server().base_url == expected
    assert config.server().environment is Environment.TEST


def test_duplicate_canonical_origins_are_rejected() -> None:
    with pytest.raises(PokerlostConfigurationError, match="distinct origins"):
        PokerlostEnvironmentConfig(
            Environment.TEST,
            {
                Environment.TEST: "https://example.invalid",
                Environment.DEV: "https://EXAMPLE.invalid:443/",
            },
        )


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://host.invalid:0",
        "https://host.invalid\\suffix",
        "https://host.invalid/%22",
        "https://user:synthetic-private@host.invalid",
        "https://host.invalid?private=synthetic-private",
    ],
)
def test_invalid_endpoint_errors_do_not_expose_configuration(endpoint: str) -> None:
    with pytest.raises(PokerlostConfigurationError) as error:
        PokerlostEnvironmentConfig(Environment.TEST, {Environment.TEST: endpoint})
    assert str(error.value) == "Invalid environment endpoint configuration"
    assert endpoint not in repr(error.value)
    assert error.value.__cause__ is None


@pytest.mark.parametrize("endpoint", ["http://host.invalid", "https://host.invalid"])
def test_local_environment_requires_loopback(endpoint: str) -> None:
    with pytest.raises(PokerlostConfigurationError, match="Invalid environment"):
        PokerlostEnvironmentConfig(Environment.LOCAL, {Environment.LOCAL: endpoint})


def test_environment_names_and_values_are_an_independent_exact_catalog() -> None:
    assert {member.name: member.value for member in Environment} == {
        "MAIN": "main",
        "DEV": "dev",
        "TEST": "test",
        "LOCAL": "local",
    }


def test_unicode_origin_matches_httpx_idna_canonicalization() -> None:
    endpoint = "https://bücher.invalid:443/"
    expected = str(httpx.URL(endpoint).copy_with(path=""))
    assert expected == "https://xn--bcher-kva.invalid"
    assert PokerlostAPIServer(endpoint).base_url == expected


def test_unicode_and_punycode_origins_are_the_same_environment_target() -> None:
    with pytest.raises(PokerlostConfigurationError, match="distinct origins"):
        PokerlostEnvironmentConfig(
            Environment.TEST,
            {
                Environment.TEST: "https://bücher.invalid",
                Environment.DEV: "https://XN--BCHER-KVA.invalid:443/",
            },
        )


def test_del_hostname_is_rejected_safely_before_session_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_session(*args, **kwargs):
        pytest.fail("Invalid endpoint must not create an HTTP session")

    monkeypatch.setattr(httpx, "AsyncClient", forbidden_session)
    endpoint = "https://host.invalid\x7f"
    with pytest.raises(ValueError) as direct_error:
        PokerlostAPIServer(endpoint)
    assert str(direct_error.value) == "Invalid Pokerlost API origin"
    assert direct_error.value.__cause__ is None
    with pytest.raises(PokerlostConfigurationError) as config_error:
        PokerlostClient.for_environment(
            PokerlostEnvironmentConfig(Environment.TEST, {Environment.TEST: endpoint})
        )
    assert str(config_error.value) == "Invalid environment endpoint configuration"
    assert config_error.value.__cause__ is None
    assert endpoint not in repr(config_error.value)
