#!/usr/bin/env python3
"""Enforce repository-local Markdown reference policy."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRECTORIES = frozenset(
    {
        ".agents",
        ".codex",
        ".git",
        ".mypy_cache",
        ".ruff_cache",
        ".venv",
        "build",
        "dist",
    }
)
INLINE_LINK_PATTERN = re.compile(r"!?\[[^\]\n]*\]\(([^)\n]+)\)")
REFERENCE_LINK_PATTERN = re.compile(r"^\s{0,3}\[[^\]\n]+\]:\s*(\S+)", flags=re.MULTILINE)
LOCAL_PATH_PATTERN = re.compile(
    r"(?:^|[\s`(])(?:/home/|/tmp/|~/|[A-Za-z]:[\\/])",
    flags=re.MULTILINE,
)
ALLOWED_LINK_SCHEMES = frozenset({"http", "https", "mailto"})


def _documents() -> tuple[Path, ...]:
    return tuple(
        path
        for path in sorted(REPOSITORY_ROOT.rglob("*.md"))
        if not EXCLUDED_DIRECTORIES.intersection(path.relative_to(REPOSITORY_ROOT).parts)
    )


def _prose_text(text: str) -> str:
    lines: list[str] = []
    fence_marker: str | None = None
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        marker = (
            "```" if stripped.startswith("```") else "~~~" if stripped.startswith("~~~") else None
        )
        if marker is not None:
            if fence_marker is None:
                fence_marker = marker
            elif fence_marker == marker:
                fence_marker = None
            lines.append("\n" if line.endswith("\n") else "")
            continue
        lines.append(line if fence_marker is None else "\n" if line.endswith("\n") else "")
    return "".join(lines)


def _normalized_destination(raw_destination: str) -> str:
    destination = raw_destination.strip()
    if destination.startswith("<"):
        closing = destination.find(">")
        return destination[1:closing] if closing >= 0 else destination
    return destination.split(maxsplit=1)[0]


def _validate_destination(destination: str) -> str | None:
    if destination.startswith("#"):
        return None

    try:
        parsed = urlsplit(destination)
    except ValueError:
        return "invalid link destination"
    if parsed.scheme in ALLOWED_LINK_SCHEMES:
        if parsed.scheme in {"http", "https"} and not parsed.netloc:
            return "HTTP(S) link must contain a host"
        return None
    if parsed.scheme:
        return f"unsupported link scheme {parsed.scheme!r}"
    return "relative inter-file Markdown links are forbidden"


def _validate_document(path: Path) -> list[str]:
    relative_path = path.relative_to(REPOSITORY_ROOT)
    text = path.read_text(encoding="utf-8")
    prose = _prose_text(text)
    errors: list[str] = []

    for pattern in (INLINE_LINK_PATTERN, REFERENCE_LINK_PATTERN):
        for match in pattern.finditer(prose):
            destination = _normalized_destination(match.group(1))
            problem = _validate_destination(destination)
            if problem is not None:
                line_number = prose.count("\n", 0, match.start()) + 1
                errors.append(f"{relative_path}:{line_number}: {problem}: {destination!r}")

    local_path = LOCAL_PATH_PATTERN.search(text)
    if local_path is not None:
        line_number = text.count("\n", 0, local_path.start()) + 1
        errors.append(
            f"{relative_path}:{line_number}: contains a workstation-specific absolute path"
        )
    return errors


def main() -> int:
    """Return a process status after checking every repository Markdown file."""
    documents = _documents()
    errors = [error for path in documents for error in _validate_document(path)]
    if errors:
        print("Documentation validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Documentation validation passed for {len(documents)} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
