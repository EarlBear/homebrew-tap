"""Log commands — query agent_logs and agent_runs from Supabase.

View CLI usage logs, agent run summaries, errors, and performance stats.
Data is written by the CLI logging module (ebjira/logging.py) when
CLI_LOG_MODE=supabase is set.

Examples:
    ebjira log recent                    # Last 20 log entries
    ebjira log errors                    # Recent failures
    ebjira log run <run-id>              # All logs from a specific run
    ebjira log issue EARL-26             # All CLI calls for an issue
    ebjira log stats                     # Command performance stats
    ebjira log runs                      # Agent run summaries with branches + doc links
"""

from __future__ import annotations

import os
from typing import Annotated, Optional

import typer

from ebjira.output import Format, output_result

log_app = typer.Typer(no_args_is_help=True)

SUPABASE_URL = os.environ.get("SUPABASE_PROJECT_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def _query_supabase(table: str, params: str = "", limit: int = 50) -> list[dict]:
    """Query Supabase REST API."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        typer.echo('{"error": "MISSING_CONFIG", "message": "SUPABASE_PROJECT_URL and SUPABASE_SERVICE_ROLE_KEY required"}', err=True)
        raise typer.Exit(2)
    import httpx

    url = f"{SUPABASE_URL}/rest/v1/{table}?{params}&limit={limit}"
    resp = httpx.get(
        url,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        },
        timeout=10.0,
    )
    return resp.json() if resp.is_success else []


@log_app.command()
def recent(
    limit: Annotated[int, typer.Option("--limit", "-l", help="Number of entries.")] = 20,
    cli: Annotated[Optional[str], typer.Option(help="Filter by CLI name (ebjira/ebdocs).")] = None,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", "-j", help="Comma-separated fields.")] = None,
) -> None:
    """Show recent CLI log entries."""
    params = "order=timestamp.desc"
    if cli:
        params += f"&cli=eq.{cli}"
    data = _query_supabase("agent_logs", params, limit)
    output_result(data, format=format, json_fields=json_fields,
                  columns=["timestamp", "cli", "command", "exit_code", "duration_ms", "issue_key"])


@log_app.command()
def errors(
    limit: Annotated[int, typer.Option("--limit", "-l", help="Number of entries.")] = 20,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", "-j", help="Comma-separated fields.")] = None,
) -> None:
    """Show recent failed CLI commands."""
    data = _query_supabase("agent_logs", "exit_code=neq.0&order=timestamp.desc", limit)
    output_result(data, format=format, json_fields=json_fields,
                  columns=["timestamp", "cli", "command", "args", "exit_code", "error_message"])


@log_app.command()
def run(
    run_id: Annotated[str, typer.Argument(help="Run ID to filter by.")],
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", "-j", help="Comma-separated fields.")] = None,
) -> None:
    """Show all log entries from a specific agent run."""
    data = _query_supabase("agent_logs", f"run_id=eq.{run_id}&order=timestamp.asc", limit=500)
    output_result(data, format=format, json_fields=json_fields,
                  columns=["timestamp", "command", "exit_code", "duration_ms", "issue_key", "error_message"])


@log_app.command()
def issue(
    key: Annotated[str, typer.Argument(help="Issue key (e.g. EARL-26).")],
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", "-j", help="Comma-separated fields.")] = None,
) -> None:
    """Show all CLI calls related to a specific issue."""
    data = _query_supabase("agent_logs", f"issue_key=eq.{key}&order=timestamp.asc", limit=200)
    output_result(data, format=format, json_fields=json_fields,
                  columns=["timestamp", "cli", "command", "exit_code", "duration_ms", "run_id"])


@log_app.command()
def stats(
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", "-j", help="Comma-separated fields.")] = None,
) -> None:
    """Show command performance statistics (requires raw query via Supabase MCP)."""
    # Use simple aggregation via REST - get all logs and aggregate in Python
    data = _query_supabase("agent_logs", "order=timestamp.desc", limit=1000)
    if not data:
        output_result({"message": "No logs found"}, format=format)
        return

    from collections import defaultdict
    stats: dict = defaultdict(lambda: {"count": 0, "total_ms": 0, "errors": 0})
    for entry in data:
        cmd = entry.get("command", "unknown")
        stats[cmd]["count"] += 1
        stats[cmd]["total_ms"] += entry.get("duration_ms", 0)
        if entry.get("exit_code", 0) != 0:
            stats[cmd]["errors"] += 1

    result = []
    for cmd, s in sorted(stats.items(), key=lambda x: x[1]["total_ms"], reverse=True):
        result.append({
            "command": cmd,
            "count": s["count"],
            "avg_ms": round(s["total_ms"] / s["count"]) if s["count"] else 0,
            "total_ms": s["total_ms"],
            "errors": s["errors"],
            "error_rate": f"{s['errors']/s['count']*100:.0f}%" if s["count"] else "0%",
        })
    output_result(result, format=format, json_fields=json_fields,
                  columns=["command", "count", "avg_ms", "errors", "error_rate"])


@log_app.command()
def runs(
    limit: Annotated[int, typer.Option("--limit", "-l", help="Number of runs.")] = 10,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", "-j", help="Comma-separated fields.")] = None,
) -> None:
    """Show agent run summaries with branches, doc links, and costs."""
    data = _query_supabase("agent_runs", "order=run_date.desc", limit)
    output_result(data, format=format, json_fields=json_fields,
                  columns=["run_date", "status", "total_cost_usd", "issues_touched", "branches", "google_doc_url", "duration_minutes"])


@log_app.command()
def cost(
    days: Annotated[int, typer.Option("--days", "-d", help="Number of days to look back.")] = 7,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", "-j", help="Comma-separated fields.")] = None,
) -> None:
    """Show agent cost summary — total spend, cost per run, token usage.

    Examples:
        ebjira log cost              # Last 7 days
        ebjira log cost --days 30    # Last 30 days
    """
    data = _query_supabase("agent_runs", "order=run_date.desc", limit=days * 5)
    if not data:
        output_result({"message": "No agent runs found"}, format=format)
        return

    total_cost = sum(float(r.get("total_cost_usd") or 0) for r in data)
    total_input = sum(int(r.get("input_tokens") or 0) for r in data)
    total_output = sum(int(r.get("output_tokens") or 0) for r in data)
    total_cache = sum(int(r.get("cache_read_tokens") or 0) for r in data)
    total_runs = len(data)
    avg_cost = total_cost / total_runs if total_runs else 0
    total_issues = sum(len(r.get("issues_touched") or []) for r in data)

    summary = {
        "period_days": days,
        "total_runs": total_runs,
        "total_cost_usd": round(total_cost, 2),
        "avg_cost_per_run_usd": round(avg_cost, 2),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_cache_read_tokens": total_cache,
        "total_issues_touched": total_issues,
        "cost_per_issue_usd": round(total_cost / total_issues, 2) if total_issues else 0,
        "runs": [
            {
                "date": r.get("run_date"),
                "cost": float(r.get("total_cost_usd") or 0),
                "issues": len(r.get("issues_touched") or []),
                "model": r.get("model", ""),
            }
            for r in data
        ],
    }
    output_result(summary, format=format, json_fields=json_fields)
