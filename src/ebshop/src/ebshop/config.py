"""Configuration loading for ebshop CLI.

In Docker mode (default), env vars are injected via --env-file .env.
No python-dotenv needed — the shell wrapper handles it.

Token auto-generation:
  If SHOPIFY_ACCESS_TOKEN is missing but SHOPIFY_CLIENT_ID and
  SHOPIFY_CLIENT_SECRET are present, the CLI will automatically
  generate a 24-hour token via the client_credentials grant.
  This requires the app and store to be in the same Shopify organization.

Precedence (last wins):
1. Environment variables (injected by Docker --env-file)
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass


@dataclass
class ShopifyConfig:
    store_url: str = ""
    access_token: str = ""
    client_id: str = ""
    client_secret: str = ""
    api_version: str = "2026-01"
    default_format: str = "json"

    def validate(self) -> list[str]:
        """Return list of missing required fields."""
        missing = []
        if not self.store_url:
            missing.append("SHOPIFY_STORE_URL")
        if not self.access_token:
            missing.append("SHOPIFY_ACCESS_TOKEN")
        return missing


def _generate_token_via_client_credentials(
    store_url: str, client_id: str, client_secret: str
) -> str | None:
    """Generate an access token via Shopify's client_credentials grant.

    Returns the access token string, or None if the request fails.
    Requires the app and store to be in the same Shopify organization.
    Token TTL: 24 hours.
    """
    import httpx

    store_domain = store_url.rstrip("/")
    # Strip protocol if present
    if "://" in store_domain:
        store_domain = store_domain.split("://", 1)[1]
    store_domain = store_domain.rstrip("/")

    url = f"https://{store_domain}/admin/oauth/access_token"

    try:
        resp = httpx.post(
            url,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            token = data.get("access_token", "")
            expires_in = data.get("expires_in", 0)
            if token:
                hours = expires_in // 3600
                print(
                    f'{{"status": "token_generated", "message": "Auto-generated {hours}h token via client_credentials", "store": "{store_domain}"}}',
                    file=sys.stderr,
                )
                return token
        else:
            error_body = resp.text[:200]
            print(
                f'{{"error": "TOKEN_GENERATION_FAILED", "status": {resp.status_code}, "message": "{error_body}"}}',
                file=sys.stderr,
            )
    except Exception as e:
        print(
            f'{{"error": "TOKEN_GENERATION_ERROR", "message": "{e}"}}',
            file=sys.stderr,
        )

    return None


def load_config() -> ShopifyConfig:
    """Load config from environment variables.

    If SHOPIFY_ACCESS_TOKEN is missing but SHOPIFY_CLIENT_ID and
    SHOPIFY_CLIENT_SECRET are present, automatically generates a
    token via client_credentials grant.
    """
    store_url = os.environ.get("SHOPIFY_STORE_URL", "")
    access_token = os.environ.get("SHOPIFY_ACCESS_TOKEN", "")
    client_id = os.environ.get("SHOPIFY_CLIENT_ID", "")
    client_secret = os.environ.get(
        "SHOPIFY_CLIENT_SECRET",
        os.environ.get("SHOPIFY_API_SECRET", ""),
    )

    # Auto-generate token if missing but credentials are available
    if not access_token and store_url and client_id and client_secret:
        generated = _generate_token_via_client_credentials(
            store_url, client_id, client_secret
        )
        if generated:
            access_token = generated

    return ShopifyConfig(
        store_url=store_url,
        access_token=access_token,
        client_id=client_id,
        client_secret=client_secret,
        api_version=os.environ.get("SHOPIFY_API_VERSION", "2026-01"),
        default_format=os.environ.get("EBSHOP_OUTPUT", "json"),
    )


# Singleton — loaded once, reused everywhere
_config: ShopifyConfig | None = None


def get_config() -> ShopifyConfig:
    """Get the global config singleton."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reset_config() -> None:
    """Reset the config singleton (for testing)."""
    global _config
    _config = None
