"""Customer commands — list, view, search, create, update, orders, tags.

Examples:
    ebshop customer list
    ebshop customer view 12345
    ebshop customer search --query "email:jane@example.com"
    ebshop customer create --email jane@example.com --first-name Jane
    ebshop customer update 12345 --tags "vip,wholesale"
    ebshop customer orders 12345
    ebshop customer tags 12345 --add "vip"
"""

from __future__ import annotations

import typer

from ebshop.client import ShopifyClient, get_client
from ebshop.models.customer import Customer, CustomerOrder
from ebshop.output import Format, output_result

customer_app = typer.Typer(help="Customer management — list, view, search, create, update, orders, tags.")

# ── GraphQL fragments ──

CUSTOMER_FIELDS = """
    id
    firstName
    lastName
    email
    phone
    createdAt
    updatedAt
    numberOfOrders
    amountSpent { amount currencyCode }
    tags
    note
    verifiedEmail
    state
    defaultAddress {
        address1 address2 city province country zip phone
    }
"""

LIST_QUERY = f"""
    query ListCustomers($first: Int!, $after: String) {{
        customers(first: $first, after: $after) {{
            edges {{ node {{ {CUSTOMER_FIELDS} }} }}
            pageInfo {{ hasNextPage endCursor }}
        }}
    }}
"""

VIEW_QUERY = f"""
    query GetCustomer($id: ID!) {{
        customer(id: $id) {{ {CUSTOMER_FIELDS} }}
    }}
"""

SEARCH_QUERY = f"""
    query SearchCustomers($first: Int!, $query: String!) {{
        customers(first: $first, query: $query) {{
            edges {{ node {{ {CUSTOMER_FIELDS} }} }}
            pageInfo {{ hasNextPage endCursor }}
        }}
    }}
"""

CREATE_MUTATION = f"""
    mutation CustomerCreate($input: CustomerInput!) {{
        customerCreate(input: $input) {{
            customer {{ {CUSTOMER_FIELDS} }}
            userErrors {{ field message }}
        }}
    }}
"""

UPDATE_MUTATION = f"""
    mutation CustomerUpdate($input: CustomerInput!) {{
        customerUpdate(input: $input) {{
            customer {{ {CUSTOMER_FIELDS} }}
            userErrors {{ field message }}
        }}
    }}
"""

ORDERS_QUERY = """
    query CustomerOrders($id: ID!, $first: Int!) {
        customer(id: $id) {
            orders(first: $first) {
                edges {
                    node {
                        id
                        name
                        createdAt
                        totalPriceSet { shopMoney { amount currencyCode } }
                    }
                }
            }
        }
    }
"""

TAGS_ADD_MUTATION = """
    mutation TagsAdd($id: ID!, $tags: [String!]!) {
        tagsAdd(id: $id, tags: $tags) {
            node { id }
            userErrors { field message }
        }
    }
"""

TAGS_REMOVE_MUTATION = """
    mutation TagsRemove($id: ID!, $tags: [String!]!) {
        tagsRemove(id: $id, tags: $tags) {
            node { id }
            userErrors { field message }
        }
    }
"""


@customer_app.command("list")
def list_customers(
    limit: int = typer.Option(50, "--limit", "-l", help="Max customers to return."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """List customers."""
    client = get_client()
    variables: dict = {"first": min(limit, 250)}

    nodes = client.graphql_paginated(
        LIST_QUERY,
        variables=variables,
        connection_path=["customers"],
        max_results=limit,
    )

    customers = [Customer.from_shopify(n).to_summary() for n in nodes]
    output_result(
        customers, format=format, json_fields=json_fields,
        columns=["id", "first_name", "last_name", "email", "orders_count", "total_spent", "state"],
    )


@customer_app.command()
def view(
    id: str = typer.Argument(help="Customer ID (numeric or GID)."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """View detailed customer information."""
    client = get_client()
    gid = ShopifyClient.to_gid("Customer", id)
    data = client.graphql(VIEW_QUERY, variables={"id": gid})
    customer_data = data.get("customer", {})
    customer = Customer.from_shopify(customer_data)
    output_result(customer.to_detail(), format=format, json_fields=json_fields)


@customer_app.command()
def search(
    query: str = typer.Option(..., "--query", "-q", help="Shopify search query (e.g. 'email:jane@example.com')."),
    limit: int = typer.Option(50, "--limit", "-l", help="Max customers to return."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Search customers by query string."""
    client = get_client()
    variables: dict = {"first": min(limit, 250), "query": query}

    nodes = client.graphql_paginated(
        SEARCH_QUERY,
        variables=variables,
        connection_path=["customers"],
        max_results=limit,
    )

    customers = [Customer.from_shopify(n).to_summary() for n in nodes]
    output_result(
        customers, format=format, json_fields=json_fields,
        columns=["id", "first_name", "last_name", "email", "orders_count", "total_spent", "state"],
    )


@customer_app.command()
def create(
    email: str = typer.Option(..., "--email", "-e", help="Customer email address."),
    first_name: str | None = typer.Option(None, "--first-name", help="First name."),
    last_name: str | None = typer.Option(None, "--last-name", help="Last name."),
    phone: str | None = typer.Option(None, "--phone", help="Phone number."),
    tags: str | None = typer.Option(None, "--tags", help="Comma-separated tags."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Create a new customer."""
    client = get_client()
    input_data: dict = {"email": email}
    if first_name is not None:
        input_data["firstName"] = first_name
    if last_name is not None:
        input_data["lastName"] = last_name
    if phone is not None:
        input_data["phone"] = phone
    if tags is not None:
        input_data["tags"] = [t.strip() for t in tags.split(",")]

    data = client.graphql(CREATE_MUTATION, variables={"input": input_data})
    customer_data = data.get("customerCreate", {}).get("customer", {})
    customer = Customer.from_shopify(customer_data)
    output_result(customer.to_detail(), format=format, json_fields=json_fields)


@customer_app.command()
def update(
    id: str = typer.Argument(help="Customer ID (numeric or GID)."),
    email: str | None = typer.Option(None, "--email", "-e", help="Update email."),
    first_name: str | None = typer.Option(None, "--first-name", help="Update first name."),
    last_name: str | None = typer.Option(None, "--last-name", help="Update last name."),
    phone: str | None = typer.Option(None, "--phone", help="Update phone."),
    tags: str | None = typer.Option(None, "--tags", help="Replace tags (comma-separated)."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Update an existing customer."""
    client = get_client()
    gid = ShopifyClient.to_gid("Customer", id)
    input_data: dict = {"id": gid}
    if email is not None:
        input_data["email"] = email
    if first_name is not None:
        input_data["firstName"] = first_name
    if last_name is not None:
        input_data["lastName"] = last_name
    if phone is not None:
        input_data["phone"] = phone
    if tags is not None:
        input_data["tags"] = [t.strip() for t in tags.split(",")]

    data = client.graphql(UPDATE_MUTATION, variables={"input": input_data})
    customer_data = data.get("customerUpdate", {}).get("customer", {})
    customer = Customer.from_shopify(customer_data)
    output_result(customer.to_detail(), format=format, json_fields=json_fields)


@customer_app.command()
def orders(
    id: str = typer.Argument(help="Customer ID (numeric or GID)."),
    limit: int = typer.Option(50, "--limit", "-l", help="Max orders to return."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """List orders for a specific customer."""
    client = get_client()
    gid = ShopifyClient.to_gid("Customer", id)
    data = client.graphql(ORDERS_QUERY, variables={"id": gid, "first": min(limit, 250)})
    order_edges = data.get("customer", {}).get("orders", {}).get("edges", [])

    order_list = [CustomerOrder.from_shopify(e["node"]).to_dict() for e in order_edges]
    output_result(
        order_list, format=format, json_fields=json_fields,
        columns=["id", "name", "total", "created_at"],
    )


@customer_app.command("tags")
def manage_tags(
    id: str = typer.Argument(help="Customer ID (numeric or GID)."),
    add: str | None = typer.Option(None, "--add", help="Comma-separated tags to add."),
    remove: str | None = typer.Option(None, "--remove", help="Comma-separated tags to remove."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Add or remove tags on a customer."""
    if not add and not remove:
        output_result(
            {"error": "Specify --add or --remove (or both)."},
            format=format, json_fields=json_fields,
        )
        raise typer.Exit(code=1)

    client = get_client()
    gid = ShopifyClient.to_gid("Customer", id)
    results: dict = {"customer_id": gid}

    if add:
        tag_list = [t.strip() for t in add.split(",")]
        client.graphql(TAGS_ADD_MUTATION, variables={"id": gid, "tags": tag_list})
        results["added"] = tag_list

    if remove:
        tag_list = [t.strip() for t in remove.split(",")]
        client.graphql(TAGS_REMOVE_MUTATION, variables={"id": gid, "tags": tag_list})
        results["removed"] = tag_list

    output_result(results, format=format, json_fields=json_fields)
