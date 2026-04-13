"""Navigation commands — list, view, create, update, delete, and sync menus from manifest.

Examples:
    ebshop navigation list
    ebshop navigation view 123456
    ebshop navigation create --title "Main Menu" --items '[{"title":"Home","url":"/"}]'
    ebshop navigation update 123456 --title "Updated Menu"
    ebshop navigation delete 123456
    ebshop navigation apply-manifest
    ebshop navigation apply-manifest --dry-run
"""

from __future__ import annotations

import json as json_lib
import os
from pathlib import Path

import typer

from ebshop.client import ShopifyClient, get_client
from ebshop.models.navigation import Menu
from ebshop.output import Format, output_result


def _load_manifest_navigation() -> dict:
    """Load navigation section from manifest.yaml."""
    try:
        import yaml
    except ImportError:
        return {}

    candidates = [
        Path(os.environ.get("MANIFEST_FILE", "")),
        Path.cwd() / "shopify-cli" / "assets" / "manifest.yaml",
        Path.cwd() / "assets" / "manifest.yaml",
        Path(__file__).resolve().parents[3] / "assets" / "manifest.yaml",
    ]
    for p in candidates:
        if p.is_file():
            with open(p) as f:
                manifest = yaml.safe_load(f)
            return manifest.get("navigation", {})
    return {}


def _build_menu_items(entries: list[dict]) -> list[dict]:
    """Convert manifest navigation entries to Shopify MenuItemCreateInput list.

    Supports nested items (submenus) via the ``items`` key.  Top-level entries
    without a ``link`` but with ``items`` become parent-only headers — Shopify
    accepts a ``title`` without a ``url`` for top-level groupings.
    """
    result = []
    for entry in entries:
        link = entry.get("link")
        item: dict = {
            "title": entry.get("title", ""),
            "type": "HTTP" if link else "FRONTPAGE",
        }
        if link:
            item["url"] = link
        else:
            # Parent-only items (like "Shop" with children) need a URL
            # Use the homepage as a dummy target
            item["url"] = "/"

        # Nested sub-items
        sub_items = entry.get("items")
        if sub_items:
            item["items"] = _build_menu_items(sub_items)

        result.append(item)
    return result


def _find_menu_by_handle(
    menus: list[dict], handle: str
) -> dict | None:
    """Return the first menu whose handle matches."""
    for m in menus:
        if m.get("handle") == handle:
            return m
    return None

navigation_app = typer.Typer(help="Online Store navigation/menu management.")

# ── GraphQL fragments ──

_MENU_FIELDS = """
    id
    title
    handle
"""

_MENU_DETAIL_FIELDS = """
    id
    title
    handle
    items(first: 50) {
        edges {
            node {
                id
                title
                url
                type
            }
        }
    }
"""


@navigation_app.command("list")
def list_menus(
    limit: int = typer.Option(10, "--limit", "-l", help="Max results to return."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """List online store navigation menus."""
    gql = f"""
        query listMenus($first: Int!, $after: String) {{
            menus(first: $first, after: $after) {{
                edges {{
                    node {{
                        {_MENU_FIELDS}
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
        connection_path=["menus"],
        max_results=limit,
    )
    menus = [Menu.from_shopify(n).summary() for n in nodes]
    output_result(
        menus,
        format=format,
        json_fields=json_fields,
        columns=["id", "title", "handle", "items_count"],
    )


@navigation_app.command("view")
def view_menu(
    id: str = typer.Argument(..., help="Menu ID (numeric or GID)."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """View a navigation menu with its items."""
    gid = ShopifyClient.to_gid("Menu", id)

    gql = f"""
        query getMenu($id: ID!) {{
            menu(id: $id) {{
                {_MENU_DETAIL_FIELDS}
            }}
        }}
    """

    client = get_client()
    data = client.graphql(gql, variables={"id": gid})
    node = data.get("menu")
    if not node:
        output_result(
            {"error": "NOT_FOUND", "message": f"Menu {id} not found."},
            format=format,
        )
        raise typer.Exit(code=1)

    menu = Menu.from_shopify(node)
    result = menu.summary()
    # Flatten items from edges
    items_edges = node.get("items", {}).get("edges", [])
    result["items"] = [
        {
            "id": e["node"]["id"],
            "title": e["node"].get("title", ""),
            "url": e["node"].get("url", ""),
            "type": e["node"].get("type", ""),
        }
        for e in items_edges
    ]
    output_result(result, format=format, json_fields=json_fields)


@navigation_app.command("create")
def create_menu(
    title: str = typer.Option(..., "--title", "-t", help="Menu title."),
    items: str = typer.Option(
        "[]", "--items", "-i",
        help='JSON array of menu items, e.g. \'[{"title":"Home","url":"/"}]\'.',
    ),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Create a navigation menu."""
    try:
        items_list = json_lib.loads(items)
    except json_lib.JSONDecodeError:
        output_result(
            {"error": "INVALID_JSON", "message": "Could not parse --items as JSON."},
            format=format,
        )
        raise typer.Exit(code=1)

    menu_items = []
    for item in items_list:
        menu_items.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "type": item.get("type", "HTTP"),
        })

    gql = f"""
        mutation menuCreate($title: String!, $items: [MenuItemCreateInput!]!) {{
            menuCreate(title: $title, items: $items) {{
                menu {{
                    {_MENU_FIELDS}
                }}
                userErrors {{ field message }}
            }}
        }}
    """

    client = get_client()
    data = client.graphql(gql, variables={"title": title, "items": menu_items})

    node = data.get("menuCreate", {}).get("menu")
    if not node:
        output_result(
            {"error": "CREATE_FAILED", "message": "Menu creation returned no menu."},
            format=format,
        )
        raise typer.Exit(code=1)

    menu = Menu.from_shopify(node)
    output_result(menu.summary(), format=format, json_fields=json_fields)


@navigation_app.command("update")
def update_menu(
    id: str = typer.Argument(..., help="Menu ID (numeric or GID)."),
    title: str | None = typer.Option(None, "--title", "-t", help="New menu title."),
    items: str | None = typer.Option(
        None, "--items", "-i",
        help='JSON array of menu items to replace existing items.',
    ),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Update a navigation menu."""
    gid = ShopifyClient.to_gid("Menu", id)

    menu_items = None
    if items is not None:
        try:
            items_list = json_lib.loads(items)
        except json_lib.JSONDecodeError:
            output_result(
                {"error": "INVALID_JSON", "message": "Could not parse --items as JSON."},
                format=format,
            )
            raise typer.Exit(code=1)
        menu_items = [
            {"title": i.get("title", ""), "url": i.get("url", ""), "type": i.get("type", "HTTP")}
            for i in items_list
        ]

    gql = f"""
        mutation menuUpdate($id: ID!, $title: String, $items: [MenuItemCreateInput!]) {{
            menuUpdate(id: $id, title: $title, items: $items) {{
                menu {{
                    {_MENU_FIELDS}
                }}
                userErrors {{ field message }}
            }}
        }}
    """

    variables: dict = {"id": gid}
    if title is not None:
        variables["title"] = title
    if menu_items is not None:
        variables["items"] = menu_items

    client = get_client()
    data = client.graphql(gql, variables=variables)

    node = data.get("menuUpdate", {}).get("menu")
    if not node:
        output_result(
            {"error": "UPDATE_FAILED", "message": "Menu update returned no menu."},
            format=format,
        )
        raise typer.Exit(code=1)

    menu = Menu.from_shopify(node)
    output_result(menu.summary(), format=format, json_fields=json_fields)


@navigation_app.command("delete")
def delete_menu(
    id: str = typer.Argument(..., help="Menu ID (numeric or GID)."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Delete a navigation menu."""
    gid = ShopifyClient.to_gid("Menu", id)

    gql = """
        mutation menuDelete($id: ID!) {
            menuDelete(id: $id) {
                deletedMenuId
                userErrors { field message }
            }
        }
    """

    client = get_client()
    data = client.graphql(gql, variables={"id": gid})
    deleted_id = data.get("menuDelete", {}).get("deletedMenuId")

    result = {
        "deleted": True,
        "id": deleted_id or gid,
    }
    output_result(result, format=format, json_fields=json_fields)


# ── Manifest-driven sync ──

# Mapping from manifest keys to Shopify menu handles.
_MANIFEST_TO_HANDLE = {
    "main_menu": "main-menu",
    "footer_menu": "footer",
}


@navigation_app.command("apply-manifest")
def apply_manifest(
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show what would change without modifying the store."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Apply navigation menus from manifest.yaml to the store.

    Reads the ``navigation`` section of the manifest and creates or updates
    the ``main-menu`` and ``footer`` menus to match.

    Examples:
        ebshop navigation apply-manifest
        ebshop navigation apply-manifest --dry-run
        MANIFEST_FILE=/path/to/manifest.yaml ebshop navigation apply-manifest
    """
    nav = _load_manifest_navigation()
    if not nav:
        output_result(
            {
                "error": "MANIFEST_NOT_FOUND",
                "message": (
                    "Could not load navigation section from manifest.yaml. "
                    "Set MANIFEST_FILE env var or run from repo root."
                ),
            },
            format=format,
        )
        raise typer.Exit(code=1)

    # Fetch existing menus so we know whether to create or update
    client = get_client()
    existing_nodes = client.graphql_paginated(
        f"""
        query listMenus($first: Int!, $after: String) {{
            menus(first: $first, after: $after) {{
                edges {{
                    node {{
                        {_MENU_FIELDS}
                    }}
                }}
                pageInfo {{ hasNextPage endCursor }}
            }}
        }}
        """,
        variables={"first": 50},
        connection_path=["menus"],
        max_results=250,
    )
    existing_menus = [
        {
            "id": n.get("id", ""),
            "title": n.get("title", ""),
            "handle": n.get("handle", ""),
        }
        for n in existing_nodes
    ]

    actions: list[dict] = []

    for manifest_key, handle in _MANIFEST_TO_HANDLE.items():
        entries = nav.get(manifest_key)
        if not entries:
            continue

        # Human-friendly title derived from the manifest key
        menu_title = manifest_key.replace("_", " ").title()  # "Main Menu" / "Footer Menu"
        menu_items = _build_menu_items(entries)
        existing = _find_menu_by_handle(existing_menus, handle)

        if existing:
            action = {
                "menu": manifest_key,
                "handle": handle,
                "operation": "update",
                "id": existing["id"],
                "items_count": len(menu_items),
            }
            if dry_run:
                actions.append(action)
                continue

            # menuUpdate requires items as [MenuItemUpdateInput!]!
            # Pass new items without IDs to replace all existing items
            update_gql = f"""
                mutation menuUpdate($id: ID!, $title: String!, $items: [MenuItemUpdateInput!]!) {{
                    menuUpdate(id: $id, title: $title, items: $items) {{
                        menu {{
                            {_MENU_FIELDS}
                        }}
                        userErrors {{ field message }}
                    }}
                }}
            """
            data = client.graphql(update_gql, variables={
                "id": existing["id"],
                "title": menu_title,
                "items": menu_items,
            })
            errors = data.get("menuUpdate", {}).get("userErrors", [])
            if errors:
                action["errors"] = [e.get("message", "") for e in errors]
            else:
                node = data.get("menuUpdate", {}).get("menu", {})
                action["result_id"] = node.get("id", "")
            actions.append(action)
        else:
            action = {
                "menu": manifest_key,
                "handle": handle,
                "operation": "create",
                "items_count": len(menu_items),
            }
            if dry_run:
                actions.append(action)
                continue

            # Create new menu
            gql = f"""
                mutation menuCreate($title: String!, $items: [MenuItemCreateInput!]!) {{
                    menuCreate(title: $title, items: $items) {{
                        menu {{
                            {_MENU_FIELDS}
                        }}
                        userErrors {{ field message }}
                    }}
                }}
            """
            data = client.graphql(gql, variables={
                "title": menu_title,
                "items": menu_items,
            })
            errors = data.get("menuCreate", {}).get("userErrors", [])
            if errors:
                action["errors"] = [e.get("message", "") for e in errors]
            else:
                node = data.get("menuCreate", {}).get("menu", {})
                action["result_id"] = node.get("id", "")
            actions.append(action)

    result = {
        "applied": not dry_run,
        "dry_run": dry_run,
        "source": "manifest.yaml",
        "menus": actions,
    }
    output_result(result, format=format, json_fields=json_fields)
