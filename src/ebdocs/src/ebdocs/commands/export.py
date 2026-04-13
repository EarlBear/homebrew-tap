"""Document export commands — download docs as PDF, DOCX, HTML, or plain text."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer

from ebdocs.client import DocsError, get_client
from ebdocs.output import Format, output_error, output_result

app = typer.Typer(name="export", help="Export documents to various formats")

# MIME type mapping for export formats
EXPORT_MIME_TYPES: dict[str, str] = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "html": "text/html",
    "txt": "text/plain",
}

# Formats that default to file output (binary formats)
BINARY_FORMATS = {"pdf", "docx"}


def _docs_url(doc_id: str) -> str:
    """Construct the Google Docs edit URL for a document."""
    return f"https://docs.google.com/document/d/{doc_id}/edit"


@app.command("download")
def export_download(
    doc_id: str = typer.Argument(..., help="Document ID to export"),
    format: str = typer.Option(
        ..., "--format", help="Export format: pdf, docx, html, or txt"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path (defaults to stdout for txt/html, file for pdf/docx)"
    ),
    out_format: Format = typer.Option(
        Format.json, "--out-format", help="CLI output format for status messages"
    ),
) -> None:
    """Export a Google Doc to PDF, DOCX, HTML, or plain text.

    Binary formats (pdf, docx) default to file output.
    Text formats (html, txt) default to stdout.
    Use --output to override the destination.
    """
    fmt = format.lower()
    if fmt not in EXPORT_MIME_TYPES:
        output_error(
            error="INVALID_FORMAT",
            message=f"Format must be one of: {', '.join(EXPORT_MIME_TYPES.keys())}. Got: {fmt}",
        )

    mime_type = EXPORT_MIME_TYPES[fmt]
    client = get_client()

    try:
        data = client.export_file(file_id=doc_id, mime_type=mime_type)
    except DocsError as e:
        output_error(error="EXPORT_FAILED", message=e.message, status=1)

    # Determine output destination
    if output:
        # Explicit output path
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(data)
        output_result(
            {
                "status": "exported",
                "doc_id": doc_id,
                "format": fmt,
                "path": str(out_path.resolve()),
                "size_bytes": len(data),
            },
            format=out_format,
        )
    elif fmt in BINARY_FORMATS:
        # Binary format with no --output: write to default filename
        filename = f"{doc_id}.{fmt}"
        out_path = Path(filename)
        out_path.write_bytes(data)
        output_result(
            {
                "status": "exported",
                "doc_id": doc_id,
                "format": fmt,
                "path": str(out_path.resolve()),
                "size_bytes": len(data),
            },
            format=out_format,
        )
    else:
        # Text format to stdout
        sys.stdout.buffer.write(data)


@app.command("url")
def export_url(
    doc_id: str = typer.Argument(..., help="Document ID"),
) -> None:
    """Print the Google Docs URL for a document.

    Outputs just the URL — useful for piping to other commands.
    """
    print(_docs_url(doc_id))
