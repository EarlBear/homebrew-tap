"""Package subcommand: flat zip of all PPTX permutations + gallery."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import typer

from ebdeck.runner import deck_cli_root

package_app = typer.Typer(
    name="package",
    help="Build zip with all PPTXs (flat) + gallery HTML. Maps to `make package`.",
    invoke_without_command=True,
)


@package_app.callback(invoke_without_command=True)
def package(ctx: typer.Context) -> None:
    """Assemble dist/earlbear-decks.zip containing every PPTX + gallery.html."""
    if ctx.invoked_subcommand is not None:
        return

    root = deck_cli_root()
    dist = root / "dist"
    package_dir = dist / "package"
    package_dir.mkdir(parents=True, exist_ok=True)

    # Clean prior package contents
    for f in package_dir.glob("*.pptx"):
        f.unlink()
    for f in package_dir.glob("*.html"):
        f.unlink()
    zip_path = dist / "earlbear-decks.zip"
    if zip_path.exists():
        zip_path.unlink()

    # Flatten: dist/output/<brand>/<tool>/<file>.pptx → <brand>-<tool>.pptx
    output_dir = dist / "output"
    if not output_dir.is_dir():
        raise SystemExit(f"ebdeck: {output_dir} does not exist. Run `ebdeck permutations` first.")

    count = 0
    for pptx in output_dir.rglob("*.pptx"):
        parts = pptx.relative_to(output_dir).parts
        if len(parts) < 3:
            continue  # expected: <brand>/<tool>/<file>.pptx
        brand, tool = parts[0], parts[1]
        dest = package_dir / f"{brand}-{tool}.pptx"
        shutil.copy2(pptx, dest)
        count += 1

    gallery_src = dist / "gallery.html"
    if not gallery_src.is_file():
        raise SystemExit(
            f"ebdeck: {gallery_src} does not exist. Run `ebdeck gallery build` first."
        )
    shutil.copy2(gallery_src, package_dir / "gallery.html")

    # zip the flat contents
    files = sorted([p.name for p in package_dir.glob("*.pptx")]) + ["gallery.html"]
    subprocess.run(["zip", "-q", str(zip_path), *files], cwd=str(package_dir), check=True)

    size = _human_size(zip_path.stat().st_size)
    typer.echo(f"✓ dist/earlbear-decks.zip ({count} decks + gallery, {size})")


def _human_size(n: int) -> str:
    for unit in ("B", "K", "M", "G"):
        if n < 1024:
            return f"{n:.0f}{unit}"
        n //= 1024  # type: ignore[assignment]
    return f"{n}T"
