"""Document management commands — create, read, write, list, delete Google Docs.

Examples:
    ebdocs doc create --title "Meeting Notes"
    ebdocs doc create --title "From Template" --template TEMPLATE_DOC_ID
    ebdocs doc create --title "From Markdown" --from-markdown notes.md
    ebdocs doc read DOC_ID --format plain
    ebdocs doc write DOC_ID --from-markdown content.md
    ebdocs doc write DOC_ID --content "# Hello" --append
    ebdocs doc list --limit 10 --format table
    ebdocs doc delete DOC_ID --confirm
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional
from urllib.parse import quote

import typer

from ebdocs.client import get_client
from ebdocs.config import get_config
from ebdocs.markdown import (
    _TableData,
    docs_to_markdown,
    markdown_to_requests,
    parse_pipe_table,
)
from ebdocs.models.doc import DocDetail, DocSummary
from ebdocs.output import Format, output_result

app = typer.Typer(name="doc", help="Create, read, write, and manage Google Docs")

# ── Shared option types ──

FormatOption = Annotated[
    Format,
    typer.Option("--format", "-f", help="Output format: json, table, or plain."),
]

JsonOption = Annotated[
    Optional[str],
    typer.Option("--json", "-j", help="Comma-separated fields to include in JSON output."),
]


def _default_format() -> Format:
    """Get the default output format from config."""
    config = get_config()
    try:
        return Format(config.default_format)
    except ValueError:
        return Format.json


# ── create ──


@app.command("create")
def create_doc(
    title: Annotated[str, typer.Option(help="Document title.")],
    template: Annotated[Optional[str], typer.Option(help="Template document ID to copy.")] = None,
    from_markdown: Annotated[Optional[Path], typer.Option(help="Markdown file to populate the document with.")] = None,
    folder_id: Annotated[Optional[str], typer.Option(help="Drive folder ID (overrides GOOGLE_DRIVE_FOLDER_ID).")] = None,
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Create a new Google Doc.

    Optionally copy from a template doc or populate from a markdown file.
    The doc is placed in the configured shared folder by default.

    Example: ebdocs doc create --title "Sprint Retro" --from-markdown retro.md
    """
    client = get_client()
    target_folder = folder_id or client._folder_id

    if template:
        # Copy from template
        result = client.copy_file(template, title=title)
        doc_id = result["id"]
        # If a custom folder was specified, move there (copy_file uses default folder)
        if folder_id:
            client.move_to_folder(doc_id, folder_id)
    else:
        # Create blank document
        doc = client.create_document(title)
        doc_id = doc["documentId"]
        # If a custom folder was specified (different from default), move there
        if folder_id:
            client.move_to_folder(doc_id, folder_id)

    # Populate with markdown content if provided
    if from_markdown:
        if not from_markdown.exists():
            typer.echo(f"File not found: {from_markdown}", err=True)
            raise typer.Exit(1)
        content = from_markdown.read_text(encoding="utf-8")
        requests = markdown_to_requests(content)
        if requests:
            client.batch_update(doc_id, requests)

    # Build summary response
    summary = DocSummary(
        id=doc_id,
        title=title,
        url=f"https://docs.google.com/document/d/{doc_id}/edit",
    )
    output_result(summary.model_dump(), format=format, json_fields=json_fields)


# ── read ──


@app.command("read")
def read_doc(
    doc_id: Annotated[str, typer.Argument(help="Document ID to read.")],
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Read a Google Doc and output its content.

    In plain mode, outputs just the markdown content.
    In json mode, outputs a DocDetail model with metadata and content.

    Example: ebdocs doc read 1a2b3c4d --format plain
    """
    client = get_client()
    doc = client.get_document(doc_id)
    markdown_text = docs_to_markdown(doc)

    if format == Format.plain:
        typer.echo(markdown_text)
        return

    detail = DocDetail.from_doc_resource(doc, text=markdown_text)
    output_result(detail.model_dump(), format=format, json_fields=json_fields)


# ── write ──


@app.command("write")
def write_doc(
    doc_id: Annotated[str, typer.Argument(help="Document ID to write to.")],
    content: Annotated[Optional[str], typer.Option(help="Markdown content to write (mutually exclusive with --from-markdown).")] = None,
    from_markdown: Annotated[Optional[Path], typer.Option(help="Markdown file to write (mutually exclusive with --content).")] = None,
    append: Annotated[bool, typer.Option("--append", help="Append to existing content instead of replacing.")] = False,
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Write markdown content to a Google Doc.

    By default, replaces all existing content. Use --append to add to the end.
    Provide content via --content or --from-markdown (mutually exclusive).

    Example: ebdocs doc write DOC_ID --from-markdown notes.md --append
    """
    # Validate mutual exclusivity
    if content and from_markdown:
        typer.echo("Error: --content and --from-markdown are mutually exclusive.", err=True)
        raise typer.Exit(1)
    if not content and not from_markdown:
        typer.echo("Error: provide either --content or --from-markdown.", err=True)
        raise typer.Exit(1)

    # Resolve content
    if from_markdown:
        if not from_markdown.exists():
            typer.echo(f"File not found: {from_markdown}", err=True)
            raise typer.Exit(1)
        md_text = from_markdown.read_text(encoding="utf-8")
    else:
        md_text = content  # type: ignore[assignment]

    client = get_client()

    if not append:
        # Delete all existing content before writing.
        # Fetch the doc to find the end index of the body.
        doc = client.get_document(doc_id)
        body = doc.get("body", {})
        body_content = body.get("content", [])

        # Find the end index (last element's endIndex - 1 to preserve final newline)
        if body_content:
            end_index = body_content[-1].get("endIndex", 1)
            # The body always has at least index 1; content starts at 1
            # Delete from index 1 to end_index - 1 (keep the trailing newline)
            if end_index > 2:
                delete_requests = [
                    {
                        "deleteContentRange": {
                            "range": {
                                "startIndex": 1,
                                "endIndex": end_index - 1,
                            }
                        }
                    }
                ]
                client.batch_update(doc_id, delete_requests)

    # Convert markdown to requests and apply
    requests = markdown_to_requests(md_text)
    if not requests:
        output_result(
            {"document_id": doc_id, "message": "No content to write.", "word_count": 0},
            format=format,
            json_fields=json_fields,
        )
        return

    if append:
        # For append, we need to insert at the end of the document.
        # Fetch the doc to find the end index.
        doc = client.get_document(doc_id)
        body = doc.get("body", {})
        body_content = body.get("content", [])
        if body_content:
            end_index = body_content[-1].get("endIndex", 1)
            insert_index = end_index - 1  # before the final newline
        else:
            insert_index = 1

        # Adjust all request indices: shift insertText locations and range indices
        adjusted_requests = _adjust_requests_for_index(requests, insert_index)
        client.batch_update(doc_id, adjusted_requests)
    else:
        # Replace mode: content was already deleted, insert at index 1
        client.batch_update(doc_id, requests)

    word_count = len(md_text.split())
    output_result(
        {"document_id": doc_id, "message": "Content written successfully.", "word_count": word_count},
        format=format,
        json_fields=json_fields,
    )


def _adjust_requests_for_index(requests: list[dict], base_index: int) -> list[dict]:
    """Shift all indices in batch update requests from base 1 to base_index.

    The markdown_to_requests function generates requests starting at index 1.
    For append mode, we need to shift all indices to start at the end of
    the existing document content.
    """
    offset = base_index - 1
    if offset == 0:
        return requests

    adjusted: list[dict] = []
    for req in requests:
        if "insertText" in req:
            r = req["insertText"]
            adjusted.append({
                "insertText": {
                    "location": {"index": r["location"]["index"] + offset},
                    "text": r["text"],
                }
            })
        elif "updateParagraphStyle" in req:
            r = req["updateParagraphStyle"]
            adjusted.append({
                "updateParagraphStyle": {
                    "range": {
                        "startIndex": r["range"]["startIndex"] + offset,
                        "endIndex": r["range"]["endIndex"] + offset,
                    },
                    "paragraphStyle": r["paragraphStyle"],
                    "fields": r["fields"],
                }
            })
        elif "createParagraphBullets" in req:
            r = req["createParagraphBullets"]
            adjusted.append({
                "createParagraphBullets": {
                    "range": {
                        "startIndex": r["range"]["startIndex"] + offset,
                        "endIndex": r["range"]["endIndex"] + offset,
                    },
                    "bulletPreset": r["bulletPreset"],
                }
            })
        elif "updateTextStyle" in req:
            r = req["updateTextStyle"]
            adjusted.append({
                "updateTextStyle": {
                    "range": {
                        "startIndex": r["range"]["startIndex"] + offset,
                        "endIndex": r["range"]["endIndex"] + offset,
                    },
                    "textStyle": r["textStyle"],
                    "fields": r["fields"],
                }
            })
        elif "insertSectionBreak" in req:
            r = req["insertSectionBreak"]
            adjusted.append({
                "insertSectionBreak": {
                    "location": {"index": r["location"]["index"] + offset},
                    "sectionType": r["sectionType"],
                }
            })
        elif "insertPageBreak" in req:
            r = req["insertPageBreak"]
            adjusted.append({
                "insertPageBreak": {
                    "location": {"index": r["location"]["index"] + offset},
                }
            })
        elif "insertTableOfContents" in req:
            r = req["insertTableOfContents"]
            adjusted.append({
                "insertTableOfContents": {
                    "location": {"index": r["location"]["index"] + offset},
                }
            })
        elif "_deferredTable" in req:
            r = req["_deferredTable"]
            adjusted.append({
                "_deferredTable": {
                    "insertTable": {
                        "rows": r["insertTable"]["rows"],
                        "columns": r["insertTable"]["columns"],
                        "location": {"index": r["insertTable"]["location"]["index"] + offset},
                    },
                    "cells": r["cells"],
                }
            })
        elif "_deferredFootnote" in req:
            r = req["_deferredFootnote"]
            adjusted.append({
                "_deferredFootnote": {
                    "createFootnote": {
                        "location": {"index": r["createFootnote"]["location"]["index"] + offset},
                    },
                    "content": r["content"],
                    "footnoteId": r["footnoteId"],
                }
            })
        else:
            # Pass through unknown request types unchanged
            adjusted.append(req)

    return adjusted


# ── list ──


@app.command("list")
def list_docs(
    folder_id: Annotated[Optional[str], typer.Option(help="Drive folder ID (defaults to config).")] = None,
    limit: Annotated[int, typer.Option(help="Max results to return.")] = 25,
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """List Google Docs in a Drive folder.

    Defaults to the configured GOOGLE_DRIVE_FOLDER_ID.

    Example: ebdocs doc list --limit 10 --format table
    """
    client = get_client()
    files = client.list_files(folder_id=folder_id, max_results=limit)

    summaries = [DocSummary.from_drive_file(f).model_dump() for f in files]
    output_result(
        summaries,
        format=format,
        json_fields=json_fields,
        columns=["id", "title", "modified_time", "url"],
    )


# ── headings ──


@app.command("headings")
def doc_headings(
    doc_id: Annotated[str, typer.Argument(help="Document ID.")],
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """List all headings in a doc with anchor links.

    Returns heading level, text, heading ID, and a clickable URL
    that jumps directly to that section.

    Example: ebdocs doc headings DOC_ID --format table
    """
    client = get_client()
    doc = client.get_document(doc_id)
    base_url = f"https://docs.google.com/document/d/{doc_id}/edit"

    headings = []
    for elem in doc.get("body", {}).get("content", []):
        para = elem.get("paragraph")
        if not para:
            continue
        style = para.get("paragraphStyle", {})
        named_style = style.get("namedStyleType", "")
        if not named_style.startswith("HEADING"):
            continue

        heading_id = style.get("headingId", "")
        text = "".join(
            run.get("textRun", {}).get("content", "")
            for run in para.get("elements", [])
        ).strip()
        level = named_style.replace("HEADING_", "")

        headings.append({
            "level": int(level) if level.isdigit() else 0,
            "text": text,
            "heading_id": heading_id,
            "url": f"{base_url}#heading={heading_id}" if heading_id else base_url,
        })

    output_result(
        headings,
        format=format,
        json_fields=json_fields,
        columns=["level", "text", "url"],
    )


# ── links ──


@app.command("links")
def doc_links(
    doc_id: Annotated[str, typer.Argument(help="Document ID.")],
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """List all linkable elements in a doc: headings, comments, and bookmarks.

    Returns a unified list with type, label, and URL for each element.
    Useful for building Jira comments with deep links into specific
    sections or comments.

    Example: ebdocs doc links DOC_ID --format table
    """
    client = get_client()
    doc = client.get_document(doc_id)
    base_url = f"https://docs.google.com/document/d/{doc_id}/edit"

    links = []

    # Headings
    for elem in doc.get("body", {}).get("content", []):
        para = elem.get("paragraph")
        if not para:
            continue
        style = para.get("paragraphStyle", {})
        named_style = style.get("namedStyleType", "")
        if not named_style.startswith("HEADING"):
            continue
        heading_id = style.get("headingId", "")
        text = "".join(
            run.get("textRun", {}).get("content", "")
            for run in para.get("elements", [])
        ).strip()
        level = named_style.replace("HEADING_", "")
        links.append({
            "type": f"h{level}",
            "label": text,
            "url": f"{base_url}#heading={heading_id}" if heading_id else base_url,
        })

    # Comments (via Drive API)
    try:
        comments = client._drive.comments().list(
            fileId=doc_id,
            fields="comments(id,content,resolved,quotedFileContent)",
        ).execute()
        for c in comments.get("comments", []):
            if c.get("resolved"):
                continue
            comment_id = c["id"]
            content = c.get("content", "")[:60]
            quoted = c.get("quotedFileContent", {}).get("value", "")
            label = f'"{quoted[:40]}..." → {content}' if quoted else content
            links.append({
                "type": "comment",
                "label": label,
                "url": f"{base_url}?disco={comment_id}",
            })
    except Exception:
        pass  # Comments may not be accessible; skip

    # Bookmarks
    for bm_id in doc.get("namedRanges", {}):
        links.append({
            "type": "bookmark",
            "label": bm_id,
            "url": f"{base_url}#bookmark=id.{bm_id}",
        })

    output_result(
        links,
        format=format,
        json_fields=json_fields,
        columns=["type", "label", "url"],
    )


# ── highlight ──


@app.command("highlight")
def doc_highlight(
    doc_id: Annotated[str, typer.Argument(help="Document ID.")],
    text: Annotated[str, typer.Option("--text", "-t", help="Text to highlight (exact match).")],
    prefix: Annotated[Optional[str], typer.Option("--prefix", help="Text before the highlight (for disambiguation).")] = None,
    suffix: Annotated[Optional[str], typer.Option("--suffix", help="Text after the highlight (for disambiguation).")] = None,
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Generate a Chrome text fragment link that highlights specific text.

    Uses the Chrome "Link to highlight" feature (#:~:text=). Works in any
    Chromium browser. The link scrolls to and highlights the matched text.

    Example:
        ebdocs doc highlight DOC_ID --text "62% of stores"
        ebdocs doc highlight DOC_ID --text "Dawn" --prefix "Migrate to"

    See: https://support.google.com/chrome/answer/10256233
    """
    base_url = f"https://docs.google.com/document/d/{doc_id}/edit"

    # Build text fragment: #:~:text=[prefix-,]textStart[,textEnd][,-suffix]
    # Simple case: just the text
    fragment = quote(text, safe="")

    if prefix and suffix:
        fragment = f"{quote(prefix, safe='')}-,{quote(text, safe='')},-{quote(suffix, safe='')}"
    elif prefix:
        fragment = f"{quote(prefix, safe='')}-,{quote(text, safe='')}"
    elif suffix:
        fragment = f"{quote(text, safe='')},-{quote(suffix, safe='')}"

    url = f"{base_url}#:~:text={fragment}"

    if format == Format.plain:
        typer.echo(url)
    else:
        output_result(
            {
                "document_id": doc_id,
                "text": text,
                "prefix": prefix,
                "suffix": suffix,
                "url": url,
            },
            format=format,
            json_fields=json_fields,
        )


# ── bookmarks ──


@app.command("bookmarks")
def doc_bookmarks(
    doc_id: Annotated[str, typer.Argument(help="Document ID.")],
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """List all bookmarks in a doc with links.

    Bookmarks are named anchors that can be linked to from other docs
    or Jira comments. Create them with 'doc bookmark-add'.

    Example: ebdocs doc bookmarks DOC_ID --format table
    """
    client = get_client()
    doc = client.get_document(doc_id)
    base_url = f"https://docs.google.com/document/d/{doc_id}/edit"

    bookmarks = []

    # Google Docs stores bookmarks in the body content as inlineObjectElements
    # or via namedRanges. Let's check both.
    for nr_name, nr_data in doc.get("namedRanges", {}).items():
        ranges = nr_data.get("namedRanges", [])
        for r in ranges:
            nr_id = r.get("namedRangeId", "")
            start = r.get("ranges", [{}])[0].get("startIndex", 0) if r.get("ranges") else 0
            bookmarks.append({
                "name": nr_name,
                "id": nr_id,
                "index": start,
                "url": f"{base_url}#bookmark=kix.{nr_id}",
            })

    # Also check for inline bookmarks in body content
    for elem in doc.get("body", {}).get("content", []):
        para = elem.get("paragraph")
        if not para:
            continue
        for pe in para.get("elements", []):
            if "person" in pe or "inlineObjectElement" in pe:
                continue
            # Check for bookmarkId in the element
            text_run = pe.get("textRun", {})
            text_style = text_run.get("textStyle", {})
            if text_style.get("link", {}).get("bookmarkId"):
                bm_id = text_style["link"]["bookmarkId"]
                bookmarks.append({
                    "name": text_run.get("content", "").strip(),
                    "id": bm_id,
                    "index": pe.get("startIndex", 0),
                    "url": f"{base_url}#bookmark=id.{bm_id}",
                })

    if not bookmarks:
        output_result(
            {"message": "No bookmarks found. Use headings or text highlights for deep links."},
            format=format,
        )
        return

    output_result(
        bookmarks,
        format=format,
        json_fields=json_fields,
        columns=["name", "id", "url"],
    )


# ── bookmark-add ──


@app.command("bookmark-add")
def doc_bookmark_add(
    doc_id: Annotated[str, typer.Argument(help="Document ID.")],
    name: Annotated[str, typer.Option("--name", "-n", help="Bookmark name (used as anchor label).")],
    at_text: Annotated[Optional[str], typer.Option("--at-text", help="Place bookmark before this text (first match).")] = None,
    at_index: Annotated[Optional[int], typer.Option("--at-index", help="Place bookmark at this character index.")] = None,
    at_heading: Annotated[Optional[str], typer.Option("--at-heading", help="Place bookmark at the heading containing this text.")] = None,
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Create a named bookmark in the doc and return its link.

    Specify where to place the bookmark with one of:
      --at-text    First occurrence of this text
      --at-heading Heading containing this text
      --at-index   Exact character index

    Example:
        ebdocs doc bookmark-add DOC_ID --name "findings" --at-heading "Key Findings"
        ebdocs doc bookmark-add DOC_ID --name "recommendation-1" --at-text "Migrate to Dawn"
    """
    if not at_text and at_index is None and not at_heading:
        typer.echo("Error: provide --at-text, --at-heading, or --at-index.", err=True)
        raise typer.Exit(1)

    client = get_client()
    doc = client.get_document(doc_id)
    base_url = f"https://docs.google.com/document/d/{doc_id}/edit"

    # Resolve the index
    insert_index = at_index

    if at_heading:
        for elem in doc.get("body", {}).get("content", []):
            para = elem.get("paragraph")
            if not para:
                continue
            style = para.get("paragraphStyle", {})
            if not style.get("namedStyleType", "").startswith("HEADING"):
                continue
            text = "".join(
                run.get("textRun", {}).get("content", "")
                for run in para.get("elements", [])
            ).strip()
            if at_heading.lower() in text.lower():
                insert_index = elem.get("startIndex", 1)
                break
        if insert_index is None:
            typer.echo(f"Error: heading containing '{at_heading}' not found.", err=True)
            raise typer.Exit(1)

    if at_text and insert_index is None:
        # Search through all text runs for the first match
        for elem in doc.get("body", {}).get("content", []):
            para = elem.get("paragraph")
            if not para:
                continue
            for pe in para.get("elements", []):
                tr = pe.get("textRun", {})
                content = tr.get("content", "")
                pos = content.find(at_text)
                if pos >= 0:
                    insert_index = pe.get("startIndex", 1) + pos
                    break
            if insert_index is not None:
                break
        if insert_index is None:
            typer.echo(f"Error: text '{at_text}' not found in document.", err=True)
            raise typer.Exit(1)

    # Create a named range (bookmark) via batchUpdate
    requests = [
        {
            "createNamedRange": {
                "name": name,
                "range": {
                    "startIndex": insert_index,
                    "endIndex": insert_index + 1,  # Must span at least 1 char
                },
            }
        }
    ]

    result = client.batch_update(doc_id, requests)

    # Extract the named range ID from the response
    named_range_id = ""
    for reply in result.get("replies", []):
        cnr = reply.get("createNamedRange", {})
        if cnr.get("namedRangeId"):
            named_range_id = cnr["namedRangeId"]
            break

    # Named range IDs already include "kix." prefix
    url = f"{base_url}#bookmark={named_range_id}" if named_range_id else base_url

    output_result(
        {
            "document_id": doc_id,
            "bookmark_name": name,
            "bookmark_id": named_range_id,
            "index": insert_index,
            "url": url,
        },
        format=format,
        json_fields=json_fields,
    )


# ── image ──


@app.command("image")
def doc_image(
    doc_id: Annotated[str, typer.Argument(help="Document ID.")],
    url: Annotated[str, typer.Option("--url", "-u", help="Public URL of the image (PNG, JPG, SVG).")],
    width: Annotated[Optional[int], typer.Option(help="Width in points (72 pts = 1 inch).")] = None,
    height: Annotated[Optional[int], typer.Option(help="Height in points.")] = None,
    append: Annotated[bool, typer.Option("--append", help="Insert at end of doc (default: beginning).")] = True,
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Insert an image into a Google Doc from a public URL.

    The image URL must be publicly accessible (Google's servers fetch it).
    For Mermaid diagrams, use mermaid.ink to render:
      https://mermaid.ink/svg/<base64-encoded-diagram>

    Example:
        ebdocs doc image DOC_ID --url "https://mermaid.ink/svg/..." --width 468
    """
    client = get_client()

    # Find insert index
    if append:
        doc = client.get_document(doc_id)
        body_content = doc.get("body", {}).get("content", [])
        insert_index = body_content[-1].get("endIndex", 2) - 1 if body_content else 1
    else:
        insert_index = 1

    requests = [
        {
            "insertInlineImage": {
                "location": {"index": insert_index},
                "uri": url,
                **({"objectSize": {
                    "width": {"magnitude": width, "unit": "PT"},
                    **({"height": {"magnitude": height, "unit": "PT"}} if height else {}),
                }} if width else {}),
            }
        }
    ]

    result = client.batch_update(doc_id, requests)

    # Extract inline object ID from response
    obj_id = ""
    for reply in result.get("replies", []):
        iio = reply.get("insertInlineImage", {})
        if iio.get("objectId"):
            obj_id = iio["objectId"]
            break

    output_result(
        {
            "document_id": doc_id,
            "image_url": url,
            "object_id": obj_id,
            "index": insert_index,
            "message": "Image inserted.",
        },
        format=format,
        json_fields=json_fields,
    )


# ── image-upload ──


@app.command("image-upload")
def doc_image_upload(
    doc_id: Annotated[str, typer.Argument(help="Document ID.")],
    file: Annotated[Path, typer.Option("--file", "-f", help="Local image file path (PNG, JPG, SVG, GIF).")],
    width: Annotated[Optional[int], typer.Option(help="Width in points (72 pts = 1 inch).")] = None,
    height: Annotated[Optional[int], typer.Option(help="Height in points.")] = None,
    append: Annotated[bool, typer.Option("--append", help="Insert at end of doc.")] = True,
    keep_file: Annotated[bool, typer.Option("--keep-file", help="Keep the uploaded file in Drive (default: delete after embedding).")] = False,
    format_opt: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Upload a local image to Drive and embed it in a Google Doc.

    Unlike 'doc image' (which requires a public URL), this command uploads
    a local file to Google Drive, makes it publicly readable, inserts it
    into the doc, and optionally deletes the Drive file afterwards.

    Great for Mermaid diagrams rendered locally:
        mmdc -i diagram.mmd -o diagram.png
        ebdocs doc image-upload DOC_ID --file diagram.png --width 468

    Example:
        ebdocs doc image-upload DOC_ID --file screenshot.png
        ebdocs doc image-upload DOC_ID --file chart.svg --width 400 --keep-file
    """
    from googleapiclient.http import MediaFileUpload

    if not file.exists():
        typer.echo(f"Error: file not found: {file}", err=True)
        raise typer.Exit(1)

    # Detect MIME type
    suffix = file.suffix.lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
        ".webp": "image/webp",
    }
    mime_type = mime_map.get(suffix)
    if not mime_type:
        typer.echo(f"Error: unsupported image format '{suffix}'. Use PNG, JPG, SVG, GIF, or WebP.", err=True)
        raise typer.Exit(1)

    client = get_client()

    # 1. Upload to Drive
    media = MediaFileUpload(str(file), mimetype=mime_type, resumable=True)
    drive_file = client._drive.files().create(
        body={
            "name": file.name,
            "mimeType": mime_type,
        },
        media_body=media,
        fields="id,webContentLink",
    ).execute()
    file_id = drive_file["id"]

    # 2. Make publicly readable (Google Docs needs to fetch it)
    client._drive.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()

    # 3. Get the direct content URL
    # Use the thumbnail/content link format that Google Docs can fetch
    image_url = f"https://drive.google.com/uc?id={file_id}&export=download"

    # 4. Find insert index
    if append:
        doc = client.get_document(doc_id)
        body_content = doc.get("body", {}).get("content", [])
        insert_index = body_content[-1].get("endIndex", 2) - 1 if body_content else 1
    else:
        insert_index = 1

    # 5. Insert into doc
    requests = [
        {
            "insertInlineImage": {
                "location": {"index": insert_index},
                "uri": image_url,
                **({"objectSize": {
                    "width": {"magnitude": width, "unit": "PT"},
                    **({"height": {"magnitude": height, "unit": "PT"}} if height else {}),
                }} if width else {}),
            }
        }
    ]

    result = client.batch_update(doc_id, requests)

    obj_id = ""
    for reply in result.get("replies", []):
        iio = reply.get("insertInlineImage", {})
        if iio.get("objectId"):
            obj_id = iio["objectId"]
            break

    # 6. Optionally delete the Drive file (image is now embedded in the doc)
    if not keep_file:
        try:
            client._drive.files().delete(fileId=file_id).execute()
        except Exception:
            pass  # Non-critical — image is already in the doc

    output_result(
        {
            "document_id": doc_id,
            "file": str(file),
            "drive_file_id": file_id if keep_file else "(deleted)",
            "object_id": obj_id,
            "index": insert_index,
            "message": "Image uploaded and inserted.",
        },
        format=format_opt,
        json_fields=json_fields,
    )



# ── table ──


@app.command("table")
def doc_table(
    doc_id: Annotated[str, typer.Argument(help="Document ID.")],
    content: Annotated[
        Optional[str],
        typer.Option("--content", "-c", help="Pipe-delimited: 'H1|H2\\nR1|R2'."),
    ] = None,
    from_csv: Annotated[
        Optional[Path],
        typer.Option("--from-csv", help="CSV file to import as a table."),
    ] = None,
    rows: Annotated[
        Optional[int],
        typer.Option(help="Create empty table with this many rows."),
    ] = None,
    cols: Annotated[
        Optional[int],
        typer.Option(help="Create empty table with this many columns."),
    ] = None,
    append: Annotated[
        bool,
        typer.Option("--append", help="Insert at end of doc (default)."),
    ] = True,
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Insert a table into a Google Doc.

    Tables require a two-pass approach: first insert the table structure,
    then fetch the doc to discover cell indices, then fill cell contents.

    Provide content via --content (pipe-delimited), --from-csv (CSV file),
    or --rows/--cols (empty table).

    Examples:
        ebdocs doc table DOC_ID --content "Name|Age\\nAlice|30\\nBob|25"
        ebdocs doc table DOC_ID --from-csv data.csv
        ebdocs doc table DOC_ID --rows 3 --cols 2
    """
    import csv
    import io

    # Validate input — exactly one source
    sources = sum([
        content is not None,
        from_csv is not None,
        rows is not None or cols is not None,
    ])
    if sources == 0:
        typer.echo("Error: provide --content, --from-csv, or --rows/--cols.", err=True)
        raise typer.Exit(1)
    if sources > 1:
        typer.echo(
            "Error: --content, --from-csv, and --rows/--cols "
            "are mutually exclusive.", err=True,
        )
        raise typer.Exit(1)

    table_data: _TableData | None = None

    if content:
        # Parse pipe-delimited content (supports \n for newlines)
        raw = content.replace("\\n", "\n")
        parsed_lines = [line.strip() for line in raw.split("\n") if line.strip()]
        if not parsed_lines:
            typer.echo("Error: --content is empty.", err=True)
            raise typer.Exit(1)
        # If lines already have pipe format (| col | col |), parse as pipe table
        if parsed_lines[0].startswith("|"):
            table_data = parse_pipe_table(raw)
        else:
            # Simple pipe-delimited: "H1|H2\nR1|R2"
            all_rows = [line.split("|") for line in parsed_lines]
            headers = [c.strip() for c in all_rows[0]]
            data_rows = [[c.strip() for c in r] for r in all_rows[1:]]
            table_data = _TableData(headers=headers, rows=data_rows)

    elif from_csv:
        if not from_csv.exists():
            typer.echo(f"Error: file not found: {from_csv}", err=True)
            raise typer.Exit(1)
        csv_text = from_csv.read_text(encoding="utf-8")
        reader = csv.reader(io.StringIO(csv_text))
        all_rows = list(reader)
        if len(all_rows) < 1:
            typer.echo("Error: CSV file is empty.", err=True)
            raise typer.Exit(1)
        headers = all_rows[0]
        data_rows = all_rows[1:]
        table_data = _TableData(headers=headers, rows=data_rows)

    elif rows is not None or cols is not None:
        r = rows or 2
        c = cols or 2
        headers = [f"Column {i+1}" for i in range(c)]
        data_rows = [["" for _ in range(c)] for _ in range(r - 1)]
        table_data = _TableData(headers=headers, rows=data_rows)

    if not table_data:
        typer.echo("Error: could not parse table data.", err=True)
        raise typer.Exit(1)

    client = get_client()

    # Find insert index
    if append:
        doc = client.get_document(doc_id)
        body_content = doc.get("body", {}).get("content", [])
        insert_index = body_content[-1].get("endIndex", 2) - 1 if body_content else 1
    else:
        insert_index = 1

    # Pass 1: Insert the table structure
    num_rows = len(table_data.rows) + 1  # +1 for header
    num_cols = len(table_data.headers)
    insert_requests = [{
        "insertTable": {
            "rows": num_rows,
            "columns": num_cols,
            "location": {"index": insert_index},
        }
    }]
    client.batch_update(doc_id, insert_requests)

    # Pass 2: Fetch the doc to discover cell indices, then fill content
    doc = client.get_document(doc_id)
    all_cells = [table_data.headers] + table_data.rows
    cell_requests = _build_table_cell_requests(doc, insert_index, all_cells)
    if cell_requests:
        client.batch_update(doc_id, cell_requests)

    output_result(
        {
            "document_id": doc_id,
            "rows": num_rows,
            "columns": num_cols,
            "cells_filled": sum(1 for row in all_cells for c in row if c.strip()),
            "message": "Table inserted.",
        },
        format=format,
        json_fields=json_fields,
    )


def _build_table_cell_requests(
    doc: dict,
    insert_index: int,
    cells: list[list[str]],
) -> list[dict]:
    """Build insertText requests for table cells after the table structure exists.

    Finds the table in the document body that starts at or after insert_index,
    then inserts text into each cell. Requests are built in reverse order
    so that indices remain valid.

    Args:
        doc: Full document resource from the Docs API.
        insert_index: The index where the table was inserted.
        cells: 2D list of cell contents (headers + data rows).

    Returns:
        List of insertText request dicts.
    """
    body = doc.get("body", {})
    content = body.get("content", [])

    # Find the table element at or after insert_index
    table_elem = None
    for elem in content:
        table = elem.get("table")
        if table:
            start_idx = elem.get("startIndex", 0)
            if start_idx >= insert_index:
                table_elem = table
                break

    if not table_elem:
        return []

    # Collect cell start indices
    requests: list[dict] = []
    table_rows = table_elem.get("tableRows", [])
    for row_idx, table_row in enumerate(table_rows):
        table_cells = table_row.get("tableCells", [])
        for col_idx, table_cell in enumerate(table_cells):
            if row_idx >= len(cells) or col_idx >= len(cells[row_idx]):
                continue
            text = cells[row_idx][col_idx]
            if not text:
                continue
            # Each cell has content with at least one paragraph
            cell_content = table_cell.get("content", [])
            if not cell_content:
                continue
            # Get the start index of the first paragraph in the cell
            first_para = cell_content[0]
            para = first_para.get("paragraph")
            if not para:
                continue
            elements = para.get("elements", [])
            if not elements:
                continue
            cell_start = elements[0].get("startIndex", 0)
            requests.append({
                "insertText": {
                    "location": {"index": cell_start},
                    "text": text,
                }
            })

    # Reverse so higher indices are inserted first (avoids index shifting)
    requests.reverse()
    return requests


# ── delete ──


@app.command("delete")
def delete_doc(
    doc_id: Annotated[str, typer.Argument(help="Document ID to delete.")],
    confirm: Annotated[bool, typer.Option("--confirm", help="Required flag to confirm deletion.")] = False,
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Move a Google Doc to trash.

    Requires --confirm flag to prevent accidental deletion.

    Example: ebdocs doc delete DOC_ID --confirm
    """
    if not confirm:
        typer.echo("Error: --confirm flag is required to delete a document.", err=True)
        raise typer.Exit(1)

    client = get_client()
    # Move to trash via Drive API update
    client._drive.files().update(
        fileId=doc_id,
        body={"trashed": True},
    ).execute()

    output_result(
        {"document_id": doc_id, "message": "Document moved to trash."},
        format=format,
        json_fields=json_fields,
    )


# ── validate ──


def _is_em_dash_exempt(para: dict, text: str) -> bool:
    """Return True if a paragraph is exempt from the em/en-dash check.

    Three categories are exempt:
      1. Quoted text — the stripped paragraph starts and ends with a
         quotation mark (curly or straight), optionally with a trailing
         punctuation mark.
      2. Blockquote — paragraphStyle.namedStyleType == "BLOCKQUOTE".
      3. All-italic paragraph — every non-empty textRun is italic
         (likely a caption or aside).
    """
    import re as _re

    # Blockquote style
    named = para.get("paragraphStyle", {}).get("namedStyleType", "")
    if named == "BLOCKQUOTE":
        return True

    # Quoted text
    stripped = (text or "").strip()
    if stripped and _re.match(r"^[\u201c\u2018\"\']", stripped) and _re.search(
        r"[\u201d\u2019\"\'][\.\,\!\?\;\:]?$", stripped
    ):
        return True

    # All-italic paragraph
    runs = [
        r.get("textRun")
        for r in para.get("elements", [])
        if r.get("textRun") and r.get("textRun", {}).get("content", "").strip()
    ]
    if runs and all(
        r.get("textStyle", {}).get("italic") is True for r in runs
    ):
        return True

    return False


def collect_doc_issues(
    doc: dict,
    source_path: Optional[Path] = None,
) -> tuple[list[dict], list[str], int]:
    """Run all validation checks against a fetched Google Doc.

    Returns (issues, checks_run, list_run_count). Used by both the
    `validate` CLI command and by `sync push --strict`.

    See the `validate` command docstring for the full list of checks.
    """
    import re

    body = doc.get("body", {}).get("content", [])
    issues: list[dict] = []
    list_runs: list[dict] = []
    current_run: dict | None = None
    last_heading_level = 0

    for el in body:
        para = el.get("paragraph")
        if not para:
            if current_run is not None:
                list_runs.append(current_run)
                current_run = None
            continue

        style = para.get("paragraphStyle", {})
        named = style.get("namedStyleType", "NORMAL_TEXT")
        bullet = para.get("bullet")
        text = "".join(
            r.get("textRun", {}).get("content", "")
            for r in para.get("elements", [])
        ).strip()

        if named.startswith("HEADING") and bullet is not None:
            issues.append({
                "kind": "heading_with_bullet",
                "level": named.replace("HEADING_", ""),
                "text": text[:60],
                "list_id": bullet.get("listId", ""),
            })

        if named.startswith("HEADING"):
            try:
                level = int(named.replace("HEADING_", ""))
            except ValueError:
                level = 0
            if level > 0 and last_heading_level > 0 and level > last_heading_level + 1:
                issues.append({
                    "kind": "heading_level_skip",
                    "from": last_heading_level,
                    "to": level,
                    "text": text[:60],
                })
            if level > 0:
                last_heading_level = level

        if bullet is not None and not named.startswith("HEADING"):
            list_id = bullet.get("listId", "")
            if current_run and current_run["list_id"] == list_id:
                current_run["count"] += 1
            else:
                if current_run:
                    list_runs.append(current_run)
                current_run = {
                    "list_id": list_id,
                    "count": 1,
                    "first_text": text[:40],
                }
        else:
            if current_run:
                list_runs.append(current_run)
                current_run = None

        for run in para.get("elements", []):
            tr = run.get("textRun")
            if not tr:
                continue
            content = tr.get("content", "")
            link_url = tr.get("textStyle", {}).get("link", {}).get("url", "")
            for m in re.finditer(r"\bEARL-\d+\b", content):
                key = m.group(0)
                if not link_url or "atlassian.net/browse/" not in link_url:
                    issues.append({
                        "kind": "earl_key_not_linked",
                        "key": key,
                        "context": content.strip()[:60],
                    })

        # Em-dash and en-dash flag for body paragraphs only. These
        # characters in flowing prose are a common AI-writing tell —
        # reviewers want plain commas, parentheses, or split sentences.
        # Headings are exempt (legitimate title separators like
        # "Watson — Orchestrator" are fine there).
        if not named.startswith("HEADING") and not _is_em_dash_exempt(para, text):
            for run in para.get("elements", []):
                tr = run.get("textRun")
                if not tr:
                    continue
                content = tr.get("content", "")
                for m in re.finditer(r"[\u2013\u2014]", content):
                    ch = m.group(0)
                    kind_name = "em_dash" if ch == "\u2014" else "en_dash"
                    issues.append({
                        "kind": f"{kind_name}_in_body",
                        "char": ch,
                        "context": content.strip()[:80],
                    })

    if current_run:
        list_runs.append(current_run)

    lists_def = doc.get("lists") or {}
    for run in list_runs:
        lid = run["list_id"]
        ldef = lists_def.get(lid, {})
        nls = ldef.get("listProperties", {}).get("nestingLevels", [])
        if not nls:
            continue
        glyph_top = nls[0].get("glyphType") or nls[0].get("glyphSymbol", "")
        run["glyph"] = glyph_top

    checks_run = [
        "heading_with_bullet",
        "heading_level_skip",
        "earl_key_not_linked",
        "em_dash_in_body",
    ]

    # Check: nesting level drift across sections (standalone).
    # Walks body paragraphs, tracking the max bullet.nestingLevel per section
    # (sections are delimited by heading paragraphs). If three or more
    # consecutive sections exhibit strictly monotonically increasing max
    # nesting with a total range >= 2, flag it — a symptom of Docs'
    # transitive list merging where new sections inherit deeper nesting.
    section_max_nesting: list[tuple[str, int]] = []
    current_heading = ""
    current_max = -1
    for el in body:
        p = el.get("paragraph")
        if not p:
            continue
        ns = p.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")
        txt = "".join(
            r.get("textRun", {}).get("content", "")
            for r in p.get("elements", [])
        ).strip()
        if ns.startswith("HEADING"):
            section_max_nesting.append((current_heading, current_max))
            current_heading = txt
            current_max = -1
            continue
        b = p.get("bullet")
        if b is not None:
            lvl = int(b.get("nestingLevel", 0) or 0)
            if lvl > current_max:
                current_max = lvl
    section_max_nesting.append((current_heading, current_max))
    # Look for a monotonically increasing run of length >= 3 with range >= 2.
    nonempty = [(h, n) for h, n in section_max_nesting if n >= 0]
    run_start = 0
    for i in range(1, len(nonempty)):
        if nonempty[i][1] > nonempty[i - 1][1]:
            run_len = i - run_start + 1
            if run_len >= 3 and (nonempty[i][1] - nonempty[run_start][1]) >= 2:
                issues.append({
                    "kind": "nesting_level_drift_across_sections",
                    "sections": [(h, n) for h, n in nonempty[run_start:i + 1] if n > 0],
                    "fix": "Likely the transitive list merging bug (gotchas #10). Restructure source to break list adjacency, or use paragraphs instead of bullets.",
                })
                break
        else:
            run_start = i
    checks_run.append("nesting_level_drift")

    if source_path is not None and source_path.exists():
        src_text = source_path.read_text()
        if src_text.startswith("---\n"):
            end = src_text.find("\n---\n", 4)
            if end != -1:
                src_text = src_text[end + 5:]

        # Check 5: heading outline
        src_headings: list[tuple[int, str]] = []
        in_fence = False
        for raw_line in src_text.splitlines():
            ls = raw_line.lstrip()
            if ls.startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            m = re.match(r"^(#{1,6})\s+(.+)$", ls)
            if m:
                src_headings.append((len(m.group(1)), m.group(2).strip()))
        doc_heading_texts: list[str] = []
        for el in body:
            p = el.get("paragraph")
            if not p:
                continue
            ns = p.get("paragraphStyle", {}).get("namedStyleType", "")
            if not ns.startswith("HEADING"):
                continue
            txt = "".join(
                r.get("textRun", {}).get("content", "")
                for r in p.get("elements", [])
            ).strip()
            doc_heading_texts.append(txt)
        src_texts = [h[1] for h in src_headings]
        for m_text in src_texts:
            if m_text not in doc_heading_texts:
                issues.append({
                    "kind": "heading_missing_in_doc",
                    "text": m_text[:80],
                })
        checks_run.append("heading_outline_matches_source")

        # Check 6: list presets
        src_has_bullet = False
        src_has_ordered = False
        in_fence = False
        for line in src_text.splitlines():
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            stripped = line.lstrip()
            if re.match(r"^[-*+]\s+", stripped):
                src_has_bullet = True
            elif re.match(r"^\d+\.\s+", stripped):
                src_has_ordered = True
        for run in list_runs:
            glyph = run.get("glyph", "")
            is_numeric = glyph in ("DECIMAL", "ALPHA", "ROMAN", "ZERO_DECIMAL")
            if is_numeric and not src_has_ordered:
                issues.append({
                    "kind": "list_preset_mismatch",
                    "run_first_text": run.get("first_text", ""),
                    "rendered_glyph": glyph,
                })
            elif not is_numeric and not src_has_bullet:
                issues.append({
                    "kind": "list_preset_mismatch",
                    "run_first_text": run.get("first_text", ""),
                    "rendered_glyph": glyph,
                })
        checks_run.append("list_preset_matches_source")

        # Check 7: mermaid blocks rendered as inline images
        mermaid_count = 0
        in_fence = False
        fence_lang = ""
        for line in src_text.splitlines():
            ls = line.lstrip()
            if ls.startswith("```"):
                if not in_fence:
                    fence_lang = ls[3:].strip().lower()
                    in_fence = True
                    if fence_lang == "mermaid":
                        mermaid_count += 1
                else:
                    in_fence = False
                    fence_lang = ""
        inline_obj_count = 0
        for el in body:
            p = el.get("paragraph")
            if not p:
                continue
            for run in p.get("elements", []):
                if run.get("inlineObjectElement"):
                    inline_obj_count += 1

        # Count tables whose first cell begins with a known mermaid
        # diagram keyword. These are the degradation-path code blocks
        # that render when the host mmdc/sidecar renderer is
        # unavailable (e.g. cloud context). Heuristic — a normal code
        # block that happens to start with "graph" could match.
        _MERMAID_KEYWORDS = (
            "flowchart", "graph", "sequencediagram", "classdiagram",
            "statediagram", "erdiagram", "journey", "gantt", "pie",
            "gitgraph", "timeline", "mindmap", "quadrantchart",
            "requirementdiagram", "c4context",
        )
        mermaid_code_block_count = 0
        for el in body:
            table = el.get("table")
            if not table:
                continue
            rows = table.get("tableRows", [])
            if not rows:
                continue
            first_row = rows[0]
            cells = first_row.get("tableCells", [])
            if not cells:
                continue
            first_cell = cells[0]
            cell_text = ""
            for ce in first_cell.get("content", []):
                cp = ce.get("paragraph")
                if not cp:
                    continue
                for run in cp.get("elements", []):
                    cell_text += run.get("textRun", {}).get("content", "")
                if cell_text.strip():
                    break
            head = cell_text.strip().lower()
            if any(head.startswith(k) for k in _MERMAID_KEYWORDS):
                mermaid_code_block_count += 1

        if mermaid_count > (inline_obj_count + mermaid_code_block_count):
            issues.append({
                "kind": "mermaid_not_rendered",
                "source_mermaid_blocks": mermaid_count,
                "rendered_inline_objects": inline_obj_count,
                "rendered_code_blocks": mermaid_code_block_count,
            })
        elif mermaid_count > 0 and mermaid_code_block_count > 0:
            # Some (or all) mermaid blocks degraded to code blocks.
            # Advisory only — cloud context is the documented behavior
            # and strict push should NOT fail on this.
            issues.append({
                "kind": "degraded_mermaid_rendering",
                "severity": "info",
                "source_blocks": mermaid_count,
                "rendered_images": min(inline_obj_count, mermaid_count),
                "rendered_code_blocks": mermaid_code_block_count,
            })
        checks_run.append("mermaid_rendered_as_image")

        # Check 8: code blocks rendered as tables
        code_block_count = 0
        in_fence = False
        fence_lang = ""
        for line in src_text.splitlines():
            ls = line.lstrip()
            if ls.startswith("```"):
                if not in_fence:
                    fence_lang = ls[3:].strip().lower()
                    in_fence = True
                    if fence_lang and fence_lang != "mermaid":
                        code_block_count += 1
                    elif not fence_lang:
                        code_block_count += 1
                else:
                    in_fence = False
                    fence_lang = ""
        table_count = sum(1 for el in body if el.get("table"))
        if code_block_count > table_count:
            issues.append({
                "kind": "code_block_not_rendered",
                "source_code_blocks": code_block_count,
                "rendered_tables": table_count,
            })
        checks_run.append("code_blocks_rendered_as_tables")

        # Check 10: transitive list merging across headings.
        # Parse source into a sequence of (kind, text) entries, fence-aware.
        src_entries: list[tuple[str, str]] = []
        in_fence = False
        for raw_line in src_text.splitlines():
            ls = raw_line.lstrip()
            if ls.startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            if not ls.strip():
                continue
            if re.match(r"^#{1,6}\s+", ls):
                src_entries.append(("heading", ls))
            elif re.match(r"^[-*+]\s+", ls):
                src_entries.append(("bullet", ls))
            elif re.match(r"^\d+\.\s+", ls):
                src_entries.append(("ordered", ls))
            else:
                src_entries.append(("plain", ls))

        # Group consecutive list items into regions.
        src_regions: list[dict] = []  # {start_idx, count, first_text}
        i = 0
        while i < len(src_entries):
            kind, text = src_entries[i]
            if kind in ("bullet", "ordered"):
                start = i
                count = 0
                first_text = text
                while i < len(src_entries) and src_entries[i][0] in ("bullet", "ordered"):
                    count += 1
                    i += 1
                src_regions.append({
                    "start": start,
                    "end": i,
                    "count": count,
                    "first_text": first_text[:40],
                })
            else:
                i += 1

        # For each consecutive pair of regions, does the gap contain a heading?
        def gap_has_heading(a: dict, b: dict) -> bool:
            for j in range(a["end"], b["start"]):
                if src_entries[j][0] == "heading":
                    return True
            return False

        # Align source regions to rendered list_runs in order, then look for
        # any consecutive pair of regions whose aligned runs share a listId.
        # Heuristic: walk runs and regions in lockstep (one region per run when
        # available). The existing list_runs walker already splits runs at any
        # non-bullet paragraph (including headings), so two regions separated
        # in source by a heading should map to two distinct runs. If those two
        # runs nevertheless share the same listId, Docs has transitively
        # merged them — the landmine #10 bug.
        n = min(len(src_regions), len(list_runs))
        for idx in range(n - 1):
            a = src_regions[idx]
            b = src_regions[idx + 1]
            if not gap_has_heading(a, b):
                continue
            run_a = list_runs[idx]
            run_b = list_runs[idx + 1]
            lid_a = run_a.get("list_id", "")
            lid_b = run_b.get("list_id", "")
            if lid_a and lid_a == lid_b:
                issues.append({
                    "kind": "transitive_list_merge",
                    "shared_list_id": lid_a,
                    "first_region_text": a["first_text"],
                    "second_region_text": b["first_text"],
                    "fix": "Headings between list regions should break adjacency. See docs/gdocs-sync-gotchas.md landmine #10. Restructure content or use different bullet presets per section.",
                })
        checks_run.append("transitive_list_merge")

        # Check: task-list items rendered as BULLET_CHECKBOX.
        src_task_total = 0
        src_task_checked = 0
        in_fence = False
        for raw_line in src_text.splitlines():
            ls = raw_line.lstrip()
            if ls.startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            m = re.match(r"^[-*+]\s+\[([ xX])\]\s+", ls)
            if m:
                src_task_total += 1
                if m.group(1) in ("x", "X"):
                    src_task_checked += 1

        if src_task_total > 0:
            checkbox_paras: list[dict] = []
            for el in body:
                p = el.get("paragraph")
                if not p:
                    continue
                b = p.get("bullet")
                if b is None:
                    continue
                lid = b.get("listId", "")
                ldef = lists_def.get(lid, {})
                nls = ldef.get("listProperties", {}).get("nestingLevels", [])
                if not nls:
                    continue
                glyph = nls[0].get("glyphType") or nls[0].get("glyphSymbol", "")
                if glyph == "CHECKBOX":
                    checkbox_paras.append(p)
            rendered_checkbox = len(checkbox_paras)
            if rendered_checkbox < src_task_total:
                issues.append({
                    "kind": "task_list_not_rendered_as_checkbox",
                    "source_task_items": src_task_total,
                    "rendered_checkbox_items": rendered_checkbox,
                    "fix": "markdown.py task-list detection or BULLET_CHECKBOX emission in coalescing pass is misfiring",
                })
            if src_task_checked > 0:
                strike_count = 0
                for p in checkbox_paras:
                    for run in p.get("elements", []):
                        tr = run.get("textRun")
                        if not tr:
                            continue
                        if tr.get("textStyle", {}).get("strikethrough"):
                            strike_count += 1
                            break
                if strike_count < src_task_checked:
                    issues.append({
                        "kind": "task_list_checked_missing_strikethrough",
                        "source_checked_items": src_task_checked,
                        "rendered_strikethrough": strike_count,
                    })
        checks_run.append("task_list_checkbox_rendered")

    return issues, checks_run, len(list_runs)


def build_projected_doc(source_path: Path) -> dict:
    """Build a synthetic Google Docs API doc dict from a local markdown file.

    The dict matches the shape that `collect_doc_issues` expects: a body
    with content elements (paragraphs, tables) carrying paragraphStyle,
    elements with textRun content, and a top-level lists map. Headings get
    `namedStyleType: HEADING_N`. List items get a `bullet` with a synthetic
    listId and the matching glyph type. Mermaid blocks become inline-image
    paragraphs. Fenced code blocks become single-cell tables with
    monospace text. EARL-NNN mentions get an `atlassian.net/browse/...`
    link in the text run's textStyle.

    The projection is faithful enough that every check in
    `collect_doc_issues` produces the same verdict it would on a real
    pushed doc — without ever calling the Drive API.
    """
    import re

    text = source_path.read_text()
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            text = text[end + 5:]

    body_content: list[dict] = []
    lists_def: dict[str, dict] = {}

    # Track contiguous list state. Adjacent items with the same kind
    # share a listId; non-list paragraphs reset the run.
    current_list_id: Optional[str] = None
    current_list_kind: Optional[str] = None  # "bullet" | "ordered" | "checkbox"
    list_counter = 0

    def _new_list(kind: str) -> str:
        nonlocal list_counter
        list_counter += 1
        list_id = f"projected-list-{list_counter}"
        if kind == "ordered":
            glyphs = [{"glyphType": "DECIMAL"}, {"glyphType": "ALPHA"}, {"glyphType": "ROMAN"}]
        elif kind == "checkbox":
            glyphs = [{"glyphSymbol": "☐"}]
        else:
            glyphs = [{"glyphSymbol": "●"}, {"glyphSymbol": "○"}, {"glyphSymbol": "■"}]
        lists_def[list_id] = {
            "listProperties": {"nestingLevels": glyphs}
        }
        return list_id

    def _make_paragraph(
        text_content: str,
        named_style: str = "NORMAL_TEXT",
        bullet: Optional[dict] = None,
        link_keys: Optional[list[tuple[int, int, str]]] = None,
    ) -> dict:
        """Build a paragraph dict with text run elements.

        link_keys is a list of (start, end, key) tuples; each becomes a
        separate text run with a Jira link applied.
        """
        elements: list[dict] = []
        if not link_keys:
            elements.append({
                "startIndex": 0,
                "endIndex": len(text_content) + 1,
                "textRun": {"content": text_content + "\n", "textStyle": {}},
            })
        else:
            cursor = 0
            for start, end, key in link_keys:
                if start > cursor:
                    pre = text_content[cursor:start]
                    elements.append({
                        "startIndex": cursor,
                        "endIndex": cursor + len(pre),
                        "textRun": {"content": pre, "textStyle": {}},
                    })
                key_text = text_content[start:end]
                elements.append({
                    "startIndex": start,
                    "endIndex": end,
                    "textRun": {
                        "content": key_text,
                        "textStyle": {
                            "link": {"url": f"https://earlbear.atlassian.net/browse/{key}"},
                        },
                    },
                })
                cursor = end
            if cursor < len(text_content):
                tail = text_content[cursor:]
                elements.append({
                    "startIndex": cursor,
                    "endIndex": cursor + len(tail) + 1,
                    "textRun": {"content": tail + "\n", "textStyle": {}},
                })
        para: dict = {
            "paragraphStyle": {"namedStyleType": named_style},
            "elements": elements,
        }
        if bullet is not None:
            para["bullet"] = bullet
        return {"paragraph": para}

    def _find_jira_keys(s: str) -> list[tuple[int, int, str]]:
        """Find every EARL-NNN match in s and return (start, end, key) tuples."""
        return [(m.start(), m.end(), m.group(0)) for m in re.finditer(r"\bEARL-\d+\b", s)]

    lines = text.splitlines()
    i = 0
    in_code_fence = False
    fence_lang = ""
    fence_buf: list[str] = []
    fence_start_line = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()

        # Code fence start/end
        if stripped.startswith("```"):
            if not in_code_fence:
                in_code_fence = True
                fence_lang = stripped[3:].strip().lower()
                fence_buf = []
                fence_start_line = i
                # Reset list run — code blocks break list adjacency
                current_list_id = None
                current_list_kind = None
                i += 1
                continue
            else:
                # End of fence — emit either an inline image (mermaid) or
                # a single-cell table (other languages).
                in_code_fence = False
                code = "\n".join(fence_buf)
                if fence_lang == "mermaid":
                    # Project as a single-cell table containing the source
                    # so the validator's `degraded_mermaid_rendering`
                    # advisory fires correctly. We can't tell from the
                    # source alone whether a PNG cache will be hit, so
                    # we project as code-block (the safe degraded form);
                    # the source-aware mermaid_rendered_as_image check
                    # will then count it correctly.
                    body_content.append({
                        "table": {
                            "tableRows": [{
                                "tableCells": [{
                                    "content": [{
                                        "paragraph": {
                                            "elements": [{
                                                "startIndex": 0,
                                                "endIndex": len(code) + 1,
                                                "textRun": {
                                                    "content": code + "\n",
                                                    "textStyle": {
                                                        "weightedFontFamily": {
                                                            "fontFamily": "Courier New",
                                                            "weight": 400,
                                                        },
                                                    },
                                                },
                                            }],
                                        },
                                    }],
                                }],
                            }],
                        }
                    })
                else:
                    # Generic code block → single-cell monospace table
                    body_content.append({
                        "table": {
                            "tableRows": [{
                                "tableCells": [{
                                    "content": [{
                                        "paragraph": {
                                            "elements": [{
                                                "startIndex": 0,
                                                "endIndex": len(code) + 1,
                                                "textRun": {
                                                    "content": code + "\n",
                                                    "textStyle": {
                                                        "weightedFontFamily": {
                                                            "fontFamily": "Courier New",
                                                            "weight": 400,
                                                        },
                                                    },
                                                },
                                            }],
                                        },
                                    }],
                                }],
                            }],
                        }
                    })
                fence_buf = []
                fence_lang = ""
                i += 1
                continue
        if in_code_fence:
            fence_buf.append(line)
            i += 1
            continue

        # Heading
        m = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if m:
            level = len(m.group(1))
            text_content = m.group(2).strip()
            current_list_id = None
            current_list_kind = None
            body_content.append(_make_paragraph(
                text_content,
                named_style=f"HEADING_{level}",
                link_keys=_find_jira_keys(text_content) or None,
            ))
            i += 1
            continue

        # Pipe table — consume contiguous lines that look like table rows
        if stripped.startswith("|") and stripped.endswith("|"):
            table_lines = []
            while i < len(lines):
                row_stripped = lines[i].lstrip()
                if not (row_stripped.startswith("|") and row_stripped.endswith("|")):
                    break
                table_lines.append(row_stripped)
                i += 1
            # Skip separator row if present
            cells_per_row: list[list[str]] = []
            for row_line in table_lines:
                if re.match(r"^\|[\s:|-]+\|$", row_line):
                    continue
                cells = [c.strip() for c in row_line.strip("|").split("|")]
                cells_per_row.append(cells)
            if cells_per_row:
                # Build a table dict with text + EARL link runs in each cell
                table_rows = []
                for row in cells_per_row:
                    table_cells = []
                    for cell_text in row:
                        link_keys = _find_jira_keys(cell_text)
                        table_cells.append({
                            "content": [{
                                "paragraph": {
                                    "elements": (
                                        [{
                                            "startIndex": 0,
                                            "endIndex": len(cell_text) + 1,
                                            "textRun": {
                                                "content": cell_text + "\n",
                                                "textStyle": (
                                                    {"link": {"url": f"https://earlbear.atlassian.net/browse/{link_keys[0][2]}"}}
                                                    if link_keys
                                                    else {}
                                                ),
                                            },
                                        }]
                                    ),
                                },
                            }],
                        })
                    table_rows.append({"tableCells": table_cells})
                body_content.append({"table": {"tableRows": table_rows}})
            current_list_id = None
            current_list_kind = None
            continue

        # List item: bullet (-/*/+), ordered (1.), or task (- [ ])
        bullet_match = re.match(r"^([-*+])\s+(.+)$", stripped)
        ordered_match = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        if bullet_match or ordered_match:
            if bullet_match:
                content = bullet_match.group(2)
                # Task list?
                task_match = re.match(r"^\[([ xX])\]\s+(.+)$", content)
                if task_match:
                    kind = "checkbox"
                    content = task_match.group(2)
                else:
                    kind = "bullet"
            else:
                kind = "ordered"
                content = ordered_match.group(2)
            if kind != current_list_kind:
                current_list_id = _new_list(kind)
                current_list_kind = kind
            body_content.append(_make_paragraph(
                content,
                bullet={"listId": current_list_id, "nestingLevel": 0},
                link_keys=_find_jira_keys(content) or None,
            ))
            i += 1
            continue

        # Blank line
        if not stripped:
            current_list_id = None
            current_list_kind = None
            i += 1
            continue

        # Plain paragraph
        current_list_id = None
        current_list_kind = None
        body_content.append(_make_paragraph(
            stripped,
            link_keys=_find_jira_keys(stripped) or None,
        ))
        i += 1

    return {
        "body": {"content": body_content},
        "lists": lists_def,
    }


@app.command("lint")
def lint(
    path: Annotated[Path, typer.Argument(help="Local markdown file to validate.")],
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Run the rendering validator against a local .md without touching Drive.

    Parses the markdown file with the same converter `sync push` uses,
    builds a synthetic doc structure from the parse result, and runs the
    full `collect_doc_issues` validator against it. No Drive doc id
    required, no API call made.

    Catches everything the post-push validator catches:
    `heading_with_bullet`, `em_dash_in_body` (with quoted/italic
    exemptions), `earl_key_not_linked`, `code_blocks_rendered_as_tables`,
    `transitive_list_merge`, `nesting_level_drift`,
    `task_list_checkbox_rendered`, and the info-severity
    `degraded_mermaid_rendering` advisory when a mermaid block has no
    cached PNG.

    Exit 0 on clean (or info-only advisories), 1 on any error-severity
    issue. Use this from pre-commit hooks and during authoring as the
    fast local rendering check.

    Examples:
        ebdocs doc lint /content/gdocs/vision/foo.md
        ebdocs doc lint /content/gdocs/vision/foo.md --format table
    """
    if not path.exists():
        typer.echo(f"Error: file not found: {path}", err=True)
        raise typer.Exit(2)
    if not path.is_file():
        typer.echo(f"Error: not a file: {path}", err=True)
        raise typer.Exit(2)

    projected = build_projected_doc(path)
    issues, checks_run, list_run_count = collect_doc_issues(projected, source_path=path)

    # Separate error-severity from info-severity (advisories).
    info_kinds = {"degraded_mermaid_rendering"}
    error_issues = [i for i in issues if i.get("kind") not in info_kinds]
    info_issues = [i for i in issues if i.get("kind") in info_kinds]

    summary = {
        "path": str(path),
        "checks_run": checks_run,
        "list_runs": list_run_count,
        "issue_count": len(error_issues),
        "advisory_count": len(info_issues),
        "passed": len(error_issues) == 0,
        "issues": error_issues,
        "advisories": info_issues,
    }

    output_result(
        summary,
        format=format,
        json_fields=json_fields,
    )

    if error_issues:
        raise typer.Exit(1)


@app.command("validate")
def validate(
    doc_id: Annotated[str, typer.Argument(help="Document ID to validate.")],
    source: Annotated[Optional[Path], typer.Option("--source", help="Path to source .md file. Enables source-vs-rendered cross-checks (heading text, list presets, mermaid images, code blocks).")] = None,
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Validate that a Google Doc renders cleanly after sync push.

    Walks the document body and checks invariants that catch the rendering
    bugs we have hit (and re-hit) in the markdown -> Docs converter. Without
    --source, runs the standalone checks (1-4). With --source, also runs the
    source-vs-rendered cross-checks (5-8).

    Standalone checks (no source needed):

    1. Heading paragraphs MUST NOT have a bullet attached. Catches heading-
       swallowed-by-list (landmine #10 in gdocs-sync-gotchas.md).

    2. List glyph consistency within each contiguous run.

    3. EARL-NNN mentions in body text should be hyperlinks.

    4. Heading levels should be monotonic (h1 -> h2 -> h3, no skipping).

    Source-vs-rendered checks (require --source):

    5. Heading outline matches source. Every `#`/`##`/`###` in the source
       should appear as a HEADING_N paragraph in the rendered doc, in the
       same order. Catches headings that were absorbed into adjacent lists.

    6. List presets match source list type. Every source `- ` bullet region
       should render as a disc/circle/square glyph list. Every source `1. `
       region should render as decimal/alpha/roman. Catches preset cascade
       bugs (landmine #9b).

    7. Mermaid blocks render as inline images. Every ```mermaid ... ```
       block should produce one inlineObject in the doc. Missing = fallback
       text = render failure (usually means the PNG cache was empty).

    8. Fenced code blocks render as tables. Every ```lang ... ``` block
       should produce one `table` element in the doc body with monospace
       text inside. Catches code blocks that silently lost their shading.

    Exit code is 0 if all checks pass, 1 if any check fails.

    Examples:
        ebdocs doc validate DOC_ID
        ebdocs doc validate DOC_ID --format table
        ebdocs doc validate DOC_ID --source /content/gdocs/vision/foo.md
    """
    client = get_client()
    doc = client.get_document(doc_id)

    issues, checks_run, list_run_count = collect_doc_issues(doc, source_path=source)

    summary = {
        "doc_id": doc_id,
        "url": f"https://docs.google.com/document/d/{doc_id}/edit",
        "checks_run": checks_run,
        "list_runs": list_run_count,
        "issue_count": len(issues),
        "passed": len(issues) == 0,
        "issues": issues,
    }

    output_result(
        summary,
        format=format,
        json_fields=json_fields,
    )

    if issues:
        raise typer.Exit(1)
