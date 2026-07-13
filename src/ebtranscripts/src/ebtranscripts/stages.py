"""Map a Claude Code project slug to a workflow stage.

Deny-by-default: a slug that matches no [stages] glob resolves to "other" — but the scan
step only opens slugs that DO match, so unmatched (personal) projects are never read.
Resolution order: stage_overrides (per session) -> [stages] glob on slug -> "other".
"""

from __future__ import annotations

import fnmatch

VALID_STAGES = {"lead-gen", "outreach", "onboarding", "review", "ops", "other"}


def slug_matches_any(slug: str, patterns: dict[str, str]) -> bool:
    """True if the project slug matches at least one configured [stages] glob."""
    return any(fnmatch.fnmatch(slug, pat) for pat in patterns)


def resolve_stage(
    slug: str,
    session_id: str,
    stages: dict[str, str],
    overrides: dict[str, str],
) -> str:
    if session_id in overrides:
        return overrides[session_id]
    for pattern, stage in stages.items():
        if fnmatch.fnmatch(slug, pattern):
            return stage
    return "other"
