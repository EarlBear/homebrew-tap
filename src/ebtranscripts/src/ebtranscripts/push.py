"""Upsert normalized (derived, sanitized) records to the telemetry DB.

Two backends behind one interface — chosen by config, never by the caller:
  - SupabasePusher: PostgREST + service-role key (production).
  - LocalPgPusher: direct SQL via psycopg to a local Postgres (dev/demo, docker-compose).

Both upsert only DERIVED records (never raw content) and are idempotent (upsert on each
table's primary key), so re-running a sync produces identical rows. The two paths run the
*same* refresh_cc_marts() (standard SQL), so metrics are identical in both.
"""

from __future__ import annotations

from typing import Any, Protocol

from .models import ExtractResult

TABLE_CONFLICT = {
    "cc_sessions": "session_id",
    "cc_tool_calls": "session_id,tool_use_id",
    "cc_subagent_runs": "session_id,task_tool_use_id",
    "cc_skill_uses": "session_id,msg_uuid",
    "cc_events": "session_id,seq",
}

# The cc_events columns a loaded event row may carry (must match migration 006). Extra keys in
# an event dict are dropped; missing ones default in the DB.
_EVENT_COLS = (
    "session_id", "seq", "kind", "ts", "tool", "agent", "skill", "is_error",
    "input_bytes", "result_bytes", "cum_tool_calls", "cum_subagent_runs",
    "cum_skill_uses", "cum_errors", "cum_input_tokens", "cum_output_tokens",
    "cum_est_cost_usd", "machine_id", "machine",
)


class Pusher(Protocol):
    def push(self, result: ExtractResult) -> dict[str, int]: ...
    def push_events(self, rows: list[dict[str, Any]]) -> int: ...
    def refresh_marts(self) -> None: ...
    def set_published(self, session_id: str, transcript_url: str) -> None: ...


def events_to_rows(
    session_id: str, events: list[dict[str, Any]],
    machine_id: str | None = None, machine: str | None = None,
) -> list[dict[str, Any]]:
    """Map parsed event-log dicts (from events.ndjson) into cc_events upsert rows.

    `seq` is the 0-based line order. The event's `cum` block is flattened to cum_* columns.
    Only the columns cc_events knows about are kept; everything else (e.g. tool_use_id,
    description_excerpt) stays in the file corpus, not the table.
    """
    rows: list[dict[str, Any]] = []
    for seq, e in enumerate(events):
        cum = e.get("cum", {}) or {}
        # The metrics_snapshot has no `cum` block — it carries the session totals directly. Map
        # them into cum_* so the cost curve stays monotonic through the final row.
        if e.get("kind") == "metrics_snapshot":
            cum = {
                "tool_calls": e.get("tool_call_count", 0),
                "subagent_runs": e.get("subagent_count", 0),
                "skill_uses": e.get("skill_use_count", 0),
                "errors": e.get("error_count", 0),
                "input_tokens": e.get("input_tokens", 0),
                "output_tokens": e.get("output_tokens", 0),
                "est_cost_usd": e.get("est_cost_usd", 0),
            }
        row = {
            "session_id": session_id,
            "seq": seq,
            "kind": e.get("kind", ""),
            "ts": e.get("ts"),
            "tool": e.get("tool"),
            "agent": e.get("agent"),
            "skill": e.get("skill"),
            "is_error": bool(e.get("is_error", False)),
            "input_bytes": int(e.get("input_bytes", 0) or 0),
            "result_bytes": int(e.get("result_bytes", 0) or 0),
            "cum_tool_calls": int(cum.get("tool_calls", 0) or 0),
            "cum_subagent_runs": int(cum.get("subagent_runs", 0) or 0),
            "cum_skill_uses": int(cum.get("skill_uses", 0) or 0),
            "cum_errors": int(cum.get("errors", 0) or 0),
            "cum_input_tokens": int(cum.get("input_tokens", 0) or 0),
            "cum_output_tokens": int(cum.get("output_tokens", 0) or 0),
            "cum_est_cost_usd": float(cum.get("est_cost_usd", 0) or 0),
            # Read the machine id from the event dict (events.py emits machine_id); fall back to the
            # old employee_id key for any pre-rename events.ndjson still in the corpus, then the arg.
            "machine_id": e.get("machine_id", e.get("employee_id", machine_id)),
            "machine": e.get("machine", machine),
        }
        rows.append({k: row[k] for k in _EVENT_COLS})
    return rows


def make_pusher(*, supabase_url: str, supabase_key: str, local_db_url: str) -> Pusher:
    """Pick the backend: Supabase if configured, else local Postgres."""
    if supabase_url and supabase_key:
        return SupabasePusher(supabase_url, supabase_key)
    if local_db_url:
        return LocalPgPusher(local_db_url)
    raise RuntimeError(
        "No push target: set SUPABASE_PROJECT_URL/SUPABASE_SERVICE_ROLE_KEY, or EBT_LOCAL_DB_URL."
    )


def _rows(result: ExtractResult) -> dict[str, list[dict[str, Any]]]:
    return {
        "cc_sessions": [result.session.model_dump()],
        "cc_tool_calls": [r.model_dump() for r in result.tool_calls],
        "cc_subagent_runs": [r.model_dump() for r in result.subagent_runs],
        "cc_skill_uses": [r.model_dump() for r in result.skill_uses],
    }


class SupabasePusher:
    def __init__(self, url: str, key: str):
        self.url = url.rstrip("/")
        self.key = key

    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        }

    def _upsert(self, table: str, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        import httpx

        resp = httpx.post(
            f"{self.url}/rest/v1/{table}",
            headers=self._headers(),
            params={"on_conflict": TABLE_CONFLICT[table]},
            json=rows,
            timeout=30.0,
        )
        resp.raise_for_status()
        return len(rows)

    def push(self, result: ExtractResult) -> dict[str, int]:
        return {t: self._upsert(t, rows) for t, rows in _rows(result).items()}

    def push_events(self, rows: list[dict[str, Any]]) -> int:
        return self._upsert("cc_events", rows)

    def refresh_marts(self) -> None:
        import httpx

        resp = httpx.post(
            f"{self.url}/rest/v1/rpc/refresh_cc_marts",
            headers=self._headers(),
            json={},
            timeout=30.0,
        )
        resp.raise_for_status()

    def set_published(self, session_id: str, transcript_url: str) -> None:
        import httpx

        resp = httpx.patch(
            f"{self.url}/rest/v1/cc_sessions",
            headers=self._headers(),
            params={"session_id": f"eq.{session_id}"},
            json={"is_published": True, "transcript_url": transcript_url},
            timeout=30.0,
        )
        resp.raise_for_status()


class LocalPgPusher:
    """Direct-SQL upsert to a local Postgres (the docker-compose local mode)."""

    def __init__(self, dsn: str):
        self.dsn = dsn

    def _connect(self):
        import psycopg  # imported lazily so the CLI works without psycopg unless local mode is used

        return psycopg.connect(self.dsn)

    def _upsert(self, cur, table: str, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        cols = list(rows[0].keys())
        conflict_cols = TABLE_CONFLICT[table].split(",")
        updates = [c for c in cols if c not in conflict_cols]
        collist = ", ".join(cols)
        placeholders = ", ".join(f"%({c})s" for c in cols)
        conflict = ", ".join(conflict_cols)
        set_clause = ", ".join(f"{c} = excluded.{c}" for c in updates) or (
            f"{conflict_cols[0]} = excluded.{conflict_cols[0]}"
        )
        sql = (
            f"insert into public.{table} ({collist}) values ({placeholders}) "
            f"on conflict ({conflict}) do update set {set_clause}"
        )
        cur.executemany(sql, rows)
        return len(rows)

    def push(self, result: ExtractResult) -> dict[str, int]:
        counts: dict[str, int] = {}
        with self._connect() as conn, conn.cursor() as cur:
            for table, rows in _rows(result).items():
                counts[table] = self._upsert(cur, table, rows)
            conn.commit()
        return counts

    def push_events(self, rows: list[dict[str, Any]]) -> int:
        with self._connect() as conn, conn.cursor() as cur:
            n = self._upsert(cur, "cc_events", rows)
            conn.commit()
        return n

    def refresh_marts(self) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("select public.refresh_cc_marts()")
            conn.commit()

    def set_published(self, session_id: str, transcript_url: str) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "update public.cc_sessions set is_published = true, transcript_url = %s "
                "where session_id = %s",
                (transcript_url, session_id),
            )
            conn.commit()
