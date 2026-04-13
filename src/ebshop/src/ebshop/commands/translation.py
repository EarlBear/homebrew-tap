"""Translation commands — content translation management.

Examples:
    ebshop translation list --resource-id gid://shopify/Product/123
    ebshop translation list --resource-id gid://shopify/Product/123 --locale fr
    ebshop translation set --resource-id gid://shopify/Product/123 --locale fr --key title --value "Chapeau"
    ebshop translation delete --resource-id gid://shopify/Product/123 --locale fr --key title
"""

from __future__ import annotations

import typer

from ebshop.client import get_client
from ebshop.models.translation import Translation
from ebshop.output import Format, output_result

translation_app = typer.Typer(help="Content translation management.")


@translation_app.command("list")
def list_translations(
    resource_id: str = typer.Option(..., "--resource-id", help="Resource GID to list translations for."),
    locale: str | None = typer.Option(None, "--locale", "-l", help="Filter by locale code (e.g. fr, de, ja)."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """List translations for a resource."""
    locale_arg = f', locale: "{locale}"' if locale else ""
    gql = f"""
        query getTranslations($resourceId: ID!) {{
            translatableResource(resourceId: $resourceId) {{
                translations{locale_arg} {{
                    key
                    value
                    locale
                    outdated
                }}
            }}
        }}
    """
    client = get_client()
    data = client.graphql(gql, variables={"resourceId": resource_id})
    resource = data.get("translatableResource", {})
    raw_translations = resource.get("translations", []) if resource else []
    translations = [Translation.from_shopify(t).summary() for t in raw_translations]
    output_result(
        translations, format=format, json_fields=json_fields,
        columns=["key", "value", "locale", "outdated"],
    )


@translation_app.command("set")
def set_translation(
    resource_id: str = typer.Option(..., "--resource-id", help="Resource GID to translate."),
    locale: str = typer.Option(..., "--locale", "-l", help="Locale code (e.g. fr, de, ja)."),
    key: str = typer.Option(..., "--key", "-k", help="Translation key (e.g. title, body_html)."),
    value: str = typer.Option(..., "--value", "-v", help="Translated value."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Set a translation for a resource field."""
    gql = """
        mutation translationsRegister($resourceId: ID!, $translations: [TranslationInput!]!) {
            translationsRegister(resourceId: $resourceId, translations: $translations) {
                translations {
                    key
                    value
                    locale
                    outdated
                }
                userErrors { field message }
            }
        }
    """
    client = get_client()
    data = client.graphql(gql, variables={
        "resourceId": resource_id,
        "translations": [{
            "key": key,
            "value": value,
            "locale": locale,
            "translatableContentDigest": "",
        }],
    })
    registered = data.get("translationsRegister", {}).get("translations", [])
    translations = [Translation.from_shopify(t).summary() for t in registered]
    output_result(
        translations if translations else {"key": key, "value": value, "locale": locale},
        format=format, json_fields=json_fields,
    )


@translation_app.command("delete")
def delete_translation(
    resource_id: str = typer.Option(..., "--resource-id", help="Resource GID."),
    locale: str = typer.Option(..., "--locale", "-l", help="Locale code."),
    key: str = typer.Option(..., "--key", "-k", help="Translation key to remove."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Delete a translation for a resource field."""
    gql = """
        mutation translationsRemove($resourceId: ID!, $translationKeys: [String!]!, $locales: [String!]!) {
            translationsRemove(resourceId: $resourceId, translationKeys: $translationKeys, locales: $locales) {
                translations {
                    key
                    value
                    locale
                    outdated
                }
                userErrors { field message }
            }
        }
    """
    client = get_client()
    data = client.graphql(gql, variables={
        "resourceId": resource_id,
        "translationKeys": [key],
        "locales": [locale],
    })
    remaining = data.get("translationsRemove", {}).get("translations", [])
    output_result(
        {"deleted": True, "key": key, "locale": locale, "remaining_count": len(remaining)},
        format=format, json_fields=json_fields,
    )
