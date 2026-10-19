"""Result for the future-facing issueLoginGrant operation."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class IssueLoginGrantResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        hide_input_in_errors=True,
    )

    login_grant: Annotated[
        str,
        StringConstraints(strict=True, min_length=1),
    ] = Field(repr=False)
    expires_in: Annotated[int, Field(strict=True, gt=0)]
