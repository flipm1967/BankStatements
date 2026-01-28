import sqlite3
import csv
import re
import sys
import os
from pathlib import Path

# Check if a filename was passed
if len(sys.argv) < 2:
    print("Error: Please provide a CSV filename to load.")
    print("Usage: python load_data.py your_file.csv")
    sys.exit(1)

csv_filename = sys.argv[1]

# Optional: validate the file exists
if not os.path.exists(csv_filename):
    print(f"Error: File '{csv_filename}' does not exist.")
    sys.exit(1)

print(f"Loading data from: {csv_filename}")

# === CONFIG ===
DB_FILE = 'load_statement.db'

# === SETUP DATABASE ===
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

# Drop tables if they exist (for clean reruns; optional)
cursor.executescript('''
DROP TABLE IF EXISTS transactions;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS categorised;
''')

# Create the transactions table
cursor.execute('''
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    transaction_type TEXT,
    description TEXT,
    paid_out REAL,
    paid_in REAL,
    balance REAL
)
''')

# Create the categories table with regex pattern match fields
cursor.execute('''
CREATE TABLE categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_type_pattern TEXT,
    description_pattern TEXT,
    main_category TEXT,
    sub1 TEXT,
    sub2 TEXT,
    sub3 TEXT,
    notes TEXT
)
''')

# Create the categorised table linking transaction IDs to category information
cursor.execute('''
CREATE TABLE categorised (
    transaction_id INTEGER PRIMARY KEY,
    main_category TEXT,
    sub1 TEXT,
    sub2 TEXT,
    sub3 TEXT,
    notes TEXT,
    FOREIGN KEY(transaction_id) REFERENCES transactions(id)
)
''')

# === IMPORT CSV TO TRANSACTIONS ===
with open(csv_filename, newline='', encoding='utf-8') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        cursor.execute('''
            INSERT INTO transactions (date, transaction_type, description, paid_out, paid_in, balance)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            row['Date'],
            row['Transaction type'],
            row['Description'],
            float(row['Paid out'] or 0),
            float(row['Paid in'] or 0),
            float(row['Balance'] or 0)
        ))

# === INSERT DEFAULT CATEGORY ===
cursor.execute('''
INSERT INTO categories (transaction_type_pattern, description_pattern, main_category, sub1, sub2, sub3, notes)
VALUES (?, ?, ?, ?, ?, ?, ?)
''', ('.*', '.*', 'Uncategorised', '', '', '', ''))

# === CATEGORISE TRANSACTIONS ===
# Fetch all transactions
cursor.execute('SELECT id, transaction_type, description FROM transactions')
transactions = cursor.fetchall()

# Fetch all category rules
cursor.execute('SELECT transaction_type_pattern, description_pattern, main_category, sub1, sub2, sub3, notes FROM categories')
category_rules = cursor.fetchall()

# Apply rules to each transaction
for txn_id, txn_type, desc in transactions:
    matched_main_category = 'Uncategorised'
    matched_sub1 = ''
    matched_sub2 = ''
    matched_sub3 = ''
    matched_notes = ''
    for type_pattern, desc_pattern, main_category, sub1, sub2, sub3, notes in category_rules:
        if re.match(type_pattern, txn_type) and re.match(desc_pattern, desc):
            matched_main_category = main_category
            matched_sub1 = sub1
            matched_sub2 = sub2
            matched_sub3 = sub3
            matched_notes = notes
            break
    cursor.execute('''
        INSERT INTO categorised (transaction_id, main_category, sub1, sub2, sub3, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (txn_id, matched_main_category, matched_sub1, matched_sub2, matched_sub3, matched_notes))

# === FINALISE ===
conn.commit()
conn.close()

print("Database created and populated successfully.")


