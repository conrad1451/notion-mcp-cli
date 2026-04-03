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

KEYS_FEW = "123456789"
KEYS = "123456789abcdefghijklmnopqrstuvwxyz"
KEYS_EXPANDED = "123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

def hyperlink(text, url):
    """Wrap text in a terminal OSC 8 hyperlink."""
    return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"


def pick_from_list(items, label_fn, key_list=KEYS_FEW, url_fn=None, prompt="Press a key to select, or any other key to quit: "):
    """Display a keyed list and return the selected item, or None."""
    key_to_item = {}
    for i, item in enumerate(items):
        if i >= len(key_list):
            break
        key = key_list[i]
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

def pick_multi_from_list_old(items, label_fn, list_size=KEYS_FEW, url_fn=None, prompt="Space to toggle, Enter to confirm: "):
    """Display a keyed list, allow multiple selections, return list of selected items."""
    key_to_item = {}
    key_to_index = {}
    selected_keys = set()

    for i, item in enumerate(items):
        if i >= len(list_size):
            break
        key = list_size[i]
        key_to_item[key] = item
        key_to_index[key] = i

    def render():
        # Clear previously printed lines
        click.echo("\033[2J\033[H", nl=False)  # clear screen
        for i, (key, item) in enumerate(key_to_item.items()):
            label = label_fn(item)
            if url_fn:
                url = url_fn(item)
                if url:
                    label = hyperlink(label, url)
            marker = "✓" if key in selected_keys else " "
            click.echo(f"  [{key}] {marker} {label}")
        click.echo()
        selected_labels = [label_fn(key_to_item[k]) for k in list_size if k in selected_keys]
        click.echo(f"  Selected: {', '.join(selected_labels) if selected_labels else 'none'}")
        click.echo()
        click.echo(prompt, nl=False)

    render()

    while True:
        key = readchar.readkey()

        if key in ("\r", "\n"):
            click.echo()
            return [key_to_item[k] for k in list_size if k in selected_keys]

        if key in (" ", "\x20"):
            # Find which item to toggle based on last non-space key — skip
            # Space alone isn't a key, so we re-render and wait
            render()
            continue

        if key in key_to_item:
            if key in selected_keys:
                selected_keys.discard(key)
            else:
                selected_keys.add(key)
            render()
        else:
            # Any other key — treat as cancel
            click.echo()
            return []

# CHQ: Gemini AI refactored
def pick_multi_from_list(items, label_fn, list_size=KEYS_FEW, url_fn=None, prompt="Space to toggle, Enter to confirm: "):
    key_to_item = {}
    selected_keys = set()

    for i, item in enumerate(items):
        if i >= len(list_size):
            break
        key = list_size[i]
        key_to_item[key] = item

    def render():
        # Clear screen and move cursor to top
        click.echo("\033[2J\033[H", nl=False)
        for key, item in key_to_item.items():
            label = label_fn(item)
            marker = "✓" if key in selected_keys else " "
            click.echo(f"  [{key}] {marker} {label}")
        
        click.echo()
        selected_labels = [label_fn(key_to_item[k]) for k in list_size if k in selected_keys]
        click.echo(f"  Selected: {', '.join(selected_labels) if selected_labels else 'none'}")
        click.echo()
        click.echo(prompt, nl=False)

    render()

    while True:
        key = readchar.readkey()

        # Handle Enter (Confirm)
        if key in (readchar.key.ENTER, "\r", "\n"):
            click.echo()
            return [key_to_item[k] for k in list_size if k in selected_keys]

        # Handle Space (Toggle)
        elif key in (readchar.key.SPACE, " ", "\x20"):
            # If your terminal isn't sending a key BEFORE the space, 
            # we need to know which key the user wants to toggle.
            # Usually, in this UI, users press the 'key' (e.g., '2') to toggle.
            pass 

        # Handle Selection Keys (e.g., '1', '2', 'a', 'b')
        elif key in key_to_item:
            if key in selected_keys:
                selected_keys.discard(key)
            else:
                selected_keys.add(key)
        
        # Handle Escape or Ctrl+C (Cancel/Back)
        elif key in (readchar.key.ESC, "\x1b"):
            click.echo("\nCancelled.")
            return []

        render()
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
        key_list=KEYS,
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
        key_list=KEYS,
        url_fn=lambda p: p.get("url"),
        prompt="Press a key to open a page, or any other key to go back: "
    )
    if page:
        read_page(page["id"])
    else:
        click.echo("No page selected.")

# CHQ: Claude AI created this function
def action_search_multi_tags(db):
    # Step 1: fetch all unique tags from the database
    click.echo("\n⏳ Loading tags...")
    try:
        result = notion.databases.retrieve(database_id=db["id"])
        tag_options = result["properties"]["Tags"]["multi_select"]["options"]
    except Exception as e:
        click.echo(f"❌ Could not load tags: {e}")
        return

    if not tag_options:
        click.echo("No tags found in this database.")
        return

    # Step 2: pick multiple tags
    click.echo("\n🏷️  Select tags to filter by:\n")
    selected_tags = pick_multi_from_list(
        tag_options,
        label_fn=lambda t: t["name"],
    )

    if not selected_tags:
        click.echo("No tags selected.")
        return

    # Step 3: build AND filter across all selected tags
    if len(selected_tags) == 1:
        db_filter = {
            "property": "Tags",
            "multi_select": {"contains": selected_tags[0]["name"]}
        }
    else:
        # CHQ: Claude does some clever coding to "AND" all
        #      of the selected_tags
        db_filter = {
            "and": [
                {"property": "Tags", "multi_select": {"contains": t["name"]}}
                for t in selected_tags
            ]
        }

    # Step 4: query
    try:
        results = notion.databases.query(
            database_id=db["id"],
            filter=db_filter
        )
    except Exception as e:
        click.echo(f"❌ Error querying database: {e}")
        return

    pages = results.get("results", [])[:len(KEYS_EXPANDED)]
    tag_names = ", ".join(t["name"] for t in selected_tags)

    if not pages:
        click.echo(f"\nNo pages found with tags: {tag_names}")
        return

    click.echo(f"\nFound {len(pages)} result(s) tagged [{tag_names}]:\n")
    page = pick_from_list(
        pages,
        label_fn=lambda p: get_page_title(p),
        key_list=KEYS,
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
    {"label": "Search by multiple tags","fn": action_search_multi_tags}, # CHQ: Claude AI added
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
            key_list=KEYS,
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
            key_list=KEYS,
            prompt="Press a key to select: "
        )
        if db is None:
            click.echo("\nGoodbye 👋\n")
            break
        command_menu(db)


if __name__ == "__main__":
    cli()