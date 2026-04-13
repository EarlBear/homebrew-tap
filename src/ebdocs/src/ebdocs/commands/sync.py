"""Sync commands — bidirectional YAML+MD sync with Google Drive.

Pulls docs under a Drive folder to local YAML+MD pairs (one YAML + one .md per doc),
diffs local vs Drive, pushes changes (content + metadata + folder moves).

Examples:
    ebdocs sync pull
    ebdocs sync pull --dry-run
    ebdocs sync diff
    ebdocs sync push --dry-run
    ebdocs sync push --file gdocs/knowledge-base/foo/bar.md
    ebdocs sync create ./new-doc.md --folder knowledge-base/runbooks --jira EARL-191
    ebdocs sync link --doc gdocs/knowledge-base/foo/bar --jira EARL-101
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer

from ebdocs.client import get_client
from ebdocs.output import Format, output_result

sync_app = typer.Typer(no_args_is_help=True)


@sync_app.command()
def pull(
    root_folder_id: Annotated[Optional[str], typer.Option("--root-folder-id", help="Drive root folder (defaults to GOOGLE_DRIVE_FOLDER_ID).")] = None,
    sync_root_name: Annotated[Optional[str], typer.Option("--sync-root", help="Subfolder name to mirror (defaults to 'knowledge-base').")] = None,
    include_sharing: Annotated[bool, typer.Option("--include-sharing", help="Fetch sharing permissions (slower).")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without writing files.")] = False,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", "-j", help="Comma-separated fields.")] = None,
) -> None:
    """Pull Google Docs from Drive into local YAML+MD files.

    Mirrors the Drive folder hierarchy under the sync base directory.
    Each doc becomes a {slug}.yaml (metadata) + {slug}.md (content) pair.

    Examples:
        ebdocs sync pull
        ebdocs sync pull --dry-run
        ebdocs sync pull --include-sharing
    """
    from ebdocs.sync_engine import pull_docs

    client = get_client()
    result = pull_docs(
        client,
        root_folder_id=root_folder_id,
        sync_root_name=sync_root_name,
        include_sharing=include_sharing,
        dry_run=dry_run,
    )
    output_result(result, format=format, json_fields=json_fields)


@sync_app.command()
def push(
    files: Annotated[Optional[list[str]], typer.Option("--file", help="Specific .md or .yaml file(s) to push (repeatable).")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview changes without pushing.")] = False,
    strict: Annotated[bool, typer.Option("--no-strict/--strict", help="Post-push validation. Default: on. Pass --no-strict to skip.")] = True,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", "-j", help="Comma-separated fields.")] = None,
) -> None:
    """Push local YAML+MD changes to Google Drive.

    For each local doc:
    - New (no id): creates doc in target folder, assigns id
    - Content hash differs from stored: writes markdown to Drive
    - Title differs: renames
    - folder_path differs: moves to target folder

    By default, every doc that was pushed is validated post-push via the
    same checks as `ebdocs doc validate`. If any doc has issues, the command
    exits non-zero so CI/automation can gate on it. Pass --no-strict to skip
    validation (e.g. for scratch docs).

    Examples:
        ebdocs sync push --dry-run
        ebdocs sync push
        ebdocs sync push --file gdocs/knowledge-base/foo/bar.md
        ebdocs sync push --no-strict
    """
    from ebdocs.sync_engine import push_docs

    client = get_client()
    result = push_docs(client, files=files, dry_run=dry_run)

    if strict and not dry_run:
        from ebdocs.commands.doc import collect_doc_issues
        from pathlib import Path as _Path

        pushed_ids: list[str] = []
        for r in (result.get("results") or []):
            if isinstance(r, str):
                pushed_ids.append(r)
            elif isinstance(r, dict) and r.get("id"):
                pushed_ids.append(r["id"])

        # Map each pushed id back to its source .md path if we can
        # infer it from the --file args (enables source-vs-rendered checks).
        source_for_id: dict[str, _Path] = {}
        if files:
            # Each --file arg maps to one doc via the yaml file. Cheap
            # heuristic: load each yaml, read `id`, map to the .md path.
            import yaml as _yaml
            for f in files:
                fp = _Path(f)
                if fp.suffix == ".md":
                    yp = fp.with_suffix(".yaml")
                else:
                    yp = fp
                if not yp.exists():
                    continue
                try:
                    meta = _yaml.safe_load(yp.read_text()) or {}
                except Exception:
                    continue
                did = meta.get("id")
                md_path = yp.with_suffix(".md")
                if did and md_path.exists():
                    source_for_id[did] = md_path

        validation: list[dict] = []
        any_failed = False
        for did in pushed_ids:
            try:
                doc = client.get_document(did)
            except Exception as e:
                validation.append({"doc_id": did, "error": str(e), "passed": False})
                any_failed = True
                continue

            src = source_for_id.get(did)
            issues, checks_run, _ = collect_doc_issues(doc, source_path=src)
            # Advisory-only issue kinds don't fail strict push. The
            # degraded_mermaid_rendering kind in particular is the
            # documented cloud-context behavior (no host mmdc / sidecar
            # available), so reporting it is informational.
            _ADVISORY_KINDS = {"degraded_mermaid_rendering"}
            failing_issues = [i for i in issues if i.get("kind") not in _ADVISORY_KINDS]
            validation.append({
                "doc_id": did,
                "url": f"https://docs.google.com/document/d/{did}/edit",
                "source": str(src) if src else None,
                "checks_run": checks_run,
                "passed": len(failing_issues) == 0,
                "issue_count": len(issues),
                "issues": issues,
            })
            if failing_issues:
                any_failed = True

        result["validation"] = validation
        output_result(result, format=format, json_fields=json_fields)
        if any_failed:
            raise typer.Exit(2)
        return

    output_result(result, format=format, json_fields=json_fields)


def _run_doc_checks(doc: dict) -> list[dict]:
    """Run the same invariants as `ebdocs doc validate` against a doc dict.

    Extracted so `sync push` strict validation can validate without re-fetching.
    Returns a list of issue dicts (empty = clean).
    """
    import re as _re
    body = doc.get("body", {}).get("content", [])
    issues: list[dict] = []
    last_heading_level = 0
    for el in body:
        para = el.get("paragraph")
        if not para:
            continue
        style = para.get("paragraphStyle", {})
        named = style.get("namedStyleType", "NORMAL_TEXT")
        bullet = para.get("bullet")
        text = "".join(
            r.get("textRun", {}).get("content", "")
            for r in para.get("elements", [])
        ).strip()

        if named.startswith("HEADING") and bullet is not None:
            issues.append({
                "kind": "heading_with_bullet",
                "level": named.replace("HEADING_", ""),
                "text": text[:60],
                "list_id": bullet.get("listId", ""),
            })

        if named.startswith("HEADING"):
            try:
                level = int(named.replace("HEADING_", ""))
            except ValueError:
                level = 0
            if level > 0 and last_heading_level > 0 and level > last_heading_level + 1:
                issues.append({
                    "kind": "heading_level_skip",
                    "from": last_heading_level,
                    "to": level,
                    "text": text[:60],
                })
            if level > 0:
                last_heading_level = level

        for run in para.get("elements", []):
            tr = run.get("textRun")
            if not tr:
                continue
            content = tr.get("content", "")
            link_url = tr.get("textStyle", {}).get("link", {}).get("url", "")
            for m in _re.finditer(r"\bEARL-\d+\b", content):
                key = m.group(0)
                if not link_url or "atlassian.net/browse/" not in link_url:
                    issues.append({
                        "kind": "earl_key_not_linked",
                        "key": key,
                        "context": content.strip()[:60],
                    })

    return issues


@sync_app.command("diff")
def diff_cmd(
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", "-j", help="Comma-separated fields.")] = None,
) -> None:
    """Compare local YAML+MD files against live Drive state.

    Shows which docs have local modifications (content, title, folder),
    which exist only locally (new, pending push), etc.

    Examples:
        ebdocs sync diff
    """
    from ebdocs.sync_engine import diff_docs

    client = get_client()
    result = diff_docs(client)
    output_result(result, format=format, json_fields=json_fields)


@sync_app.command()
def create(
    md_path: Annotated[str, typer.Argument(help="Path to an existing .md file.")],
    folder: Annotated[Optional[str], typer.Option("--folder", help="Drive folder_path for the new doc.")] = None,
    title: Annotated[Optional[str], typer.Option("--title", help="Doc title (defaults to filename).")] = None,
    jira: Annotated[Optional[list[str]], typer.Option("--jira", help="Jira issue key(s) to cross-link (repeatable).")] = None,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", "-j", help="Comma-separated fields.")] = None,
) -> None:
    """Create a new doc locally (YAML stub next to the .md file).

    This is a local operation. Run 'ebdocs sync push' afterward to create the
    doc on Drive.

    Examples:
        ebdocs sync create ./new-doc.md --folder knowledge-base/runbooks
        ebdocs sync create ./foo.md --jira EARL-101 --jira EARL-185
    """
    from ebdocs.sync_engine import create_doc_from_file

    result = create_doc_from_file(
        md_path=Path(md_path),
        title=title,
        folder_path=folder,
        jira_issues=jira,
    )
    output_result(result, format=format, json_fields=json_fields)


@sync_app.command()
def link(
    doc: Annotated[str, typer.Option("--doc", help="gdocs path (without .yaml suffix) to link.")],
    jira: Annotated[str, typer.Option("--jira", help="Jira issue key.")],
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", "-j", help="Comma-separated fields.")] = None,
) -> None:
    """Add a cross-link between a Jira issue and a local gdocs path.

    Updates links.yaml in the content repo root.

    Examples:
        ebdocs sync link --doc gdocs/knowledge-base/foo/bar --jira EARL-101
    """
    from ebdocs.links_registry import add_link

    path = add_link(jira, doc)
    output_result(
        {"action": "linked", "jira": jira, "gdocs": doc, "registry": str(path)},
        format=format,
        json_fields=json_fields,
    )


@sync_app.command("unlink")
def unlink_cmd(
    doc: Annotated[str, typer.Option("--doc", help="gdocs path (without .yaml suffix) to unlink.")],
    jira: Annotated[str, typer.Option("--jira", help="Jira issue key.")],
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", "-j", help="Comma-separated fields.")] = None,
) -> None:
    """Remove a Jira <-> gdocs cross-link from links.yaml.

    Examples:
        ebdocs sync unlink --doc gdocs/knowledge-base/foo/bar --jira EARL-101
    """
    from ebdocs.links_registry import remove_link

    path = remove_link(jira, doc)
    output_result(
        {"action": "unlinked", "jira": jira, "gdocs": doc, "registry": str(path)},
        format=format,
        json_fields=json_fields,
    )


@sync_app.command("list-links")
def list_links_cmd(
    jira: Annotated[Optional[str], typer.Option("--jira", help="Filter by Jira key.")] = None,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
    json_fields: Annotated[Optional[str], typer.Option("--json", "-j", help="Comma-separated fields.")] = None,
) -> None:
    """List cross-links from links.yaml.

    Examples:
        ebdocs sync list-links
        ebdocs sync list-links --jira EARL-101
    """
    from ebdocs.links_registry import load_registry, gdocs_for_jira

    if jira:
        result = {"jira": jira, "gdocs": gdocs_for_jira(jira)}
    else:
        result = load_registry()
    output_result(result, format=format, json_fields=json_fields)


@sync_app.command("preview")
def preview_cmd(
    md_path: Annotated[Optional[str], typer.Argument(help="Markdown file path. Omit to read from stdin.")] = None,
    code_only: Annotated[bool, typer.Option("--code-only", help="Only print fenced code blocks (skip prose).")] = False,
    no_color: Annotated[bool, typer.Option("--no-color", help="Disable ANSI colors (useful for piping).")] = False,
) -> None:
    """Preview markdown with terminal syntax highlighting.

    Renders the markdown to the terminal with ANSI color codes for fenced
    code blocks. Useful for verifying syntax highlighting before pushing to
    Drive — no Docker round-trip needed.

    Supports the same languages as the Drive sync push, including the custom
    Mermaid lexer (mermaid / mmd). Unknown languages render as plain monospace.

    Examples:
        ebdocs sync preview gdocs/knowledge-base/foo/bar.md
        cat doc.md | ebdocs sync preview
        ebdocs sync preview doc.md --code-only
        ebdocs sync preview doc.md --no-color | less
    """
    import re as _re
    import sys as _sys
    from pathlib import Path as _Path

    # Read input
    if md_path:
        text = _Path(md_path).read_text()
    else:
        text = _sys.stdin.read()

    # Strip frontmatter for cleaner preview
    fm_match = _re.match(r"^---\s*\n.*?\n---\s*\n", text, _re.DOTALL)
    if fm_match:
        text = text[fm_match.end():]

    # Find every fenced code block
    fence_re = _re.compile(r"^(```)([^\n]*)\n(.*?)\n```$", _re.MULTILINE | _re.DOTALL)

    try:
        from pygments import highlight as pyg_highlight
        from pygments.lexers import get_lexer_by_name
        from pygments.formatters import Terminal256Formatter
        from pygments.util import ClassNotFound
        # Ensure custom Mermaid lexer is registered
        from ebdocs import syntax_highlight  # noqa: F401
        formatter = Terminal256Formatter(style="monokai")
        pyg_available = True
    except ImportError:
        pyg_available = False

    def _colorize(code: str, lang: str) -> str:
        if no_color or not pyg_available or not lang:
            return code
        try:
            lexer = get_lexer_by_name(lang, stripall=False)
        except ClassNotFound:
            return code
        return pyg_highlight(code, lexer, formatter).rstrip()

    # ANSI color helpers (don't depend on pygments)
    def _ansi(text: str, code: str) -> str:
        if no_color:
            return text
        return f"\033[{code}m{text}\033[0m"

    BOLD = "1"
    DIM = "2"
    CYAN = "36"
    YELLOW = "33"
    GRAY = "90"

    if code_only:
        # Print only fenced blocks, with a header showing the language
        for match in fence_re.finditer(text):
            lang = match.group(2).strip() or "(none)"
            code = match.group(3)
            print(_ansi(f"─── {lang} ───", DIM + ";" + CYAN))
            print(_colorize(code, lang))
            print()
        return

    # Walk through text replacing fenced blocks with highlighted versions
    last_end = 0
    parts: list[str] = []
    for match in fence_re.finditer(text):
        # Prose between blocks — light styling for headings
        prose = text[last_end:match.start()]
        for line in prose.splitlines():
            if line.startswith("# "):
                parts.append(_ansi(line, BOLD + ";" + CYAN))
            elif line.startswith("## "):
                parts.append(_ansi(line, BOLD + ";" + YELLOW))
            elif line.startswith("### "):
                parts.append(_ansi(line, BOLD))
            else:
                parts.append(line)

        lang = match.group(2).strip() or ""
        code = match.group(3)
        # Render the fence with language label
        fence_marker = _ansi("```" + (lang or ""), DIM + ";" + GRAY)
        parts.append(fence_marker)
        parts.append(_colorize(code, lang))
        parts.append(_ansi("```", DIM + ";" + GRAY))
        last_end = match.end()

    # Trailing prose
    trailing = text[last_end:]
    for line in trailing.splitlines():
        if line.startswith("# "):
            parts.append(_ansi(line, BOLD + ";" + CYAN))
        elif line.startswith("## "):
            parts.append(_ansi(line, BOLD + ";" + YELLOW))
        elif line.startswith("### "):
            parts.append(_ansi(line, BOLD))
        else:
            parts.append(line)

    print("\n".join(parts))
