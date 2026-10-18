"""Validate actual wire contracts, identity invariants and secret-safe representations."""

from __future__ import annotations

import itertools
import json
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest
from pydantic import TypeAdapter, ValidationError

from pypokerlost.enums import PokerlostScopes, PrincipalType
from pypokerlost.types import (
    GetTokenRequest,
    MutablePokerlostType,
    PokerlostAccessTokenClaims,
    PokerlostAudience,
    PokerlostAuthorizationContext,
    PokerlostOperation,
    PokerlostResponse,
    PokerlostStoredToken,
    PokerlostToken,
    PokerlostTokenKey,
    PokerlostType,
    ProvisionHumanRequest,
    RefreshTokenRequest,
    ReplacePrincipalScopesRequest,
    ReplacePrincipalScopesResponse,
)
from pypokerlost.types._scope_set import parse_scope_set
from pypokerlost.types.json import JSONValue

PRINCIPAL = UUID("00000000-0000-0000-0000-000000000001")
CLIENT = UUID("00000000-0000-0000-0000-000000000002")
SCOPE = PokerlostScopes.ACCOUNTS_SELF_GET_ME


@pytest.mark.parametrize("kind", [PokerlostAudience, PokerlostOperation])
@pytest.mark.parametrize("value", ["a", "getToken", "accountsService", "a123", "aB9"])
def test_identifiers_round_trip(kind: type[str], value: str) -> None:
    parsed = kind(value)
    assert kind(parsed) is parsed
    adapter = TypeAdapter(kind)
    assert adapter.validate_python(value) == value
    assert adapter.validate_json(json.dumps(value)) == value
    assert adapter.dump_json(parsed) == json.dumps(value).encode()


@pytest.mark.parametrize("kind", [PokerlostAudience, PokerlostOperation])
@pytest.mark.parametrize("value", ["", "LeadingUpper", "a/b", "a_b", "a.b", "a-1", "a\n", "я"])
def test_identifiers_reject_noncanonical_names(kind: type[str], value: str) -> None:
    with pytest.raises(ValueError):
        kind(value)


@pytest.mark.parametrize("kind", [PokerlostAudience, PokerlostOperation])
@pytest.mark.parametrize("value", [None, 1, True, b"probe"])
def test_identifiers_reject_coercion(kind: type[str], value: object) -> None:
    with pytest.raises(TypeError):
        kind(value)
    with pytest.raises(ValidationError):
        TypeAdapter(kind).validate_python(value)


def test_scope_order_is_canonical_for_bounded_permutations() -> None:
    scopes = tuple(PokerlostScopes)[:4]
    for length in range(1, len(scopes) + 1):
        for selected in itertools.permutations(scopes, length):
            expected = tuple(sorted(selected, key=lambda item: item.value))
            assert parse_scope_set(selected, field_name="Scopes") == expected
            assert (
                parse_scope_set([str(item) for item in selected], field_name="Scopes") == expected
            )
            assert parse_scope_set(frozenset(selected), field_name="Scopes") == expected


@pytest.mark.parametrize(
    "value", [None, "accounts.self.getMe", set(), {}, ["unknown"], [{}], [], [SCOPE, SCOPE]]
)
def test_scope_sets_reject_wrong_shape_and_authority(value: object) -> None:
    with pytest.raises(ValueError, match="Scopes"):
        parse_scope_set(value, field_name="Scopes")


def test_empty_authority_is_only_enabled_by_explicit_contract() -> None:
    assert parse_scope_set([], field_name="Scopes", allow_empty=True) == ()
    assert (
        ReplacePrincipalScopesRequest(
            business_operation_id=CLIENT, principal_id=PRINCIPAL, scopes=[]
        ).scopes
        == ()
    )
    assert (
        ProvisionHumanRequest(
            business_operation_id=CLIENT, account_id=PRINCIPAL, initial_scopes=[]
        ).initial_scopes
        == ()
    )


def test_scope_replacement_response_allows_explicit_empty_authority() -> None:
    assert ReplacePrincipalScopesResponse(principal_id=PRINCIPAL, scopes=[]).scopes == ()


def token_data() -> dict[str, object]:
    return {
        "access_token": "synthetic-access-secret",
        "refresh_token": "synthetic-refresh-secret",
        "expires_in": 60,
        "scopes": [SCOPE.value],
        "audience": "accountsService",
    }


def test_tokens_round_trip_without_secrets_in_repr() -> None:
    token = PokerlostToken.model_validate(token_data())
    assert token.scopes == (SCOPE,)
    assert "synthetic" not in repr(token)
    assert token.model_dump(mode="json") == token_data()
    offset = timezone(timedelta(hours=3))
    stored = PokerlostStoredToken(
        token=token, expires_at=datetime(2030, 1, 1, 3, tzinfo=offset), version=1
    )
    assert stored.expires_at == datetime(2030, 1, 1, tzinfo=UTC)
    assert stored.expires_at.tzinfo is UTC
    assert "synthetic" not in repr(stored)
    key = PokerlostTokenKey(client_id=str(CLIENT), audience=token.audience, scopes=token.scopes)
    assert key == PokerlostTokenKey.model_validate_json(key.model_dump_json())
    assert hash(key) == hash(PokerlostTokenKey.model_validate_json(key.model_dump_json()))


@pytest.mark.parametrize(
    "patch",
    [
        {"access_token": ""},
        {"refresh_token": ""},
        {"expires_in": 0},
        {"expires_in": True},
        {"expires_in": "60"},
        {"scopes": []},
        {"audience": "wrong/audience"},
        {"unexpected": "synthetic-private-input"},
    ],
)
def test_invalid_token_values_do_not_echo_inputs(patch: dict[str, object]) -> None:
    with pytest.raises(ValidationError) as error:
        PokerlostToken.model_validate(token_data() | patch)
    assert "synthetic-private-input" not in str(error.value)
    assert "synthetic-access-secret" not in str(error.value)


@pytest.mark.parametrize(
    "patch", [{"version": 0}, {"version": True}, {"expires_at": datetime(2030, 1, 1)}]
)
def test_stored_token_requires_version_and_absolute_expiry(patch: dict[str, object]) -> None:
    value = {
        "token": PokerlostToken.model_validate(token_data()),
        "version": 1,
        "expires_at": datetime(2030, 1, 1, tzinfo=UTC),
    }
    with pytest.raises(ValidationError):
        PokerlostStoredToken.model_validate(value | patch)


def test_request_models_keep_credential_and_refresh_semantics() -> None:
    request = GetTokenRequest(
        client_id=str(CLIENT),
        client_secret="synthetic-client-secret",
        scopes=[SCOPE],
        audience="accountsService",
    )
    assert request.client_id == CLIENT
    assert request.client_secret.get_secret_value() == "synthetic-client-secret"
    assert "synthetic-client-secret" not in repr(request)
    refresh = RefreshTokenRequest(
        refresh_token="synthetic-refresh-secret", audience="accountsService"
    )
    assert refresh.scopes is None
    assert "synthetic-refresh-secret" not in repr(refresh)
    assert RefreshTokenRequest(
        refresh_token="synthetic-refresh-secret", audience="accountsService", scopes=[SCOPE]
    ).scopes == (SCOPE,)
    with pytest.raises(ValidationError):
        RefreshTokenRequest(
            refresh_token="synthetic-refresh-secret", audience="accountsService", scopes=[]
        )


@pytest.mark.parametrize(
    "envelope",
    [
        {"ok": True, "error": "FAILURE"},
        {"ok": True, "error_message": "failure"},
        {"ok": True, "retry_after": 0.0},
        {"ok": False, "result": 1, "error": "FAILURE"},
        {"ok": False},
        {"ok": False, "error": ""},
        {"ok": False, "error": "FAILURE", "retry_after": -0.1},
        {"ok": False, "error": "FAILURE", "retry_after": float("nan")},
        {"ok": False, "error": "FAILURE", "retry_after": float("inf")},
        {"ok": 1},
        {"ok": True, "unexpected": "synthetic-private-input"},
    ],
)
def test_response_envelope_rejects_ambiguous_or_nonfinite_data(envelope: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        PokerlostResponse[object].model_validate(envelope)


def test_response_envelope_preserves_success_and_failure_shapes() -> None:
    assert PokerlostResponse[int](ok=True, result=7).model_dump() == {
        "ok": True,
        "result": 7,
        "error": None,
        "error_message": None,
        "retry_after": None,
    }
    failure = PokerlostResponse[object](ok=False, error="BUSY", retry_after=0.0)
    assert failure.error == "BUSY"
    assert failure.retry_after == 0.0


def claims_data() -> dict[str, object]:
    return {
        "iss": "https://issuer.invalid",
        "sub": str(PRINCIPAL),
        "aud": "accountsService",
        "iat": 1_700_000_000,
        "nbf": 1_700_000_000,
        "exp": 1_700_000_060,
        "jti": str(UUID(int=3)),
        "client_id": str(CLIENT),
        "scopes": [SCOPE.value],
        "principal_type": "human",
    }


def test_claims_support_numeric_dates_aliases_and_native_values() -> None:
    wire = claims_data()
    claims = PokerlostAccessTokenClaims.model_validate(wire)
    assert claims.issued_at == datetime.fromtimestamp(1_700_000_000, tz=UTC)
    assert claims.subject == PRINCIPAL
    assert claims.principal_type is PrincipalType.HUMAN
    assert claims.model_dump(mode="json", by_alias=True, exclude_none=True) == wire
    native = claims.model_dump()
    assert PokerlostAccessTokenClaims.model_validate(native) == claims


@pytest.mark.parametrize(
    "patch",
    [
        {"exp": 1_700_000_000},
        {"iat": 1_700_000_060},
        {"sub": str(CLIENT)},
        {"service_name": "service"},
        {"principal_type": "service", "account_id": str(PRINCIPAL)},
        {"principal_type": "service", "session_id": str(PRINCIPAL)},
        {"iat": 10**100},
        {"iat": True},
        {"iat": datetime(2030, 1, 1)},
        {"sub": "not-a-uuid"},
        {"principal_type": "role"},
        {"scopes": []},
    ],
)
def test_claim_invariants_reject_invalid_identity_and_time(patch: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        PokerlostAccessTokenClaims.model_validate(claims_data() | patch)


@pytest.mark.parametrize("principal_type", list(PrincipalType))
def test_authorization_context_preserves_exact_identity(principal_type: PrincipalType) -> None:
    context = PokerlostAuthorizationContext(
        principal_id=PRINCIPAL,
        principal_type=principal_type,
        client_id=CLIENT,
        audience="accountsService",
        scopes=[SCOPE],
    )
    assert context.principal_id == PRINCIPAL
    assert context.principal_type is principal_type
    assert context.scopes == (SCOPE,)


@pytest.mark.parametrize(
    "patch",
    [
        {"service_name": "service"},
        {"principal_type": PrincipalType.SERVICE, "account_id": PRINCIPAL},
        {"principal_type": PrincipalType.SERVICE, "session_id": PRINCIPAL},
    ],
)
def test_authorization_context_rejects_mixed_human_service_bindings(
    patch: dict[str, object],
) -> None:
    value = {
        "principal_id": PRINCIPAL,
        "principal_type": PrincipalType.HUMAN,
        "client_id": CLIENT,
        "audience": "accountsService",
        "scopes": [SCOPE],
    }
    with pytest.raises(ValidationError):
        PokerlostAuthorizationContext.model_validate(value | patch)


def test_immutable_and_mutable_model_assignment_contract() -> None:
    class Immutable(PokerlostType):
        count: int

    class Mutable(MutablePokerlostType):
        count: int

    immutable = Immutable(count=1)
    with pytest.raises(ValidationError, match="frozen"):
        immutable.count = 2
    mutable = Mutable(count=1)
    mutable.count = 2
    assert mutable.count == 2
    with pytest.raises(ValidationError):
        mutable.count = object()


def test_json_codec_round_trips_bounded_nested_builtin_values() -> None:
    adapter = TypeAdapter(JSONValue)
    values: list[object] = [None, True, False, 0, 2**120, 1.5, "text"]
    for _ in range(3):
        for value in values:
            parsed = adapter.validate_python(value)
            assert parsed == value
            assert json.loads(adapter.dump_json(parsed)) == value
        values = [[value] for value in values] + [{"value": value} for value in values]


class StringSubclass(str):
    pass


@pytest.mark.parametrize(
    "value",
    [
        b"text",
        {1: "value"},
        {StringSubclass("key"): 7},
        (1,),
        {1},
        StringSubclass("text"),
        float("nan"),
        float("inf"),
        {"nested": b"text"},
    ],
)
def test_json_codec_rejects_non_json_objects_and_nonfinite_values(value: object) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(JSONValue).validate_python(value)
