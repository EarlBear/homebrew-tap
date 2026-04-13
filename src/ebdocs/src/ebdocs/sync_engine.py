"""Sync engine — pull/diff/push logic for local YAML+MD <-> Google Drive docs.

Mental model (parallel to ebjira sync):
- Local files are the source of truth for editing.
- Each doc is represented as a YAML metadata file + sibling markdown file.
- YAML holds identity, placement, sharing, hash; .md holds the actual content.
- Folder hierarchy under the sync root mirrors Drive folder hierarchy.

Sync directory is resolved from:
1. EBDOCS_SYNC_DIR (explicit override)
2. CONTENT_DIR/gdocs (shared content repo)
3. dist/gdocs (default for local dev)

The Drive root folder for sync is resolved by finding/creating a "knowledge-base"
subfolder under GOOGLE_DRIVE_FOLDER_ID (configurable via SYNC_ROOT_FOLDER_NAME).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from ebdocs.client import DocsClient
from ebdocs.markdown import docs_to_markdown, markdown_to_requests

# -- Constants --


def _resolve_sync_base() -> Path:
    """Resolve the sync base directory."""
    explicit = os.environ.get("EBDOCS_SYNC_DIR")
    if explicit:
        return Path(explicit)
    content_dir = os.environ.get("CONTENT_DIR")
    if content_dir:
        return Path(content_dir) / "gdocs"
    return Path("dist/gdocs")


SYNC_BASE = _resolve_sync_base()

# Name of the top-level Drive folder to mirror (under GOOGLE_DRIVE_FOLDER_ID)
SYNC_ROOT_FOLDER_NAME = os.environ.get("SYNC_ROOT_FOLDER_NAME", "knowledge-base")

METADATA_FILE = ".drive-metadata.json"

# Fixed field order for deterministic YAML output (clean git diffs).
FIELD_ORDER = [
    "id", "link", "title",
    "folder_path", "folder_id",
    "content_file", "content_hash",
    "shared_with",
    "created", "updated",
]

DIFFABLE_META_FIELDS = ["title", "folder_path", "shared_with"]


# -- Helpers --


def _slugify(title: str) -> str:
    """Convert a doc title to a filesystem-safe slug."""
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "-", slug)
    return slug.strip("-") or "untitled"


def _sha256(text: str) -> str:
    """Return sha256:<hex> for a string."""
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _ordered_dict(d: dict) -> dict:
    """Return a dict with keys in FIELD_ORDER, then any extras alphabetically."""
    ordered: dict[str, Any] = {}
    for field in FIELD_ORDER:
        if field in d:
            ordered[field] = d[field]
    for field in sorted(d.keys()):
        if field not in ordered:
            ordered[field] = d[field]
    return ordered


def _dump_yaml(data: dict) -> str:
    """Dump a YAML metadata dict with consistent field ordering."""
    return yaml.dump(
        _ordered_dict(data),
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )


def _load_yaml(path: Path) -> dict | None:
    """Load a YAML file, return dict or None on error."""
    if not path.exists():
        return None
    try:
        data = yaml.safe_load(path.read_text())
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def sync_root_dir() -> Path:
    """Return the local sync root directory (SYNC_BASE/SYNC_ROOT_FOLDER_NAME)."""
    return SYNC_BASE / SYNC_ROOT_FOLDER_NAME


# -- Frontmatter handling --
#
# Markdown files may have a YAML frontmatter block at the top, delimited by --- lines.
# Frontmatter is LOCAL-ONLY: stripped before push, preserved on pull, and excluded
# from content_hash calculation. This lets us store agent-facing metadata (jira_source,
# tags, agent_hints, provenance) alongside the content without polluting Drive.

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def split_frontmatter(text: str) -> tuple[dict, str]:
    """Split a markdown document into (frontmatter_dict, body_text).

    If no frontmatter is present, returns ({}, text).
    If frontmatter is malformed, returns ({}, text) — never raises.
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    fm_text = match.group(1)
    body = text[match.end():]
    try:
        fm = yaml.safe_load(fm_text) or {}
        if not isinstance(fm, dict):
            return {}, text
        return fm, body
    except Exception:
        return {}, text


def join_frontmatter(frontmatter: dict, body: str) -> str:
    """Join a frontmatter dict + body back into a single markdown string.

    If frontmatter is empty, returns body unchanged.
    """
    if not frontmatter:
        return body
    fm_text = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False, allow_unicode=True)
    # Ensure body starts on a fresh line
    if not body.startswith("\n"):
        body = "\n" + body if body else ""
    return f"---\n{fm_text}---\n{body}"


def _body_for_sync(md_path: str | Path) -> str:
    """Read a .md file and return just the body (frontmatter stripped).

    Empty string if the file doesn't exist.
    """
    p = Path(md_path)
    if not p.exists():
        return ""
    _, body = split_frontmatter(p.read_text())
    return body


def _write_body_preserving_frontmatter(md_path: str | Path, new_body: str) -> None:
    """Write new body to an .md file, preserving any existing frontmatter."""
    p = Path(md_path)
    existing_fm: dict = {}
    if p.exists():
        existing_fm, _ = split_frontmatter(p.read_text())
    p.write_text(join_frontmatter(existing_fm, new_body))


def _write_markdown_to_doc(
    client: DocsClient,
    doc_id: str,
    markdown: str,
    md_source_dir: Path | None = None,
) -> None:
    """Write markdown content to a Google Doc.

    Tries MCP Worker first (formatted), falls back to direct batch_update
    with deferred image / mermaid handling.

    Args:
        client: Docs client.
        doc_id: Target Google Doc ID.
        markdown: Markdown body to write.
        md_source_dir: Directory of the source .md file. Used to resolve relative
            image paths and as the cache root for rendered mermaid PNGs.
    """
    has_deferred_features = bool(re.search(r"^```", markdown, re.MULTILINE) or "![" in markdown)

    # Try MCP Worker first if available — but only if there are no mermaid/image/
    # code blocks. The Worker write-markdown endpoint doesn't support deferred
    # image uploads or single-cell code-block tables, so anything with these
    # MUST go through the direct path.
    if client._mcp_auth and not has_deferred_features:
        try:
            client.write_markdown(doc_id, markdown, replace=True)
            return
        except Exception:
            pass

    # Direct batch_update path: clear existing content first.
    try:
        doc = client.get_document(doc_id)
        body_content = doc.get("body", {}).get("content", [])
        end_index = 1
        for el in body_content:
            if el.get("endIndex", 0) > end_index:
                end_index = el["endIndex"]
        if end_index > 2:
            client.batch_update(doc_id, [{
                "deleteContentRange": {
                    "range": {"startIndex": 1, "endIndex": end_index - 1}
                }
            }])
    except Exception:
        pass

    # Convert markdown → requests, then resolve any _deferredImage entries
    # by rendering (mermaid) and/or uploading (file) to Drive.
    requests = markdown_to_requests(markdown)
    if not requests:
        return


    requests = _resolve_deferred_images(client, requests, md_source_dir)

    # Separate _deferredCodeBlock and _deferredTable requests for post-batch
    # processing. Both need multi-pass insertion (insert structure → fetch doc
    # → fill cells), which doesn't fit in a single batch_update.
    code_blocks: list[dict] = []
    tables: list[dict] = []
    main_requests: list[dict] = []
    for req in requests:
        if "_deferredCodeBlock" in req:
            code_blocks.append(req["_deferredCodeBlock"])
        elif "_deferredTable" in req:
            tables.append(req["_deferredTable"])
        else:
            main_requests.append(req)

    if main_requests:
        # Reorder: insertInlineImage (and its paired center updateParagraphStyle)
        # must run AFTER every style/paragraph request that targets indices
        # past the image, otherwise the +1 shift per image corrupts the tail
        # of the request list. Extract image-related requests, run the rest
        # first, then run images in DESCENDING index order so each image's
        # insertion doesn't shift subsequent images.
        image_reqs: list[dict] = []
        bullet_reqs: list[dict] = []
        other_reqs: list[dict] = []
        for req in main_requests:
            if "insertInlineImage" in req:
                image_reqs.append(req)
            elif (
                "updateParagraphStyle" in req
                and req["updateParagraphStyle"].get("paragraphStyle", {}).get("alignment") == "CENTER"
            ):
                # Center alignment paired with image — defer with it.
                image_reqs.append(req)
            elif "createParagraphBullets" in req or "deleteParagraphBullets" in req:
                # Docs API's createParagraphBullets strips leading tabs from
                # each bulleted paragraph (tabs become nesting level). That
                # shrinks the body and would break any subsequent request
                # whose index was computed against the pre-strip body. We
                # therefore run ALL bullet requests in a third batch, after
                # text-style / paragraph-style requests have landed.
                bullet_reqs.append(req)
            else:
                other_reqs.append(req)

        if other_reqs:
            client.batch_update(doc_id, other_reqs)

        if image_reqs:
            # Sort image inserts descending by index. Keep each image with its
            # paired center paragraph style immediately after it.
            def _key(req: dict) -> int:
                if "insertInlineImage" in req:
                    return req["insertInlineImage"].get("location", {}).get("index", 0)
                return req["updateParagraphStyle"].get("range", {}).get("startIndex", 0)
            image_reqs.sort(key=_key, reverse=True)
            client.batch_update(doc_id, image_reqs)

        if bullet_reqs:
            # Order matters within the bullets batch:
            #   1. ALL createParagraphBullets first (each one auto-extends its
            #      list to adjacent headings as a side effect).
            #   2. ALL deleteParagraphBullets after (clears those spurious
            #      list memberships from heading paragraphs).
            # If we ran them interleaved in source order, a later
            # createParagraphBullets would re-swallow a heading that an
            # earlier deleteParagraphBullets had just cleared.
            create_bullets = [r for r in bullet_reqs if "createParagraphBullets" in r]
            delete_bullets = [r for r in bullet_reqs if "deleteParagraphBullets" in r]
            try:
                client.batch_update(doc_id, create_bullets + delete_bullets)
            except Exception:
                pass  # Bullet failure is non-fatal — content still renders

        # After batch_update completes, Google has fetched and cached any
        # inline images, so the temp Drive uploads can be removed.
        _cleanup_temp_uploads()

    # Process code blocks and tables in DESCENDING index order so earlier
    # inserts don't shift later ones.
    deferred = [("code", cb["location"]["index"], cb) for cb in code_blocks]
    deferred += [("table", t["insertTable"]["location"]["index"], t) for t in tables]
    deferred.sort(key=lambda x: x[1], reverse=True)
    for kind, _idx, payload in deferred:
        if kind == "code":
            _insert_code_block(client, doc_id, payload)
        else:
            _insert_table(client, doc_id, payload)

    # Post-push pass: linkify table cells whose text matches an in-doc
    # heading. This enables summary-table → agent-detail cross-linking
    # without the author having to manage heading IDs manually.
    if tables:
        _linkify_table_cells_to_headings(client, doc_id)

    # Post-push theming pass: apply paragraph spacing, heading styles,
    # and body font so every doc gets a consistent branded look. See
    # _apply_doc_theme docstring for the full theme spec.
    _apply_doc_theme(client, doc_id)


_temp_uploads_to_clean: list[tuple] = []


# Cell shading for code blocks (light gray-blue, matches the previous paragraph
# styling so the visual is consistent with what users have already seen).
_CODE_CELL_BG = {"red": 0.95, "green": 0.95, "blue": 0.97}
_MONOSPACE_FONT = "Courier New"


def _insert_code_block(client: DocsClient, doc_id: str, cb: dict) -> None:
    """Insert a single-cell table at the given location and fill it with code.

    Three-pass operation:
    1. Delete the placeholder character + insert a 1x1 table
    2. Re-fetch the doc to find the cell content index
    3. Insert code text into the cell with monospace, cell shading, and
       per-token syntax highlighting

    Args:
        client: Docs client.
        doc_id: Target Google Doc ID.
        cb: _deferredCodeBlock dict with keys: code, language, location.
    """
    code = cb.get("code", "")
    language = cb.get("language", "")
    location = cb.get("location", {"index": 1})
    insert_index = location.get("index", 1)

    if not code:
        return

    # Pass 1: delete placeholder newline at insert_index, insert 1x1 table.
    # The placeholder is a single \n. After deletion, the table inserts at the
    # same index.
    try:
        client.batch_update(doc_id, [
            {
                "deleteContentRange": {
                    "range": {"startIndex": insert_index, "endIndex": insert_index + 1},
                }
            },
            {
                "insertTable": {
                    "rows": 1,
                    "columns": 1,
                    "location": {"index": insert_index},
                }
            },
        ])
    except Exception as e:
        # If table insertion fails, fall back to plain text insertion so the
        # code is at least visible in the doc.
        client.batch_update(doc_id, [{
            "insertText": {
                "location": {"index": insert_index},
                "text": code + "\n",
            }
        }])
        return

    # Pass 2: re-fetch to find the cell content index.
    # The table won't necessarily start at insert_index — Google Docs may
    # prepend paragraphs around it. Find the FIRST table at or after
    # insert_index and use its inner cell.
    doc = client.get_document(doc_id)
    body_content = doc.get("body", {}).get("content", [])
    table_start_index: int | None = None
    cell_text_index: int | None = None
    for el in body_content:
        start = el.get("startIndex", -1)
        if start < insert_index:
            continue
        table = el.get("table")
        if not table:
            continue
        # Found a table at/after the target index
        table_start_index = start
        rows = table.get("tableRows", [])
        if not rows:
            break
        cells = rows[0].get("tableCells", [])
        if not cells:
            break
        cell = cells[0]
        cell_content = cell.get("content", [])
        if not cell_content:
            break
        first_para = cell_content[0]
        para = first_para.get("paragraph")
        if not para:
            break
        elements = para.get("elements", [])
        if elements:
            cell_text_index = elements[0].get("startIndex")
        else:
            cell_text_index = first_para.get("startIndex")
        break

    if cell_text_index is None or table_start_index is None:
        return

    # Pass 3: insert code text + apply styling.
    requests: list[dict] = [
        {
            "insertText": {
                "location": {"index": cell_text_index},
                "text": code,
            }
        }
    ]

    text_end_index = cell_text_index + len(code)

    # Monospace font on the entire code text
    requests.append({
        "updateTextStyle": {
            "range": {"startIndex": cell_text_index, "endIndex": text_end_index},
            "textStyle": {
                "weightedFontFamily": {
                    "fontFamily": _MONOSPACE_FONT,
                    "weight": 400,
                },
                "fontSize": {"magnitude": 9, "unit": "PT"},
            },
            "fields": "weightedFontFamily,fontSize",
        }
    })

    # Cell background shading. tableStartLocation must point at the actual
    # table start, NOT the original insert_index (Google Docs may have shifted
    # the table by prepending paragraphs).
    requests.append({
        "updateTableCellStyle": {
            "tableStartLocation": {"index": table_start_index},
            "tableCellStyle": {
                "backgroundColor": {
                    "color": {"rgbColor": _CODE_CELL_BG}
                },
                "paddingLeft": {"magnitude": 8, "unit": "PT"},
                "paddingRight": {"magnitude": 8, "unit": "PT"},
                "paddingTop": {"magnitude": 6, "unit": "PT"},
                "paddingBottom": {"magnitude": 6, "unit": "PT"},
            },
            "fields": "backgroundColor,paddingLeft,paddingRight,paddingTop,paddingBottom",
        }
    })

    # Per-token syntax highlighting (if pygments supports the language)
    if language:
        try:
            from ebdocs.syntax_highlight import highlight
            spans = highlight(code, language)
            for span in spans:
                r, g, b = span.color
                requests.append({
                    "updateTextStyle": {
                        "range": {
                            "startIndex": cell_text_index + span.start,
                            "endIndex": cell_text_index + span.end,
                        },
                        "textStyle": {
                            "foregroundColor": {
                                "color": {"rgbColor": {"red": r, "green": g, "blue": b}}
                            }
                        },
                        "fields": "foregroundColor",
                    }
                })
        except Exception:
            pass  # Highlighting is best-effort

    try:
        client.batch_update(doc_id, requests)
    except Exception:
        pass  # Code is at least inserted; styling failure is non-critical


def _compute_column_widths(
    cells: list[list[str]],
    num_cols: int,
    page_width_pt: int = 468,
) -> list[float]:
    """Compute content-aware column widths for a markdown table.

    For each column, compute a representative "weight" from its cells:
    - With >=4 rows: use the 75th percentile of each row's longest
      comma/semicolon-delimited chunk, so three quarters of rows fit
      comfortably and outlier rows wrap.
    - With <4 rows: fall back to the max-based formula (percentile is
      meaningless on small samples).

    sqrt compresses the range, then widths are distributed proportionally
    across available page width, clamped to [45, 220] pt, and
    re-normalized to sum to available width.
    """
    import math

    min_col_pt = 45
    max_col_pt = 220

    def _cell_longest(text: str) -> int:
        if not text:
            return 0
        chunks = re.split(r"[,;]\s*", text)
        longest = max((len(c.strip()) for c in chunks), default=len(text))
        total_discounted = len(text) // 3
        return max(longest, total_discounted)

    def _percentile(values: list[int], pct: float) -> float:
        if not values:
            return 0.0
        s = sorted(values)
        if len(s) == 1:
            return float(s[0])
        k = (len(s) - 1) * pct
        lo = int(math.floor(k))
        hi = int(math.ceil(k))
        if lo == hi:
            return float(s[lo])
        return s[lo] + (s[hi] - s[lo]) * (k - lo)

    num_rows = len(cells)
    use_percentile = num_rows >= 4

    def _col_weight(col_idx: int) -> float:
        per_row = []
        for row in cells:
            if col_idx >= len(row):
                continue
            per_row.append(_cell_longest(row[col_idx] or ""))
        if not per_row:
            representative = 0.0
        elif use_percentile:
            representative = _percentile(per_row, 0.75)
        else:
            representative = float(max(per_row))
        return math.sqrt(max(representative, 4))

    weights = [_col_weight(i) for i in range(num_cols)]
    total_weight = sum(weights) or 1.0

    col_widths: list[float] = []
    for w in weights:
        raw = (w / total_weight) * page_width_pt
        col_widths.append(max(min_col_pt, min(max_col_pt, raw)))

    scale = page_width_pt / sum(col_widths)
    col_widths = [w * scale for w in col_widths]

    if os.environ.get("EBDOCS_DEBUG_TABLES"):
        import sys
        print(
            f"[ebdocs table] rows={num_rows} cols={num_cols} "
            f"mode={'p75' if use_percentile else 'max'} "
            f"weights={[round(w, 2) for w in weights]} "
            f"widths={[round(w, 1) for w in col_widths]}",
            file=sys.stderr,
        )

    return col_widths


def _insert_table(client: DocsClient, doc_id: str, payload: dict) -> None:
    """Insert a markdown table as a real Google Docs table.

    Two-pass: insert the table structure, refetch the doc to find the cell
    start indices, then fill each cell with insertText requests (reversed so
    indices remain valid).

    Args:
        client: Docs client.
        doc_id: Target doc.
        payload: _deferredTable payload with keys insertTable and cells.
    """
    insert_req = payload.get("insertTable", {})
    cells: list[list[str]] = payload.get("cells", [])
    location = insert_req.get("location", {"index": 1})
    insert_index = location.get("index", 1)

    if not cells:
        return

    # Pass 1: delete the placeholder newline and insert the table structure.
    try:
        client.batch_update(doc_id, [
            {
                "deleteContentRange": {
                    "range": {"startIndex": insert_index, "endIndex": insert_index + 1},
                }
            },
            {
                "insertTable": {
                    "rows": insert_req.get("rows", len(cells)),
                    "columns": insert_req.get("columns", len(cells[0]) if cells else 0),
                    "location": {"index": insert_index},
                }
            },
        ])
    except Exception:
        return

    # Pass 2: refetch the doc, find the table at-or-after insert_index,
    # and insert text into each cell.
    try:
        doc = client.get_document(doc_id)
    except Exception:
        return

    content = doc.get("body", {}).get("content", [])
    table_elem = None
    table_start_index = 0
    for elem in content:
        table = elem.get("table")
        if not table:
            continue
        if elem.get("startIndex", 0) >= insert_index:
            table_elem = table
            table_start_index = elem.get("startIndex", 0)
            break
    if not table_elem:
        return

    num_rows = len(table_elem.get("tableRows", []))
    num_cols = 0
    if table_elem.get("tableRows"):
        num_cols = len(table_elem["tableRows"][0].get("tableCells", []))

    fill_requests: list[dict] = []
    # Also collect per-cell text ranges so we can apply small-font styling.
    cell_text_ranges: list[tuple[int, int]] = []
    for row_idx, table_row in enumerate(table_elem.get("tableRows", [])):
        if row_idx >= len(cells):
            break
        for col_idx, table_cell in enumerate(table_row.get("tableCells", [])):
            if col_idx >= len(cells[row_idx]):
                continue
            text = cells[row_idx][col_idx]
            if not text:
                continue
            cell_content = table_cell.get("content", [])
            if not cell_content:
                continue
            para = cell_content[0].get("paragraph")
            if not para:
                continue
            elements = para.get("elements", [])
            if not elements:
                continue
            cell_start = elements[0].get("startIndex", 0)
            fill_requests.append({
                "insertText": {
                    "location": {"index": cell_start},
                    "text": text,
                }
            })
            # Track [cell_start, cell_start+len(text)) for later styling.
            # Positions will shift after inserts, but since we apply styling
            # only after ALL inserts have landed (and the range for each cell
            # is fixed relative to the preceding cells), we'll refetch.
            cell_text_ranges.append((cell_start, cell_start + len(text)))

    # Reverse so higher indices are inserted first.
    fill_requests.reverse()
    if fill_requests:
        try:
            client.batch_update(doc_id, fill_requests)
        except Exception:
            return

    # Pass 3: tighten the table. Smaller font, reduced cell padding, and
    # narrower column widths for all-but-the-last column so the final
    # column absorbs the slack. Tables created via insertTable default to
    # 11pt font and ~5pt padding per side, which blows out inventories
    # with many columns. We target 9pt font and 3pt padding.
    try:
        doc = client.get_document(doc_id)
    except Exception:
        return
    content = doc.get("body", {}).get("content", [])
    table_elem2 = None
    for elem in content:
        table = elem.get("table")
        if not table:
            continue
        if elem.get("startIndex", 0) >= insert_index:
            table_elem2 = table
            table_start_index = elem.get("startIndex", 0)
            break
    if not table_elem2:
        return

    style_requests: list[dict] = []

    # Shrink font on every cell text range, and auto-linkify EARL-NNN
    # mentions inside cells. Table cells bypass markdown.py's inline
    # segment processing entirely — _parse_pipe_table captures raw cell
    # text — so the usual auto-linkifier never runs on them. We do it
    # here on the post-fill doc by scanning each cell's actual text
    # content for the Jira key pattern.
    _JIRA_RE = re.compile(r"\bEARL-\d+\b")
    _JIRA_URL = "https://earlbear.atlassian.net/browse/"
    for row_idx, table_row in enumerate(table_elem2.get("tableRows", [])):
        for col_idx, table_cell in enumerate(table_row.get("tableCells", [])):
            cell_content = table_cell.get("content", [])
            if not cell_content:
                continue
            para = cell_content[0].get("paragraph")
            if not para:
                continue
            elements = para.get("elements", [])
            if not elements:
                continue
            first_el = elements[0]
            last_el = elements[-1]
            rs = first_el.get("startIndex", 0)
            re_idx = last_el.get("endIndex", rs + 1)
            if re_idx <= rs:
                continue
            style_requests.append({
                "updateTextStyle": {
                    "range": {"startIndex": rs, "endIndex": re_idx - 1},
                    "textStyle": {
                        "fontSize": {"magnitude": 9, "unit": "PT"},
                    },
                    "fields": "fontSize",
                }
            })

            # Auto-linkify EARL-NNN inside this cell. Walk the cell's
            # text runs, map each match's character offset back to a
            # document index, and emit an updateTextStyle(link) request.
            for run in elements:
                tr = run.get("textRun")
                if not tr:
                    continue
                content_text = tr.get("content", "")
                run_start = run.get("startIndex", 0)
                for m in _JIRA_RE.finditer(content_text):
                    key = m.group(0)
                    link_start = run_start + m.start()
                    link_end = run_start + m.end()
                    style_requests.append({
                        "updateTextStyle": {
                            "range": {
                                "startIndex": link_start,
                                "endIndex": link_end,
                            },
                            "textStyle": {
                                "link": {"url": _JIRA_URL + key},
                            },
                            "fields": "link",
                        }
                    })

    # Apply tighter padding to ALL cells via a single updateTableCellStyle
    # over the whole table. `tableRange` covers the entire table.
    style_requests.append({
        "updateTableCellStyle": {
            "tableRange": {
                "tableCellLocation": {
                    "tableStartLocation": {"index": table_start_index},
                    "rowIndex": 0,
                    "columnIndex": 0,
                },
                "rowSpan": num_rows,
                "columnSpan": num_cols,
            },
            "tableCellStyle": {
                "paddingTop":    {"magnitude": 3, "unit": "PT"},
                "paddingBottom": {"magnitude": 3, "unit": "PT"},
                "paddingLeft":   {"magnitude": 4, "unit": "PT"},
                "paddingRight":  {"magnitude": 4, "unit": "PT"},
            },
            "fields": "paddingTop,paddingBottom,paddingLeft,paddingRight",
        }
    })

    # Content-aware column widths. For each column, compute a "weight"
    # based on the longest wrapped cell text. Distribute the available
    # page width (~468pt for standard 8.5x11 with 1in margins) across
    # columns proportional to their weights, with a floor so narrow
    # columns stay readable and a cap so one column can't hog everything.
    #
    # Weight formula: for each cell, count characters in the LONGEST
    # natural chunk (split on commas/semicolons so enumerated lists are
    # measured by their longest item, not total length). Take the max
    # per column, then apply sqrt to compress huge ranges.
    if num_cols >= 2:
        col_widths = _compute_column_widths(cells, num_cols)

        for col_idx, width_pt in enumerate(col_widths):
            style_requests.append({
                "updateTableColumnProperties": {
                    "tableStartLocation": {"index": table_start_index},
                    "columnIndices": [col_idx],
                    "tableColumnProperties": {
                        "widthType": "FIXED_WIDTH",
                        "width": {"magnitude": round(width_pt, 1), "unit": "PT"},
                    },
                    "fields": "widthType,width",
                }
            })

    if style_requests:
        try:
            client.batch_update(doc_id, style_requests)
        except Exception:
            pass  # Styling failure is non-critical — table is still there


def _linkify_table_cells_to_headings(client: DocsClient, doc_id: str) -> None:
    """Rewrite table cells whose text matches an in-doc heading into anchor links.

    Enables summary-table → detail-section navigation without the author
    having to manage heading IDs manually. For every paragraph inside a
    table cell, if its stripped text exactly matches a HEADING_N
    paragraph elsewhere in the doc, apply an updateTextStyle with
    link.url pointing at that heading's anchor:

        https://docs.google.com/document/d/<doc_id>/edit#heading=<headingId>

    Only runs when tables exist. Silent on any Docs API error — link
    failures are non-critical, the table content is still there.
    """
    try:
        doc = client.get_document(doc_id)
    except Exception:
        return

    body = doc.get("body", {}).get("content", [])

    # Build heading text → headingId map (only HEADING_1..6 paragraphs
    # that have a stable headingId assigned by Docs).
    heading_ids: dict[str, str] = {}
    for el in body:
        p = el.get("paragraph")
        if not p:
            continue
        style = p.get("paragraphStyle", {})
        named = style.get("namedStyleType", "")
        if not named.startswith("HEADING"):
            continue
        hid = style.get("headingId", "")
        if not hid:
            continue
        text = "".join(
            r.get("textRun", {}).get("content", "")
            for r in p.get("elements", [])
        ).strip()
        if text and text not in heading_ids:
            heading_ids[text] = hid

    if not heading_ids:
        return

    base_url = f"https://docs.google.com/document/d/{doc_id}/edit#heading="

    # Walk every cell in every table, find ones whose trimmed text
    # matches a heading, and emit updateTextStyle link requests.
    link_requests: list[dict] = []
    for el in body:
        table = el.get("table")
        if not table:
            continue
        for table_row in table.get("tableRows", []):
            for table_cell in table_row.get("tableCells", []):
                for cell_para_el in table_cell.get("content", []):
                    p = cell_para_el.get("paragraph")
                    if not p:
                        continue
                    elements = p.get("elements", [])
                    if not elements:
                        continue
                    cell_text = "".join(
                        r.get("textRun", {}).get("content", "")
                        for r in elements
                    ).strip()
                    if not cell_text:
                        continue
                    hid = heading_ids.get(cell_text)
                    if not hid:
                        continue
                    # Range covers the cell's first text run's start
                    # through the last text run's endIndex - 1 (Docs
                    # ranges are half-open so endIndex is the position
                    # *after* the last character).
                    rs = elements[0].get("startIndex", 0)
                    re_idx = elements[-1].get("endIndex", rs + 1)
                    if re_idx <= rs + 1:
                        continue
                    link_requests.append({
                        "updateTextStyle": {
                            "range": {
                                "startIndex": rs,
                                "endIndex": re_idx - 1,
                            },
                            "textStyle": {
                                "link": {"url": base_url + hid},
                            },
                            "fields": "link",
                        }
                    })

    if link_requests:
        try:
            client.batch_update(doc_id, link_requests)
        except Exception:
            pass  # Non-critical


# ── Theme ──
#
# The visual style applied to every pushed doc is loaded from
# .claude/skills/authoring-drive-docs/theme.yaml via the EBDOCS_THEME_FILE
# env var (populated by the bin/ebdocs wrapper at invocation time).
#
# If the file is missing, unreadable, or malformed, we fall back to the
# hard-coded defaults below so pushes never fail on theming issues.
# Theming is cosmetic — any loader error is logged and ignored.

# Hard-coded fallback defaults, used when EBDOCS_THEME_FILE is unset
# or the file fails to load. Mirrors the shape of theme.yaml.
_THEME_DEFAULTS: dict = {
    "body": {
        # Roboto ships in the default Docs font menu. Unrecognized font
        # names fall back to Arial (NOT silently preserved), so only
        # default here with fonts that every Docs account has.
        "font": "Roboto",
        "font_size_pt": 11,
        "space_below_pt": 8,
        "line_spacing": 1.15,
    },
    "headings": {
        "font": "Montserrat",  # Ships in default Docs font menu
        "weight": 700,
        "color": {"red": 0.15, "green": 0.25, "blue": 0.4},
        "space_above_pt": 14,
        "space_below_pt": 6,
        "sizes_pt": {1: 22, 2: 18, 3: 14, 4: 12, 5: 11, 6: 11},
    },
}


_THEME_EXPECTED_KEYS: tuple[tuple[str, ...], ...] = (
    ("body", "font"),
    ("body", "font_size_pt"),
    ("body", "space_below_pt"),
    ("body", "line_spacing"),
    ("headings", "font"),
    ("headings", "weight"),
    ("headings", "color", "red"),
    ("headings", "color", "green"),
    ("headings", "color", "blue"),
    ("headings", "space_above_pt"),
    ("headings", "space_below_pt"),
    ("headings", "sizes_pt"),
)


def _validate_theme(theme: dict, source: str) -> bool:
    """Warn to stderr about any missing expected theme keys.

    Returns True when every expected key is present. Never raises —
    theming is cosmetic and must never fail a push.
    """
    import sys
    all_ok = True
    for path in _THEME_EXPECTED_KEYS:
        node: object = theme
        missing = False
        for part in path:
            if not isinstance(node, dict) or part not in node:
                missing = True
                break
            node = node[part]
        if missing:
            dotted = ".".join(path)
            print(
                f"[ebdocs] theme.yaml from {source}: missing "
                f"'{dotted}' \u2014 falling back to default for this field",
                file=sys.stderr,
            )
            all_ok = False
        elif path[-1] == "sizes_pt" and not isinstance(node, dict):
            print(
                f"[ebdocs] theme.yaml from {source}: 'headings.sizes_pt' "
                f"must be a dict \u2014 falling back to default for this field",
                file=sys.stderr,
            )
            all_ok = False
    return all_ok


def _load_theme() -> dict:
    """Load theme settings from EBDOCS_THEME_FILE, falling back to defaults.

    The theme file is YAML. Missing keys inherit from _THEME_DEFAULTS via
    a shallow-deep merge. Errors are silent — theming should never fail a
    push, and a missing or malformed theme just means the doc gets the
    defaults.
    """
    path = os.environ.get("EBDOCS_THEME_FILE", "")
    if not path or not Path(path).exists():
        return _THEME_DEFAULTS

    try:
        import yaml as _yaml
        with open(path) as f:
            loaded = _yaml.safe_load(f) or {}
    except Exception:
        return _THEME_DEFAULTS

    # Validate the loaded (pre-merge) dict so a missing key produces a
    # visible stderr warning instead of being silently masked by the
    # default that the deep-merge below will fill in.
    _validate_theme(loaded if isinstance(loaded, dict) else {}, path)

    # Deep-merge: loaded values override defaults, per top-level section.
    merged: dict = {}
    for section in ("body", "headings"):
        merged[section] = dict(_THEME_DEFAULTS[section])
        if isinstance(loaded.get(section), dict):
            for k, v in loaded[section].items():
                # Nested dicts (color, sizes_pt) get merged one level deep.
                if isinstance(v, dict) and isinstance(merged[section].get(k), dict):
                    merged[section][k] = {**merged[section][k], **v}
                else:
                    # Keep int keys for sizes_pt even if YAML loaded them as str
                    if k == "sizes_pt" and isinstance(v, dict):
                        merged[section][k] = {int(kk): vv for kk, vv in v.items()}
                    else:
                        merged[section][k] = v
    return merged


def _apply_doc_theme(client: DocsClient, doc_id: str) -> None:
    """Apply the branded theme to a pushed doc.

    Walks every paragraph in the body and applies:
    - Body paragraphs: paragraph space-below for visible separation,
      line spacing, body font, body font size
    - Heading paragraphs: heading font, heading font size per level,
      heading color, paragraph space-above/below

    Theme values come from _load_theme(), which reads the YAML file
    pointed at by $EBDOCS_THEME_FILE and falls back to _THEME_DEFAULTS.

    Runs silently on any API error. Theming is cosmetic — a failure
    should never fail a push.
    """
    try:
        doc = client.get_document(doc_id)
    except Exception:
        return

    body = doc.get("body", {}).get("content", [])
    if not body:
        return

    theme = _load_theme()
    b = theme["body"]
    h = theme["headings"]

    requests: list[dict] = []

    for el in body:
        p = el.get("paragraph")
        if not p:
            continue
        style = p.get("paragraphStyle", {})
        named = style.get("namedStyleType", "NORMAL_TEXT")

        # Paragraph start/end indices. The range for updateParagraphStyle
        # and updateTextStyle covers [first_element.start, last_element.end - 1]
        # to avoid the trailing newline that Docs interprets as out of range.
        elements = p.get("elements", [])
        if not elements:
            continue
        rs = elements[0].get("startIndex", 0)
        re_idx = elements[-1].get("endIndex", rs + 1)
        if re_idx <= rs + 1:
            continue
        text_range = {"startIndex": rs, "endIndex": re_idx - 1}

        if named.startswith("HEADING"):
            try:
                level = int(named.replace("HEADING_", ""))
            except ValueError:
                level = 1
            sizes_pt = h.get("sizes_pt", {})
            size_pt = sizes_pt.get(level, 14)
            # Heading paragraph style
            requests.append({
                "updateParagraphStyle": {
                    "range": text_range,
                    "paragraphStyle": {
                        "spaceAbove": {"magnitude": h["space_above_pt"], "unit": "PT"},
                        "spaceBelow": {"magnitude": h["space_below_pt"], "unit": "PT"},
                    },
                    "fields": "spaceAbove,spaceBelow",
                }
            })
            # Heading text style (font + size + color)
            requests.append({
                "updateTextStyle": {
                    "range": text_range,
                    "textStyle": {
                        "weightedFontFamily": {
                            "fontFamily": h["font"],
                            "weight": int(h.get("weight", 700)),
                        },
                        "fontSize": {"magnitude": size_pt, "unit": "PT"},
                        "foregroundColor": {
                            "color": {"rgbColor": h["color"]},
                        },
                    },
                    "fields": "weightedFontFamily,fontSize,foregroundColor",
                }
            })
        else:
            # Body paragraph: space-below + line spacing
            requests.append({
                "updateParagraphStyle": {
                    "range": text_range,
                    "paragraphStyle": {
                        "spaceBelow": {"magnitude": b["space_below_pt"], "unit": "PT"},
                        "lineSpacing": b["line_spacing"] * 100,  # API expects percent
                    },
                    "fields": "spaceBelow,lineSpacing",
                }
            })
            # Body text style (font + size)
            requests.append({
                "updateTextStyle": {
                    "range": text_range,
                    "textStyle": {
                        "weightedFontFamily": {
                            "fontFamily": b["font"],
                            "weight": 400,
                        },
                        "fontSize": {"magnitude": b["font_size_pt"], "unit": "PT"},
                    },
                    "fields": "weightedFontFamily,fontSize",
                }
            })

    if not requests:
        return

    try:
        client.batch_update(doc_id, requests)
    except Exception:
        pass  # Theming is cosmetic, never fail the push


def _cleanup_temp_uploads() -> None:
    """Delete temporary Drive uploads after batch_update has embedded the images.

    Google fetches and caches inline images at insertion time, so we don't need
    to keep the source files in Drive afterwards. Failures are silent — leaving
    a stray file is non-critical.
    """
    global _temp_uploads_to_clean
    for client, file_id in _temp_uploads_to_clean:
        try:
            client._drive.files().delete(fileId=file_id).execute()
        except Exception:
            pass
    _temp_uploads_to_clean = []


def _resolve_deferred_images(
    client: DocsClient,
    requests: list[dict],
    md_source_dir: Path | None,
) -> list[dict]:
    """Resolve any _deferredImage requests into real insertInlineImage requests.

    For each deferred image:
    - kind=mermaid: render the source via mmdc to a PNG (with caching)
    - kind=file: read the file at the given path

    Then upload to Drive, make publicly readable, and emit insertInlineImage
    pointing to the Drive content URL. Temp uploads are tracked for cleanup
    via _cleanup_temp_uploads().

    Returns the request list with deferred entries replaced.
    """
    from googleapiclient.http import MediaFileUpload

    # Resolve cache directory: if md_source_dir is set, use a sibling .assets/
    # directory; otherwise fall back to a tempdir.
    if md_source_dir is not None:
        assets_dir = md_source_dir / ".assets"
    else:
        import tempfile
        assets_dir = Path(tempfile.gettempdir()) / "ebdocs-mermaid-cache"

    resolved: list[dict] = []
    for req in requests:
        if "_deferredImage" not in req:
            resolved.append(req)
            continue

        deferred = req["_deferredImage"]
        kind = deferred.get("kind", "")
        location = deferred.get("location", {"index": 1})

        # Determine the local PNG path
        png_path: Path | None = None
        if kind == "mermaid":
            from ebdocs.mermaid import render_or_cache, MermaidRenderError, source_hash
            source = deferred.get("mermaid_source", "")
            h = source_hash(source)
            cached_png = assets_dir / f"mermaid-{h}.png"

            # Prefer the cached PNG (rendered on the host before sync push).
            # This is the canonical fast path: local .md keeps the ```mermaid
            # block so editors render it natively, and the host's
            # render_mermaid.py ensures the PNG cache is up to date.
            if cached_png.exists():
                png_path = cached_png
            else:
                # Cache miss — render inline. `render_or_cache` tries mmdc
                # first (host fast path) and falls back to the ephemeral
                # ebdocs-mermaid sidecar container (in-container path, no
                # Chromium in the main image; each render spawns a
                # `docker run --rm` one-shot that exits in seconds).
                try:
                    png_path = render_or_cache(source, assets_dir)
                except MermaidRenderError:
                    # Cloud context or local dev without mmdc/sidecar: fall
                    # back to rendering the mermaid source as a
                    # syntax-highlighted code block in the Drive doc. The
                    # reader sees the diagram source as colored code (via
                    # the Pygments mermaid lexer) instead of a visual
                    # diagram. See docs/gdocs-sync-gotchas.md landmine #14
                    # for the full fallback chain: host mmdc → sidecar →
                    # code-block degradation.
                    resolved.append({
                        "_deferredCodeBlock": {
                            "code": source,
                            "language": "mmd",
                            "location": location,
                        }
                    })
                    continue
        elif kind == "file":
            image_path = deferred.get("image_path", "")
            if md_source_dir is not None:
                png_path = (md_source_dir / image_path).resolve()
            else:
                png_path = Path(image_path)
            if not png_path.exists():
                resolved.append({
                    "insertText": {
                        "location": location,
                        "text": f"[image not found: {image_path}]\n",
                    }
                })
                continue
        else:
            continue

        # Upload to Drive
        suffix = png_path.suffix.lower()
        mime_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        mime_type = mime_map.get(suffix, "image/png")

        try:
            media = MediaFileUpload(str(png_path), mimetype=mime_type, resumable=False)
            drive_file = client._drive.files().create(
                body={"name": png_path.name, "mimeType": mime_type},
                media_body=media,
                fields="id,webContentLink",
            ).execute()
            file_id = drive_file["id"]

            # Make publicly readable so Google can fetch the image to embed it
            client._drive.permissions().create(
                fileId=file_id,
                body={"type": "anyone", "role": "reader"},
            ).execute()

            image_url = f"https://drive.google.com/uc?id={file_id}&export=download"

            resolved.append({
                "insertInlineImage": {
                    "location": location,
                    "uri": image_url,
                }
            })

            # Center the paragraph that contains the inserted image. The inline
            # image consumes 1 character at the location index, so the paragraph
            # range is [index, index+1).
            insert_index = location.get("index", 1)
            resolved.append({
                "updateParagraphStyle": {
                    "range": {
                        "startIndex": insert_index,
                        "endIndex": insert_index + 1,
                    },
                    "paragraphStyle": {"alignment": "CENTER"},
                    "fields": "alignment",
                }
            })

            # Track for post-batch cleanup. After Google fetches the image and
            # embeds it (via batch_update), the temp file is no longer needed.
            _temp_uploads_to_clean.append((client, file_id))
        except Exception as e:
            resolved.append({
                "insertText": {
                    "location": location,
                    "text": f"[image upload failed: {e}]\n",
                }
            })

    return resolved


# -- Metadata extraction --


def _doc_to_meta(
    doc_file: dict,
    folder_path: str,
    folder_id: str,
    content_hash: str,
    content_file: str,
    permissions: list[dict] | None = None,
) -> dict:
    """Build a YAML metadata dict from a Drive file + content info."""
    result: dict[str, Any] = {
        "id": doc_file.get("id", ""),
        "link": doc_file.get("webViewLink", ""),
        "title": doc_file.get("name", ""),
        "folder_path": folder_path,
        "folder_id": folder_id,
        "content_file": content_file,
        "content_hash": content_hash,
    }
    if permissions is not None:
        shared = []
        for p in permissions:
            # Skip owner (comes through as default)
            if p.get("role") == "owner":
                continue
            email = p.get("emailAddress", "")
            if email:
                shared.append({"email": email, "role": p.get("role", "reader")})
        if shared:
            result["shared_with"] = sorted(shared, key=lambda x: x["email"])
    result["created"] = doc_file.get("createdTime", "")
    result["updated"] = doc_file.get("modifiedTime", "")
    return result


# -- Pull --


def pull_docs(
    client: DocsClient,
    root_folder_id: str | None = None,
    sync_root_name: str | None = None,
    include_sharing: bool = False,
    dry_run: bool = False,
) -> dict:
    """Pull all docs under the sync root folder into local YAML+MD files.

    Args:
        client: DocsClient instance.
        root_folder_id: Drive root folder to look under. Defaults to GOOGLE_DRIVE_FOLDER_ID.
        sync_root_name: Name of the subfolder to mirror. Defaults to SYNC_ROOT_FOLDER_NAME.
        include_sharing: If True, fetch permissions for each doc (slower).
        dry_run: If True, list what would be written without writing.
    """
    root_id = root_folder_id  # None -> uses configured folder
    subfolder_name = sync_root_name or SYNC_ROOT_FOLDER_NAME

    # Find or create the sync root subfolder
    if dry_run:
        sync_root = client.find_folder_by_name(subfolder_name, root_id)
        if not sync_root:
            return {
                "action": "would_pull",
                "error": f"Sync root folder '{subfolder_name}' does not exist under root",
                "docs": 0,
            }
    else:
        sync_root = client.ensure_folder(subfolder_name, root_id)

    sync_root_id = sync_root["id"]
    base = sync_root_dir()

    # Walk the tree
    walked = client.walk_folder_tree(sync_root_id)

    written: list[str] = []

    if dry_run:
        for rel_path, doc_file in walked:
            slug = _slugify(doc_file.get("name", "untitled"))
            local_dir = base / rel_path if rel_path else base
            md_path = local_dir / f"{slug}.md"
            written.append(str(md_path))
        return {
            "action": "would_pull",
            "docs": len(walked),
            "sync_root": subfolder_name,
            "files": written,
        }

    # Ensure local base exists
    base.mkdir(parents=True, exist_ok=True)

    # Build an index of existing local files by doc id so we can preserve filenames
    existing_by_id = _load_all_local(base)
    existing_by_id = {k: v for k, v in existing_by_id.items() if not k.startswith("__new__:")}

    for rel_path, doc_file in walked:
        doc_id = doc_file["id"]
        title = doc_file.get("name", "untitled")

        # Preserve existing local filename if the id already exists locally
        if doc_id in existing_by_id:
            existing = existing_by_id[doc_id]
            yaml_path = Path(existing["_yaml_path"])
            md_path = Path(existing["_md_path"])
            yaml_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            slug = _slugify(title)
            local_dir = base / rel_path if rel_path else base
            local_dir.mkdir(parents=True, exist_ok=True)
            yaml_path = local_dir / f"{slug}.yaml"
            md_path = local_dir / f"{slug}.md"

        # Fetch full doc content
        doc = client.get_document(doc_id)
        md_content = docs_to_markdown(doc)
        # Preserve any existing local frontmatter — only the body is synced.
        _write_body_preserving_frontmatter(md_path, md_content)

        # Compute hash on body only (frontmatter is local-only).
        content_hash = _sha256(md_content)

        # Fetch permissions if requested
        permissions = None
        if include_sharing:
            try:
                permissions = client.list_permissions(doc_id)
            except Exception:
                permissions = []

        # Build folder_path (e.g., "knowledge-base/ecommerce-fundamentals")
        folder_path = subfolder_name if not rel_path else f"{subfolder_name}/{rel_path}"

        # Resolve folder_id for this doc's container
        container_folder_id = (doc_file.get("parents") or [sync_root_id])[0]

        meta = _doc_to_meta(
            doc_file=doc_file,
            folder_path=folder_path,
            folder_id=container_folder_id,
            content_hash=content_hash,
            content_file=md_path.name,
            permissions=permissions,
        )
        yaml_path.write_text(_dump_yaml(meta))

        written.append(str(yaml_path))
        written.append(str(md_path))

    # Write metadata
    metadata = {
        "last_pull": datetime.now(timezone.utc).isoformat(),
        "sync_root_name": subfolder_name,
        "sync_root_id": sync_root_id,
        "doc_count": len(walked),
    }
    (base / METADATA_FILE).write_text(json.dumps(metadata, indent=2))

    return {
        "action": "pulled",
        "docs": len(walked),
        "sync_root": subfolder_name,
        "sync_root_id": sync_root_id,
        "files": written,
        "metadata_file": str(base / METADATA_FILE),
    }


# -- Load all local --


def _load_all_local(base: Path) -> dict[str, dict]:
    """Load all YAML metadata files under the sync base.

    Returns dict keyed by doc id (for existing docs) or yaml path (for new docs without id).
    """
    result: dict[str, dict] = {}
    if not base.exists():
        return result
    for yaml_file in base.rglob("*.yaml"):
        # Skip metadata files
        if yaml_file.name.startswith("."):
            continue
        data = _load_yaml(yaml_file)
        if not data:
            continue
        # Attach the local paths for later use
        data["_yaml_path"] = str(yaml_file)
        data["_md_path"] = str(yaml_file.with_suffix(".md"))
        data["_rel_yaml"] = str(yaml_file.relative_to(base))
        key = data.get("id") or f"__new__:{yaml_file}"
        result[key] = data
    return result


def _read_md_content(md_path: str) -> str:
    """Read the sibling markdown file's BODY (frontmatter stripped).

    Frontmatter is local-only metadata — it should not affect hash comparison
    or be pushed to Drive.
    """
    return _body_for_sync(md_path)


# -- Diff --


def diff_docs(client: DocsClient) -> dict:
    """Compare local YAML+MD files against live Drive state.

    Returns a dict of changes:
    - content_changed: .md hash differs from stored hash
    - meta_changed: title/folder_path/shared_with differs from Drive
    - local_only: local file exists but no Drive doc (new, to be created)
    - remote_only: Drive doc exists but no local file (pull needed)
    """
    # Scan the entire gdocs/ tree, not just the sync root — vision/, drafts/,
    # and any other top-level subfolder should be diffable once a doc exists.
    base = SYNC_BASE
    local = _load_all_local(base)

    changes: list[dict] = []

    for key, meta in sorted(local.items()):
        if key.startswith("__new__:"):
            # New doc waiting to be created
            changes.append({
                "yaml": meta.get("_rel_yaml", ""),
                "action": "new",
                "title": meta.get("title", ""),
                "folder_path": meta.get("folder_path", ""),
            })
            continue

        doc_id = meta["id"]
        md_content = _read_md_content(meta["_md_path"])
        stored_hash = meta.get("content_hash", "")
        current_hash = _sha256(md_content)

        field_diffs: list[dict] = []
        if current_hash != stored_hash:
            field_diffs.append({
                "field": "content",
                "stored_hash": stored_hash,
                "current_hash": current_hash,
            })

        # Fetch remote meta to compare title/folder
        try:
            remote = (
                client._drive.files()
                .get(
                    fileId=doc_id,
                    fields="id, name, parents, createdTime, modifiedTime",
                    supportsAllDrives=True,
                )
                .execute()
            )
        except Exception as e:
            changes.append({"id": doc_id, "action": "error", "message": str(e)})
            continue

        if remote.get("name", "") != meta.get("title", ""):
            field_diffs.append({
                "field": "title",
                "local": meta.get("title", ""),
                "remote": remote.get("name", ""),
            })

        remote_parent = (remote.get("parents") or [""])[0]
        if remote_parent != meta.get("folder_id", ""):
            field_diffs.append({
                "field": "folder_id",
                "local": meta.get("folder_id", ""),
                "remote": remote_parent,
            })

        if field_diffs:
            changes.append({
                "id": doc_id,
                "title": meta.get("title", ""),
                "action": "modified",
                "fields": field_diffs,
            })

    return {"changes": changes, "total": len(changes)}


# -- Push --


def push_docs(
    client: DocsClient,
    files: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Push local changes to Drive.

    For each local YAML:
    - If no id: create doc in target folder, assign id
    - If content hash differs: write_markdown to Drive
    - If title differs: rename
    - If folder_path differs: move_to_folder

    Args:
        files: Optional list of .md or .yaml paths to push (filters local set).
        dry_run: Preview only.
    """
    # Scan the entire gdocs/ tree so docs outside the sync root (vision/,
    # drafts/, etc.) are pushable once they exist locally with a folder_id.
    base = SYNC_BASE
    local = _load_all_local(base)

    # Filter if specific files requested
    if files:
        wanted = set()
        for f in files:
            p = Path(f).resolve()
            # Match either the .md or .yaml path
            for key, meta in local.items():
                if Path(meta["_yaml_path"]).resolve() == p or Path(meta["_md_path"]).resolve() == p:
                    wanted.add(key)
        local = {k: v for k, v in local.items() if k in wanted}

    if not local:
        return {"action": "pushed", "results": [], "total": 0, "message": "No local docs found"}

    results: list[dict] = []

    for key, meta in sorted(local.items()):
        yaml_path = Path(meta["_yaml_path"])
        md_content = _read_md_content(meta["_md_path"])
        is_new = key.startswith("__new__:")

        if is_new:
            # Create new doc
            title = meta.get("title") or yaml_path.stem.replace("-", " ").title()
            folder_path = meta.get("folder_path", "")
            if dry_run:
                results.append({
                    "yaml": meta.get("_rel_yaml", ""),
                    "action": "would_create",
                    "title": title,
                    "folder_path": folder_path,
                })
                continue

            # Ensure target folder exists
            # folder_path is relative to root (e.g., "knowledge-base/ecommerce-fundamentals")
            # We need to resolve it under GOOGLE_DRIVE_FOLDER_ID
            target_folder = client.ensure_folder_path(folder_path) if folder_path else None
            target_id = target_folder["id"] if target_folder else None

            # Safety: check if a doc with this title already exists in the target folder
            # (protects against duplicate creation on retry after partial failure)
            doc_id = None
            if target_id:
                existing_docs = client.list_files(folder_id=target_id, max_results=200)
                for existing_doc in existing_docs:
                    if existing_doc.get("name") == title:
                        doc_id = existing_doc["id"]
                        break

            if not doc_id:
                # Create new doc
                created = client.create_document(title)
                doc_id = created.get("documentId") or created.get("id")
                # Move to target folder if different from default
                if target_id and doc_id:
                    client.move_to_folder(doc_id, target_id)

            # Write content
            if md_content.strip():
                md_path = Path(meta["_md_path"])
                _write_markdown_to_doc(client, doc_id, md_content, md_path.parent)

            # Update YAML with assigned id + hash of the body we pushed.
            # We intentionally do NOT overwrite the local .md file — local is
            # the source of truth, Drive is a rendered view.
            meta["id"] = doc_id
            meta["link"] = f"https://docs.google.com/document/d/{doc_id}/edit"
            meta["folder_id"] = target_id or ""
            meta["content_hash"] = _sha256(md_content)
            # Remove internal keys before writing
            clean_meta = {k: v for k, v in meta.items() if not k.startswith("_")}
            yaml_path.write_text(_dump_yaml(clean_meta))

            results.append({
                "yaml": meta.get("_rel_yaml", ""),
                "action": "created",
                "id": doc_id,
                "title": title,
            })
            continue

        # Existing doc — check for changes
        doc_id = meta["id"]
        stored_hash = meta.get("content_hash", "")
        current_hash = _sha256(md_content)

        actions_taken: list[str] = []

        # Content change
        if current_hash != stored_hash:
            if dry_run:
                actions_taken.append("content")
            else:
                md_path = Path(meta["_md_path"])
                _write_markdown_to_doc(client, doc_id, md_content, md_path.parent)
                # Store hash of what we pushed (body only).
                # Do NOT overwrite the local .md — local is source of truth.
                meta["content_hash"] = current_hash
                actions_taken.append("content")

        # Title/folder diff — fetch remote
        try:
            remote = (
                client._drive.files()
                .get(fileId=doc_id, fields="id, name, parents", supportsAllDrives=True)
                .execute()
            )
        except Exception as e:
            results.append({"id": doc_id, "action": "error", "message": str(e)})
            continue

        local_title = meta.get("title", "")
        if local_title and local_title != remote.get("name", ""):
            if dry_run:
                actions_taken.append("title")
            else:
                client._drive.files().update(
                    fileId=doc_id,
                    body={"name": local_title},
                    supportsAllDrives=True,
                ).execute()
                actions_taken.append("title")

        local_folder_path = meta.get("folder_path", "")
        remote_parent = (remote.get("parents") or [""])[0]
        if local_folder_path:
            # Resolve target folder
            if dry_run:
                target_id = meta.get("folder_id", "")
            else:
                target = client.ensure_folder_path(local_folder_path)
                target_id = target["id"]
            if target_id and target_id != remote_parent:
                if dry_run:
                    actions_taken.append("folder")
                else:
                    client.move_to_folder(doc_id, target_id)
                    meta["folder_id"] = target_id
                    actions_taken.append("folder")

        if not actions_taken:
            continue

        # Rewrite local YAML to persist updated hash/folder_id
        if not dry_run:
            clean_meta = {k: v for k, v in meta.items() if not k.startswith("_")}
            yaml_path.write_text(_dump_yaml(clean_meta))

        results.append({
            "id": doc_id,
            "title": meta.get("title", ""),
            "action": "would_update" if dry_run else "updated",
            "fields": actions_taken,
        })

    return {"action": "pushed", "results": results, "total": len(results)}


# -- Create helper (new doc from existing .md) --


def create_doc_from_file(
    md_path: Path,
    title: str | None = None,
    folder_path: str | None = None,
    jira_issues: list[str] | None = None,
) -> dict:
    """Create a new YAML+MD pair (without pushing to Drive).

    This is a local operation — the doc is created on Drive via push_docs.

    Args:
        md_path: Path to an existing .md file (must be under sync base).
        title: Doc title (defaults to filename).
        folder_path: folder_path for YAML (defaults to dir structure).

    Returns dict with status and the yaml path.
    """
    base = sync_root_dir()
    if not md_path.exists():
        return {"error": f"Markdown file not found: {md_path}"}

    # Read body only for hash (frontmatter is local-only)
    _, md_content = split_frontmatter(md_path.read_text())
    slug = md_path.stem
    effective_title = title or slug.replace("-", " ").title()

    # Compute folder_path from location if not given
    if folder_path is None:
        try:
            rel = md_path.parent.relative_to(base.parent)
            folder_path = str(rel)
        except ValueError:
            folder_path = SYNC_ROOT_FOLDER_NAME

    yaml_path = md_path.with_suffix(".yaml")

    meta: dict[str, Any] = {
        "id": "",
        "link": "",
        "title": effective_title,
        "folder_path": folder_path,
        "folder_id": "",
        "content_file": md_path.name,
        "content_hash": _sha256(md_content),
    }

    yaml_path.write_text(_dump_yaml(meta))

    # Optionally add to links registry
    linked_jira: list[str] = []
    if jira_issues:
        from ebdocs.links_registry import add_link
        gdocs_path = str(yaml_path.with_suffix("").relative_to(base.parent.parent)) \
            if base.parent.parent in yaml_path.parents else str(yaml_path.with_suffix(""))
        for key in jira_issues:
            add_link(key, gdocs_path)
            linked_jira.append(key)

    return {
        "action": "created_local",
        "yaml": str(yaml_path),
        "md": str(md_path),
        "title": effective_title,
        "folder_path": folder_path,
        "linked_jira": linked_jira,
        "next_step": "Run 'ebdocs sync push' to create on Drive",
    }
