# core/search.py
# pylint: disable=duplicate-code
"""Filter construction and database query execution for Notion searches.

Provides utilities for building Notion API filter objects from subgroup
definitions and title text, combining multiple filter conditions, and executing
database queries with comprehensive logging and error handling. Supports
subgroup-based tag filtering with per-subgroup NOT logic, whole-subgroup
negation, AND/OR operators between subgroups, and title searches.
"""

# CHQ: Claude rearranged order of imports

import json
import click
from notion_client import APIResponseError

from client import notion, KEYS_EXPANDED
from core.database import get_title_property_name
from utils.debug import debug
from utils.formatting import browse_pages

# ---------------------------------------------------------------------------
# Low-level filter primitives
# ---------------------------------------------------------------------------


def _tag_contains(tags_property: str, tag: str) -> dict:
    return {"property": tags_property, "multi_select": {"contains": tag}}


def _tag_not_contains(tags_property: str, tag: str) -> dict:
    return {"property": tags_property, "multi_select": {"does_not_contain": tag}}


# ---------------------------------------------------------------------------
# Subgroup → Notion filter
# ---------------------------------------------------------------------------


def _build_subgroup_filter(sg: dict, tags_property: str) -> dict | None:
    """
    Convert a single subgroup definition into a Notion filter object.

    Within a subgroup:
      - include_tags are OR'd together  (page must contain at least one)
      - not_tags are AND'd as negations (page must not contain any)
      - the combined result is then AND'd
      - if sg['is_not'] is True the whole thing is wrapped in a NOT

    Returns None if the subgroup has no tags at all.
    """
    include_filters = [_tag_contains(tags_property, t) for t in sg["include_tags"]]
    not_filters = [_tag_not_contains(tags_property, t) for t in sg["not_tags"]]

    if not include_filters and not not_filters:
        return None

    parts = []

    # Include tags: at least one must match → OR
    if len(include_filters) == 1:
        parts.append(include_filters[0])
    elif len(include_filters) > 1:
        parts.append({"or": include_filters})

    # NOT tags: none must match → AND of does_not_contain
    parts.extend(not_filters)

    # Combine include + not parts with AND
    if len(parts) == 1:
        inner = parts[0]
    else:
        inner = {"and": parts}

    # Whole-subgroup negation: wrap in {"not": ...}
    if sg["is_not"]:
        return {"not": inner}

    return inner


# ---------------------------------------------------------------------------
# Flat chain of subgroups with AND/OR operators
# ---------------------------------------------------------------------------


def _build_subgroup_chain_filter(
    subgroups: list[dict], tags_property: str
) -> dict | None:
    """
    Build the filter for the entire subgroup chain.

    The chain is evaluated left-to-right using the operator_after value of
    each subgroup (except the last).  For example:

        SG1 AND SG2 OR SG3

    is modelled as a flat list of (filter, operator) pairs and folded into
    nested Notion AND/OR objects.  Notion's API uses {"and": [...]} and
    {"or": [...]} at the top level, so we collect consecutive same-operator
    runs and wrap them accordingly.

    Strategy: fold left.
      accumulator starts as the first subgroup filter.
      for each subsequent subgroup, combine accumulator with next filter
      using the previous subgroup's operator_after.
    """
    built = []
    for sg in subgroups:
        f = _build_subgroup_filter(sg, tags_property)
        if f is not None:
            built.append((f, sg["operator_after"]))

    if not built:
        return None

    # Fold left over (filter, operator) pairs
    # The last operator_after is irrelevant (nothing follows the last group)
    result = built[0][0]
    for i in range(1, len(built)):
        current_filter = built[i][0]
        # operator connecting result → current is the operator_after of built[i-1]
        op = built[i - 1][1].lower()  # "and" or "or"
        if op == "and":
            # Flatten into existing AND if possible
            if isinstance(result, dict) and "and" in result:
                result = {"and": result["and"] + [current_filter]}
            else:
                result = {"and": [result, current_filter]}
        else:  # "or"
            if isinstance(result, dict) and "or" in result:
                result = {"or": result["or"] + [current_filter]}
            else:
                result = {"or": [result, current_filter]}

    return result


# ---------------------------------------------------------------------------
# Legacy flat filter (used when no subgroups are defined)
# ---------------------------------------------------------------------------


def build_filters(selected_tag_group: set, tags_property: str) -> list:
    """
    Constructs inclusion filters for Notion's API from a flat tag set.
    All tags must be present (AND semantics).

    Args:
        selected_tag_group (set): Tags to include.
        tags_property (str): The name of the property to filter against.

    Returns:
        list: A list of Notion filter condition objects.
    """
    if not selected_tag_group:
        return []

    if len(selected_tag_group) == 1:
        return [_tag_contains(tags_property, list(selected_tag_group)[0])]

    return [{"and": [_tag_contains(tags_property, tag) for tag in selected_tag_group]}]


# ---------------------------------------------------------------------------
# Top-level filter builder
# ---------------------------------------------------------------------------


def build_notion_filter(
    selected_tag_group: set,
    subgroups: list[dict],
    title_filter: str,
    tags_property: str,
    title_prop: str,
) -> dict:
    """
    Combines subgroup (or flat tag) filters and title filter into one
    Notion API filter object.

    If subgroups are defined, uses subgroup chain logic.
    Otherwise falls back to the flat AND-all-tags logic.

    Args:
        selected_tag_group: All tags chosen during browsing (used for flat fallback).
        subgroups: Subgroup definitions (may be empty).
        title_filter: Text to search for in page titles.
        tags_property: Property name for the tags multi_select field.
        title_prop: Property name for the title field.

    Returns:
        A Notion filter dict ready to pass to databases.query().
    """
    filters = []

    if subgroups:
        chain = _build_subgroup_chain_filter(subgroups, tags_property)
        if chain:
            filters.append(chain)
    else:
        filters.extend(build_filters(selected_tag_group, tags_property))

    if title_filter:
        filters.append({"property": title_prop, "title": {"contains": title_filter}})

    if not filters:
        return {}
    if len(filters) == 1:
        return filters[0]
    return {"and": filters}


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


# CHQ: Claude AI made helper function
def log_search_params(
    selected_tag_group: set,
    subgroups: list[dict],
    title_filter: str,
):
    """Log search parameters to the terminal."""
    if subgroups:
        click.echo("\n🔎 Searching Notion with subgroup filters:")
        for i, sg in enumerate(subgroups):
            not_prefix = "NOT " if sg["is_not"] else ""
            include_str = ", ".join(sorted(sg["include_tags"])) or "—"
            not_str = ", ".join(sorted(sg["not_tags"])) or "—"
            click.echo(
                f"   [{i + 1}] {not_prefix}{sg['name']}"
                f"  ✓ {include_str}  ✗ {not_str}"
            )
            if i < len(subgroups) - 1:
                click.echo(f"        ── {sg['operator_after']} ──")
    else:
        tags_list = sorted(selected_tag_group)
        click.echo(f"\n🔎 Searching Notion for: {', '.join(tags_list)}")
        click.echo(f"   Include tags: {', '.join(tags_list)}")

    if title_filter:
        click.echo(f"   Title contains: '{title_filter}'")

    click.echo("...")


# ---------------------------------------------------------------------------
# Main search executor
# ---------------------------------------------------------------------------


def perform_notion_search(
    db: dict,
    selected_tag_group: set,
    subgroups: list[dict],
    title_filter: str,
    tags_property: str,
):
    """
    Compiles all filters and executes the Notion database query.

    Args:
        db: Database config.
        selected_tag_group: All tags chosen during browsing.
        subgroups: Subgroup definitions (may be empty).
        title_filter: Text to search for in titles.
        tags_property: Property name for tags.
    """
    if not selected_tag_group and not title_filter:
        click.echo("No tags or title selected.")
        return

    log_search_params(selected_tag_group, subgroups, title_filter)

    title_prop = get_title_property_name(db["id"])
    notion_filter = build_notion_filter(
        selected_tag_group, subgroups, title_filter, tags_property, title_prop
    )

    if not notion_filter:
        click.echo("⚠️  No filter could be constructed.")
        return

    # CHQ: ClaudeAI made error more specific
    try:
        debug(f"tags_property = {tags_property}")
        debug(f"title_prop = {title_prop}")
        debug(json.dumps(notion_filter, indent=2))

        response = notion.databases.query(database_id=db["id"], filter=notion_filter)
        results = response.get("results", [])[: len(KEYS_EXPANDED)]

        if not results:
            click.echo("\nNo pages found matching your criteria.")
            return

        click.echo(f"\nFound {len(results)} result(s):")
        browse_pages(results)

    except APIResponseError as e:
        click.echo(f"❌ Notion Query Error: {e}")
