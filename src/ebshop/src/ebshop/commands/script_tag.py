"""Script tag commands — list, create, and delete storefront JavaScript injections.

Examples:
    ebshop script-tag list
    ebshop script-tag list --limit 20
    ebshop script-tag create --src "https://example.com/tracking.js"
    ebshop script-tag create --src "https://example.com/receipt.js" --display-scope order-status
    ebshop script-tag delete 123456
"""

from __future__ import annotations

import typer

from ebshop.client import ShopifyClient, get_client
from ebshop.models.script_tag import ScriptTag
from ebshop.output import Format, output_result

script_tag_app = typer.Typer(help="Storefront JavaScript injection (script tags).")

# ── GraphQL fragments ──

_SCRIPT_TAG_FIELDS = """
    id
    src
    displayScope
    createdAt
    updatedAt
"""


@script_tag_app.command("list")
def list_script_tags(
    limit: int = typer.Option(10, "--limit", "-l", help="Max results to return."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """List script tag injections."""
    gql = f"""
        query listScriptTags($first: Int!, $after: String) {{
            scriptTags(first: $first, after: $after) {{
                edges {{
                    node {{
                        {_SCRIPT_TAG_FIELDS}
                    }}
                }}
                pageInfo {{ hasNextPage endCursor }}
            }}
        }}
    """

    client = get_client()
    nodes = client.graphql_paginated(
        gql,
        variables={"first": min(limit, 50)},
        connection_path=["scriptTags"],
        max_results=limit,
    )
    tags = [ScriptTag.from_shopify(n).summary() for n in nodes]
    output_result(
        tags,
        format=format,
        json_fields=json_fields,
        columns=["id", "src", "display_scope", "created_at"],
    )


@script_tag_app.command("create")
def create_script_tag(
    src: str = typer.Option(..., "--src", "-s", help="URL of the JavaScript to inject."),
    display_scope: str = typer.Option(
        "all", "--display-scope", "-d",
        help="Where to inject: 'all' or 'order-status'.",
    ),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Create a script tag injection."""
    # Convert user-friendly scope to GraphQL enum
    scope_enum = "ALL" if display_scope == "all" else "ORDER_STATUS"

    gql = f"""
        mutation scriptTagCreate($input: ScriptTagInput!) {{
            scriptTagCreate(input: $input) {{
                scriptTag {{
                    {_SCRIPT_TAG_FIELDS}
                }}
                userErrors {{ field message }}
            }}
        }}
    """

    client = get_client()
    data = client.graphql(gql, variables={
        "input": {
            "src": src,
            "displayScope": scope_enum,
        },
    })

    node = data.get("scriptTagCreate", {}).get("scriptTag")
    if not node:
        output_result(
            {"error": "CREATE_FAILED", "message": "Script tag creation returned no tag."},
            format=format,
        )
        raise typer.Exit(code=1)

    tag = ScriptTag.from_shopify(node)
    output_result(tag.summary(), format=format, json_fields=json_fields)


@script_tag_app.command("delete")
def delete_script_tag(
    id: str = typer.Argument(..., help="Script tag ID (numeric or GID)."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Delete a script tag injection."""
    gid = ShopifyClient.to_gid("ScriptTag", id)

    gql = """
        mutation scriptTagDelete($id: ID!) {
            scriptTagDelete(id: $id) {
                deletedScriptTagId
                userErrors { field message }
            }
        }
    """

    client = get_client()
    data = client.graphql(gql, variables={"id": gid})
    deleted_id = data.get("scriptTagDelete", {}).get("deletedScriptTagId")

    result = {
        "deleted": True,
        "id": deleted_id or gid,
    }
    output_result(result, format=format, json_fields=json_fields)
