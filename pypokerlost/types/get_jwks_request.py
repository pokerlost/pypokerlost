"""Payload for the future-facing getJwks operation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class GetJwksRequest(BaseModel):
    """Explicit empty JSON payload for public key publication."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
