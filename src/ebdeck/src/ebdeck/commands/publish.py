"""Publish subcommand: copy dist/output + gallery into a sibling earlbear-sites repo."""

from __future__ import annotations

import shutil
from pathlib import Path

import typer

from ebdeck.runner import deck_cli_root

publish_app = typer.Typer(
    name="publish",
    help="Copy dist/output/<brand>/ + dist/gallery.html into <site>/decks/<name>/.",
    invoke_without_command=True,
)


@publish_app.callback(invoke_without_command=True)
def publish(
    ctx: typer.Context,
    site: Path = typer.Option(
        ...,
        "--site",
        help="Path to sibling earlbear-sites repo (must be a git checkout).",
    ),
    name: str = typer.Option(
        ...,
        "--name",
        help="Deck name — the subdirectory under <site>/decks/ that receives the output.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite <site>/decks/<name>/ without confirmation.",
    ),
) -> None:
    """Feed a built deck bundle into an earlbear-sites checkout for publishing.

    Copies:
        dist/output/*/.     → <site>/decks/<name>/
        dist/gallery.html   → <site>/decks/<name>/gallery.html
    """
    if ctx.invoked_subcommand is not None:
        return

    root = deck_cli_root()
    dist = root / "dist"
    gallery = dist / "gallery.html"
    output = dist / "output"

    site = site.expanduser().resolve()
    if not site.is_dir():
        raise SystemExit(f"ebdeck publish: --site {site} is not a directory")
    if not (site / ".git").exists():
        raise SystemExit(f"ebdeck publish: --site {site} is not a git checkout")
    if not gallery.is_file():
        raise SystemExit(
            f"ebdeck publish: {gallery} missing — run `ebdeck gallery build` first"
        )
    if not output.is_dir() or not any(output.iterdir()):
        raise SystemExit(
            f"ebdeck publish: {output} is empty — run `ebdeck permutations` first"
        )

    target = site / "decks" / name
    if target.exists():
        if not force:
            typer.confirm(
                f"{target} already exists. Remove and replace?", abort=True
            )
        shutil.rmtree(target)
    target.mkdir(parents=True)

    # Copy contents of every brand subdir (flat structure preserved per brand)
    for entry in output.iterdir():
        dest = target / entry.name
        if entry.is_dir():
            shutil.copytree(entry, dest)
        else:
            shutil.copy2(entry, dest)

    shutil.copy2(gallery, target / "gallery.html")

    typer.echo(f"✓ Published deck bundle → {target}")
    typer.echo("Next steps:")
    typer.echo(f"  cd {site}")
    typer.echo(f"  git add decks/{name}")
    typer.echo(f'  git commit -m "feat(decks): add {name}"')
