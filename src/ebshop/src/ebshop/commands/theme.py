"""Theme commands — list, view, assets, get/update individual assets, and publish.

Examples:
    ebshop theme list
    ebshop theme view 123456789
    ebshop theme assets 123456789
    ebshop theme get-asset 123456789 config/settings_data.json
    ebshop theme update-asset 123456789 config/settings_data.json --value '...'
    ebshop theme update-asset 123456789 config/settings_data.json --file settings.json
    ebshop theme publish 123456789
"""

from __future__ import annotations

from pathlib import Path

import typer

from ebshop.client import get_client
from ebshop.models.theme import Theme, ThemeAsset
from ebshop.output import Format, output_result

theme_app = typer.Typer(help="Theme management — list, view, assets, publish.")


@theme_app.command("list")
def list_themes(
    limit: int = typer.Option(50, "--limit", "-l", help="Max themes to return."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """List all themes in the store."""
    client = get_client()
    data = client.graphql("""
        {
            themes(first: 50) {
                nodes {
                    id
                    name
                    role
                    createdAt
                    updatedAt
                }
            }
        }
    """)
    nodes = data.get("themes", {}).get("nodes", [])
    # Map GraphQL camelCase to snake_case for model
    themes = []
    for node in nodes[:limit]:
        themes.append(Theme.from_shopify({
            "id": int(client.from_gid(node.get("id", "0"))),
            "name": node.get("name", ""),
            "role": node.get("role", "").lower(),
            "created_at": node.get("createdAt", ""),
            "updated_at": node.get("updatedAt", ""),
        }))
    result = [t.summary() for t in themes]
    output_result(result, format=format, json_fields=json_fields,
                  columns=["id", "name", "role", "created_at", "updated_at"])


@theme_app.command()
def view(
    theme_id: str = typer.Argument(..., help="Theme ID (numeric)."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """View details of a single theme (via REST)."""
    client = get_client()
    data = client.rest_get(f"/themes/{theme_id}.json")
    raw = data.get("theme", {})
    theme = Theme.from_shopify(raw)
    output_result(theme.summary(), format=format, json_fields=json_fields)


@theme_app.command()
def assets(
    theme_id: str = typer.Argument(..., help="Theme ID (numeric)."),
    limit: int = typer.Option(250, "--limit", "-l", help="Max assets to return."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """List assets for a theme (via REST)."""
    client = get_client()
    data = client.rest_get(f"/themes/{theme_id}/assets.json")
    raw_assets = data.get("assets", [])
    assets_list = [ThemeAsset.from_shopify(a).summary() for a in raw_assets[:limit]]
    output_result(assets_list, format=format, json_fields=json_fields,
                  columns=["key", "content_type", "size", "updated_at"])


@theme_app.command("get-asset")
def get_asset(
    theme_id: str = typer.Argument(..., help="Theme ID (numeric)."),
    asset_key: str = typer.Argument(..., help="Asset key, e.g. 'config/settings_data.json'."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Get a single theme asset's content (via REST)."""
    client = get_client()
    data = client.rest_get(
        f"/themes/{theme_id}/assets.json",
        params={"asset[key]": asset_key},
    )
    raw = data.get("asset", {})
    result = {
        "key": raw.get("key", ""),
        "value": raw.get("value", ""),
        "content_type": raw.get("content_type", ""),
        "size": raw.get("size"),
        "updated_at": raw.get("updated_at", ""),
    }
    output_result(result, format=format, json_fields=json_fields)


@theme_app.command("update-asset")
def update_asset(
    theme_id: str = typer.Argument(..., help="Theme ID (numeric)."),
    asset_key: str = typer.Argument(..., help="Asset key, e.g. 'config/settings_data.json'."),
    value: str | None = typer.Option(
        None, "--value", "-v", help="Asset value as a string (for small payloads)."
    ),
    file: Path | None = typer.Option(
        None, "--file", help="Path to a file whose content will be used as the asset value."
    ),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Update (upload) a single theme asset (via REST PUT).

    Provide either --value with inline content or --file with a path to read from.
    """
    if not value and not file:
        raise typer.BadParameter("Provide either --value or --file.")
    if value and file:
        raise typer.BadParameter("Provide either --value or --file, not both.")

    if file:
        value = file.read_text(encoding="utf-8")

    client = get_client()
    data = client.rest_put(
        f"/themes/{theme_id}/assets.json",
        json={"asset": {"key": asset_key, "value": value}},
    )
    raw = data.get("asset", {})
    result = {
        "key": raw.get("key", ""),
        "content_type": raw.get("content_type", ""),
        "size": raw.get("size"),
        "updated_at": raw.get("updated_at", ""),
        "message": f"Asset '{asset_key}' updated successfully.",
    }
    output_result(result, format=format, json_fields=json_fields)


@theme_app.command()
def publish(
    theme_id: str = typer.Argument(..., help="Theme ID (numeric) to publish."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Publish a theme (make it the live theme via REST PUT)."""
    client = get_client()
    data = client.rest_put(
        f"/themes/{theme_id}.json",
        json={"theme": {"role": "main"}},
    )
    raw = data.get("theme", {})
    theme = Theme.from_shopify(raw)
    result = theme.summary()
    result["published"] = True
    output_result(result, format=format, json_fields=json_fields)
