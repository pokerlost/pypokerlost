from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from pypokerlost.enums import ServiceName

if TYPE_CHECKING:
    from pypokerlost.methods import PokerlostMethod


class BaseResponseHandler(ABC):
    """Interpret one application response without transport dependencies."""

    @abstractmethod
    def handle[ResultT](
        self,
        *,
        method: PokerlostMethod[ResultT],
        service: ServiceName,
        operation: str,
        status_code: int,
        content: str,
    ) -> ResultT:
        """Validate protocol inputs and return the method's declared result."""
