"""Issue type management commands — list, view, create, update, delete."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from ebjira.client import get_client
from ebjira.models.common import IssueType
from ebjira.output import Format, output_result

issuetype_app = typer.Typer(
    name="issuetype",
    help="Manage issue types (create, update, delete).",
    no_args_is_help=True,
)


@issuetype_app.command("list")
def list_issue_types(
    project: Annotated[Optional[str], typer.Option("--project", "-p", help="Filter by project key (e.g. PROJ).")] = None,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """List all issue types, optionally filtered by project.

    Examples:
        ebjira issuetype list
        ebjira issuetype list --project PROJ
        ebjira issuetype list --format table
        ebjira issuetype list --json id,name
    """
    client = get_client()
    if project:
        # Resolve project key to ID first
        project_data = client.get(client.platform(f"/project/{project}"))
        project_id = project_data["id"]
        raw = client.get(
            client.platform("/issuetype/project"),
            params={"projectId": project_id},
        )
    else:
        raw = client.get(client.platform("/issuetype"))
    issue_types = [IssueType.from_jira(it).model_dump() for it in raw]
    output_result(
        issue_types,
        format=format,
        json_fields=json_fields,
        columns=["id", "name", "subtask", "hierarchy_level", "description"],
    )


@issuetype_app.command("view")
def view_issue_type(
    id: Annotated[str, typer.Argument(help="Issue type ID.")],
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """View details of a single issue type.

    Examples:
        ebjira issuetype view 10001
        ebjira issuetype view 10001 --format table
    """
    client = get_client()
    raw = client.get(client.platform(f"/issuetype/{id}"))
    issue_type = IssueType.from_jira(raw).model_dump()
    output_result(issue_type, format=format, json_fields=json_fields)


@issuetype_app.command("create")
def create_issue_type(
    name: Annotated[str, typer.Option("--name", "-n", help="Issue type name.")],
    description: Annotated[Optional[str], typer.Option("--description", "-d", help="Issue type description.")] = None,
    type: Annotated[str, typer.Option("--type", "-t", help="Type: 'standard' or 'subtask'.")] = "standard",
    hierarchy_level: Annotated[Optional[int], typer.Option("--hierarchy-level", help="Hierarchy level (integer).")] = None,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """Create a new issue type.

    Examples:
        ebjira issuetype create --name "Bug Report"
        ebjira issuetype create --name "Sub-bug" --type subtask --description "A child bug"
        ebjira issuetype create --name "Epic" --hierarchy-level 1
    """
    client = get_client()
    body: dict = {"name": name, "type": type}
    if description is not None:
        body["description"] = description
    if hierarchy_level is not None:
        body["hierarchyLevel"] = hierarchy_level
    raw = client.post(client.platform("/issuetype"), json=body)
    issue_type = IssueType.from_jira(raw).model_dump()
    output_result(issue_type, format=format, json_fields=json_fields)


@issuetype_app.command("update")
def update_issue_type(
    id: Annotated[str, typer.Argument(help="Issue type ID to update.")],
    name: Annotated[Optional[str], typer.Option("--name", "-n", help="New name.")] = None,
    description: Annotated[Optional[str], typer.Option("--description", "-d", help="New description.")] = None,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """Update an existing issue type.

    Examples:
        ebjira issuetype update 10001 --name "Renamed Type"
        ebjira issuetype update 10001 --description "Updated description"
        ebjira issuetype update 10001 --name "New Name" --description "New desc"
    """
    client = get_client()
    body: dict = {}
    if name is not None:
        body["name"] = name
    if description is not None:
        body["description"] = description
    raw = client.put(client.platform(f"/issuetype/{id}"), json=body)
    issue_type = IssueType.from_jira(raw).model_dump()
    output_result(issue_type, format=format, json_fields=json_fields)


@issuetype_app.command("delete")
def delete_issue_type(
    id: Annotated[str, typer.Argument(help="Issue type ID to delete.")],
    alternative_id: Annotated[Optional[str], typer.Option("--alternative-id", help="ID of alternative issue type to migrate existing issues to.")] = None,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """Delete an issue type, optionally migrating issues to an alternative.

    Examples:
        ebjira issuetype delete 10001
        ebjira issuetype delete 10001 --alternative-id 10002
    """
    client = get_client()
    params = {}
    if alternative_id is not None:
        params["alternativeIssueTypeId"] = alternative_id
    client.delete(client.platform(f"/issuetype/{id}"), params=params or None)
    result = {"deleted": True, "id": id}
    output_result(result, format=format, json_fields=json_fields)


@issuetype_app.command("alternatives")
def list_alternatives(
    id: Annotated[str, typer.Argument(help="Issue type ID to find alternatives for.")],
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """List alternative issue types for migration before deleting.

    Examples:
        ebjira issuetype alternatives 10001
        ebjira issuetype alternatives 10001 --format table
    """
    client = get_client()
    raw = client.get(client.platform(f"/issuetype/{id}/alternatives"))
    issue_types = [IssueType.from_jira(it).model_dump() for it in raw]
    output_result(
        issue_types,
        format=format,
        json_fields=json_fields,
        columns=["id", "name", "subtask", "description"],
    )
