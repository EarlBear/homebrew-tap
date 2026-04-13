"""Locale commands — store language management.

Examples:
    ebshop locale list
    ebshop locale enable --locale fr
    ebshop locale disable --locale fr
"""

from __future__ import annotations

import typer

from ebshop.client import get_client
from ebshop.models.locale import ShopLocale
from ebshop.output import Format, output_result

locale_app = typer.Typer(help="Store language management.")


@locale_app.command("list")
def list_locales(
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """List all shop locales (languages)."""
    gql = """
        {
            shopLocales {
                locale
                name
                primary
                published
            }
        }
    """
    client = get_client()
    data = client.graphql(gql)
    raw_locales = data.get("shopLocales", [])
    locales = [ShopLocale.from_shopify(loc).summary() for loc in raw_locales]
    output_result(
        locales, format=format, json_fields=json_fields,
        columns=["locale", "name", "primary", "published"],
    )


@locale_app.command("enable")
def enable_locale(
    locale: str = typer.Option(..., "--locale", "-l", help="Locale code to enable (e.g. fr, de, ja)."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Enable a locale for the store."""
    gql = """
        mutation shopLocaleEnable($locale: String!) {
            shopLocaleEnable(locale: $locale) {
                shopLocale {
                    locale
                    name
                    primary
                    published
                }
                userErrors { field message }
            }
        }
    """
    client = get_client()
    data = client.graphql(gql, variables={"locale": locale})
    shop_locale = data.get("shopLocaleEnable", {}).get("shopLocale")
    if not shop_locale:
        output_result(
            {"error": "ENABLE_FAILED", "message": f"Failed to enable locale '{locale}'."},
            format=format,
        )
        raise typer.Exit(code=1)

    result = ShopLocale.from_shopify(shop_locale).summary()
    output_result(result, format=format, json_fields=json_fields)


@locale_app.command("disable")
def disable_locale(
    locale: str = typer.Option(..., "--locale", "-l", help="Locale code to disable."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Disable a locale for the store."""
    gql = """
        mutation shopLocaleDisable($locale: String!) {
            shopLocaleDisable(locale: $locale) {
                locale
                userErrors { field message }
            }
        }
    """
    client = get_client()
    data = client.graphql(gql, variables={"locale": locale})
    disabled_locale = data.get("shopLocaleDisable", {}).get("locale", "")
    output_result(
        {"disabled": True, "locale": disabled_locale or locale},
        format=format, json_fields=json_fields,
    )
