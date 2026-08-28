#!/usr/bin/env python3
"""Validate the repository documentation structure and local links."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ROOT_DOCUMENTS = (
    REPOSITORY_ROOT / "README.md",
    REPOSITORY_ROOT / "AGENTS.md",
    REPOSITORY_ROOT / "SERVICE.md",
)
ALLOWED_FENCE_LANGUAGES = frozenset(
    {
        "bash",
        "cmake",
        "cpp",
        "json",
        "python",
        "text",
        "toml",
        "yaml",
    }
)
H1_PATTERN = re.compile(r"^#\s+\S")
LINK_PATTERN = re.compile(r"(?<!!)\[[^\]\n]+\]\(([^)\n]+)\)")
LOCAL_PATH_PATTERN = re.compile(r"(?:^|[\s`(])(?:/home/|/tmp/|~/)")


def _documents() -> tuple[Path, ...]:
    docs = tuple(sorted((REPOSITORY_ROOT / "docs").rglob("*.md")))
    return (*ROOT_DOCUMENTS, *docs)


def _validate_opening(path: Path, lines: list[str]) -> list[str]:
    h1_indexes = [index for index, line in enumerate(lines) if H1_PATTERN.match(line)]
    if len(h1_indexes) != 1:
        return [f"{path}: expected exactly one H1, found {len(h1_indexes)}"]

    for line in lines[h1_indexes[0] + 1 :]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("#", "- ", "* ", "```", "|")):
            return [f"{path}: H1 must be followed by an introductory paragraph"]
        return []
    return [f"{path}: H1 has no introductory paragraph"]


def _validate_fences(path: Path, lines: list[str]) -> list[str]:
    errors: list[str] = []
    open_language: str | None = None
    for line_number, line in enumerate(lines, start=1):
        if not line.startswith("```"):
            continue
        marker = line.removeprefix("```").strip()
        if open_language is None:
            if marker not in ALLOWED_FENCE_LANGUAGES:
                errors.append(
                    f"{path}:{line_number}: unsupported or missing fence language {marker!r}",
                )
            open_language = marker
        elif marker:
            errors.append(f"{path}:{line_number}: closing fence must not declare a language")
        else:
            open_language = None
    if open_language is not None:
        errors.append(f"{path}: unclosed {open_language!r} code fence")
    return errors


def _prose_lines(lines: list[str]) -> list[str]:
    prose: list[str] = []
    inside_fence = False
    for line in lines:
        if line.startswith("```"):
            inside_fence = not inside_fence
            continue
        if not inside_fence:
            prose.append(line)
    return prose


def _link_target(path: Path, destination: str) -> Path | None:
    normalized = destination.strip().split(maxsplit=1)[0].strip("<>")
    parsed = urlsplit(normalized)
    if parsed.scheme or parsed.netloc or normalized.startswith("#"):
        return None
    relative_path = unquote(parsed.path)
    if not relative_path:
        return None
    return (path.parent / relative_path).resolve()


def _validate_links(path: Path, text: str) -> list[str]:
    errors: list[str] = []
    for destination in LINK_PATTERN.findall(text):
        target = _link_target(path, destination)
        if target is not None and not target.exists():
            errors.append(f"{path}: unresolved relative link {destination!r}")
    return errors


def _validate_document(path: Path) -> list[str]:
    relative_path = path.relative_to(REPOSITORY_ROOT)
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    prose_lines = _prose_lines(lines)
    errors = [
        *_validate_opening(relative_path, prose_lines),
        *_validate_fences(relative_path, lines),
        *_validate_links(path, "\n".join(prose_lines)),
    ]
    if LOCAL_PATH_PATTERN.search(text):
        errors.append(f"{relative_path}: contains a workstation-specific absolute path")
    return errors


def main() -> int:
    """Return a process status after validating every canonical Markdown page."""
    documents = _documents()
    errors = [error for path in documents for error in _validate_document(path)]
    if errors:
        print("Documentation validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Documentation validation passed for {len(documents)} pages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
