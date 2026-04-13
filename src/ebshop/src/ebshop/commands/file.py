"""File commands — list, view, upload, and delete store files/assets.

Examples:
    ebshop file list
    ebshop file list --limit 20
    ebshop file view 123456
    ebshop file upload --url "https://example.com/image.png" --alt "Product photo"
    ebshop file delete 123456
"""

from __future__ import annotations

import typer

from ebshop.client import ShopifyClient, get_client
from ebshop.models.file import File
from ebshop.output import Format, output_result

file_app = typer.Typer(help="File and asset management.")

# ── GraphQL fragments ──

_FILE_FIELDS = """
    id
    alt
    createdAt
    fileStatus
    ... on GenericFile {
        url
        originalFileSize
        mimeType
    }
    ... on MediaImage {
        image {
            url
            width
            height
        }
        mimeType
    }
"""


@file_app.command("list")
def list_files(
    limit: int = typer.Option(10, "--limit", "-l", help="Max results to return."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """List store files and assets."""
    gql = f"""
        query listFiles($first: Int!, $after: String) {{
            files(first: $first, after: $after) {{
                edges {{
                    node {{
                        {_FILE_FIELDS}
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
        connection_path=["files"],
        max_results=limit,
    )
    files = [File.from_shopify(n).summary() for n in nodes]
    output_result(
        files,
        format=format,
        json_fields=json_fields,
        columns=["id", "alt", "url", "status", "created_at"],
    )


@file_app.command("view")
def view_file(
    id: str = typer.Argument(..., help="File ID (numeric or GID)."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """View details of a specific file."""
    # Try GenericFile first, fall back to MediaImage
    gid = ShopifyClient.to_gid("GenericFile", id)

    gql = f"""
        query getFile($id: ID!) {{
            node(id: $id) {{
                ... on GenericFile {{
                    {_FILE_FIELDS}
                }}
                ... on MediaImage {{
                    {_FILE_FIELDS}
                }}
            }}
        }}
    """

    client = get_client()
    data = client.graphql(gql, variables={"id": gid})
    node = data.get("node")
    if not node:
        output_result(
            {"error": "NOT_FOUND", "message": f"File {id} not found."},
            format=format,
        )
        raise typer.Exit(code=1)

    file = File.from_shopify(node)
    output_result(file.summary(), format=format, json_fields=json_fields)


@file_app.command("upload")
def upload_file(
    url: str = typer.Option(..., "--url", "-u", help="Public URL of the file to upload."),
    alt: str = typer.Option("", "--alt", "-a", help="Alt text description for the file."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Upload a file by URL."""
    gql = f"""
        mutation fileCreate($files: [FileCreateInput!]!) {{
            fileCreate(files: $files) {{
                files {{
                    {_FILE_FIELDS}
                }}
                userErrors {{ field message }}
            }}
        }}
    """

    client = get_client()
    data = client.graphql(gql, variables={
        "files": [{
            "originalSource": url,
            "alt": alt,
        }],
    })

    files = data.get("fileCreate", {}).get("files", [])
    if not files:
        output_result(
            {"error": "UPLOAD_FAILED", "message": "File upload returned no file."},
            format=format,
        )
        raise typer.Exit(code=1)

    file = File.from_shopify(files[0])
    output_result(file.summary(), format=format, json_fields=json_fields)


@file_app.command("delete")
def delete_file(
    id: str = typer.Argument(..., help="File ID (numeric or GID)."),
    format: Format = typer.Option(Format.json, "--format", "-f", help="Output format."),
    json_fields: str | None = typer.Option(
        None, "--json", help="Comma-separated fields to include in JSON output."
    ),
) -> None:
    """Delete a file."""
    gid = ShopifyClient.to_gid("GenericFile", id)

    gql = """
        mutation fileDelete($fileIds: [ID!]!) {
            fileDelete(fileIds: $fileIds) {
                deletedFileIds
                userErrors { field message }
            }
        }
    """

    client = get_client()
    data = client.graphql(gql, variables={"fileIds": [gid]})
    deleted_ids = data.get("fileDelete", {}).get("deletedFileIds", [])

    result = {
        "deleted": True,
        "id": deleted_ids[0] if deleted_ids else gid,
    }
    output_result(result, format=format, json_fields=json_fields)
