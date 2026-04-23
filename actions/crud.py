# actions/crud.py
from client import KEYS_EXPANDED, load_tag_hierarchy
from core.database import get_database_schema, get_title_property_name
from core.search import perform_notion_search
from actions.navigation import (
    run_selection_loop,
    get_tags_property_name_safe,
    pick_from_list,
)
from utils.formatting import browse_pages, read_page

import click


def action_read():
    # def action_read(db):
    """CLI Action: Read a specific page content using its Notion UUID."""

    # click.echo("The database" + db.get("tags_property"))
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
        perform_notion_search(
            db, selected_tag_group, excluded_tag_group, title_filter, tags_property
        )
