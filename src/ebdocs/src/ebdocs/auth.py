"""Google API credential loading for ebdocs CLI.

Supports two auth modes (auto-detected from env vars):

Mode 1 — OAuth Refresh Token (RECOMMENDED for agents):
  Set GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, GOOGLE_OAUTH_REFRESH_TOKEN.
  A human runs `ebdocs auth login` once to get the refresh token.
  After that, the CLI uses the refresh token headlessly forever.
  Docs appear as the human user (e.g., omar@earlbear.com).

Mode 2 — Service Account:
  Set GOOGLE_SERVICE_ACCOUNT_KEY (file path) or GOOGLE_SERVICE_ACCOUNT_KEY_JSON (inline).
  Fully headless, no one-time consent needed.
  Docs are owned by the service account (must be shared via Drive API).

Setup (one-time, for OAuth mode):
  1. Go to https://console.cloud.google.com/apis/credentials
  2. Create OAuth 2.0 Client ID (type: Desktop app)
  3. Download the client secret JSON
  4. Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET in .env
  5. Run: ebdocs auth login
     → Opens browser for consent (or prints URL for headless)
     → Saves refresh token to .env
  6. Set GOOGLE_OAUTH_REFRESH_TOKEN in .env (printed by the login command)
  7. All future runs are headless — the refresh token auto-renews access tokens.
"""

from __future__ import annotations

import json
import sys

from google.oauth2.credentials import Credentials as OAuthCredentials
from google.oauth2.service_account import Credentials as SACredentials

from ebdocs.config import get_config

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]

TOKEN_URI = "https://oauth2.googleapis.com/token"


def load_credentials() -> OAuthCredentials | SACredentials:
    """Load credentials based on configured auth mode.

    Priority: OAuth refresh token > Service Account key JSON > SA key file.
    """
    config = get_config()

    # Mode 1: OAuth Refresh Token (recommended)
    if config.auth_mode == "oauth":
        return _load_oauth_credentials()

    # Mode 2: Service Account
    if config.auth_mode == "service_account":
        return _load_sa_credentials()

    # No credentials configured
    _exit_error(
        "AUTH_MISSING",
        "No Google credentials configured. Options:\n"
        "  1. (Recommended) Set GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, "
        "GOOGLE_OAUTH_REFRESH_TOKEN\n"
        "     Run 'ebdocs auth login' to get the refresh token.\n"
        "  2. Set GOOGLE_SERVICE_ACCOUNT_KEY (path) or GOOGLE_SERVICE_ACCOUNT_KEY_JSON (inline)",
    )


def _load_oauth_credentials() -> OAuthCredentials:
    """Load OAuth2 credentials from refresh token."""
    config = get_config()

    if not config.oauth_client_secret:
        _exit_error(
            "AUTH_MISSING_SECRET",
            "GOOGLE_OAUTH_CLIENT_ID is set but GOOGLE_OAUTH_CLIENT_SECRET is missing.",
        )

    return OAuthCredentials(
        token=None,  # Will be refreshed automatically on first API call
        refresh_token=config.oauth_refresh_token,
        token_uri=TOKEN_URI,
        client_id=config.oauth_client_id,
        client_secret=config.oauth_client_secret,
        scopes=SCOPES,
    )


def _load_sa_credentials() -> SACredentials:
    """Load service account credentials from key file or inline JSON."""
    config = get_config()

    # Inline JSON first
    if config.service_account_key_json:
        try:
            info = json.loads(config.service_account_key_json)
            return SACredentials.from_service_account_info(info, scopes=SCOPES)
        except (json.JSONDecodeError, ValueError) as e:
            _exit_error(
                "AUTH_INVALID_JSON",
                f"GOOGLE_SERVICE_ACCOUNT_KEY_JSON is not valid JSON: {e}",
            )

    # File path
    if config.service_account_key:
        try:
            return SACredentials.from_service_account_file(
                config.service_account_key, scopes=SCOPES
            )
        except FileNotFoundError:
            _exit_error(
                "AUTH_FILE_NOT_FOUND",
                f"Service account key file not found: {config.service_account_key}",
            )
        except (ValueError, Exception) as e:
            _exit_error("AUTH_FILE_INVALID", f"Failed to load key file: {e}")

    _exit_error("AUTH_MISSING", "No service account credentials found.")


def run_oauth_login_flow() -> str:
    """Run the one-time OAuth consent flow. Returns the refresh token.

    This is called by `ebdocs auth login`. It opens a browser (or prints a URL)
    for the user to consent. After consent, the refresh token is returned.
    The user saves it to .env as GOOGLE_OAUTH_REFRESH_TOKEN.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow

    config = get_config()

    if not config.oauth_client_id or not config.oauth_client_secret:
        _exit_error(
            "AUTH_LOGIN_MISSING",
            "Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET in .env first.",
        )

    client_config = {
        "installed": {
            "client_id": config.oauth_client_id,
            "client_secret": config.oauth_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": TOKEN_URI,
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)

    try:
        # Try local server flow (opens browser)
        creds = flow.run_local_server(port=0, open_browser=True)
    except Exception:
        # Fallback: console flow (prints URL, user pastes code)
        creds = flow.run_console()

    return creds.refresh_token


def _exit_error(code: str, message: str) -> None:
    """Print structured error and exit."""
    print(json.dumps({"error": code, "message": message}), file=sys.stderr)
    sys.exit(2)
