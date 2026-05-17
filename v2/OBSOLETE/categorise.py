import sqlite3
import csv
import re
import sys
import os

# Check if a filename was passed
if len(sys.argv) < 2:
    print("Error: Please provide a category filename to load.")
    print("Usage: python categorise.py your_file.csv")
    sys.exit(1)

csv_filename = sys.argv[1]

# Optional: validate the file exists
if not os.path.exists(csv_filename):
    print(f"Error: File '{csv_filename}' does not exist.")
    sys.exit(1)

print(f"📂 Loading data from: {csv_filename}")


# === CONFIG ===
DB_FILE = 'load_statement.db'
TRUNCATE_CATEGORIES = True  # Set to True to clear old categories first
DEBUG=False

# === CONNECT TO DB ===
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

# === OPTIONAL: TRUNCATE CATEGORIES TABLE ===
if TRUNCATE_CATEGORIES:
    print("Truncating existing category rules...")
    cursor.execute("DELETE FROM categories")

# === LOAD NEW CATEGORIES (CSV or Markdown table) ===
def parse_md_table(path):
    rules = []
    with open(path, encoding='utf-8') as f:
        lines = [l.rstrip('\n') for l in f]

    # find the table header separator (---) line index
    sep_idx = None
    for i, line in enumerate(lines):
        if re.match(r"^\s*\|?\s*-{3,}", line):
            sep_idx = i
            break

    if sep_idx is None:
        return rules

    # table rows start after the separator
    for line in lines[sep_idx+1:]:
        line = line.strip()
        if not line or not line.startswith('|'):
            continue
        # split on '|' and strip cells; ignore leading/trailing empty cells
        cells = [c.strip() for c in line.split('|')]
        # remove empty leading/trailing due to table formatting
        if cells and cells[0] == '':
            cells = cells[1:]
        if cells and cells[-1] == '':
            cells = cells[:-1]
        # ensure at least 2 columns
        if len(cells) < 2:
            continue
        # pad to 7 columns
        while len(cells) < 7:
            cells.append('')
        rules.append({
            'transaction_type_pattern': cells[0],
            'description_pattern': cells[1],
            'main_category': cells[2],
            'sub1': cells[3],
            'sub2': cells[4],
            'sub3': cells[5],
            'notes': cells[6],
        })


if csv_filename.lower().endswith('.md'):
    print(f"Parsing Markdown categories from: {csv_filename}")
    md_rules = parse_md_table(csv_filename)
    for row in md_rules:
        cursor.execute('''
            INSERT INTO categories (transaction_type_pattern, description_pattern, main_category, sub1, sub2, sub3, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            row['transaction_type_pattern'],
            row['description_pattern'],
            row['main_category'],
            row['sub1'],
            row['sub2'],
            row['sub3'],
            row['notes']
        ))
else:
    with open(csv_filename, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            cursor.execute('''
                INSERT INTO categories (transaction_type_pattern, description_pattern, main_category, sub1, sub2, sub3, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                row.get('transaction_type_pattern') or row.get('transaction_type') or '',
                row.get('description_pattern') or row.get('description') or '',
                row.get('main_category') or '',
                row.get('sub1') or '',
                row.get('sub2') or '',
                row.get('sub3') or '',
                row.get('notes') or ''
            ))

def regex_search(pattern, text):
    text = text or ''
    pattern = pattern or ''
    try:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    except re.error:
        return False

    try:
        norm_pattern = re.sub(r'\s+', '', pattern)
        norm_text = re.sub(r'\s+', '', text)
        return bool(re.search(norm_pattern, norm_text, re.IGNORECASE))
    except re.error:
        return False

# === RE-CATEGORISE TRANSACTIONS ===

# Clear old categorisation
cursor.execute("DELETE FROM categorised")

# Fetch transactions
cursor.execute('SELECT id, transaction_type, description FROM transactions')
transactions = cursor.fetchall()

# Fetch rules (include all new columns)
cursor.execute('SELECT transaction_type_pattern, description_pattern, main_category, sub1, sub2, sub3, notes FROM categories')
category_rules = cursor.fetchall()

# Re-apply category rules with debug output
for txn_id, txn_type, desc in transactions:
    matched_main_category = 'Uncategorised'
    matched_sub1 = ''
    matched_sub2 = ''
    matched_sub3 = ''
    matched_notes = ''
    matched = False

    for type_pattern, desc_pattern, main_category, sub1, sub2, sub3, notes in category_rules:
        # Handle None values by converting to empty strings
        type_pattern = type_pattern or ''
        desc_pattern = desc_pattern or ''
        main_category = main_category or ''
        sub1 = sub1 or ''
        sub2 = sub2 or ''
        sub3 = sub3 or ''
        notes = notes or ''
        
        type_match = regex_search(type_pattern, txn_type)
        desc_match = regex_search(desc_pattern, desc)

        if type_match and desc_match:
            matched_main_category = main_category
            matched_sub1 = sub1
            matched_sub2 = sub2
            matched_sub3 = sub3
            matched_notes = notes
            matched = True
            if DEBUG:
                print(f"✅ MATCH: [txn_type='{txn_type}'] [desc='{desc}']")
                print(f"    ➤ Rule matched: type_pattern='{type_pattern}', desc_pattern='{desc_pattern}'")
                print(f"    ➤ Category: {main_category} > {sub1} > {sub2}")
            break  # Stop at first match

    if not matched and DEBUG:
        print(f"❌ NO MATCH: [txn_type='{txn_type}'] [desc='{desc}']")
        print(f"    ➤ Assigned category: Uncategorised")

    # Store the result or default uncategorised in the categorised table
    cursor.execute('''
        INSERT INTO categorised (transaction_id, main_category, sub1, sub2, sub3, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (txn_id, matched_main_category, matched_sub1, matched_sub2, matched_sub3, matched_notes))


# Finalize
conn.commit()
conn.close()
print("Category rules updated and applied successfully.")

