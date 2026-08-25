from enum import StrEnum


class ResponseKind(StrEnum):
    """Wire-level response kinds exposed through OpenAPI metadata."""

    APPLICATION_RESPONSE = "application_response"
    CONTENT_STREAM = "content_stream"
