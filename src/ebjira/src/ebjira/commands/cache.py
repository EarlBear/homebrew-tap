"""Cache commands — manage the local Jira ID cache.

The cache stores issue type IDs, status IDs, component IDs, and user account IDs
so that other commands and skills don't need to discover them every time.

The cache lives at .jira-cache.json (gitignored). Regenerate with:
    ebjira cache refresh --project EARL
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Annotated, Optional

import typer

from ebjira.client import get_client
from ebjira.output import Format, output_result

cache_app = typer.Typer(no_args_is_help=True)

CACHE_FILE = os.environ.get("JIRA_CACHE_FILE", ".jira-cache.json")


def _build_cache(project: str) -> dict:
    """Pull live Jira data and build a complete ID cache."""
    client = get_client()
    p = client.platform

    cache: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": {"key": project},
    }

    # Project info
    proj = client.get(p(f"/project/{project}"))
    cache["project"]["id"] = proj.get("id", "")
    cache["project"]["style"] = proj.get("style", "")

    # Issue types (all global + project-scoped)
    types = client.get(p("/issuetype"))
    cache["issue_types"] = {}
    for t in types:
        cache["issue_types"][t["name"]] = t["id"]

    # Statuses
    statuses = client.get(p("/status"))
    cache["statuses"] = {s["name"]: s["id"] for s in statuses}

    # Components for project
    components = client.get(p(f"/project/{project}/components"))
    cache["components"] = {c["name"]: c["id"] for c in components}

    # Users
    users = client.get(p("/user/search"), params={"query": "", "maxResults": 50})
    cache["users"] = {}
    for u in users:
        if u.get("active"):
            cache["users"][u["displayName"]] = u["accountId"]

    # Owner aliases (known mappings)
    cache["owner_aliases"] = {
        "saad": "duke",
        "Omar Eid": "omar",
    }

    return cache


@cache_app.command()
def refresh(
    project: Annotated[str, typer.Option("--project", "-p", help="Project key.")] = "EARL",
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="Output file path.")] = None,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
) -> None:
    """Refresh the local Jira ID cache from live data.

    Pulls issue types, statuses, components, and users from Jira and writes
    to .jira-cache.json (or --output path).

    Examples:
        ebjira cache refresh --project EARL
        ebjira cache refresh --output /tmp/cache.json
    """
    cache = _build_cache(project)
    filepath = output or CACHE_FILE

    with open(filepath, "w") as f:
        json.dump(cache, f, indent=2)
        f.write("\n")

    output_result(
        {
            "status": "refreshed",
            "file": filepath,
            "issue_types": len(cache["issue_types"]),
            "statuses": len(cache["statuses"]),
            "components": len(cache["components"]),
            "users": len(cache["users"]),
        },
        format=format,
    )


@cache_app.command()
def show(
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", "-j", help="Comma-separated fields.")] = None,
) -> None:
    """Show the current cached IDs.

    Examples:
        ebjira cache show
        ebjira cache show --json issue_types
        ebjira cache show --format table
    """
    if not os.path.isfile(CACHE_FILE):
        output_result(
            {"error": "NO_CACHE", "message": f"No cache file at {CACHE_FILE}. Run: ebjira cache refresh"},
            format=format,
        )
        raise typer.Exit(1)

    with open(CACHE_FILE) as f:
        cache = json.load(f)

    output_result(cache, format=format, json_fields=json_fields)


@cache_app.command()
def lookup(
    name: Annotated[str, typer.Argument(help="Name to look up (issue type, status, component, or user).")],
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
) -> None:
    """Look up an ID by name from the cache.

    Searches across issue types, statuses, components, and users.

    Examples:
        ebjira cache lookup Deliverable
        ebjira cache lookup "In Progress"
        ebjira cache lookup omar
    """
    if not os.path.isfile(CACHE_FILE):
        output_result(
            {"error": "NO_CACHE", "message": f"No cache file. Run: ebjira cache refresh"},
            format=format,
        )
        raise typer.Exit(1)

    with open(CACHE_FILE) as f:
        cache = json.load(f)

    matches = []
    for category in ["issue_types", "statuses", "components", "users"]:
        mapping = cache.get(category, {})
        for key, value in mapping.items():
            if name.lower() in key.lower():
                matches.append({"category": category, "name": key, "id": value})

    # Also check aliases
    for alias, canonical in cache.get("owner_aliases", {}).items():
        if name.lower() in alias.lower():
            matches.append({"category": "alias", "name": alias, "maps_to": canonical})

    output_result(matches, format=format, columns=["category", "name", "id"])
