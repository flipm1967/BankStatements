import sqlite3
import csv
import re

# === CONFIG ===
DB_FILE = 'load_statement.db'
CATEGORIES_CSV = '../DATA/new_categories.csv'
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
with open(CATEGORIES_CSV, newline='', encoding='utf-8') as csvfile:
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

