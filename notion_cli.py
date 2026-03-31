#!/usr/bin/env python3

# CHQ: Claude AI created this file

import os
import json
import click
import readchar
from notion_client import Client
from dotenv import load_dotenv

load_dotenv()

notion = Client(auth=os.environ["NOTION_TOKEN"])

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "databases.json")


# ── Config ─────────────────────────────────────────────────────────────────────

def load_databases():
    if not os.path.exists(CONFIG_PATH):
        click.echo(f"❌ Config file not found: {CONFIG_PATH}")
        raise SystemExit(1)
    with open(CONFIG_PATH) as f:
        data = json.load(f)
    return data.get("databases", [])


# ── Helpers ────────────────────────────────────────────────────────────────────

KEYS = "123456789abcdefghijklmnopqrstuvwxyz"
KEYS_EXPANDED = "123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

def hyperlink(text, url):
    """Wrap text in a terminal OSC 8 hyperlink."""
    return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"


def pick_from_list(items, label_fn, url_fn=None, prompt="Press a key to select, or any other key to quit: "):
    """Display a keyed list and return the selected item, or None."""
    key_to_item = {}
    for i, item in enumerate(items):
        if i >= len(KEYS_EXPANDED):
            break
        key = KEYS_EXPANDED[i]
        key_to_item[key] = item
        label = label_fn(item)
        if url_fn:
            url = url_fn(item)
            if url:
                label = hyperlink(label, url)
        click.echo(f"  [{key}] {label}")
    click.echo()
    click.echo(prompt, nl=False)
    key = readchar.readkey()
    click.echo(key)
    return key_to_item.get(key)

def extract_plain_text(rich_text_list):
    return "".join(block.get("plain_text", "") for block in rich_text_list)


def get_page_title(page):
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            return extract_plain_text(prop["title"]) or "Untitled"
    return "Untitled"


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


def read_page(page_id):
    page = notion.pages.retrieve(page_id=page_id)
    title = get_page_title(page)
    click.echo(f"\n📄 {title}")
    click.echo("─" * 50)
    blocks = notion.blocks.children.list(block_id=page_id)
    content = blocks_to_text(blocks.get("results", []))
    click.echo(content if content.strip() else "(Page is empty)")
    click.echo()

# CHQ: Claude AI added function
def show_db_properties(db):
    try:
        result = notion.databases.retrieve(database_id=db["id"])
        props = result.get("properties", {})
        click.echo(f"\n  Properties: {', '.join(props.keys())}")
    except Exception as e:
        click.echo(f"  ⚠️  Could not load properties: {e}")

# ── Actions ────────────────────────────────────────────────────────────────────

# CHQ: Claude AI updated to allow searching by specific properties
def action_search(db):
    # Step 1: pick search field
    SEARCH_FIELDS = [
        {"label": "Name (title)", "type": "title"},
        {"label": "Tags",         "type": "multi_select"},
        {"label": "Area",         "type": "select"},
        {"label": "Type",         "type": "select"},
    ]

    click.echo("\n🔎 Search by:\n")
    field = pick_from_list(
        SEARCH_FIELDS,
        label_fn=lambda f: f["label"],
        prompt="Pick a field: "
    )
    if field is None:
        click.echo("No field selected.")
        return

    query = click.prompt(f"\n  Enter {field['label']} to search for")

    # Step 2: build filter based on field type
    notion_field = field["label"] if field["label"] != "Name (title)" else "Name"

    if field["type"] == "title":
        db_filter = {
            "property": notion_field,
            "title": {"contains": query}
        }
    elif field["type"] == "multi_select":
        db_filter = {
            "property": notion_field,
            "multi_select": {"contains": query}
        }
    elif field["type"] == "select":
        db_filter = {
            "property": notion_field,
            "select": {"equals": query}
        }

    # Step 3: query the database
    try:
        results = notion.databases.query(
            database_id=db["id"],
            filter=db_filter
        )
    except Exception as e:
        click.echo(f"❌ Error querying database: {e}")
        return

    pages = results.get("results", [])[:len(KEYS_EXPANDED)]

    if not pages:
        click.echo(f"\nNo pages found where {field['label']} contains \"{query}\".")
        return

    click.echo(f"\nFound {len(pages)} result(s):\n")
    page = pick_from_list(
        pages,
        label_fn=lambda p: get_page_title(p),
        url_fn=lambda p: p.get("url"),
        prompt="Press a key to open a page, or any other key to go back: "
    )
    if page:
        read_page(page["id"])
    else:
        click.echo("No page selected.")

def action_read(db):
    page_id = click.prompt("\n📄 Enter page ID")
    try:
        read_page(page_id)
    except Exception as e:
        click.echo(f"❌ Error: {e}")


def action_create(db):
    title = click.prompt("\n✏️  Page title")
    body = click.prompt("Body text (optional, press Enter to skip)", default="")
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
            parent={"type": "database_id", "database_id": db["id"]},
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


def action_append(db):
    page_id = click.prompt("\n📎 Enter page ID to append to")
    text = click.prompt("Text to append")
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


# ── Command menu ───────────────────────────────────────────────────────────────

COMMANDS = [
    {"label": "Search pages",      "fn": action_search},
    {"label": "Read page by ID",   "fn": action_read},
    {"label": "Create page",       "fn": action_create},
    {"label": "Append to page",    "fn": action_append},
    {"label": "Switch database",   "fn": None},
    {"label": "Quit",              "fn": None},
]


def command_menu(db):
    while True:
        click.echo(f"\n📂 Database: {db['name']}")
        show_db_properties(db)          # CHQ: Claude AI added function
        click.echo("─" * 40)
        cmd = pick_from_list(
            COMMANDS,
            label_fn=lambda c: c["label"],
            prompt="Choose an action: "
        )

        if cmd is None or cmd["label"] == "Quit":
            click.echo("\nGoodbye 👋\n")
            raise SystemExit(0)
        elif cmd["label"] == "Switch database":
            return  # bubble back up to db selector
        else:
            try:
                cmd["fn"](db)
            except Exception as e:
                click.echo(f"❌ Error: {e}")


# ── Entry point ────────────────────────────────────────────────────────────────

@click.command()
def cli():
    """Notion terminal CLI — interactive database selector."""
    databases = load_databases()

    if not databases:
        click.echo("❌ No databases found in databases.json")
        raise SystemExit(1)

    while True:
        click.echo("\n🗂  Select a database:\n")
        db = pick_from_list(
            databases,
            label_fn=lambda d: d["name"],
            prompt="Press a key to select: "
        )
        if db is None:
            click.echo("\nGoodbye 👋\n")
            break
        command_menu(db)


if __name__ == "__main__":
    cli()