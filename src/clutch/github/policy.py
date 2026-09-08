"""Deterministic allowlist and binary checks for untrusted GitHub content."""

from __future__ import annotations

import base64
import binascii
from pathlib import PurePosixPath

ALLOWED_EXTENSIONS = frozenset(
    {".json", ".md", ".py", ".pyi", ".toml", ".txt", ".yaml", ".yml"}
)


def is_safe_repository_path(path: str) -> bool:
    """Reject traversal, absolute, backslash, NUL, and control-character paths."""

    if not path or len(path) > 1_000 or path.startswith("/"):
        return False
    if "\\" in path or "\x00" in path:
        return False
    if any(ord(character) < 32 for character in path):
        return False
    parsed = PurePosixPath(path)
    return all(part not in {"", ".", ".."} for part in parsed.parts)


def is_supported_text_path(path: str) -> bool:
    return is_safe_repository_path(path) and PurePosixPath(path).suffix.lower() in (
        ALLOWED_EXTENSIONS
    )


def decode_base64_text(value: str) -> str | None:
    """Return UTF-8 text only; binary, malformed, and NUL content is rejected."""

    try:
        decoded = base64.b64decode(value, validate=True)
        text = decoded.decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None
    if "\x00" in text:
        return None
    return text


def is_text_patch(value: str) -> bool:
    return "\x00" not in value
