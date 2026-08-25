from __future__ import annotations

from pypokerlost import TransportError, UnexpectedStatusError


def test_unexpected_status_error_bounds_response_diagnostics() -> None:
    error = UnexpectedStatusError(
        500,
        operation="tests.echo",
        response_body=b"x" * 2_000,
    )

    assert error.status_code == 500
    assert error.operation == "tests.echo"
    assert len(error.response_excerpt) <= 512
    assert "x" * 1_000 not in str(error)


def test_sensitive_error_details_are_not_exposed() -> None:
    status_error = UnexpectedStatusError(
        401,
        operation="tests.echo",
        response_body=b"Authorization: Bearer highly-sensitive-value",
    )
    transport_error = TransportError(
        operation="tests.echo",
        detail="token=highly-sensitive-value",
    )

    assert "highly-sensitive-value" not in str(status_error)
    assert "highly-sensitive-value" not in str(transport_error)
