"""Accept the built distribution outside a source checkout without repeating unit tests."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

import pypokerlost
import pypokerlost_generator.models as generator_models
import pypokerlost_generator.rendering as generator_rendering
import pypokerlost_generator.schema as generator_schema
from pypokerlost import (
    Environment,
    PokerlostClient,
    PokerlostEnvironmentConfig,
    PokerlostMethod,
    PokerlostRequestOptions,
)
from pypokerlost.enums import PokerlostErrorCode, PokerlostScopes, ServiceId
from pypokerlost.methods import GetToken
from pypokerlost.middleware import PokerlostAuthenticationMiddleware
from pypokerlost.types import PokerlostAudience, PokerlostTokenKey
from pypokerlost_generator import __main__ as generator


def main() -> None:
    """Check metadata, typed imports and the actual installed generator entry point."""
    root = Path(__file__).resolve().parents[1]
    expected = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    package = Path(pypokerlost.__file__).resolve().parent
    distribution = importlib.metadata.distribution("pypokerlost")
    assert distribution.version == pypokerlost.__version__ == expected
    assert "site-packages" in package.parts and not package.is_relative_to(root)
    assert not (root / "src").exists()
    assert (package / "py.typed").is_file()
    assert "site-packages" in Path(generator.__file__).resolve().parts
    for module in (generator_models, generator_rendering, generator_schema):
        assert "site-packages" in Path(module.__file__).resolve().parts
    assert generator.SourceDocument is generator_models.SourceDocument
    assert generator.parse_document is generator_schema.parse_document
    assert generator.render_method is generator_rendering.render_method
    entrypoint = next(
        item for item in distribution.entry_points if item.name == "pypokerlost-generate"
    )
    assert entrypoint.value == "pypokerlost_generator.__main__:main"
    result = subprocess.run(
        [sys.executable, "-I", "-m", "pypokerlost_generator", "--version"],
        cwd="/tmp",
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    assert result.stdout.strip() == generator.GENERATOR_VERSION
    assert PokerlostAudience.for_service(ServiceId.ACCOUNTS) == "accountsService"
    assert PokerlostErrorCode.ACCESS_TOKEN_EXPIRED.value == "POKERLOST_ACCESS_TOKEN_EXPIRED"
    environment = PokerlostEnvironmentConfig(
        Environment.TEST, {Environment.TEST: "https://TEST.invalid:443/"}
    )
    assert environment.server().base_url == "https://test.invalid"
    assert environment.server().environment is Environment.TEST
    assert PokerlostClient.for_environment(environment).session is not (
        PokerlostClient.for_environment(environment).session
    )
    legacy_key = PokerlostTokenKey(
        client_id="synthetic-installed-client",
        audience="accountsService",
        scopes=(PokerlostScopes.ACCOUNTS_SELF_GET_ME,),
    )
    assert set(legacy_key.model_dump()) == {"client_id", "audience", "scopes"}
    bound_key = PokerlostTokenKey(
        **legacy_key.model_dump(),
        environment=Environment.TEST,
        origin=environment.server().base_url,
    )
    assert set(bound_key.model_dump()) == {
        "environment",
        "origin",
        "client_id",
        "audience",
        "scopes",
    }
    with tempfile.TemporaryDirectory(prefix="pypokerlost-contract-") as temporary:
        output = Path(temporary) / "sdk_contract.json"
        command = [
            sys.executable,
            "-I",
            "-m",
            "pypokerlost_generator",
            "contract",
            "--output",
            str(output),
        ]
        for arguments in (command, [*command, "--check"]):
            subprocess.run(
                arguments, cwd="/tmp", capture_output=True, text=True, check=True, timeout=30
            )
        contract = json.loads(output.read_text())
        contract_digest = hashlib.sha256(output.read_bytes()).hexdigest()
        assert output.with_suffix(".json.sha256").read_text() == (
            f"{contract_digest}  sdk_contract.json\n"
        )
        assert contract["contract_version"] == 1
        assert contract["service_ids"]["POKER"] == "pokerService"
    for symbol in (
        Environment,
        PokerlostEnvironmentConfig,
        PokerlostClient,
        PokerlostMethod,
        PokerlostRequestOptions,
        PokerlostScopes,
        GetToken,
        PokerlostAuthenticationMiddleware,
    ):
        assert symbol.__module__.startswith("pypokerlost.")
    built = sorted(Path("/artifacts").glob("*"))
    exported = sorted(Path("/verified-artifacts").glob("*"))
    assert {path.name for path in built} == {path.name for path in exported}
    hashes = {}
    for path in exported:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == hashlib.sha256((Path("/artifacts") / path.name).read_bytes()).hexdigest()
        hashes[path.name] = digest
    assert any(name.endswith(".whl") for name in hashes)
    assert any(name.endswith(".tar.gz") for name in hashes)
    report = {
        "package": expected,
        "artifactSha256": hashes,
        "generator": generator.GENERATOR_VERSION,
        "manifest": generator.MANIFEST_VERSION,
        "protocolContract": contract["contract_version"],
        "outsideCheckout": True,
        "typed": True,
        "installedEntrypoint": True,
    }
    (root / "coverage").mkdir(exist_ok=True)
    (root / "coverage/installed.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
