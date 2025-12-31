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
    category TEXT,
    essential TEXT
)
''')

# Create the categorised table linking transaction IDs to category names
cursor.execute('''
CREATE TABLE categorised (
    transaction_id INTEGER PRIMARY KEY,
    category TEXT,
    essential TEXT,
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
INSERT INTO categories (transaction_type_pattern, description_pattern, category, essential)
VALUES (?, ?, ?, ?)
''', ('.*', '.*', 'Uncategorised', 'N'))

# === CATEGORISE TRANSACTIONS ===
# Fetch all transactions
cursor.execute('SELECT id, transaction_type, description FROM transactions')
transactions = cursor.fetchall()

# Fetch all category rules (include essential flag)
cursor.execute('SELECT transaction_type_pattern, description_pattern, category, essential FROM categories')
category_rules = cursor.fetchall()

# Apply rules to each transaction
for txn_id, txn_type, desc in transactions:
    matched_category = 'Uncategorised'
    matched_essential = 'N'
    for type_pattern, desc_pattern, category, essential in category_rules:
        if re.match(type_pattern, txn_type) and re.match(desc_pattern, desc):
            matched_category = category
            matched_essential = essential
            break
    cursor.execute('''
        INSERT INTO categorised (transaction_id, category, essential)
        VALUES (?, ?, ?)
    ''', (txn_id, matched_category, matched_essential))

# === FINALISE ===
conn.commit()
conn.close()

print("Database created and populated successfully.")


