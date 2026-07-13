"""Turn parsed JSONL lines into normalized, sanitized telemetry records.

Records are *constructed* from a safe-field allowlist — we never copy a raw content
block. The only free-text that survives is two bounded, redacted excerpts (the session's
first prompt and each tool call's coarse input summary), plus redacted subagent/skill
descriptions. File bodies and full prompts never enter a record.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from .models import (
    ExtractResult,
    SessionRecord,
    SkillUseRecord,
    SubagentRunRecord,
    TokenCheckpoint,
    ToolCallRecord,
)
from .parser import parse_lines
from .pricing import estimate_cost
from .sanitizer import redact
from .stages import resolve_stage

EXCERPT_MAX = 280
SUMMARY_MAX = 200


def _iso_to_dt(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _coarse_input_summary(tool_name: str, tool_input: dict[str, Any]) -> str:
    """A deliberately shallow, redacted description of a tool call — never the payload.

    Command word, file basename, or subagent/skill name only.
    """
    parts: list[str] = []
    command = tool_input.get("command")
    if isinstance(command, str) and command.strip():
        parts.append(command.strip().split()[0])
    for key in ("file_path", "path", "notebook_path"):
        val = tool_input.get(key)
        if isinstance(val, str) and val:
            parts.append(os.path.basename(val))
            break
    if "url" in tool_input and isinstance(tool_input["url"], str):
        parts.append("url")
    if "subagent_type" in tool_input:
        parts.append(str(tool_input["subagent_type"]))
    if "skill" in tool_input:
        parts.append(str(tool_input["skill"]))
    summary = " ".join(p for p in parts if p) or tool_name
    return redact(summary)[:SUMMARY_MAX]


def _block_bytes(block: dict[str, Any]) -> int:
    try:
        return len(str(block.get("input") or block.get("content") or block.get("text") or ""))
    except Exception:
        return 0


def extract_session(
    text: str,
    project_slug: str,
    stages: dict[str, str],
    overrides: dict[str, str],
    pricing: dict[str, dict[str, float]],
    *,
    redact_emails: bool = True,
    extra_patterns: list[str] | None = None,
    identity: tuple[str, str] | None = None,
) -> ExtractResult | None:
    """Extract one session's records from the full JSONL text. None if no usable lines.

    `identity` is an optional (machine_id, machine) pair stamped onto the SessionRecord for
    per-employee attribution. Left None by default so existing callers (offline analyze,
    round-trip tests) stay deterministic; the sync/drive paths pass it explicitly via
    identity.machine_identity().
    """
    lines = list(parse_lines(text))
    if not lines:
        return None

    session_id = next((line.session_id for line in lines if line.session_id), None)
    if not session_id:
        return None

    stage = resolve_stage(project_slug, session_id, stages, overrides)

    # Session-level aggregates.
    cwd = next((line.cwd for line in lines if line.cwd), None)
    git_branch = next((line.git_branch for line in lines if line.git_branch), None)
    version = next((line.version for line in lines if line.version), None)
    model = next((line.model for line in reversed(lines) if line.model), None)

    timestamps = [t for t in (_iso_to_dt(line.timestamp) for line in lines) if t]
    started = min(timestamps) if timestamps else None
    ended = max(timestamps) if timestamps else None
    duration = int((ended - started).total_seconds()) if started and ended else None

    in_tok = out_tok = cache_r = cache_c = 0
    num_user = num_assistant = 0
    token_timeline: list[TokenCheckpoint] = []
    for line in lines:
        if line.type == "user":
            num_user += 1
        elif line.type == "assistant":
            num_assistant += 1
            in_tok += int(line.usage.get("input_tokens", 0) or 0)
            out_tok += int(line.usage.get("output_tokens", 0) or 0)
            cache_r += int(line.usage.get("cache_read_input_tokens", 0) or 0)
            cache_c += int(line.usage.get("cache_creation_input_tokens", 0) or 0)
            # A checkpoint per assistant turn: cumulative tokens + cost AS OF this turn, from
            # real per-turn usage (not a distributed session total). The event log stamps each
            # event with the checkpoint in force at its timestamp.
            token_timeline.append(TokenCheckpoint(
                ts=line.timestamp,
                cum_input_tokens=in_tok,
                cum_output_tokens=out_tok,
                cum_cost_usd=estimate_cost(line.model or model, in_tok, out_tok,
                                           cache_r, cache_c, pricing),
            ))

    # First non-meta user text -> redacted excerpt. Slash-command wrappers
    # (<command-name>/x</command-name> ...) are summarized as the command, not the raw tag.
    first_prompt = ""
    for line in lines:
        if line.type == "user" and not line.is_meta:
            if line.command_name:
                first_prompt = f"[command] {line.command_name}"
                break
            for block in line.content:
                if block.get("type") == "text" and block.get("text"):
                    first_prompt = redact(
                        str(block["text"]), redact_emails=redact_emails, extra=extra_patterns
                    )[:EXCERPT_MAX]
                    break
        if first_prompt:
            break

    tool_calls: list[ToolCallRecord] = []
    subagent_runs: list[SubagentRunRecord] = []
    skill_uses: list[SkillUseRecord] = []
    error_count = 0

    # Pair tool_use with tool_result by id for is_error / result bytes / duration.
    tool_use_ts: dict[str, datetime | None] = {}
    results_by_id: dict[str, dict[str, Any]] = {}
    for line in lines:
        for block in line.content:
            if block.get("type") == "tool_result":
                tid = block.get("tool_use_id")
                if tid:
                    results_by_id[tid] = {
                        "is_error": bool(block.get("is_error", False)),
                        "bytes": _block_bytes(block),
                        "ts": _iso_to_dt(line.timestamp),
                    }

    for line in lines:
        if line.command_name:
            skill_uses.append(
                SkillUseRecord(
                    session_id=session_id,
                    msg_uuid=line.uuid or "",
                    ts=line.timestamp,
                    skill_name=line.command_name,
                    source="slash-command",
                    args_excerpt="",
                )
            )
        for block in line.content:
            btype = block.get("type")
            if btype != "tool_use":
                continue
            tid = block.get("id") or ""
            name = block.get("name") or "unknown"
            tool_input = block.get("input") or {}
            if not isinstance(tool_input, dict):
                tool_input = {}
            ts_dt = _iso_to_dt(line.timestamp)
            tool_use_ts[tid] = ts_dt
            result = results_by_id.get(tid, {})
            if result.get("is_error"):
                error_count += 1
            duration_ms = None
            if ts_dt and result.get("ts"):
                duration_ms = int((result["ts"] - ts_dt).total_seconds() * 1000)

            tool_calls.append(
                ToolCallRecord(
                    session_id=session_id,
                    tool_use_id=tid,
                    msg_uuid=line.uuid,
                    ts=line.timestamp,
                    tool_name=name,
                    is_sidechain=line.is_sidechain,
                    input_summary=_coarse_input_summary(name, tool_input),
                    input_bytes=_block_bytes(block),
                    result_bytes=int(result.get("bytes", 0)),
                    is_error=bool(result.get("is_error", False)),
                    duration_ms=duration_ms,
                )
            )

            # Subagent invocations: newer Claude Code names the tool "Agent"; older
            # versions used "Task". Both carry subagent_type + description.
            if name in ("Agent", "Task"):
                subagent_runs.append(
                    SubagentRunRecord(
                        session_id=session_id,
                        task_tool_use_id=tid,
                        agent_name=str(tool_input.get("subagent_type", "")) or None,
                        description_excerpt=redact(
                            str(tool_input.get("description", "")),
                            redact_emails=redact_emails,
                            extra=extra_patterns,
                        )[:EXCERPT_MAX],
                        started_at=line.timestamp,
                        success=None if not result else (not result.get("is_error", False)),
                    )
                )
            elif name == "Skill":
                skill_uses.append(
                    SkillUseRecord(
                        session_id=session_id,
                        msg_uuid=line.uuid or tid,
                        ts=line.timestamp,
                        skill_name=str(tool_input.get("skill", "unknown")),
                        source="skill-tool",
                        args_excerpt="",
                    )
                )

    est_cost = estimate_cost(model, in_tok, out_tok, cache_r, cache_c, pricing)

    machine_id, machine = identity if identity is not None else (None, None)
    session = SessionRecord(
        session_id=session_id,
        project_slug=project_slug,
        cwd=cwd,
        git_branch=git_branch,
        machine_id=machine_id,
        machine=machine,
        stage=stage,
        started_at=started.isoformat() if started else None,
        ended_at=ended.isoformat() if ended else None,
        duration_seconds=duration,
        model=model,
        claude_version=version,
        num_turns=num_user + num_assistant,
        num_user_msgs=num_user,
        num_assistant_msgs=num_assistant,
        input_tokens=in_tok,
        output_tokens=out_tok,
        cache_read_tokens=cache_r,
        cache_creation_tokens=cache_c,
        est_cost_usd=est_cost,
        tool_call_count=len(tool_calls),
        subagent_count=len(subagent_runs),
        skill_use_count=len(skill_uses),
        error_count=error_count,
        first_prompt_excerpt=first_prompt,
    )

    return ExtractResult(
        session=session,
        tool_calls=tool_calls,
        subagent_runs=subagent_runs,
        skill_uses=skill_uses,
        token_timeline=token_timeline,
    )
