"""Filter management commands — list, view, create, update, and delete saved filters."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from ebjira.client import get_client
from ebjira.models.common import Filter
from ebjira.output import Format, output_result

filter_app = typer.Typer(
    name="filter",
    help="Manage saved filters.",
    no_args_is_help=True,
)


@filter_app.command("list")
def list_filters(
    name: Annotated[Optional[str], typer.Option("--name", "-n", help="Filter by name (substring match).")] = None,
    owner: Annotated[Optional[str], typer.Option("--owner", help="Filter by owner account ID.")] = None,
    favorites: Annotated[bool, typer.Option("--favorites", help="Show only favorite filters.")] = False,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Maximum number of filters to return.")] = 50,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """List or search saved filters.

    By default, searches all filters. Use --favorites to show only favorites.
    """
    client = get_client()

    if favorites:
        raw = client.get(client.platform("/filter/favourite"))
        # Favourites endpoint returns a flat list
        filters = [Filter.from_jira(f).model_dump() for f in raw]
        if limit:
            filters = filters[:limit]
    else:
        params: dict = {}
        if name:
            params["filterName"] = name
        if owner:
            params["accountId"] = owner
        raw = client.get_paginated(
            client.platform("/filter/search"),
            results_key="values",
            params=params,
            max_results=limit,
        )
        filters = [Filter.from_jira(f).model_dump() for f in raw]

    output_result(
        filters,
        format=format,
        json_fields=json_fields,
        columns=["id", "name", "owner", "jql"],
    )


@filter_app.command("view")
def view_filter(
    id: Annotated[str, typer.Argument(help="Filter ID.")],
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """View details of a saved filter."""
    client = get_client()
    raw = client.get(client.platform(f"/filter/{id}"))
    result = Filter.from_jira(raw).model_dump()
    output_result(result, format=format, json_fields=json_fields)


@filter_app.command("create")
def create_filter(
    name: Annotated[str, typer.Option("--name", "-n", help="Filter name.")],
    jql: Annotated[str, typer.Option("--jql", help="JQL query string.")],
    description: Annotated[Optional[str], typer.Option("--description", "-d", help="Filter description.")] = None,
    favorite: Annotated[bool, typer.Option("--favorite", help="Mark as favorite.")] = False,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """Create a new saved filter."""
    client = get_client()
    body: dict = {
        "name": name,
        "jql": jql,
        "favourite": favorite,
    }
    if description is not None:
        body["description"] = description
    raw = client.post(client.platform("/filter"), json=body)
    result = Filter.from_jira(raw).model_dump()
    output_result(result, format=format, json_fields=json_fields)


@filter_app.command("update")
def update_filter(
    id: Annotated[str, typer.Argument(help="Filter ID to update.")],
    name: Annotated[Optional[str], typer.Option("--name", "-n", help="New filter name.")] = None,
    jql: Annotated[Optional[str], typer.Option("--jql", help="New JQL query string.")] = None,
    description: Annotated[Optional[str], typer.Option("--description", "-d", help="New filter description.")] = None,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """Update an existing saved filter."""
    client = get_client()
    body: dict = {}
    if name is not None:
        body["name"] = name
    if jql is not None:
        body["jql"] = jql
    if description is not None:
        body["description"] = description
    raw = client.put(client.platform(f"/filter/{id}"), json=body)
    result = Filter.from_jira(raw).model_dump()
    output_result(result, format=format, json_fields=json_fields)


@filter_app.command("delete")
def delete_filter(
    id: Annotated[str, typer.Argument(help="Filter ID to delete.")],
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """Delete a saved filter."""
    client = get_client()
    client.delete(client.platform(f"/filter/{id}"))
    output_result(
        {"deleted": True, "id": id},
        format=format,
        json_fields=json_fields,
    )
