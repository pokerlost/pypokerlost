"""OpenAPI parsing and global preflight: invalid inputs never write output."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from scripts import generate_methods as generator
from tests.generator_builders import SCOPE, document, object_schema, operation, success_schema


def parsed(raw: dict[str, Any]) -> generator.SourceDocument:
    return generator.parse_document(raw, label="synthetic-contract.json")


def test_public_and_protected_contracts_keep_exact_scopes_and_identity() -> None:
    public = parsed(document())
    protected = parsed(document("technicalProtected", protected=True))
    operations = generator.collect_operations((protected, public))
    assert [str(item.operation) for item in operations] == ["technicalProbe", "technicalProtected"]
    assert operations[0].scopes is None
    assert operations[1].scopes == (SCOPE,)
    assert operations[0].class_name == "TechnicalProbe"
    assert operations[0].module_name == "technical_probe"
    assert len(public.source_sha256) == 64
    reordered = dict(reversed(list(document().items())))
    assert parsed(reordered).source_sha256 == public.source_sha256


@pytest.mark.parametrize(
    "patch",
    [
        {"openapi": "3.0.3"},
        {"openapi": ""},
        {"openapi": 3.1},
        {"info": None},
        {"info": {"title": "", "version": "1.0.0"}},
        {"info": {"title": "Fixture", "version": "01.0.0"}},
        {"paths": []},
        {"components": []},
        {"security": [{}]},
        {"x-private-extension": "synthetic-private-value"},
        {"components": {"schemas": {"T": {"x-private": 7}}}},
        {"paths": {1: {}}},
    ],
)
def test_document_rejects_invalid_metadata_and_extensions(patch: dict[str, Any]) -> None:
    with pytest.raises(generator.GenerationError):
        parsed(document() | patch)


@pytest.mark.parametrize(
    "scheme",
    [
        None,
        {},
        {"type": "http", "scheme": "bearer"},
        {"type": "oauth2", "unexpected": 1},
        {"type": "oauth2", "flows": {}},
        {"type": "oauth2", "flows": {"password": {}}},
        {"type": "oauth2", "flows": {"clientCredentials": {}}},
    ],
)
def test_oauth_scheme_is_explicit_and_unambiguous(scheme: object) -> None:
    raw = document(protected=True)
    raw["components"]["securitySchemes"]["PokerlostOAuth2"] = scheme
    with pytest.raises(generator.GenerationError):
        parsed(raw)


@pytest.mark.parametrize(
    "kind", ["name", "multiple", "tokenUrl", "flowFields", "scopeName", "scopeDescription"]
)
def test_oauth_catalog_rejects_noncanonical_contracts(kind: str) -> None:
    raw = document(protected=True)
    schemes = raw["components"]["securitySchemes"]
    flow = schemes["PokerlostOAuth2"]["flows"]["clientCredentials"]
    if kind == "name":
        schemes["WrongName"] = schemes.pop("PokerlostOAuth2")
    elif kind == "multiple":
        schemes["Another"] = deepcopy(schemes["PokerlostOAuth2"])
    elif kind == "tokenUrl":
        flow["tokenUrl"] = "/otherToken"
    elif kind == "flowFields":
        flow["refreshUrl"] = "/refreshToken"
    elif kind == "scopeName":
        flow["scopes"] = {"notDotted": "Description"}
    else:
        flow["scopes"] = {SCOPE: ""}
    with pytest.raises(generator.GenerationError):
        parsed(raw)


@pytest.mark.parametrize(
    "security",
    [
        [{}],
        [{"Wrong": [SCOPE]}],
        [{"PokerlostOAuth2": []}],
        [{"PokerlostOAuth2": [SCOPE, SCOPE]}],
        [{"PokerlostOAuth2": ["unknown.scope"]}],
        [{"PokerlostOAuth2": [SCOPE]}, {"PokerlostOAuth2": [SCOPE]}],
        [{"PokerlostOAuth2": [SCOPE], "Other": [SCOPE]}],
        [{"PokerlostOAuth2": "not-an-array"}],
    ],
)
def test_protected_operation_requires_one_known_nonempty_scope_set(security: object) -> None:
    raw = document(protected=True)
    operation(raw)["security"] = security
    with pytest.raises(generator.GenerationError):
        generator.collect_operations((parsed(raw),))


def test_operation_cannot_use_undeclared_scheme_or_scope_absent_from_sdk() -> None:
    raw = document()
    operation(raw)["security"] = [{"PokerlostOAuth2": [SCOPE]}]
    with pytest.raises(generator.GenerationError, match="no Pokerlost OAuth2"):
        generator.collect_operations((parsed(raw),))
    raw = document(protected=True)
    raw["components"]["securitySchemes"]["PokerlostOAuth2"]["flows"]["clientCredentials"][
        "scopes"
    ] = {"future.operation": "Synthetic unknown scope"}
    operation(raw)["security"] = [{"PokerlostOAuth2": ["future.operation"]}]
    with pytest.raises(generator.GenerationError, match="absent from PokerlostScopes"):
        generator.collect_operations((parsed(raw),))


@pytest.mark.parametrize(
    "kind",
    [
        "verb",
        "path",
        "operationId",
        "pathParameters",
        "operationParameters",
        "bodyRequired",
        "media",
        "requestEnvelope",
        "unknownRequired",
        "additionalProperties",
    ],
)
def test_business_contracts_fail_preflight_before_any_write(tmp_path: Path, kind: str) -> None:
    raw = document()
    spec = operation(raw)
    path = raw["paths"]["/technicalProbe"]
    body = spec["requestBody"]
    if kind == "verb":
        path["get"] = path.pop("post")
    elif kind == "path":
        raw["paths"]["/nested/technicalProbe"] = raw["paths"].pop("/technicalProbe")
    elif kind == "operationId":
        spec["operationId"] = "invalid_operation"
    elif kind == "pathParameters":
        path["parameters"] = [{"name": "id"}]
    elif kind == "operationParameters":
        spec["parameters"] = [{"name": "id"}]
    elif kind == "bodyRequired":
        body["required"] = False
    elif kind == "media":
        body["content"] = {"text/plain": {}}
    else:
        schema = body["content"]["application/json"]["schema"]
        if kind == "requestEnvelope":
            schema["properties"]["token"] = {"type": "string"}
        elif kind == "unknownRequired":
            schema["required"].append("missing")
        else:
            schema["additionalProperties"] = True
    output = tmp_path / "output"
    with pytest.raises(generator.GenerationError):
        generator.generate((parsed(raw),), output=output, check=False)
    assert not output.exists()
    assert not (tmp_path / ".pypokerlost-generated").exists()


@pytest.mark.parametrize(
    "kind",
    [
        "empty",
        "headers",
        "media",
        "fields",
        "required",
        "ok",
        "error",
        "retry",
        "noSuccess",
        "differentSuccess",
        "failureResult",
    ],
)
def test_response_envelopes_are_checked_as_a_complete_contract(kind: str) -> None:
    raw = document()
    response = operation(raw)["responses"]["200"]
    envelope = success_schema(raw)
    if kind == "empty":
        operation(raw)["responses"] = {}
    elif kind == "headers":
        response["headers"] = {"Retry-After": {}}
    elif kind == "media":
        response["content"] = {"text/plain": {}}
    elif kind == "fields":
        envelope["properties"].pop("retry_after")
    elif kind == "required":
        envelope["required"].append("result")
    elif kind == "ok":
        envelope["properties"]["ok"] = {"type": "integer"}
    elif kind == "error":
        envelope["properties"]["error"] = {"type": "integer"}
    elif kind == "retry":
        envelope["properties"]["retry_after"] = {"type": "string"}
    elif kind == "noSuccess":
        operation(raw)["responses"] = {"default": response}
        envelope["properties"]["result"] = {"type": "null"}
    elif kind == "differentSuccess":
        operation(raw)["responses"]["201"] = deepcopy(response)
        operation(raw)["responses"]["201"]["content"]["application/json"]["schema"][
            "description"
        ] = "Different schema"
    else:
        operation(raw)["responses"]["400"] = deepcopy(response)
    with pytest.raises(generator.GenerationError):
        generator.collect_operations((parsed(raw),))


@pytest.mark.parametrize("operation_id", ["getRoot", "getHealth", "getOpenApi", "getReadiness"])
def test_public_infrastructure_get_routes_are_not_generated(operation_id: str) -> None:
    raw = document()
    path = "/" if operation_id == "getRoot" else "/" + operation_id
    raw["paths"][path] = {"get": {"operationId": operation_id}}
    assert len(generator.collect_operations((parsed(raw),))) == 1


@pytest.mark.parametrize("kind", ["path", "parameters", "body", "security"])
def test_infrastructure_routes_cannot_hide_business_or_auth_contracts(kind: str) -> None:
    raw = document()
    get: dict[str, Any] = {"operationId": "getOpenApi"}
    raw["paths"]["/wrong" if kind == "path" else "/getOpenApi"] = {"get": get}
    if kind == "parameters":
        get["parameters"] = [{}]
    elif kind == "body":
        get["requestBody"] = {}
    elif kind == "security":
        get["security"] = [{}]
    with pytest.raises(generator.GenerationError):
        generator.collect_operations((parsed(raw),))


def test_global_operation_and_module_collisions_fail_before_writing(tmp_path: Path) -> None:
    for sources in [(document(), document()), (document("readXML"), document("readXml"))]:
        output = tmp_path / "output"
        with pytest.raises(generator.GenerationError, match="collision"):
            generator.generate(tuple(parsed(raw) for raw in sources), output=output, check=False)
        assert not output.exists()


def test_allof_envelopes_merge_distinct_fields_and_reject_repeated_fields() -> None:
    raw = document(payload=object_schema({"value": {"type": "integer"}}, ["value"]))
    body = operation(raw)["requestBody"]["content"]["application/json"]
    original = body["schema"]
    body["schema"] = {"allOf": [original, object_schema()]}
    assert len(generator.collect_operations((parsed(raw),))) == 1
    body["schema"] = {"allOf": [original, original]}
    with pytest.raises(generator.GenerationError, match="repeats object fields"):
        generator.collect_operations((parsed(raw),))
