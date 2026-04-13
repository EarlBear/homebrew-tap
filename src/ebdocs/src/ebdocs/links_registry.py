"""Cross-link registry between Jira issues and Google Drive docs.

Stored at {CONTENT_DIR}/links.yaml as a single flat file. Read/write is atomic
(full file rewrite). Keys are Jira issue keys; values are lists of gdocs paths
(relative to CONTENT_DIR, without .yaml suffix).

Example:
    jira_to_gdocs:
      EARL-101:
        - gdocs/knowledge-base/ecommerce-fundamentals/abcd-of-ecommerce
      EARL-99:
        - gdocs/knowledge-base/conversion-playbook/funnel-architecture
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml


def _registry_path() -> Path:
    """Resolve the path to links.yaml.

    Precedence:
    1. CONTENT_DIR/links.yaml (canonical shared location)
    2. dist/links.yaml (local dev fallback)
    """
    content_dir = os.environ.get("CONTENT_DIR")
    if content_dir:
        return Path(content_dir) / "links.yaml"
    return Path("dist/links.yaml")


def load_registry() -> dict:
    """Load the cross-link registry. Returns empty dict if file doesn't exist."""
    path = _registry_path()
    if not path.exists():
        return {"jira_to_gdocs": {}}
    try:
        data = yaml.safe_load(path.read_text()) or {}
        if "jira_to_gdocs" not in data:
            data["jira_to_gdocs"] = {}
        return data
    except Exception:
        return {"jira_to_gdocs": {}}


def save_registry(registry: dict) -> Path:
    """Save the cross-link registry, returning the path written."""
    path = _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Sort jira keys for clean git diffs
    jira_map = registry.get("jira_to_gdocs", {})
    sorted_map = {k: sorted(jira_map[k]) for k in sorted(jira_map.keys())}
    output = {"jira_to_gdocs": sorted_map}
    path.write_text(yaml.dump(output, default_flow_style=False, sort_keys=False, allow_unicode=True))
    return path


def add_link(jira_key: str, gdocs_path: str) -> Path:
    """Add a Jira -> gdocs link to the registry. Idempotent."""
    registry = load_registry()
    jira_map = registry.setdefault("jira_to_gdocs", {})
    existing = jira_map.setdefault(jira_key, [])
    if gdocs_path not in existing:
        existing.append(gdocs_path)
    return save_registry(registry)


def remove_link(jira_key: str, gdocs_path: str) -> Path:
    """Remove a specific Jira -> gdocs link. Deletes the jira key if empty after."""
    registry = load_registry()
    jira_map = registry.get("jira_to_gdocs", {})
    if jira_key in jira_map:
        if gdocs_path in jira_map[jira_key]:
            jira_map[jira_key].remove(gdocs_path)
        if not jira_map[jira_key]:
            del jira_map[jira_key]
    return save_registry(registry)


def gdocs_for_jira(jira_key: str) -> list[str]:
    """Return all gdocs paths linked to a Jira issue."""
    registry = load_registry()
    return registry.get("jira_to_gdocs", {}).get(jira_key, [])


def jira_for_gdocs(gdocs_path: str) -> list[str]:
    """Return all Jira keys linked to a gdocs path (reverse lookup via iteration)."""
    registry = load_registry()
    jira_map = registry.get("jira_to_gdocs", {})
    return [k for k, paths in jira_map.items() if gdocs_path in paths]
