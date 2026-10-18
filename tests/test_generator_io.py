"""File and HTTP I/O failures through the real generator entrypoints."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from scripts import generate_methods as generator
from tests.generator_builders import document


def install_http(
    monkeypatch: pytest.MonkeyPatch, respond: Callable[[httpx.Request], httpx.Response]
) -> list[httpx.Request]:
    original = httpx.AsyncClient
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return respond(request)

    def create(*, timeout: float, trust_env: bool) -> httpx.AsyncClient:
        assert timeout > 0
        assert trust_env is False
        return original(
            timeout=timeout, trust_env=trust_env, transport=httpx.MockTransport(handler)
        )

    monkeypatch.setattr(httpx, "AsyncClient", create)
    return requests


def test_service_fetch_and_cli_generate_public_openapi(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    requests = install_http(monkeypatch, lambda request: httpx.Response(200, json=document()))
    source = asyncio.run(generator._fetch_source("https://service.invalid", 2))
    assert source.title == "Technical fixture"
    result = CliRunner().invoke(
        generator.app,
        ["service", "https://service.invalid", "--output", str(tmp_path / "pypokerlost")],
    )
    assert result.exit_code == 0, result.output
    assert len(requests) == 2
    assert all(
        request.method == "GET" and str(request.url) == "https://service.invalid/getOpenApi"
        for request in requests
    )
    assert all("authorization" not in request.headers for request in requests)


@pytest.mark.parametrize("timeout", [0, -1, True, "10", None])
def test_fetch_requires_positive_explicit_timeout(timeout: object) -> None:
    with pytest.raises(generator.GenerationError, match="timeout"):
        asyncio.run(generator._fetch_source("https://service.invalid", timeout))


@pytest.mark.parametrize(
    "url",
    [
        "http://service.invalid",
        "https://user:synthetic@service.invalid",
        "https://service.invalid/path",
    ],
)
def test_fetch_rejects_ambient_target_state_before_io(url: str) -> None:
    with pytest.raises(generator.GenerationError, match="service URL"):
        asyncio.run(generator._fetch_source(url, 1))


@pytest.mark.parametrize("kind", ["network", "json", "refused", "notObject", "badContract"])
def test_publication_failures_are_safe_and_do_not_write(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, kind: str
) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if kind == "network":
            raise httpx.ConnectError("synthetic-private-detail")
        if kind == "json":
            return httpx.Response(200, content=b"synthetic-private-detail")
        if kind == "refused":
            return httpx.Response(403, json=document())
        if kind == "notObject":
            return httpx.Response(200, json=[])
        return httpx.Response(200, json={"private": "synthetic-private-detail"})

    install_http(monkeypatch, respond)
    result = CliRunner().invoke(
        generator.app,
        ["service", "https://service.invalid", "--output", str(tmp_path / "pypokerlost")],
    )
    assert result.exit_code == 1
    assert "synthetic-private-detail" not in result.output
    assert not (tmp_path / "pypokerlost").exists()


def test_empty_source_sequence_is_an_explicit_cli_failure(tmp_path: Path) -> None:
    with pytest.raises(generator.typer.Exit) as error:
        generator._execute_file((), output=tmp_path / "pypokerlost", check=False)
    assert error.value.exit_code == 1


@pytest.mark.parametrize(
    "reader", [generator._read_source, generator._defined_public_types, generator._defined_methods]
)
def test_unreadable_sources_use_domain_errors(
    tmp_path: Path, reader: Callable[[Path], object]
) -> None:
    # A directory raises a real OSError on all supported test users, including root.
    with pytest.raises(generator.GenerationError):
        reader(tmp_path)


def test_invalid_encoding_and_syntax_are_controlled(tmp_path: Path) -> None:
    path = tmp_path / "bad.py"
    path.write_bytes(b"\xff")
    for reader in (
        generator._read_source,
        generator._defined_methods,
        generator._defined_public_types,
    ):
        with pytest.raises(generator.GenerationError):
            reader(path)
    path.write_text("class broken (\n")
    with pytest.raises(generator.GenerationError):
        generator._defined_methods(path)
    with pytest.raises(generator.GenerationError):
        generator._defined_public_types(path)
    with pytest.raises(generator.GenerationError):
        generator._method_metadata(
            tmp_path, "TechnicalProbe", scope_members=generator.SDK_SCOPE_MEMBERS
        )


def test_facade_and_manifest_io_failures_are_controlled(tmp_path: Path) -> None:
    (tmp_path / "bad.py").mkdir()
    with pytest.raises(generator.GenerationError):
        generator._facade_modules(tmp_path, methods=False)
    with pytest.raises(generator.GenerationError):
        generator._validate_handwritten_methods(tmp_path, scope_members=generator.SDK_SCOPE_MEMBERS)
    with pytest.raises(generator.GenerationError):
        generator._previous_owned_files(tmp_path)


def test_malformed_manifest_and_generated_target_fail_before_write(tmp_path: Path) -> None:
    output = tmp_path / "pypokerlost"
    (output / "methods/__init__.py").mkdir(parents=True)
    source = generator.parse_document(document(), label="synthetic.json")
    with pytest.raises(generator.GenerationError, match="generated target"):
        generator.generate((source,), output=output, check=False)
    assert not (output / "methods/technical_probe.py").exists()
    path = tmp_path / "manifest.json"
    path.write_text("not JSON")
    with pytest.raises(generator.GenerationError):
        generator._previous_owned_files(path)
    path.write_text(json.dumps({"files": [True]}))
    with pytest.raises(generator.GenerationError):
        generator._previous_owned_files(path)
