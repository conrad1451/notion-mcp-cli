"""Scaffolds a tag_categories.json file from a Notion database's Tags property."""

#!/usr/bin/env python3

# scaffold_tags.py

import os
import json
from notion_client import Client
from dotenv import load_dotenv

load_dotenv()

notion = Client(auth=os.environ["NOTION_TOKEN"])

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "databases.json")


def load_databases():
    """Load database configurations from the JSON config file."""
    # CHQ: ClaudeAI added utf-8 encoding to filepath
    with open(CONFIG_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("databases", [])


def fetch_tag_options(db_id):
    """Fetch all tag option names from a Notion database's Tags multi-select property."""
    result = notion.databases.retrieve(database_id=db_id)
    tag_options = (
        result["properties"].get("Tags", {}).get("multi_select", {}).get("options", [])
    )
    return [t["name"] for t in tag_options]


def scaffold_tag_file(db):
    """Generate a scaffold tag_categories.json file for a database if one doesn't exist."""
    tag_file = db.get("tag_file")
    if not tag_file:
        print(f"⚠️  No tag_file configured for {db['name']}, skipping.")
        return

    output_path = os.path.join(os.path.dirname(__file__), tag_file)

    if os.path.exists(output_path):
        print(f"⏭️  {db['name']}: {tag_file} already exists, skipping.")
        return

    print(f"⏳ Fetching tags for {db['name']}...")
    tags = fetch_tag_options(db["id"])

    if not tags:
        print(f"⚠️  No tags found for {db['name']}.")
        return

    # Scaffold: all tags dumped into a single "Uncategorized" bucket
    scaffold = {"Uncategorized": {"All": tags}}

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    # CHQ: ClaudeAI added utf-8 encoding to filepath
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(scaffold, f, indent=2)

    print(f"✅ {db['name']}: wrote {len(tags)} tags to {tag_file}")


if __name__ == "__main__":
    databases = load_databases()
    # CHQ: Claude AI renamed loop variable to prevent variable shadowing
    for database in databases:
        scaffold_tag_file(database)
