from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING, Any, ClassVar

from pypokerlost.client.current_client import get_current_client
from pypokerlost.methods.base_method import BaseMethod

if TYPE_CHECKING:
    from pypokerlost.client.client import Client


class Method[ResultT](BaseMethod):
    """Immutable, awaitable description of an ordinary typed RPC operation."""

    result_type: ClassVar[Any]

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        if "operation" not in cls.__dict__:
            return
        cls._validate_method_class()
        if not hasattr(cls, "result_type"):
            msg = "Concrete ordinary methods must declare result_type"
            raise TypeError(msg)

    def model_post_init(self, context: Any, /) -> None:
        super().model_post_init(context)
        if not hasattr(type(self), "result_type"):
            msg = "Concrete ordinary methods must declare result_type"
            raise TypeError(msg)

    async def execute(self, client: Client | None = None) -> ResultT:
        """Execute through an explicit client or the task-local current client."""
        resolved_client = client if client is not None else get_current_client()
        return await resolved_client.make_request(self)

    def __await__(self) -> Generator[Any, None, ResultT]:
        return self.execute().__await__()
