"""Token -> estimated USD cost. Pricing is per model, USD per million tokens.

Defaults are empty (cost 0) so columns are always populated without guessing; real
numbers come from transcripts.toml [pricing]. Unknown models cost 0 rather than crash.
"""

from __future__ import annotations


def estimate_cost(
    model: str | None,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cache_creation_tokens: int,
    pricing: dict[str, dict[str, float]],
) -> float:
    if not model:
        return 0.0
    rates = pricing.get(model)
    if not rates:
        return 0.0
    per_m = 1_000_000.0
    cost = (
        input_tokens * rates.get("input", 0.0)
        + output_tokens * rates.get("output", 0.0)
        + cache_read_tokens * rates.get("cache_read", 0.0)
        + cache_creation_tokens * rates.get("cache_write", 0.0)
    ) / per_m
    return round(cost, 4)
