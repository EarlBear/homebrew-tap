"""Workflow commands — list, view, create, update, delete, transitions."""

from __future__ import annotations

import uuid
from typing import Annotated, Optional

import typer

from ebjira.client import get_client
from ebjira.models.common import Status, Workflow, WorkflowDetail, WorkflowTransition
from ebjira.output import Format, output_error, output_result

workflow_app = typer.Typer(
    name="workflow",
    help="Manage workflows.",
    no_args_is_help=True,
)


@workflow_app.command("list")
def list_workflows(
    limit: Annotated[Optional[int], typer.Option("--limit", "-l", help="Maximum number of workflows to return.")] = None,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """List all workflows."""
    client = get_client()
    raw = client.get_paginated(
        client.platform("/workflow/search"),
        results_key="values",
        max_results=limit,
    )
    workflows = [Workflow.from_jira(w).model_dump() for w in raw]
    output_result(
        workflows,
        format=format,
        json_fields=json_fields,
        columns=["id", "name", "description", "is_default"],
    )


@workflow_app.command("view")
def view_workflow(
    name: Annotated[str, typer.Argument(help="Workflow name to view.")],
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """View workflow details including its statuses."""
    client = get_client()
    data = client.get(
        client.platform("/workflow/search"),
        params={"workflowName": name, "expand": "statuses"},
    )
    values = data.get("values", []) if isinstance(data, dict) else []
    if not values:
        output_error(
            error="WORKFLOW_NOT_FOUND",
            message=f"Workflow '{name}' not found.",
        )
    wf_data = values[0]
    wf = Workflow.from_jira(wf_data).model_dump()
    raw_statuses = wf_data.get("statuses", [])
    wf["statuses"] = [Status.from_jira(s).model_dump() for s in raw_statuses]
    output_result(wf, format=format, json_fields=json_fields)


def _parse_statuses(statuses_str: str) -> list[dict]:
    """Parse comma-separated 'name:category' pairs into status dicts with UUIDs.

    Returns list of dicts with keys: name, category, statusReference (UUID).
    """
    valid_categories = ("TODO", "IN_PROGRESS", "DONE")
    result = []
    for pair in statuses_str.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if ":" not in pair:
            output_error(
                error="INVALID_STATUS_FORMAT",
                message=f"Status '{pair}' must be in 'name:category' format.",
            )
        name, category = pair.rsplit(":", 1)
        name = name.strip()
        category = category.strip()
        if category not in valid_categories:
            output_error(
                error="INVALID_CATEGORY",
                message=f"Category must be one of: {', '.join(valid_categories)}. Got '{category}'.",
            )
        result.append({
            "name": name,
            "category": category,
            "statusReference": str(uuid.uuid4()),
        })
    return result


def _parse_transitions(transitions_str: str, status_map: dict[str, str]) -> list[dict]:
    """Parse comma-separated 'from>to' pairs into transition dicts.

    status_map maps status name -> statusReference UUID.
    """
    result = []
    for pair in transitions_str.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if ">" not in pair:
            output_error(
                error="INVALID_TRANSITION_FORMAT",
                message=f"Transition '{pair}' must be in 'from>to' format.",
            )
        from_name, to_name = pair.split(">", 1)
        from_name = from_name.strip()
        to_name = to_name.strip()
        if from_name not in status_map:
            output_error(
                error="UNKNOWN_STATUS",
                message=f"Transition references unknown status '{from_name}'.",
            )
        if to_name not in status_map:
            output_error(
                error="UNKNOWN_STATUS",
                message=f"Transition references unknown status '{to_name}'.",
            )
        result.append({
            "id": str(uuid.uuid4()),
            "name": f"{from_name} to {to_name}",
            "from": [{"statusReference": status_map[from_name]}],
            "to": {"statusReference": status_map[to_name]},
            "type": "DIRECTED",
        })
    return result


@workflow_app.command("create")
def create_workflow(
    name: Annotated[str, typer.Option("--name", "-n", help="Workflow name.")],
    project: Annotated[str, typer.Option("--project", "-p", help="Project key to scope the workflow to.")],
    statuses: Annotated[str, typer.Option("--statuses", "-s", help="Comma-separated statuses as 'name:category' pairs (e.g. 'Open:TODO,Done:DONE').")],
    transitions: Annotated[Optional[str], typer.Option("--transitions", "-t", help="Comma-separated transitions as 'from>to' pairs (e.g. 'Open>Done').")] = None,
    description: Annotated[Optional[str], typer.Option("--description", "-d", help="Workflow description.")] = None,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """Create a workflow with statuses and transitions."""
    client = get_client()

    # Resolve project key to ID
    project_data = client.get(client.platform(f"/project/{project}"))
    project_id = project_data.get("id", "")

    # Parse statuses
    parsed_statuses = _parse_statuses(statuses)

    # Build status reference map: name -> statusReference UUID
    status_map: dict[str, str] = {}
    for s in parsed_statuses:
        status_map[s["name"]] = s["statusReference"]

    # Parse transitions
    parsed_transitions: list[dict] = []
    if transitions:
        parsed_transitions = _parse_transitions(transitions, status_map)

    # Build API payload
    workflow_entry: dict = {
        "name": name,
        "statuses": [
            {"statusReference": s["statusReference"], "properties": {}}
            for s in parsed_statuses
        ],
        "transitions": {t["id"]: t for t in parsed_transitions},
    }
    if description:
        workflow_entry["description"] = description

    body = {
        "statuses": [
            {
                "name": s["name"],
                "statusCategory": s["category"],
                "statusReference": s["statusReference"],
            }
            for s in parsed_statuses
        ],
        "workflows": [workflow_entry],
        "scope": {
            "type": "PROJECT",
            "project": {"id": project_id},
        },
    }

    raw = client.post(client.platform("/workflows/create"), json=body)
    output_result(raw, format=format, json_fields=json_fields)


@workflow_app.command("update")
def update_workflow(
    name: Annotated[str, typer.Argument(help="Workflow name to update.")],
    add_status: Annotated[Optional[str], typer.Option("--add-status", help="Status to add as 'name:category'.")] = None,
    remove_status: Annotated[Optional[str], typer.Option("--remove-status", help="Status name to remove.")] = None,
    add_transition: Annotated[Optional[str], typer.Option("--add-transition", help="Transition to add as 'from>to'.")] = None,
    remove_transition: Annotated[Optional[str], typer.Option("--remove-transition", help="Transition name to remove (format: 'from to to').")] = None,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """Update a workflow — add/remove statuses and transitions."""
    if not any([add_status, remove_status, add_transition, remove_transition]):
        output_error(
            error="NO_CHANGES",
            message="Provide at least one of --add-status, --remove-status, --add-transition, --remove-transition.",
        )

    client = get_client()

    # Fetch current workflow
    data = client.get(
        client.platform("/workflow/search"),
        params={"workflowName": name, "expand": "statuses,transitions"},
    )
    values = data.get("values", []) if isinstance(data, dict) else []
    if not values:
        output_error(
            error="WORKFLOW_NOT_FOUND",
            message=f"Workflow '{name}' not found.",
        )
    wf_data = values[0]

    # Extract version for optimistic locking
    version = wf_data.get("version", {})

    # Build current statuses list
    current_statuses = list(wf_data.get("statuses", []))
    current_transitions = list(wf_data.get("transitions", []))

    # Build a status name -> reference map from current workflow
    status_ref_map: dict[str, str] = {}
    for s in current_statuses:
        s_name = s.get("name", "")
        s_ref = s.get("statusReference", s.get("id", ""))
        if s_name:
            status_ref_map[s_name] = s_ref

    # New statuses to create at the API level
    new_statuses_payload: list[dict] = []

    # Add status
    if add_status:
        parsed = _parse_statuses(add_status)
        for s in parsed:
            status_ref_map[s["name"]] = s["statusReference"]
            current_statuses.append({
                "statusReference": s["statusReference"],
                "properties": {},
            })
            new_statuses_payload.append({
                "name": s["name"],
                "statusCategory": s["category"],
                "statusReference": s["statusReference"],
            })

    # Remove status
    if remove_status:
        remove_names = [n.strip() for n in remove_status.split(",") if n.strip()]
        remove_refs = {status_ref_map[n] for n in remove_names if n in status_ref_map}
        current_statuses = [
            s for s in current_statuses
            if s.get("statusReference", s.get("id", "")) not in remove_refs
        ]
        for n in remove_names:
            status_ref_map.pop(n, None)

    # Add transition
    if add_transition:
        new_transitions = _parse_transitions(add_transition, status_ref_map)
        current_transitions.extend(new_transitions)

    # Remove transition
    if remove_transition:
        remove_names_set = {n.strip() for n in remove_transition.split(",") if n.strip()}
        current_transitions = [
            t for t in current_transitions
            if t.get("name", "") not in remove_names_set
        ]

    # Build update payload
    workflow_entry: dict = {
        "name": name,
        "version": version,
        "statuses": [
            {"statusReference": s.get("statusReference", s.get("id", "")), "properties": s.get("properties", {})}
            for s in current_statuses
        ],
        "transitions": current_transitions,
    }

    body: dict = {
        "workflows": [workflow_entry],
        "statuses": new_statuses_payload,
    }

    raw = client.put(client.platform("/workflows/update"), json=body)
    output_result(raw, format=format, json_fields=json_fields)


@workflow_app.command("delete")
def delete_workflow(
    entity_id: Annotated[str, typer.Argument(help="Workflow entity ID to delete.")],
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """Delete a workflow by entity ID."""
    client = get_client()
    client.delete(client.platform(f"/workflow/{entity_id}"))
    output_result(
        {"deleted": True, "id": entity_id},
        format=format,
        json_fields=json_fields,
    )


@workflow_app.command("transitions")
def list_transitions(
    name: Annotated[str, typer.Option("--name", "-n", help="Workflow name.")],
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """List transitions for a workflow."""
    client = get_client()
    data = client.get(
        client.platform("/workflow/search"),
        params={"workflowName": name, "expand": "transitions,statuses"},
    )
    values = data.get("values", []) if isinstance(data, dict) else []
    if not values:
        output_error(
            error="WORKFLOW_NOT_FOUND",
            message=f"Workflow '{name}' not found.",
        )
    wf_data = values[0]

    # Build status ID -> name map for resolving references
    status_id_map: dict[str, str] = {}
    for s in wf_data.get("statuses", []):
        sid = s.get("id", s.get("statusReference", ""))
        sname = s.get("name", sid)
        status_id_map[sid] = sname

    raw_transitions = wf_data.get("transitions", [])
    result = []
    for t in raw_transitions:
        # Resolve from statuses
        from_refs = t.get("from", [])
        from_names = []
        for ref in from_refs:
            if isinstance(ref, dict):
                ref_id = ref.get("statusReference", ref.get("id", ""))
                from_names.append(status_id_map.get(ref_id, ref.get("name", ref_id)))
            else:
                from_names.append(status_id_map.get(str(ref), str(ref)))

        # Resolve to status
        to_ref = t.get("to", {})
        if isinstance(to_ref, dict):
            to_id = to_ref.get("statusReference", to_ref.get("id", ""))
            to_name = status_id_map.get(to_id, to_ref.get("name", to_id))
        else:
            to_name = status_id_map.get(str(to_ref), str(to_ref)) if to_ref else ""

        result.append({
            "name": t.get("name", ""),
            "type": t.get("type", ""),
            "from_status": ", ".join(from_names) if from_names else "(any)",
            "to_status": to_name,
        })

    output_result(
        result,
        format=format,
        json_fields=json_fields,
        columns=["name", "type", "from_status", "to_status"],
    )
