"""Decode AutoCAD text escape sequences."""

from __future__ import annotations

import re

from .fonts import ShxFont

PERCENT_ESCAPES = {"c": "Ø", "d": "°", "p": "±", "%": "%", "u": "", "o": ""}


def decode_text(value: str, font: ShxFont | None = None) -> str:
    """Decode Unicode, bigfont, and percent escapes without altering formatting codes."""
    def unicode_repl(match: re.Match[str]) -> str:
        return chr(int(match.group(1), 16))

    def bigfont_repl(match: re.Match[str]) -> str:
        code = int(match.group(1), 16)
        if font and (character := font.get_char(code)):
            return character
        try:
            codec = font.encoding if font and font.encoding != "unknown" else "gbk"
            return bytes(((code >> 8) & 0xFF, code & 0xFF)).decode(codec)
        except (UnicodeDecodeError, LookupError):
            return match.group(0)

    def percent_repl(match: re.Match[str]) -> str:
        token = match.group(1)
        if token.lower() in PERCENT_ESCAPES:
            return PERCENT_ESCAPES[token.lower()]
        if token.isdigit() and int(token) < 256:
            return chr(int(token))
        return match.group(0)

    value = re.sub(r"\\U\+([0-9A-Fa-f]{4,8})", unicode_repl, value)
    value = re.sub(r"\\M\+5([0-9A-Fa-f]{4})", bigfont_repl, value)
    return re.sub(r"%%([A-Za-z%]|\d{1,3})", percent_repl, value)


def clean_mtext(value: str) -> str:
    value = value.replace(r"\P", "\n").replace(r"\p", "\n").replace("~", " ")
    value = value.replace("{", "").replace("}", "")
    value = re.sub(r"\\[A-Za-z][^;\\\n]*;?", "", value)
    value = re.sub(r"[ \t]+", " ", value)
    return re.sub(r"\n\s*\n+", "\n", value).strip()

