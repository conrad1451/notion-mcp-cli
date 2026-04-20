import click
from client import load_databases
from actions.crud import action_read, action_create, action_search, action_append
from actions.navigation import pick_from_list, action_search_multi_tags
from core.database import show_db_properties

# Constants for shortcut keys
KEYS = "123456789abcdefghijklmnopqrstuvwxyz"

COMMANDS = [
    {"label": "Search pages", "fn": action_search},
    {"label": "Search by multiple tags", "fn": action_search_multi_tags},
    {"label": "Read page by ID", "fn": action_read},
    {"label": "Create page", "fn": action_create},
    {"label": "Append to page", "fn": action_append},
    {"label": "Switch database", "fn": None},
    {"label": "Quit", "fn": None},
]

def command_menu(db):
    """
    Displays the main action menu for a specific database.
    
    Args:
        db (dict): The currently active database config object.
    """
    while True:
        click.echo(f"\n📂 Database: {db['name']}")
        show_db_properties(db)
        click.echo("─" * 40)
        
        cmd = pick_from_list(
            COMMANDS,
            label_fn=lambda c: c["label"],
            key_list=KEYS,
            prompt="Choose an action: ",
        )

        if cmd is None or cmd["label"] == "Quit":
            click.echo("\nGoodbye 👋\n")
            raise SystemExit(0)
        elif cmd["label"] == "Switch database":
            return  # Returns to the database selector in cli()
        else:
            # Inside command_menu
            if cmd["fn"]:
                try:
                    cmd["fn"](db)
                except Exception as e:
                    click.echo(f"❌ Error executing {cmd['label']}: {e}")


@click.command()
def cli():
    """Notion terminal CLI — interactive database selector."""
    databases = load_databases()

    if not databases:
        click.echo("❌ No databases found in configuration.")
        return

    while True:
        click.echo("\n--- Notion CLI: Database Selection ---")
        selected_db = pick_from_list(
            databases,
            label_fn=lambda d: d["name"],
            key_list=KEYS,
            prompt="Select a database to work with (or any other key to quit): "
        )

        if not selected_db:
            click.echo("\nExiting.")
            break

        command_menu(selected_db)

if __name__ == "__main__":
    cli()