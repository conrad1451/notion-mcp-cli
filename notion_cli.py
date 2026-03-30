#!/usr/bin/env python3

# CHQ: Claude AI created this file

import os
import json
import click
from notion_client import Client
from dotenv import load_dotenv

import readchar

load_dotenv()

notion = Client(auth=os.environ["NOTION_TOKEN"])


def extract_plain_text(rich_text_list):
    return "".join(block.get("plain_text", "") for block in rich_text_list)


def get_page_title(page):
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            return extract_plain_text(prop["title"]) or "Untitled"
    return "Untitled"


def print_page_summary(page):
    title = get_page_title(page)
    page_id = page["id"]
    url = page.get("url", "")
    click.echo(f"  📄 {title}")
    click.echo(f"     ID:  {page_id}")
    click.echo(f"     URL: {url}")


def blocks_to_text(blocks):
    lines = []
    for block in blocks:
        btype = block.get("type")
        data = block.get(btype, {})
        rich = data.get("rich_text", [])
        text = extract_plain_text(rich)
        if btype == "heading_1":
            lines.append(f"\n# {text}")
        elif btype == "heading_2":
            lines.append(f"\n## {text}")
        elif btype == "heading_3":
            lines.append(f"\n### {text}")
        elif btype == "bulleted_list_item":
            lines.append(f"  • {text}")
        elif btype == "numbered_list_item":
            lines.append(f"  1. {text}")
        elif btype == "to_do":
            checked = "✅" if data.get("checked") else "☐"
            lines.append(f"  {checked} {text}")
        elif btype == "code":
            lines.append(f"\n```\n{text}\n```")
        elif btype == "divider":
            lines.append("─" * 40)
        elif text:
            lines.append(text)
    return "\n".join(lines)


@click.group()
def cli():
    """Notion terminal CLI — read, search, and create pages."""
    pass


@cli.command()
@click.argument("query")
@click.option("--limit", default=9, show_default=True, help="Max results to show.")
def search(query, limit):
    """Search for pages and press a key to open one."""
    # import readchar

    KEYS = "123456789abcdefghijklmnopqrstuvwxyz"


    """Search your Notion workspace for pages matching QUERY."""
    click.echo(f"\n🔍 Searching for: \"{query}\"\n")
    results = notion.search(query=query, filter={"property": "object", "value": "page"})
    pages = results.get("results", [])[:limit]
    if not pages:
        click.echo("No pages found.")
        return


    # Print results with keys
    key_to_page = {}
    for i, page in enumerate(pages):
        key = KEYS[i]
        key_to_page[key] = page
        title = get_page_title(page)
        url = page.get("url", "")
        click.echo(f"  [{key}] 📄 {title}")
        click.echo(f"       {url}")
        click.echo()

    click.echo("Press a key to open a page, or any other key to quit: ", nl=False)

    key = readchar.readkey()
    click.echo(key)

    if key not in key_to_page:
        click.echo("No matching key, exiting.")
        return

    page = key_to_page[key]
    page_id = page["id"]
    title = get_page_title(page)

    click.echo(f"\n📄 {title}")

    click.echo("─" * 50)
    blocks = notion.blocks.children.list(block_id=page_id)
    content = blocks_to_text(blocks.get("results", []))
    click.echo(content if content.strip() else "(Page is empty)")
    click.echo()

    #click.echo(f"Found {len(pages)} result(s):\n")
    #for page in pages:
    #    print_page_summary(page)
    #    click.echo()


@cli.command()
@click.argument("page_id")
def read(page_id):
    """Read the content of a page by its PAGE_ID."""
    try:
        page = notion.pages.retrieve(page_id=page_id)
        title = get_page_title(page)
        click.echo(f"\n📄 {title}")
        click.echo("─" * 50)
        blocks = notion.blocks.children.list(block_id=page_id)
        content = blocks_to_text(blocks.get("results", []))
        click.echo(content if content.strip() else "(Page is empty)")
        click.echo()
    except Exception as e:
        click.echo(f"❌ Error: {e}")


@cli.command()
@click.argument("title")
@click.option("--parent-id", required=True, help="Page ID of the parent page.")
@click.option("--body", default="", help="Optional body text for the page.")
def create(title, parent_id, body):
    """Create a new page with TITLE under the given parent page."""
    children = []
    if body:
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": body}}]
            }
        })
    try:
        page = notion.pages.create(
            parent={"type": "page_id", "page_id": parent_id},
            properties={
                "title": {
                    "title": [{"type": "text", "text": {"content": title}}]
                }
            },
            children=children
        )
        click.echo(f"\n✅ Page created: {title}")
        click.echo(f"   ID:  {page['id']}")
        click.echo(f"   URL: {page.get('url', '')}\n")
    except Exception as e:
        click.echo(f"❌ Error: {e}")


@cli.command()
@click.argument("page_id")
@click.argument("text")
def append(page_id, text):
    """Append a paragraph of TEXT to an existing page."""
    try:
        notion.blocks.children.append(
            block_id=page_id,
            children=[{
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": text}}]
                }
            }]
        )
        click.echo(f"\n✅ Appended text to page {page_id}\n")
    except Exception as e:
        click.echo(f"❌ Error: {e}")


if __name__ == "__main__":
    cli()
