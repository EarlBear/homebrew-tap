"""Markdown-to-Google-Docs batchUpdate converter.

Converts markdown text into a list of Google Docs API batchUpdate requests.
Also provides docs_to_markdown() for reading documents back as markdown.

The Google Docs API uses 1-based character offsets for insertions.
Requests are built in reverse order to avoid index shifting.

Supported markdown elements:
- H1-H3 (# ## ###)
- Bold (**text**)
- Italic (*text* or _text_)
- Mixed formatting (**bold _italic_**)
- Unordered lists (- item or * item)
- Ordered lists (1. item)
- Nested lists (any depth)
- Inline code (`code`) — rendered in Courier New
- Fenced code blocks (```...```) — rendered in Courier New
- Links ([text](url)) — rendered as hyperlinks
- Horizontal rules (---) — rendered as section breaks
- Page breaks (---pagebreak---) — rendered as page breaks
- Table of contents ([TOC]) — rendered as insertTableOfContents
- Tables (pipe tables) — parsed for two-pass insertion
- Footnotes ([^1] / [^1]: content) — rendered as createFootnote
- HTML entities (&amp; etc.) — decoded by markdown-it
- Plain text paragraphs
- Paragraph breaks (blank lines)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from markdown_it import MarkdownIt

MONOSPACE_FONT = "Courier New"

# Regex patterns for custom block-level elements
_PAGEBREAK_RE = re.compile(r"^---pagebreak---$", re.MULTILINE)
_TOC_RE = re.compile(r"^\[TOC\]$", re.MULTILINE)
_TABLE_ROW_RE = re.compile(r"^\|(.+)\|$")
_TABLE_SEP_RE = re.compile(r"^\|[-\s|:]+\|$")
_FOOTNOTE_REF_RE = re.compile(r"\[\^(\w+)\]")
_TASK_MARKER_RE = re.compile(r"^\[([ xX])\]\s+")
_FOOTNOTE_DEF_RE = re.compile(r"^\[\^(\w+)\]:\s*(.+)$", re.MULTILINE)

# Jira issue key auto-linkification. Any standalone EARL-<num> mention in body
# text is converted into a hyperlink to the issue in Jira Cloud. The [EARL-NNN]
# bracketed form used in source (from markdown shortcut references that have no
# definition) is also matched so it becomes a link.
_JIRA_KEY_RE = re.compile(r"\b(EARL-\d+)\b")
_JIRA_BROWSE_BASE = "https://earlbear.atlassian.net/browse/"


@dataclass
class _Segment:
    """A segment of text with formatting metadata."""
    text: str
    bold: bool = False
    italic: bool = False
    monospace: bool = False
    link_url: str = ""
    strikethrough: bool = False


@dataclass
class _TableData:
    """A parsed pipe table."""
    headers: list[str]
    rows: list[list[str]]


@dataclass
class _Block:
    """A block element (paragraph, heading, list item)."""
    segments: list[_Segment] = field(default_factory=list)
    heading_level: int = 0  # 0 = paragraph, 1-3 = H1-H3
    is_list_item: bool = False
    is_ordered: bool = False
    list_nesting: int = 0  # 0-based nesting level
    is_task_list: bool = False
    task_checked: bool = False
    is_code_block: bool = False
    code_block_language: str = ""  # fence language tag (e.g. "python", "bash") for syntax highlighting
    is_horizontal_rule: bool = False
    is_page_break: bool = False
    is_toc: bool = False
    table: _TableData | None = None
    is_footnote_ref: bool = False  # placeholder inserted for footnote
    footnote_id: str = ""
    footnote_content: str = ""
    # Mermaid diagrams: rendered to PNG via mermaid.ink and inserted as inline image
    is_mermaid: bool = False
    mermaid_source: str = ""
    # Inline image (from markdown ![alt](path) syntax) — local file path resolved relative
    # to the source markdown file's directory. Pre-rendered mermaid blocks become these.
    is_image: bool = False
    image_path: str = ""
    image_alt: str = ""


def _preprocess_custom_blocks(content: str) -> tuple[str, dict[str, str]]:
    """Extract custom block-level elements before markdown-it parsing.

    Replaces page breaks, TOC markers, and tables with UUID placeholders
    so markdown-it doesn't mangle them. Also extracts footnote definitions.

    Returns:
        (preprocessed_content, placeholder_map)
    """
    import uuid
    placeholders: dict[str, str] = {}

    # Extract footnote definitions (must happen before general parsing)
    footnote_defs: dict[str, str] = {}
    for match in _FOOTNOTE_DEF_RE.finditer(content):
        fn_id = match.group(1)
        fn_content = match.group(2).strip()
        footnote_defs[fn_id] = fn_content
    # Remove footnote definition lines from content
    content = _FOOTNOTE_DEF_RE.sub("", content)
    # Store footnote defs in placeholders with a special prefix
    for fn_id, fn_content in footnote_defs.items():
        placeholders[f"__footnote_def__{fn_id}"] = fn_content

    # Replace ---pagebreak--- with placeholder
    def _replace_pagebreak(m: re.Match) -> str:
        key = f"__pagebreak__{uuid.uuid4().hex[:8]}"
        placeholders[key] = "pagebreak"
        return key

    content = _PAGEBREAK_RE.sub(_replace_pagebreak, content)

    # Replace [TOC] with placeholder
    def _replace_toc(m: re.Match) -> str:
        key = f"__toc__{uuid.uuid4().hex[:8]}"
        placeholders[key] = "toc"
        return key

    content = _TOC_RE.sub(_replace_toc, content)

    # Replace pipe tables with placeholders
    lines = content.split("\n")
    result_lines: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if _TABLE_ROW_RE.match(line):
            # Collect all contiguous table lines
            table_lines: list[str] = [line]
            j = i + 1
            while j < len(lines):
                next_line = lines[j].strip()
                if _TABLE_ROW_RE.match(next_line) or _TABLE_SEP_RE.match(next_line):
                    table_lines.append(next_line)
                    j += 1
                else:
                    break
            # Parse the table
            table = _parse_pipe_table(table_lines)
            if table:
                key = f"__table__{uuid.uuid4().hex[:8]}"
                placeholders[key] = "table"
                # Store table data as a special placeholder
                placeholders[f"{key}__data"] = _serialize_table(table)
                result_lines.append(key)
            else:
                # Not a valid table, keep original lines
                result_lines.extend(table_lines)
            i = j
        else:
            result_lines.append(lines[i])
            i += 1

    content = "\n".join(result_lines)
    return content, placeholders


def _parse_pipe_table(lines: list[str]) -> _TableData | None:
    """Parse pipe table lines into a TableData structure."""
    if len(lines) < 2:
        return None

    # First line is headers
    header_line = lines[0]
    headers = [cell.strip() for cell in header_line.strip("|").split("|")]

    # Second line should be separator (optional — some tables omit it)
    data_start = 1
    if len(lines) > 1 and _TABLE_SEP_RE.match(lines[1]):
        data_start = 2

    rows: list[list[str]] = []
    for line in lines[data_start:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        # Pad or truncate to match header count
        while len(cells) < len(headers):
            cells.append("")
        rows.append(cells[:len(headers)])

    return _TableData(headers=headers, rows=rows)


def _serialize_table(table: _TableData) -> str:
    """Serialize a table to a compact string for placeholder storage."""
    import json
    return json.dumps({"headers": table.headers, "rows": table.rows})


def _deserialize_table(data: str) -> _TableData:
    """Deserialize a table from placeholder storage."""
    import json
    d = json.loads(data)
    return _TableData(headers=d["headers"], rows=d["rows"])


def _parse_markdown(content: str) -> list[_Block]:
    """Parse markdown into a list of blocks using markdown-it."""
    # Preprocess custom block elements
    content, placeholders = _preprocess_custom_blocks(content)

    md = MarkdownIt("commonmark")
    tokens = md.parse(content)

    blocks: list[_Block] = []
    current_block: _Block | None = None
    in_ordered_list = False
    list_nesting = 0

    i = 0
    while i < len(tokens):
        token = tokens[i]

        if token.type == "heading_open":
            level = int(token.tag[1])  # h1 -> 1, h2 -> 2, etc.
            current_block = _Block(heading_level=min(level, 3))

        elif token.type == "heading_close":
            if current_block:
                blocks.append(current_block)
                current_block = None

        elif token.type == "paragraph_open":
            if current_block is None:
                current_block = _Block()

        elif token.type == "paragraph_close":
            if current_block:
                # Check if this paragraph contains a placeholder
                if len(current_block.segments) == 1:
                    text = current_block.segments[0].text.strip()
                    if text.startswith("__pagebreak__") and text in placeholders:
                        blocks.append(_Block(is_page_break=True))
                        current_block = None
                        i += 1
                        continue
                    elif text.startswith("__toc__") and text in placeholders:
                        blocks.append(_Block(is_toc=True))
                        current_block = None
                        i += 1
                        continue
                    elif text.startswith("__table__") and text in placeholders:
                        table_data_key = f"{text}__data"
                        if table_data_key in placeholders:
                            table = _deserialize_table(placeholders[table_data_key])
                            blocks.append(_Block(table=table))
                        current_block = None
                        i += 1
                        continue

                # Check for footnote references in segments and expand them
                new_segments: list[_Segment] = []
                has_footnotes = False
                for seg in current_block.segments:
                    parts = _FOOTNOTE_REF_RE.split(seg.text)
                    refs = _FOOTNOTE_REF_RE.findall(seg.text)
                    if refs:
                        has_footnotes = True
                        for pi, part in enumerate(parts):
                            if part:
                                new_segments.append(_Segment(
                                    text=part, bold=seg.bold, italic=seg.italic,
                                    monospace=seg.monospace, link_url=seg.link_url,
                                ))
                            # After each split part (except the last), insert a footnote ref
                            if pi < len(refs):
                                fn_id = refs[pi]
                                fn_content = placeholders.get(f"__footnote_def__{fn_id}", "")
                                # Footnote block marker (handled in request gen)
                                new_segments.append(_Segment(text=f"__fn__{fn_id}__"))
                                # Store footnote content for later
                                if fn_content:
                                    placeholders[f"__fn_content__{fn_id}"] = fn_content
                    else:
                        new_segments.append(seg)

                if has_footnotes:
                    current_block.segments = new_segments

                blocks.append(current_block)
                current_block = None

        elif token.type == "bullet_list_open":
            in_ordered_list = False
            list_nesting += 1

        elif token.type == "ordered_list_open":
            in_ordered_list = True
            list_nesting += 1

        elif token.type in ("bullet_list_close", "ordered_list_close"):
            list_nesting -= 1
            if list_nesting <= 0:
                list_nesting = 0
                in_ordered_list = False

        elif token.type == "list_item_open":
            current_block = _Block(
                is_list_item=True,
                is_ordered=in_ordered_list,
                list_nesting=max(0, list_nesting - 1),
            )

        elif token.type == "list_item_close":
            if current_block:
                blocks.append(current_block)
                current_block = None

        elif token.type == "fence":
            # Fenced code block (```...```)
            code_text = token.content
            # Strip trailing newline from code content if present
            if code_text.endswith("\n"):
                code_text = code_text[:-1]

            # Mermaid blocks are rendered to PNG and inserted as inline images.
            language = (token.info or "").strip().lower()
            if language == "mermaid":
                mermaid_block = _Block(is_mermaid=True, mermaid_source=code_text)
                blocks.append(mermaid_block)
            else:
                # All other fenced code blocks become single-cell tables in Drive
                # with optional pygments-driven syntax highlighting.
                code_block = _Block(is_code_block=True, code_block_language=language)
                code_block.segments.append(_Segment(text=code_text, monospace=True))
                blocks.append(code_block)

        elif token.type == "code_block":
            # Indented code block
            code_block = _Block(is_code_block=True)
            code_text = token.content
            if code_text.endswith("\n"):
                code_text = code_text[:-1]
            code_block.segments.append(_Segment(text=code_text, monospace=True))
            blocks.append(code_block)

        elif token.type == "hr":
            # Horizontal rule → section break
            blocks.append(_Block(is_horizontal_rule=True))

        elif token.type == "inline" and current_block is not None:
            _parse_inline(token, current_block)

        i += 1

    # Attach footnote content map to be used during request generation
    _parse_markdown._footnote_contents = {  # type: ignore[attr-defined]
        k.replace("__fn_content__", ""): v
        for k, v in placeholders.items()
        if k.startswith("__fn_content__")
    }

    return blocks


def _parse_inline(token: Any, block: _Block) -> None:
    """Parse inline tokens (bold, italic, text, code, links, images) into segments.

    Image tokens (![alt](path)) are special: if the inline contains exactly one
    image and nothing else (or only whitespace text), the parent paragraph block
    is marked as is_image with image_path/image_alt set. The block will be
    rendered as an inline image instead of text.
    """
    if not token.children:
        if token.content:
            block.segments.append(_Segment(text=token.content))
        return

    bold = False
    italic = False
    link_url = ""

    # Detect image-only paragraph: single image child with no surrounding non-whitespace text
    images = [c for c in token.children if c.type == "image"]
    text_children = [c for c in token.children if c.type == "text" and c.content.strip()]
    if len(images) == 1 and not text_children:
        img = images[0]
        attrs = img.attrs or {}
        block.is_image = True
        block.image_path = attrs.get("src", "")
        block.image_alt = img.content or attrs.get("alt", "")
        return

    for child in token.children:
        if child.type == "strong_open":
            bold = True
        elif child.type == "strong_close":
            bold = False
        elif child.type == "em_open":
            italic = True
        elif child.type == "em_close":
            italic = False
        elif child.type == "link_open":
            # Extract href from attrs
            link_url = ""
            if child.attrs:
                link_url = child.attrs.get("href", "")
        elif child.type == "link_close":
            link_url = ""
        elif child.type == "text":
            # Auto-linkify EARL-NNN mentions unless the text is already inside
            # an explicit link. Split around each match so the key itself gets
            # a link_url while surrounding text keeps current styling.
            if link_url or not _JIRA_KEY_RE.search(child.content):
                block.segments.append(_Segment(
                    text=child.content, bold=bold, italic=italic,
                    link_url=link_url,
                ))
            else:
                last = 0
                for m in _JIRA_KEY_RE.finditer(child.content):
                    if m.start() > last:
                        block.segments.append(_Segment(
                            text=child.content[last:m.start()],
                            bold=bold, italic=italic,
                        ))
                    block.segments.append(_Segment(
                        text=m.group(1),
                        bold=bold, italic=italic,
                        link_url=_JIRA_BROWSE_BASE + m.group(1),
                    ))
                    last = m.end()
                if last < len(child.content):
                    block.segments.append(_Segment(
                        text=child.content[last:],
                        bold=bold, italic=italic,
                    ))
        elif child.type == "softbreak":
            block.segments.append(_Segment(text="\n"))
        elif child.type == "code_inline":
            # Inline code → monospace font
            block.segments.append(_Segment(text=child.content, monospace=True))

    # Task-list detection: if this is a list item and the first segment with
    # non-empty text starts with `[ ] ` / `[x] `, strip the marker and set
    # the task flags. We detect via regex rather than the markdown-it tasklists
    # plugin to avoid an extra dependency.
    if block.is_list_item and block.segments:
        for idx, seg in enumerate(block.segments):
            if not seg.text:
                continue
            m = _TASK_MARKER_RE.match(seg.text)
            if m:
                block.is_task_list = True
                block.task_checked = m.group(1).lower() == "x"
                seg.text = seg.text[m.end():]
            break


def _heading_id(level: int) -> str:
    """Map heading level to Google Docs named style ID."""
    return {
        1: "HEADING_1",
        2: "HEADING_2",
        3: "HEADING_3",
    }.get(level, "NORMAL_TEXT")


def markdown_to_requests(content: str) -> list[dict]:
    """Convert markdown text to a list of Google Docs batchUpdate requests.

    The requests insert text starting at index 1 (beginning of the document body).
    They are ordered so that applying them in sequence produces the correct document.

    Build strategy: calculate all text first, then generate insert + format requests
    in reverse order so indices don't shift.

    Tables, TOC, and footnotes generate deferred requests that require a two-pass
    approach (insert structure, then fill). These are returned with special keys:
    - ``_deferredTable``: table insertion requiring cell population after creation
    - ``_deferredFootnote``: footnote requiring content insertion after creation

    Args:
        content: Markdown-formatted string.

    Returns:
        List of batchUpdate request dicts ready for the Docs API.
    """
    blocks = _parse_markdown(content)
    if not blocks:
        return []

    # Get footnote contents from parsing phase
    footnote_contents: dict[str, str] = getattr(
        _parse_markdown, "_footnote_contents", {}
    )

    # Phase 1: Build the full text and track segment positions.
    #
    # Docs API index subtleties:
    # - Indices are UTF-16 code units (emoji outside BMP count as 2 units).
    # - createParagraphBullets strips leading tabs from list items, shrinking
    #   the body by 1 unit per consumed tab.
    #
    # We track positions in "pre-strip" (UTF-16, tabs-included) space. Then
    # at request-emission time we convert to "post-strip" for any request that
    # runs AFTER createParagraphBullets in the batch (all text-style requests,
    # which Docs evaluates against the post-strip body). createParagraphBullets
    # itself and heading paragraph styles run BEFORE bullets strip the body
    # shift within each bulleted paragraph, so they use pre-strip positions.
    def _u16_len(s: str) -> int:
        return len(s.encode("utf-16-le")) // 2
    _doc_len = _u16_len  # All Phase-1 position tracking uses pre-strip UTF-16.
    full_text = ""
    segment_positions: list[tuple[int, int, _Segment]] = []  # (start, end, segment)
    block_ranges: list[tuple[int, int, _Block]] = []  # (start, end, block)
    # Track footnote reference positions for deferred insertion
    footnote_refs: list[tuple[int, str, str]] = []  # (offset, fn_id, fn_content)

    for block in blocks:
        block_start = _doc_len(full_text)

        if block.is_horizontal_rule:
            # Horizontal rules need a placeholder newline for the section break
            full_text += "\n"
            block_end = _doc_len(full_text)
            block_ranges.append((block_start, block_end, block))
            continue

        if block.is_page_break:
            # Page breaks need a placeholder newline
            full_text += "\n"
            block_end = _doc_len(full_text)
            block_ranges.append((block_start, block_end, block))
            continue

        if block.is_toc:
            # TOC needs a placeholder newline
            full_text += "\n"
            block_end = _doc_len(full_text)
            block_ranges.append((block_start, block_end, block))
            continue

        if block.table is not None:
            # Tables need a placeholder newline — actual table inserted in pass 2
            full_text += "\n"
            block_end = _doc_len(full_text)
            block_ranges.append((block_start, block_end, block))
            continue

        if block.is_image or block.is_mermaid:
            # Images and mermaid diagrams reserve a single newline placeholder.
            # The sync engine handles the actual upload + insertInlineImage in
            # a deferred pass.
            full_text += "\n"
            block_end = _doc_len(full_text)
            block_ranges.append((block_start, block_end, block))
            continue

        if block.is_code_block:
            # Code blocks reserve a single newline placeholder. The sync engine
            # replaces this with a single-cell table containing the code text,
            # styled with monospace + cell shading + per-token syntax highlighting.
            full_text += "\n"
            block_end = _doc_len(full_text)
            block_ranges.append((block_start, block_end, block))
            continue

        if block.is_list_item and block.is_task_list and block.task_checked:
            for seg in block.segments:
                seg.strikethrough = True

        if block.is_list_item:
            # Docs API convention: createParagraphBullets counts leading tabs
            # and uses the number as the nesting level, then STRIPS those tabs
            # from the body (shrinking subsequent positions by 1 per tab).
            #
            # That's a problem if bullet requests run in the same batch_update
            # as text-style requests: style ranges computed against the pre-
            # strip body land past the shrunken body end, and Docs returns
            # "Index N must be less than end index M".
            #
            # Workaround: the sync engine splits the request list so that
            # createParagraphBullets runs in a SECOND batch_update AFTER all
            # other requests. See _write_markdown_to_doc in sync_engine.py.
            # Within the bullets-only batch, tab-consumption shifts positions
            # but no subsequent request depends on them, so it's safe.
            #
            # Example source:
            #     - parent
            #       - child
            # Compiled tokens: parent at nesting=0 (no tab), child at
            # nesting=1 (one leading "\t"). The "\t" is sent to Docs,
            # consumed by createParagraphBullets, and becomes nesting level 1.
            indent = "\t" * block.list_nesting
            full_text += indent

        for seg in block.segments:
            # Check for footnote reference markers
            if seg.text.startswith("__fn__") and seg.text.endswith("__"):
                fn_id = seg.text[6:-2]  # strip __fn__ and __
                fn_content = footnote_contents.get(fn_id, "")
                footnote_refs.append((_doc_len(full_text), fn_id, fn_content))
                # Don't add text for footnote markers — they'll be replaced by
                # the footnote superscript from createFootnote
                continue
            seg_start = _doc_len(full_text)
            full_text += seg.text
            seg_end = _doc_len(full_text)
            segment_positions.append((seg_start, seg_end, seg))

        full_text += "\n"
        block_end = _doc_len(full_text)
        block_ranges.append((block_start, block_end, block))

    # Check if there are any deferred blocks (tables, TOC, footnotes, page breaks, images, code blocks)
    has_deferred = any(
        b.table is not None or b.is_toc or b.is_page_break
        or b.is_image or b.is_mermaid or b.is_code_block
        for _, _, b in block_ranges
    ) or bool(footnote_refs)

    if not full_text.strip() and not has_deferred:
        return []

    # Phase 2: Build requests.
    # First request: insert all text at index 1.
    requests: list[dict] = [
        {
            "insertText": {
                "location": {"index": 1},
                "text": full_text,
            }
        }
    ]

    # Apply paragraph styles (headings, lists) — offsets are 1-based in the doc
    for start, end, block in block_ranges:
        doc_start = start + 1
        doc_end = end + 1

        if block.is_horizontal_rule:
            # Insert a section break (horizontal rule)
            requests.append({
                "insertSectionBreak": {
                    "location": {"index": doc_start},
                    "sectionType": "CONTINUOUS",
                }
            })
            continue

        if block.is_page_break:
            requests.append({
                "insertPageBreak": {
                    "location": {"index": doc_start},
                }
            })
            continue

        if block.is_toc:
            requests.append({
                "insertTableOfContents": {
                    "location": {"index": doc_start},
                }
            })
            continue

        if block.table is not None:
            # Deferred table request — the caller must handle two-pass insertion
            table = block.table
            num_rows = len(table.rows) + 1  # +1 for header row
            num_cols = len(table.headers)
            requests.append({
                "_deferredTable": {
                    "insertTable": {
                        "rows": num_rows,
                        "columns": num_cols,
                        "location": {"index": doc_start},
                    },
                    "cells": [table.headers] + table.rows,
                }
            })
            continue

        if block.is_image:
            # Deferred image — sync engine uploads the local file to Drive,
            # makes it publicly readable, then issues an insertInlineImage at
            # the placeholder index.
            requests.append({
                "_deferredImage": {
                    "image_path": block.image_path,
                    "alt": block.image_alt,
                    "location": {"index": doc_start},
                    "kind": "file",
                }
            })
            continue

        if block.is_mermaid:
            # Deferred mermaid — sync engine renders the source via mmdc,
            # then uploads the resulting PNG and inserts inline.
            requests.append({
                "_deferredImage": {
                    "mermaid_source": block.mermaid_source,
                    "location": {"index": doc_start},
                    "kind": "mermaid",
                }
            })
            continue

        if block.heading_level > 0:
            requests.append({
                "updateParagraphStyle": {
                    "range": {"startIndex": doc_start, "endIndex": doc_end},
                    "paragraphStyle": {
                        "namedStyleType": _heading_id(block.heading_level),
                    },
                    "fields": "namedStyleType",
                }
            })
            # Docs auto-extends adjacent list paragraphs to include headings
            # between two bulleted blocks — the heading inherits the list's
            # bulletId. Clear it explicitly so the heading renders as a true
            # heading. These requests are routed to bullet_reqs and run AFTER
            # createParagraphBullets, which means by the time they execute
            # the body has shrunk by N (where N = tabs consumed before this
            # heading's position). So the range must be in POST-STRIP space.
            # Count tabs in full_text that sit before this block's UTF-16
            # position (`start` from the Phase 2 loop variable, NOT the
            # outer-scope `block_start` which is stale). Walk the string
            # tracking cumulative UTF-16 length.
            tabs_before = 0
            u16_seen = 0
            for ch in full_text:
                if u16_seen >= start:
                    break
                if ch == "\t":
                    tabs_before += 1
                u16_seen += 2 if ord(ch) > 0xFFFF else 1
            ds = doc_start - tabs_before
            de = doc_end - tabs_before
            requests.append({
                "deleteParagraphBullets": {
                    "range": {"startIndex": ds, "endIndex": de},
                }
            })

        if block.is_code_block:
            # Deferred code block — sync engine inserts a 1-cell table at the
            # placeholder index, fills the cell with the code text, applies
            # monospace + cell shading, and (if the language is recognized)
            # applies per-token syntax highlighting via pygments.
            code_text = "\n".join(seg.text for seg in block.segments)
            requests.append({
                "_deferredCodeBlock": {
                    "code": code_text,
                    "language": block.code_block_language,
                    "location": {"index": doc_start},
                }
            })
            continue

        # Intentionally no per-item createParagraphBullets emission here —
        # we coalesce them into one-request-per-contiguous-region below
        # (see "Bullet region coalescing" pass).

    # ── Bullet region coalescing ──
    #
    # Walk block_ranges and find maximal runs of consecutive is_list_item
    # blocks that share the same `is_ordered` flag. Emit ONE
    # createParagraphBullets per run covering [first.block_start,
    # last.block_end) with the matching preset.
    #
    # Why: Docs' `createParagraphBullets` auto-joins a paragraph to the
    # list immediately before it if their presets match. Issuing one
    # request per list item causes 70 consecutive joins, and when a
    # later request uses a DIFFERENT preset (numbered for delegation
    # rules vs disc for inventory), the join cascades across headings
    # and promotes the whole contiguous region to the last preset. See
    # docs/gdocs-sync-gotchas.md landmine #9b for the full story.
    #
    # IMPORTANT — coordinate space: createParagraphBullets consumes
    # leading tabs (see landmine #1). Within a single batch_update, Docs
    # processes requests sequentially against the current body state.
    # So the SECOND create's range must account for tabs already
    # consumed by the FIRST create, etc. We emit all create ranges in
    # POST-STRIP space (same as delete ranges) so they are consistent
    # across the whole bullets batch.
    #
    # Helper: count tabs in full_text up to a given pre-strip UTF-16
    # position. Walks the string char-by-char tracking cumulative
    # UTF-16 length.
    def _tabs_before(pre_strip_pos: int) -> int:
        count = 0
        u16 = 0
        for ch in full_text:
            if u16 >= pre_strip_pos:
                break
            if ch == "\t":
                count += 1
            u16 += 2 if ord(ch) > 0xFFFF else 1
        return count

    i = 0
    while i < len(block_ranges):
        _s, _e, _b = block_ranges[i]
        if not _b.is_list_item:
            i += 1
            continue
        run_start = _s
        run_end = _e
        is_ordered = _b.is_ordered
        is_task = _b.is_task_list
        j = i + 1
        while j < len(block_ranges):
            ns, ne, nb = block_ranges[j]
            if (
                not nb.is_list_item
                or nb.is_ordered != is_ordered
                or nb.is_task_list != is_task
            ):
                break
            run_end = ne
            j += 1
        # Convert to post-strip (1-based) positions: subtract the tab
        # count that sits at positions strictly less than run_start for
        # the start, and less than run_end for the end.
        ps_start = (run_start + 1) - _tabs_before(run_start)
        ps_end = (run_end + 1) - _tabs_before(run_end)
        requests.append({
            "createParagraphBullets": {
                "range": {
                    "startIndex": ps_start,
                    "endIndex": ps_end,
                },
                "bulletPreset": (
                    "BULLET_CHECKBOX"
                    if is_task
                    else "NUMBERED_DECIMAL_ALPHA_ROMAN"
                    if is_ordered
                    else "BULLET_DISC_CIRCLE_SQUARE"
                ),
            }
        })
        i = j

    # Apply text styles (bold, italic, monospace, links)
    for start, end, seg in segment_positions:
        doc_start = start + 1
        doc_end = end + 1
        style: dict[str, Any] = {}
        fields: list[str] = []

        if seg.bold:
            style["bold"] = True
            fields.append("bold")
        if seg.italic:
            style["italic"] = True
            fields.append("italic")
        if seg.monospace:
            style["weightedFontFamily"] = {
                "fontFamily": MONOSPACE_FONT,
                "weight": 400,
            }
            fields.append("weightedFontFamily")
        if seg.link_url:
            style["link"] = {"url": seg.link_url}
            fields.append("link")
        if seg.strikethrough:
            style["strikethrough"] = True
            fields.append("strikethrough")

        if not fields:
            continue

        requests.append({
            "updateTextStyle": {
                "range": {"startIndex": doc_start, "endIndex": doc_end},
                "textStyle": style,
                "fields": ",".join(fields),
            }
        })

    # Add deferred footnote requests (must be applied after text insertion)
    # Process in reverse order so indices don't shift
    for offset, fn_id, fn_content in sorted(footnote_refs, reverse=True):
        doc_offset = offset + 1
        requests.append({
            "_deferredFootnote": {
                "createFootnote": {
                    "location": {"index": doc_offset},
                },
                "content": fn_content,
                "footnoteId": fn_id,
            }
        })

    return requests


def parse_pipe_table(text: str) -> _TableData | None:
    """Parse a markdown pipe table string into a TableData structure.

    Public API for the ``doc table`` command.

    Args:
        text: Markdown pipe table string (lines separated by newlines).

    Returns:
        _TableData or None if the text is not a valid pipe table.
    """
    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
    if len(lines) < 2:
        return None
    return _parse_pipe_table(lines)


def table_to_requests(table: _TableData, index: int = 1) -> list[dict]:
    """Convert a table into a list of batchUpdate requests.

    Returns the insertTable request and deferred cell content requests.
    The caller must apply insertTable first, fetch the doc to get cell indices,
    then apply the cell content requests.

    Args:
        table: Parsed table data.
        index: Document index where the table should be inserted.

    Returns:
        List containing one ``_deferredTable`` request dict.
    """
    num_rows = len(table.rows) + 1  # +1 for header
    num_cols = len(table.headers)
    return [{
        "_deferredTable": {
            "insertTable": {
                "rows": num_rows,
                "columns": num_cols,
                "location": {"index": index},
            },
            "cells": [table.headers] + table.rows,
        }
    }]


def docs_to_markdown(doc: dict) -> str:
    """Convert a Google Docs document resource to markdown.

    Reads the document body and reconstructs markdown from the structural
    elements and text runs, including tables.

    Args:
        doc: A full document resource from the Docs API (documents().get()).

    Returns:
        Markdown-formatted string.
    """
    body = doc.get("body", {})
    content = body.get("content", [])
    lines: list[str] = []

    for element in content:
        # Handle tables
        table = element.get("table")
        if table:
            table_lines = _table_element_to_markdown(table)
            lines.extend(table_lines)
            lines.append("")  # blank line after table
            continue

        # Handle table of contents
        toc = element.get("tableOfContents")
        if toc:
            lines.append("[TOC]")
            lines.append("")
            continue

        paragraph = element.get("paragraph")
        if not paragraph:
            # Handle section breaks / page breaks
            section_break = element.get("sectionBreak")
            if section_break:
                sb_type = section_break.get("sectionStyle", {}).get("sectionType", "")
                if sb_type == "NEXT_PAGE":
                    lines.append("---pagebreak---")
                    lines.append("")
                else:
                    lines.append("---")
                    lines.append("")
            continue

        style = paragraph.get("paragraphStyle", {})
        named_style = style.get("namedStyleType", "NORMAL_TEXT")
        bullet = paragraph.get("bullet")

        # Check for page breaks within paragraph elements
        has_page_break = False
        for elem in paragraph.get("elements", []):
            if elem.get("pageBreak"):
                has_page_break = True

        if has_page_break:
            lines.append("---pagebreak---")
            lines.append("")
            continue

        # Build the paragraph text from runs
        text_parts: list[str] = []
        for elem in paragraph.get("elements", []):
            text_run = elem.get("textRun")
            if not text_run:
                # Check for footnote references
                footnote_ref = elem.get("footnoteReference")
                if footnote_ref:
                    fn_id = footnote_ref.get("footnoteId", "")
                    # We'll use a numeric footnote marker
                    text_parts.append(f"[^{fn_id}]")
                continue

            content_text = text_run.get("content", "")
            text_style = text_run.get("textStyle", {})

            # Strip trailing newline (Docs adds one per paragraph)
            if content_text.endswith("\n"):
                content_text = content_text[:-1]

            if not content_text:
                continue

            # Apply inline formatting
            is_bold = text_style.get("bold", False)
            is_italic = text_style.get("italic", False)
            link = text_style.get("link", {})
            link_url = link.get("url", "") if isinstance(link, dict) else ""
            font_family = (
                text_style.get("weightedFontFamily", {}).get("fontFamily", "")
            )
            is_monospace = font_family == MONOSPACE_FONT

            if is_monospace and not link_url:
                content_text = f"`{content_text}`"
            elif is_bold and is_italic:
                content_text = f"***{content_text}***"
            elif is_bold:
                content_text = f"**{content_text}**"
            elif is_italic:
                content_text = f"*{content_text}*"

            if link_url:
                content_text = f"[{content_text}]({link_url})"

            text_parts.append(content_text)

        line = "".join(text_parts)
        if not line:
            lines.append("")
            continue

        # Apply block-level formatting
        if bullet:
            nesting = bullet.get("nestingLevel", 0)
            indent = "  " * nesting
            list_id = bullet.get("listId", "")
            # Check if ordered (look at the list properties in the doc)
            lists = doc.get("lists", {})
            list_props = lists.get(list_id, {})
            nesting_levels = (
                list_props.get("listProperties", {}).get("nestingLevels", [])
            )
            is_ordered = False
            if nesting_levels and len(nesting_levels) > nesting:
                glyph_type = nesting_levels[nesting].get("glyphType", "")
                if glyph_type in ("DECIMAL", "ALPHA", "ROMAN"):
                    is_ordered = True

            if is_ordered:
                line = f"{indent}1. {line}"
            else:
                line = f"{indent}- {line}"
        elif named_style == "HEADING_1":
            line = f"# {line}"
        elif named_style == "HEADING_2":
            line = f"## {line}"
        elif named_style == "HEADING_3":
            line = f"### {line}"

        lines.append(line)

    # Emit footnote definitions at the end
    footnotes = doc.get("footnotes", {})
    if footnotes:
        lines.append("")
        for fn_id, fn_data in footnotes.items():
            fn_text = _extract_footnote_text(fn_data)
            lines.append(f"[^{fn_id}]: {fn_text}")

    # Clean up: collapse multiple blank lines
    result = "\n".join(lines)
    while "\n\n\n" in result:
        result = result.replace("\n\n\n", "\n\n")
    return result.strip() + "\n"


def _table_element_to_markdown(table: dict) -> list[str]:
    """Convert a Google Docs table element to markdown pipe table lines."""
    rows_data: list[list[str]] = []

    for row in table.get("tableRows", []):
        cells: list[str] = []
        for cell in row.get("tableCells", []):
            # Extract text from cell content
            cell_text_parts: list[str] = []
            for content_elem in cell.get("content", []):
                para = content_elem.get("paragraph")
                if not para:
                    continue
                for elem in para.get("elements", []):
                    tr = elem.get("textRun")
                    if tr:
                        text = tr.get("content", "").strip()
                        if text:
                            cell_text_parts.append(text)
            cells.append(" ".join(cell_text_parts))
        rows_data.append(cells)

    if not rows_data:
        return []

    # First row is headers
    headers = rows_data[0]
    lines = ["| " + " | ".join(headers) + " |"]
    # Separator line
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    # Data rows
    for row in rows_data[1:]:
        # Pad row to match header count
        while len(row) < len(headers):
            row.append("")
        lines.append("| " + " | ".join(row[:len(headers)]) + " |")

    return lines


def _extract_footnote_text(footnote_data: dict) -> str:
    """Extract plain text from a footnote body."""
    parts: list[str] = []
    for content_elem in footnote_data.get("content", []):
        para = content_elem.get("paragraph")
        if not para:
            continue
        for elem in para.get("elements", []):
            tr = elem.get("textRun")
            if tr:
                text = tr.get("content", "").strip()
                if text:
                    parts.append(text)
    return " ".join(parts)
