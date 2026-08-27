from typing import Annotated

from pydantic import StringConstraints

type StorageKey = Annotated[
    str,
    StringConstraints(
        strict=True,
        min_length=1,
        pattern=r"\S",
    ),
]
