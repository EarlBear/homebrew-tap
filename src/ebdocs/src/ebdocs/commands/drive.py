"""Google Drive operations — upload files to shared folder."""

from __future__ import annotations

import base64
import os
import sys
from pathlib import Path
from typing import Optional

import typer
from typing_extensions import Annotated

from ebdocs.output import output_error, output_result

drive_app = typer.Typer(no_args_is_help=True)


@drive_app.command("upload")
def drive_upload(
    file_path: Annotated[str, typer.Argument(help="Path to the file to upload")],
    filename: Annotated[Optional[str], typer.Option(help="Override filename (defaults to file basename)")] = None,
    mime_type: Annotated[str, typer.Option(help="MIME type")] = "application/octet-stream",
    folder_id: Annotated[Optional[str], typer.Option(help="Drive folder ID (defaults to configured folder)")] = None,
    format: Annotated[str, typer.Option(help="Output format")] = "json",
) -> None:
    """Upload a file to Google Drive.

    Uploads the file to the shared Drive folder (or specified folder).
    In cloud environments, automatically falls back to the MCP Worker
    REST API if the proxy blocks direct Google API access.

    Examples:
        ebdocs drive upload /tmp/workspace.zip
        ebdocs drive upload report.pdf --mime-type application/pdf
        ebdocs drive upload /tmp/logs.jsonl --filename "agent-run-2026-04-06.jsonl"
    """
    path = Path(file_path)
    if not path.exists():
        output_error(error="FILE_NOT_FOUND", message=f"File not found: {file_path}", status=1)
        return

    upload_filename = filename or path.name

    # Auto-detect common MIME types
    if mime_type == "application/octet-stream":
        ext_map = {
            ".zip": "application/zip",
            ".pdf": "application/pdf",
            ".json": "application/json",
            ".jsonl": "application/x-ndjson",
            ".csv": "text/csv",
            ".html": "text/html",
            ".md": "text/markdown",
            ".txt": "text/plain",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
        }
        mime_type = ext_map.get(path.suffix.lower(), mime_type)

    # Read and base64-encode the file
    content_b64 = base64.b64encode(path.read_bytes()).decode("ascii")

    # Try MCP Worker REST API (works in cloud where Google APIs are blocked)
    mcp_client_id = os.environ.get("MCP_OAUTH_CLIENT_ID")
    mcp_client_secret = os.environ.get("MCP_OAUTH_CLIENT_SECRET")
    mcp_api_url = os.environ.get("GDOCS_MCP_API_URL", "https://gdocs-mcp.omar-aed.workers.dev/api")

    if mcp_client_id and mcp_client_secret:
        try:
            import httpx

            resp = httpx.post(
                f"{mcp_api_url}/drive/upload",
                auth=httpx.BasicAuth(mcp_client_id, mcp_client_secret),
                json={
                    "filename": upload_filename,
                    "content_base64": content_b64,
                    "mime_type": mime_type,
                    "folder_id": folder_id,
                },
                timeout=60.0,
            )
            if resp.status_code == 200:
                output_result(resp.json(), format=format)
                return
            else:
                # MCP failed — fall through to direct API
                print(f"[ebdocs] MCP upload failed ({resp.status_code}), trying direct API", file=sys.stderr)
        except Exception as e:
            print(f"[ebdocs] MCP upload error: {e}, trying direct API", file=sys.stderr)

    # Fallback: direct Google Drive API via the client
    try:
        from ebdocs.client import get_client

        client = get_client()
        content_bytes = path.read_bytes()
        # The client doesn't have an upload method, so use the MCP request fallback
        result = client._mcp_request("drive/upload", json_body={
            "filename": upload_filename,
            "content_base64": content_b64,
            "mime_type": mime_type,
            "folder_id": folder_id,
        })
        output_result(result, format=format)
    except Exception as e:
        output_error(error="UPLOAD_FAILED", message=str(e), status=1)
