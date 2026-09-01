"""Pokerlost API-declared failure."""

from __future__ import annotations

from .pokerlost_client_error import PokerlostClientError


class PokerlostAPIError(PokerlostClientError):
    """A canonical failed PokerlostResponse with safe scalar metadata only."""

    operation: str
    status_code: int
    error: str
    error_message: str | None
    retry_after: float | None

    def __init__(
        self,
        *,
        operation: str,
        status_code: int,
        error: str,
        error_message: str | None,
        retry_after: float | None,
    ) -> None:
        self.operation = operation
        self.status_code = status_code
        self.error = error
        self.error_message = error_message
        self.retry_after = retry_after
        message = (
            f"Pokerlost API error {error!r}; operation={operation!r}; status_code={status_code}"
        )
        if error_message is not None:
            message = f"{message}; message={error_message}"
        super().__init__(message)
