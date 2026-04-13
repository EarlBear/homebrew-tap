"""Sharing and permissions commands."""

from __future__ import annotations

from typing import Optional

import typer

from ebdocs.client import DocsError, get_client
from ebdocs.models.doc import Permission
from ebdocs.output import Format, output_error, output_result

app = typer.Typer(name="share", help="Manage document sharing and permissions")


@app.command("add")
def share_add(
    doc_id: str = typer.Argument(..., help="Document ID to share"),
    email: str = typer.Option(..., "--email", help="Email address to share with"),
    role: str = typer.Option(
        "reader",
        "--role",
        help="Permission role: reader, writer, or commenter",
    ),
    message: Optional[str] = typer.Option(
        None, "--message", help="Optional notification message sent to the user"
    ),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format"),
) -> None:
    """Share a document with a user by email."""
    valid_roles = ("reader", "writer", "commenter")
    if role not in valid_roles:
        output_error(
            error="INVALID_ROLE",
            message=f"Role must be one of: {', '.join(valid_roles)}. Got: {role}",
        )

    client = get_client()
    try:
        send_notification = message is not None
        raw = client.share(
            file_id=doc_id,
            email=email,
            role=role,
            send_notification=send_notification,
        )
        perm = Permission.from_api(raw)
        output_result(perm.model_dump(), format=format)
    except DocsError as e:
        output_error(error=f"SHARE_FAILED", message=e.message, status=1)


@app.command("remove")
def share_remove(
    doc_id: str = typer.Argument(..., help="Document ID"),
    email: str = typer.Option(..., "--email", help="Email address to remove"),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format"),
) -> None:
    """Remove sharing permissions for a user by email."""
    client = get_client()
    try:
        permissions = client.list_permissions(doc_id)
        target = None
        for perm in permissions:
            if perm.get("emailAddress", "").lower() == email.lower():
                target = perm
                break

        if not target:
            output_error(
                error="PERMISSION_NOT_FOUND",
                message=f"No permission found for email: {email}",
            )

        client.remove_permission(doc_id, target["id"])
        result = {"status": "removed", "email": email, "doc_id": doc_id}
        output_result(result, format=format)
    except DocsError as e:
        output_error(error="REMOVE_FAILED", message=e.message, status=1)


@app.command("list")
def share_list(
    doc_id: str = typer.Argument(..., help="Document ID"),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format"),
) -> None:
    """List all permissions on a document."""
    client = get_client()
    try:
        raw_perms = client.list_permissions(doc_id)
        permissions = [Permission.from_api(p) for p in raw_perms]
        data = [p.model_dump() for p in permissions]
        output_result(
            data,
            format=format,
            columns=["id", "email", "role", "type"],
        )
    except DocsError as e:
        output_error(error="LIST_PERMISSIONS_FAILED", message=e.message, status=1)
