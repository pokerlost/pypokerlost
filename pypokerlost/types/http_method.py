from enum import StrEnum


class HttpMethod(StrEnum):
    """HTTP methods supported by declarative SDK method metadata."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
