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

# === LOAD NEW CATEGORIES CSV ===
with open(csv_filename, newline='', encoding='utf-8') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        cursor.execute('''
            INSERT INTO categories (transaction_type_pattern, description_pattern, category)
            VALUES (?, ?, ?)
        ''', (
            row['transaction_type_pattern'],
            row['description_pattern'],
            row['category']
        ))

# === RE-CATEGORISE TRANSACTIONS ===

# Clear old categorisation
cursor.execute("DELETE FROM categorised")

# Fetch transactions
cursor.execute('SELECT id, transaction_type, description FROM transactions')
transactions = cursor.fetchall()

# Fetch rules
cursor.execute('SELECT transaction_type_pattern, description_pattern, category FROM categories')
category_rules = cursor.fetchall()

# Re-apply category rules with debug output
for txn_id, txn_type, desc in transactions:
    matched_category = 'Uncategorised'
    matched = False

    for type_pattern, desc_pattern, category in category_rules:
        type_match = re.search(type_pattern, txn_type, re.IGNORECASE)
        desc_match = re.search(desc_pattern, desc, re.IGNORECASE)

        if type_match and desc_match:
            matched_category = category
            matched = True
            if DEBUG:
              print(f"✅ MATCH: [txn_type='{txn_type}'] [desc='{desc}']")
              print(f"    ➤ Rule matched: type_pattern='{type_pattern}', desc_pattern='{desc_pattern}'")
              print(f"    ➤ Category: {category}")
            break  # Stop at first match

    if not matched and DEBUG:
        print(f"❌ NO MATCH: [txn_type='{txn_type}'] [desc='{desc}']")
        print(f"    ➤ Assigned category: Uncategorised")

    # Store the result or default uncategorised in the categorised table
    cursor.execute('''
        INSERT INTO categorised (transaction_id, category)
        VALUES (?, ?)
    ''', (txn_id, matched_category))


# Finalize
conn.commit()
conn.close()
print("Category rules updated and applied successfully.")

