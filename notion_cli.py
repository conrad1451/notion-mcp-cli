#!/usr/bin/env python3

# CHQ: Claude AI created this file
# CHQ: Gemini AI added docstrings

import os
import json
import click
import readchar
from notion_client import Client
from dotenv import load_dotenv
import shutil
from typing import List

if os.name == 'nt':
    import msvcrt # pylint: disable=import-error
else:
    import tty # pylint: disable=import-error
    import termios # pylint: disable=import-error
    
import sys 

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
    """
    Prints a debug message to the console if the DEBUG environment variable is enabled.
    
    Args:
        msg (str): The message to display.
    """
    if DEBUG:
        click.echo(f"[DEBUG] {msg}")

def load_databases():
    """
    Loads database configurations from the local JSON file.
    
    Returns:
        list: A list of database configuration dictionaries.
    
    Raises:
        SystemExit: If the configuration file is missing.
    """
    if not os.path.exists(CONFIG_PATH):
        click.echo(f"❌ Config file not found: {CONFIG_PATH}")
        raise SystemExit(1)
    with open(CONFIG_PATH) as f:
        data = json.load(f)
    return data.get("databases", [])

_DB_SCHEMA_CACHE = {}

def get_database_schema(database_id):
    """
    Retrieves and caches the Notion database schema to minimize API calls.
    
    Args:
        database_id (str): The Notion UUID for the database.
        
    Returns:
        dict: The database object metadata from Notion.
    """
    if database_id not in _DB_SCHEMA_CACHE:
        _DB_SCHEMA_CACHE[database_id] = notion.databases.retrieve(database_id=database_id)
    return _DB_SCHEMA_CACHE[database_id]

# ── Helpers ────────────────────────────────────────────────────────────────────

KEYS_FEW = "123456789"
KEYS = "123456789abcdefghijklmnopqrstuvwxyz"
KEYS_EXPANDED = "123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def hyperlink(text, url):
    """
    Wraps text in terminal-specific OSC 8 escape sequences to create clickable links.
    
    Args:
        text (str): The display text.
        url (str): The destination URL.
        
    Returns:
        str: The formatted escape string.
    """
    return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"


def pick_from_list(
    items,
    label_fn,
    key_list=KEYS_FEW,
    url_fn=None,
    prompt="Press a key to select, or any other key to quit: ",
):
    """
    Displays a list of items with single-key shortcuts for user selection.
    
    Args:
        items (list): The collection of items to choose from.
        label_fn (callable): Function to extract a display string from an item.
        key_list (str): String of characters to use as shortcuts.
        url_fn (callable, optional): Function to extract a URL for terminal hyperlinking.
        prompt (str): The input prompt message.
        
    Returns:
        any: The selected item, or None if the user cancels.
    """
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
    prompt="Press item keys to toggle, Enter to confirm: ",
):
    """
    Provides an interactive multi-select UI with visual checkmarks and toggle logic.
    
    Args:
        items (list): Items to display.
        label_fn (callable): Function to format the item label.
        key_list (str): Shortcuts for selection.
        url_fn (callable, optional): URL extractor for hyperlinks.
        prompt (str): Interaction instructions.
        
    Returns:
        list: All items selected by the user upon confirmation.
    """
    key_to_item = {}
    selected_keys = set()

    for i, item in enumerate(items):
        if i >= len(key_list):
            break
        key = key_list[i]
        key_to_item[key] = item

    def render():
        # Clear screen and move cursor to top
        # click.echo("\033[2J\033[H", nl=False)
        click.clear()
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
    Interactive utility to move tags between 'Include' and 'Exclude' sets.
    
    Args:
        selected_tag_group (set): Set of tags to be included in search.
        excluded_tag_group (set): Set of tags to be explicitly filtered out.
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
    """
    Flattens Notion's rich_text array into a single plain-text string.
    
    Args:
        rich_text_list (list): Notion rich_text objects.
        
    Returns:
        str: Concatenated plain text.
    """
    return "".join(block.get("plain_text", "") for block in rich_text_list)


def get_page_title(page):
    """
    Locates and extracts the 'title' property from a Notion page object.
    
    Args:
        page (dict): The Notion page object.
        
    Returns:
        str: The plain-text title or 'Untitled'.
    """
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            return extract_plain_text(prop["title"]) or "Untitled"
    return "Untitled"


def blocks_to_text(blocks):
    """
    Converts Notion block objects into Markdown-style terminal text.
    
    Args:
        blocks (list): List of Notion block objects.
        
    Returns:
        str: Formatted string representing the page content.
    """
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
    """
    Parses various Notion property types into human-readable strings.
    
    Args:
        prop_data (dict): The specific property data from a page.
        
    Returns:
        str/int/bool: The formatted value based on the property type.
    """
    type_name = prop_data.get("type")

    val_to_return = None # CHQ: Gemini AI fixed this

    if type_name == "rich_text":
        val_to_return = extract_plain_text(prop_data.get("rich_text", []))
    elif type_name == "title":
        val_to_return = extract_plain_text(prop_data.get("title", []))
    elif type_name == "multi_select":
        val_to_return = ", ".join(i.get("name", "") for i in prop_data.get("multi_select", []))
    elif type_name == "select":
        val_to_return = (prop_data.get("select") or {}).get("name")
    elif type_name == "url":
        val_to_return = prop_data.get("url") # CHQ: Gemini AI fixed typo
    elif type_name == "number":
        val_to_return = prop_data.get("number")
    elif type_name == "checkbox":
        val_to_return = prop_data.get("checkbox")
    elif type_name == "date":
        val_to_return = prop_data.get("date")
    elif type_name == "email":
        val_to_return = prop_data.get("email")
    elif type_name == "phone_number":
        val_to_return = prop_data.get("phone_number")
    elif type_name == "status":
        val_to_return = (prop_data.get("status") or {}).get("name")
    elif type_name == "created_time":
        val_to_return = prop_data.get("created_time")
    elif type_name == "last_edited_time":
        val_to_return = prop_data.get("last_edited_time")

    elif type_name == "people":
        val_to_return = ", ".join(p.get("name", "Unknown") for p in prop_data.get("people", []))
    
    return val_to_return

# CHQ: ChatGPT created function
def get_title_property_name(database_id):
    """
    Identifies which database property is designated as the 'title' type.
    
    Args:
        database_id (str): The database to inspect.
        
    Returns:
        str: The name of the title property.
    """
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
    """
    Fetches page metadata and content, then triggers the paginated terminal viewer.
    
    Args:
        page_id (str): The UUID of the Notion page.
    """
    page = notion.pages.retrieve(page_id=page_id)
    title = get_page_title(page)
    
    properties = page.get("properties", {})
    blocks = notion.blocks.children.list(block_id=page_id)
    content = blocks_to_text(blocks.get("results", []))
    
    # Prepare page data
    page_data = {
        "page_id": page_id,
        "title": title,
        "properties": properties,
        "content": content if content.strip() else "(Page is empty)"
    }
    
    # Get terminal width for pagination
    terminal_width = shutil.get_terminal_size().columns
    
    # Paginate content
    pages = paginate_content(page_data["content"], terminal_width - 10)
    
    # Display with navigation
    display_paginated(page_data, pages)


def paginate_content(content: str, max_width: int, lines_per_page: int = 20) -> List[str]:
    """
    Splits a large string into chunks based on terminal line constraints.
    
    Args:
        content (str): The full page text.
        max_width (int): Character width for wrapping.
        lines_per_page (int): Maximum lines to display at once.
        
    Returns:
        List[str]: A list of content strings for each page.
    """
    """Split content into pages based on line count."""
    lines = content.split('\n')
    pages = []
    current_page = []
    
    for line in lines:
        # Wrap long lines
        wrapped = wrap_text(line, max_width)
        current_page.extend(wrapped)
        
        if len(current_page) >= lines_per_page:
            pages.append('\n'.join(current_page[:lines_per_page]))
            current_page = current_page[lines_per_page:]
    
    if current_page:
        pages.append('\n'.join(current_page))
    
    return pages if pages else ["(Page is empty)"]


def wrap_text(text: str, max_width: int) -> List[str]:
    """Wrap text to fit terminal width."""
    if len(text) <= max_width:
        return [text]
    
    wrapped = []
    current = ""
    for word in text.split():
        if len(current) + len(word) + 1 <= max_width:
            current += (word + " " if current else word)
        else:
            if current:
                wrapped.append(current)
            current = word
    
    if current:
        wrapped.append(current)
    
    return wrapped


def display_paginated(page_data: dict, pages: List[str]):
    """
    The main UI loop for reading content with arrow-key navigation.
    
    Args:
        page_data (dict): Metadata including title and properties.
        pages (list): The list of paginated content strings.
    """
    current_page = 0
    total_pages = len(pages)
    
    while True:
        # Clear screen
        click.clear()
        
        # Display header
        click.echo(f"\n📄 {page_data['title']}")
        click.echo("─" * 50)
        
        # Display page properties
        print_page_properties(page_data["page_id"], page_data["properties"])
        
        click.echo("─" * 50)
        
        # Display current page content
        click.echo(pages[current_page])
        
        # Display footer with navigation info
        click.echo("\n" + "─" * 50)
        click.echo(f"Page {current_page + 1}/{total_pages}")
        
        if total_pages > 1:
            nav_text = "Use ← → or A/D to navigate | Q to quit"
            click.echo(nav_text)
        else:
            click.echo("Press Q to quit")
        
        # Get user input
        try:
            key = get_key_input()
            
            if key.lower() == 'q':
                click.clear()
                break
            elif key in ['right', 'd', 'D'] and current_page < total_pages - 1:
                current_page += 1
            elif key in ['left', 'a', 'A'] and current_page > 0:
                current_page -= 1
            elif key == 'home':
                current_page = 0
            elif key == 'end':
                current_page = total_pages - 1
        except KeyboardInterrupt:
            click.clear()
            break


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


def get_key_input() -> str:
    """
    Cross-platform handler to capture raw keyboard input, including escape sequences.
    
    Returns:
        str: A normalized string representing the key (e.g., 'left', 'q', 'd').
    """
    # import sys
    # import os
    
    if os.name == 'nt':  # Windows
        # import msvcrt
        key = msvcrt.getch()
        if key == b'\xe0':  # Special key prefix
            key = msvcrt.getch()
            special_keys = {b'M': 'left', b'P': 'right', b'G': 'home', b'O': 'end'}
            return special_keys.get(key, key.decode('utf-8', errors='ignore').lower())
        return key.decode('utf-8', errors='ignore').lower()
    else:  # macOS and Linux
        # import tty
        # import termios
        
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            key = sys.stdin.read(1)
            
            # Handle escape sequences for arrow keys
            if key == '\x1b':
                next_char = sys.stdin.read(1)
                if next_char == '[':
                    arrow = sys.stdin.read(1)
                    arrows = {'A': 'up', 'B': 'down', 'C': 'right', 'D': 'left'}
                    return arrows.get(arrow, arrow.lower())
            
            return key.lower()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
# CHQ: Claude AI added function
def show_db_properties(db):
    """
    Displays the available property names for the currently selected database.
    
    Args:
        db (dict): The database config object.
    """
    try:
        result = get_database_schema(db["id"])
        props = result.get("properties", {})
        click.echo(f"\n  Properties: {', '.join(props.keys())}")
    except Exception as e:
        click.echo(f"  ⚠️  Could not load properties: {e}")


def get_tags_property_name(db):
    """
    Validates and retrieves the configured 'multi_select' property for tagging.
    
    Args:
        db (dict): The database config object.
        
    Returns:
        str: The property name if valid.
    """
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
    """
    UI loop that allows users to select and read multiple pages from search results.
    
    Args:
        pages (list): List of Notion page objects.
    """
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
    """
    Filters database properties to identify those that are searchable via text or value.
    
    Args:
        props (dict): The properties dictionary from a database schema.
        
    Returns:
        list: Searchable fields with their labels and types.
    """
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

# CHQ: Gemini AI corrected signature of function
def set_db_filters(ptype, prop_name, query):
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
    """
    Constructs the logic for inclusion and exclusion filters for Notion's API.
    
    Args:
        selected_tag_group (set): Tags to include.
        excluded_tag_group (set): Tags to exclude.
        tags_property (str): The name of the property to filter against.
        
    Returns:
        list: A list of Notion filter condition objects.
    """

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
      

# CHQ: Claude AI made helper function
def load_tag_hierarchy(db):
    """
    Reads the hierarchical JSON file used for organized tag browsing.
    
    Args:
        db (dict): The database config object.
        
    Returns:
        dict/None: The parsed hierarchy or None if failed.
    """
    """Load and parse the tag hierarchy file."""
    try:
        tag_file = db.get("tag_file")
        if not tag_file:
            click.echo("❌ No tag file configured for this database.")
            return None
        
        tag_file_path = os.path.join(os.path.dirname(__file__), tag_file)
        with open(tag_file_path, "r") as f:
            return json.load(f)
    except Exception as e:
        click.echo(f"❌ Could not load tag_categories.json: {e}")
        return None


# CHQ: Claude AI made helper function
def get_tags_property_name_safe(db):
    """Safely retrieve tags property name with error handling."""
    try:
        return get_tags_property_name(db)
    except Exception as e:
        click.echo(f"❌ Could not find tags property: {e}")
        return None

# CHQ: Claude AI made helper function
def run_selection_loop(tag_hierarchy):
    """
    The 'Shopping Basket' loop where users build their search criteria.
    
    Args:
        tag_hierarchy (dict): The structured tag data.
        
    Returns:
        tuple: (selected_tags, excluded_tags, title_filter_string)
    """
    """Main loop for user to select tags and filters."""
    selected_tag_group = set()
    excluded_tag_group = set()
    title_filter = ""
    
    while True:
        action = show_basket_menu(tag_hierarchy, selected_tag_group, excluded_tag_group, 
                                  title_filter)
        
        if action == "cancel":
            return set(), set(), ""
        if action == "clear":
            selected_tag_group.clear()
            excluded_tag_group.clear()
            title_filter = ""
            continue
        if action == "title":
            title_filter = get_title_filter_from_user()
            continue
        if action == "toggle":
            toggle_tag_inclusion(selected_tag_group, excluded_tag_group)
            continue
        if action == "search":
            break
        if action == "continue":
            navigate_and_select_tags(tag_hierarchy, selected_tag_group, 
                                    excluded_tag_group)
    
    return selected_tag_group, excluded_tag_group, title_filter

# CHQ: Claude AI made helper function
def show_basket_menu(tag_hierarchy, selected_tag_group, excluded_tag_group, title_filter):
    """Display current selection and return user's chosen action."""
    # If nothing is selected, don't show the menu, just go straight to browsing
    if not (selected_tag_group or excluded_tag_group or title_filter):
        return "continue"

    click.echo("\n" + "─" * 40)
    click.echo("🛒 Current Selection Basket:")
    
    include_text = ", ".join(sorted(selected_tag_group)) if selected_tag_group else "none"
    click.echo(f"  ✓ Include: {include_text}")
    
    exclude_text = ", ".join(sorted(excluded_tag_group)) if excluded_tag_group else "none"
    click.echo(f"  ✗ Exclude: {exclude_text}")
    
    if title_filter:
        click.echo(f"  🔤 Title contains: '{title_filter}'")
    
    options = [
        {"label": "🚀 Search Notion now", "action": "search"},
        {"label": "📂 Browse tags / Add more", "action": "continue"},
        {"label": "🔤 Set/Change title filter", "action": "title"},
        {"label": "🔄 Toggle Include/Exclude status", "action": "toggle"},
        {"label": "🗑️  Clear all", "action": "clear"},
        {"label": "⬅️  Cancel and go back", "action": "cancel"},
    ]

    click.echo("\n--- What would you like to do? ---")
    selected_option = pick_from_list(
        options, label_fn=lambda o: o["label"], key_list="123456"
    )
    
    return selected_option["action"] if selected_option else "cancel"


# CHQ: Claude AI made helper function
def get_title_filter_from_user():
    """Prompt user for title filter."""
    return click.prompt(
        "\n🔤 Enter title to search for (or press Enter to clear)"
    )


# CHQ: Claude AI made helper function
# Gemini AI added tag_heirarchy as parameter
def navigate_and_select_tags(tag_hierarchy, selected_tag_group, excluded_tag_group):
    """
    Recursive-style navigation through the tag folders to pick items.
    
    Args:
        tag_hierarchy (dict): The hierarchy to navigate.
        selected_tag_group (set): Set to update with new inclusions.
        excluded_tag_group (set): Set to update with exclusions.
    """
    # Use a stack to keep track of folder levels so 'Back' works properly
    history = [(tag_hierarchy, "Root")]
    
    while history:
        current_data, folder_name = history[-1]
        
        if isinstance(current_data, dict):
            options = list(current_data.keys())
            click.echo(f"\n📂 Location: {folder_name}")
            
            selected_key = pick_from_list(
                options,
                label_fn=lambda x: f"[{x}]",
                key_list=KEYS_EXPANDED,
                prompt="Select a category (or any other key to go UP): ",
            )
            
            if selected_key:
                history.append((current_data[selected_key], selected_key))
            else:
                history.pop() # Go up one level
        
        elif isinstance(current_data, list):
            selected_tags = pick_multi_from_list(
                current_data,
                label_fn=lambda t: t,
                key_list=KEYS_EXPANDED,
            )
            if selected_tags:
                selected_tag_group.update(selected_tags)
                excluded_tag_group.difference_update(selected_tags)
            
            history.pop() # Return to the parent folder after selection
            
        if not history:
            break



# CHQ: Claude AI made helper function
def perform_notion_search(db, selected_tag_group, excluded_tag_group, 
                         title_filter, tags_property):
    """
    Compiles all filters and executes the Notion database query.
    
    Args:
        db (dict): Database config.
        selected_tag_group (set): Tags to include.
        excluded_tag_group (set): Tags to exclude.
        title_filter (str): Text to search for in titles.
        tags_property (str): Property name for tags.
    """
    if not selected_tag_group and not title_filter:
        click.echo("No tags or title selected.")
        return
    
    log_search_params(selected_tag_group, excluded_tag_group, title_filter)
    
    title_prop = get_title_property_name(db["id"])
    notion_filter = build_notion_filter(selected_tag_group, excluded_tag_group, 
                                       title_filter, tags_property, title_prop)
    
    try:
        debug(f"tags_property = {tags_property}")
        debug(f"title_prop = {title_prop}")
        debug(json.dumps(notion_filter, indent=2))
        
        response = notion.databases.query(database_id=db["id"], 
                                         filter=notion_filter)
        results = response.get("results", [])[:len(KEYS_EXPANDED)]
        
        if not results:
            click.echo("\nNo pages found matching your criteria.")
            return
        
        click.echo(f"\nFound {len(results)} result(s):")
        browse_pages(results)
        
    except Exception as error:
        click.echo(f"❌ Notion Query Error: {error}")


# CHQ: Claude AI made helper function
def log_search_params(selected_tag_group, excluded_tag_group, title_filter):
    """Log search parameters to user."""
    tags_list = list(selected_tag_group)
    click.echo(f"\n🔎 Searching Notion for: {', '.join(tags_list)}")
    
    if selected_tag_group:
        click.echo(f"   Include tags: {', '.join(selected_tag_group)}")
    if excluded_tag_group:
        click.echo(f"   Excluded tags: {', '.join(excluded_tag_group)}")
    if title_filter:
        click.echo(f"   Title contains: '{title_filter}'")
    
    click.echo("...")


# CHQ: Claude AI made helper function
def build_notion_filter(selected_tag_group, excluded_tag_group, title_filter, 
                       tags_property, title_prop):
    """Construct the Notion API filter object."""
    filters = build_filters(selected_tag_group, excluded_tag_group, tags_property)
    
    if title_filter:
        filters.append({
            "property": title_prop,
            "title": {"contains": title_filter}
        })
    
    if len(filters) == 1:
        return filters[0]
    else:
        return {"and": filters}

# ── Actions ────────────────────────────────────────────────────────────────────


# CHQ: Claude AI updated to allow searching by specific properties
def action_search(db):
    """CLI Action: Search a database by a single chosen property."""

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

    # CHQ: Gemini AI corrected function call to include arguments
    db_filter = set_db_filters(ptype, prop_name, query)
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
    """CLI Action: Search a database using the hierarchical multi-tag selector."""
    # Load configuration
    tag_hierarchy = load_tag_hierarchy(db)
    if not tag_hierarchy:
        return
    
    tags_property = get_tags_property_name_safe(db)
    if not tags_property:
        return
    
    # User selection loop
    selected_tag_group, excluded_tag_group, title_filter = run_selection_loop(
        tag_hierarchy
    )
    
    # Perform search if valid
    if selected_tag_group or title_filter:
        perform_notion_search(db, selected_tag_group, excluded_tag_group, 
                            title_filter, tags_property)


def action_read(db):
    """CLI Action: Read a specific page content using its Notion UUID."""

    page_id = click.prompt("\n📄 Enter page ID")
    try:
        read_page(page_id)
    except Exception as e:
        click.echo(f"❌ Error: {e}")


def action_create(db):
    """CLI Action: Create a new page with a title and optional body text."""

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
    """CLI Action: Add a text paragraph to the end of an existing page."""

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
    """
    Displays the main action menu for a specific database.
    
    Args:
        db (dict): The currently active database config.
    """

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
