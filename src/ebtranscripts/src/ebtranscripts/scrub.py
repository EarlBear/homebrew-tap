"""Scrub a full session transcript — redact every string value, preserve JSONL structure.

This is the shared full-transcript scrubber, promoted out of render.py so both the HTML
renderer (allowlisted publishing) and the Google Drive consolidation path (scrubbed
session.jsonl corpus) use ONE implementation. render.py re-exports these for back-compat.

    scrub_transcript(raw_text) -> str   # the scrubbed JSONL text

HONEST CAVEAT — this is a WEAKER guarantee than the derived-record path.
Extraction (extract.py) builds records from a *structural allowlist*: raw content blocks are
never copied, so the strongest secrets (file bodies, full prompts) never enter a record at all.
Scrubbing a *full* transcript is the opposite shape: we keep every message — including tool
RESULT bodies that may contain file contents — and rely on a *regex* pass (sanitizer.redact())
to catch secrets in them. A secret that doesn't match any pattern and isn't high-entropy (e.g.
a plausible-looking password in prose) can survive. That is why the Google Drive write gate
(drive.py) requires gitleaks as a fail-closed second detector on this output — see
verify.scan_clean_strict() and docs/drive-consolidation-design.md §2c. Never treat the scrubbed
full transcript as carrying the allowlist's structural guarantee.
"""

from __future__ import annotations

import json

from .sanitizer import redact


def scrub_transcript(text: str, *, redact_emails: bool = True,
                     extra_patterns: list[str] | None = None) -> str:
    """Redact every text/content string in each JSONL line, preserving structure.

    Unlike extraction (which drops raw content entirely), this keeps the message shape but
    scrubs every string value through redact(). Non-JSON and blank lines are dropped.
    """
    out_lines: list[str] = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        _redact_in_place(obj, redact_emails, extra_patterns)
        out_lines.append(json.dumps(obj))
    return "\n".join(out_lines) + "\n"


def _redact_in_place(node: object, redact_emails: bool, extra: list[str] | None) -> None:
    if isinstance(node, dict):
        for key, val in node.items():
            if isinstance(val, str):
                node[key] = redact(val, redact_emails=redact_emails, extra=extra)
            else:
                _redact_in_place(val, redact_emails, extra)
    elif isinstance(node, list):
        for i, val in enumerate(node):
            if isinstance(val, str):
                node[i] = redact(val, redact_emails=redact_emails, extra=extra)
            else:
                _redact_in_place(val, redact_emails, extra)
