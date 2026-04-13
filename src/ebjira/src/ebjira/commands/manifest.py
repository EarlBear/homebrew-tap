"""Manifest commands — discover, diff, plan, apply, export, diagram.

Declarative Jira project configuration. The manifest (manifest.yaml) is the
single source of truth. These commands compare it against live Jira state
and reconcile differences.

Examples:
    ebjira manifest discover --project EARL
    ebjira manifest diff --project EARL
    ebjira manifest plan --project EARL
    ebjira manifest apply --project EARL --dry-run
    ebjira manifest export --project EARL --output snapshot.yaml
    ebjira manifest diagram --manifest manifest.yaml --output-dir docs/diagrams/
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Annotated, Any, Optional

import typer
import yaml

from ebjira.client import get_client
from ebjira.manifest_schema import (
    Manifest,
    StatusConfig,
    load_manifest,
)
from ebjira.output import Format, console, err_console, output_result

manifest_app = typer.Typer(
    name="manifest",
    help="Declarative Jira project configuration (discover, diff, plan, apply, export, diagram).",
    no_args_is_help=True,
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
    typer.Option("--project", "-p", help="Project key (overrides manifest)."),
]
ManifestOption = Annotated[
    Optional[str],
    typer.Option("--manifest", "-m", help="Path to manifest YAML (default: $JIRA_MANIFEST_FILE or manifests/jira/manifest.yaml)."),
]


# ── Data fetching ──


def _fetch_jira_state(project: str) -> dict[str, Any]:
    """Fetch statuses, issue types, components, workflows, and workflow schemes from Jira."""
    client = get_client()

    # Project ID
    project_data = client.get(client.platform(f"/project/{project}"))
    project_id = project_data["id"]

    # Issue types
    issue_types_raw = client.get(
        client.platform("/issuetype/project"),
        params={"projectId": project_id},
    )

    # Statuses — use global search to find all statuses (not just project-scoped)
    statuses: list[dict] = []
    try:
        statuses_raw = client.get(
            client.platform("/statuses/search"),
            params={"maxResults": 200},
        )
        for s in statuses_raw.get("values", []):
            cat = s.get("statusCategory", "")
            statuses.append({
                "id": s.get("id", ""),
                "name": s.get("name", ""),
                "category": cat if isinstance(cat, str) else "",
                "category_key": cat if isinstance(cat, str) else "",
            })
    except Exception:
        # Fallback to project-scoped statuses
        statuses_raw = client.get(client.platform(f"/project/{project}/statuses"))
        seen: set[str] = set()
        for it in statuses_raw:
            for s in it.get("statuses", []):
                sid = s.get("id", "")
                if sid not in seen:
                    seen.add(sid)
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
        {"id": c.get("id", ""), "name": c.get("name", ""), "description": c.get("description", "")}
        for c in components_raw
    ]

    # Workflows
    workflows: list[dict] = []
    try:
        wf_search = client.get(client.platform("/workflow/search"), params={"maxResults": 50})
        wf_values = wf_search.get("values", []) if isinstance(wf_search, dict) else []
        workflows = [
            {
                # Jira API quirk: workflow name is in description field, not name
                "name": w.get("id", {}).get("name", "") if isinstance(w.get("id"), dict) and w.get("id", {}).get("name") else w.get("description", w.get("name", "")),
                "entity_id": (
                    w.get("id", {}).get("entityId", "")
                    if isinstance(w.get("id"), dict)
                    else ""
                ),
                "description": w.get("description", ""),
            }
            for w in wf_values
        ]
    except Exception:
        pass

    # Workflow schemes
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
                "default_workflow": (
                    ws.get("defaultWorkflow", {}).get("name", "")
                    if isinstance(ws.get("defaultWorkflow"), dict)
                    else ws.get("defaultWorkflow", "")
                ),
            }
            for ws in ws_raw
        ]
    except Exception:
        pass

    try:
        project_scheme = client.get(
            client.platform("/workflowscheme/project"),
            params={"projectId": project_id},
        )
        values = project_scheme.get("values", []) if isinstance(project_scheme, dict) else []
        if values:
            wfs = values[0].get("workflowScheme", {})
            project_workflow_scheme = {"id": wfs.get("id", ""), "name": wfs.get("name", "")}
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
        "workflows": workflows,
        "workflow_schemes": workflow_schemes,
        "project_workflow_scheme": project_workflow_scheme,
    }


# ── Diff logic ──


def _normalize_jira_category(raw: str) -> str:
    """Map a Jira status category key/name to the manifest category value."""
    return {
        "new": "TODO",
        "indeterminate": "IN_PROGRESS",
        "done": "DONE",
        # Display-name fallbacks
        "To Do": "TODO",
        "In Progress": "IN_PROGRESS",
        "Done": "DONE",
    }.get(raw, raw)


def _compute_manifest_diff(manifest: Manifest, jira_state: dict[str, Any]) -> list[dict]:
    """Compare manifest against live Jira state, return list of changes."""
    changes: list[dict] = []

    # --- Statuses ---
    retired_status_names = set(manifest.retired.statuses)
    jira_statuses_by_name = {s["name"]: s for s in jira_state["statuses"]}
    manifest_status_names = {s.name for s in manifest.statuses}

    for sc in manifest.statuses:
        if sc.name not in jira_statuses_by_name:
            changes.append({
                "section": "statuses",
                "action": "create",
                "target": sc.name,
                "detail": f"category={sc.category}",
            })
        else:
            # Gap 1: Status category mismatch — status exists but has wrong category
            jira_cat = _normalize_jira_category(jira_statuses_by_name[sc.name].get("category", ""))
            if jira_cat and jira_cat != sc.category:
                changes.append({
                    "section": "statuses",
                    "action": "category_mismatch",
                    "target": sc.name,
                    "detail": f"expected={sc.category}, actual={jira_cat}",
                })

    for s in jira_state["statuses"]:
        if s["name"] not in manifest_status_names:
            # Gap 2: Retired statuses — suppress extra_in_jira for known retired statuses
            if s["name"] in retired_status_names:
                changes.append({
                    "section": "statuses",
                    "action": "retired_in_jira",
                    "target": s["name"],
                    "detail": f"id={s['id']}, documented as retired in manifest",
                })
            else:
                changes.append({
                    "section": "statuses",
                    "action": "extra_in_jira",
                    "target": s["name"],
                    "detail": f"id={s['id']}, exists in Jira but not in manifest",
                })

    # --- Issue types ---
    jira_type_names = {it["name"] for it in jira_state["issue_types"]}
    manifest_type_names = {it.name for it in manifest.issue_types}

    for it in manifest.issue_types:
        if it.name not in jira_type_names:
            changes.append({
                "section": "issue_types",
                "action": "create",
                "target": it.name,
                "detail": f"hierarchy={it.hierarchy}, description={it.description}",
            })

    for it in jira_state["issue_types"]:
        if it["name"] not in manifest_type_names:
            changes.append({
                "section": "issue_types",
                "action": "extra_in_jira",
                "target": it["name"],
                "detail": f"id={it['id']}, exists in Jira but not in manifest",
            })

    # --- Components ---
    jira_comps_by_name = {c["name"]: c for c in jira_state["components"]}
    manifest_comp_names = {c.name for c in manifest.components}

    for comp in manifest.components:
        if comp.name not in jira_comps_by_name:
            changes.append({
                "section": "components",
                "action": "create",
                "target": comp.name,
                "detail": comp.description,
            })
        elif comp.description:
            # Gap 3: Component description mismatch — component exists but description differs
            jira_desc = jira_comps_by_name[comp.name].get("description", "")
            if jira_desc != comp.description:
                changes.append({
                    "section": "components",
                    "action": "description_mismatch",
                    "target": comp.name,
                    "detail": f"expected={comp.description!r}, actual={jira_desc!r}",
                })

    for c in jira_state["components"]:
        if c["name"] not in manifest_comp_names:
            changes.append({
                "section": "components",
                "action": "extra_in_jira",
                "target": c["name"],
                "detail": f"id={c['id']}, exists in Jira but not in manifest",
            })

    # --- Workflow ---
    if manifest.workflow:
        jira_wf_names = {w["name"] for w in jira_state.get("workflows", [])}
        if manifest.workflow.name not in jira_wf_names:
            changes.append({
                "section": "workflow",
                "action": "create",
                "target": manifest.workflow.name,
                "detail": manifest.workflow.description,
            })

    # --- Workflow scheme ---
    if manifest.workflow_scheme:
        jira_ws_names = {ws["name"] for ws in jira_state.get("workflow_schemes", [])}
        if manifest.workflow_scheme.name not in jira_ws_names:
            changes.append({
                "section": "workflow_scheme",
                "action": "create",
                "target": manifest.workflow_scheme.name,
                "detail": f"default_workflow={manifest.workflow_scheme.default_workflow}",
            })

        # Check assignment
        project_ws = jira_state.get("project_workflow_scheme")
        if not project_ws or project_ws.get("name") != manifest.workflow_scheme.name:
            current = project_ws.get("name", "(none)") if project_ws else "(none)"
            changes.append({
                "section": "workflow_scheme",
                "action": "assign",
                "target": manifest.workflow_scheme.name,
                "detail": f"current={current}",
            })

    return changes


# ── Commands ──


@manifest_app.command("discover")
def discover(
    project: ProjectOption = "",
    manifest_path: ManifestOption = None,
    output: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Write JSON snapshot to file."),
    ] = None,
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Fetch and display current Jira project state.

    Terraform-style discovery: reads the live state of statuses, issue
    types, components, workflows, and workflow schemes. Useful before
    running ``diff`` or ``plan`` to understand what currently exists.

    Examples:
        ebjira manifest discover
        ebjira manifest discover --project EARL
        ebjira manifest discover --output snapshot.json
        ebjira manifest discover --format table
    """
    # Resolve project: explicit flag wins, otherwise fall back to manifest.
    proj = project
    if not proj:
        try:
            m = load_manifest(manifest_path)
            proj = m.project.key
        except FileNotFoundError:
            err_console.print(
                "[red]No --project given and no manifest found to infer project key.[/red]"
            )
            raise typer.Exit(code=2)

    jira_state = _fetch_jira_state(proj)

    result: dict[str, Any] = {
        "project": proj,
        "statuses": jira_state["statuses"],
        "issue_types": jira_state["issue_types"],
        "components": jira_state["components"],
        "workflows": jira_state["workflows"],
        "workflow_schemes": jira_state["workflow_schemes"],
        "project_workflow_scheme": jira_state.get("project_workflow_scheme"),
    }

    if output:
        Path(output).write_text(json.dumps(result, indent=2))
        err_console.print(f"[green]Snapshot written to {output}[/green]")

    if format == Format.table:
        console.print(f"\n[bold]Jira Discovery — {proj}[/bold]\n")
        console.print(f"  Statuses ({len(result['statuses'])}):")
        for s in result["statuses"]:
            console.print(f"    - {s.get('name', '?')} ({s.get('category', '')})")
        console.print(f"\n  Issue Types ({len(result['issue_types'])}):")
        for it in result["issue_types"]:
            console.print(
                f"    - {it.get('name', '?')} (hierarchy={it.get('hierarchy_level', 0)})"
            )
        console.print(f"\n  Components ({len(result['components'])}):")
        for c in result["components"]:
            console.print(f"    - {c.get('name', '?')}: {c.get('description', '')}")
        console.print(f"\n  Workflows ({len(result['workflows'])}):")
        for w in result["workflows"]:
            console.print(f"    - {w.get('name', '?')}")
        console.print(f"\n  Workflow Schemes ({len(result['workflow_schemes'])}):")
        for ws in result["workflow_schemes"]:
            console.print(f"    - {ws.get('name', '?')}")
        console.print()
    else:
        output_result(result, format=format, json_fields=json_fields)


@manifest_app.command("plan")
def plan(
    project: ProjectOption = "",
    manifest_path: ManifestOption = None,
    output: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Write plan to JSONL file (one action per line)."),
    ] = None,
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Show the actions needed to bring Jira into conformance.

    Like ``diff``, but formatted as a list of creation actions you can
    review before running ``apply``. Extra-in-Jira items are not
    included (apply never deletes without ``--allow-delete``).

    Examples:
        ebjira manifest plan
        ebjira manifest plan --project EARL
        ebjira manifest plan --output plan.jsonl
    """
    m = load_manifest(manifest_path)
    proj = project or m.project.key
    jira_state = _fetch_jira_state(proj)
    changes = _compute_manifest_diff(m, jira_state)

    # Actions that require no automated fix (informational only)
    _SKIP_ACTIONS = {"extra_in_jira", "retired_in_jira", "category_mismatch"}

    actions: list[dict[str, Any]] = []
    for change in changes:
        if change["action"] in _SKIP_ACTIONS:
            continue

        section = change["section"]
        target = change["target"]
        action_kind = change["action"]

        if section == "statuses" and action_kind == "create":
            sc = next((s for s in m.statuses if s.name == target), None)
            actions.append({
                "action": "create_status",
                "section": section,
                "name": target,
                "category": sc.category if sc else "",
            })
        elif section == "issue_types" and action_kind == "create":
            it = next((i for i in m.issue_types if i.name == target), None)
            actions.append({
                "action": "create_issue_type",
                "section": section,
                "name": target,
                "hierarchy": it.hierarchy if it else 0,
                "description": it.description if it else "",
            })
        elif section == "components" and action_kind == "create":
            comp = next((c for c in m.components if c.name == target), None)
            actions.append({
                "action": "create_component",
                "section": section,
                "name": target,
                "project": proj,
                "description": comp.description if comp else "",
            })
        elif section == "components" and action_kind == "description_mismatch":
            comp = next((c for c in m.components if c.name == target), None)
            actions.append({
                "action": "update_component",
                "section": section,
                "name": target,
                "description": comp.description if comp else "",
            })
        elif section == "workflow" and action_kind == "create":
            actions.append({
                "action": "create_workflow",
                "section": section,
                "name": target,
            })
        elif section == "workflow_scheme" and action_kind == "create":
            actions.append({
                "action": "create_workflow_scheme",
                "section": section,
                "name": target,
            })
        elif section == "workflow_scheme" and action_kind == "assign":
            actions.append({
                "action": "assign_workflow_scheme",
                "section": section,
                "name": target,
            })
        else:
            actions.append({
                "action": f"{section}_{action_kind}",
                "section": section,
                "name": target,
            })

    result: dict[str, Any] = {
        "project": proj,
        "actions": actions,
        "total": len(actions),
    }

    if output:
        jsonl = "\n".join(json.dumps(a) for a in actions)
        Path(output).write_text(jsonl + ("\n" if jsonl else ""))
        err_console.print(
            f"[green]Plan written to {output} ({len(actions)} actions)[/green]"
        )

    if format == Format.table:
        console.print(f"\n[bold]Conformance Plan — {proj}[/bold]\n")
        if not actions:
            console.print("[green]No actions needed — Jira is conformant.[/green]\n")
        else:
            for i, a in enumerate(actions, 1):
                extra = ""
                if "category" in a:
                    extra = f" (category={a['category']})"
                elif "hierarchy" in a:
                    extra = f" (hierarchy={a['hierarchy']})"
                console.print(f"  {i}. [{a['action']}] {a.get('name', '')}{extra}")
            console.print(
                f"\n{len(actions)} action(s) planned. "
                "Run `ebjira manifest apply` to execute.\n"
            )
    else:
        output_result(result, format=format, json_fields=json_fields)


@manifest_app.command("diff")
def diff(
    project: ProjectOption = "",
    manifest_path: ManifestOption = None,
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Compare manifest against live Jira state.

    Shows what's different between the manifest file and the actual
    Jira project configuration. Flags missing items, extra items,
    and mismatches.

    Examples:
        ebjira manifest diff
        ebjira manifest diff --project EARL
        ebjira manifest diff --manifest custom-manifest.yaml
        ebjira manifest diff --format table
    """
    m = load_manifest(manifest_path)
    proj = project or m.project.key
    jira_state = _fetch_jira_state(proj)
    changes = _compute_manifest_diff(m, jira_state)

    if not changes:
        result: dict = {"changes": [], "message": "Manifest matches Jira. No differences."}
    else:
        result = {"changes": changes, "total": len(changes)}

    if format == Format.table:
        if changes:
            output_result(
                changes,
                format=format,
                json_fields=json_fields,
                columns=["section", "action", "target", "detail"],
            )
        else:
            console.print("[green]Manifest matches Jira. No differences.[/green]")
    else:
        output_result(result, format=format, json_fields=json_fields)


@manifest_app.command("apply")
def apply(
    project: ProjectOption = "",
    manifest_path: ManifestOption = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would happen without making changes.")] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompts.")] = False,
    allow_delete: Annotated[bool, typer.Option("--allow-delete", help="Allow removing items that exist in Jira but not in manifest.")] = False,
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Make Jira match the manifest.

    Computes the diff and applies changes: creates missing statuses,
    issue types, components, workflows, and workflow schemes. Never
    deletes anything without --allow-delete.

    Examples:
        ebjira manifest apply --dry-run
        ebjira manifest apply --yes
        ebjira manifest apply --project EARL --yes
        ebjira manifest apply --allow-delete --yes
    """
    m = load_manifest(manifest_path)
    proj = project or m.project.key
    jira_state = _fetch_jira_state(proj)
    changes = _compute_manifest_diff(m, jira_state)

    if not changes:
        output_result(
            {"applied": [], "skipped": [], "message": "No changes needed."},
            format=format,
            json_fields=json_fields,
        )
        return

    client = get_client()
    applied: list[dict] = []
    skipped: list[dict] = []

    # Build lookup maps from manifest
    manifest_statuses: dict[str, StatusConfig] = {s.name: s for s in m.statuses}
    manifest_types: dict[str, Any] = {it.name: it for it in m.issue_types}
    manifest_comps: dict[str, Any] = {c.name: c for c in m.components}

    for change in changes:
        section = change["section"]
        action = change["action"]
        target = change["target"]

        # Skip extras unless --allow-delete
        if action == "extra_in_jira":
            if not allow_delete:
                skipped.append({**change, "status": "skipped", "reason": "extra_in_jira (use --allow-delete)"})
                continue
            # We don't actually implement deletion in this wave — just flag it
            skipped.append({**change, "status": "skipped", "reason": "deletion not yet implemented"})
            continue

        # Retired statuses are informational only — nothing to apply
        if action == "retired_in_jira":
            skipped.append({**change, "status": "skipped", "reason": "retired_in_jira (documented, no action needed)"})
            continue

        # Category mismatches are informational only — Jira doesn't support changing status category via API
        if action == "category_mismatch":
            skipped.append({**change, "status": "skipped", "reason": "category_mismatch (informational only — cannot change status category via API)"})
            continue

        # Build description
        if section == "statuses" and action == "create":
            sc = manifest_statuses[target]
            desc = f"Create status '{target}' (category: {sc.category})"
        elif section == "issue_types" and action == "create":
            it_conf = manifest_types[target]
            desc = f"Create issue type '{target}' (hierarchy: {it_conf.hierarchy})"
        elif section == "components" and action == "create":
            comp = manifest_comps[target]
            desc = f"Create component '{target}'"
        elif section == "components" and action == "description_mismatch":
            comp = manifest_comps[target]
            desc = f"Update component '{target}' description"
        elif section == "workflow" and action == "create":
            desc = f"Create workflow '{target}'"
        elif section == "workflow_scheme" and action == "create":
            desc = f"Create workflow scheme '{target}'"
        elif section == "workflow_scheme" and action == "assign":
            desc = f"Assign workflow scheme '{target}' to project"
        else:
            desc = f"{section}/{action}: {target}"

        if dry_run:
            err_console.print(f"[yellow]DRY RUN:[/yellow] {desc}")
            applied.append({**change, "status": "dry_run"})
            continue

        if not yes:
            confirm = typer.confirm(f"  {desc}?")
            if not confirm:
                skipped.append({**change, "status": "skipped"})
                continue

        try:
            if section == "statuses" and action == "create":
                sc = manifest_statuses[target]
                body: dict = {
                    "statuses": [{"name": target, "statusCategory": sc.category}],
                    "scope": {"type": "GLOBAL"},
                }
                try:
                    client.post(client.platform("/statuses"), json=body)
                except Exception as status_err:
                    # Status may already exist globally — check and skip if so
                    if "already exist" in str(status_err).lower() or "duplicate" in str(status_err).lower():
                        applied.append({**change, "status": "applied", "note": "already exists globally"})
                        continue
                    raise
                applied.append({**change, "status": "applied"})

            elif section == "issue_types" and action == "create":
                it_conf = manifest_types[target]
                body = {
                    "name": target,
                    "type": "subtask" if it_conf.hierarchy < 0 else "standard",
                }
                if it_conf.description:
                    body["description"] = it_conf.description
                if it_conf.hierarchy != 0:
                    body["hierarchyLevel"] = it_conf.hierarchy
                client.post(client.platform("/issuetype"), json=body)
                applied.append({**change, "status": "applied"})

            elif section == "components" and action == "create":
                comp = manifest_comps[target]
                body = {"name": target, "project": proj, "description": comp.description}
                client.post(client.platform("/component"), json=body)
                applied.append({**change, "status": "applied"})

            elif section == "components" and action == "description_mismatch":
                # Update the component's description to match the manifest
                jira_comp = next((c for c in jira_state["components"] if c["name"] == target), None)
                if not jira_comp:
                    skipped.append({**change, "status": "error", "error": f"component '{target}' not found in Jira state"})
                    continue
                comp = manifest_comps[target]
                client.put(
                    client.platform(f"/component/{jira_comp['id']}"),
                    json={"description": comp.description},
                )
                applied.append({**change, "status": "applied"})

            elif section == "workflow" and action == "create":
                assert m.workflow is not None
                # Build statuses with UUID references
                wf_statuses: list[dict] = []
                wf_status_map: dict[str, str] = {}
                for sc in m.statuses:
                    ref = str(uuid.uuid4())
                    wf_status_map[sc.name] = ref
                    wf_statuses.append({
                        "name": sc.name,
                        "statusCategory": sc.category,
                        "statusReference": ref,
                    })

                # Build transitions (each needs a unique id)
                wf_transitions: list[dict] = []
                for tr in m.workflow.transitions:
                    wf_transitions.append({
                        "id": str(uuid.uuid4()),
                        "name": f"{tr.from_status} to {tr.to_status}",
                        "from": [{"statusReference": wf_status_map[tr.from_status]}],
                        "to": {"statusReference": wf_status_map[tr.to_status]},
                        "type": "DIRECTED",
                    })

                # Build transitions dict keyed by id
                transitions_dict: dict[str, dict] = {}
                for wft in wf_transitions:
                    tid = wft["id"]
                    transitions_dict[tid] = wft

                workflow_entry: dict = {
                    "name": m.workflow.name,
                    "description": m.workflow.description,
                    "statuses": [
                        {"statusReference": s["statusReference"], "properties": {}}
                        for s in wf_statuses
                    ],
                    "transitions": transitions_dict,
                }
                wf_body: dict = {
                    "statuses": wf_statuses,
                    "workflows": [workflow_entry],
                    "scope": {"type": "PROJECT", "project": {"id": jira_state["project_id"]}},
                }
                client.post(client.platform("/workflows/create"), json=wf_body)
                applied.append({**change, "status": "applied"})

            elif section == "workflow_scheme" and action == "create":
                assert m.workflow_scheme is not None
                ws_body: dict = {
                    "name": m.workflow_scheme.name,
                    "description": m.workflow_scheme.description,
                    "defaultWorkflow": m.workflow_scheme.default_workflow,
                }
                result = client.post(client.platform("/workflowscheme"), json=ws_body)
                created_id = str(result.get("id", ""))
                applied.append({**change, "status": "applied", "created_id": created_id})

            elif section == "workflow_scheme" and action == "assign":
                # Strategy: update the project's EXISTING scheme to use the new workflow
                # (PUT /workflowscheme/{id} with updateDraftIfNeeded=true)
                # This works for non-empty projects, unlike PUT /workflowscheme/project
                assert m.workflow_scheme is not None

                # Find the project's current scheme ID
                current_scheme_id = None
                for ws in jira_state.get("workflow_schemes", []):
                    current_scheme_id = str(ws["id"])
                    break  # Take the first one

                if current_scheme_id:
                    # Step 1: Update scheme with draft (works for non-empty projects)
                    update_body: dict = {
                        "defaultWorkflow": m.workflow_scheme.default_workflow,
                        "updateDraftIfNeeded": True,
                    }
                    client.put(
                        client.platform(f"/workflowscheme/{current_scheme_id}"),
                        json=update_body,
                    )

                    # Step 2: Check if a draft was created (non-empty project)
                    try:
                        draft = client.get(client.platform(f"/workflowscheme/{current_scheme_id}/draft"))
                        if draft.get("draft"):
                            # Step 3: Publish draft with status mappings
                            # Map old statuses to Open (initial EARL Workflow status) for all issue types
                            it_ids = [str(it["id"]) for it in jira_state.get("issue_types", [])]
                            # Old statuses that might have issues: Backlog (10037), Selected for Dev (10038)
                            old_status_ids = ["10037", "10038", "10073"]  # Backlog, Selected for Dev, To Do
                            open_status_id = "1"  # Open
                            mappings = []
                            for tid in it_ids:
                                for old_sid in old_status_ids:
                                    mappings.append({"issueTypeId": tid, "statusId": old_sid, "newStatusId": open_status_id})

                            publish_resp = client.post(
                                client.platform(f"/workflowscheme/{current_scheme_id}/draft/publish"),
                                json={"statusMappings": mappings},
                            )
                            applied.append({**change, "status": "applied", "scheme_id": current_scheme_id, "note": "draft published with status migration"})
                        else:
                            applied.append({**change, "status": "applied", "scheme_id": current_scheme_id, "note": "updated directly (no draft needed)"})
                    except Exception:
                        # No draft means the update applied directly (empty project or scheme not active)
                        applied.append({**change, "status": "applied", "scheme_id": current_scheme_id, "note": "updated existing scheme"})
                else:
                    # No existing scheme — try direct assignment (only works for empty projects)
                    scheme_id = None
                    for prev in applied:
                        if prev.get("section") == "workflow_scheme" and prev.get("action") == "create" and prev.get("created_id"):
                            scheme_id = prev["created_id"]
                            break
                    if not scheme_id:
                        for ws in jira_state.get("workflow_schemes", []):
                            if ws["name"] == target:
                                scheme_id = str(ws["id"])
                                break
                    if not scheme_id:
                        err_console.print(f"[red]Workflow scheme '{target}' not found.[/red]")
                        skipped.append({**change, "status": "error", "error": "scheme not found"})
                        continue
                    client.put(
                        client.platform("/workflowscheme/project"),
                        json={"projectId": jira_state["project_id"], "workflowSchemeId": scheme_id},
                    )
                    applied.append({**change, "status": "applied", "scheme_id": scheme_id})

        except Exception as e:
            err_console.print(f"[red]Failed: {desc} — {e}[/red]")
            skipped.append({**change, "status": "error", "error": str(e)})

    result_data: dict = {
        "applied": applied,
        "skipped": skipped,
        "summary": {"applied_count": len(applied), "skipped_count": len(skipped)},
    }
    output_result(result_data, format=format, json_fields=json_fields)


@manifest_app.command("export")
def export(
    project: ProjectOption = "EARL",
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="Write to file (default: stdout).")] = None,
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Export current Jira state as a manifest YAML.

    Snapshots live Jira configuration into a manifest file.
    Useful for bootstrapping, drift investigation, and backup.

    Examples:
        ebjira manifest export --project EARL
        ebjira manifest export --project EARL --output snapshot.yaml
    """
    jira_state = _fetch_jira_state(project)

    # Map Jira category keys to manifest category names
    category_map = {
        "new": "TODO",
        "indeterminate": "IN_PROGRESS",
        "done": "DONE",
        # Fallbacks for display names
        "To Do": "TODO",
        "In Progress": "IN_PROGRESS",
        "Done": "DONE",
    }

    manifest_dict: dict[str, Any] = {
        "version": "1",
        "project": {
            "key": project,
            "name": project,
            "type": "company-managed",
        },
        "issue_types": [
            {
                "name": it["name"],
                "hierarchy": it.get("hierarchy_level", 0),
                "description": it.get("description", ""),
            }
            for it in jira_state["issue_types"]
        ],
        "statuses": [
            {
                "name": s["name"],
                "category": category_map.get(s.get("category_key", ""), category_map.get(s.get("category", ""), "TODO")),
            }
            for s in jira_state["statuses"]
        ],
        "components": [
            {"name": c["name"], "description": c.get("description", "")}
            for c in jira_state["components"]
        ],
    }

    # Include workflow info if found
    if jira_state.get("workflows"):
        wf = jira_state["workflows"][0]
        manifest_dict["workflow"] = {
            "name": wf["name"],
            "description": wf.get("description", ""),
        }

    # Include workflow scheme
    if jira_state.get("workflow_schemes"):
        ws = jira_state["workflow_schemes"][0]
        manifest_dict["workflow_scheme"] = {
            "name": ws["name"],
            "default_workflow": ws.get("default_workflow", ""),
        }

    yaml_str = yaml.dump(manifest_dict, default_flow_style=False, sort_keys=False, allow_unicode=True)

    if output:
        Path(output).write_text(yaml_str)
        console.print(f"[green]Manifest exported to {output}[/green]")
        if format == Format.json:
            output_result({"file": output, "sections": list(manifest_dict.keys())}, format=format, json_fields=json_fields)
    else:
        if format == Format.json:
            output_result(manifest_dict, format=format, json_fields=json_fields)
        else:
            print(yaml_str)


@manifest_app.command("diagram")
def diagram(
    manifest_path: ManifestOption = None,
    output_dir: Annotated[str, typer.Option("--output-dir", "-o", help="Directory for generated diagrams.")] = "docs/diagrams",
    format: FormatOption = Format.json,
    json_fields: JsonOption = None,
) -> None:
    """Generate Mermaid diagrams from the manifest.

    Produces workflow state diagram, issue type hierarchy,
    component map, and agent operating model flowchart.

    Examples:
        ebjira manifest diagram
        ebjira manifest diagram --output-dir docs/diagrams/
        ebjira manifest diagram --manifest custom.yaml
    """
    m = load_manifest(manifest_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    generated: list[str] = []

    # 1. Workflow state diagram
    if m.workflow and m.statuses:
        lines = ["stateDiagram-v2"]
        # Initial state
        first_status = m.statuses[0].name if m.statuses else None
        if first_status:
            lines.append(f"    [*] --> {_mermaid_id(first_status)}")

        # State declarations with categories
        for sc in m.statuses:
            sid = _mermaid_id(sc.name)
            lines.append(f"    {sid}: {sc.name}")

        # Transitions
        for tr in m.workflow.transitions:
            from_id = _mermaid_id(tr.from_status)
            to_id = _mermaid_id(tr.to_status)
            lines.append(f"    {from_id} --> {to_id}")

        # Done state to end
        done_statuses = [s for s in m.statuses if s.category == "DONE"]
        for ds in done_statuses:
            lines.append(f"    {_mermaid_id(ds.name)} --> [*]")

        # Notes for categories
        lines.append("")
        lines.append("    note right of Prioritized")
        lines.append("        Category: TODO")
        lines.append("    end note")

        workflow_md = f"```mermaid\n{chr(10).join(lines)}\n```\n"
        (out / "workflow.md").write_text(workflow_md)
        generated.append("workflow.md")

    # 2. Issue types hierarchy
    if m.issue_types:
        lines = ["graph TD"]
        for it in m.issue_types:
            node_id = _mermaid_id(it.name)
            lines.append(f"    {node_id}[{it.name}<br/>hierarchy={it.hierarchy}]")

        # Epic -> standard types
        epics = [it for it in m.issue_types if it.hierarchy > 0]
        standards = [it for it in m.issue_types if it.hierarchy == 0]
        subtasks = [it for it in m.issue_types if it.hierarchy < 0]

        for epic in epics:
            for std in standards:
                lines.append(f"    {_mermaid_id(epic.name)} --> {_mermaid_id(std.name)}")

        for std in standards:
            for sub in subtasks:
                lines.append(f"    {_mermaid_id(std.name)} --> {_mermaid_id(sub.name)}")

        types_md = f"```mermaid\n{chr(10).join(lines)}\n```\n"
        (out / "issue-types.md").write_text(types_md)
        generated.append("issue-types.md")

    # 3. Components map
    if m.components:
        lines = ["graph LR"]
        for comp in m.components:
            cid = _mermaid_id(comp.name)
            short_desc = comp.description[:40] + "..." if len(comp.description) > 40 else comp.description
            lines.append(f"    {cid}[{comp.name}<br/>{short_desc}]")

        comps_md = f"```mermaid\n{chr(10).join(lines)}\n```\n"
        (out / "components.md").write_text(comps_md)
        generated.append("components.md")

    # 4. Agent operating model
    if m.agent and m.agent.name:
        lines = ["flowchart TD"]
        lines.append(f"    PICKUP[Pick up work<br/>{m.agent.name}]")
        lines.append("    DRAFT[Draft artifact]")
        lines.append("    REVIEW[Ready For Review]")
        lines.append("    BLOCKED[Blocked]")
        lines.append("    REWORK[Rework from feedback]")
        lines.append("    DONE[Done<br/>humans only]")
        lines.append("")
        lines.append("    PICKUP --> DRAFT")
        lines.append("    DRAFT --> REVIEW")
        lines.append("    DRAFT --> BLOCKED")
        lines.append("    REVIEW --> DONE")
        lines.append("    REVIEW --> REWORK")
        lines.append("    REWORK --> DRAFT")
        lines.append("    BLOCKED --> DRAFT")
        lines.append("")

        # Forbidden
        if m.agent.forbidden_transitions:
            for ft in m.agent.forbidden_transitions:
                lines.append(f"    %% FORBIDDEN: agent cannot transition to {ft.to_status}")

        # Labels
        if m.agent.labels_agent_adds:
            lines.append(f"    %% Agent adds labels: {', '.join(m.agent.labels_agent_adds)}")
        if m.agent.labels_agent_never_touches:
            lines.append(f"    %% Agent never touches: {', '.join(m.agent.labels_agent_never_touches)}")

        agent_md = f"```mermaid\n{chr(10).join(lines)}\n```\n"
        (out / "agent-flow.md").write_text(agent_md)
        generated.append("agent-flow.md")

    result_data: dict = {"output_dir": str(out), "generated": generated}

    if format == Format.table or format == Format.plain:
        for f_name in generated:
            console.print(f"[green]Generated:[/green] {out / f_name}")
    else:
        output_result(result_data, format=format, json_fields=json_fields)


# ── Helpers ──


def _mermaid_id(name: str) -> str:
    """Convert a name to a Mermaid-safe identifier."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)
