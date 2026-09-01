"""Bearer header enrichment through a secret-safe access-token provider."""

from __future__ import annotations

from pypokerlost.client.auth import AccessTokenProvider
from pypokerlost.exceptions import MiddlewareConfigurationError

from .base_middleware import APIMiddleware, APIMiddlewareCallNext
from .context import APIMiddlewareContext


class BearerTokenMiddleware(APIMiddleware):
    """Add one provider-owned bearer token without replaying failures."""

    def __init__(self, token_provider: AccessTokenProvider) -> None:
        self._token_provider = token_provider

    async def start(self) -> None:
        await self._token_provider.start()

    async def close(self) -> None:
        await self._token_provider.close()

    async def __call__[ResultT](
        self,
        call_next: APIMiddlewareCallNext[ResultT],
        context: APIMiddlewareContext,
    ) -> ResultT:
        token = None
        options = None
        try:
            if any(name.casefold() == "authorization" for name, _ in context.options.headers):
                raise MiddlewareConfigurationError("Authorization header is already configured")

            token = await self._token_provider.get_access_token()
            options = context.options.with_headers(
                {
                    "Authorization": f"Bearer {token.value.get_secret_value()}",
                },
            )
            return await call_next(options=options)
        finally:
            token = None
            options = None
            context = None  # type: ignore[assignment]
