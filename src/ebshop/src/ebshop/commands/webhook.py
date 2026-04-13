"""Webhook commands — list, create, and delete webhook subscriptions.

Examples:
    ebshop webhook list
    ebshop webhook list --limit 10
    ebshop webhook create --topic orders/create --address https://example.com/hook
    ebshop webhook delete 123456
"""

from __future__ import annotations

import typer

from ebshop.client import ShopifyClient, get_client
from ebshop.models.webhook import Webhook
from ebshop.output import Format, output_result

webhook_app = typer.Typer(help="Webhook subscription management.")

# ── GraphQL fragments ──

_WEBHOOK_FIELDS = """
    id
    topic
    callbackUrl
    format
    createdAt
    updatedAt
"""


def _topic_to_enum(topic: str) -> str:
    """Convert user-friendly topic to GraphQL enum.

    'orders/create' -> 'ORDERS_CREATE'
    """
    return topic.replace("/", "_").upper()


@webhook_app.command("list")
def list_webhooks(
    limit: int = typer.Option(10, "--limit", "-l", help="Max results to return."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """List webhook subscriptions."""
    gql = f"""
        query listWebhooks($first: Int!, $after: String) {{
            webhookSubscriptions(first: $first, after: $after) {{
                edges {{
                    node {{
                        {_WEBHOOK_FIELDS}
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
        connection_path=["webhookSubscriptions"],
        max_results=limit,
    )
    webhooks = [Webhook.from_shopify(n).summary() for n in nodes]
    output_result(
        webhooks,
        format=format,
        json_fields=json_fields,
        columns=["id", "topic", "callback_url", "format", "created_at"],
    )


@webhook_app.command("create")
def create_webhook(
    topic: str = typer.Option(..., "--topic", "-t", help="Event topic (e.g. orders/create, products/update)."),
    address: str = typer.Option(..., "--address", "-a", help="Callback URL for the webhook."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Create a webhook subscription."""
    enum_topic = _topic_to_enum(topic)

    gql = f"""
        mutation webhookCreate($topic: WebhookSubscriptionTopic!, $webhookSubscription: WebhookSubscriptionInput!) {{
            webhookSubscriptionCreate(topic: $topic, webhookSubscription: $webhookSubscription) {{
                webhookSubscription {{
                    {_WEBHOOK_FIELDS}
                }}
                userErrors {{ field message }}
            }}
        }}
    """

    client = get_client()
    data = client.graphql(gql, variables={
        "topic": enum_topic,
        "webhookSubscription": {
            "callbackUrl": address,
            "format": "JSON",
        },
    })

    node = data.get("webhookSubscriptionCreate", {}).get("webhookSubscription")
    if not node:
        output_result(
            {"error": "CREATE_FAILED", "message": "Webhook creation returned no subscription."},
            format=format,
        )
        raise typer.Exit(code=1)

    webhook = Webhook.from_shopify(node)
    output_result(webhook.summary(), format=format, json_fields=json_fields)


@webhook_app.command("delete")
def delete_webhook(
    id: str = typer.Argument(..., help="Webhook subscription ID (numeric or GID)."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Delete a webhook subscription."""
    gid = ShopifyClient.to_gid("WebhookSubscription", id)

    gql = """
        mutation webhookDelete($id: ID!) {
            webhookSubscriptionDelete(id: $id) {
                deletedWebhookSubscriptionId
                userErrors { field message }
            }
        }
    """

    client = get_client()
    data = client.graphql(gql, variables={"id": gid})
    deleted_id = data.get("webhookSubscriptionDelete", {}).get("deletedWebhookSubscriptionId")

    result = {
        "deleted": True,
        "id": deleted_id or gid,
    }
    output_result(result, format=format, json_fields=json_fields)
