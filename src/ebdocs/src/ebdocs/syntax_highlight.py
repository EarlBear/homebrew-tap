"""Syntax highlighting for code blocks pushed to Google Docs.

Uses Pygments to tokenize source code and produce a list of (start, end, color)
spans that the sync engine converts into Docs API updateTextStyle requests.

The token theme is intentionally simple — neutral colors that read well on a
light gray cell background. Customizing the palette is a one-line change in
TOKEN_COLORS.

Languages auto-detected via the fence info string (```python, ```bash, etc.).
Unknown languages fall back to plain monospace with no coloring.
"""

from __future__ import annotations

from dataclasses import dataclass

try:
    from pygments import lex
    from pygments.lexers import get_lexer_by_name, guess_lexer
    from pygments.token import (
        Comment,
        Error,
        Generic,
        Keyword,
        Literal,
        Name,
        Number,
        Operator,
        Other,
        Punctuation,
        String,
        Token,
        Whitespace,
    )
    from pygments.util import ClassNotFound
    PYGMENTS_AVAILABLE = True

    # Register the custom Mermaid lexer so 'mermaid' and 'mmd' resolve.
    try:
        from ebdocs.mermaid_lexer import register as _register_mermaid
        _register_mermaid()
    except Exception:
        pass
except ImportError:
    PYGMENTS_AVAILABLE = False


# Foreground colors as 0.0–1.0 RGB tuples (Docs API expects floats).
# Tuned for legibility on a light gray-blue cell background (~#F2F2F7).
# Inspired by GitHub's light theme.
_BLUE = (0.07, 0.34, 0.62)        # #1255A0 — keywords
_PURPLE = (0.42, 0.16, 0.62)      # #6B299E — operators, decorators
_GREEN = (0.04, 0.45, 0.18)       # #0A732E — strings
_RED = (0.65, 0.10, 0.18)         # #A6192F — built-ins, error
_TEAL = (0.00, 0.45, 0.50)        # #007380 — numbers
_BROWN = (0.50, 0.30, 0.10)       # #804C19 — class names
_GRAY = (0.42, 0.45, 0.50)        # #6B7280 — comments
_DARK = (0.18, 0.20, 0.24)        # #2E333D — default text


# Token-type → color mapping. Pygments tokens have hierarchy
# (e.g. Token.Keyword.Namespace inherits from Token.Keyword), so we
# walk up the parent chain to find a match.
_TOKEN_COLORS: list[tuple] = []  # populated lazily after import


def _build_token_colors() -> None:
    global _TOKEN_COLORS
    if not PYGMENTS_AVAILABLE or _TOKEN_COLORS:
        return
    _TOKEN_COLORS = [
        (Comment, _GRAY),
        (Keyword, _BLUE),
        (Operator, _PURPLE),
        (Name.Builtin, _RED),
        (Name.Class, _BROWN),
        (Name.Function, _BROWN),
        (Name.Decorator, _PURPLE),
        (Name.Namespace, _BROWN),
        (String, _GREEN),
        (Number, _TEAL),
        (Literal, _TEAL),
        (Error, _RED),
        (Generic.Heading, _BLUE),
        (Generic.Subheading, _BLUE),
        (Generic.Inserted, _GREEN),
        (Generic.Deleted, _RED),
    ]


@dataclass
class HighlightSpan:
    """A colored span within a code string."""
    start: int  # character offset (inclusive)
    end: int    # character offset (exclusive)
    color: tuple  # (r, g, b) floats 0.0–1.0


def _color_for_token(token_type) -> tuple | None:
    """Walk a token type up its parent chain to find a matching color."""
    _build_token_colors()
    current = token_type
    while current is not None:
        for tt, color in _TOKEN_COLORS:
            if current is tt:
                return color
        current = current.parent if hasattr(current, "parent") else None
    return None


def highlight(code: str, language: str) -> list[HighlightSpan]:
    """Tokenize code and return colored spans.

    Args:
        code: Source code as a string.
        language: Pygments language name (e.g. 'python', 'bash', 'json').
                  Empty string or unknown language → returns empty list.

    Returns:
        List of HighlightSpan objects. Default-colored tokens (text, whitespace)
        are NOT included — only tokens that should be visually distinct.
        Empty list if pygments is unavailable or language is unknown.
    """
    if not PYGMENTS_AVAILABLE or not code or not language:
        return []

    try:
        lexer = get_lexer_by_name(language, stripall=False)
    except ClassNotFound:
        return []

    spans: list[HighlightSpan] = []
    offset = 0
    for token_type, value in lex(code, lexer):
        length = len(value)
        if length == 0:
            continue
        # Skip pure whitespace
        if token_type in (Whitespace,) or (not value.strip()):
            offset += length
            continue
        color = _color_for_token(token_type)
        if color is not None:
            spans.append(HighlightSpan(
                start=offset,
                end=offset + length,
                color=color,
            ))
        offset += length
    return spans


def is_supported(language: str) -> bool:
    """Return True if pygments has a lexer for the given language."""
    if not PYGMENTS_AVAILABLE or not language:
        return False
    try:
        get_lexer_by_name(language, stripall=False)
        return True
    except ClassNotFound:
        return False
