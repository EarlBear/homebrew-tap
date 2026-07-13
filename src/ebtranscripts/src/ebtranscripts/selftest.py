"""The planted-secret sanitizer self-test — the fail-closed gate shared by every egress path.

Extracted from main.py so non-CLI modules (drive.py) can run the same gate without importing
the Typer app (which would create a circular import). main.py re-exports these names.

The gate is two-layer: (1) our own redaction must remove every known planted substring from
its fixture line, and (2) if gitleaks is installed, an independent scan of the redacted fixture
must also come back clean. If the fixture template is missing, the gate FAILS (never passes
vacuously).

Why the planted secrets are assembled, not stored literally
-----------------------------------------------------------
The planted secrets are deliberately *secret-shaped* — that is the whole point: they prove the
redaction layer catches real provider-token shapes. But a fully-formed `shpat_…` / `ghp_…` /
`xoxb-…` literal committed to a **public** repo trips GitHub push-protection (this package is
mirrored into the public homebrew tap). So we never commit the assembled form. The template
(`planted-secrets.template.jsonl`) carries `{{KEY}}` placeholders, and `_FRAGMENTS` stores each
secret split into a prefix + body — neither half matches a scanner on its own. `assemble()`
reconstructs the exact original fixture line at runtime, in memory, so the gate sees the real
secret-shaped text while nothing secret-shaped is ever at rest in git.
"""

from __future__ import annotations

from pathlib import Path

from .sanitizer import redact
from .verify import scan_clean

# Each planted secret split (prefix, body). Neither fragment matches a scanner pattern alone
# (the prefix is too short; the body carries no telltale prefix), so the template + this map
# are safe to commit — even to a public repo — while assemble() re-forms the real shapes at
# runtime. Order is the placeholder key; the assembled full string is what redaction must kill.
_FRAGMENTS: dict[str, tuple[str, str]] = {
    "ANTH": ("sk-ant-api03-", "AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"),
    "OPENAI": ("sk-proj", "0123456789ABCDEFGHIJKLMNOPQRSTUV"),
    "GHP": ("ghp_", "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"),
    "AWS": ("AKIA", "IOSFODNN7EXAMPLE"),
    "SHOP": ("shpat_", "abcdef0123456789abcdef0123456789"),
    "GHPAT": ("github_pat_", "11ABCDEFG0123456789_abcdefghijklmnopqrstuvwxyz012345"),
    # Split inside the first segment so neither fragment carries the eyJ…eyJ…. JWT shape.
    "JWT": ("eyJhbGci", "OiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"),  # noqa: E501
    "PG": ("hunter", "2password"),
    "EMAIL": ("secret.person", "@example.com"),
    "SLACK": ("xoxb-", "1234567890-ABCDEFGHIJKLMNOP"),
    "PEM": ("MIIEowIBAAKCAQEA", "0aBcDeFg"),
    "STRIPE": ("sk_live_", "secrettokenvalue123456"),
}


def _assemble_secret(key: str) -> str:
    """Reconstruct one planted secret from its (prefix, body) fragments."""
    prefix, body = _FRAGMENTS[key]
    return prefix + body


# The concrete secrets planted in the fixture, assembled at import time. The self-test asserts
# none of these substrings survive a redaction pass of their fixture line. Two of them
# ("hunter2password", the PEM body) are only secret *in context* (URL userinfo, PEM block) —
# that is deliberate and documented in test_sanitizer.py::CONTEXT_ONLY.
PLANTED_SECRETS = [_assemble_secret(k) for k in _FRAGMENTS]


def template_path() -> Path:
    # The template ships with the package; it holds {{KEY}} placeholders, never live secrets.
    return Path(__file__).parent / "fixtures" / "planted-secrets.template.jsonl"


def assemble_fixture() -> str | None:
    """Return the planted-secret fixture JSONL with every {{KEY}} placeholder assembled.

    Returns None if the template is missing — callers must fail closed on None rather than
    treat an absent fixture as clean.
    """
    path = template_path()
    if not path.exists():
        return None
    text = path.read_text()
    for key in _FRAGMENTS:
        text = text.replace("{{" + key + "}}", _assemble_secret(key))
    return text


def run_self_test() -> bool:
    """No planted secret may survive redaction of its fixture line. True if clean.

    Two layers: (1) our own redaction removes every known planted substring, and (2) if
    gitleaks is installed, an independent scan of the redacted fixture must also come back
    clean — catching anything our patterns miss.
    """
    text = assemble_fixture()
    if text is None:
        # No fixture template bundled: fail closed rather than pass vacuously.
        return False
    redacted_lines: list[str] = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        cleaned = redact(raw)
        for secret in PLANTED_SECRETS:
            if secret in cleaned:
                return False
        redacted_lines.append(cleaned)
    # Independent verification over the full redacted output.
    if not scan_clean("\n".join(redacted_lines)):
        return False
    return True
