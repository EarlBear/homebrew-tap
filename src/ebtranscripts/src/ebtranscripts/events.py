"""Build a redacted event append-log from an already-safe ExtractResult.

The Drive corpus is an append-log of *events of interest* — tool calls, subagent runs, skill
uses, and a session metrics snapshot — NOT the full transcript. Crucially, every event is
CONSTRUCTED from the derived records the extractor already produced (tool_calls / subagent_runs
/ skill_uses), which were themselves built from a safe-field allowlist with coarse, redacted
summaries. So this module never touches raw transcript text — it is a *serialization of
already-safe fields*, which is why it carries the same structural guarantee as the derived
record, at event granularity.

This is what replaced the full scrubbed session.jsonl on the Drive path: shipping the whole
transcript body made a regex layer the load-bearing defense against arbitrary PII; an
allowlist-built event log restores the structural guarantee, so the regex/PII patterns are back
to being a light backstop on the couple of short excerpts rather than the primary control. See
docs/drive-consolidation-design.md §2c.

Output: newline-delimited JSON (NDJSON), one event per line, time-ordered, ending with a
metrics_snapshot. Append-only by construction, so it fits the byte-offset delta-sync model
(only new event lines sync on the next run).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from .models import EXTRACTOR_VERSION, ExtractResult

EVENTS_VERSION = "1.1.0"  # 1.1: cumulative aggregates stamped on each event


def _event(kind: str, ts: str | None, **fields) -> dict:
    e = {"kind": kind}
    if ts is not None:
        e["ts"] = ts
    e.update(fields)
    return e


# Which cumulative COUNT each event kind increments.
_COUNTS_FOR = {
    "tool_call": "tool_calls",
    "subagent_run": "subagent_runs",
    "skill_use": "skill_uses",
}


def _token_cum_at(ts: str | None, timeline: list) -> tuple[int, int, float]:
    """Cumulative (input, output, cost) from the latest turn checkpoint with ts <= `ts`.

    Tokens/cost are recorded per assistant turn, not per tool call, so the correct "as of this
    event" value is the most recent turn checkpoint at or before the event — never a fabricated
    per-tool split. If the event predates any turn (or has no ts), totals are zero.
    """
    best = (0, 0, 0.0)
    for cp in timeline:  # timeline is in turn order (non-decreasing ts)
        if ts is None or cp.ts is None or cp.ts <= ts:
            best = (cp.cum_input_tokens, cp.cum_output_tokens, cp.cum_cost_usd)
        else:
            break
    return best


def _stamp_cumulative(events: list[dict], timeline: list) -> None:
    """Add a `cum` block to each event: running counts (exact) + token/cost (per-turn real)."""
    counts = {"tool_calls": 0, "subagent_runs": 0, "skill_uses": 0, "errors": 0}
    for e in events:
        key = _COUNTS_FOR.get(e["kind"])
        if key:
            counts[key] += 1
        if e.get("is_error"):
            counts["errors"] += 1
        cum_in, cum_out, cum_cost = _token_cum_at(e.get("ts"), timeline)
        e["cum"] = {
            "tool_calls": counts["tool_calls"],
            "subagent_runs": counts["subagent_runs"],
            "skill_uses": counts["skill_uses"],
            "errors": counts["errors"],
            "input_tokens": cum_in,
            "output_tokens": cum_out,
            "est_cost_usd": round(cum_cost, 6),
        }


def build_events(result: ExtractResult) -> list[dict]:
    """Return the ordered list of event dicts for a session (allowlist-built, never raw)."""
    s = result.session
    events: list[dict] = [
        _event(
            "session_start", s.started_at,
            session_id=s.session_id,
            project_slug=s.project_slug,
            stage=s.stage,
            model=s.model,
            machine_id=s.machine_id,
            machine=s.machine,
        )
    ]

    # Tool calls — tool name + coarse (already-redacted) input summary + byte sizes, never
    # the payload. is_error/duration are safe scalars.
    for tc in result.tool_calls:
        events.append(_event(
            "tool_call", tc.ts,
            tool=tc.tool_name,
            tool_use_id=tc.tool_use_id,
            input_summary=tc.input_summary,
            input_bytes=tc.input_bytes,
            result_bytes=tc.result_bytes,
            is_error=tc.is_error,
            is_sidechain=tc.is_sidechain,
            duration_ms=tc.duration_ms,
        ))

    for sr in result.subagent_runs:
        events.append(_event(
            "subagent_run", sr.started_at,
            agent=sr.agent_name,
            task_tool_use_id=sr.task_tool_use_id,
            description_excerpt=sr.description_excerpt,  # already redacted, length-capped
            tool_call_count=sr.tool_call_count,
            input_tokens=sr.input_tokens,
            output_tokens=sr.output_tokens,
            success=sr.success,
        ))

    for su in result.skill_uses:
        events.append(_event(
            "skill_use", su.ts,
            skill=su.skill_name,
            source=su.source,
            args_excerpt=su.args_excerpt,  # currently always "" from the extractor
        ))

    # Sort by timestamp so the log is time-ordered; events with no ts keep their relative order
    # (Python sort is stable). None sorts first, which is fine for the session_start anchor.
    events.sort(key=lambda e: (e.get("ts") is not None, e.get("ts") or ""))

    # Stamp each event with cumulative aggregates AS OF that event, so "cost up to event N" is
    # answerable without distributing a session total. COUNTS are exact — we accumulate as we
    # walk the time-ordered events. TOKENS/COST come from the real per-turn token_timeline: for
    # each event we use the latest checkpoint whose ts <= the event's ts (tokens are recorded on
    # assistant turns, not on tool calls, so this is the correct "as of now" value, never a
    # fabricated per-tool split).
    _stamp_cumulative(events, result.token_timeline)

    # Final metrics snapshot — the derived counts as of session end. All safe aggregates.
    events.append(_event(
        "metrics_snapshot", s.ended_at,
        session_id=s.session_id,
        duration_seconds=s.duration_seconds,
        num_turns=s.num_turns,
        tool_call_count=s.tool_call_count,
        subagent_count=s.subagent_count,
        skill_use_count=s.skill_use_count,
        input_tokens=s.input_tokens,
        output_tokens=s.output_tokens,
        est_cost_usd=s.est_cost_usd,
        error_count=s.error_count,
        extractor_version=EXTRACTOR_VERSION,
        events_version=EVENTS_VERSION,
    ))
    return events


def build_event_log(result: ExtractResult) -> str:
    """NDJSON event append-log for a session — one JSON object per line, time-ordered."""
    return "\n".join(json.dumps(e) for e in build_events(result)) + "\n"


def _split_body_footer(events: list[dict]) -> tuple[list[dict], dict | None]:
    """Split into the appendable body and the trailing metrics_snapshot footer.

    The snapshot is a moving "current totals" line that is regenerated every sync; the body
    (session_start + tool/subagent/skill events with their cumulatives) is append-only and
    stable once written.
    """
    if events and events[-1].get("kind") == "metrics_snapshot":
        return events[:-1], events[-1]
    return events, None


@dataclass
class AppendPlan:
    """How to update an existing events.ndjson for a re-synced session."""

    rewrite: bool          # True = full recompute (rewind/divergence); False = append tail
    append_lines: list[str]  # the NEW body lines to append (empty if rewrite)
    full_text: str         # the complete file to write when rewrite is True
    footer_line: str       # the (regenerated) metrics_snapshot line, always rewritten
    new_body_count: int    # number of body events after this sync


def plan_incremental_append(result: ExtractResult, existing_text: str | None) -> AppendPlan:
    """Compute how to update events.ndjson for `result` given its current on-disk `existing_text`.

    Append case: the previously-written body events are a prefix of the freshly-built body
    (the session grew append-only) — we append only the new body tail, then rewrite the footer.
    Rewrite case: the bodies diverge (an in-place /rewind rewrote earlier events, or there is no
    existing file / it's unparseable) — we recompute and rewrite the whole log. Correctness wins
    over append efficiency: a rewind must never append new cumulatives onto stale lines.
    """
    new_events = build_events(result)
    new_body, new_footer = _split_body_footer(new_events)
    footer_line = json.dumps(new_footer) if new_footer is not None else ""
    full_text = "\n".join(json.dumps(e) for e in new_events) + "\n"

    def _rewrite() -> AppendPlan:
        return AppendPlan(True, [], full_text, footer_line, len(new_body))

    if not existing_text or not existing_text.strip():
        return _rewrite()

    # Parse the existing file's body (drop its trailing snapshot footer).
    try:
        old_events = [json.loads(ln) for ln in existing_text.splitlines() if ln.strip()]
    except json.JSONDecodeError:
        return _rewrite()
    old_body, _ = _split_body_footer(old_events)

    # The old body must be an exact prefix of the new body for a safe append.
    if len(old_body) > len(new_body):
        return _rewrite()  # shrank — a rewind removed events
    for a, b in zip(old_body, new_body):
        if a != b:
            return _rewrite()  # an earlier event changed — rewind rewrote history

    append_body = [json.dumps(e) for e in new_body[len(old_body):]]
    return AppendPlan(False, append_body, full_text, footer_line, len(new_body))
