"""Workflow scheme commands — list, view, create, update, assign to project."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from ebjira.client import get_client
from ebjira.models.common import WorkflowScheme
from ebjira.output import Format, output_error, output_result

workflowscheme_app = typer.Typer(
    name="workflowscheme",
    help="Manage workflow schemes.",
    no_args_is_help=True,
)


@workflowscheme_app.command("list")
def list_workflow_schemes(
    limit: Annotated[Optional[int], typer.Option("--limit", "-l", help="Maximum number of schemes to return.")] = None,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """List all workflow schemes.

    Examples:
        ebjira workflowscheme list
        ebjira workflowscheme list --limit 10
        ebjira workflowscheme list --format table
    """
    client = get_client()
    raw = client.get_paginated(
        client.platform("/workflowscheme"),
        results_key="values",
        max_results=limit,
    )
    schemes = [WorkflowScheme.from_jira(s).model_dump() for s in raw]
    output_result(
        schemes,
        format=format,
        json_fields=json_fields,
        columns=["id", "name", "default_workflow", "description"],
    )


@workflowscheme_app.command("view")
def view_workflow_scheme(
    id: Annotated[str, typer.Argument(help="Workflow scheme ID.")],
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """View details of a single workflow scheme.

    Examples:
        ebjira workflowscheme view 10001
        ebjira workflowscheme view 10001 --format table
    """
    client = get_client()
    raw = client.get(client.platform(f"/workflowscheme/{id}"))
    scheme = WorkflowScheme.from_jira(raw).model_dump()
    output_result(scheme, format=format, json_fields=json_fields)


@workflowscheme_app.command("create")
def create_workflow_scheme(
    name: Annotated[str, typer.Option("--name", "-n", help="Scheme name.")],
    description: Annotated[Optional[str], typer.Option("--description", "-d", help="Scheme description.")] = None,
    default_workflow: Annotated[Optional[str], typer.Option("--default-workflow", help="Default workflow name.")] = None,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """Create a new workflow scheme.

    Examples:
        ebjira workflowscheme create --name "My Scheme"
        ebjira workflowscheme create --name "My Scheme" --default-workflow "jira"
    """
    client = get_client()
    body: dict = {"name": name}
    if description is not None:
        body["description"] = description
    if default_workflow is not None:
        body["defaultWorkflow"] = default_workflow
    raw = client.post(client.platform("/workflowscheme"), json=body)
    scheme = WorkflowScheme.from_jira(raw).model_dump()
    output_result(scheme, format=format, json_fields=json_fields)


@workflowscheme_app.command("update")
def update_workflow_scheme(
    id: Annotated[str, typer.Argument(help="Workflow scheme ID to update.")],
    name: Annotated[Optional[str], typer.Option("--name", "-n", help="New scheme name.")] = None,
    description: Annotated[Optional[str], typer.Option("--description", "-d", help="New scheme description.")] = None,
    default_workflow: Annotated[Optional[str], typer.Option("--default-workflow", help="New default workflow name.")] = None,
    mapping: Annotated[Optional[list[str]], typer.Option("--mapping", "-m", help="Issue type to workflow mapping as issueTypeId:workflowName. Repeatable.")] = None,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """Update an existing workflow scheme.

    Examples:
        ebjira workflowscheme update 10001 --name "Renamed Scheme"
        ebjira workflowscheme update 10001 --default-workflow "jira"
        ebjira workflowscheme update 10001 --mapping 10001:MyWorkflow --mapping 10002:OtherWorkflow
    """
    body: dict = {"id": int(id)}
    if name is not None:
        body["name"] = name
    if description is not None:
        body["description"] = description
    if default_workflow is not None:
        body["defaultWorkflow"] = default_workflow
    if mapping:
        items: dict = {}
        for m in mapping:
            parts = m.split(":", 1)
            if len(parts) != 2:
                output_error(
                    error="INVALID_MAPPING",
                    message=f"Mapping must be issueTypeId:workflowName. Got '{m}'.",
                )
            items[parts[0]] = parts[1]
        body["issueTypeMappings"] = items
    has_changes = any(k != "id" for k in body)
    if not has_changes:
        output_error(
            error="NO_CHANGES",
            message="Provide at least one of --name, --description, --default-workflow, or --mapping to update.",
        )
    client = get_client()
    raw = client.put(client.platform(f"/workflowscheme/{id}"), json=body)
    scheme = WorkflowScheme.from_jira(raw).model_dump()
    output_result(scheme, format=format, json_fields=json_fields)


@workflowscheme_app.command("assign")
def assign_workflow_scheme(
    project: Annotated[str, typer.Option("--project", "-p", help="Project key (e.g. EARL).")],
    scheme_id: Annotated[str, typer.Option("--scheme-id", "-s", help="Workflow scheme ID to assign.")],
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """Assign a workflow scheme to a project.

    Resolves the project key to its ID, then associates the scheme.

    Examples:
        ebjira workflowscheme assign --project EARL --scheme-id 10001
    """
    client = get_client()
    # Resolve project key to ID
    project_data = client.get(client.platform(f"/project/{project}"))
    project_id = project_data["id"]
    body = {"projectId": project_id, "workflowSchemeId": scheme_id}
    client.put(client.platform("/workflowscheme/project"), json=body)
    output_result(
        {"assigned": True, "project": project, "project_id": project_id, "scheme_id": scheme_id},
        format=format,
        json_fields=json_fields,
    )
