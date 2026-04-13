"""Status commands — list, create, update, and delete statuses."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from ebjira.client import get_client
from ebjira.models.common import Status
from ebjira.output import Format, output_result

status_app = typer.Typer(
    name="status",
    help="Manage statuses.",
    no_args_is_help=True,
)


@status_app.command("list")
def list_statuses(
    limit: Annotated[Optional[int], typer.Option("--limit", "-l", help="Maximum number of statuses to return.")] = None,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """List all statuses."""
    client = get_client()
    raw = client.get_paginated(
        client.platform("/statuses/search"),
        results_key="values",
        max_results=limit,
    )
    statuses = [Status.from_jira(s).model_dump() for s in raw]
    output_result(
        statuses,
        format=format,
        json_fields=json_fields,
        columns=["id", "name", "category", "description"],
    )


@status_app.command("create")
def create_status(
    name: Annotated[str, typer.Option("--name", "-n", help="Status name.")],
    category: Annotated[str, typer.Option("--category", "-c", help="Status category: TODO, IN_PROGRESS, or DONE.")],
    description: Annotated[Optional[str], typer.Option("--description", "-d", help="Status description.")] = None,
    project: Annotated[Optional[str], typer.Option("--project", "-p", help="Project ID for project scope (omit for global scope).")] = None,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """Create a status (bulk endpoint, creates one)."""
    valid_categories = ("TODO", "IN_PROGRESS", "DONE")
    if category not in valid_categories:
        from ebjira.output import output_error
        output_error(
            error="INVALID_CATEGORY",
            message=f"Category must be one of: {', '.join(valid_categories)}. Got '{category}'.",
        )
    client = get_client()
    status_entry: dict = {"name": name, "statusCategory": category}
    if description is not None:
        status_entry["description"] = description
    scope: dict
    if project:
        scope = {"type": "PROJECT", "project": {"id": project}}
    else:
        scope = {"type": "GLOBAL"}
    body = {"statuses": [status_entry], "scope": scope}
    raw = client.post(client.platform("/statuses"), json=body)
    output_result(raw, format=format, json_fields=json_fields)


@status_app.command("update")
def update_status(
    id: Annotated[str, typer.Argument(help="Status ID to update.")],
    name: Annotated[Optional[str], typer.Option("--name", "-n", help="New status name.")] = None,
    description: Annotated[Optional[str], typer.Option("--description", "-d", help="New status description.")] = None,
    category: Annotated[Optional[str], typer.Option("--category", "-c", help="New status category: TODO, IN_PROGRESS, or DONE.")] = None,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """Update a status by ID."""
    if category is not None:
        valid_categories = ("TODO", "IN_PROGRESS", "DONE")
        if category not in valid_categories:
            from ebjira.output import output_error
            output_error(
                error="INVALID_CATEGORY",
                message=f"Category must be one of: {', '.join(valid_categories)}. Got '{category}'.",
            )
    status_entry: dict = {"id": id}
    if name is not None:
        status_entry["name"] = name
    if description is not None:
        status_entry["description"] = description
    if category is not None:
        status_entry["statusCategory"] = category
    if len(status_entry) == 1:
        from ebjira.output import output_error
        output_error(
            error="NO_CHANGES",
            message="Provide at least one of --name, --description, or --category to update.",
        )
    client = get_client()
    body = {"statuses": [status_entry]}
    raw = client.put(client.platform("/statuses"), json=body)
    output_result(raw, format=format, json_fields=json_fields)


@status_app.command("delete")
def delete_statuses(
    ids: Annotated[str, typer.Argument(help="Comma-separated status IDs to delete.")],
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """Delete one or more statuses by ID."""
    client = get_client()
    id_list = [i.strip() for i in ids.split(",") if i.strip()]
    params = [("ids", i) for i in id_list]
    # httpx supports list-of-tuples for repeated query params
    client._client.delete(
        client.platform("/statuses"),
        params=params,
    )
    output_result(
        {"deleted": True, "ids": id_list},
        format=format,
        json_fields=json_fields,
    )
