"""Component commands — list, create, update, and delete project components."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from ebjira.client import get_client
from ebjira.output import Format, output_result

component_app = typer.Typer(
    name="component",
    help="Manage project components.",
    no_args_is_help=True,
)


@component_app.command("list")
def list_components(
    project: Annotated[str, typer.Option("--project", "-p", help="Project key (e.g. EARL).")],
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """List all components in a project.

    Example: ebjira component list --project EARL
    """
    client = get_client()
    raw = client.get(client.platform(f"/project/{project}/components"))
    components = []
    for c in raw:
        components.append({
            "id": c.get("id", ""),
            "name": c.get("name", ""),
            "description": c.get("description", ""),
            "lead": c.get("lead", {}).get("displayName", "") if c.get("lead") else "",
            "assigneeType": c.get("assigneeType", ""),
        })
    output_result(
        components,
        format=format,
        json_fields=json_fields,
        columns=["id", "name", "description", "lead"],
    )


@component_app.command("create")
def create_component(
    project: Annotated[str, typer.Option("--project", "-p", help="Project key (e.g. EARL).")],
    name: Annotated[str, typer.Option("--name", "-n", help="Component name.")],
    description: Annotated[Optional[str], typer.Option("--description", "-d", help="Component description.")] = None,
    lead_account_id: Annotated[Optional[str], typer.Option("--lead", help="Lead user account ID.")] = None,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """Create a component in a project.

    Example: ebjira component create --project EARL --name "discovery-toolkit" --description "Finding stores"
    """
    client = get_client()
    payload: dict = {
        "project": project,
        "name": name,
    }
    if description is not None:
        payload["description"] = description
    if lead_account_id is not None:
        payload["leadAccountId"] = lead_account_id

    result = client.post(client.platform("/component"), json=payload)
    output_result(result, format=format, json_fields=json_fields)


@component_app.command("update")
def update_component(
    id: Annotated[str, typer.Argument(help="Component ID to update.")],
    name: Annotated[Optional[str], typer.Option("--name", "-n", help="New component name.")] = None,
    description: Annotated[Optional[str], typer.Option("--description", "-d", help="New component description.")] = None,
    lead_account_id: Annotated[Optional[str], typer.Option("--lead", help="New lead user account ID.")] = None,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """Update a component by ID.

    Example: ebjira component update 10001 --name "new-name" --description "Updated"
    """
    payload: dict = {}
    if name is not None:
        payload["name"] = name
    if description is not None:
        payload["description"] = description
    if lead_account_id is not None:
        payload["leadAccountId"] = lead_account_id

    if not payload:
        from ebjira.output import output_error
        output_error(
            error="NO_CHANGES",
            message="Provide at least one of --name, --description, or --lead to update.",
        )

    client = get_client()
    result = client.put(client.platform(f"/component/{id}"), json=payload)
    output_result(result, format=format, json_fields=json_fields)


@component_app.command("delete")
def delete_component(
    id: Annotated[str, typer.Argument(help="Component ID to delete.")],
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """Delete a component by ID.

    Example: ebjira component delete 10001
    """
    client = get_client()
    client.delete(client.platform(f"/component/{id}"))
    output_result(
        {"deleted": True, "id": id},
        format=format,
        json_fields=json_fields,
    )
