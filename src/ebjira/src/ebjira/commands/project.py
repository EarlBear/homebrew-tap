"""Project management commands — list, view, create, and inspect projects."""

from __future__ import annotations

import re
from typing import Annotated, Optional

import typer

from ebjira.client import get_client
from ebjira.models.project import Component, ProjectDetail, ProjectSummary, Version
from ebjira.output import Format, output_result

project_app = typer.Typer(
    name="project",
    help="Manage projects and their configuration.",
    no_args_is_help=True,
)


@project_app.command("list")
def list_projects(
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Maximum number of projects to return.")] = 50,
) -> None:
    """List all projects visible to the authenticated user."""
    client = get_client()
    raw = client.get_paginated(
        client.platform("/project/search"),
        results_key="values",
        max_results=limit,
    )
    projects = [ProjectSummary.from_jira(p).model_dump() for p in raw]
    output_result(
        projects,
        format=format,
        json_fields=json_fields,
        columns=["key", "name", "project_type_key", "style"],
    )


@project_app.command("view")
def view_project(
    key: Annotated[str, typer.Argument(help="Project key (e.g. PROJ).")],
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """View details of a single project."""
    client = get_client()
    raw = client.get(client.platform(f"/project/{key}"))
    project = ProjectDetail.from_jira(raw).model_dump()
    output_result(project, format=format, json_fields=json_fields)


@project_app.command("create")
def create_project(
    key: Annotated[str, typer.Option("--key", "-k", help="Project key (e.g. PROJ).")],
    name: Annotated[str, typer.Option("--name", "-n", help="Project name.")],
    lead: Annotated[str, typer.Option("--lead", help="Lead account ID.")],
    type: Annotated[str, typer.Option("--type", "-t", help="Project type key.")] = "software",
    description: Annotated[Optional[str], typer.Option("--description", "-d", help="Project description.")] = None,
    template: Annotated[Optional[str], typer.Option("--template", help="Project template key (e.g. com.pyxis.greenhopper.jira:gh-simplified-scrum-classic).")] = None,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """Create a new Jira project."""
    client = get_client()
    body: dict = {
        "key": key,
        "name": name,
        "projectTypeKey": type,
        "leadAccountId": lead,
    }
    if description is not None:
        body["description"] = description
    if template is not None:
        body["projectTemplateKey"] = template
    raw = client.post(client.platform("/project"), json=body)
    output_result(raw, format=format, json_fields=json_fields)


@project_app.command("components")
def list_components(
    key: Annotated[str, typer.Argument(help="Project key (e.g. PROJ).")],
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """List components for a project."""
    client = get_client()
    raw = client.get(client.platform(f"/project/{key}/components"))
    components = [Component.from_jira(c).model_dump() for c in raw]
    output_result(
        components,
        format=format,
        json_fields=json_fields,
        columns=["id", "name", "lead", "description"],
    )


@project_app.command("versions")
def list_versions(
    key: Annotated[str, typer.Argument(help="Project key (e.g. PROJ).")],
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """List versions for a project."""
    client = get_client()
    raw = client.get(client.platform(f"/project/{key}/versions"))
    versions = [Version.from_jira(v).model_dump() for v in raw]
    output_result(
        versions,
        format=format,
        json_fields=json_fields,
        columns=["id", "name", "released", "release_date", "description"],
    )


@project_app.command("roles")
def list_roles(
    key: Annotated[str, typer.Argument(help="Project key (e.g. PROJ).")],
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """List roles defined in a project."""
    client = get_client()
    raw = client.get(client.platform(f"/project/{key}/role"))
    # raw is a dict of role_name -> URL, extract id from URL
    roles = []
    for name, url in raw.items():
        # URL looks like .../rest/api/3/project/{key}/role/{id}
        match = re.search(r"/role/(\d+)$", url)
        role_id = match.group(1) if match else ""
        roles.append({"name": name, "id": role_id, "url": url})
    output_result(
        roles,
        format=format,
        json_fields=json_fields,
        columns=["name", "id", "url"],
    )


@project_app.command("statuses")
def list_statuses(
    key: Annotated[str, typer.Argument(help="Project key (e.g. PROJ).")],
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", help="Comma-separated fields to include in JSON output.")] = None,
) -> None:
    """List statuses available in a project, across all issue types."""
    client = get_client()
    raw = client.get(client.platform(f"/project/{key}/statuses"))
    # raw is a list of issue types, each with a "statuses" list. Flatten to unique statuses.
    seen: set[str] = set()
    statuses: list[dict] = []
    for issue_type in raw:
        for status in issue_type.get("statuses", []):
            sid = status.get("id", "")
            if sid not in seen:
                seen.add(sid)
                category = status.get("statusCategory", {})
                statuses.append({
                    "id": sid,
                    "name": status.get("name", ""),
                    "category": category.get("name", "") if isinstance(category, dict) else "",
                })
    output_result(
        statuses,
        format=format,
        json_fields=json_fields,
        columns=["id", "name", "category"],
    )
