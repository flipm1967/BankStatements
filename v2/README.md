Will read in bank statements from Nationwide, process and categorise then display.

Prerequisites (one-time)
- On Debian/Ubuntu (example):
	- `sudo apt install git keepass dos2unix libxcb-cursor0 sqlite3`
- Create and activate the virtualenv (optional):
	- Unix: `./create_venv.sh` then `source bankenv/bin/activate`
	- PowerShell: `.\bankenv\Scripts\Activate.ps1`
	- CMD: `.\bankenv\Scripts\activate.bat`

Download statements
- From Nationwide current account: choose the date range (e.g. "last 12 months") and Download Transactions as an OFX file.
- Move the downloaded `.ofx` file into the `DATA/` folder.

Load and categorise (recommended modern workflow)

**Quick (one-command) workflow:**
```powershell
.\process_statement.ps1 "../DATA/Statement Download 2026-May-17 9-17-33.ofx"
```

Or, to auto-detect the latest OFX file in `../DATA/`:
```powershell
.\process_statement.ps1
```

This runs all three steps below and opens the report automatically.

**Manual step-by-step workflow (if needed):**
1. Load the OFX into the database:

```powershell
py load_statement_ofx.py "../DATA/Statement Download 2026-May-17 9-17-33.ofx"
```

Caution: Running `load_statement_ofx.py` will drop and recreate the database tables (`transactions`, `categories`, `categorised`) so any existing data in `load_statement.db` will be replaced.

Note: `categorise_md.py` requires a populated `transactions` table and will exit with an error if no transactions are present — run the load step first.

2. Apply categories from the Markdown table (defaults to `categories.md`):
```powershell
py categorise_md.py
```

3. Create the HTML report:
```powershell
py display.py
```

4. Open `display.html` in your browser.
Other useful commands
- List unique uncategorised transaction patterns:

```powershell
py list_uncategorised.py
```
- If you prefer the CSV workflow, use `load_statement.py` (CSV import) and `categorise.py` (CSV categories). Those legacy scripts are present in `OBSOLETE/` if needed.

Database and scripts mapping
- `load_statement_ofx.py` (or `load_statement.py`) creates/imports the `transactions` table.
- `categorise_md.py` reads `categories.md` and populates `categories`, then writes `categorised` after applying rules.
- Legacy scripts: `categorise.py` / `load_statement.py` exist for the older CSV workflow and are available in `OBSOLETE/`.

Inspecting the DB
- You can open `load_statement.db` in VS Code with the SQLite Viewer extension, or use the CLI:

```powershell
sqlite3 load_statement.db
```
.tables
.schema transactions
.quit

Notes
- `categorise_md.py` defaults to `categories.md` so you can run it without arguments.
- Use the `py` launcher on Windows for consistency in examples; on Unix use `python3` if preferred.
- Keep this README up to date whenever you change workflow scripts or execution steps.


