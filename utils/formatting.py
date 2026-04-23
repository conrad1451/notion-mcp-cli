# utils/formatting.py
import click
import readchar
import shutil

from typing import List
from client import notion, KEYS_FEW, KEYS_EXPANDED
from utils.keyboard import get_key_input

# 1. LOW-LEVEL HELPERS (Must be first)
# ─────────────────────────────────────────────────────────────────────────


def extract_plain_text(rich_text_list):
    """Flattens Notion rich_text objects."""
    return "".join(block.get("plain_text", "") for block in rich_text_list)


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


def wrap_text(text: str, max_width: int) -> List[str]:
    """Wrap text to fit terminal width."""
    if len(text) <= max_width:
        return [text]

    wrapped = []
    current = ""
    for word in text.split():
        if len(current) + len(word) + 1 <= max_width:
            current += word + " " if current else word
        else:
            if current:
                wrapped.append(current)
            current = word

    if current:
        wrapped.append(current)

    return wrapped


# 2. FORMATTING & PARSING LOGIC
# ─────────────────────────────────────────────────────────────────────────


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

    val_to_return = None  # CHQ: Gemini AI fixed this

    if type_name == "rich_text":
        val_to_return = extract_plain_text(prop_data.get("rich_text", []))
    elif type_name == "title":
        val_to_return = extract_plain_text(prop_data.get("title", []))
    elif type_name == "multi_select":
        val_to_return = ", ".join(
            i.get("name", "") for i in prop_data.get("multi_select", [])
        )
    elif type_name == "select":
        val_to_return = (prop_data.get("select") or {}).get("name")
    elif type_name == "url":
        val_to_return = prop_data.get("url")  # CHQ: Gemini AI fixed typo
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
        val_to_return = ", ".join(
            p.get("name", "Unknown") for p in prop_data.get("people", [])
        )

    return val_to_return


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


# 3. DISPLAY & PAGINATION LOGIC
# ─────────────────────────────────────────────────────────────────────────


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


def paginate_content(
    content: str, max_width: int, lines_per_page: int = 20
) -> List[str]:
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
    lines = content.split("\n")
    pages = []
    current_page = []

    for line in lines:
        # Wrap long lines
        wrapped = wrap_text(line, max_width)
        current_page.extend(wrapped)

        if len(current_page) >= lines_per_page:
            pages.append("\n".join(current_page[:lines_per_page]))
            current_page = current_page[lines_per_page:]

    if current_page:
        pages.append("\n".join(current_page))

    return pages if pages else ["(Page is empty)"]


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

            if key.lower() == "q":
                click.clear()
                break
            elif key in ["right", "d", "D"] and current_page < total_pages - 1:
                current_page += 1
            elif key in ["left", "a", "A"] and current_page > 0:
                current_page -= 1
            elif key == "home":
                current_page = 0
            elif key == "end":
                current_page = total_pages - 1
        except KeyboardInterrupt:
            click.clear()
            break


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
        "content": content if content.strip() else "(Page is empty)",
    }

    # Get terminal width for pagination
    terminal_width = shutil.get_terminal_size().columns

    # Paginate content
    pages = paginate_content(page_data["content"], terminal_width - 10)

    # Display with navigation
    display_paginated(page_data, pages)


# 4. EXPORTED SELECTION UI (Uses everything above)
# ─────────────────────────────────────────────────────────────────────────


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
