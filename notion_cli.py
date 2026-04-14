#!/usr/bin/env python3

# CHQ: Claude AI created this file

import os
import json
import click
import readchar
from notion_client import Client
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("NOTION_TOKEN")
if not token:
    click.echo("❌ NOTION_TOKEN is not set.")
    raise SystemExit(1)
notion = Client(auth=token)
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "databases.json")


# ── Config ─────────────────────────────────────────────────────────────────────

# CHQ: ChatGPT added fflag to turn ondebug print staements during debugging state
DEBUG = os.getenv("DEBUG", "").lower() in ("1", "true", "yes")

def debug(msg):
    if DEBUG:
        click.echo(f"[DEBUG] {msg}")

def load_databases():
    if not os.path.exists(CONFIG_PATH):
        click.echo(f"❌ Config file not found: {CONFIG_PATH}")
        raise SystemExit(1)
    with open(CONFIG_PATH) as f:
        data = json.load(f)
    return data.get("databases", [])

_DB_SCHEMA_CACHE = {}

def get_database_schema(database_id):
    if database_id not in _DB_SCHEMA_CACHE:
        _DB_SCHEMA_CACHE[database_id] = notion.databases.retrieve(database_id=database_id)
    return _DB_SCHEMA_CACHE[database_id]

# ── Helpers ────────────────────────────────────────────────────────────────────

KEYS_FEW = "123456789"
KEYS = "123456789abcdefghijklmnopqrstuvwxyz"
KEYS_EXPANDED = "123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def hyperlink(text, url):
    """Wrap text in a terminal OSC 8 hyperlink."""
    return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"


def pick_from_list(
    items,
    label_fn,
    key_list=KEYS_FEW,
    url_fn=None,
    prompt="Press a key to select, or any other key to quit: ",
):
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


# CHQ: Gemini AI refactored
def pick_multi_from_list(
    items,
    label_fn,
    key_list=KEYS_FEW,
    url_fn=None,
    prompt="Press item keys to toggle, Enter to confirm: ",
):
    key_to_item = {}
    selected_keys = set()

    for i, item in enumerate(items):
        if i >= len(key_list):
            break
        key = key_list[i]
        key_to_item[key] = item

    def render():
        # Clear screen and move cursor to top
        click.echo("\033[2J\033[H", nl=False)
        for key, item in key_to_item.items():
            label = label_fn(item)
            marker = "✓" if key in selected_keys else " "
            click.echo(f"  [{key}] {marker} {label}")

        click.echo()
        selected_labels = [
            label_fn(key_to_item[k]) for k in key_list if k in selected_keys
        ]
        click.echo(
            f"  Selected: {', '.join(selected_labels) if selected_labels else 'none'}"
        )
        click.echo()
        click.echo(prompt, nl=False)

    render()

    while True:
        key = readchar.readkey()

        # Handle Enter (Confirm)
        if key in (readchar.key.ENTER, "\r", "\n"):
            click.echo()
            return [key_to_item[k] for k in key_list if k in selected_keys]

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


def toggle_tag_inclusion(selected_tag_group, excluded_tag_group):
    """
    Let the user move tags between Include and Exclude groups.
    Returns nothing; mutates the sets in place.
    """
    all_tags = sorted(selected_tag_group | excluded_tag_group)

    if not all_tags:
        click.echo("\n⚠️ No tags selected yet.")
        return

    click.echo("\n🔄 Toggle tags between Include and Exclude:\n")
    click.echo("Current status:")
    for tag in all_tags:
        status = "✓ Include" if tag in selected_tag_group else "✗ Exclude"
        click.echo(f"  - {tag}: {status}")

    click.echo()
    chosen_tags = pick_multi_from_list(
        all_tags,
        label_fn=lambda t: (
            f"{t} [{'INCLUDE' if t in selected_tag_group else 'EXCLUDE'}]"
        ),
        key_list=KEYS_EXPANDED,
        prompt="Select tags to toggle, then press Enter: ",
    )

    if not chosen_tags:
        click.echo("No tags toggled.")
        return

    for tag in chosen_tags:
        if tag in selected_tag_group:
            selected_tag_group.remove(tag)
            excluded_tag_group.add(tag)
        elif tag in excluded_tag_group:
            excluded_tag_group.remove(tag)
            selected_tag_group.add(tag)

    click.echo("\n✅ Updated tag inclusion/exclusion.")


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


# CHQ: ChatGPT created function
def format_property_value(prop_data):
    type_name = prop_data.get("type")

    if type_name == "rich_text":
        return extract_plain_text(prop_data.get("rich_text", []))
    elif type_name == "title":
        return extract_plain_text(prop_data.get("title", []))
    elif type_name == "multi_select":
        return ", ".join(i.get("name", "") for i in prop_data.get("multi_select", []))
    elif type_name == "select":
        return (prop_data.get("select") or {}).get("name")
    elif type_name == "url":
        return prop_data.get("url")
    elif type_name == "number":
        return prop_data.get("number")
    elif type_name == "checkbox":
        return prop_data.get("checkbox")
    elif type_name == "date":
        return prop_data.get("date")
    elif type_name == "email":
        return prop_data.get("email")
    elif type_name == "phone_number":
        return prop_data.get("phone_number")
    elif type_name == "status":
        return (prop_data.get("status") or {}).get("name")
    elif type_name == "created_time":
        return prop_data.get("created_time")
    elif type_name == "last_edited_time":
        return prop_data.get("last_edited_time")

    elif type_name == "people":
        return ", ".join(p.get("name", "Unknown") for p in prop_data.get("people", []))
     

# CHQ: ChatGPT created function
def get_title_property_name(database_id):
    result = get_database_schema(database_id)
    props = result.get("properties", {})
    for name, prop in props.items():
        if prop.get("type") == "title":
            return name
    raise ValueError("No title property found")


def print_page_properties(page_id, properties):
    # source: ChatGPT (via Bing)
    if not properties:
        click.echo("No properties found for this page.")
        return

    click.echo(f"Properties for page {page_id}:")
    for prop_name, prop_data in properties.items():
        click.echo(f"- {prop_name} ({prop_data.get('type', 'unknown')}):")
        click.echo(f" {format_property_value(prop_data)}")
        click.echo()


def read_page(page_id):
    page = notion.pages.retrieve(page_id=page_id)
    title = get_page_title(page)
    click.echo(f"\n📄 {title}")
    click.echo("─" * 50)

    click.echo("Page details: ")

    properties = page.get("properties", {})
    print_page_properties(page_id, properties)

    # click.echo("Page details: ")

    click.echo("─" * 50)
    blocks = notion.blocks.children.list(block_id=page_id)
    content = blocks_to_text(blocks.get("results", []))
    click.echo(content if content.strip() else "(Page is empty)")
    click.echo()


# CHQ: Claude AI added function
def show_db_properties(db):
    try:
        result = get_database_schema(db["id"])
        props = result.get("properties", {})
        click.echo(f"\n  Properties: {', '.join(props.keys())}")
    except Exception as e:
        click.echo(f"  ⚠️  Could not load properties: {e}")


def get_tags_property_name(db):
    prop_name = db.get("tags_property")
    if not prop_name:
        raise ValueError("No tags_property configured for this database")
    result = get_database_schema(db["id"])
    props = result.get("properties", {})

    if prop_name not in props:
        raise ValueError(f"Configured tags_property '{prop_name}' not found")

    if props[prop_name].get("type") != "multi_select":
        raise ValueError(f"Configured tags_property '{prop_name}' is not multi_select")

    return prop_name


# CHQ: ChatGPT created so CLI UX goes back to search results to
#      allow additional pages to be read without triggered a
#      duplicate search
def browse_pages(pages):
    """Let user repeatedly open pages from a result list."""
    if not pages:
        return

    while True:
        click.echo("\nSelect a page to read, or any other key to go back:\n")

        selected_page = pick_from_list(
            pages,
            label_fn=lambda p: get_page_title(p),
            key_list=KEYS_EXPANDED,
            url_fn=lambda p: p.get("url"),
            prompt="Choice: ",
        )

        if not selected_page:
            break

        read_page(selected_page["id"])

        # # Pause before returning to results
        # click.echo("\n↩ Press any key to return to results...")
        # readchar.readkey()

        click.echo("\n↩ Press Enter to go back, or SPACEBAR to exit results...")
        key = readchar.readkey()
        if key == " ":
            break


def set_search_fields(props):
    # Only include searchable property types
    SEARCHABLE_TYPES = {
        "title",
        "multi_select",
        "select",
        "rich_text",
        "number",
        "email",
        "phone_number",
        "url",
    }

    search_fields = []
    for name, prop in props.items():
        ptype = prop.get("type")
        if ptype in SEARCHABLE_TYPES:
            search_fields.append({"label": name, "type": ptype})

    if not search_fields:
        click.echo("No searchable properties found.")
        # return

    return search_fields

def set_db_filters():
    db_filter = {}
    if ptype == "title":
        db_filter = {"property": prop_name, "title": {"contains": query}}
    elif ptype == "rich_text":
        db_filter = {"property": prop_name, "rich_text": {"contains": query}}
    elif ptype == "multi_select":
        db_filter = {"property": prop_name, "multi_select": {"contains": query}}
    elif ptype == "select":
        db_filter = {"property": prop_name, "select": {"equals": query}}
    elif ptype == "number":
        try:
            db_filter = {"property": prop_name, "number": {"equals": float(query)}}
        except ValueError:
            click.echo("❌ Invalid number.")
            return
    elif ptype in ("email", "phone_number", "url"):
        db_filter = {"property": prop_name, ptype: {"contains": query}}
    else:
        click.echo(f"⚠️ Unsupported filter type: {ptype}")
        # return
    return db_filter

 

def build_filters(selected_tag_group, excluded_tag_group, tags_property):
    # Build filter
    filters = []

    if selected_tag_group:
        if len(selected_tag_group) == 1:
            filters.append(
                {
                    "property": tags_property,
                    "multi_select": {"contains": list(selected_tag_group)[0]},
                }
            )
        else:
            filters.append(
                {
                    "and": [
                        {"property": tags_property, "multi_select": {"contains": tag}}
                        for tag in selected_tag_group
                    ]
                }
            )

    # Build exclude filters (NOT any of the excluded tags)
    if excluded_tag_group:
        for tag in excluded_tag_group:
            filters.append(
                {"property": tags_property, "multi_select": {"does_not_contain": tag}}
            )

    return filters
      
# ── Actions ────────────────────────────────────────────────────────────────────


# CHQ: Claude AI updated to allow searching by specific properties
def action_search(db):
    # Step 1: fetch real properties from Notion
    click.echo("\n⏳ Loading database properties...")
    try:
        result = get_database_schema(db["id"])
        props = result.get("properties", {})
    except Exception as e:
        click.echo(f"❌ Could not load properties: {e}")
        return

    search_fields = set_search_fields(props)

    # Step 2: pick search field
    click.echo("\n🔎 Search by:\n")
    field = pick_from_list(
        search_fields,
        label_fn=lambda f: f"{f['label']} ({f['type']})",
        key_list=KEYS,
        prompt="Pick a field: ",
    )
    if field is None:
        click.echo("No field selected.")
        return

    query = click.prompt(f"\n  Enter value to search for in \"{field['label']}\"")

    # Step 3: build filter based on field type
    ptype = field["type"]
    prop_name = field["label"]

    db_filter = set_db_filters()
    # Step 4: query the database
    try:
        results = notion.databases.query(database_id=db["id"], filter=db_filter)
    except Exception as e:
        click.echo(f"❌ Error querying database: {e}")
        return

    # CHQ: ChatGPT added message warning when reuslts shown are only a subset of total results
    all_pages = results.get("results", [])
    pages = all_pages[: len(KEYS_EXPANDED)]

    if len(all_pages) > len(KEYS_EXPANDED):
        click.echo(f"⚠️ Showing first {len(KEYS_EXPANDED)} results only.")
    
    if not pages:
        click.echo(f"\nNo pages found where \"{field['label']}\" contains \"{query}\".")
        return

    click.echo(f"\nFound {len(pages)} result(s):\n")
    browse_pages(pages)


# CHQ: Gemini AI made this to target folders at any depth
def action_search_multi_tags(db):
    # 0. Load the local tag category file
    try:
        tag_file = db.get("tag_file")
        if not tag_file:
            click.echo("❌ No tag file configured for this database.")
            return
        tag_file_path = os.path.join(os.path.dirname(__file__), tag_file)

        with open(tag_file_path, "r") as f:
            tag_hierarchy = json.load(f)
    except Exception as e:
        click.echo(f"❌ Could not load tag_categories.json: {e}")
        return

    # CHQ: ChatGPT fixed bug of missing tags_property
    try:
        tags_property = get_tags_property_name(db)
    except Exception as e:
        click.echo(f"❌ Could not find tags property: {e}")
        return

    selected_tag_group = set()
    excluded_tag_group = set()  # CHQ: added by ClaudeAI
    title_filter = ""

    while True:
        if selected_tag_group or excluded_tag_group:
            click.echo("\n🛒 Current Selection Basket:")

            if selected_tag_group:
                click.echo(f"  ✓ Include: {', '.join(sorted(selected_tag_group))}")
            else:
                click.echo("  ✓ Include: none")

            if excluded_tag_group:
                click.echo(f"  ✗ Exclude: {', '.join(sorted(excluded_tag_group))}")
            else:
                click.echo("  ✗ Exclude: none")

            if title_filter:
                click.echo(f"  🔤 Title contains: '{title_filter}'")

            options = [
                {"label": "Search Notion with these tags", "action": "search"},
                {"label": "Add more tags from another category", "action": "continue"},
                {"label": "Add/change title filter", "action": "title"},
                {
                    "label": "Toggle include/exclude for selected tags",
                    "action": "toggle",
                },
                {"label": "Clear all and start over", "action": "clear"},
                {"label": "Cancel and go back", "action": "cancel"},
            ]
            click.echo("\n--- What would you like to do? ---")
            selected_option = pick_from_list(
                options, label_fn=lambda o: o["label"], key_list="123456"
            )

            if not selected_option or selected_option["action"] == "cancel":
                return
            if selected_option["action"] == "clear":
                selected_tag_group.clear()
                excluded_tag_group.clear()
                title_filter = ""
                continue
            if selected_option["action"] == "title":
                title_filter = click.prompt(
                    "\n🔤 Enter title to search for (or press Enter to clear)"
                )
                continue
            if selected_option["action"] == "toggle":
                toggle_tag_inclusion(selected_tag_group, excluded_tag_group)
                continue
            if selected_option["action"] == "search":
                break

        current_level_data = tag_hierarchy
        current_path = []

        # Keep asking the user to pick a sub-folder as long as the data is a dictionary
        while isinstance(current_level_data, dict):
            options = list(current_level_data.keys())

            # Show the user where they are in the folder structure
            path_str = " > ".join(current_path) if current_path else "Root"
            click.echo(f"\n📂 Location: {path_str}")

            selected_key = pick_from_list(
                options,
                label_fn=lambda x: x,
                key_list=KEYS_EXPANDED,
                prompt="Select a category/folder (or any other key to go back): ",
            )

            if not selected_key:
                # This breaks the "dive" and goes back to the main basket menu
                current_level_data = None
                break

            # Move deeper into the dictionary
            current_path.append(selected_key)
            current_level_data = current_level_data[selected_key]

        # If the user backed out, restart the main loop
        if current_level_data is None:
            continue

        # 3. SELECT TAGS
        # At this point, current_level_data MUST be a list
        if isinstance(current_level_data, list):
            selected_tags_from_list = pick_multi_from_list(
                current_level_data,
                label_fn=lambda t: t,
                key_list=KEYS_EXPANDED,
                prompt="Press item keys to toggle, Enter to confirm: ",
            )

            if selected_tags_from_list:
                selected_tag_group.update(selected_tags_from_list)
                # CHQ: Claude AI: remove from excluded list if added beforehand
                excluded_tag_group.difference_update(selected_tags_from_list)
        else:
            click.echo("⚠️ Expected a list of tags but found something else.")

    # 4. PERFORM THE ACTUAL NOTION SEARCH
    if not selected_tag_group and not title_filter:
        click.echo("No tags or title selected.")
        return

    tags_list = list(selected_tag_group)
    click.echo(f"\n🔎 Searching Notion for: {', '.join(tags_list)}")
    if selected_tag_group:
        click.echo(f"   Include tags: {', '.join(selected_tag_group)}")
    if excluded_tag_group:
        click.echo(f"   Excluded tags: {', '.join(excluded_tag_group)}")
    if title_filter:
        click.echo(f"   Title contains: '{title_filter}'")
    click.echo("...")

    title_prop = get_title_property_name(db["id"])

    # Build filter
    filters = build_filters(selected_tag_group, excluded_tag_group, tags_property)


    # CHQ: ChatGPT fixed title filter bug
    if title_filter:
        filters.append({"property": title_prop, "title": {"contains": title_filter}})
    if len(filters) == 1:
        notion_filter = filters[0]
    else:
        notion_filter = {"and": filters}

    try:
        debug(f"tags_property = {tags_property}")
        debug(f"title_prop = {title_prop}")
        debug(json.dumps(notion_filter, indent=2))
        response = notion.databases.query(database_id=db["id"], filter=notion_filter)
        results = response.get("results", [])[: len(KEYS_EXPANDED)]

        if not results:
            click.echo("\nNo pages found matching your criteria.")
            return

        click.echo(f"\nFound {len(results)} result(s):")
        browse_pages(results)
        
    except Exception as error:
        click.echo(f"❌ Notion Query Error: {error}")


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
    # CHQ: ChatGPT made function to dynamically Find
    #      name of title property
    title_prop = get_title_property_name(db["id"])

    if body:
        children.append(
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": body}}]
                },
            }
        )
    try:
        page = notion.pages.create(
            parent={"type": "database_id", "database_id": db["id"]},
            properties={
                title_prop: {"title": [{"type": "text", "text": {"content": title}}]}
            },
            children=children,
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
            children=[
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": text}}]
                    },
                }
            ],
        )
        click.echo(f"\n✅ Appended text to page {page_id}\n")
    except Exception as e:
        click.echo(f"❌ Error: {e}")


# ── Command menu ───────────────────────────────────────────────────────────────


COMMANDS = [
    {"label": "Search pages", "fn": action_search},
    {
        "label": "Search by multiple tags",
        "fn": action_search_multi_tags,
    },  # CHQ: Claude AI added
    {"label": "Read page by ID", "fn": action_read},
    {"label": "Create page", "fn": action_create},
    {"label": "Append to page", "fn": action_append},
    {"label": "Switch database", "fn": None},
    {"label": "Quit", "fn": None},
]


def command_menu(db):
    while True:
        click.echo(f"\n📂 Database: {db['name']}")
        show_db_properties(db)  # CHQ: Claude AI added function
        click.echo("─" * 40)
        cmd = pick_from_list(
            COMMANDS,
            label_fn=lambda c: c["label"],
            key_list=KEYS,
            prompt="Choose an action: ",
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
            prompt="Press a key to select: ",
        )
        if db is None:
            click.echo("\nGoodbye 👋\n")
            break
        command_menu(db)


if __name__ == "__main__":
    cli()
