"""Inventory commands — levels, locations, adjust, set, product inventory.

Examples:
    ebshop inventory levels 123456
    ebshop inventory locations --limit 10
    ebshop inventory adjust 123456 --location-id 789 --delta 5 --reason "Restock"
    ebshop inventory set 123456 --location-id 789 --quantity 20
    ebshop inventory product 98765
"""

from __future__ import annotations

import typer

from ebshop.client import get_client
from ebshop.models.inventory import InventoryLevel, Location
from ebshop.output import Format, output_result

inventory_app = typer.Typer(help="Inventory levels, locations, and adjustments.")


@inventory_app.command()
def levels(
    inventory_item_id: str = typer.Argument(..., help="Inventory item ID (numeric or GID)."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Show inventory levels for an item across all locations."""
    client = get_client()
    gid = client.to_gid("InventoryItem", inventory_item_id)
    data = client.graphql(
        """
        query inventoryLevels($id: ID!) {
            inventoryItem(id: $id) {
                inventoryLevels(first: 10) {
                    edges {
                        node {
                            location { id name }
                            quantities(names: ["available", "on_hand"]) {
                                name
                                quantity
                            }
                        }
                    }
                }
            }
        }
        """,
        variables={"id": gid},
    )
    item = data.get("inventoryItem", {}) or {}
    edges = item.get("inventoryLevels", {}).get("edges", [])
    results = [InventoryLevel.from_shopify(e["node"]).summary() for e in edges]
    output_result(
        results,
        format=format,
        json_fields=json_fields,
        columns=["location_id", "location_name", "available", "on_hand"],
    )


@inventory_app.command()
def locations(
    limit: int = typer.Option(10, "--limit", "-l", help="Max locations to return."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """List store locations."""
    client = get_client()
    data = client.graphql(
        """
        query locations($first: Int!) {
            locations(first: $first) {
                edges {
                    node {
                        id
                        name
                        address { city province country }
                        isActive
                    }
                }
            }
        }
        """,
        variables={"first": limit},
    )
    edges = data.get("locations", {}).get("edges", [])
    results = [Location.from_shopify(e["node"]).summary() for e in edges]
    output_result(
        results,
        format=format,
        json_fields=json_fields,
        columns=["id", "name", "city", "province", "country", "is_active"],
    )


@inventory_app.command()
def adjust(
    inventory_item_id: str = typer.Argument(..., help="Inventory item ID (numeric or GID)."),
    location_id: str = typer.Option(..., "--location-id", help="Location ID (numeric or GID)."),
    delta: int = typer.Option(..., "--delta", help="Quantity change (positive or negative)."),
    reason: str | None = typer.Option(None, "--reason", help="Reason for adjustment."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Adjust inventory quantity by a delta (+ or -)."""
    client = get_client()
    item_gid = client.to_gid("InventoryItem", inventory_item_id)
    loc_gid = client.to_gid("Location", location_id)
    data = client.graphql(
        """
        mutation adjustInventory($input: InventoryAdjustQuantitiesInput!) {
            inventoryAdjustQuantities(input: $input) {
                inventoryAdjustmentGroup {
                    reason
                    changes {
                        name
                        delta
                        item { id }
                        location { id name }
                    }
                }
                userErrors { field message }
            }
        }
        """,
        variables={
            "input": {
                "name": "available",
                "reason": reason or "correction",
                "changes": [
                    {
                        "inventoryItemId": item_gid,
                        "locationId": loc_gid,
                        "delta": delta,
                    }
                ],
            }
        },
    )
    group = (
        data.get("inventoryAdjustQuantities", {})
        .get("inventoryAdjustmentGroup", {})
    ) or {}
    changes = group.get("changes", [])
    results = []
    for c in changes:
        results.append({
            "item_id": c.get("item", {}).get("id", ""),
            "location_id": c.get("location", {}).get("id", ""),
            "location_name": c.get("location", {}).get("name", ""),
            "name": c.get("name", ""),
            "delta": c.get("delta", 0),
            "reason": group.get("reason", ""),
        })
    output_result(
        results,
        format=format,
        json_fields=json_fields,
        columns=["item_id", "location_id", "location_name", "name", "delta", "reason"],
    )


@inventory_app.command("set")
def set_quantity(
    inventory_item_id: str = typer.Argument(..., help="Inventory item ID (numeric or GID)."),
    location_id: str = typer.Option(..., "--location-id", help="Location ID (numeric or GID)."),
    quantity: int = typer.Option(..., "--quantity", help="Absolute quantity to set."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Set inventory quantity to an absolute value."""
    client = get_client()
    item_gid = client.to_gid("InventoryItem", inventory_item_id)
    loc_gid = client.to_gid("Location", location_id)
    data = client.graphql(
        """
        mutation setInventory($input: InventorySetQuantitiesInput!) {
            inventorySetQuantities(input: $input) {
                inventoryAdjustmentGroup {
                    reason
                    changes {
                        name
                        delta
                        quantityAfterChange
                        item { id }
                        location { id name }
                    }
                }
                userErrors { field message }
            }
        }
        """,
        variables={
            "input": {
                "name": "available",
                "reason": "correction",
                "quantities": [
                    {
                        "inventoryItemId": item_gid,
                        "locationId": loc_gid,
                        "quantity": quantity,
                    }
                ],
            }
        },
    )
    group = (
        data.get("inventorySetQuantities", {})
        .get("inventoryAdjustmentGroup", {})
    ) or {}
    changes = group.get("changes", [])
    results = []
    for c in changes:
        results.append({
            "item_id": c.get("item", {}).get("id", ""),
            "location_id": c.get("location", {}).get("id", ""),
            "location_name": c.get("location", {}).get("name", ""),
            "name": c.get("name", ""),
            "delta": c.get("delta", 0),
            "quantity_after": c.get("quantityAfterChange", 0),
            "reason": group.get("reason", ""),
        })
    output_result(
        results,
        format=format,
        json_fields=json_fields,
        columns=["item_id", "location_id", "location_name", "name", "quantity_after", "reason"],
    )


@inventory_app.command()
def product(
    product_id: str = typer.Argument(..., help="Product ID (numeric or GID)."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Show inventory levels for all variants of a product."""
    client = get_client()
    gid = client.to_gid("Product", product_id)
    data = client.graphql(
        """
        query productInventory($id: ID!) {
            product(id: $id) {
                title
                variants(first: 50) {
                    edges {
                        node {
                            id
                            title
                            sku
                            inventoryItem {
                                id
                                inventoryLevels(first: 10) {
                                    edges {
                                        node {
                                            location { id name }
                                            quantities(names: ["available", "on_hand"]) {
                                                name
                                                quantity
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """,
        variables={"id": gid},
    )
    product_data = data.get("product", {}) or {}
    variant_edges = product_data.get("variants", {}).get("edges", [])
    results = []
    for ve in variant_edges:
        variant = ve["node"]
        inv_item = variant.get("inventoryItem", {}) or {}
        level_edges = inv_item.get("inventoryLevels", {}).get("edges", [])
        for le in level_edges:
            level = InventoryLevel.from_shopify(le["node"])
            results.append({
                "variant_id": variant.get("id", ""),
                "variant_title": variant.get("title", ""),
                "sku": variant.get("sku", ""),
                "inventory_item_id": inv_item.get("id", ""),
                "location_id": level.location_id,
                "location_name": level.location_name,
                "available": level.available,
                "on_hand": level.on_hand,
            })
    output_result(
        results,
        format=format,
        json_fields=json_fields,
        columns=["variant_title", "sku", "location_name", "available", "on_hand"],
    )
