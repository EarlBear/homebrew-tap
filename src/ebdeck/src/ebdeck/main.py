"""EarlBear deck CLI — thin typer wrapper over the deck-cli docker-compose toolchain.

Usage:
    ebdeck --help                  Show all command groups
    ebdeck <group> --help          Show commands in a group
    ebdeck <group> <cmd> --help    Show command options
    ebdeck --version               Show version

ebdeck shells out to `docker compose` against deck-cli/docker-compose.yaml
for the heavy-lifting toolchains (marp, slidev, python-pptx, figma,
thumbnails, gallery). ebdeck itself runs on the host — unlike the other
CLIs in this repo, it is NOT Docker-wrapped, because docker-in-docker
is the wrong choice for an orchestrator. See deck-cli/README.md.
"""

from __future__ import annotations

import json
from typing import Optional

import typer

from ebdeck import __version__

app = typer.Typer(
    name="ebdeck",
    help="EarlBear deck CLI — generate, package, and publish decks.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)


def version_callback(value: bool) -> None:
    if value:
        print(json.dumps({"name": "ebdeck", "version": __version__}))
        raise typer.Exit()


@app.callback()
def main_callback(
    version: Optional[bool] = typer.Option(  # noqa: UP007
        None,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        help="Show version.",
    ),
) -> None:
    """EarlBear deck CLI."""
    pass


def _register_commands() -> None:
    """Import and register all command group sub-apps."""
    from ebdeck.commands.build import build_app
    from ebdeck.commands.figma import figma_app
    from ebdeck.commands.gallery import gallery_app
    from ebdeck.commands.package import package_app
    from ebdeck.commands.permutations import permutations_app
    from ebdeck.commands.publish import publish_app

    app.add_typer(build_app, name="build")
    app.add_typer(permutations_app, name="permutations")
    app.add_typer(gallery_app, name="gallery")
    app.add_typer(package_app, name="package")
    app.add_typer(figma_app, name="figma")
    app.add_typer(publish_app, name="publish")


_register_commands()


def main() -> None:
    """CLI entry point."""
    app()


if __name__ == "__main__":
    main()
