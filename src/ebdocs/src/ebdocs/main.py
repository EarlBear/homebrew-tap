"""EarlBear Google Docs CLI — agent-first Google Docs interface.

Usage:
    ebdocs --help              Show all command groups
    ebdocs <group> --help      Show commands in a group
    ebdocs <group> <cmd> -h    Show command options and examples
    ebdocs --help-json         Dump full command tree as JSON (for agents)
    ebdocs --version           Show version
"""

from __future__ import annotations

import json
import os
import re
from typing import Optional

import typer

# Strip googleapis/google.com from NO_PROXY before any library reads it.
# In proxied environments (Anthropic cloud), NO_PROXY=*.googleapis.com
# causes httplib2 to bypass the proxy and fail (no local DNS).
# httpx-based CLIs (ebjira, ebshop) handle this fine — only httplib2 breaks.
# We strip it here at startup so httplib2 never sees it.
def _strip_google_from_no_proxy():
    for var in ("NO_PROXY", "no_proxy"):
        val = os.environ.get(var)
        if val and "google" in val.lower():
            cleaned = ",".join(
                entry.strip() for entry in val.split(",")
                if not re.search(r"google", entry, re.IGNORECASE)
            )
            if cleaned:
                os.environ[var] = cleaned
            else:
                os.environ.pop(var, None)

_strip_google_from_no_proxy()

from ebdocs import __version__
from ebdocs.client import DocsError
from ebdocs.output import output_error

app = typer.Typer(
    name="ebdocs",
    help="Google Docs CLI for EarlBear agents and humans.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)


def version_callback(value: bool) -> None:
    if value:
        print(json.dumps({"name": "ebdocs", "version": __version__}))
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
    """EarlBear Google Docs CLI — agent-first Google Docs interface."""
    pass


def _build_command_tree(typer_app: typer.Typer) -> dict:
    """Build a JSON-serializable command tree from a Typer app."""
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
from ebdocs._discover import discover_command
app.command("discover")(discover_command)


# ── Register command groups ──

def _register_commands() -> None:
    """Import and register all command group sub-apps."""
    from ebdocs.commands.doc import app as doc_app
    from ebdocs.commands.share import app as share_app
    from ebdocs.commands.comment import app as comment_app
    from ebdocs.commands.export import app as export_app
    from ebdocs.commands.link import app as link_app
    from ebdocs.commands.links import app as links_app
    from ebdocs.commands.auth import app as auth_app

    app.add_typer(doc_app, name="doc", help="Create, read, write, and manage Google Docs")
    app.add_typer(share_app, name="share", help="Manage document sharing and permissions")
    app.add_typer(comment_app, name="comment", help="Add, list, and resolve comments")
    app.add_typer(export_app, name="export", help="Export documents to various formats")
    app.add_typer(link_app, name="link", help="Manage links between docs and external systems")
    app.add_typer(links_app, name="links", help="Manage KB back-references (refs:, specifies:) and per-subtree indexes")
    app.add_typer(auth_app, name="auth", help="Verify credentials and service account access")

    from ebdocs.commands.drive import drive_app
    app.add_typer(drive_app, name="drive", help="Upload files to Google Drive")

    from ebdocs.commands.sync import sync_app
    app.add_typer(sync_app, name="sync", help="Bidirectional YAML+MD sync with Google Drive (pull, push, diff, create, link)")


_register_commands()


def main() -> None:
    """CLI entry point."""
    import sys
    import time as _time

    from ebdocs.logging import is_enabled, log_command

    # Extract command info from argv for logging
    args = sys.argv[1:]
    cmd_str = " ".join(args[:3]) if args else "help"

    start = _time.monotonic()
    exit_code = 0
    error_msg = None

    try:
        app()
    except DocsError as e:
        exit_code = 1
        error_msg = e.message
        output_error(
            error=f"GOOGLE_{e.status_code}",
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
            # Extract doc ID from args if present
            doc_id = None
            for a in args:
                if len(a) > 20 and not a.startswith("-"):
                    doc_id = a
                    break
            log_command(
                command=cmd_str,
                args=" ".join(args),
                exit_code=exit_code,
                duration_ms=duration_ms,
                error_message=error_msg,
                issue_key=doc_id,
            )
