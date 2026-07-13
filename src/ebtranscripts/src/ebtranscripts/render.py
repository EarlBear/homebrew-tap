"""Render an allowlisted session to sanitized HTML via claude-code-transcripts.

Flow: read the raw session -> sanitize its full text to a scratch JSONL (raw is never
rendered) -> run `claude-code-transcripts json` on the sanitized copy -> the site's
restyle step themes the output. Allowlist-only: callers must check the allowlist first.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from .scrub import _redact_in_place, scrub_transcript
from .verify import scan_clean

# The full-transcript scrubber now lives in scrub.py (shared with the Drive path). Kept here
# under its historical name so existing render callers/imports are unchanged.
sanitize_session_text = scrub_transcript

__all__ = ["sanitize_session_text", "scrub_transcript", "_redact_in_place", "render_session"]


def render_session(
    raw_text: str,
    session_id: str,
    out_dir: Path,
    *,
    redact_emails: bool = True,
    extra_patterns: list[str] | None = None,
    tool_version: str | None = None,
) -> dict:
    """Sanitize then render one session to out_dir/<session_id>/. Returns manifest entry.

    Raises RuntimeError if the sanitized text still trips gitleaks (defense in depth).
    """
    sanitized = sanitize_session_text(
        raw_text, redact_emails=redact_emails, extra_patterns=extra_patterns
    )
    if not scan_clean(sanitized):
        raise RuntimeError(
            f"Sanitized session {session_id} still trips gitleaks; refusing to render."
        )

    session_out = out_dir / session_id
    session_out.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        sanitized_path = Path(td) / f"{session_id}.jsonl"
        sanitized_path.write_text(sanitized)

        pkg = "claude-code-transcripts"
        spec = f"{pkg}=={tool_version}" if tool_version else pkg
        cmd = ["uvx", "--from", spec, pkg, "json", str(sanitized_path), "-o", str(session_out)]
        if shutil.which("uvx") is None:
            # Fall back to a directly-installed console script.
            cmd = [pkg, "json", str(sanitized_path), "-o", str(session_out)]
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)

    pages = sorted(p.name for p in session_out.glob("page-*.html"))
    return {
        "session_id": session_id,
        "pages": len(pages),
    }
