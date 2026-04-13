"""Issue link commands — list link types, create and delete issue links."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from ebjira.client import get_client
from ebjira.output import Format, output_result

issuelink_app = typer.Typer(
    name="issuelink",
    help="Manage issue links (create, delete, list types).",
    no_args_is_help=True,
)


@issuelink_app.command("types")
def list_types(
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """List all issue link types (blocks, relates to, etc.).

    Example: ebjira issuelink types
    """
    client = get_client()
    data = client.get(client.platform("/issueLinkType"))
    link_types = []
    for lt in data.get("issueLinkTypes", []):
        link_types.append({
            "id": lt.get("id", ""),
            "name": lt.get("name", ""),
            "inward": lt.get("inward", ""),
            "outward": lt.get("outward", ""),
        })
    output_result(
        link_types,
        format=format,
        json_fields=json_fields,
        columns=["id", "name", "inward", "outward"],
    )


@issuelink_app.command("create")
def create_link(
    from_issue: Annotated[str, typer.Option("--from-issue", help="Source issue key (e.g. EARL-1).")],
    to_issue: Annotated[str, typer.Option("--to-issue", help="Target issue key (e.g. EARL-2).")],
    type: Annotated[str, typer.Option("--type", "-t", help='Link type name (e.g. "blocks", "relates to").')],
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """Create an issue link between two issues.

    Example: ebjira issuelink create --from-issue EARL-1 --to-issue EARL-2 --type "blocks"
    """
    client = get_client()
    payload = {
        "type": {"name": type},
        "inwardIssue": {"key": from_issue},
        "outwardIssue": {"key": to_issue},
    }
    client.post(client.platform("/issueLink"), json=payload)
    output_result(
        {"linked": True, "from": from_issue, "to": to_issue, "type": type},
        format=format,
        json_fields=json_fields,
    )


@issuelink_app.command("delete")
def delete_link(
    link_id: Annotated[str, typer.Argument(help="Issue link ID to delete.")],
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """Delete an issue link by ID.

    Example: ebjira issuelink delete 10001
    """
    client = get_client()
    client.delete(client.platform(f"/issueLink/{link_id}"))
    output_result(
        {"deleted": True, "id": link_id},
        format=format,
        json_fields=json_fields,
    )
