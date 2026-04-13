"""Figma plugin subcommand: install / build / watch."""

from __future__ import annotations

import typer

from ebdeck.runner import compose, deck_cli_root, run

figma_app = typer.Typer(
    name="figma",
    help="Figma plugin build commands (install/build/watch).",
    no_args_is_help=True,
)


@figma_app.command("install")
def install() -> None:
    """Install Figma plugin dependencies locally (npm install in poc-figma/)."""
    root = deck_cli_root()
    run(["npm", "install"], cwd=root / "poc-figma")


@figma_app.command("build")
def build() -> None:
    """Build the Figma plugin via Docker → poc-figma/output/."""
    root = deck_cli_root()
    (root / "poc-figma" / "output").mkdir(parents=True, exist_ok=True)
    compose(["run", "--rm", "figma-build"])


@figma_app.command("build-local")
def build_local() -> None:
    """Build Figma plugin locally via node esbuild (no Docker)."""
    root = deck_cli_root()
    run(["node", "esbuild.config.mjs"], cwd=root / "poc-figma")


@figma_app.command("watch")
def watch() -> None:
    """Build Figma plugin in watch mode locally (no Docker)."""
    root = deck_cli_root()
    run(["node", "esbuild.config.mjs", "--watch"], cwd=root / "poc-figma")
