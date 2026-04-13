
[![Python Linter](https://github.com/conrad1451/animaltrackingetls/actions/workflows/pylint.yml/badge.svg)](https://github.com/conrad1451/animaltrackingetls/actions/workflows/pylint.yml)


# notion-pkm-cli

A terminal CLI written in Python for interacting with my Notion Personal Knowledge Management (PKM) system, directly from the command line via the Notion API.

## Features

- Interactive database selector at startup
- Command menu per database (search, read, create, append)
- Database properties displayed on selection
- Keypress-driven search results with terminal hyperlinks
- Search results scoped to the selected database

## Requirements

- Python 3.11+
- A Notion integration token
- Notion pages/databases shared with your integration

## Installation

### 1. Clone the repo

```bash
git clone https://github.com/your-username/notion-pkm-cli.git
cd notion-pkm-cli
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

Or manually:

```bash
pip install notion-client click python-dotenv readchar
```

### 4. Set up your Notion integration

1. Go to [notion.so/profile/integrations](https://www.notion.so/profile/integrations)
2. Click **New integration** and give it a name
3. Copy the token (starts with `ntn_`)
4. Create a `.env` file in the project root:

```
NOTION_TOKEN=ntn_your_token_here
```

5. Share your Notion databases with the integration: open any database in Notion → `•••` menu → **Add connections** → select your integration

### 5. Configure your databases

Create a `databases.json` file in the project root:

```json
{
  "databases": [
    { "name": "Work", "id": "your-database-id-here" },
    { "name": "Personal", "id": "your-database-id-here" }
  ]
}
```

To find a database ID: open the database in Notion and copy the 32-character string from the URL after the last `/` and before the `?`.

## Usage

```bash
python notion_cli.py
```

You'll be presented with a database selector, then a command menu:

```
🗂  Select a database:

  [1] Work
  [2] Personal

Press a key to select: 1

📂 Database: Work
  Properties: Name, Status, Assignee, Due Date
────────────────────────────────────────
  [1] Search pages
  [2] Read page by ID
  [3] Create page
  [4] Append to page
  [5] Switch database
  [6] Quit

Choose an action:
```

### Commands

| Command         | Description                                                       |
| --------------- | ----------------------------------------------------------------- |
| Search pages    | Search within the selected database and open a result by keypress |
| Read page by ID | Read any page by pasting its ID                                   |
| Create page     | Create a new page in the selected database                        |
| Append to page  | Append a paragraph to an existing page                            |
| Switch database | Return to the database selector                                   |
| Quit            | Exit the app                                                      |

## Project Structure

```
notion-pkm-cli/
├── notion_cli.py       # Main CLI script
├── databases.json      # Your database config (gitignored)
├── .env                # Your Notion token (gitignored)
├── requirements.txt    # Python dependencies
└── .gitignore
```

## Gitignored Files

The following are excluded from version control and must be created locally:

- `.env` — contains your secret Notion token
- `databases.json` — contains your database IDs

## Notes

- Terminal hyperlinks in search results require a modern terminal (VS Code terminal, iTerm2, Warp, Ghostty). They degrade gracefully in unsupported terminals.
- The venv folder is gitignored. Recreate it with `python3 -m venv venv && pip install -r requirements.txt` after cloning.
