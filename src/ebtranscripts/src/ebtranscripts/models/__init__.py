"""Normalized telemetry records — the shapes pushed to Supabase (cc_* tables).

These are *derived* records, never raw content. Excerpts are already redacted by the
time they land in a model instance.
"""

from __future__ import annotations

from pydantic import BaseModel

from ..sanitizer import SANITIZER_VERSION

EXTRACTOR_VERSION = "1.0.0"


class SessionRecord(BaseModel):
    session_id: str
    project_slug: str
    cwd: str | None = None
    git_branch: str | None = None
    # Per-machine attribution, derived at the edge (see identity.py). machine_id is the hardware
    # serial (stable across rename; was employee_id/whoami). Nullable so pre-identity callers/rows
    # remain valid; the marts COALESCE these to 'unknown'.
    machine_id: str | None = None
    machine: str | None = None
    stage: str = "other"
    started_at: str | None = None
    ended_at: str | None = None
    duration_seconds: int | None = None
    model: str | None = None
    claude_version: str | None = None
    num_turns: int = 0
    num_user_msgs: int = 0
    num_assistant_msgs: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    est_cost_usd: float = 0.0
    tool_call_count: int = 0
    subagent_count: int = 0
    skill_use_count: int = 0
    error_count: int = 0
    first_prompt_excerpt: str = ""
    is_published: bool = False
    transcript_url: str | None = None
    sanitizer_version: str = SANITIZER_VERSION
    extractor_version: str = EXTRACTOR_VERSION


class ToolCallRecord(BaseModel):
    session_id: str
    tool_use_id: str
    msg_uuid: str | None = None
    ts: str | None = None
    tool_name: str
    is_sidechain: bool = False
    input_summary: str = ""
    input_bytes: int = 0
    result_bytes: int = 0
    is_error: bool = False
    duration_ms: int | None = None


class SubagentRunRecord(BaseModel):
    session_id: str
    task_tool_use_id: str
    agent_name: str | None = None
    description_excerpt: str = ""
    started_at: str | None = None
    ended_at: str | None = None
    duration_seconds: int | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    tool_call_count: int = 0
    success: bool | None = None


class SkillUseRecord(BaseModel):
    session_id: str
    msg_uuid: str
    ts: str | None = None
    skill_name: str
    source: str  # "skill-tool" | "slash-command"
    args_excerpt: str = ""


class TokenCheckpoint(BaseModel):
    """Cumulative token/cost totals as of one assistant turn (real per-turn usage, not
    fabricated). The event log stamps each event with the checkpoint in force at its
    timestamp, so 'cost as of event N' is answerable without distributing a session total."""

    ts: str | None = None
    cum_input_tokens: int = 0
    cum_output_tokens: int = 0
    cum_cost_usd: float = 0.0


class ExtractResult(BaseModel):
    """Everything extracted from one session file."""

    session: SessionRecord
    tool_calls: list[ToolCallRecord] = []
    subagent_runs: list[SubagentRunRecord] = []
    skill_uses: list[SkillUseRecord] = []
    # Per-assistant-turn cumulative token/cost timeline, in order — exact, from real usage.
    token_timeline: list[TokenCheckpoint] = []
