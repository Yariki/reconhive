"""Safe text handling for untrusted network protocol data."""
from __future__ import annotations

from typing import Any

_PRESERVED_CONTROLS = {"\t", "\n", "\r"}


def sanitize_text(value: str | None) -> str | None:
    """Escape control bytes PostgreSQL text cannot store or users cannot read.

    PostgreSQL rejects U+0000 outright. Other C0 controls are legal but make
    banners and logs difficult to inspect, so they are represented as visible
    ``\\xNN`` sequences. Newlines, carriage returns, and tabs are preserved.
    """
    if value is None:
        return None

    safe: list[str] = []
    for char in value:
        codepoint = ord(char)
        if char in _PRESERVED_CONTROLS or (codepoint >= 32 and codepoint != 127):
            safe.append(char)
        elif codepoint <= 0xFF:
            safe.append(f"\\x{codepoint:02x}")
        else:
            safe.append(f"\\u{codepoint:04x}")
    return "".join(safe)


def decode_banner(data: bytes) -> str | None:
    """Decode an arbitrary protocol banner into safe, readable UTF-8 text."""
    decoded = data.decode("utf-8", errors="replace")
    return (sanitize_text(decoded) or "").strip() or None


def sanitize_json(value: Any) -> Any:
    """Recursively sanitize strings before writing them to PostgreSQL JSONB."""
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, dict):
        return {sanitize_text(str(key)): sanitize_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize_json(item) for item in value]
    return value
