import os
import json
from notion_client import Client
from dotenv import load_dotenv
import click


load_dotenv()

TOKEN = os.getenv("NOTION_TOKEN")
notion = Client(auth=TOKEN)
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "databases.json")
DEBUG = os.getenv("DEBUG", "").lower() in ("1", "true", "yes")
KEYS_FEW = "123456789"
KEYS_EXPANDED = "123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

_DB_SCHEMA_CACHE = {}

def load_databases():
    """Loads database configurations from JSON."""
    if not os.path.exists(CONFIG_PATH):
        raise SystemExit("❌ Config file not found.")
    with open(CONFIG_PATH) as f:
        return json.load(f).get("databases", [])

# CHQ: Claude AI made helper function
def load_tag_hierarchy(db):
    """
    Reads the hierarchical JSON file used for organized tag browsing.
    
    Args:
        db (dict): The database config object.
        
    Returns:
        dict/None: The parsed hierarchy or None if failed.
    """
    """Load and parse the tag hierarchy file."""
    try:
        tag_file = db.get("tag_file")
        if not tag_file:
            click.echo("❌ No tag file configured for this database.")
            return None
        
        tag_file_path = os.path.join(os.path.dirname(__file__), tag_file)
        with open(tag_file_path, "r") as f:
            return json.load(f)
    except Exception as e:
        click.echo(f"❌ Could not load tag_categories.json: {e}")
        return None
