"""Usage logging for ebshop CLI.

Records every command invocation to Supabase and/or a local JSONL file.
Off by default — activated via CLI_LOG_MODE env var.

Modes (comma-separated for multiple):
  CLI_LOG_MODE=supabase       → writes to Supabase agent_logs table
  CLI_LOG_MODE=jsonl          → appends to CLI_LOG_FILE (default: .cli-log.jsonl)
  CLI_LOG_MODE=supabase,jsonl → both (recommended for agent: structured + verbose)
  (unset)                     → logging disabled (default for human developers)

Required env vars for supabase mode:
  SUPABASE_PROJECT_URL, SUPABASE_SERVICE_ROLE_KEY

Optional env vars:
  CLI_RUN_ID   — groups all logs from a single agent run
  CLI_LOG_FILE — path for jsonl mode (default: .cli-log.jsonl)

The agent uploads the JSONL file to Google Drive at check-out via:
  ebdocs export upload --file .cli-log.jsonl --folder <LOGS_FOLDER_ID>
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any

LOG_MODE = os.environ.get("CLI_LOG_MODE", "")
LOG_URL = os.environ.get("SUPABASE_PROJECT_URL", "")
LOG_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
RUN_ID = os.environ.get("CLI_RUN_ID", "")
CLI_NAME = "ebshop"
# Naming convention: <run-id>-<cli>.jsonl (e.g. run-2026-03-29-0800-ebshop.jsonl)
_default_log_file = f"{RUN_ID}-{CLI_NAME}.jsonl" if RUN_ID else f".{CLI_NAME}-log.jsonl"
LOG_FILE = os.environ.get("CLI_LOG_FILE", _default_log_file)


def _modes() -> set[str]:
    return {m.strip() for m in LOG_MODE.split(",") if m.strip()}


def is_enabled() -> bool:
    return bool(_modes())


def log_command(
    command: str,
    args: str = "",
    exit_code: int = 0,
    response_size: int = 0,
    duration_ms: int = 0,
    error_message: str | None = None,
    issue_key: str | None = None,
) -> None:
    """Log a single CLI command invocation."""
    if not is_enabled():
        return

    # Redact sensitive args
    safe_args = _redact(args)

    entry = {
        "run_id": RUN_ID or None,
        "cli": CLI_NAME,
        "command": command,
        "args": safe_args,
        "exit_code": exit_code,
        "response_size": response_size,
        "duration_ms": duration_ms,
        "error_message": error_message,
        "issue_key": issue_key,
    }

    modes = _modes()
    if "supabase" in modes:
        _write_supabase(entry)
    if "jsonl" in modes:
        _write_jsonl(entry)


def _write_supabase(entry: dict) -> None:
    """Write log entry to Supabase agent_logs table."""
    if not LOG_URL or not LOG_KEY:
        return
    try:
        import httpx

        httpx.post(
            f"{LOG_URL}/rest/v1/agent_logs",
            headers={
                "apikey": LOG_KEY,
                "Authorization": f"Bearer {LOG_KEY}",
                "Content-Type": "application/json",
            },
            json=entry,
            timeout=5.0,
        )
    except Exception:
        pass  # Logging should never crash the CLI


def _write_jsonl(entry: dict) -> None:
    """Append log entry to a JSONL file."""
    try:
        entry["timestamp"] = datetime.now(timezone.utc).isoformat()
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except Exception:
        pass


def _redact(args: str) -> str:
    """Remove sensitive values from args string."""
    redact_patterns = ["token", "password", "secret", "key", "apikey"]
    parts = args.split()
    redacted = []
    skip_next = False
    for part in parts:
        if skip_next:
            redacted.append("***")
            skip_next = False
            continue
        lower = part.lower().replace("-", "").replace("_", "")
        if any(p in lower for p in redact_patterns):
            skip_next = True
        redacted.append(part)
    return " ".join(redacted)


class CommandTimer:
    """Context manager that times a command and logs it."""

    def __init__(self, command: str, args: str = "", issue_key: str | None = None):
        self.command = command
        self.args = args
        self.issue_key = issue_key
        self.start = 0.0
        self.exit_code = 0
        self.response_size = 0
        self.error_message: str | None = None

    def __enter__(self) -> "CommandTimer":
        self.start = time.monotonic()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        duration_ms = int((time.monotonic() - self.start) * 1000)
        if exc_val:
            self.exit_code = 1
            self.error_message = str(exc_val)[:500]
        log_command(
            command=self.command,
            args=self.args,
            exit_code=self.exit_code,
            response_size=self.response_size,
            duration_ms=duration_ms,
            error_message=self.error_message,
            issue_key=self.issue_key,
        )
