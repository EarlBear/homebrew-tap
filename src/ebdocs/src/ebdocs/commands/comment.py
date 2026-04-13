"""Comment management commands."""

from __future__ import annotations

from typing import Optional

import typer

from ebdocs.client import DocsError, get_client
from ebdocs.models.doc import Comment
from ebdocs.output import Format, output_error, output_result

app = typer.Typer(name="comment", help="Add, list, and resolve comments")


@app.command("add")
def comment_add(
    doc_id: str = typer.Argument(..., help="Document ID"),
    text: str = typer.Option(..., "--text", help="Comment text"),
    quoted_text: Optional[str] = typer.Option(
        None, "--quoted-text", help="Anchor comment to specific text in the document"
    ),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format"),
) -> None:
    """Add a comment to a document."""
    client = get_client()
    try:
        # Build the comment body with optional anchor
        body: dict = {"content": text}
        if quoted_text:
            body["quotedFileContent"] = {
                "mimeType": "text/html",
                "value": quoted_text,
            }

        # Use the Drive API directly for anchored comments since the client
        # method doesn't support quotedFileContent
        if quoted_text:
            raw = (
                client._drive.comments()
                .create(
                    fileId=doc_id,
                    body=body,
                    fields="id, content, author, createdTime, resolved, quotedFileContent",
                )
                .execute()
            )
        else:
            raw = client.add_comment(doc_id, text)

        comment = Comment.from_api(raw)
        result = comment.model_dump()
        # Add direct link to this comment
        result["url"] = f"https://docs.google.com/document/d/{doc_id}/edit?disco={comment.id}"
        output_result(result, format=format)
    except DocsError as e:
        output_error(error="COMMENT_ADD_FAILED", message=e.message, status=1)
    except Exception as e:
        output_error(error="COMMENT_ADD_FAILED", message=str(e), status=1)


@app.command("list")
def comment_list(
    doc_id: str = typer.Argument(..., help="Document ID"),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format"),
    include_resolved: bool = typer.Option(
        False, "--include-resolved", help="Include resolved comments"
    ),
) -> None:
    """List comments on a document."""
    client = get_client()
    try:
        raw_comments = client.list_comments(doc_id, include_resolved=include_resolved)
        comments = [Comment.from_api(c) for c in raw_comments]
        data = []
        for c in comments:
            d = c.model_dump()
            d["url"] = f"https://docs.google.com/document/d/{doc_id}/edit?disco={c.id}"
            data.append(d)
        output_result(
            data,
            format=format,
            columns=["id", "content", "author", "url", "resolved"],
        )
    except DocsError as e:
        output_error(error="COMMENT_LIST_FAILED", message=e.message, status=1)


@app.command("resolve")
def comment_resolve(
    doc_id: str = typer.Argument(..., help="Document ID"),
    comment_id: str = typer.Argument(..., help="Comment ID to resolve"),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format"),
) -> None:
    """Mark a comment as resolved."""
    client = get_client()
    try:
        raw = client.resolve_comment(doc_id, comment_id)
        result = {
            "status": "resolved",
            "comment_id": raw.get("id", comment_id),
            "doc_id": doc_id,
        }
        output_result(result, format=format)
    except DocsError as e:
        output_error(error="COMMENT_RESOLVE_FAILED", message=e.message, status=1)
