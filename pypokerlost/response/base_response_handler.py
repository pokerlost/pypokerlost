from __future__ import annotations

import abc
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pypokerlost.methods import PokerlostMethod


class BaseResponseHandler(abc.ABC):
    """Interpret one application response without transport dependencies."""

    @abc.abstractmethod
    def handle[ResultT](
        self,
        *,
        method: PokerlostMethod[ResultT],
        operation: str,
        status_code: int,
        content: str,
    ) -> ResultT:
        """Validate protocol inputs and return the method's declared result."""
