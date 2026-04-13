"""Shop commands — store info, health check, and policies.

Examples:
    ebshop shop info
    ebshop shop health
    ebshop shop policies
"""

from __future__ import annotations

import typer

from ebshop.client import get_client
from ebshop.output import Format, output_result

shop_app = typer.Typer(help="Store info and health check.")


@shop_app.command()
def info(
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Show store information (name, plan, domain, email, currency)."""
    client = get_client()
    data = client.graphql("""
        {
            shop {
                name
                email
                myshopifyDomain
                primaryDomain { url host }
                plan { displayName partnerDevelopment shopifyPlus }
                currencyCode
                timezoneAbbreviation
                ianaTimezone
                weightUnit
                billingAddress { country countryCodeV2 province city }
            }
        }
    """)
    shop = data.get("shop", {})
    result = {
        "name": shop.get("name", ""),
        "email": shop.get("email", ""),
        "myshopify_domain": shop.get("myshopifyDomain", ""),
        "primary_domain": shop.get("primaryDomain", {}).get("url", ""),
        "plan": shop.get("plan", {}).get("displayName", ""),
        "partner_development": shop.get("plan", {}).get("partnerDevelopment", False),
        "shopify_plus": shop.get("plan", {}).get("shopifyPlus", False),
        "currency": shop.get("currencyCode", ""),
        "timezone": shop.get("ianaTimezone", ""),
        "timezone_abbr": shop.get("timezoneAbbreviation", ""),
        "weight_unit": shop.get("weightUnit", ""),
        "country": shop.get("billingAddress", {}).get("country", ""),
    }
    output_result(result, format=format, json_fields=json_fields)


@shop_app.command()
def health(
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Quick connectivity check against the Shopify store."""
    client = get_client()
    data = client.graphql("{ shop { name myshopifyDomain plan { displayName } } }")
    shop = data.get("shop", {})
    result = {
        "status": "ok",
        "store": shop.get("name", ""),
        "domain": shop.get("myshopifyDomain", ""),
        "plan": shop.get("plan", {}).get("displayName", ""),
        "api_version": client.api_version,
    }
    output_result(result, format=format, json_fields=json_fields)


@shop_app.command()
def policies(
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """List store policies (privacy, terms of service, refund, shipping)."""
    client = get_client()
    data = client.rest_get("/policies.json")
    raw_policies = data.get("policies", [])
    policies_list = []
    for policy in raw_policies:
        policies_list.append({
            "type": policy.get("title", ""),
            "title": policy.get("title", ""),
            "url": policy.get("url", ""),
        })
    output_result(policies_list, format=format, json_fields=json_fields,
                  columns=["type", "title", "url"])
