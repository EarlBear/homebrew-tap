"""Pygments lexer for Mermaid diagram source.

Mermaid has no built-in Pygments lexer (and no maintained PyPI package), so
this module provides a hand-written one. It covers the constructs that show
up in real-world flowcharts and sequence diagrams:

- Diagram type keywords (graph, flowchart, sequenceDiagram, classDiagram,
  stateDiagram, erDiagram, gantt, pie, journey, mindmap, timeline, etc.)
- Direction tokens (TD, TB, LR, RL, BT)
- Edge operators (-->, ---, -.->, ==>, ~~~, o--o, x--x)
- Edge labels |text|
- Node shapes [...], (...), ((...)), {...}, >...]
- Subgraph / end blocks
- style / classDef / class / linkStyle / click directives
- Comments (%% ... end of line)

Use ``MermaidLexer`` as a normal Pygments lexer. The convenience
``register()`` function plugs it into Pygments' lexer registry under the
names 'mermaid' and 'mmd' so ``get_lexer_by_name`` can find it.
"""

from __future__ import annotations

from pygments.lexer import RegexLexer, bygroups, include, words
from pygments.token import (
    Comment,
    Generic,
    Keyword,
    Name,
    Number,
    Operator,
    Punctuation,
    String,
    Text,
    Whitespace,
)

__all__ = ["MermaidLexer"]


# Diagram type keywords (top of every Mermaid diagram)
_DIAGRAM_TYPES = (
    "graph", "flowchart",
    "sequenceDiagram",
    "classDiagram", "classDiagram-v2",
    "stateDiagram", "stateDiagram-v2",
    "erDiagram",
    "journey",
    "gantt",
    "pie",
    "mindmap",
    "timeline",
    "quadrantChart",
    "requirementDiagram",
    "gitGraph",
    "C4Context", "C4Container", "C4Component", "C4Dynamic", "C4Deployment",
    "sankey-beta",
    "block-beta",
    "packet-beta",
    "architecture-beta",
    "xychart-beta",
)

# Direction tokens used after diagram type
_DIRECTIONS = ("TD", "TB", "BT", "LR", "RL")

# Structural keywords inside diagrams
_KEYWORDS = (
    "subgraph", "end",
    "direction",
    "style", "classDef", "class", "linkStyle",
    "click",
    "participant", "actor",
    "note", "loop", "alt", "else", "opt", "par", "and", "rect",
    "activate", "deactivate",
    "autonumber",
    "section",
    "title",
    "accTitle", "accDescr",
    "dateFormat", "axisFormat", "tickInterval",
    "excludes", "includes",
    "todayMarker",
    "state",
    "namespace",
)


class MermaidLexer(RegexLexer):
    """Pygments lexer for Mermaid diagram source code.

    Aliases: mermaid, mmd
    Filenames: *.mmd, *.mermaid
    """

    name = "Mermaid"
    aliases = ["mermaid", "mmd"]
    filenames = ["*.mmd", "*.mermaid"]
    mimetypes = ["text/x-mermaid"]

    tokens = {
        "root": [
            # Comments
            (r"%%[^\n]*", Comment.Single),

            # Whitespace
            (r"\s+", Whitespace),

            # Diagram type keywords (must come first to take priority over identifiers)
            (words(_DIAGRAM_TYPES, suffix=r"\b"), Keyword.Namespace),

            # Direction tokens
            (words(_DIRECTIONS, suffix=r"\b"), Keyword.Constant),

            # Structural keywords
            (words(_KEYWORDS, suffix=r"\b"), Keyword),

            # Edge operators (must come before generic punctuation)
            (r"<?-+\.+-+>?", Operator),         # -.-, -.->, <-.-
            (r"<?={2,}>?", Operator),            # ==>, <==>, ===
            (r"<?-+>?", Operator),               # ->, -->, --->, ---, <-->
            (r"~~~+", Operator),                 # ~~~ (link with no shaft)
            (r"o--o|x--x", Operator),            # circular / cross edges
            (r"o-+", Operator),
            (r"-+o", Operator),
            (r"x-+", Operator),
            (r"-+x", Operator),

            # Edge labels: |text|
            (r"\|", Punctuation, "edge_label"),

            # Strings (quoted node labels)
            (r'"[^"]*"', String.Double),
            (r"'[^']*'", String.Single),

            # Node shapes — match the bracket characters as punctuation,
            # then capture the inner text as a Name
            (r"\[\[", Punctuation),              # [[ subroutine
            (r"\]\]", Punctuation),
            (r"\(\(\(", Punctuation),
            (r"\)\)\)", Punctuation),
            (r"\(\(", Punctuation),
            (r"\)\)", Punctuation),
            (r"\(\[", Punctuation),
            (r"\]\)", Punctuation),
            (r"\(\\", Punctuation),
            (r"\\\)", Punctuation),
            (r"\(/", Punctuation),
            (r"/\)", Punctuation),
            (r"\[/", Punctuation),
            (r"/\]", Punctuation),
            (r"\[\\", Punctuation),
            (r"\\\]", Punctuation),
            (r">", Punctuation),                 # > asymmetric shape
            (r"[\[\](){}]", Punctuation),

            # Style directives like fill:#fff, stroke:#000
            (r":::\w+", Name.Attribute),         # ::class shorthand
            (r"#[0-9a-fA-F]{3,8}\b", Number.Hex),

            # Numbers
            (r"\d+(\.\d+)?", Number),

            # Identifiers (node IDs, etc.)
            (r"[A-Za-z_][\w-]*", Name),

            # Misc punctuation
            (r"[,;:.]", Punctuation),
            (r"&", Operator),
            (r"=", Operator),

            # Anything else — pass through as text
            (r".", Text),
        ],
        "edge_label": [
            (r"\|", Punctuation, "#pop"),
            (r"[^|]+", String.Symbol),
        ],
    }


_REGISTERED = False


def register() -> None:
    """Register the Mermaid lexer with Pygments so get_lexer_by_name works.

    Idempotent — safe to call multiple times.
    """
    global _REGISTERED
    if _REGISTERED:
        return
    try:
        from pygments.lexers import _lexer_cache, find_lexer_class_by_name
        # Check if a built-in lexer already exists for these aliases
        try:
            find_lexer_class_by_name("mermaid")
            _REGISTERED = True
            return
        except Exception:
            pass

        # Inject our lexer into the registry. Pygments uses _lexer_cache as
        # an alias→class map populated lazily.
        from pygments.lexers._mapping import LEXERS
        LEXERS["MermaidLexer"] = (
            "ebdocs.mermaid_lexer",  # module
            "Mermaid",                # name
            ("mermaid", "mmd"),       # aliases
            ("*.mmd", "*.mermaid"),   # filenames
            ("text/x-mermaid",),      # mimetypes
        )
        # Clear any cached lookups so the new entry is picked up
        _lexer_cache.clear()
        _REGISTERED = True
    except Exception:
        # Best effort — if registry injection fails, syntax_highlight will
        # fall back to "no lexer found" for mmd blocks (still gets monospace
        # + cell shading from the table treatment).
        pass
