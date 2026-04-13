"""Permutations subcommand: wraps scripts/permutations.sh."""

from __future__ import annotations

import typer

from ebdeck.runner import deck_cli_root, run

permutations_app = typer.Typer(
    name="permutations",
    help="Generate all brand × tool permutations (parallel) → dist/output/.",
    invoke_without_command=True,
)


@permutations_app.callback(invoke_without_command=True)
def permutations(
    ctx: typer.Context,
    content: str = typer.Option(
        "investor-pitch.yaml", "--content", "-c", help="Content YAML filename (under content/)."
    ),
    max_parallel: int = typer.Option(
        6, "--max-parallel", "-j", help="Max parallel jobs per wave (default 6)."
    ),
) -> None:
    """Run scripts/permutations.sh CONTENT MAX_PARALLEL from the deck-cli root."""
    if ctx.invoked_subcommand is not None:
        return
    root = deck_cli_root()
    script = root / "scripts" / "permutations.sh"
    if not script.is_file():
        raise SystemExit(f"ebdeck: {script} not found")
    run(["bash", str(script), content, str(max_parallel)])
