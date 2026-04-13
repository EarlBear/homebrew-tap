"""Attachment commands — list, get, add, sync, and delete file attachments.

Convention: when `CONTENT_DIR` is set (either via env or mounted at /content
in the Docker wrapper), attachments are stored locally under
`$CONTENT_DIR/jira/attachments/<ISSUE-KEY>/<filename>` with filenames matching
Jira exactly. `attachment sync` is the primary UX for hydrating this layout;
`add` and `get` also honor it when possible.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Optional

import typer

from ebjira.client import get_client
from ebjira.models.common import Attachment
from ebjira.output import Format, output_result

attachment_app = typer.Typer(no_args_is_help=True)


def _attachments_dir(issue_key: str) -> Optional[Path]:
    """Return $CONTENT_DIR/jira/attachments/<KEY> if CONTENT_DIR is set, else None."""
    content_dir = os.environ.get("CONTENT_DIR")
    if not content_dir:
        return None
    return Path(content_dir) / "jira" / "attachments" / issue_key


def _download_attachment(client, attachment_id: str) -> tuple[str, bytes]:
    """Fetch attachment metadata + bytes by ID. Returns (filename, bytes)."""
    metadata = client.get(client.platform(f"/attachment/{attachment_id}"))
    content_url = metadata.get("content", "")
    filename = metadata.get("filename", f"attachment-{attachment_id}")
    content = client.get(content_url)
    if isinstance(content, dict):
        content = json.dumps(content).encode()
    elif isinstance(content, str):
        content = content.encode()
    return filename, content


@attachment_app.command(name="list")
def list_(
    issue_key: str = typer.Argument(help="Issue key to list attachments for (e.g. PROJ-42)."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: Optional[str] = typer.Option(None, "--json", "-j", help="Comma-separated fields to include in JSON output."),
) -> None:
    """List attachments on an issue."""
    client = get_client()
    data = client.get(client.platform(f"/issue/{issue_key}?fields=attachment"))
    raw = (data.get("fields") or {}).get("attachment") or []
    result = [Attachment.from_jira(a).model_dump() for a in raw]
    output_result(result, format=format, json_fields=json_fields)


@attachment_app.command()
def get(
    id: str = typer.Argument(help="Attachment ID."),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="File path to save to. If omitted and --issue-key is set, writes under $CONTENT_DIR/jira/attachments/<KEY>/. If both omitted, outputs base64 JSON."),
    issue_key: Optional[str] = typer.Option(None, "--issue-key", "-k", help="Issue key to resolve the conventional output directory ($CONTENT_DIR/jira/attachments/<KEY>/)."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: Optional[str] = typer.Option(None, "--json", "-j", help="Comma-separated fields to include in JSON output."),
) -> None:
    """Download an attachment by ID."""
    client = get_client()
    filename, content_bytes = _download_attachment(client, id)

    dest: Optional[Path] = None
    if output:
        dest = Path(output)
    elif issue_key:
        conv_dir = _attachments_dir(issue_key)
        if conv_dir is None:
            typer.echo("Error: --issue-key was given but CONTENT_DIR is not set", err=True)
            raise typer.Exit(1)
        dest = conv_dir / filename

    if dest is not None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content_bytes)
        result = {
            "filename": filename,
            "size": len(content_bytes),
            "saved_to": str(dest),
        }
    else:
        result = {
            "filename": filename,
            "size": len(content_bytes),
            "content_base64": base64.b64encode(content_bytes).decode(),
        }

    output_result(result, format=format, json_fields=json_fields)


@attachment_app.command()
def sync(
    issue_key: str = typer.Argument(help="Issue key to sync all attachments for (e.g. PROJ-42)."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: Optional[str] = typer.Option(None, "--json", "-j", help="Comma-separated fields to include in JSON output."),
) -> None:
    """Download all attachments for an issue to $CONTENT_DIR/jira/attachments/<KEY>/.

    Filenames match Jira exactly. Requires CONTENT_DIR to be set.
    """
    conv_dir = _attachments_dir(issue_key)
    if conv_dir is None:
        typer.echo("Error: CONTENT_DIR is not set — cannot resolve sync directory", err=True)
        raise typer.Exit(1)

    client = get_client()
    data = client.get(client.platform(f"/issue/{issue_key}?fields=attachment"))
    raw = (data.get("fields") or {}).get("attachment") or []

    conv_dir.mkdir(parents=True, exist_ok=True)
    synced = []
    for att in raw:
        att_id = att.get("id", "")
        filename, content_bytes = _download_attachment(client, att_id)
        dest = conv_dir / filename
        dest.write_bytes(content_bytes)
        synced.append({
            "id": att_id,
            "filename": filename,
            "size": len(content_bytes),
            "saved_to": str(dest),
        })

    result = {
        "issue_key": issue_key,
        "directory": str(conv_dir),
        "count": len(synced),
        "attachments": synced,
    }
    output_result(result, format=format, json_fields=json_fields)


@attachment_app.command()
def add(
    issue_key: str = typer.Argument(help="Issue key to attach to (e.g. PROJ-42)."),
    file: str = typer.Argument(help="File path, or base64 string when --base64 is set."),
    base64_flag: bool = typer.Option(False, "--base64", help="Treat file argument as a base64 string instead of a file path."),
    filename: Optional[str] = typer.Option(None, "--filename", help="Filename for the attachment (required with --base64)."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: Optional[str] = typer.Option(None, "--json", "-j", help="Comma-separated fields to include in JSON output."),
) -> None:
    """Add an attachment to an issue.

    For Docker environments, use --base64 to pass file content as a base64 string
    along with --filename to set the attachment name.
    """
    client = get_client()

    if base64_flag:
        if not filename:
            typer.echo("Error: --filename is required when using --base64", err=True)
            raise typer.Exit(1)
        raw = client.upload_attachment_base64(issue_key, filename, file)
    else:
        path = Path(file)
        # If the path doesn't exist and looks like a bare filename (no separator),
        # try resolving it under $CONTENT_DIR/jira/attachments/<ISSUE-KEY>/ — the
        # conventional location for locally-staged attachments.
        if not path.exists() and "/" not in file and "\\" not in file:
            conv_dir = _attachments_dir(issue_key)
            if conv_dir is not None:
                candidate = conv_dir / file
                if candidate.exists():
                    path = candidate
        if not path.exists():
            typer.echo(f"Error: file not found: {file}", err=True)
            raise typer.Exit(1)
        content = path.read_bytes()
        name = filename or path.name
        raw = client.upload_attachment(issue_key, name, content)

    # API returns a list of attachments
    if isinstance(raw, list) and raw:
        attachments = [Attachment.from_jira(a).model_dump() for a in raw]
        result = attachments[0] if len(attachments) == 1 else attachments
    else:
        result = raw

    output_result(result, format=format, json_fields=json_fields)


@attachment_app.command()
def delete(
    id: str = typer.Argument(help="Attachment ID to delete."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: Optional[str] = typer.Option(None, "--json", "-j", help="Comma-separated fields to include in JSON output."),
) -> None:
    """Delete an attachment by ID."""
    client = get_client()
    client.delete(client.platform(f"/attachment/{id}"))
    result = {"deleted": True, "id": id}
    output_result(result, format=format, json_fields=json_fields)
