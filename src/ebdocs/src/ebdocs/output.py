"""Output formatting for ebdocs CLI.

Supports three modes:
- json (default): structured JSON to stdout
- table: Rich table for humans
- plain: one value per line, for piping

Errors always go to stderr as JSON.
"""

from __future__ import annotations

import json
import sys
from enum import Enum
from typing import Any

from rich.console import Console
from rich.table import Table

console = Console()
err_console = Console(stderr=True)


class Format(str, Enum):
    json = "json"
    table = "table"
    plain = "plain"


def _pick_fields(data: Any, fields: list[str]) -> Any:
    """Filter dicts to only include specified fields."""
    if isinstance(data, list):
        return [_pick_fields(item, fields) for item in data]
    if isinstance(data, dict):
        return {k: v for k, v in data.items() if k in fields}
    return data


def _flatten_value(value: Any) -> str:
    """Flatten a value for table/plain display."""
    if value is None:
        return ""
    if isinstance(value, dict):
        for key in ("name", "displayName", "value", "emailAddress", "id"):
            if key in value:
                return str(value[key])
        return json.dumps(value)
    if isinstance(value, list):
        return ", ".join(_flatten_value(item) for item in value)
    return str(value)


def output_result(
    data: Any,
    format: Format = Format.json,
    json_fields: str | None = None,
    columns: list[str] | None = None,
) -> None:
    """Output data in the requested format.

    Args:
        data: The data to output (dict, list of dicts, or primitive).
        format: Output format.
        json_fields: Comma-separated field names for --json filtering.
        columns: Column names for table display. If None, auto-detected from data.
    """
    if json_fields:
        fields = [f.strip() for f in json_fields.split(",")]
        data = _pick_fields(data, fields)

    if format == Format.json:
        _output_json(data)
    elif format == Format.table:
        _output_table(data, columns)
    elif format == Format.plain:
        _output_plain(data)


def _output_json(data: Any) -> None:
    """Output as formatted JSON."""
    print(json.dumps(data, indent=2, default=str))


def _output_table(data: Any, columns: list[str] | None = None) -> None:
    """Output as a Rich table."""
    if isinstance(data, dict):
        table = Table(show_header=True)
        table.add_column("Field", style="bold")
        table.add_column("Value")
        for key, value in data.items():
            table.add_row(key, _flatten_value(value))
        console.print(table)
        return

    if not isinstance(data, list) or not data:
        console.print(str(data))
        return

    if columns is None:
        if isinstance(data[0], dict):
            columns = list(data[0].keys())
        else:
            print("\n".join(str(item) for item in data))
            return

    table = Table(show_header=True)
    for col in columns:
        table.add_column(col.upper(), style="bold" if col in ("id", "documentId") else None)

    for item in data:
        if isinstance(item, dict):
            row = [_flatten_value(item.get(col, "")) for col in columns]
            table.add_row(*row)

    console.print(table)


def _output_plain(data: Any) -> None:
    """Output one value per line, for piping."""
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                values = list(item.values())
                print(_flatten_value(values[0]) if values else "")
            else:
                print(_flatten_value(item))
    elif isinstance(data, dict):
        for key, value in data.items():
            print(f"{key}\t{_flatten_value(value)}")
    else:
        print(str(data))


def output_error(error: str, message: str, status: int = 1) -> None:
    """Output an error as JSON to stderr and exit."""
    err_data = {"error": error, "message": message, "status": status}
    print(json.dumps(err_data), file=sys.stderr)
    raise SystemExit(status)
