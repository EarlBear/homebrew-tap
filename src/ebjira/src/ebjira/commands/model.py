"""Domain model commands — analyze, diff, apply, and generate ERD.

Compares the current Jira project state against the target domain model
defined in docs/design-work-taxonomy.md and helps evolve toward it.

Examples:
    ebjira model analyze --project EARL
    ebjira model diff --project EARL --format table
    ebjira model apply --project EARL --dry-run
    ebjira model erd --project EARL --include-issues --output erd.md
"""

from __future__ import annotations

import re
import sys
import uuid
from collections import Counter
from typing import Annotated, Optional

import typer

from ebjira.client import get_client
from ebjira.output import Format, console, err_console, output_result

model_app = typer.Typer(
    name="model",
    help="Analyze and evolve the domain model (types, statuses, components).",
    no_args_is_help=True,
)

# ── Target model from design-work-taxonomy.md ──

TARGET_TYPES = {
    "Epic": {"hierarchy_level": 1, "description": "Collection of related work"},
    "Story": {"hierarchy_level": 0, "description": "Customer can do something new"},
    "Feature": {"hierarchy_level": 0, "description": "Backend capability unlocking stories"},
    "Deliverable": {"hierarchy_level": 0, "description": "Produce a document or artifact"},
    "Task": {"hierarchy_level": 0, "description": "Action that needs to happen"},
    "Bug": {"hierarchy_level": 0, "description": "Something is broken"},
    "Subtask": {"hierarchy_level": -1, "description": "Smaller piece of parent work"},
}

TARGET_STATUSES = {
    "Prioritized": "TODO",
    "In Progress": "IN_PROGRESS",
    "Blocked": "IN_PROGRESS",
    "Ready For Review": "IN_PROGRESS",
    "Done": "DONE",
}

TARGET_COMPONENTS = {
    "discovery-toolkit": "Tools for finding and qualifying Shopify stores (Google Dorking, Store Finder, Mobile Browse Agent)",
    "store-analyzer": "Tools for analyzing stores (Site Crawler, Theme Scorer, Shop Intelligence DB, ABCD Checklist)",
    "outreach-crm": "Tools for managing customer outreach (Pitch Email, Follow-Up, Credibility Statement)",
    "sales-enablement": "Materials for sales (Pitch Deck, Blog Posts, Website Catalog, Founder's Package)",
    "earlbear-platform": "The EarlBear product/website that customers see",
}

TARGET_WORKFLOW = {
    "name": "EARL Workflow",
    "description": "EarlBear project workflow: Prioritized \u2192 In Progress \u2192 Blocked \u2192 Ready For Review \u2192 Done",
    "transitions": [
        ("Prioritized", "In Progress"),
        ("In Progress", "Blocked"),
        ("In Progress", "Ready For Review"),
        ("Blocked", "In Progress"),
        ("Ready For Review", "Done"),
    ],
}

TARGET_WORKFLOW_SCHEME = {
    "name": "EARL Workflow Scheme",
    "description": "Assigns EARL Workflow to all issue types",
}

# Component assignments from the design doc
TARGET_COMPONENT_ASSIGNMENTS: dict[str, str] = {
    "EARL-2": "discovery-toolkit",
    "EARL-3": "discovery-toolkit",
    "EARL-6": "discovery-toolkit",
    "EARL-7": "discovery-toolkit",
    "EARL-11": "discovery-toolkit",
    "EARL-12": "discovery-toolkit",
    "EARL-4": "store-analyzer",
    "EARL-8": "store-analyzer",
    "EARL-9": "store-analyzer",
    "EARL-10": "store-analyzer",
    "EARL-14": "store-analyzer",
    "EARL-15": "store-analyzer",
    "EARL-16": "outreach-crm",
    "EARL-17": "outreach-crm",
    "EARL-18": "outreach-crm",
    "EARL-19": "outreach-crm",
    "EARL-13": "sales-enablement",
    "EARL-20": "sales-enablement",
    "EARL-21": "sales-enablement",
    "EARL-22": "sales-enablement",
    "EARL-24": "sales-enablement",
    "EARL-5": "earlbear-platform",
    "EARL-23": "earlbear-platform",
    "EARL-25": "earlbear-platform",
}

# Reclassification rules from the design doc
RECLASSIFY_MAP: dict[str, str] = {
    "EARL-22": "Deliverable",  # Pitch Deck
    "EARL-24": "Deliverable",  # Credibility Package
    "EARL-20": "Deliverable",  # Founder's Package
    "EARL-16": "Deliverable",  # Top 3 Issues Report
    "EARL-21": "Deliverable",  # Per-Store Analysis Blog Post
    "EARL-13": "Deliverable",  # Website Example Catalog
    "EARL-8": "Feature",       # Site Crawler
    "EARL-6": "Feature",       # Shopify Store Finder
    "EARL-3": "Feature",       # Theme Divergence Scorer
    # Borderline — design doc recommends Feature
    "EARL-9": "Feature",       # ABCD Store Checklist
    "EARL-10": "Feature",      # Screenshot Library
    "EARL-14": "Feature",      # Page Graph Catalog
    "EARL-15": "Feature",      # Shop Intelligence DB
}

# Heuristic keyword sets for misclassification detection
DELIVERABLE_KEYWORDS = re.compile(
    r"\b(report|deck|package|blog|catalog|email|pitch|credibility|post|document|guide|template)\b",
    re.IGNORECASE,
)
FEATURE_KEYWORDS = re.compile(
    r"\b(crawler|scorer|finder|engine|db|database|agent|intelligence|graph|screenshot|checklist)\b",
    re.IGNORECASE,
)
TASK_KEYWORDS = re.compile(
    r"\b(set up|configure|install|migrate|clean|update|fix|deploy|test)\b",
    re.IGNORECASE,
)

# ── Shared options ──

FormatOption = Annotated[
    Format,
    typer.Option("--format", "-f", help="Output format: json, table, or plain."),
]
JsonOption = Annotated[
    Optional[str],
    typer.Option("--json", "-j", help="Comma-separated fields to include in JSON output."),
]
ProjectOption = Annotated[
    str,
    typer.Option("--project", "-p", help="Project key (e.g. EARL)."),
]


# ── Helpers ──


def _fetch_all_data(project: str) -> dict:
    """Fetch issue types, statuses, components, and issues for a project."""
    client = get_client()

    # Issue types for the project
    project_data = client.get(client.platform(f"/project/{project}"))
    project_id = project_data["id"]
    issue_types_raw = client.get(
        client.platform("/issuetype/project"),
        params={"projectId": project_id},
    )

    # Statuses for the project
    statuses_raw = client.get(client.platform(f"/project/{project}/statuses"))
    seen_statuses: set[str] = set()
    statuses = []
    for it in statuses_raw:
        for s in it.get("statuses", []):
            sid = s.get("id", "")
            if sid not in seen_statuses:
                seen_statuses.add(sid)
                cat = s.get("statusCategory", {})
                statuses.append({
                    "id": sid,
                    "name": s.get("name", ""),
                    "category": cat.get("name", "") if isinstance(cat, dict) else "",
                    "category_key": cat.get("key", "") if isinstance(cat, dict) else "",
                })

    # Components
    components_raw = client.get(client.platform(f"/project/{project}/components"))
    components = [
        {
            "id": c.get("id", ""),
            "name": c.get("name", ""),
            "description": c.get("description", ""),
        }
        for c in components_raw
    ]

    # All issues
    issues = client.search_jql_all(
        jql=f'project = "{project}" ORDER BY key ASC',
        fields=["summary", "issuetype", "status", "labels", "components", "parent"],
        max_results=200,
    )
    parsed_issues = []
    for issue in issues:
        fields = issue.get("fields", {})
        it = fields.get("issuetype", {})
        st = fields.get("status", {})
        comps = fields.get("components", [])
        labels = fields.get("labels", [])
        parent = fields.get("parent", {})
        parsed_issues.append({
            "key": issue.get("key", ""),
            "summary": fields.get("summary", ""),
            "type": it.get("name", ""),
            "type_id": it.get("id", ""),
            "status": st.get("name", ""),
            "labels": labels,
            "components": [c.get("name", "") for c in comps],
            "parent_key": parent.get("key", "") if parent else "",
        })

    # Workflows — search for the target workflow by name
    workflows: list[dict] = []
    try:
        wf_search = client.get(
            client.platform("/workflow/search"),
            params={"workflowName": TARGET_WORKFLOW["name"]},
        )
        wf_values = wf_search.get("values", []) if isinstance(wf_search, dict) else []
        workflows = [
            {
                "name": w.get("name", ""),
                "entity_id": w.get("id", {}).get("entityId", "") if isinstance(w.get("id"), dict) else "",
            }
            for w in wf_values
        ]
    except Exception:
        pass  # Workflow search may fail on some Jira configurations

    # Workflow schemes — search for the target scheme and check project assignment
    workflow_schemes: list[dict] = []
    project_workflow_scheme: dict | None = None
    try:
        ws_raw = client.get_paginated(
            client.platform("/workflowscheme"),
            results_key="values",
        )
        workflow_schemes = [
            {
                "id": ws.get("id", ""),
                "name": ws.get("name", ""),
                "default_workflow": ws.get("defaultWorkflow", {}).get("name", "") if isinstance(ws.get("defaultWorkflow"), dict) else ws.get("defaultWorkflow", ""),
            }
            for ws in ws_raw
        ]
    except Exception:
        pass

    # Check which workflow scheme is assigned to the project
    try:
        project_scheme = client.get(
            client.platform(f"/workflowscheme/project"),
            params={"projectId": project_id},
        )
        values = project_scheme.get("values", []) if isinstance(project_scheme, dict) else []
        if values:
            ps = values[0]
            wfs = ps.get("workflowScheme", {})
            project_workflow_scheme = {
                "id": wfs.get("id", ""),
                "name": wfs.get("name", ""),
            }
    except Exception:
        pass

    return {
        "project_id": project_id,
        "issue_types": [
            {
                "id": it.get("id", ""),
                "name": it.get("name", ""),
                "subtask": it.get("subtask", False),
                "hierarchy_level": it.get("hierarchyLevel", 0),
                "description": it.get("description", ""),
            }
            for it in issue_types_raw
        ],
        "statuses": statuses,
        "components": components,
        "issues": parsed_issues,
        "workflows": workflows,
        "workflow_schemes": workflow_schemes,
        "project_workflow_scheme": project_workflow_scheme,
    }


def _detect_misclassification(issue: dict) -> dict | None:
    """Heuristically detect if an issue might be misclassified."""
    key = issue["key"]
    summary = issue["summary"]
    current_type = issue["type"]

    # Check explicit reclassification map first
    if key in RECLASSIFY_MAP:
        recommended = RECLASSIFY_MAP[key]
        if current_type != recommended:
            return {
                "key": key,
                "summary": summary,
                "current_type": current_type,
                "recommended_type": recommended,
                "reasoning": f"Design doc reclassification: {current_type} -> {recommended}",
                "confidence": "high",
            }
        return None

    # Heuristic detection for issues not in the explicit map
    if current_type == "Epic":
        return None  # Don't reclassify Epics

    suggested = None
    reasoning = None

    if current_type != "Deliverable" and DELIVERABLE_KEYWORDS.search(summary):
        suggested = "Deliverable"
        reasoning = f"Summary contains deliverable keywords (artifact to produce)"
    elif current_type != "Feature" and FEATURE_KEYWORDS.search(summary):
        suggested = "Feature"
        reasoning = f"Summary contains feature keywords (backend capability)"
    elif current_type not in ("Task", "Subtask") and TASK_KEYWORDS.search(summary):
        suggested = "Task"
        reasoning = f"Summary contains task keywords (generic action)"

    if suggested and suggested != current_type:
        return {
            "key": key,
            "summary": summary,
            "current_type": current_type,
            "recommended_type": suggested,
            "reasoning": reasoning,
            "confidence": "medium",
        }
    return None


def _compute_diff(data: dict) -> list[dict]:
    """Compare current state against target model, return list of changes."""
    changes: list[dict] = []

    # 1. Missing issue types
    current_type_names = {it["name"] for it in data["issue_types"]}
    for type_name, type_def in TARGET_TYPES.items():
        if type_name not in current_type_names:
            changes.append({
                "action": "create_type",
                "target": type_name,
                "current": None,
                "recommended": type_name,
                "reasoning": f"Target model requires type '{type_name}': {type_def['description']}",
            })

    # 2. Missing statuses
    current_status_names = {s["name"] for s in data["statuses"]}
    for status_name, category in TARGET_STATUSES.items():
        if status_name not in current_status_names:
            changes.append({
                "action": "create_status",
                "target": status_name,
                "current": None,
                "recommended": f"{status_name} ({category})",
                "reasoning": f"Target workflow requires status '{status_name}' in category {category}",
            })

    # 3. Missing components
    current_comp_names = {c["name"] for c in data["components"]}
    for comp_name, comp_desc in TARGET_COMPONENTS.items():
        if comp_name not in current_comp_names:
            changes.append({
                "action": "create_component",
                "target": comp_name,
                "current": None,
                "recommended": comp_name,
                "reasoning": f"Target model requires component: {comp_desc}",
            })

    # 4. Reclassifications
    for issue in data["issues"]:
        rec = _detect_misclassification(issue)
        if rec:
            changes.append({
                "action": "reclassify",
                "target": rec["key"],
                "current": rec["current_type"],
                "recommended": rec["recommended_type"],
                "reasoning": rec["reasoning"],
            })

    # 5. Missing component assignments
    current_comp_names_set = current_comp_names  # already a set
    for issue in data["issues"]:
        key = issue["key"]
        if key in TARGET_COMPONENT_ASSIGNMENTS:
            target_comp = TARGET_COMPONENT_ASSIGNMENTS[key]
            if target_comp not in issue["components"]:
                changes.append({
                    "action": "assign_component",
                    "target": key,
                    "current": ", ".join(issue["components"]) or "(none)",
                    "recommended": target_comp,
                    "reasoning": f"Design doc assigns {key} to component '{target_comp}'",
                })

    # 6. Missing workflow
    existing_wf_names = {w["name"] for w in data.get("workflows", [])}
    if TARGET_WORKFLOW["name"] not in existing_wf_names:
        changes.append({
            "action": "create_workflow",
            "target": TARGET_WORKFLOW["name"],
            "current": None,
            "recommended": TARGET_WORKFLOW["name"],
            "reasoning": f"Target model requires workflow '{TARGET_WORKFLOW['name']}': {TARGET_WORKFLOW['description']}",
        })

    # 7. Missing workflow scheme
    existing_scheme_names = {ws["name"] for ws in data.get("workflow_schemes", [])}
    if TARGET_WORKFLOW_SCHEME["name"] not in existing_scheme_names:
        changes.append({
            "action": "create_workflow_scheme",
            "target": TARGET_WORKFLOW_SCHEME["name"],
            "current": None,
            "recommended": TARGET_WORKFLOW_SCHEME["name"],
            "reasoning": f"Target model requires workflow scheme '{TARGET_WORKFLOW_SCHEME['name']}': {TARGET_WORKFLOW_SCHEME['description']}",
        })

    # 8. Workflow scheme not assigned to project
    project_scheme = data.get("project_workflow_scheme")
    target_scheme_name = TARGET_WORKFLOW_SCHEME["name"]
    if not project_scheme or project_scheme.get("name") != target_scheme_name:
        current_name = project_scheme.get("name", "(none)") if project_scheme else "(none)"
        changes.append({
            "action": "assign_workflow_scheme",
            "target": target_scheme_name,
            "current": current_name,
            "recommended": target_scheme_name,
            "reasoning": f"Workflow scheme '{target_scheme_name}' must be assigned to the project",
        })

    return changes


# ── Commands ──


@model_app.command("analyze")
def analyze(
    project: ProjectOption = "EARL",
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Analyze the current domain model — types, statuses, components, issues.

    Fetches all project data and generates a summary including type
    distribution, status distribution, component coverage, label usage,
    and misclassification recommendations.

    Examples:
        ebjira model analyze --project EARL
        ebjira model analyze --format table
        ebjira model analyze --json types,recommendations
    """
    data = _fetch_all_data(project)

    # Type distribution
    type_counts = Counter(i["type"] for i in data["issues"])
    type_dist = [{"type": t, "count": c} for t, c in type_counts.most_common()]

    # Status distribution
    status_counts = Counter(i["status"] for i in data["issues"])
    status_dist = [{"status": s, "count": c} for s, c in status_counts.most_common()]

    # Component coverage
    issues_with_comp = sum(1 for i in data["issues"] if i["components"])
    issues_without_comp = sum(1 for i in data["issues"] if not i["components"])
    comp_coverage = {
        "with_component": issues_with_comp,
        "without_component": issues_without_comp,
        "total": len(data["issues"]),
    }

    # Label usage
    all_labels: list[str] = []
    for i in data["issues"]:
        all_labels.extend(i["labels"])
    label_counts = Counter(all_labels)
    label_usage = [{"label": l, "count": c} for l, c in label_counts.most_common()]

    # Misclassification recommendations
    recommendations = []
    for issue in data["issues"]:
        rec = _detect_misclassification(issue)
        if rec:
            recommendations.append(rec)

    result = {
        "types": {
            "defined": [{"name": it["name"], "id": it["id"]} for it in data["issue_types"]],
            "distribution": type_dist,
        },
        "statuses": {
            "defined": [{"name": s["name"], "id": s["id"], "category": s["category"]} for s in data["statuses"]],
            "distribution": status_dist,
        },
        "components": {
            "defined": [{"name": c["name"], "id": c["id"]} for c in data["components"]],
            "coverage": comp_coverage,
        },
        "issues": {
            "total": len(data["issues"]),
            "by_type": type_dist,
        },
        "labels": label_usage,
        "recommendations": recommendations,
    }

    if format == Format.table:
        # Show recommendations table for table format
        if recommendations:
            output_result(
                recommendations,
                format=format,
                json_fields=json_fields,
                columns=["key", "summary", "current_type", "recommended_type", "confidence", "reasoning"],
            )
        else:
            console.print("[green]No misclassification recommendations.[/green]")
        # Also print summary stats
        console.print(f"\nTypes: {len(data['issue_types'])} defined, {len(type_dist)} in use")
        console.print(f"Statuses: {len(data['statuses'])} defined")
        console.print(f"Components: {len(data['components'])} defined, {comp_coverage['with_component']}/{comp_coverage['total']} issues assigned")
        console.print(f"Labels: {len(label_usage)} unique labels in use")
        console.print(f"Recommendations: {len(recommendations)} reclassifications suggested")
    else:
        output_result(result, format=format, json_fields=json_fields)


@model_app.command("diff")
def diff(
    project: ProjectOption = "EARL",
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Show what changes are needed to reach the target domain model.

    Compares current Jira state against the target model from
    docs/design-work-taxonomy.md. Shows missing types, statuses,
    components, and recommended reclassifications.

    Examples:
        ebjira model diff --project EARL
        ebjira model diff --format table
        ebjira model diff --json action,target,recommended
    """
    data = _fetch_all_data(project)
    changes = _compute_diff(data)

    if not changes:
        result = {"changes": [], "message": "Current model matches target. No changes needed."}
    else:
        result = {"changes": changes, "total": len(changes)}

    if format == Format.table:
        if changes:
            output_result(
                changes,
                format=format,
                json_fields=json_fields,
                columns=["action", "target", "current", "recommended", "reasoning"],
            )
        else:
            console.print("[green]No changes needed — current model matches target.[/green]")
    else:
        output_result(result, format=format, json_fields=json_fields)


@model_app.command("apply")
def apply(
    project: ProjectOption = "EARL",
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would happen without making changes.")] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompts.")] = False,
    type_only: Annotated[bool, typer.Option("--type-only", help="Only create missing issue types.")] = False,
    status_only: Annotated[bool, typer.Option("--status-only", help="Only create missing statuses.")] = False,
    components_only: Annotated[bool, typer.Option("--components-only", help="Only create missing components.")] = False,
    reclassify_only: Annotated[bool, typer.Option("--reclassify-only", help="Only reclassify issues.")] = False,
    workflow_only: Annotated[bool, typer.Option("--workflow-only", help="Only create the target workflow.")] = False,
    scheme_only: Annotated[bool, typer.Option("--scheme-only", help="Only create and assign the workflow scheme.")] = False,
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Apply model changes to reach the target domain model.

    Reads the diff and applies changes: creates types, statuses,
    components, and reclassifies issues. Each change requires
    confirmation unless --yes is passed.

    Examples:
        ebjira model apply --project EARL --dry-run
        ebjira model apply --project EARL --yes
        ebjira model apply --project EARL --type-only
        ebjira model apply --project EARL --reclassify-only --dry-run
        ebjira model apply --project EARL --workflow-only
        ebjira model apply --project EARL --scheme-only
    """
    data = _fetch_all_data(project)
    changes = _compute_diff(data)

    if not changes:
        output_result(
            {"applied": [], "message": "No changes needed."},
            format=format,
            json_fields=json_fields,
        )
        return

    # Filter changes by scope flags
    any_scope = type_only or status_only or components_only or reclassify_only or workflow_only or scheme_only
    if any_scope:
        allowed_actions = set()
        if type_only:
            allowed_actions.add("create_type")
        if status_only:
            allowed_actions.add("create_status")
        if components_only:
            allowed_actions.update({"create_component", "assign_component"})
        if reclassify_only:
            allowed_actions.add("reclassify")
        if workflow_only:
            allowed_actions.add("create_workflow")
        if scheme_only:
            allowed_actions.update({"create_workflow_scheme", "assign_workflow_scheme"})
        changes = [c for c in changes if c["action"] in allowed_actions]

    if not changes:
        output_result(
            {"applied": [], "message": "No matching changes for the selected scope."},
            format=format,
            json_fields=json_fields,
        )
        return

    client = get_client()
    applied: list[dict] = []
    skipped: list[dict] = []

    # Build lookup maps
    type_name_to_id: dict[str, str] = {it["name"]: it["id"] for it in data["issue_types"]}
    comp_name_to_id: dict[str, str] = {c["name"]: c["id"] for c in data["components"]}

    for change in changes:
        action = change["action"]
        target = change["target"]
        recommended = change["recommended"]

        # Describe the change
        if action == "create_type":
            desc = f"Create issue type '{target}' (hierarchy level {TARGET_TYPES[target]['hierarchy_level']})"
        elif action == "create_status":
            desc = f"Create status '{target}' (category: {TARGET_STATUSES[target]})"
        elif action == "create_component":
            desc = f"Create component '{target}'"
        elif action == "assign_component":
            desc = f"Assign {target} to component '{recommended}'"
        elif action == "reclassify":
            desc = f"Reclassify {target}: {change['current']} -> {recommended}"
        elif action == "create_workflow":
            desc = f"Create workflow '{target}' with {len(TARGET_WORKFLOW['transitions'])} transitions"
        elif action == "create_workflow_scheme":
            desc = f"Create workflow scheme '{target}'"
        elif action == "assign_workflow_scheme":
            desc = f"Assign workflow scheme '{target}' to project (current: {change['current']})"
        else:
            desc = f"{action}: {target}"

        if dry_run:
            err_console.print(f"[yellow]DRY RUN:[/yellow] {desc}")
            applied.append({**change, "status": "dry_run"})
            continue

        # Confirm unless --yes
        if not yes:
            confirm = typer.confirm(f"  {desc}?")
            if not confirm:
                skipped.append({**change, "status": "skipped"})
                continue

        # Execute the change
        try:
            if action == "create_type":
                type_def = TARGET_TYPES[target]
                body: dict = {
                    "name": target,
                    "type": "subtask" if type_def["hierarchy_level"] < 0 else "standard",
                }
                if type_def["description"]:
                    body["description"] = type_def["description"]
                if type_def["hierarchy_level"] != 0:
                    body["hierarchyLevel"] = type_def["hierarchy_level"]
                result = client.post(client.platform("/issuetype"), json=body)
                # Update lookup for subsequent reclassifications
                type_name_to_id[target] = result.get("id", "")
                applied.append({**change, "status": "applied", "created_id": result.get("id", "")})

            elif action == "create_status":
                category = TARGET_STATUSES[target]
                status_entry: dict = {"name": target, "statusCategory": category}
                scope = {"type": "PROJECT", "project": {"id": data["project_id"]}}
                body = {"statuses": [status_entry], "scope": scope}
                result = client.post(client.platform("/statuses"), json=body)
                applied.append({**change, "status": "applied"})

            elif action == "create_component":
                body = {
                    "name": target,
                    "project": project,
                    "description": TARGET_COMPONENTS.get(target, ""),
                }
                result = client.post(client.platform("/component"), json=body)
                comp_name_to_id[target] = result.get("id", "")
                applied.append({**change, "status": "applied", "created_id": result.get("id", "")})

            elif action == "assign_component":
                comp_id = comp_name_to_id.get(recommended)
                if not comp_id:
                    # Try to find it from current data
                    for c in data["components"]:
                        if c["name"] == recommended:
                            comp_id = c["id"]
                            break
                if not comp_id:
                    err_console.print(f"[red]Component '{recommended}' not found. Create it first.[/red]")
                    skipped.append({**change, "status": "error", "error": f"Component '{recommended}' not found"})
                    continue
                # Get current components for the issue, add the new one
                issue_data = client.get(
                    client.platform(f"/issue/{target}"),
                    params={"fields": "components"},
                )
                current_comps = issue_data.get("fields", {}).get("components", [])
                comp_ids = [{"id": c["id"]} for c in current_comps]
                comp_ids.append({"id": comp_id})
                client.put(
                    client.platform(f"/issue/{target}"),
                    json={"fields": {"components": comp_ids}},
                )
                applied.append({**change, "status": "applied"})

            elif action == "reclassify":
                target_type_id = type_name_to_id.get(recommended)
                if not target_type_id:
                    err_console.print(f"[red]Issue type '{recommended}' not found. Create it first.[/red]")
                    skipped.append({**change, "status": "error", "error": f"Type '{recommended}' not found"})
                    continue
                client.put(
                    client.platform(f"/issue/{target}"),
                    json={"fields": {"issuetype": {"id": target_type_id}}},
                )
                applied.append({**change, "status": "applied"})

            elif action == "create_workflow":
                # Build statuses with UUID references for the workflow create API
                wf_statuses: list[dict] = []
                wf_status_map: dict[str, str] = {}
                for status_name, category in TARGET_STATUSES.items():
                    ref = str(uuid.uuid4())
                    wf_status_map[status_name] = ref
                    wf_statuses.append({
                        "name": status_name,
                        "statusCategory": category,
                        "statusReference": ref,
                    })

                # Build transitions from TARGET_WORKFLOW
                wf_transitions: list[dict] = []
                for from_name, to_name in TARGET_WORKFLOW["transitions"]:
                    wf_transitions.append({
                        "name": f"{from_name} to {to_name}",
                        "from": wf_status_map[from_name],
                        "to": wf_status_map[to_name],
                        "type": "DIRECTED",
                    })

                workflow_entry: dict = {
                    "name": TARGET_WORKFLOW["name"],
                    "description": TARGET_WORKFLOW["description"],
                    "statuses": [
                        {"statusReference": s["statusReference"], "properties": {}}
                        for s in wf_statuses
                    ],
                    "transitions": wf_transitions,
                }

                wf_body = {
                    "statuses": wf_statuses,
                    "workflows": [workflow_entry],
                    "scope": {
                        "type": "PROJECT",
                        "project": {"id": data["project_id"]},
                    },
                }

                result = client.post(client.platform("/workflows/create"), json=wf_body)
                applied.append({**change, "status": "applied"})

            elif action == "create_workflow_scheme":
                ws_body: dict = {
                    "name": TARGET_WORKFLOW_SCHEME["name"],
                    "description": TARGET_WORKFLOW_SCHEME["description"],
                    "defaultWorkflow": TARGET_WORKFLOW["name"],
                }
                result = client.post(client.platform("/workflowscheme"), json=ws_body)
                # Store the created scheme ID for subsequent assign action
                created_scheme_id = str(result.get("id", ""))
                applied.append({**change, "status": "applied", "created_id": created_scheme_id})

            elif action == "assign_workflow_scheme":
                # Find the scheme ID — either just created or already existing
                scheme_id = None
                # Check if we just created it in a previous step
                for prev in applied:
                    if prev.get("action") == "create_workflow_scheme" and prev.get("created_id"):
                        scheme_id = prev["created_id"]
                        break
                if not scheme_id:
                    # Look up from existing schemes
                    for ws in data.get("workflow_schemes", []):
                        if ws["name"] == target:
                            scheme_id = str(ws["id"])
                            break
                if not scheme_id:
                    err_console.print(f"[red]Workflow scheme '{target}' not found. Create it first.[/red]")
                    skipped.append({**change, "status": "error", "error": f"Scheme '{target}' not found"})
                    continue
                client.put(
                    client.platform("/workflowscheme/project"),
                    json={"projectId": data["project_id"], "workflowSchemeId": scheme_id},
                )
                applied.append({**change, "status": "applied", "scheme_id": scheme_id})

        except Exception as e:
            err_console.print(f"[red]Failed: {desc} — {e}[/red]")
            skipped.append({**change, "status": "error", "error": str(e)})

    result_data = {
        "applied": applied,
        "skipped": skipped,
        "summary": {
            "applied_count": len(applied),
            "skipped_count": len(skipped),
        },
    }
    output_result(result_data, format=format, json_fields=json_fields)


@model_app.command("erd")
def erd(
    project: ProjectOption = "EARL",
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="Write to file (default: stdout).")] = None,
    include_issues: Annotated[bool, typer.Option("--include-issues", help="Show actual issues in the diagram.")] = False,
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Generate a Mermaid ERD from the current Jira project state.

    Pulls live data and generates an ERD showing issue types, hierarchy
    relationships, component groupings, and status workflow. Includes
    click directives linking to Jira filters.

    Examples:
        ebjira model erd --project EARL
        ebjira model erd --project EARL --include-issues
        ebjira model erd --project EARL --output docs/erd.md
        ebjira model erd --format plain
    """
    data = _fetch_all_data(project)
    client = get_client()
    base_url = client.base_url

    lines: list[str] = []
    lines.append("erDiagram")

    # Collect which types and components actually exist
    type_names = {it["name"] for it in data["issue_types"]}
    comp_names = [c["name"] for c in data["components"]]

    # Group issues by type and component
    issues_by_type: dict[str, list[dict]] = {}
    issues_by_comp: dict[str, list[dict]] = {}
    for issue in data["issues"]:
        t = issue["type"]
        issues_by_type.setdefault(t, []).append(issue)
        for comp in issue["components"]:
            issues_by_comp.setdefault(comp, []).append(issue)

    # Hierarchy relationships (Epic -> child types)
    child_types = type_names - {"Epic", "Subtask"}
    for ct in sorted(child_types):
        lines.append(f"    Epic ||--o{{ {_mermaid_safe(ct)} : contains")

    # Subtask relationships
    subtask_parents = {"Story", "Feature", "Task"} & type_names
    for parent in sorted(subtask_parents):
        if "Subtask" in type_names:
            lines.append(f'    {_mermaid_safe(parent)} ||--o{{ Subtask : "broken into"')

    # Component relationships
    component_related_types = {"Story", "Feature", "Deliverable", "Task"} & type_names
    for comp in comp_names:
        for ct in sorted(component_related_types):
            lines.append(f'    {_mermaid_safe(comp)} ||--o{{ {_mermaid_safe(ct)} : "app context"')

    lines.append("")

    # Entity definitions — Components
    for comp in comp_names:
        safe = _mermaid_safe(comp)
        desc = ""
        for c in data["components"]:
            if c["name"] == comp:
                desc = c.get("description", "")
                break
        issue_count = len(issues_by_comp.get(comp, []))
        lines.append(f"    {safe} {{")
        lines.append(f'        string name "{comp}"')
        lines.append(f'        int issue_count "{issue_count}"')
        if desc:
            lines.append(f'        string description "{_esc(desc[:60])}"')
        lines.append("    }")

    # Entity definitions — Issue types
    for it in data["issue_types"]:
        name = it["name"]
        safe = _mermaid_safe(name)
        count = len(issues_by_type.get(name, []))
        lines.append(f"    {safe} {{")
        lines.append(f'        string name "{name}"')
        lines.append(f'        int hierarchy_level "{it["hierarchy_level"]}"')
        lines.append(f'        int count "{count}"')
        if it.get("description"):
            lines.append(f'        string description "{_esc(it["description"][:60])}"')
        lines.append("    }")

    # Include actual issues if requested
    if include_issues:
        lines.append("")
        lines.append("    %% Actual issues")
        for issue in data["issues"]:
            safe_key = _mermaid_safe(issue["key"])
            safe_type = _mermaid_safe(issue["type"])
            lines.append(f"    {safe_type} ||--|| {safe_key} : instance")
            lines.append(f"    {safe_key} {{")
            lines.append(f'        string summary "{_esc(issue["summary"][:50])}"')
            lines.append(f'        string status "{issue["status"]}"')
            if issue["labels"]:
                lines.append(f'        string labels "{", ".join(issue["labels"][:3])}"')
            lines.append("    }")

    # Click directives for Jira filters
    lines.append("")
    lines.append("    %% Click directives — link to Jira filters")
    for it in data["issue_types"]:
        name = it["name"]
        safe = _mermaid_safe(name)
        jql = f'project = {project} AND issuetype = "{name}"'
        url = f"{base_url}/issues/?jql={_url_encode(jql)}"
        lines.append(f'    click {safe} "{url}" "View {name} issues in Jira"')
    for comp in comp_names:
        safe = _mermaid_safe(comp)
        jql = f'project = {project} AND component = "{comp}"'
        url = f"{base_url}/issues/?jql={_url_encode(jql)}"
        lines.append(f'    click {safe} "{url}" "View {comp} issues in Jira"')

    mermaid = "\n".join(lines)

    if output:
        with open(output, "w") as f:
            f.write(f"```mermaid\n{mermaid}\n```\n")
        console.print(f"[green]ERD written to {output}[/green]")
        result_data: dict = {"file": output, "lines": len(lines)}
    else:
        result_data = {"mermaid": mermaid}

    if format == Format.table or format == Format.plain:
        print(mermaid)
    else:
        output_result(result_data, format=format, json_fields=json_fields)


# ── Mermaid helpers ──


def _mermaid_safe(name: str) -> str:
    """Convert a name to a Mermaid-safe identifier (alphanumeric + underscore)."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)


def _esc(text: str) -> str:
    """Escape quotes for Mermaid strings."""
    return text.replace('"', "'").replace("\n", " ")


def _url_encode(text: str) -> str:
    """Minimal URL encoding for JQL in click directives."""
    return text.replace(" ", "%20").replace('"', "%22").replace("=", "%3D")
