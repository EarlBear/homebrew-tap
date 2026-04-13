"""Configuration loading for ebdocs CLI.

In Docker mode (default), env vars are injected via --env-file .env.
No python-dotenv needed — the shell wrapper handles it.

Precedence (last wins):
1. Environment variables (injected by Docker --env-file)
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class DocsConfig:
    # Auth Mode 1: Service Account (headless, docs owned by SA)
    service_account_key: str = ""
    service_account_key_json: str = ""

    # Auth Mode 2: OAuth Refresh Token (headless after one-time consent, docs owned by user)
    oauth_client_id: str = ""
    oauth_client_secret: str = ""
    oauth_refresh_token: str = ""

    # Shared config
    drive_folder_id: str = ""
    default_format: str = "json"

    @property
    def auth_mode(self) -> str:
        """Determine which auth mode to use based on configured env vars."""
        if self.oauth_refresh_token and self.oauth_client_id:
            return "oauth"
        if self.service_account_key or self.service_account_key_json:
            return "service_account"
        return "none"

    def validate(self) -> list[str]:
        """Return list of missing required fields."""
        missing = []
        if self.auth_mode == "none":
            missing.append(
                "GOOGLE_OAUTH_REFRESH_TOKEN + GOOGLE_OAUTH_CLIENT_ID (recommended) "
                "or GOOGLE_SERVICE_ACCOUNT_KEY"
            )
        if self.auth_mode == "oauth" and not self.oauth_client_secret:
            missing.append("GOOGLE_OAUTH_CLIENT_SECRET")
        if not self.drive_folder_id:
            missing.append("GOOGLE_DRIVE_FOLDER_ID")
        return missing


def load_config() -> DocsConfig:
    """Load config from environment variables."""
    return DocsConfig(
        service_account_key=os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY", ""),
        service_account_key_json=os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY_JSON", ""),
        oauth_client_id=os.environ.get("GOOGLE_OAUTH_CLIENT_ID", ""),
        oauth_client_secret=os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", ""),
        oauth_refresh_token=os.environ.get("GOOGLE_OAUTH_REFRESH_TOKEN", ""),
        drive_folder_id=os.environ.get("GOOGLE_DRIVE_FOLDER_ID", ""),
        default_format=os.environ.get("EBDOCS_OUTPUT", "json"),
    )


# Singleton — loaded once, reused everywhere
_config: DocsConfig | None = None


def get_config() -> DocsConfig:
    """Get the global config singleton."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reset_config() -> None:
    """Reset the config singleton (for testing)."""
    global _config
    _config = None
