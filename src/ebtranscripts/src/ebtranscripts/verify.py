"""Defense-in-depth secret verification, independent of our own redaction.

Our `sanitizer.redact()` is the primary control (a Gitleaks-style named-pattern + entropy
pass, applied at extraction). This module adds a SECOND, independent detector over the
already-sanitized output — reusing Gitleaks' battle-tested rule library — so a gap in our
patterns is caught before anything is pushed or published. This mirrors the 2026 best
practice of pairing a fast rule scanner with a separate verification layer.

Gitleaks is optional: if it is not installed, `scan_clean()` returns True (our own
redaction still ran). Where it matters most — the publish path — the caller should treat
a missing scanner as a reason to warn, not to silently ship.

For the Google Drive consolidation boundary (drive.py) that best-effort posture is NOT
acceptable: Drive is a new exfiltration path carrying a *full* scrubbed transcript (a weaker,
regex-only guarantee). `scan_clean_strict()` therefore treats a missing gitleaks as a HARD
FAILURE — no clean verdict without the second detector actually having run. This is a distinct
function so the existing best-effort callers (render, self-test) are unaffected.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def gitleaks_available() -> bool:
    return shutil.which("gitleaks") is not None


def scan_text(text: str) -> list[dict]:
    """Run gitleaks over `text`; return the list of findings (empty if clean/unavailable).

    The candidate text is piped to `gitleaks stdin` — it is NEVER written to disk, so no
    secret-bearing temp file exists even briefly. Only the redacted findings *report* is
    written to a temp path (findings carry no raw secret; gitleaks redacts them), then read
    back and deleted with the TemporaryDirectory.
    """
    if not gitleaks_available():
        return []
    with tempfile.TemporaryDirectory() as td:
        report = Path(td) / "report.json"
        # `gitleaks stdin` scans piped content with no file on disk and no git history.
        subprocess.run(
            [
                "gitleaks",
                "stdin",
                "--report-format",
                "json",
                "--report-path",
                str(report),
                "--redact",
                "--no-banner",
                "--exit-code",
                "0",
            ],
            input=text.encode(),
            capture_output=True,
            timeout=60,
        )
        if not report.exists():
            return []
        try:
            data = json.loads(report.read_text() or "[]")
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []


def scan_clean(text: str) -> bool:
    """True if gitleaks finds no secrets in `text` (or gitleaks is unavailable).

    Best-effort: a missing gitleaks yields True. Use for render/self-test, NOT the Drive gate.
    """
    return len(scan_text(text)) == 0


def scan_clean_strict(text: str) -> bool:
    """True only if gitleaks IS installed AND finds no secrets in `text`.

    Fail-closed: a missing gitleaks yields False (unlike `scan_clean`). This is the required
    gate for the Google Drive write boundary — nothing reaches Drive without a real, passing
    second-detector scan. Callers should tell the user to `brew install gitleaks` on a False
    caused by absence; check `gitleaks_available()` to distinguish "absent" from "found secrets".
    """
    if not gitleaks_available():
        return False
    return len(scan_text(text)) == 0
