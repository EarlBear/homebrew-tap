"""Gallery subcommand: wraps thumbnails + gallery generation."""

from __future__ import annotations

import subprocess

import typer

from ebdeck.runner import compose, deck_cli_root

gallery_app = typer.Typer(
    name="gallery",
    help="Thumbnails + HTML gallery generation.",
    no_args_is_help=True,
)


@gallery_app.command("thumbnails")
def thumbnails() -> None:
    """Convert all PPTXs under dist/output/ to PNG thumbnails."""
    compose(["run", "--rm", "thumbnails"])


@gallery_app.command("build")
def build(
    skip_thumbnails: bool = typer.Option(
        False, "--skip-thumbnails", help="Skip thumbnail regeneration (use existing PNGs)."
    ),
) -> None:
    """Generate dist/gallery.html from thumbnails. Maps to `make gallery`."""
    if not skip_thumbnails:
        thumbnails()
    compose(["run", "--rm", "gallery"])
    typer.echo("✓ Gallery: dist/gallery.html")


@gallery_app.command("open")
def open_gallery() -> None:
    """Build gallery + open dist/gallery.html in the default browser."""
    build(skip_thumbnails=False)
    root = deck_cli_root()
    path = root / "dist" / "gallery.html"
    if not path.is_file():
        raise SystemExit(f"ebdeck: {path} does not exist")
    subprocess.run(["open", str(path)], check=False)
