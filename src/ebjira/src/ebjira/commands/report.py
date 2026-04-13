"""Report commands — board-style reports sliced by type, epic, component, and AI status.

Examples:
    ebjira report type-summary --project EARL
    ebjira report epic-summary --project EARL --format table
    ebjira report ai-dashboard --project EARL
    ebjira report component-summary --project EARL
    ebjira report health --project EARL --format table
"""

from __future__ import annotations

from collections import defaultdict
from typing import Annotated, Optional

import typer

from ebjira.client import get_client
from ebjira.output import Format, output_result

report_app = typer.Typer(
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# ── Shared option types ──

FormatOption = Annotated[
    Format,
    typer.Option("--format", "-f", help="Output format: json, table, or plain."),
]

JsonOption = Annotated[
    Optional[str],
    typer.Option("--json", "-j", help="Comma-separated fields to include in JSON output."),
]

# ── Shared fields for search queries ──

_REPORT_FIELDS = [
    "summary", "status", "issuetype", "priority",
    "labels", "assignee", "parent", "components",
    "created", "updated",
]


def _fetch_all_issues(project: str, extra_jql: str = "") -> list[dict]:
    """Fetch all issues for a project via JQL."""
    client = get_client()
    jql = f'project = "{project}"'
    if extra_jql:
        jql += f" AND {extra_jql}"
    jql += " ORDER BY created ASC"
    return client.search_jql_all(jql=jql, fields=_REPORT_FIELDS, max_results=500)


def _extract_field(issue: dict, field: str) -> str:
    """Safely extract a nested Jira field value as a string."""
    fields = issue.get("fields", {})
    value = fields.get(field)
    if value is None:
        return ""
    if isinstance(value, dict):
        return value.get("name", value.get("displayName", ""))
    return str(value)


def _extract_status(issue: dict) -> str:
    return _extract_field(issue, "status")


def _extract_type(issue: dict) -> str:
    return _extract_field(issue, "issuetype")


def _extract_parent_name(issue: dict) -> str:
    """Extract the parent (epic) summary from an issue."""
    fields = issue.get("fields", {})
    parent = fields.get("parent")
    if not parent:
        return "(No Epic)"
    # Parent has fields.summary in the search response
    parent_fields = parent.get("fields", {})
    if parent_fields:
        return parent_fields.get("summary", parent.get("key", "(No Epic)"))
    return parent.get("key", "(No Epic)")


def _extract_labels(issue: dict) -> list[str]:
    return issue.get("fields", {}).get("labels", [])


def _extract_components(issue: dict) -> list[str]:
    components = issue.get("fields", {}).get("components", [])
    return [c.get("name", "") for c in components if isinstance(c, dict)]


def _extract_key(issue: dict) -> str:
    return issue.get("key", "")


def _extract_summary(issue: dict) -> str:
    return issue.get("fields", {}).get("summary", "")


def _build_crosstab(issues: list[dict], group_fn, group_label: str) -> tuple[list[dict], list[str]]:
    """Build a cross-tab from issues grouped by group_fn and status.

    Returns (rows_as_dicts, ordered_status_columns).
    """
    # Collect all statuses and groups
    groups: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    all_statuses: set[str] = set()

    for issue in issues:
        group = group_fn(issue)
        status = _extract_status(issue)
        if not status:
            status = "(Unknown)"
        groups[group][status] += 1
        all_statuses.add(status)

    # Canonical status order (common Jira statuses first, then alphabetical remainder)
    status_order = ["Prioritized", "In Progress", "Blocked", "Ready For Review", "Done"]
    ordered = [s for s in status_order if s in all_statuses]
    remaining = sorted(all_statuses - set(ordered))
    ordered.extend(remaining)

    # Build row dicts
    rows = []
    for group_name in sorted(groups.keys()):
        row: dict = {group_label: group_name}
        for status in ordered:
            row[status] = groups[group_name].get(status, 0)
        rows.append(row)

    return rows, ordered


# ── type-summary ──


@report_app.command("type-summary")
def type_summary(
    project: Annotated[str, typer.Option(help="Project key (e.g. EARL).")],
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Type swimlane report — issues grouped by type and status.

    Shows a cross-tab grid: rows are issue types, columns are statuses,
    cells are issue counts. Use --format table for a visual swimlane view.

    Example: ebjira report type-summary --project EARL --format table
    """
    issues = _fetch_all_issues(project)
    rows, statuses = _build_crosstab(issues, _extract_type, "type")
    columns = ["type"] + statuses
    output_result(rows, format=format, json_fields=json_fields, columns=columns)


# ── epic-summary ──


@report_app.command("epic-summary")
def epic_summary(
    project: Annotated[str, typer.Option(help="Project key (e.g. EARL).")],
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Epic swimlane report — issues grouped by epic (parent) and status.

    Shows a cross-tab grid: rows are epic names, columns are statuses,
    cells are issue counts. Epics themselves are excluded (only children shown).

    Example: ebjira report epic-summary --project EARL --format table
    """
    all_issues = _fetch_all_issues(project)
    # Exclude epics themselves — only show their children
    child_issues = [i for i in all_issues if _extract_type(i).lower() != "epic"]
    rows, statuses = _build_crosstab(child_issues, _extract_parent_name, "epic")
    columns = ["epic"] + statuses
    output_result(rows, format=format, json_fields=json_fields, columns=columns)


# ── ai-dashboard ──


@report_app.command("ai-dashboard")
def ai_dashboard(
    project: Annotated[str, typer.Option(help="Project key (e.g. EARL).")],
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """AI work status dashboard — eligible, drafting, in review, completed.

    Queries issues with labels ai-eligible or ai-drafted and breaks them
    down by workflow stage. Shows aggregate counts and individual issues.

    Example: ebjira report ai-dashboard --project EARL
    """
    # Fetch ai-eligible and ai-drafted issues
    issues = _fetch_all_issues(
        project,
        extra_jql='labels in ("ai-eligible", "ai-drafted")',
    )

    # Categorize
    ai_eligible: list[dict] = []
    drafting: list[dict] = []
    in_review: list[dict] = []
    completed: list[dict] = []
    all_issue_summaries: list[dict] = []

    for issue in issues:
        labels = _extract_labels(issue)
        status = _extract_status(issue)
        key = _extract_key(issue)
        summary = _extract_summary(issue)
        issue_type = _extract_type(issue)

        entry = {
            "key": key,
            "summary": summary,
            "type": issue_type,
            "status": status,
            "labels": labels,
        }
        all_issue_summaries.append(entry)

        if "ai-eligible" in labels:
            ai_eligible.append(entry)

        # Categorize by current status
        status_lower = status.lower()
        if status_lower == "drafting":
            drafting.append(entry)
        elif status_lower == "in review" and "ai-drafted" in labels:
            in_review.append(entry)
        elif status_lower == "done" and "ai-drafted" in labels:
            completed.append(entry)

    # Compute draft pass rate
    total_drafted = len(in_review) + len(completed)
    # Issues that were drafted and are now back in progress (rework) indicate failures
    rework = [
        e for e in all_issue_summaries
        if "ai-drafted" in e["labels"] and e["status"].lower() in ("in progress", "to do")
    ]
    total_attempts = total_drafted + len(rework)
    pass_rate = (
        f"{(total_drafted / total_attempts * 100):.0f}%"
        if total_attempts > 0
        else "N/A"
    )

    result = {
        "ai_eligible": len(ai_eligible),
        "drafting": len(drafting),
        "in_review": len(in_review),
        "completed": len(completed),
        "draft_pass_rate": pass_rate,
        "drafting_issues": [e["key"] for e in drafting],
        "in_review_issues": [e["key"] for e in in_review],
        "completed_issues": [e["key"] for e in completed],
        "issues": all_issue_summaries,
    }

    output_result(result, format=format, json_fields=json_fields)


# ── component-summary ──


@report_app.command("component-summary")
def component_summary(
    project: Annotated[str, typer.Option(help="Project key (e.g. EARL).")],
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Component/application health — issues grouped by component and status.

    Shows which applications have work in progress, stuck, or done.
    Issues without a component appear under "(No Component)".

    Example: ebjira report component-summary --project EARL --format table
    """
    all_issues = _fetch_all_issues(project)
    # Exclude epics
    child_issues = [i for i in all_issues if _extract_type(i).lower() != "epic"]

    # Build crosstab — an issue can belong to multiple components
    groups: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    all_statuses: set[str] = set()

    for issue in child_issues:
        components = _extract_components(issue)
        status = _extract_status(issue) or "(Unknown)"
        all_statuses.add(status)

        if not components:
            groups["(No Component)"][status] += 1
        else:
            for comp in components:
                groups[comp][status] += 1

    # Canonical status order
    status_order = ["Prioritized", "In Progress", "Blocked", "Ready For Review", "Done"]
    ordered = [s for s in status_order if s in all_statuses]
    remaining = sorted(all_statuses - set(ordered))
    ordered.extend(remaining)

    rows = []
    for comp_name in sorted(groups.keys()):
        row: dict = {"component": comp_name}
        for status in ordered:
            row[status] = groups[comp_name].get(status, 0)
        rows.append(row)

    columns = ["component"] + ordered
    output_result(rows, format=format, json_fields=json_fields, columns=columns)


# ── health ──


@report_app.command("health")
def health(
    project: Annotated[str, typer.Option(help="Project key (e.g. EARL).")],
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Overall project health dashboard — combines all report views.

    Shows type distribution, epic progress, AI status, component coverage,
    issues without components, and priority distribution in one report.

    Example: ebjira report health --project EARL --format table
    """
    all_issues = _fetch_all_issues(project)
    child_issues = [i for i in all_issues if _extract_type(i).lower() != "epic"]

    # ── Type distribution ──
    type_counts: dict[str, int] = defaultdict(int)
    for issue in child_issues:
        type_counts[_extract_type(issue) or "(Unknown)"] += 1

    # ── Status distribution ──
    status_counts: dict[str, int] = defaultdict(int)
    for issue in child_issues:
        status_counts[_extract_status(issue) or "(Unknown)"] += 1

    # ── Priority distribution ──
    priority_counts: dict[str, int] = defaultdict(int)
    for issue in child_issues:
        priority_counts[_extract_field(issue, "priority") or "(None)"] += 1

    # ── Epic progress (% done per epic) ──
    epic_totals: dict[str, int] = defaultdict(int)
    epic_done: dict[str, int] = defaultdict(int)
    for issue in child_issues:
        epic = _extract_parent_name(issue)
        epic_totals[epic] += 1
        if _extract_status(issue).lower() == "done":
            epic_done[epic] += 1

    epic_progress = []
    for epic_name in sorted(epic_totals.keys()):
        total = epic_totals[epic_name]
        done = epic_done.get(epic_name, 0)
        pct = f"{(done / total * 100):.0f}%" if total > 0 else "0%"
        epic_progress.append({
            "epic": epic_name,
            "total": total,
            "done": done,
            "progress": pct,
        })

    # ── AI status ──
    ai_eligible_count = sum(
        1 for i in child_issues if "ai-eligible" in _extract_labels(i)
    )
    ai_drafted_count = sum(
        1 for i in child_issues if "ai-drafted" in _extract_labels(i)
    )

    # ── Issues without components ──
    no_component = [
        {"key": _extract_key(i), "summary": _extract_summary(i)}
        for i in child_issues
        if not _extract_components(i)
    ]

    # ── Component coverage ──
    component_set: set[str] = set()
    for issue in child_issues:
        for comp in _extract_components(issue):
            component_set.add(comp)

    result = {
        "total_issues": len(all_issues),
        "total_non_epic": len(child_issues),
        "type_distribution": dict(sorted(type_counts.items())),
        "status_distribution": dict(sorted(status_counts.items())),
        "priority_distribution": dict(sorted(priority_counts.items())),
        "epic_progress": epic_progress,
        "ai_eligible": ai_eligible_count,
        "ai_drafted": ai_drafted_count,
        "components": sorted(component_set),
        "issues_without_component": no_component,
        "issues_without_component_count": len(no_component),
    }

    output_result(result, format=format, json_fields=json_fields)
