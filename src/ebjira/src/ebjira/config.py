"""Configuration loading for ebjira CLI.

In Docker mode (default), env vars are injected via --env-file .env.
No python-dotenv needed — the shell wrapper handles it.

Precedence (last wins):
1. Environment variables (injected by Docker --env-file)
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class JiraConfig:
    base_url: str = ""
    user_email: str = ""
    api_token: str = ""
    default_project: str = ""
    default_format: str = "json"

    def validate(self) -> list[str]:
        """Return list of missing required fields."""
        missing = []
        if not self.base_url:
            missing.append("JIRA_BASE_URL")
        if not self.user_email:
            missing.append("JIRA_USER_EMAIL")
        if not self.api_token:
            missing.append("JIRA_API_TOKEN")
        return missing


def load_config() -> JiraConfig:
    """Load config from environment variables."""
    return JiraConfig(
        base_url=os.environ.get("JIRA_BASE_URL", ""),
        user_email=os.environ.get("JIRA_USER_EMAIL", ""),
        api_token=os.environ.get("JIRA_API_TOKEN", ""),
        default_project=os.environ.get("JIRA_PROJECT", ""),
        default_format=os.environ.get("JIRA_OUTPUT", "json"),
    )


# Singleton — loaded once, reused everywhere
_config: JiraConfig | None = None


def get_config() -> JiraConfig:
    """Get the global config singleton."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reset_config() -> None:
    """Reset the config singleton (for testing)."""
    global _config
    _config = None
