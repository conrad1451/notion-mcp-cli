# core/navigation.py
"""Interactive tag and filter navigation for Notion database searches.

Provides utilities for building hierarchical tag selection interfaces, managing
subgroup-based tag organisation with per-subgroup NOT logic, and conducting
guided searches through nested tag folders. Supports a 'shopping basket'
workflow for refining search criteria before querying Notion.
"""

import copy  # CHQ: ClaudeAI moved import to top
import click
from client import KEYS_EXPANDED, load_tag_hierarchy

from utils.formatting import pick_from_list, pick_multi_from_list
from core.search import perform_notion_search
from core.database import get_tags_property_name

# ---------------------------------------------------------------------------
# Session-level saved subgroups (persists until the Python process exits)
# ---------------------------------------------------------------------------
_SESSION_SAVED_SUBGROUPS: list[dict] = []


# ---------------------------------------------------------------------------
# Subgroup helpers
# ---------------------------------------------------------------------------


def _make_subgroup(name: str) -> dict:
    """Create an empty subgroup dict."""
    return {
        "name": name,
        "include_tags": set(),  # tags that must be present (OR within group)
        "not_tags": set(),  # tags explicitly negated within this group
        "is_not": False,  # whether the whole subgroup is negated
        "operator_after": "AND",  # operator connecting this group to the next
    }


def _all_assigned_tags(subgroups: list[dict]) -> set:
    """Return every tag assigned to any subgroup (include or not)."""
    assigned = set()
    for sg in subgroups:
        assigned |= sg["include_tags"]
        assigned |= sg["not_tags"]
    return assigned


def _unassigned_tags(selected_tag_group: set, subgroups: list[dict]) -> set:
    return selected_tag_group - _all_assigned_tags(subgroups)


# CHQ: Claude AI created function
def _handle_organiser_action(
    action: str, subgroups: list[dict], selected_tag_group: set
) -> bool:
    """Handle one organiser menu action. Returns False when loop should exit."""
    if action == "done":
        unassigned = _unassigned_tags(selected_tag_group, subgroups)
        if unassigned:
            click.echo(
                f"\n⚠️  The following tags are still unassigned: "
                f"{', '.join(sorted(unassigned))}"
            )
            click.echo("   Please assign all tags before finishing.")
            return True  # stay in loop
        return False  # exit

    if action == "add":
        if len(subgroups) < 10:
            name = f"SG{len(subgroups) + 1}"
            subgroups.append(_make_subgroup(name))
            click.echo(f"✅  Added subgroup '{name}'.")
        else:
            click.echo("⚠️  Maximum of 10 subgroups reached.")

    elif action == "edit":
        sg = _pick_subgroup(subgroups, "Edit which subgroup?")
        if sg:
            _edit_subgroup(sg, selected_tag_group, subgroups)

    elif action == "swap":
        _swap_subgroups(subgroups)

    elif action == "delete":
        sg = _pick_subgroup(subgroups, "Delete which subgroup?")
        if sg:
            subgroups.remove(sg)
            click.echo(f"🗑️  Deleted '{sg['name']}'.")

    elif action == "save":
        sg = _pick_subgroup(subgroups, "Save which subgroup to session?")
        if sg:
            _SESSION_SAVED_SUBGROUPS.append(copy.deepcopy(sg))
            click.echo(f"💾  Saved '{sg['name']}' to session.")

    elif action == "load":
        _load_saved_subgroup(subgroups, selected_tag_group)

    return True  # stay in loop


# CHQ: Claude AI created function
def _handle_edit_action(
    action: str, sg: dict, selected_tag_group: set, all_subgroups: list[dict]
) -> bool:
    """Handle one edit-subgroup action. Returns False when done."""
    if action == "done":
        return False

    if action == "rename":
        new_name = click.prompt("New name", default=sg["name"])
        sg["name"] = new_name.strip() or sg["name"]

    elif action == "add_include":
        available = _available_tags_for_subgroup(
            selected_tag_group, sg, all_subgroups, include_own=True
        )
        if not available:
            click.echo("⚠️  No unassigned tags available.")
            return True
        chosen = pick_multi_from_list(
            sorted(available), label_fn=lambda t: t, key_list=KEYS_EXPANDED
        )
        sg["include_tags"].update(chosen)
        sg["not_tags"] -= set(chosen)

    elif action == "rm_include":
        if sg["include_tags"]:
            chosen = pick_multi_from_list(
                sorted(sg["include_tags"]), label_fn=lambda t: t, key_list=KEYS_EXPANDED
            )
            sg["include_tags"] -= set(chosen)
        else:
            click.echo("⚠️  No include tags to remove.")

    elif action == "add_not":
        available = _available_tags_for_subgroup(
            selected_tag_group, sg, all_subgroups, include_own=True
        )
        if not available:
            click.echo("⚠️  No unassigned tags available.")
            return True
        chosen = pick_multi_from_list(
            sorted(available), label_fn=lambda t: t, key_list=KEYS_EXPANDED
        )
        sg["not_tags"].update(chosen)
        sg["include_tags"] -= set(chosen)

    elif action == "rm_not":
        if sg["not_tags"]:
            chosen = pick_multi_from_list(
                sorted(sg["not_tags"]), label_fn=lambda t: t, key_list=KEYS_EXPANDED
            )
            sg["not_tags"] -= set(chosen)
        else:
            click.echo("⚠️  No NOT tags to remove.")

    elif action == "toggle_not":
        sg["is_not"] = not sg["is_not"]
        click.echo(f"  Subgroup is now {'NOT ' if sg['is_not'] else ''}negated.")

    elif action == "operator":
        op = pick_from_list(
            ["AND", "OR"],
            label_fn=lambda x: x,
            key_list="12",
            prompt="Operator after this subgroup: ",
        )
        if op:
            sg["operator_after"] = op

    return True


# ---------------------------------------------------------------------------
# Subgroup organiser — main entry point
# ---------------------------------------------------------------------------


def organise_into_subgroups(
    selected_tag_group: set,
    subgroups: list[dict],
) -> list[dict]:
    """
    Interactive organiser that lets the user distribute selected_tag_group
    tags into named subgroups with include/NOT semantics and AND/OR operators.

    Args:
        selected_tag_group: The flat pool of tags chosen during browsing.
        subgroups: Existing subgroup list (may be empty on first entry).

    Returns:
        Updated subgroups list.
    """
    is_currently_selecting = True

    while is_currently_selecting:
        _print_subgroup_overview(subgroups, selected_tag_group)

        options = [
            {"label": "➕  Add new subgroup", "action": "add"},
            {"label": "✏️   Edit a subgroup", "action": "edit"},
            {"label": "🔀  Swap two subgroups (reorder)", "action": "swap"},
            {"label": "🗑️   Delete a subgroup", "action": "delete"},
            {"label": "💾  Save a subgroup to session", "action": "save"},
            {"label": "📂  Load a saved subgroup", "action": "load"},
            {"label": "✅  Done", "action": "done"},
        ]

        click.echo("Broski gotta do my test!")
        click.echo("\n--- Subgroup Organiser ---")
        choice = pick_from_list(
            options,
            label_fn=lambda o: o["label"],
            key_list="1234567",
        )

        is_currently_selecting = not choice is None

        if is_currently_selecting:

            # CHQ: Python lists and dicts are passed by reference,
            # so changes to 'subgroups' from within the function
            # '_handle_organiser_action' are automatically
            # reflected outside the function

            is_currently_selecting = _handle_organiser_action(
                choice["action"], subgroups, selected_tag_group
            )

    return subgroups


# ---------------------------------------------------------------------------
# Subgroup overview display
# ---------------------------------------------------------------------------


def _print_subgroup_overview(subgroups: list[dict], selected_tag_group: set):
    click.echo("\n" + "─" * 50)
    click.echo("📦 Subgroups:")
    if not subgroups:
        click.echo("  (none yet)")
    else:
        for i, sg in enumerate(subgroups):
            not_prefix = "NOT " if sg["is_not"] else ""
            include_str = (
                ", ".join(sorted(sg["include_tags"])) if sg["include_tags"] else "—"
            )
            not_str = ", ".join(sorted(sg["not_tags"])) if sg["not_tags"] else "—"
            click.echo(
                f"  [{i + 1}] {not_prefix}{sg['name']}"
                f"  ✓ {include_str}  ✗ {not_str}"
            )
            if i < len(subgroups) - 1:
                click.echo(f"       ── {sg['operator_after']} ──")

    unassigned = _unassigned_tags(selected_tag_group, subgroups)
    if unassigned:
        click.echo(f"\n  ⚠️  Unassigned: {', '.join(sorted(unassigned))}")
    click.echo("─" * 50)


# ---------------------------------------------------------------------------
# Subgroup picker
# ---------------------------------------------------------------------------


def _pick_subgroup(subgroups: list[dict], prompt: str) -> dict | None:
    if not subgroups:
        click.echo("⚠️  No subgroups exist yet.")
        return None
    click.echo(f"\n{prompt}")
    return pick_from_list(
        subgroups,
        label_fn=lambda sg: sg["name"],
        key_list=KEYS_EXPANDED,
    )


# ---------------------------------------------------------------------------
# Subgroup editor
# ---------------------------------------------------------------------------


def _edit_subgroup(sg: dict, selected_tag_group: set, all_subgroups: list[dict]):
    """Interactive menu to edit a single subgroup."""
    has_exited_loop = False

    while not has_exited_loop:
        not_prefix = "NOT " if sg["is_not"] else ""
        include_str = ", ".join(sorted(sg["include_tags"])) or "—"
        not_str = ", ".join(sorted(sg["not_tags"])) or "—"
        click.echo(
            f"\n✏️  Editing: {not_prefix}{sg['name']}"
            f"  |  ✓ Include: {include_str}  |  ✗ NOT: {not_str}"
            f"  |  Operator after: {sg['operator_after']}"
        )

        options = [
            {"label": "Rename this subgroup", "action": "rename"},
            {"label": "Add include tags", "action": "add_include"},
            {"label": "Remove include tags", "action": "rm_include"},
            {"label": "Add NOT tags", "action": "add_not"},
            {"label": "Remove NOT tags", "action": "rm_not"},
            {
                "label": f"Toggle whole-subgroup NOT (currently: {sg['is_not']})",
                "action": "toggle_not",
            },
            {
                "label": f"Set operator after (currently: {sg['operator_after']})",
                "action": "operator",
            },
            {"label": "Done editing", "action": "done"},
        ]

        choice = pick_from_list(
            options,
            label_fn=lambda o: o["label"],
            key_list="12345678",
        )

        has_exited_loop = choice is None or choice["action"] == "done"

        if not has_exited_loop:
            has_exited_loop = not _handle_edit_action(
                choice["action"], sg, selected_tag_group, all_subgroups
            )


def _available_tags_for_subgroup(
    selected_tag_group: set,
    current_sg: dict,
    all_subgroups: list[dict],
    include_own: bool,
) -> set:
    """
    Tags from selected_tag_group that are not yet assigned to any subgroup,
    plus (optionally) tags already in current_sg itself.
    """
    assigned_elsewhere = set()
    for sg in all_subgroups:

        has_tag_in_other_subgroup = sg is current_sg

        if not has_tag_in_other_subgroup:
            assigned_elsewhere |= sg["include_tags"]
            assigned_elsewhere |= sg["not_tags"]

    available = selected_tag_group - assigned_elsewhere
    if not include_own:
        available -= current_sg["include_tags"]
        available -= current_sg["not_tags"]
    return available


# ---------------------------------------------------------------------------
# Swap / reorder
# ---------------------------------------------------------------------------


def _swap_subgroups(subgroups: list[dict]):
    if len(subgroups) < 2:
        click.echo("⚠️  Need at least 2 subgroups to swap.")
        return
    click.echo("\nSwap: pick first subgroup.")
    a = _pick_subgroup(subgroups, "First:")
    if not a:
        return
    click.echo("Pick second subgroup.")
    b = _pick_subgroup(subgroups, "Second:")
    if not b or b is a:
        click.echo("⚠️  Same subgroup selected, no swap performed.")
        return
    i, j = subgroups.index(a), subgroups.index(b)
    subgroups[i], subgroups[j] = subgroups[j], subgroups[i]
    click.echo(f"🔀  Swapped '{a['name']}' and '{b['name']}'.")


# ---------------------------------------------------------------------------
# Save / load session subgroups
# ---------------------------------------------------------------------------


def _load_saved_subgroup(subgroups: list[dict], selected_tag_group: set):
    if not _SESSION_SAVED_SUBGROUPS:
        click.echo("⚠️  No subgroups saved in this session.")
        return
    if len(subgroups) >= 10:
        click.echo("⚠️  Maximum of 10 subgroups already reached.")
        return

    click.echo("\n📂 Saved subgroups:")
    chosen = pick_from_list(
        _SESSION_SAVED_SUBGROUPS,
        label_fn=lambda sg: (
            f"{sg['name']}  ✓ {', '.join(sorted(sg['include_tags'])) or '—'}"
            f"  ✗ {', '.join(sorted(sg['not_tags'])) or '—'}"
        ),
        key_list=KEYS_EXPANDED,
    )
    if not chosen:
        return

    loaded = copy.deepcopy(chosen)

    # Automatically add any tags from the saved subgroup into selected_tag_group
    # so they are treated as if the user had browsed and selected them
    foreign = (loaded["include_tags"] | loaded["not_tags"]) - selected_tag_group
    if foreign:
        selected_tag_group.update(foreign)
        click.echo(f"\n➕  Added to selection pool: {', '.join(sorted(foreign))}")

    # Warn about tags already assigned to another subgroup and drop conflicts
    already_assigned = _all_assigned_tags(subgroups)
    conflicts = (loaded["include_tags"] | loaded["not_tags"]) & already_assigned
    if conflicts:
        click.echo(
            f"⚠️  These tags are already assigned to another subgroup and will "
            f"be removed from the loaded subgroup: {', '.join(sorted(conflicts))}"
        )
        loaded["include_tags"] -= conflicts
        loaded["not_tags"] -= conflicts

    subgroups.append(loaded)
    click.echo(f"✅  Loaded '{loaded['name']}' into current subgroups.")


# ---------------------------------------------------------------------------
# Basket menu (replaces old toggle)
# ---------------------------------------------------------------------------


def show_basket_menu(selected_tag_group, subgroups, title_filter):
    """Display current selection basket and return the user's chosen action."""

    click.echo("\n" + "─" * 40)
    click.echo("🛒 Current Selection Basket:")

    tags_text = ", ".join(sorted(selected_tag_group)) if selected_tag_group else "none"
    click.echo(f"  🏷️  Selected tags: {tags_text}")

    if subgroups:
        click.echo(f"  📦  Subgroups defined: {len(subgroups)}")
        unassigned = _unassigned_tags(selected_tag_group, subgroups)
        if unassigned:
            click.echo(f"  ⚠️   Unassigned: {', '.join(sorted(unassigned))}")
    else:
        click.echo("  📦  Subgroups: none")

    if title_filter:
        click.echo(f"  🔤  Title contains: '{title_filter}'")

    options = [
        {"label": "🚀 Search Notion now", "action": "search"},
        {"label": "📂 Browse tags / Add more", "action": "continue"},
        {"label": "🔤 Set/Change title filter", "action": "title"},
        {"label": "📦 Organise into subgroups", "action": "subgroups"},
        {"label": "🗑️  Clear all", "action": "clear"},
        {"label": "⬅️  Cancel and go back", "action": "cancel"},
    ]

    click.echo("\n--- What would you like to do? ---")
    selected_option = pick_from_list(
        options, label_fn=lambda o: o["label"], key_list="123456"
    )

    return selected_option["action"] if selected_option else "cancel"


# ---------------------------------------------------------------------------
# Tag navigation (unchanged from original)
# ---------------------------------------------------------------------------


def get_tags_property_name_safe(db):
    """Safely retrieve tags property name with error handling."""
    # CHQ: ClaudeAI made error more specific
    try:
        return get_tags_property_name(db)
    except ValueError as e:
        click.echo(f"❌ Could not find tags property: {e}")
        return None


def navigate_and_select_tags(tag_hierarchy, selected_tag_group):
    """
    Recursive-style navigation through the tag folders to pick items.

    Args:
        tag_hierarchy (dict): The hierarchy to navigate.
        selected_tag_group (set): Set to update with new inclusions.
    """
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
                history.pop()

        elif isinstance(current_data, list):
            selected_tags = pick_multi_from_list(
                current_data,
                label_fn=lambda t: t,
                key_list=KEYS_EXPANDED,
            )
            if selected_tags:
                selected_tag_group.update(selected_tags)

            history.pop()


def get_title_filter_from_user():
    """Prompt user for title filter."""
    return click.prompt("\n🔤 Enter title to search for (or press Enter to clear)")


# ---------------------------------------------------------------------------
# Main selection loop
# ---------------------------------------------------------------------------


def run_selection_loop(tag_hierarchy):
    """
    The 'Shopping Basket' loop where users build their search criteria,
    including organising tags into subgroups.

    Args:
        tag_hierarchy (dict): The structured tag data.

    Returns:
        tuple: (selected_tag_group, subgroups, title_filter)
            - selected_tag_group (set): All tags chosen during browsing.
            - subgroups (list[dict]): Subgroup definitions (may be empty).
            - title_filter (str): Optional title substring filter.
    """
    selected_tag_group: set = set()
    subgroups: list[dict] = []
    title_filter: str = ""

    is_currently_selecting = True

    while is_currently_selecting:

        # while True:
        action = show_basket_menu(selected_tag_group, subgroups, title_filter)

        if action == "cancel":
            return set(), [], ""

        if action == "clear":
            selected_tag_group.clear()
            subgroups.clear()
            title_filter = ""

        elif action == "title":
            title_filter = get_title_filter_from_user()

        elif action == "subgroups":
            subgroups = organise_into_subgroups(selected_tag_group, subgroups)

        elif action == "search":
            # Block search if subgroups exist but tags are unassigned
            if subgroups:
                unassigned = _unassigned_tags(selected_tag_group, subgroups)
                if unassigned:
                    click.echo(
                        f"\n🚫 Cannot search: unassigned tags remain: "
                        f"{', '.join(sorted(unassigned))}"
                    )
                    click.echo(
                        "   Use '📦 Organise into subgroups' to assign them first."
                    )

                else:
                    is_currently_selecting = False

        elif action == "continue":
            navigate_and_select_tags(tag_hierarchy, selected_tag_group)

    return selected_tag_group, subgroups, title_filter


# ---------------------------------------------------------------------------
# Top-level CLI action (used by actions/crud.py)
# ---------------------------------------------------------------------------


def action_search_multi_tags(db):
    """CLI Action: Search a database using the hierarchical multi-tag selector."""
    tag_hierarchy = load_tag_hierarchy(db)
    if not tag_hierarchy:
        return

    tags_property = get_tags_property_name_safe(db)
    if not tags_property:
        return

    selected_tag_group, subgroups, title_filter = run_selection_loop(tag_hierarchy)

    if selected_tag_group or title_filter:
        perform_notion_search(
            db,
            selected_tag_group,
            subgroups,
            title_filter,
            tags_property,
        )
