from typing import Final

_ELLIPSIS: Final = "…"
_OPERATION_LIMIT: Final = 128
_DETAIL_LIMIT: Final = 256
_RESPONSE_EXCERPT_LIMIT: Final = 512
_SENSITIVE_MARKERS: Final = (
    "authorization",
    "bearer ",
    "cookie",
    "password",
    "private_key",
    "private key",
    "secret",
    "token",
)


def safe_operation(operation: str | None) -> str | None:
    if operation is None:
        return None
    return _bounded_single_line(operation, limit=_OPERATION_LIMIT)


def safe_detail(detail: str | None) -> str | None:
    if detail is None:
        return None
    bounded_detail = _bounded_single_line(detail, limit=_DETAIL_LIMIT)
    if _contains_sensitive_marker(bounded_detail):
        return "<redacted sensitive detail>"
    return bounded_detail


def safe_response_excerpt(response_body: bytes | str) -> str:
    if isinstance(response_body, bytes):
        excerpt = response_body[: _RESPONSE_EXCERPT_LIMIT + 1].decode(
            encoding="utf-8",
            errors="replace",
        )
    else:
        excerpt = response_body[: _RESPONSE_EXCERPT_LIMIT + 1]

    excerpt = _bounded_single_line(excerpt, limit=_RESPONSE_EXCERPT_LIMIT)
    if _contains_sensitive_marker(excerpt):
        return "<redacted sensitive response body>"
    return excerpt


def _bounded_single_line(value: str, *, limit: int) -> str:
    bounded_value = value[: limit + 1]
    printable_value = "".join(
        character if character.isprintable() else " " for character in bounded_value
    )
    return _truncate(" ".join(printable_value.split()), limit=limit)


def _truncate(value: str, *, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: limit - 1]}{_ELLIPSIS}"


def _contains_sensitive_marker(value: str) -> bool:
    folded_value = value.casefold()
    return any(marker in folded_value for marker in _SENSITIVE_MARKERS)
