"""Mermaid diagram rendering for ebdocs sync.

Rendering happens host-side (outside the main ebdocs container) via
either local `mmdc` or the `ebdocs-mermaid` sidecar image, invoked by
`bin/ebdocs` as a pre-render pass before launching the main container,
or by running `docs/scripts/render_mermaid.py` directly. The main
ebdocs image itself never renders mermaid — it only reads already-
rendered PNGs from the `.assets/` cache.

When a cache miss reaches the main container (cloud context with no
host docker, or local dev where neither mmdc nor the sidecar is
available), `render_fallback` raises `MermaidRenderError` and the
sync engine falls back to embedding the raw mermaid source as a
syntax-highlighted code block in the Drive doc (see
`_resolve_deferred_images` in sync_engine.py for the degradation path).

Caching: rendered images are stored under `{md_source_dir}/.assets/`
keyed by sha256 of the source.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path


class MermaidRenderError(Exception):
    """Raised when mermaid rendering fails."""


def is_mmdc_available() -> bool:
    """Check if the mmdc CLI is on PATH."""
    return shutil.which("mmdc") is not None


def source_hash(source: str) -> str:
    """Return a short stable hash for a mermaid source string."""
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]


def render_to_png(source: str, output_path: Path) -> Path:
    """Render mermaid source to a PNG file using the host-side mmdc CLI.

    Raises:
        MermaidRenderError: If mmdc is missing or rendering fails.
    """
    if not is_mmdc_available():
        raise MermaidRenderError(
            "mmdc CLI not found on PATH. Install with: "
            "npm install -g @mermaid-js/mermaid-cli"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".mmd", delete=False) as tmp:
        tmp.write(source)
        tmp_path = Path(tmp.name)

    try:
        result = subprocess.run(
            ["mmdc", "-i", str(tmp_path), "-o", str(output_path), "-b", "transparent"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise MermaidRenderError(
                f"mmdc failed (exit {result.returncode}): "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
        if not output_path.exists():
            raise MermaidRenderError(f"mmdc did not produce output file: {output_path}")
        return output_path
    finally:
        tmp_path.unlink(missing_ok=True)


def render_fallback(source: str, out_path: Path) -> Path:
    """Render mermaid source using the only in-process backend available.

    This function runs *inside* the main ebdocs container and only tries
    host-side `mmdc` if it happens to be on PATH (which in practice it
    is not — the main image does not ship Node or Chromium). Every other
    rendering path lives outside the main container: either the bin/ebdocs
    host wrapper pre-renders before launching, or `docs/scripts/render_mermaid.py`
    is run manually by the author.

    Raises MermaidRenderError when no backend succeeds. Callers in
    `sync_engine._resolve_deferred_images` catch this and fall back to
    embedding the raw mermaid source as a syntax-highlighted code block
    in the Drive doc, so cloud-context renders (no host docker, no mmdc)
    still produce a coherent doc with the diagram source preserved.
    """
    if is_mmdc_available():
        return render_to_png(source, out_path)
    raise MermaidRenderError(
        "mermaid cache miss and no in-container renderer available. "
        "Run docs/scripts/render_mermaid.py on the host before pushing, "
        "or let bin/ebdocs pre-render automatically on `sync push`."
    )


def render_or_cache(source: str, cache_dir: Path) -> Path:
    """Render a mermaid source to PNG, reusing cached output if available."""
    h = source_hash(source)
    output = cache_dir / f"mermaid-{h}.png"
    if output.exists():
        return output
    return render_fallback(source, output)
