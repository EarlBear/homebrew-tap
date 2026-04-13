"""Build subcommand: wraps docker compose build + toolchain runs (marp/slidev/pptx)."""

from __future__ import annotations

import shutil
from pathlib import Path

import typer

from ebdeck.runner import brand_prefix, compose, content_prefix, deck_cli_root, run

build_app = typer.Typer(
    name="build",
    help="Build Docker images and generate decks (marp, slidev, python-pptx).",
    no_args_is_help=True,
)

# Defaults mirror Makefile:
#   CONTENT ?= investor-pitch.yaml
#   BRAND   ?= brand.yaml
CONTENT_OPT = typer.Option(
    "investor-pitch.yaml",
    "--content",
    "-c",
    help="Content YAML filename (under content/).",
)
BRAND_OPT = typer.Option(
    "brand.yaml",
    "--brand",
    "-b",
    help="Brand YAML path (e.g. brand.yaml or brands/matcha.yaml).",
)


@build_app.command("images")
def build_images(
    no_cache: bool = typer.Option(False, "--no-cache", help="Rebuild all images from scratch."),
) -> None:
    """Build (or rebuild) all docker-compose images. Maps to `make build` / `make rebuild`."""
    args = ["build"]
    if no_cache:
        args.append("--no-cache")
    compose(args)


@build_app.command("marp")
def build_marp(content: str = CONTENT_OPT, brand: str = BRAND_OPT) -> None:
    """Generate Marp Markdown only (→ poc-marp/output/deck.md)."""
    compose(["run", "--rm", "marp", f"/data/content/{content}", f"/data/{brand}"])


@build_app.command("marp-pdf")
def build_marp_pdf(content: str = CONTENT_OPT, brand: str = BRAND_OPT) -> None:
    """Generate Marp → PDF."""
    compose(
        [
            "run",
            "--rm",
            "--entrypoint",
            "sh",
            "marp-pdf",
            "-c",
            (
                f"node generate.js /data/content/{content} /data/{brand} && "
                "npx @marp-team/marp-cli --allow-local-files output/deck.md "
                "--pdf -o output/deck.pdf"
            ),
        ]
    )


@build_app.command("marp-pptx")
def build_marp_pptx(content: str = CONTENT_OPT, brand: str = BRAND_OPT) -> None:
    """Generate Marp → PPTX."""
    compose(
        [
            "run",
            "--rm",
            "--entrypoint",
            "sh",
            "marp-pptx",
            "-c",
            (
                f"node generate.js /data/content/{content} /data/{brand} && "
                "npx @marp-team/marp-cli --allow-local-files output/deck.md "
                "--pptx -o output/deck.pptx"
            ),
        ]
    )


@build_app.command("slidev")
def build_slidev(content: str = CONTENT_OPT, brand: str = BRAND_OPT) -> None:
    """Generate Slidev Markdown only."""
    compose(["run", "--rm", "slidev", f"/data/content/{content}", f"/data/{brand}"])


@build_app.command("slidev-pptx")
def build_slidev_pptx(content: str = CONTENT_OPT, brand: str = BRAND_OPT) -> None:
    """Generate Slidev → PPTX."""
    compose(
        [
            "run",
            "--rm",
            "--entrypoint",
            "sh",
            "slidev-pptx",
            "-c",
            (
                f"node generate.js /data/content/{content} /data/{brand} && "
                "slidev export output/slides.md --output output/deck.pptx "
                "--format pptx --timeout 60000"
            ),
        ]
    )


@build_app.command("pptx")
def build_pptx(content: str = CONTENT_OPT, brand: str = BRAND_OPT) -> None:
    """Generate native editable PPTX via python-pptx."""
    compose(["run", "--rm", "pptx", f"/data/content/{content}", f"/data/{brand}"])


@build_app.command("all")
def build_all(content: str = CONTENT_OPT, brand: str = BRAND_OPT) -> None:
    """Generate all three PPTX styles for a single brand (marp-pptx + slidev-pptx + pptx)."""
    build_marp_pptx(content=content, brand=brand)
    build_slidev_pptx(content=content, brand=brand)
    build_pptx(content=content, brand=brand)


@build_app.command("dist")
def build_dist(content: str = CONTENT_OPT, brand: str = BRAND_OPT) -> None:
    """Generate all tools + collect into dist/output/<brand>/. Maps to `make dist`."""
    build_all(content=content, brand=brand)

    root = deck_cli_root()
    bp = brand_prefix(brand)
    cp = content_prefix(content)
    out = root / "dist" / "output" / bp
    (out / "marp").mkdir(parents=True, exist_ok=True)
    (out / "slidev").mkdir(parents=True, exist_ok=True)
    (out / "pptx").mkdir(parents=True, exist_ok=True)

    copies = [
        (root / "poc-marp/output/deck.pptx", out / "marp" / f"{cp}-marp.pptx"),
        (root / "poc-marp/output/deck.pdf", out / "marp" / f"{cp}-marp.pdf"),
        (root / "poc-slidev/output/deck.pptx", out / "slidev" / f"{cp}-slidev.pptx"),
        (root / "poc-pptx/output/deck.pptx", out / "pptx" / f"{cp}-pptx.pptx"),
    ]
    for src, dst in copies:
        if src.is_file():
            shutil.copy2(src, dst)

    content_src = root / "content" / content
    if content_src.is_file():
        shutil.copy2(content_src, out / content)

    typer.echo(f"✓ Collected in dist/output/{bp}/")


@build_app.command("clean")
def build_clean(
    all_outputs: bool = typer.Option(False, "--all", help="Also remove dist/output + gallery."),
) -> None:
    """Remove per-tool output. Maps to `make clean` / `make clean-all`."""
    root = deck_cli_root()
    targets = [
        root / "poc-marp/output",
        root / "poc-slidev/output",
        root / "poc-pptx/output",
        root / "poc-figma/dist",
    ]
    if all_outputs:
        targets.extend(
            [root / "dist/output", root / "dist/thumbnails", root / "dist/gallery.html"]
        )
    for t in targets:
        if t.is_dir():
            shutil.rmtree(t)
        elif t.is_file():
            t.unlink()
    typer.echo("✓ Cleaned")
