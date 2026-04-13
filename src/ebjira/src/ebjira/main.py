"""EarlBear Jira CLI — agent-first Jira interface.

Usage:
    ebjira --help              Show all command groups
    ebjira <group> --help      Show commands in a group
    ebjira <group> <cmd> -h    Show command options and examples
    ebjira --help-json         Dump full command tree as JSON (for agents)
    ebjira --version           Show version
"""

from __future__ import annotations

import json
import sys
from typing import Optional

import typer

from ebjira import __version__
from ebjira.client import JiraError
from ebjira.output import output_error

app = typer.Typer(
    name="ebjira",
    help="Jira CLI for agents and humans.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)


def version_callback(value: bool) -> None:
    if value:
        print(json.dumps({"name": "ebjira", "version": __version__}))
        raise typer.Exit()


def help_json_callback(value: bool) -> None:
    """Dump the full command tree as JSON for programmatic discovery."""
    if value:
        tree = _build_command_tree(app)
        print(json.dumps(tree, indent=2))
        raise typer.Exit()


@app.callback()
def main_callback(
    version: Optional[bool] = typer.Option(
        None, "--version", "-V", callback=version_callback, is_eager=True,
        help="Show version.",
    ),
    help_json: Optional[bool] = typer.Option(
        None, "--help-json", callback=help_json_callback, is_eager=True,
        help="Dump full command tree as JSON (for agent introspection).",
        hidden=True,
    ),
) -> None:
    """EarlBear Jira CLI — agent-first Jira interface."""
    pass


def _build_command_tree(typer_app: typer.Typer) -> dict:
    """Build a JSON-serializable command tree from a Typer app."""
    # Get the underlying Click group
    click_app = typer.main.get_command(typer_app)
    return _click_to_dict(click_app)


def _click_to_dict(cmd) -> dict:
    """Recursively convert a Click command/group to a dict."""
    import click

    result: dict = {
        "name": cmd.name or "",
        "description": (cmd.help or "").strip().split("\n")[0],
    }

    if isinstance(cmd, click.Group):
        commands = {}
        for name in cmd.list_commands(click.Context(cmd)):
            sub = cmd.get_command(click.Context(cmd), name)
            if sub and not sub.hidden:
                commands[name] = _click_to_dict(sub)
        if commands:
            result["commands"] = commands
    else:
        # Leaf command — include params
        params = []
        for param in cmd.params:
            if isinstance(param, click.Option):
                if param.hidden or param.name == "help":
                    continue
                p: dict = {
                    "name": param.opts[0] if param.opts else param.name,
                    "type": param.type.name if hasattr(param.type, "name") else str(param.type),
                    "required": param.required,
                }
                if param.default is not None:
                    p["default"] = param.default
                if param.help:
                    p["help"] = param.help
                params.append(p)
            elif isinstance(param, click.Argument):
                params.append({
                    "name": param.name,
                    "type": param.type.name if hasattr(param.type, "name") else str(param.type),
                    "required": param.required,
                })
        if params:
            result["options"] = params

    return result


# ── discover command ──
from ebjira._discover import discover_command
app.command("discover")(discover_command)


# ── Register command groups ──
# Each command group is a separate module that exports a Typer sub-app.
# Import and register them here as they're built.

def _register_commands() -> None:
    """Import and register all command group sub-apps."""
    from ebjira.commands.attachment import attachment_app
    from ebjira.commands.board import board_app
    from ebjira.commands.bulk import bulk_app
    from ebjira.commands.cache import cache_app
    from ebjira.commands.component import component_app
    from ebjira.commands.log import log_app
    from ebjira.commands.dashboard import dashboard_app
    from ebjira.commands.epic import epic_app
    from ebjira.commands.field import field_app
    from ebjira.commands.filter import filter_app
    from ebjira.commands.issue import issue_app
    from ebjira.commands.issuelink import issuelink_app
    from ebjira.commands.issuetype import issuetype_app
    from ebjira.commands.label import label_app
    from ebjira.commands.model import model_app
    from ebjira.commands.priority import priority_app
    from ebjira.commands.project import project_app
    from ebjira.commands.report import report_app
    from ebjira.commands.resolution import resolution_app
    from ebjira.commands.server import server_app
    from ebjira.commands.sprint import sprint_app
    from ebjira.commands.status import status_app
    from ebjira.commands.user import user_app
    from ebjira.commands.workflow import workflow_app
    from ebjira.commands.workflowscheme import workflowscheme_app
    from ebjira.commands.worklog import worklog_app
    from ebjira.commands.issuetypescheme import issuetypescheme_app
    from ebjira.commands.manifest import manifest_app
    from ebjira.commands.seed import seed_app
    from ebjira.commands.dev import dev_app
    from ebjira.commands.sync import sync_app
    from ebjira.commands.lint import lint_app

    app.add_typer(issue_app, name="issue", help="Manage issues (create, view, update, search, transition)")
    app.add_typer(issuelink_app, name="issuelink", help="Manage issue links (create, delete, list types)")
    app.add_typer(issuetype_app, name="issuetype", help="Manage issue types (create, update, delete)")
    app.add_typer(project_app, name="project", help="Manage projects and their configuration")
    app.add_typer(epic_app, name="epic", help="View epics and their children.")
    app.add_typer(bulk_app, name="bulk", help="Bulk operations on issues (transition, update)")
    app.add_typer(component_app, name="component", help="Manage project components (list, create, update, delete)")
    app.add_typer(board_app, name="board", help="View boards and backlogs")
    app.add_typer(sprint_app, name="sprint", help="Manage sprints (create, update, move issues)")
    app.add_typer(field_app, name="field", help="Manage fields and field options")
    app.add_typer(filter_app, name="filter", help="Manage saved filters")
    app.add_typer(attachment_app, name="attachment", help="Manage file attachments.")
    app.add_typer(label_app, name="label", help="View labels")
    app.add_typer(model_app, name="model", help="Analyze and evolve the domain model (types, statuses, components)")
    app.add_typer(priority_app, name="priority", help="View priorities")
    app.add_typer(resolution_app, name="resolution", help="View resolutions")
    app.add_typer(report_app, name="report", help="Project reports (type swimlanes, epic health, AI dashboard)")
    app.add_typer(user_app, name="user", help="Search and view users")
    app.add_typer(server_app, name="server", help="Server info and health check")
    app.add_typer(workflow_app, name="workflow", help="View workflows and statuses")
    app.add_typer(status_app, name="status", help="Manage statuses")
    app.add_typer(dashboard_app, name="dashboard", help="Manage dashboards")
    app.add_typer(worklog_app, name="worklog", help="Manage time tracking worklogs")
    app.add_typer(cache_app, name="cache", help="Manage local Jira ID cache (.jira-cache.json)")
    app.add_typer(log_app, name="log", help="Query agent CLI usage logs and run summaries")
    app.add_typer(workflowscheme_app, name="workflowscheme", help="Manage workflow schemes (list, create, assign to project)")
    app.add_typer(issuetypescheme_app, name="issuetypescheme", help="Manage issue type schemes (list, create, assign to project)")
    app.add_typer(manifest_app, name="manifest", help="Declarative Jira project configuration (diff, apply, export, diagram)")
    app.add_typer(seed_app, name="seed", help="Declarative issue management (export, diff, apply as hierarchical YAML)")
    app.add_typer(dev_app, name="dev", help="Issue-aware local development (start, status, finish, commit)")
    app.add_typer(sync_app, name="sync", help="Bidirectional YAML sync (pull, push, diff, snapshots)")
    app.add_typer(lint_app, name="lint", help="Lint local issue YAML for structure and content gaps")


_register_commands()


def main() -> None:
    """CLI entry point."""
    import sys
    import time as _time

    from ebjira.logging import CommandTimer, is_enabled, log_command

    # Extract command info from argv for logging
    args = sys.argv[1:]
    cmd_str = " ".join(args[:3]) if args else "help"

    start = _time.monotonic()
    exit_code = 0
    error_msg = None

    try:
        app()
    except JiraError as e:
        exit_code = 1
        error_msg = e.message
        output_error(
            error=f"JIRA_{e.status_code}",
            message=e.message,
            status=1,
        )
    except KeyboardInterrupt:
        exit_code = 130
        raise SystemExit(130)
    except SystemExit as e:
        exit_code = e.code if isinstance(e.code, int) else 1
        raise
    finally:
        if is_enabled():
            duration_ms = int((_time.monotonic() - start) * 1000)
            # Extract issue key from args if present
            issue_key = None
            for i, a in enumerate(args):
                if a.startswith("EARL-"):
                    issue_key = a
                    break
            log_command(
                command=cmd_str,
                args=" ".join(args),
                exit_code=exit_code,
                duration_ms=duration_ms,
                error_message=error_msg,
                issue_key=issue_key,
            )
