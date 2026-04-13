"""KB back-references CLI — doc-to-doc and doc-to-Jira link management.

This command group manages the `refs:` (intra-KB) and `specifies:` (doc->Jira)
frontmatter fields across the content repo, and maintains per-subtree
`links.yaml` indexes that act as a reverse-lookup cache.

Scope / layout:
  - `{CONTENT_DIR}/gdocs/knowledge-base/links.yaml`  — doc_to_docs + doc_to_jira
  - `{CONTENT_DIR}/jira/links.yaml`                  — jira_to_docs (reverse view)

Source of truth is doc frontmatter. The indexes are generated and validated;
`ebdocs links rebuild` regenerates them, `ebdocs links validate` confirms they
are in sync and all ref targets resolve.

Design decisions (iteration 3 of the EARL grooming campaign):
  Q5  broken refs FAIL pre-commit; `links rename` is the escape hatch.
  Q6  `specifies:` (doc->Jira) and `refs:` (doc->doc) are separate namespaces.
  Q7  no live Jira check in pre-commit; `validate --live` for manual/CI use.
  Q8  hook FAILS on stale index; user runs `links rebuild`.
  Q9  per-subtree indexes; no repo-root file.

Ref path convention: `refs:` entries are KB-root-relative slugs (no .md suffix),
e.g. `tech-designs/shopify-agent/overview`. `specifies:` entries are bare Jira
keys like `EARL-99`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

import typer
import yaml

from ebdocs.output import Format, output_error, output_result
from ebdocs.sync_engine import split_frontmatter, join_frontmatter

app = typer.Typer(
    name="links",
    help="Manage KB back-references (refs:, specifies:) and per-subtree indexes",
    no_args_is_help=True,
)


# ── Constants ──

KB_SUBTREE = "gdocs/knowledge-base"
JIRA_SUBTREE = "jira"
GDOCS_ROOT = "gdocs"  # specifies: scanned across all gdocs/**


# ── Helpers ──


def _content_dir() -> Path:
    cd = os.environ.get("CONTENT_DIR")
    if not cd:
        output_error(
            error="CONTENT_DIR_UNSET",
            message="CONTENT_DIR env var must point to the earlbear-content repo",
        )
    p = Path(cd)
    if not p.is_dir():
        output_error(
            error="CONTENT_DIR_INVALID",
            message=f"CONTENT_DIR does not exist: {p}",
        )
    return p


def _iter_md(root: Path):
    """Yield all .md files under root."""
    if not root.is_dir():
        return
    for p in sorted(root.rglob("*.md")):
        yield p


def _rel_slug(md_path: Path, base: Path) -> str:
    """Convert an .md file path to a base-relative slug (no suffix)."""
    rel = md_path.relative_to(base).with_suffix("")
    return rel.as_posix()


def _load_fm(md_path: Path) -> dict:
    try:
        fm, _ = split_frontmatter(md_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return fm or {}


def _normalize_list(value) -> list[str]:
    """Coerce a frontmatter field to a list of stripped strings."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()]
    if isinstance(value, list):
        return [str(v).strip() for v in value if v is not None and str(v).strip()]
    return []


def _scan_docs(content: Path) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Scan gdocs for refs: and specifies: frontmatter.

    Returns:
        (doc_refs, doc_specs) where:
            doc_refs: KB-slug -> sorted list of KB-slug targets (intra-KB only)
            doc_specs: gdocs-path-slug -> sorted list of Jira keys
    """
    kb_root = content / KB_SUBTREE
    gdocs_root = content / GDOCS_ROOT

    doc_refs: dict[str, list[str]] = {}
    doc_specs: dict[str, list[str]] = {}

    for md in _iter_md(gdocs_root):
        fm = _load_fm(md)
        if not fm:
            continue

        # specifies: applies to any gdocs/**.md
        specs = _normalize_list(fm.get("specifies"))
        if specs:
            slug = _rel_slug(md, content)  # e.g. gdocs/knowledge-base/foo/bar
            doc_specs[slug] = sorted(set(specs))

        # refs: only meaningful under knowledge-base/
        try:
            md.relative_to(kb_root)
            is_kb = True
        except ValueError:
            is_kb = False
        if is_kb:
            refs = _normalize_list(fm.get("refs"))
            if refs:
                kb_slug = _rel_slug(md, kb_root)
                doc_refs[kb_slug] = sorted(set(refs))

    return doc_refs, doc_specs


def _build_indexes(content: Path) -> tuple[dict, dict]:
    """Build the two per-subtree index dicts from frontmatter scan."""
    doc_refs, doc_specs = _scan_docs(content)

    # KB index: doc_to_docs + doc_to_jira (only KB-side specifies)
    kb_specs = {
        k.removeprefix(KB_SUBTREE + "/"): v
        for k, v in doc_specs.items()
        if k.startswith(KB_SUBTREE + "/")
    }

    kb_index: dict = {
        "doc_to_docs": {k: {"refs": v} for k, v in sorted(doc_refs.items())},
        "doc_to_jira": {k: {"specifies": v} for k, v in sorted(kb_specs.items())},
    }

    # Jira reverse index: any gdocs doc -> Jira
    jira_to_docs: dict[str, list[str]] = {}
    for doc_slug, keys in doc_specs.items():
        for k in keys:
            jira_to_docs.setdefault(k, []).append(doc_slug)
    jira_index: dict = {
        "jira_to_docs": {
            k: {"specified_by": sorted(set(v))}
            for k, v in sorted(jira_to_docs.items())
        }
    }

    return kb_index, jira_index


def _dump_yaml(data: dict) -> str:
    return yaml.safe_dump(
        data,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _kb_index_path(content: Path) -> Path:
    return content / KB_SUBTREE / "links.yaml"


def _jira_index_path(content: Path) -> Path:
    return content / JIRA_SUBTREE / "links.yaml"


def _kb_doc_exists(content: Path, kb_slug: str) -> bool:
    return (content / KB_SUBTREE / f"{kb_slug}.md").is_file()


# ── Commands ──


@app.command("validate")
def validate(
    live: bool = typer.Option(
        False, "--live", help="Also validate Jira keys in specifies: via live API call"
    ),
    subtree: Optional[str] = typer.Option(
        None, "--subtree", help="Limit to one subtree (gdocs/knowledge-base or jira)"
    ),
    format: Format = typer.Option(Format.json, "--format", "-f"),
) -> None:
    """Validate refs: and specifies: frontmatter.

    Fails (exit 1) if:
      - Any refs: target does not resolve to an existing KB .md file.
      - The on-disk links.yaml index is stale vs a fresh scan (run `links rebuild`).
      - `--live` is set and a specifies: key is not found in Jira.
    """
    content = _content_dir()
    doc_refs, doc_specs = _scan_docs(content)

    broken_refs: list[dict] = []
    for src, targets in doc_refs.items():
        for t in targets:
            if not _kb_doc_exists(content, t):
                broken_refs.append({"source": src, "target": t})

    # Index freshness check
    fresh_kb, fresh_jira = _build_indexes(content)
    stale_indexes: list[str] = []

    if subtree in (None, KB_SUBTREE):
        on_disk = _read_yaml(_kb_index_path(content))
        if on_disk != fresh_kb:
            stale_indexes.append(str(_kb_index_path(content).relative_to(content)))

    if subtree in (None, JIRA_SUBTREE):
        on_disk = _read_yaml(_jira_index_path(content))
        if on_disk != fresh_jira:
            stale_indexes.append(str(_jira_index_path(content).relative_to(content)))

    # Live Jira check
    missing_jira: list[str] = []
    if live:
        missing_jira = _live_validate_jira(
            sorted({k for keys in doc_specs.values() for k in keys})
        )

    result = {
        "broken_refs": broken_refs,
        "stale_indexes": stale_indexes,
        "missing_jira": missing_jira,
        "scanned": {
            "docs_with_refs": len(doc_refs),
            "docs_with_specifies": len(doc_specs),
        },
    }

    ok = not (broken_refs or stale_indexes or missing_jira)
    result["ok"] = ok
    output_result(result, format=format)
    if not ok:
        raise typer.Exit(code=1)


def _live_validate_jira(keys: list[str]) -> list[str]:
    """Hit Jira REST API directly via httpx and return keys that don't exist."""
    if not keys:
        return []
    try:
        import httpx
    except ImportError:
        return []

    base = os.environ.get("JIRA_BASE_URL") or os.environ.get("JIRA_URL")
    email = os.environ.get("JIRA_EMAIL")
    token = os.environ.get("JIRA_API_TOKEN")
    if not (base and email and token):
        # Can't validate; return empty rather than fail
        print(
            "WARN: --live set but JIRA_BASE_URL/JIRA_EMAIL/JIRA_API_TOKEN not configured; skipping live check",
            file=sys.stderr,
        )
        return []

    missing: list[str] = []
    base = base.rstrip("/")
    with httpx.Client(auth=(email, token), timeout=15.0) as client:
        for k in keys:
            try:
                r = client.get(f"{base}/rest/api/3/issue/{k}", params={"fields": "summary"})
                if r.status_code == 404:
                    missing.append(k)
            except Exception:
                # Network failure: don't block, report as missing=[] but warn
                print(f"WARN: live check for {k} failed: transport error", file=sys.stderr)
    return missing


@app.command("rename")
def rename(
    old: str = typer.Argument(..., help="Old KB slug (e.g. tech-designs/shopify-agent)"),
    new: str = typer.Argument(..., help="New KB slug"),
    subtree: Optional[str] = typer.Option(None, "--subtree"),
    apply: bool = typer.Option(False, "--apply", help="Actually rewrite files (default: dry-run)"),
    format: Format = typer.Option(Format.json, "--format", "-f"),
) -> None:
    """Rewrite every refs: entry pointing at <old> to <new>.

    Dry-run by default. Use --apply to persist changes.
    """
    content = _content_dir()
    kb_root = content / KB_SUBTREE

    changes: list[dict] = []
    for md in _iter_md(kb_root):
        fm, body = split_frontmatter(md.read_text(encoding="utf-8"))
        if not fm:
            continue
        refs = _normalize_list(fm.get("refs"))
        if old not in refs:
            continue
        new_refs = [new if r == old else r for r in refs]
        # Dedupe while preserving order
        seen = set()
        deduped = []
        for r in new_refs:
            if r not in seen:
                deduped.append(r)
                seen.add(r)
        fm["refs"] = deduped
        changes.append(
            {
                "file": str(md.relative_to(content)),
                "before": refs,
                "after": deduped,
            }
        )
        if apply:
            md.write_text(join_frontmatter(fm, body), encoding="utf-8")

    output_result(
        {"applied": apply, "old": old, "new": new, "changes": changes, "count": len(changes)},
        format=format,
    )


@app.command("show")
def show(
    path: str = typer.Argument(..., help="KB slug or doc path to look up"),
    format: Format = typer.Option(Format.json, "--format", "-f"),
) -> None:
    """Print inbound refs (who points at this doc) via the KB index."""
    content = _content_dir()
    kb_index = _read_yaml(_kb_index_path(content))
    jira_index = _read_yaml(_jira_index_path(content))

    # Normalize input: strip .md, strip gdocs/knowledge-base/ prefix
    slug = path.removesuffix(".md")
    slug = slug.removeprefix(KB_SUBTREE + "/")

    doc_to_docs = (kb_index.get("doc_to_docs") or {})
    inbound_docs = [src for src, entry in doc_to_docs.items()
                    if slug in (entry or {}).get("refs", [])]

    doc_to_jira = (kb_index.get("doc_to_jira") or {}).get(slug) or {}
    outbound_jira = doc_to_jira.get("specifies", [])

    jira_to_docs = jira_index.get("jira_to_docs") or {}

    output_result(
        {
            "slug": slug,
            "inbound_refs_from_docs": sorted(inbound_docs),
            "outbound_specifies": outbound_jira,
            "jira_reverse_entries": {
                k: v for k, v in jira_to_docs.items() if k in outbound_jira
            },
        },
        format=format,
    )


@app.command("rebuild")
def rebuild(
    subtree: Optional[str] = typer.Option(None, "--subtree"),
    format: Format = typer.Option(Format.json, "--format", "-f"),
) -> None:
    """Regenerate per-subtree links.yaml indexes from frontmatter."""
    content = _content_dir()
    kb_index, jira_index = _build_indexes(content)

    written: list[str] = []

    if subtree in (None, KB_SUBTREE):
        path = _kb_index_path(content)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_dump_yaml(kb_index), encoding="utf-8")
        written.append(str(path.relative_to(content)))

    if subtree in (None, JIRA_SUBTREE):
        path = _jira_index_path(content)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_dump_yaml(jira_index), encoding="utf-8")
        written.append(str(path.relative_to(content)))

    output_result(
        {
            "written": written,
            "kb_doc_to_docs": len(kb_index.get("doc_to_docs") or {}),
            "kb_doc_to_jira": len(kb_index.get("doc_to_jira") or {}),
            "jira_to_docs": len(jira_index.get("jira_to_docs") or {}),
        },
        format=format,
    )


@app.command("bootstrap")
def bootstrap(
    format: Format = typer.Option(Format.json, "--format", "-f"),
) -> None:
    """Migrate the legacy repo-root links.yaml into per-subtree indexes.

    Reads `{CONTENT_DIR}/links.yaml` (legacy `jira_to_gdocs` schema),
    rebuilds the per-subtree indexes from current frontmatter (source of
    truth), then deletes the legacy root file. Idempotent — safe to run
    when the legacy file is already gone.
    """
    content = _content_dir()
    legacy = content / "links.yaml"

    legacy_data = _read_yaml(legacy) if legacy.exists() else {}
    legacy_jira_to_gdocs = (legacy_data.get("jira_to_gdocs") or {}) if legacy_data else {}

    # Compute fresh indexes from frontmatter (the source of truth)
    kb_index, jira_index = _build_indexes(content)

    # Diff: entries in legacy not reflected in fresh jira_index
    fresh_jira = jira_index.get("jira_to_docs") or {}
    missing_in_fresh: dict[str, list[str]] = {}
    for k, docs in legacy_jira_to_gdocs.items():
        fresh_entry = (fresh_jira.get(k) or {}).get("specified_by", [])
        missing = [d for d in docs if d not in fresh_entry]
        if missing:
            missing_in_fresh[k] = missing

    # Write fresh indexes
    _kb_index_path(content).parent.mkdir(parents=True, exist_ok=True)
    _kb_index_path(content).write_text(_dump_yaml(kb_index), encoding="utf-8")
    _jira_index_path(content).parent.mkdir(parents=True, exist_ok=True)
    _jira_index_path(content).write_text(_dump_yaml(jira_index), encoding="utf-8")

    # Delete legacy file
    deleted = False
    if legacy.exists():
        legacy.unlink()
        deleted = True

    output_result(
        {
            "legacy_deleted": deleted,
            "legacy_path": str(legacy.relative_to(content)),
            "legacy_entries": sum(len(v) for v in legacy_jira_to_gdocs.values()),
            "missing_in_fresh": missing_in_fresh,
            "written": [
                str(_kb_index_path(content).relative_to(content)),
                str(_jira_index_path(content).relative_to(content)),
            ],
        },
        format=format,
    )
