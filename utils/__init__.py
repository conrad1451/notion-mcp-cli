# utils/__init__.py
"""Utilities package with functions for debugging, formatting, and keyboard input.

Exports:
    debug: Output debugging information
    pick_from_list: Select a single item from a list interactively
    pick_multi_from_list: Select multiple items from a list interactively
    browse_pages: Navigate through paginated content
    get_key_input: Capture keyboard input from the user
    set_search_fields: Filters database properties to find those searchable via text or value
"""

from .debug import debug

from .formatting import (
    pick_from_list,
    pick_multi_from_list,
    browse_pages,
)

from .keyboard import get_key_input

from .search import set_search_fields, set_db_filters

# This tells Pylance/IDE that these are intentional exports
__all__ = [
    "debug",
    "pick_from_list",
    "pick_multi_from_list",
    "browse_pages",
    "get_key_input",
    "set_search_fields",
    "set_db_filters",
]
