"""Field management commands — list, inspect options, create, update, delete fields."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from ebjira.client import get_client
from ebjira.output import Format, output_result

field_app = typer.Typer(
    name="field",
    help="Manage fields and field options.",
    no_args_is_help=True,
)


@field_app.command("list")
def list_fields(
    custom_only: Annotated[bool, typer.Option("--custom-only", help="Show only custom fields.")] = False,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """List all fields (system and custom)."""
    client = get_client()
    raw = client.get(client.platform("/field"))
    fields = []
    for f in raw:
        if custom_only and not f.get("custom", False):
            continue
        schema = f.get("schema") or {}
        fields.append({
            "id": f.get("id", ""),
            "name": f.get("name", ""),
            "custom": f.get("custom", False),
            "schema_type": schema.get("type", ""),
        })
    output_result(
        fields,
        format=format,
        json_fields=json_fields,
        columns=["id", "name", "custom", "schema_type"],
    )


@field_app.command("options")
def field_options(
    project_key: Annotated[str, typer.Argument(help="Project key (e.g. PROJ).")],
    issue_type_id: Annotated[str, typer.Argument(help="Issue type ID.")],
    field_id: Annotated[str, typer.Argument(help="Field ID to get allowed values for.")],
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """Get allowed values for a field in a given project and issue type."""
    client = get_client()
    raw = client.get(
        client.platform(f"/issue/createmeta/{project_key}/issuetypes/{issue_type_id}")
    )
    fields_dict = raw.get("fields", {}) if isinstance(raw, dict) else {}
    field_meta = fields_dict.get(field_id)
    if field_meta is None:
        from ebjira.output import output_error
        output_error(
            error="FIELD_NOT_FOUND",
            message=f"Field '{field_id}' not found for project {project_key} issue type {issue_type_id}.",
        )
    allowed = field_meta.get("allowedValues", [])
    # Normalize output: use id + name if present, fall back to id + value
    options = []
    for v in allowed:
        entry: dict = {"id": v.get("id", "")}
        if "name" in v:
            entry["name"] = v["name"]
        elif "value" in v:
            entry["name"] = v["value"]
        else:
            entry["name"] = ""
        options.append(entry)
    output_result(
        options,
        format=format,
        json_fields=json_fields,
        columns=["id", "name"],
    )


@field_app.command("create")
def create_field(
    name: Annotated[str, typer.Option("--name", "-n", help="Field name.")],
    type: Annotated[str, typer.Option("--type", "-t", help="Field type (e.g. com.atlassian.jira.plugin.system.customfieldtypes:textfield).")],
    description: Annotated[Optional[str], typer.Option("--description", "-d", help="Field description.")] = None,
    search_key: Annotated[Optional[str], typer.Option("--search-key", help="Searcher key for the field.")] = None,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """Create a custom field."""
    client = get_client()
    body: dict = {"name": name, "type": type}
    if description is not None:
        body["description"] = description
    if search_key is not None:
        body["searcherKey"] = search_key
    raw = client.post(client.platform("/field"), json=body)
    output_result(raw, format=format, json_fields=json_fields)


@field_app.command("update")
def update_field(
    field_id: Annotated[str, typer.Argument(help="Field ID to update (e.g. customfield_10001).")],
    name: Annotated[Optional[str], typer.Option("--name", "-n", help="New field name.")] = None,
    description: Annotated[Optional[str], typer.Option("--description", "-d", help="New field description.")] = None,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """Update a custom field's name or description."""
    body: dict = {}
    if name is not None:
        body["name"] = name
    if description is not None:
        body["description"] = description
    if not body:
        from ebjira.output import output_error
        output_error(
            error="NO_CHANGES",
            message="Provide at least one of --name or --description to update.",
        )
    client = get_client()
    raw = client.put(client.platform(f"/field/{field_id}"), json=body)
    output_result(raw, format=format, json_fields=json_fields)


@field_app.command("delete")
def delete_field(
    field_id: Annotated[str, typer.Argument(help="Field ID to delete (e.g. customfield_10001).")],
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """Delete a custom field."""
    client = get_client()
    client.delete(client.platform(f"/field/{field_id}"))
    output_result(
        {"deleted": True, "id": field_id},
        format=format,
        json_fields=json_fields,
    )
