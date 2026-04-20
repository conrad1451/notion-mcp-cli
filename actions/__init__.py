# actions/__init__.py
"""
Actions package containing high-level workflows for Notion CLI interactions,
including CRUD operations and menu navigation.
"""
from .navigation import action_search_multi_tags
from .crud import action_read, action_create, action_search

# This tells Pylance/IDE that these are intentional exports
__all__ = [
    "action_search_multi_tags",
    "action_read",
    "action_create",
    "action_search",
]
