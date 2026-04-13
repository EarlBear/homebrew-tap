"""Blog commands — list blogs, view blog, list articles, create article.

Examples:
    ebshop blog list
    ebshop blog view 123456789
    ebshop blog articles 123456789
    ebshop blog create-article 123456789 --title "My Post" --body-html "<p>Hello</p>"
"""

from __future__ import annotations

import typer

from ebshop.client import get_client
from ebshop.models.blog import Article, Blog
from ebshop.output import Format, output_result

blog_app = typer.Typer(help="Blog management — list, view, articles, create-article.")


@blog_app.command("list")
def list_blogs(
    limit: int = typer.Option(50, "--limit", "-l", help="Max blogs to return."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """List all blogs in the store."""
    client = get_client()
    data = client.rest_get("/blogs.json")
    raw_blogs = data.get("blogs", [])
    blogs = [Blog.from_shopify(b).summary() for b in raw_blogs[:limit]]
    output_result(blogs, format=format, json_fields=json_fields,
                  columns=["id", "title", "handle", "commentable", "created_at"])


@blog_app.command()
def view(
    blog_id: str = typer.Argument(..., help="Blog ID (numeric)."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """View details of a single blog."""
    client = get_client()
    data = client.rest_get(f"/blogs/{blog_id}.json")
    raw = data.get("blog", {})
    blog = Blog.from_shopify(raw)
    output_result(blog.summary(), format=format, json_fields=json_fields)


@blog_app.command()
def articles(
    blog_id: str = typer.Argument(..., help="Blog ID (numeric)."),
    limit: int = typer.Option(50, "--limit", "-l", help="Max articles to return."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """List articles for a blog."""
    client = get_client()
    data = client.rest_get(f"/blogs/{blog_id}/articles.json")
    raw_articles = data.get("articles", [])
    result = [Article.from_shopify(a).summary() for a in raw_articles[:limit]]
    output_result(result, format=format, json_fields=json_fields,
                  columns=["id", "title", "author", "tags", "published_at", "created_at"])


@blog_app.command("create-article")
def create_article(
    blog_id: str = typer.Argument(..., help="Blog ID to create the article in."),
    title: str = typer.Option(..., "--title", help="Article title."),
    body_html: str = typer.Option(..., "--body-html", help="Article body as HTML."),
    author: str | None = typer.Option(None, "--author", help="Author name."),
    tags: str | None = typer.Option(None, "--tags", help="Comma-separated tags."),
    published: bool = typer.Option(False, "--published", help="Publish immediately."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Create a new article in a blog."""
    client = get_client()
    article_data: dict = {
        "title": title,
        "body_html": body_html,
        "published": published,
    }
    if author:
        article_data["author"] = author
    if tags:
        article_data["tags"] = tags

    data = client.rest_post(
        f"/blogs/{blog_id}/articles.json",
        json={"article": article_data},
    )
    raw = data.get("article", {})
    article = Article.from_shopify(raw)
    output_result(article.detail(), format=format, json_fields=json_fields)
