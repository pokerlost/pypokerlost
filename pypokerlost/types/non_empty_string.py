from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints

type NonEmptyString = Annotated[
    str,
    StringConstraints(
        strict=True,
        min_length=1,
        pattern=r"\S",
    ),
]
