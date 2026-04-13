"""Authentication commands — login and status check.

Examples:
    ebshop auth login      # OAuth flow to get access token
    ebshop auth status     # Check current credentials and API connectivity
"""

from __future__ import annotations

import json
import sys

import typer

from ebshop.config import get_config
from ebshop.output import Format, output_error, output_result

auth_app = typer.Typer(help="Authentication — login and credential status.")


@auth_app.command("login")
def auth_login() -> None:
    """Run the Shopify OAuth flow to get an access token.

    Opens a browser for you to authorize the app on your store.
    After approval, the access token is printed. Save it to .env
    as SHOPIFY_ACCESS_TOKEN.

    Requires SHOPIFY_CLIENT_ID, SHOPIFY_CLIENT_SECRET, and
    SHOPIFY_STORE_URL to be set in .env.

    NOTE: Run this in a SEPARATE TERMINAL, not inside Claude Code
    (needs browser access).
    """
    from ebshop.auth import run_oauth_login_flow

    try:
        access_token = run_oauth_login_flow()
    except SystemExit:
        raise
    except Exception as e:
        output_error(
            error="AUTH_LOGIN_FAILED",
            message=f"OAuth login flow failed: {e}",
        )
        return

    # Output the token and instructions
    print(json.dumps({
        "status": "success",
        "access_token": access_token,
    }))
    print(
        f"\nAdd this to your .env:\n\n"
        f"  SHOPIFY_ACCESS_TOKEN={access_token}\n",
        file=sys.stderr,
    )


@auth_app.command("status")
def auth_status(
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Show current authentication status and verify API access.

    Checks whether credentials are configured, tests connectivity
    to the Shopify Admin API, and shows store info if connected.
    """
    config = get_config()

    result: dict = {
        "store_url": config.store_url or "(not set)",
        "access_token_set": bool(config.access_token),
        "client_id_set": bool(config.client_id),
        "client_secret_set": bool(config.client_secret),
        "api_version": config.api_version,
        "api_access": False,
        "store_name": None,
    }

    if not config.store_url or not config.access_token:
        result["message"] = (
            "Credentials incomplete. Set SHOPIFY_STORE_URL and "
            "SHOPIFY_ACCESS_TOKEN in .env. Run 'ebshop auth login' to get a token."
        )
        output_result(result, format=format, json_fields=json_fields)
        return

    # Test API connectivity
    try:
        from ebshop.client import get_client
        client = get_client()
        data = client.graphql("{ shop { name myshopifyDomain plan { displayName } } }")
        shop = data.get("shop", {})
        result["api_access"] = True
        result["store_name"] = shop.get("name", "")
        result["domain"] = shop.get("myshopifyDomain", "")
        result["plan"] = shop.get("plan", {}).get("displayName", "")
    except SystemExit:
        result["api_access"] = False
        result["message"] = "Failed to connect — check credentials"
    except Exception as e:
        result["api_access"] = False
        result["api_error"] = str(e)

    output_result(result, format=format, json_fields=json_fields)
