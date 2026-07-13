"""Edge-side secret scrubbing.

Two-layer design, structural first:

  1. Records are *constructed* from an explicit safe-field allowlist — we never copy a
     raw content block and delete fields from it. File bodies and full prompts are never
     staged; only bounded, redacted excerpts exist. (That construction lives in
     extract.py; this module provides the excerpt-redaction it relies on.)

  2. A pattern pass over every excerpt/summary string removes anything secret-shaped:
     JWTs, provider API keys, cloud keys, private-key blocks, bearer tokens, URL
     userinfo, emails (configurable), and high-entropy tokens.

Every sanitized value is produced by `redact()`. The planted-secret fixture test asserts
zero known secrets survive a pass; `--self-test` runs it at runtime and fails closed.
"""

from __future__ import annotations

import math
import re

SANITIZER_VERSION = "1.0.0"

# Order matters: more specific patterns first so their replacement label is the one used.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # PEM / private key blocks (collapse the whole block).
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL)),  # noqa: E501
    # JWTs: three base64url segments separated by dots.
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b")),
    # Anthropic keys.
    ("anthropic-key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{8,}\b")),
    # OpenAI-style keys.
    ("openai-key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    # Stripe-style keys (sk_live_, sk_test_, rk_live_, pk_live_).
    ("stripe-key", re.compile(r"\b[sprSPR]k_(?:live|test)_[A-Za-z0-9]{10,}\b")),
    # GitHub tokens (classic + fine-grained).
    ("github-token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b")),
    ("github-pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    # AWS access key id.
    ("aws-key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    # Shopify tokens.
    ("shopify-token", re.compile(r"\bshp(?:at|ss|ca|pa)_[A-Za-z0-9]{16,}\b")),
    # Slack tokens.
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    # Bearer tokens in text.
    ("bearer", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}", re.IGNORECASE)),
    # URL with userinfo (user:pass@host).
    ("url-userinfo", re.compile(r"\b([a-z][a-z0-9+.-]*://)[^/\s:@]+:[^/\s:@]+@")),
    # --- Structured PII (a defense-in-depth backstop; the structural allowlist is primary) ---
    # US SSN: xxx-xx-xxxx (with the common invalid-range guard omitted for simplicity — we
    # prefer over-catching a real SSN to under-catching). Requires the dashes so a plain
    # 9-digit run (an id, an order number) is not swept up here.
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    # IPv4. (IPv6 handled below with a looser pattern.)
    ("ipv4", re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")),
    # MAC address — before IPv6, since the IPv6 pattern also matches colon-hex groups.
    ("mac", re.compile(r"\b(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b")),
    # IPv6 (compressed or full). Conservative: needs at least two colon groups incl. a "::"
    # or 4+ hextet groups, so ordinary "a:b" text isn't matched.
    ("ipv6", re.compile(r"\b(?:[0-9A-Fa-f]{1,4}:){2,7}[0-9A-Fa-f]{1,4}\b|\b(?:[0-9A-Fa-f]{1,4}:){1,7}:\b")),  # noqa: E501
    # Phone numbers: US/international shapes with a separator, so a bare "5551234" or a
    # store-count like "214" is NOT matched — we require at least a country/area grouping
    # with separators (space, dash, dot, or parens) and 10+ digits total.
    ("phone", re.compile(
        r"(?<![\w.])(?:\+?\d{1,3}[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]\d{3}[\s.-]\d{4}(?![\w])"
    )),
    # US postal address-ish: a street number + name + common suffix. Regex on addresses is
    # inherently partial (free-form addresses escape it) — documented as a known limitation.
    ("us-address", re.compile(
        r"\b\d{1,6}\s+(?:[A-Z][A-Za-z]*\s){1,4}"
        r"(?:Street|St|Avenue|Ave|Boulevard|Blvd|Road|Rd|Lane|Ln|Drive|Dr|Court|Ct|Way|"
        r"Place|Pl|Terrace|Ter|Circle|Cir)\b\.?",
        re.IGNORECASE,
    )),
    # US ZIP (5 or ZIP+4), but only when prefixed by a state-like token or the word "zip",
    # so a bare 5-digit number (a count, an id) isn't swept. Applied after address.
    ("us-zip", re.compile(  # noqa: E501
        r"\b[A-Z]{2}\s+\d{5}(?:-\d{4})?\b|\bzip[:\s]+\d{5}(?:-\d{4})?\b", re.IGNORECASE)),
]

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

# Credit-card candidate: 13-19 digits, optionally grouped by spaces/dashes. Only redacted if
# the digits pass the Luhn checksum — so a random 16-digit id or order number is left alone.
_CC_CANDIDATE = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")

# Secret assignment: `password: x`, `passwd=x`, `api_key=...`, `token=...`, `secret: ...`.
# Captures the KEY (group 1) + separator so we redact the VALUE only, keeping the label. A bare
# password in prose (not in a url:pass@host and not assigned) is genuinely indistinguishable from
# prose — that residual gap is why the structural allowlist runs first.
_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|pwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token|token)"
    r"(\s*[:=]\s*)(?P<val>\"[^\"]+\"|'[^']+'|\S+)"
)


def _luhn_ok(digits: str) -> bool:
    """Luhn checksum — the standard credit-card validity check."""
    ds = [int(c) for c in digits]
    if len(ds) < 13:
        return False
    total = 0
    for i, d in enumerate(reversed(ds)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _redact_credit_cards(text: str) -> str:
    def sub(m: re.Match[str]) -> str:
        raw = m.group(0)
        digits = re.sub(r"[ -]", "", raw)
        return "[REDACTED:credit-card]" if _luhn_ok(digits) else raw
    return _CC_CANDIDATE.sub(sub, text)


def _redact_assignments(text: str) -> str:
    # Keep the key + separator, redact only the assigned value.
    return _ASSIGNMENT.sub(lambda m: f"{m.group(1)}{m.group(2)}[REDACTED:credential]", text)

# Generic high-entropy token: a long run of key-ish characters. Applied last, and only to
# tokens that look like secrets (mixed case/digits), to avoid nuking ordinary prose.
_LONG_TOKEN = re.compile(r"\b[A-Za-z0-9_\-]{32,}\b")

# UUIDs and tool-use ids are identifiers, not secrets — exempt them from the entropy sweep
# so session_id / tool_use_id survive (they're needed as keys, and leak nothing).
_HEX = "[0-9a-fA-F]"
_UUID = re.compile(rf"\b{_HEX}{{8}}-{_HEX}{{4}}-{_HEX}{{4}}-{_HEX}{{4}}-{_HEX}{{12}}\b")
_TOOL_USE_ID = re.compile(r"\b(?:toolu|call|msg|run|req)_[A-Za-z0-9]{6,}\b")


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts: dict[str, int] = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def redact(text: str | None, *, redact_emails: bool = True, extra: list[str] | None = None) -> str:
    """Return `text` with every secret-shaped substring replaced by a [REDACTED:kind] tag.

    Safe to call on any excerpt before it is staged or rendered. Returns "" for None.
    """
    if not text:
        return ""

    out = text

    # Secret assignments first (`password: x`) — redact the value, keep the label — before the
    # named patterns can partially consume the value.
    out = _redact_assignments(out)

    for label, pattern in _PATTERNS:
        out = pattern.sub(f"[REDACTED:{label}]", out)

    if redact_emails:
        out = _EMAIL.sub("[REDACTED:email]", out)

    # Credit cards: Luhn-validated so random digit runs (ids, order numbers) are left alone.
    # Before the entropy sweep so a valid card is labelled credit-card, not high-entropy.
    out = _redact_credit_cards(out)

    for raw in extra or []:
        try:
            out = re.sub(raw, "[REDACTED:custom]", out)
        except re.error:
            # A bad user-supplied pattern must never crash the sanitizer.
            continue

    # High-entropy sweep: only replace long tokens that actually look random — but never
    # UUIDs or tool-use ids, which are identifiers (needed as keys, leak nothing).
    def _entropy_sub(m: re.Match[str]) -> str:
        token = m.group(0)
        if _UUID.fullmatch(token) or _TOOL_USE_ID.fullmatch(token):
            return token
        if _shannon_entropy(token) >= 3.5:
            return "[REDACTED:high-entropy]"
        return token

    out = _LONG_TOKEN.sub(_entropy_sub, out)
    return out


def has_secret(text: str | None) -> bool:
    """True if `text` still contains anything secret-shaped after a redaction pass.

    Used by the planted-secret fixture test and `sanitize --self-test`.
    """
    if not text:
        return False
    redacted = redact(text)
    return "[REDACTED:" in redacted
