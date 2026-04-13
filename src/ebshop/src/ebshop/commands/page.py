"""Page commands — list, view, create, update, delete Online Store pages.

Examples:
    ebshop page list
    ebshop page list --limit 10
    ebshop page view 123456
    ebshop page create --title "About Us" --body-html "<p>Welcome</p>"
    ebshop page create --title "FAQ" --body-html "<p>Questions</p>" --published
    ebshop page update 123456 --title "Updated Title"
    ebshop page update 123456 --published
    ebshop page update 123456 --unpublished
    ebshop page delete 123456
"""

from __future__ import annotations

import typer

from ebshop.client import get_client
from ebshop.models.page import Page
from ebshop.output import Format, output_result

page_app = typer.Typer(help="Online Store page management.")


@page_app.command("list")
def list_pages(
    limit: int = typer.Option(50, "--limit", "-n", help="Max pages to return."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """List Online Store pages."""
    client = get_client()
    params = {"limit": min(limit, 250)}
    data = client.rest_get("/pages.json", params=params)
    pages_list = data.get("pages", [])
    pages = [Page.from_shopify(p).summary() for p in pages_list]
    output_result(
        pages,
        format=format,
        json_fields=json_fields,
        columns=["id", "title", "handle", "author", "published", "updated_at"],
    )


@page_app.command("view")
def view_page(
    id: str = typer.Argument(..., help="Page ID (numeric)."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """View detailed page information."""
    client = get_client()
    data = client.rest_get(f"/pages/{id}.json")
    node = data.get("page")
    if not node:
        output_result(
            {"error": "NOT_FOUND", "message": f"Page '{id}' not found."},
            format=format,
        )
        raise typer.Exit(code=1)

    page = Page.from_shopify(node)
    output_result(page.detail(), format=format, json_fields=json_fields)


@page_app.command("create")
def create_page(
    title: str = typer.Option(..., "--title", "-t", help="Page title."),
    body_html: str = typer.Option(..., "--body-html", "-b", help="Page body (HTML)."),
    published: bool = typer.Option(False, "--published", help="Publish the page immediately."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Create a new Online Store page."""
    page_input: dict = {"title": title, "body_html": body_html}
    if published:
        page_input["published"] = True
    else:
        page_input["published"] = False

    client = get_client()
    data = client.rest_post("/pages.json", json={"page": page_input})
    node = data.get("page")
    if not node:
        output_result(
            {"error": "CREATE_FAILED", "message": "Page creation returned no page."},
            format=format,
        )
        raise typer.Exit(code=1)

    page = Page.from_shopify(node)
    output_result(page.detail(), format=format, json_fields=json_fields)


@page_app.command("update")
def update_page(
    id: str = typer.Argument(..., help="Page ID (numeric)."),
    title: str | None = typer.Option(None, "--title", "-t", help="New title."),
    body_html: str | None = typer.Option(None, "--body-html", "-b", help="New body (HTML)."),
    published: bool | None = typer.Option(None, "--published/--unpublished", help="Publish or unpublish the page."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Update an existing Online Store page."""
    page_input: dict = {"id": int(id)}
    if title is not None:
        page_input["title"] = title
    if body_html is not None:
        page_input["body_html"] = body_html
    if published is not None:
        page_input["published"] = published

    client = get_client()
    data = client.rest_put(f"/pages/{id}.json", json={"page": page_input})
    node = data.get("page")
    if not node:
        output_result(
            {"error": "UPDATE_FAILED", "message": "Page update returned no page."},
            format=format,
        )
        raise typer.Exit(code=1)

    page = Page.from_shopify(node)
    output_result(page.detail(), format=format, json_fields=json_fields)


@page_app.command("delete")
def delete_page(
    id: str = typer.Argument(..., help="Page ID (numeric)."),
) -> None:
    """Delete an Online Store page."""
    client = get_client()
    client.rest_delete(f"/pages/{id}.json")
    output_result({"deleted": True, "id": id})
