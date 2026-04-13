#!/usr/bin/env python3
"""
Generate PNG thumbnails from all PPTX files in dist/output/.

Strategy: PPTX → PDF (via LibreOffice) → PNG per page (via pdftoppm or Pillow).
LibreOffice's direct PPTX→PNG only exports the first slide, so we go through PDF.

Output: dist/thumbnails/{brand}/{tool}/slide-{N}.png

Usage:
    python generate-thumbnails.py [--first-only] [--width 400]
"""

import os
import sys
import glob
import subprocess
import tempfile
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    Image = None

DIST_DIR = os.environ.get("DIST_DIR", "/data/dist")
OUTPUT_DIR = os.path.join(DIST_DIR, "output")
THUMB_DIR = os.path.join(DIST_DIR, "thumbnails")

FIRST_ONLY = "--first-only" in sys.argv
THUMB_WIDTH = 400

for i, arg in enumerate(sys.argv):
    if arg == "--width" and i + 1 < len(sys.argv):
        THUMB_WIDTH = int(sys.argv[i + 1])


def convert_pptx_to_pngs(pptx_path, out_dir):
    """Convert PPTX → PDF → PNGs for all slides."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Step 1: PPTX → PDF via LibreOffice
        cmd_pdf = [
            "libreoffice",
            "--headless",
            "--convert-to", "pdf",
            "--outdir", tmpdir,
            pptx_path,
        ]
        result = subprocess.run(cmd_pdf, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            print(f"  ✗ PDF conversion failed: {result.stderr[:200]}", file=sys.stderr)
            return []

        # Find the generated PDF
        pdfs = glob.glob(os.path.join(tmpdir, "*.pdf"))
        if not pdfs:
            print(f"  ✗ No PDF generated", file=sys.stderr)
            return []
        pdf_path = pdfs[0]

        # Step 2: PDF → PNGs
        # Try pdftoppm first (faster, better quality), fall back to LibreOffice
        png_dir = os.path.join(tmpdir, "pngs")
        os.makedirs(png_dir, exist_ok=True)

        pngs = try_pdftoppm(pdf_path, png_dir) or try_libreoffice_png(pdf_path, png_dir)

        if not pngs:
            print(f"  ✗ No PNGs generated from PDF", file=sys.stderr)
            return []

        os.makedirs(out_dir, exist_ok=True)
        saved = []

        for i, png_path in enumerate(pngs):
            if FIRST_ONLY and i >= 1:
                break

            dest = os.path.join(out_dir, f"slide-{i + 1}.png")

            if Image:
                img = Image.open(png_path)
                ratio = THUMB_WIDTH / img.width
                new_height = int(img.height * ratio)
                img = img.resize((THUMB_WIDTH, new_height), Image.LANCZOS)
                img.save(dest, "PNG", optimize=True)
            else:
                shutil.copy2(png_path, dest)

            saved.append(dest)

        return saved


def try_pdftoppm(pdf_path, png_dir):
    """Use pdftoppm (from poppler-utils) to convert PDF pages to PNGs."""
    try:
        cmd = [
            "pdftoppm",
            "-png",
            "-r", "150",  # 150 DPI — good enough for thumbnails
            pdf_path,
            os.path.join(png_dir, "slide"),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            pngs = sorted(glob.glob(os.path.join(png_dir, "slide-*.png")))
            if pngs:
                return pngs
    except FileNotFoundError:
        pass
    return None


def try_libreoffice_png(pdf_path, png_dir):
    """Fallback: use LibreOffice to convert PDF → PNG (only gets first page)."""
    cmd = [
        "libreoffice",
        "--headless",
        "--convert-to", "png",
        "--outdir", png_dir,
        pdf_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode == 0:
        pngs = sorted(glob.glob(os.path.join(png_dir, "*.png")))
        if pngs:
            return pngs
    return None


def main():
    if not os.path.isdir(OUTPUT_DIR):
        print(f"✗ Output directory not found: {OUTPUT_DIR}")
        sys.exit(1)

    pptx_files = sorted(glob.glob(os.path.join(OUTPUT_DIR, "*", "*", "*.pptx")))
    total = len(pptx_files)

    if total == 0:
        print("✗ No PPTX files found in dist/output/")
        sys.exit(1)

    MAX_WORKERS = 3  # LibreOffice supports parallel (unlike Chromium)

    print(f"━━━ Thumbnail Generator ━━━")
    print(f"PPTX files: {total}")
    print(f"Mode: {'first slide only' if FIRST_ONLY else 'all slides'}")
    print(f"Width: {THUMB_WIDTH}px")
    print(f"Workers: {MAX_WORKERS}")
    print()

    counter_lock = threading.Lock()
    done = 0
    failed = 0

    def process_one(pptx_path):
        nonlocal done, failed
        rel = os.path.relpath(pptx_path, OUTPUT_DIR)
        parts = rel.split(os.sep)
        if len(parts) < 3:
            return

        brand, tool = parts[0], parts[1]
        thumb_out = os.path.join(THUMB_DIR, brand, tool)

        # Skip if cached
        existing = os.path.join(thumb_out, "slide-1.png")
        if os.path.exists(existing):
            pptx_mtime = os.path.getmtime(pptx_path)
            thumb_mtime = os.path.getmtime(existing)
            if thumb_mtime >= pptx_mtime:
                num_cached = len(glob.glob(os.path.join(thumb_out, "slide-*.png")))
                with counter_lock:
                    done += 1
                    print(f"  [{done + failed}/{total}] {brand}/{tool} (cached, {num_cached} slides)")
                return

        saved = convert_pptx_to_pngs(pptx_path, thumb_out)
        with counter_lock:
            if saved:
                done += 1
                print(f"  [{done + failed}/{total}] {brand}/{tool} → {len(saved)} slide(s)")
            else:
                failed += 1
                print(f"  [{done + failed}/{total}] {brand}/{tool} ✗ FAILED")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(process_one, p) for p in pptx_files]
        for f in as_completed(futures):
            f.result()  # raise any exceptions

    print()
    print(f"✓ Thumbnails: {done} success, {failed} failed")
    print(f"  Output: {THUMB_DIR}/")


if __name__ == "__main__":
    main()
