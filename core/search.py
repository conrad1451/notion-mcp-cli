# core/search.py
from core.database import get_title_property_name
from client import notion, KEYS_EXPANDED

from utils.formatting import debug, browse_pages

import click
import json
 

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
      

def build_notion_filter(
    selected_tag_group, 
    excluded_tag_group, 
    title_filter, 
    tags_property, 
    title_prop
):
    """Combines tags and title filters into one object."""
    filters = build_filters(selected_tag_group, excluded_tag_group, tags_property)
    if title_filter:
        filters.append({"property": title_prop, "title": {"contains": title_filter}})
    return filters[0] if len(filters) == 1 else {"and": filters}


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

