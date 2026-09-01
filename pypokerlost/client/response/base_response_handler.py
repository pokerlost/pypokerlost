"""Abstract response handling contract."""

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
        retry_after: float | None = None,
    ) -> ResultT:
        """Validate protocol inputs and return the method's declared result."""

    def _handle_with_metadata[ResultT](
        self,
        *,
        method: PokerlostMethod[ResultT],
        operation: str,
        status_code: int,
        content: str,
        retry_after: float | None,
        returning: object,
    ) -> ResultT:
        """Use captured result metadata when supported by the concrete handler."""
        del returning
        return self.handle(
            method=method,
            operation=operation,
            status_code=status_code,
            content=content,
            retry_after=retry_after,
        )
