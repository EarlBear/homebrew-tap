"""Issue type scheme commands — list, create, update, assign to project."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from ebjira.client import get_client
from ebjira.models.common import IssueTypeScheme
from ebjira.output import Format, output_error, output_result

issuetypescheme_app = typer.Typer(
    name="issuetypescheme",
    help="Manage issue type schemes.",
    no_args_is_help=True,
)


@issuetypescheme_app.command("list")
def list_issue_type_schemes(
    limit: Annotated[Optional[int], typer.Option("--limit", "-l", help="Maximum number of schemes to return.")] = None,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """List all issue type schemes.

    Examples:
        ebjira issuetypescheme list
        ebjira issuetypescheme list --limit 10
        ebjira issuetypescheme list --format table
    """
    client = get_client()
    raw = client.get_paginated(
        client.platform("/issuetypescheme"),
        results_key="values",
        max_results=limit,
    )
    schemes = [IssueTypeScheme.from_jira(s).model_dump() for s in raw]
    output_result(
        schemes,
        format=format,
        json_fields=json_fields,
        columns=["id", "name", "default_issue_type_id", "description"],
    )


@issuetypescheme_app.command("create")
def create_issue_type_scheme(
    name: Annotated[str, typer.Option("--name", "-n", help="Scheme name.")],
    description: Annotated[Optional[str], typer.Option("--description", "-d", help="Scheme description.")] = None,
    issue_type_ids: Annotated[Optional[str], typer.Option("--issue-type-ids", help="Comma-separated issue type IDs.")] = None,
    default_issue_type_id: Annotated[Optional[str], typer.Option("--default-issue-type-id", help="Default issue type ID.")] = None,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """Create a new issue type scheme.

    Examples:
        ebjira issuetypescheme create --name "My Scheme" --issue-type-ids 10001,10002
        ebjira issuetypescheme create --name "My Scheme" --issue-type-ids 10001,10002 --default-issue-type-id 10001
    """
    client = get_client()
    body: dict = {"name": name}
    if description is not None:
        body["description"] = description
    if issue_type_ids is not None:
        body["issueTypeIds"] = [i.strip() for i in issue_type_ids.split(",") if i.strip()]
    if default_issue_type_id is not None:
        body["defaultIssueTypeId"] = default_issue_type_id
    raw = client.post(client.platform("/issuetypescheme"), json=body)
    output_result(raw, format=format, json_fields=json_fields)


@issuetypescheme_app.command("update")
def update_issue_type_scheme(
    id: Annotated[str, typer.Argument(help="Issue type scheme ID to update.")],
    name: Annotated[Optional[str], typer.Option("--name", "-n", help="New scheme name.")] = None,
    description: Annotated[Optional[str], typer.Option("--description", "-d", help="New description.")] = None,
    issue_type_ids: Annotated[Optional[str], typer.Option("--issue-type-ids", help="Comma-separated issue type IDs.")] = None,
    default_issue_type_id: Annotated[Optional[str], typer.Option("--default-issue-type-id", help="Default issue type ID.")] = None,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """Update an existing issue type scheme.

    Examples:
        ebjira issuetypescheme update 10001 --name "Renamed Scheme"
        ebjira issuetypescheme update 10001 --issue-type-ids 10001,10002,10003
    """
    body: dict = {}
    if name is not None:
        body["name"] = name
    if description is not None:
        body["description"] = description
    if default_issue_type_id is not None:
        body["defaultIssueTypeId"] = default_issue_type_id
    if not body and issue_type_ids is None:
        output_error(
            error="NO_CHANGES",
            message="Provide at least one of --name, --description, --issue-type-ids, or --default-issue-type-id to update.",
        )
    client = get_client()
    # Update scheme details if any provided
    if body:
        client.put(client.platform(f"/issuetypescheme/{id}"), json=body)
    # Update issue type list if provided (separate endpoint)
    if issue_type_ids is not None:
        ids_list = [i.strip() for i in issue_type_ids.split(",") if i.strip()]
        client.put(
            client.platform(f"/issuetypescheme/{id}/issuetype"),
            json={"issueTypeIds": ids_list},
        )
    output_result(
        {"updated": True, "id": id, **body},
        format=format,
        json_fields=json_fields,
    )


@issuetypescheme_app.command("assign")
def assign_issue_type_scheme(
    project: Annotated[str, typer.Option("--project", "-p", help="Project key (e.g. EARL).")],
    scheme_id: Annotated[str, typer.Option("--scheme-id", "-s", help="Issue type scheme ID to assign.")],
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """Assign an issue type scheme to a project.

    Resolves the project key to its ID, then associates the scheme.

    Examples:
        ebjira issuetypescheme assign --project EARL --scheme-id 10001
    """
    client = get_client()
    # Resolve project key to ID
    project_data = client.get(client.platform(f"/project/{project}"))
    project_id = project_data["id"]
    body = {"projectId": project_id, "issueTypeSchemeId": scheme_id}
    client.put(client.platform("/issuetypescheme/project"), json=body)
    output_result(
        {"assigned": True, "project": project, "project_id": project_id, "scheme_id": scheme_id},
        format=format,
        json_fields=json_fields,
    )
