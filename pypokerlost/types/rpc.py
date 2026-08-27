from __future__ import annotations

from typing import Annotated, Literal

from pydantic import StringConstraints

type HTTPMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
type RPCOperation = Annotated[
    str,
    StringConstraints(
        strict=True,
        pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$",
    ),
]
