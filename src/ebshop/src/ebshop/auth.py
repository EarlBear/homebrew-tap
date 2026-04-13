"""Shopify OAuth credential flow for ebshop CLI.

Shopify Custom Apps created via the Dev Dashboard use OAuth2 authorization
code grant to obtain an access token. The flow:

1. User runs `ebshop auth login`
2. CLI opens browser to Shopify authorization URL
3. User approves the app in Shopify Admin
4. Shopify redirects to localhost with an authorization code
5. CLI exchanges the code for an access token
6. User saves the token to .env as SHOPIFY_ACCESS_TOKEN

After that, all CLI calls use the static access token — no refresh needed.
Shopify access tokens for Custom Apps do not expire.
"""

from __future__ import annotations

import http.server
import json
import sys
import threading
import urllib.parse
import webbrowser
from typing import Any

import httpx

from ebshop.config import get_config


def run_oauth_login_flow() -> str:
    """Run the Shopify OAuth authorization code flow.

    Opens a browser for the user to authorize the app, captures the
    authorization code via a local HTTP server, exchanges it for an
    access token, and returns the token.
    """
    config = get_config()

    if not config.client_id:
        _exit_error(
            "AUTH_MISSING_CLIENT_ID",
            "SHOPIFY_CLIENT_ID is required for OAuth login. "
            "Find it in Dev Dashboard > Settings > Credentials.",
        )
    if not config.client_secret:
        _exit_error(
            "AUTH_MISSING_CLIENT_SECRET",
            "SHOPIFY_CLIENT_SECRET is required for OAuth login. "
            "Find it in Dev Dashboard > Settings > Credentials.",
        )
    if not config.store_url:
        _exit_error(
            "AUTH_MISSING_STORE_URL",
            "SHOPIFY_STORE_URL is required. Set it in .env "
            "(e.g., https://your-store.myshopify.com).",
        )

    # All scopes we request — matches what's configured in the Dev Dashboard app version
    scopes = ",".join([
        "read_products", "write_products",
        "read_orders", "write_orders", "read_all_orders",
        "read_customers", "write_customers",
        "read_inventory", "write_inventory",
        "read_content", "write_content",
        "read_themes", "write_themes", "write_theme_code",
        "read_reports", "read_analytics",
        "read_price_rules", "write_price_rules",
        "read_discounts", "write_discounts",
        "read_fulfillments", "write_fulfillments",
        "read_locations", "write_locations",
        "read_metaobjects", "write_metaobjects",
        "read_metaobject_definitions", "write_metaobject_definitions",
        "read_online_store_pages", "write_online_store_pages",
        "read_online_store_navigation", "write_online_store_navigation",
        "read_draft_orders", "write_draft_orders",
        "read_files", "write_files",
        "read_locales", "write_locales",
        "read_publications", "write_publications",
        "read_shipping", "write_shipping",
        "read_returns", "write_returns",
        "read_marketing_events", "write_marketing_events",
        "read_customer_events",
        "read_legal_policies", "write_legal_policies",
        "read_gift_cards", "write_gift_cards",
        "read_channels", "write_channels",
        "read_checkouts", "write_checkouts",
        "read_resource_feedbacks", "write_resource_feedbacks",
        "read_merchant_managed_fulfillment_orders", "write_merchant_managed_fulfillment_orders",
        "read_script_tags", "write_script_tags",
        "read_custom_pixels", "write_custom_pixels",
        "read_pixels", "write_pixels",
        "read_checkout_branding_settings", "write_checkout_branding_settings",
        "read_translations", "write_translations",
        "read_inventory_shipments", "write_inventory_shipments",
        "read_inventory_transfers", "write_inventory_transfers",
        "read_assigned_fulfillment_orders", "write_assigned_fulfillment_orders",
        "read_third_party_fulfillment_orders", "write_third_party_fulfillment_orders",
        "read_product_listings", "write_product_listings",
        "read_product_feeds", "write_product_feeds",
        "read_markets", "write_markets",
        "read_apps", "read_audit_events",
        "read_customer_merge", "write_customer_merge",
        "read_discovery", "write_discovery",
        "read_marketing_integrated_campaigns", "write_marketing_integrated_campaigns",
        "read_cart_transforms", "write_cart_transforms",
        "read_validations", "write_validations",
        "read_purchase_options", "write_purchase_options",
        "read_payment_terms", "write_payment_terms",
        "read_customer_payment_methods",
    ])

    redirect_uri = "http://localhost:19456/callback"
    nonce = "earlbear_ebshop_auth"

    store_url = config.store_url.rstrip("/")
    auth_url = (
        f"{store_url}/admin/oauth/authorize"
        f"?client_id={config.client_id}"
        f"&scope={scopes}"
        f"&redirect_uri={urllib.parse.quote(redirect_uri, safe='')}"
        f"&state={nonce}"
    )

    # Capture the authorization code via local HTTP server
    auth_code: dict[str, str | None] = {"code": None, "error": None}

    class CallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)

            state = params.get("state", [None])[0]
            if state != nonce:
                auth_code["error"] = f"State mismatch: expected {nonce}, got {state}"
                self.send_response(400)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>Error: State mismatch</h1>")
                return

            code = params.get("code", [None])[0]
            if code:
                auth_code["code"] = code
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<h1>Authorization successful!</h1>"
                    b"<p>You can close this tab and return to the terminal.</p>"
                )
            else:
                error = params.get("error", ["unknown"])[0]
                auth_code["error"] = f"Authorization denied: {error}"
                self.send_response(400)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(f"<h1>Error: {error}</h1>".encode())

        def log_message(self, format: str, *args: Any) -> None:
            pass  # Suppress HTTP server logs

    server = http.server.HTTPServer(("localhost", 19456), CallbackHandler)

    # Open browser
    print(f"Opening browser for Shopify authorization...", file=sys.stderr)
    print(f"If the browser doesn't open, visit this URL:\n\n{auth_url}\n", file=sys.stderr)
    webbrowser.open(auth_url)

    # Wait for the callback (with timeout)
    server.timeout = 120
    server.handle_request()
    server.server_close()

    if auth_code["error"]:
        _exit_error("AUTH_DENIED", str(auth_code["error"]))

    if not auth_code["code"]:
        _exit_error("AUTH_NO_CODE", "No authorization code received. Try again.")

    # Exchange the authorization code for an access token
    token_url = f"{store_url}/admin/oauth/access_token"
    resp = httpx.post(
        token_url,
        json={
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "code": auth_code["code"],
        },
        timeout=30.0,
    )

    if not resp.is_success:
        _exit_error(
            "AUTH_TOKEN_EXCHANGE_FAILED",
            f"Token exchange failed ({resp.status_code}): {resp.text}",
        )

    token_data = resp.json()
    access_token = token_data.get("access_token", "")

    if not access_token:
        _exit_error("AUTH_NO_TOKEN", f"No access_token in response: {token_data}")

    return access_token


def _exit_error(code: str, message: str) -> None:
    """Print structured error and exit."""
    print(json.dumps({"error": code, "message": message}), file=sys.stderr)
    sys.exit(2)
