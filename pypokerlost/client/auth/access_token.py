"""Secret-safe access token returned by an outbound token provider."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

type _ExpiresIn = Annotated[int, Field(strict=True, gt=0)]


class AccessToken(BaseModel):
    """Hold one bearer token and its validated acquisition metadata."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
        hide_input_in_errors=True,
    )

    value: SecretStr = Field(repr=False, exclude=True, min_length=1)
    token_type: Literal["bearer"] = "bearer"
    expires_in: _ExpiresIn
    scopes: tuple[str, ...]

    def __init__(
        self,
        *,
        value: SecretStr,
        token_type: Literal["bearer"] = "bearer",
        expires_in: int,
        scopes: tuple[str, ...],
    ) -> None:
        if not isinstance(value, SecretStr):
            raise TypeError("Access token value must be a SecretStr")
        raw_value = ""
        try:
            raw_value = value.get_secret_value()
            if any(not 0x21 <= ord(character) <= 0x7E for character in raw_value):
                raise ValueError("Access token must contain visible ASCII characters only")
            super().__init__(
                value=value,
                token_type=token_type,
                expires_in=expires_in,
                scopes=scopes,
            )
        finally:
            raw_value = ""
            value = None  # type: ignore[assignment]
