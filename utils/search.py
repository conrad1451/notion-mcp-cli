# utils/search.py

import click

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


def set_search_fields(props):
    """
    Filters database properties to identify those that are searchable via text or value.

    Args:
        props (dict): The properties dictionary from a database schema.

    Returns:
        list: Searchable fields with their labels and types.
    """

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
    """
    Constructs a Notion API filter object based on property type and query.

    Args:
        ptype (str): The property type (e.g., 'title', 'rich_text', 'number').
        prop_name (str): The name of the property to filter on.
        query (str): The search query value.

    Returns:
        dict: A Notion API filter object, or None if the type is unsupported.
    """

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
