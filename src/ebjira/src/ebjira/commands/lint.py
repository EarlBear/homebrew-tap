"""Lint local Jira issue YAML files for structure and content gaps."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Annotated, Any, Optional

import typer
import yaml
from rich.table import Table

from ebjira.output import Format, console, output_result
from ebjira.sync_engine import _resolve_sync_base, summary_hash

lint_app = typer.Typer(
    name="lint",
    help="Lint local issue YAML for structure and content gaps.",
    no_args_is_help=True,
)


SEVERITY_ORDER = {"info": 0, "warn": 1, "error": 2}
# As-a/GWT story format applies to Stories only (project tenet #10 in CLAUDE.md).
# Features, Deliverables, Epics, Tasks, Sub-tasks, Bugs use other shapes.
EXEMPT_TYPES = {"Sub-task", "Bug", "Epic", "Task", "Feature", "Deliverable"}

# Stale-summary applies to anything an agent might pick up. Sub-tasks are
# implementation details under a parent that already has a summary.
STALE_SUMMARY_EXEMPT_TYPES = {"Sub-task"}

KNOWN_RULES = {"structure", "stale-summary", "all"}


@dataclass
class Finding:
    rule: str
    severity: str
    message: str
    excerpt: str


def _excerpt(text: str, n: int = 80) -> str:
    text = text.strip().replace("\n", " ")
    return text[:n] + ("…" if len(text) > n else "")


def check_structure(description: str) -> list[Finding]:
    """Detect structure/content gaps in a story description."""
    findings: list[Finding] = []
    if not description or not description.strip():
        findings.append(Finding("missing-user-story", "error", "Empty description", ""))
        findings.append(Finding("missing-gwt", "error", "No Given/When/Then scenarios", ""))
        return findings

    lines = description.splitlines()
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", description) if p.strip()]

    has_user_story_heading = any(re.match(r"^##\s*User Story", ln, re.I) for ln in lines)
    has_as_a = any(re.search(r"\bAs an?\b.*\bI want\b", ln, re.I) for ln in lines)
    if not (has_user_story_heading or has_as_a):
        findings.append(Finding(
            "missing-user-story", "error",
            "No '## User Story' heading or 'As a … I want …' statement",
            _excerpt(paragraphs[0]) if paragraphs else "",
        ))

    has_given = any(re.match(r"^\s*Given\b", ln, re.I) for ln in lines)
    has_when = any(re.match(r"^\s*When\b", ln, re.I) for ln in lines)
    has_then = any(re.match(r"^\s*Then\b", ln, re.I) for ln in lines)
    if not (has_given and has_when and has_then):
        findings.append(Finding(
            "missing-gwt", "error",
            "No Given/When/Then acceptance scenarios",
            "",
        ))

    heading_count = sum(1 for ln in lines if re.match(r"^#{2,3}\s", ln))
    bullet_count = sum(1 for ln in lines if re.match(r"^\s*[-*]\s", ln))
    if len(paragraphs) >= 8 and heading_count == 0 and bullet_count == 0:
        findings.append(Finding(
            "wall-of-paragraphs", "warn",
            f"{len(paragraphs)} paragraphs with no headings or bullets",
            _excerpt(paragraphs[0]),
        ))

    # label-paragraph: short single-line paragraph ending in ':' followed by another paragraph
    for i, p in enumerate(paragraphs[:-1]):
        if "\n" in p:
            continue
        if len(p) > 60:
            continue
        if p.endswith(":") and not p.startswith(("-", "*", "#")):
            findings.append(Finding(
                "label-paragraph", "warn",
                "Label paragraph should be a '##' heading",
                _excerpt(p),
            ))

    # bare-enumeration: 3+ consecutive paragraphs starting with (1)/(a)/(i) parens patterns
    # (legitimate `1.` ordered lists are not flagged — those are valid markdown)
    enum_re = re.compile(r"^\s*\((\d+|[a-z]|[ivx]+)\)\s")
    run = 0
    run_start: str | None = None
    for p in paragraphs:
        first_line = p.splitlines()[0]
        if enum_re.match(first_line):
            if run == 0:
                run_start = first_line
            run += 1
            if run == 3:
                findings.append(Finding(
                    "bare-enumeration", "warn",
                    "Bare (1)/(a)/(i) enumeration should be a markdown list",
                    _excerpt(run_start or first_line),
                ))
        else:
            run = 0
            run_start = None

    # arrow-flow: line with 2+ arrows in prose, but NOT inside a Given/When/Then clause
    # or a markdown list/heading/code block
    gwt_re = re.compile(r"^\s*(Given|When|Then|And|But)\b", re.I)
    for ln in lines:
        arrows = ln.count(" → ") + ln.count(" -> ")
        stripped = ln.strip()
        if arrows >= 2 and not stripped.startswith(("-", "*", "#", "```")) \
                and not gwt_re.match(stripped):
            findings.append(Finding(
                "arrow-flow", "info",
                "Arrow flow in prose — consider bullet list or mermaid diagram",
                _excerpt(ln),
            ))
            break

    return findings


def check_stale_summary(summary: str, description: str, summary_ai: Any) -> list[Finding]:
    """Detect missing/stale/empty summary_ai blocks.

    Fires when:
      - summary_ai is missing entirely
      - summary_ai.text is empty
      - summary_ai.hash does not match md5(summary + "\\n" + description)
    """
    expected = summary_hash(summary, description)
    if not isinstance(summary_ai, dict):
        return [Finding("stale-summary", "warn", "Missing summary_ai block", expected[:12])]
    text = (summary_ai.get("text") or "").strip()
    actual = (summary_ai.get("hash") or "").strip().lower()
    if not text:
        return [Finding("stale-summary", "warn", "Empty summary_ai.text", expected[:12])]
    if actual != expected:
        return [Finding(
            "stale-summary", "warn",
            f"Hash mismatch (expected {expected[:12]}, got {(actual or 'null')[:12]})",
            _excerpt(text),
        )]
    return []


def _iter_issue_files(project: str, key: str | None) -> list[Path]:
    base = _resolve_sync_base() / project
    if not base.exists():
        raise typer.BadParameter(f"Project directory not found: {base}")
    files = sorted(base.rglob("*.yaml"))
    if key:
        files = [f for f in files if f.stem == key]
    return files


@lint_app.command("issues")
def lint_issues(
    project: Annotated[str, typer.Option("--project", "-p", help="Project key (e.g. EARL).")],
    rule: Annotated[str, typer.Option("--rule", "-r", help="Rule to run: structure | stale-summary | all.")] = "structure",
    severity: Annotated[str, typer.Option("--severity", "-s", help="Minimum severity: info|warn|error.")] = "info",
    key: Annotated[Optional[str], typer.Option("--key", "-k", help="Limit to a single issue key.")] = None,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.json,
) -> None:
    """Lint local issue YAML for structure gaps."""
    if rule not in KNOWN_RULES:
        raise typer.BadParameter(f"Unknown rule: {rule}")

    run_structure = rule in ("structure", "all")
    run_stale = rule in ("stale-summary", "all")

    min_sev = SEVERITY_ORDER.get(severity, 0)
    files = _iter_issue_files(project, key)

    results: list[dict] = []
    for f in files:
        try:
            data = yaml.safe_load(f.read_text()) or {}
        except yaml.YAMLError:
            continue
        itype = data.get("type", "")
        description = data.get("description", "") or ""
        summary = data.get("summary", "") or ""

        raw: list[Finding] = []
        if run_structure and itype not in EXEMPT_TYPES:
            raw.extend(check_structure(description))
        if run_stale and itype not in STALE_SUMMARY_EXEMPT_TYPES:
            raw.extend(check_stale_summary(summary, description, data.get("summary_ai")))

        findings = [
            asdict(fnd) for fnd in raw
            if SEVERITY_ORDER.get(fnd.severity, 0) >= min_sev
        ]
        if findings:
            results.append({
                "key": data.get("key", f.stem),
                "type": itype,
                "parent": data.get("parent", ""),
                "summary": data.get("summary", ""),
                "findings": findings,
            })

    if format == Format.table:
        if not results:
            console.print("[green]No findings.[/green]")
        else:
            table = Table(title=f"Lint findings — {project}")
            table.add_column("Key", style="cyan")
            table.add_column("Type")
            table.add_column("Rule", style="yellow")
            table.add_column("Sev")
            table.add_column("Message")
            table.add_column("Excerpt", style="dim")
            for r in results:
                for fnd in r["findings"]:
                    table.add_row(
                        r["key"], r["type"], fnd["rule"],
                        fnd["severity"], fnd["message"], fnd["excerpt"],
                    )
            console.print(table)
            console.print(f"\n[bold]{len(results)}[/bold] issues with findings")
    else:
        output_result(results, format=format)

    if results:
        raise typer.Exit(code=1)
