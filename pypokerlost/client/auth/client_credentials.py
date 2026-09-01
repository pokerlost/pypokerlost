"""Secret-safe OAuth2 confidential-client credentials."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr

type _ClientSecret = Annotated[SecretStr, Field(min_length=1)]


class ClientCredentials(BaseModel):
    """Hold a public client identifier and an undisclosed client secret."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
        hide_input_in_errors=True,
    )

    client_id: UUID
    client_secret: _ClientSecret = Field(repr=False, exclude=True)

    def __init__(
        self,
        *,
        client_id: UUID,
        client_secret: SecretStr,
    ) -> None:
        if not isinstance(client_secret, SecretStr):
            raise TypeError("Client secret must be a SecretStr")
        raw_secret = ""
        try:
            raw_secret = client_secret.get_secret_value()
            if not raw_secret:
                raise ValueError("Client secret must not be empty")
            try:
                raw_secret.encode()
            except UnicodeEncodeError:
                raise ValueError("Client secret must be valid UTF-8 text") from None
            super().__init__(client_id=client_id, client_secret=client_secret)
        finally:
            raw_secret = ""
            client_secret = None  # type: ignore[assignment]
