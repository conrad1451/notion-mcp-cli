# core/database.py
from client import notion, _DB_SCHEMA_CACHE

import click


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


def get_database_schema(database_id):
    """
    Retrieves and caches the Notion database schema to minimize API calls.

    Args:
        database_id (str): The Notion UUID for the database.

    Returns:
        dict: The database object metadata from Notion.
    """
    if database_id not in _DB_SCHEMA_CACHE:
        _DB_SCHEMA_CACHE[database_id] = notion.databases.retrieve(
            database_id=database_id
        )
    return _DB_SCHEMA_CACHE[database_id]


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
