"""Authentication verification commands."""

from __future__ import annotations

import json
import sys

import typer

from ebdocs.config import get_config
from ebdocs.output import Format, output_error, output_result

app = typer.Typer(name="auth", help="Verify credentials and service account access")


@app.command("status")
def auth_status(
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format"),
) -> None:
    """Show current authentication status and verify API access.

    Displays the auth mode (OAuth or Service Account), the authenticated
    identity, and whether the Google Docs API is reachable.
    """
    config = get_config()
    auth_mode = config.auth_mode

    if auth_mode == "none":
        output_error(
            error="AUTH_NOT_CONFIGURED",
            message=(
                "No Google credentials configured. "
                "Run 'ebdocs auth login' (OAuth) or set GOOGLE_SERVICE_ACCOUNT_KEY."
            ),
        )

    result: dict = {
        "auth_mode": auth_mode,
        "email": None,
        "api_access": False,
    }

    # Load credentials and determine email
    try:
        from ebdocs.auth import load_credentials

        creds = load_credentials()
    except SystemExit:
        output_error(
            error="AUTH_LOAD_FAILED",
            message="Failed to load credentials. Check your .env configuration.",
        )
        return  # unreachable, but helps type checkers

    # Get email based on auth mode
    if auth_mode == "service_account":
        result["email"] = getattr(creds, "service_account_email", None)
    elif auth_mode == "oauth":
        # Try to get email from the token info endpoint
        try:
            import google.auth.transport.requests

            request = google.auth.transport.requests.Request()
            creds.refresh(request)
            # After refresh, the token is valid — query userinfo
            import urllib.request

            req = urllib.request.Request(
                "https://www.googleapis.com/oauth2/v1/userinfo?alt=json",
                headers={"Authorization": f"Bearer {creds.token}"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                userinfo = json.loads(resp.read())
                result["email"] = userinfo.get("email")
        except Exception:
            result["email"] = "(could not retrieve — token may need refresh)"

    # Test API access by listing 1 file
    try:
        from googleapiclient.discovery import build

        drive = build("drive", "v3", credentials=creds, cache_discovery=False)
        drive.files().list(
            pageSize=1,
            fields="files(id)",
            q="mimeType = 'application/vnd.google-apps.document'",
        ).execute()
        result["api_access"] = True
        drive.close()
    except Exception as e:
        result["api_access"] = False
        result["api_error"] = str(e)

    output_result(result, format=format)


@app.command("login")
def auth_login() -> None:
    """Run the one-time OAuth consent flow to get a refresh token.

    Opens a browser for Google account consent. After approval, prints
    the refresh token. Save it to your .env file.

    Only works in OAuth mode — requires GOOGLE_OAUTH_CLIENT_ID and
    GOOGLE_OAUTH_CLIENT_SECRET to be set in .env.
    """
    config = get_config()

    if not config.oauth_client_id or not config.oauth_client_secret:
        output_error(
            error="AUTH_LOGIN_REQUIRES_OAUTH",
            message=(
                "OAuth login requires GOOGLE_OAUTH_CLIENT_ID and "
                "GOOGLE_OAUTH_CLIENT_SECRET in .env. "
                "See: https://console.cloud.google.com/apis/credentials"
            ),
        )

    try:
        from ebdocs.auth import run_oauth_login_flow

        refresh_token = run_oauth_login_flow()
    except SystemExit:
        raise
    except Exception as e:
        output_error(
            error="AUTH_LOGIN_FAILED",
            message=f"OAuth login flow failed: {e}",
        )
        return  # unreachable

    # Output the token and instructions
    print(json.dumps({
        "status": "success",
        "refresh_token": refresh_token,
    }))
    print(
        f"\nAdd this to your .env:\n\n"
        f"  GOOGLE_OAUTH_REFRESH_TOKEN={refresh_token}\n",
        file=sys.stderr,
    )
