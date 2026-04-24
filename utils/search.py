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
