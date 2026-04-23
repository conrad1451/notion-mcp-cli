# core/navigation.py
"""Interactive tag and filter navigation for Notion database searches.

Provides utilities for building hierarchical tag selection interfaces, managing
include/exclude tag groups, and conducting guided searches through nested tag
folders. Supports dynamic tag toggling, title filtering, and a 'shopping basket'
workflow for refining search criteria before querying Notion.
"""
import click

from utils.keyboard import get_key_input
from utils.formatting import extract_plain_text, pick_from_list, pick_multi_from_list
from core.search import build_filters, build_notion_filter, perform_notion_search
from core.database import get_tags_property_name, get_database_schema

from client import KEYS_FEW, KEYS_EXPANDED, load_tag_hierarchy

# KEYS_FEW = "123456789"
# KEYS = "123456789abcdefghijklmnopqrstuvwxyz"
# KEYS_EXPANDED = "123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


# def get_tags_property_name(db):
#     """
#     Validates and retrieves the configured 'multi_select' property for tagging.

#     Args:
#         db (dict): The database config object.

#     Returns:
#         str: The property name if valid.
#     """
#     prop_name = db.get("tags_property")
#     if not prop_name:
#         raise ValueError("No tags_property configured for this database")
#     result = get_database_schema(db["id"])
#     props = result.get("properties", {})

#     if prop_name not in props:
#         raise ValueError(f"Configured tags_property '{prop_name}' not found")

#     if props[prop_name].get("type") != "multi_select":
#         raise ValueError(f"Configured tags_property '{prop_name}' is not multi_select")

#     return prop_name


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


# CHQ: Claude AI made helper function
def show_basket_menu(
    tag_hierarchy, selected_tag_group, excluded_tag_group, title_filter
):
    """Display current selection and return user's chosen action."""
    # If nothing is selected, don't show the menu, just go straight to browsing
    if not (selected_tag_group or excluded_tag_group or title_filter):
        return "continue"

    click.echo("\n" + "─" * 40)
    click.echo("🛒 Current Selection Basket:")

    include_text = (
        ", ".join(sorted(selected_tag_group)) if selected_tag_group else "none"
    )
    click.echo(f"  ✓ Include: {include_text}")

    exclude_text = (
        ", ".join(sorted(excluded_tag_group)) if excluded_tag_group else "none"
    )
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
def get_tags_property_name_safe(db):
    """Safely retrieve tags property name with error handling."""
    try:
        return get_tags_property_name(db)
    except Exception as e:
        click.echo(f"❌ Could not find tags property: {e}")
        return None


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
                history.pop()  # Go up one level

        elif isinstance(current_data, list):
            selected_tags = pick_multi_from_list(
                current_data,
                label_fn=lambda t: t,
                key_list=KEYS_EXPANDED,
            )
            if selected_tags:
                selected_tag_group.update(selected_tags)
                excluded_tag_group.difference_update(selected_tags)

            history.pop()  # Return to the parent folder after selection

        if not history:
            break


# CHQ: Claude AI made helper function
def get_title_filter_from_user():
    """Prompt user for title filter."""
    return click.prompt("\n🔤 Enter title to search for (or press Enter to clear)")


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
        action = show_basket_menu(
            tag_hierarchy, selected_tag_group, excluded_tag_group, title_filter
        )

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
            navigate_and_select_tags(
                tag_hierarchy, selected_tag_group, excluded_tag_group
            )

    return selected_tag_group, excluded_tag_group, title_filter


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
        perform_notion_search(
            db, selected_tag_group, excluded_tag_group, title_filter, tags_property
        )
