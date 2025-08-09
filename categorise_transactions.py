import sqlite3
import pandas as pd
import re
import argparse

DB_FILE = "load_statement.db"
CATEGORY_CSV = "categories.csv"

def load_categories(cursor, truncate=False):
    if truncate:
        print("[INFO] Truncating categories table...")
        cursor.execute("DELETE FROM categories")

    df = pd.read_csv(CATEGORY_CSV)

    for _, row in df.iterrows():
        cursor.execute('''
            INSERT INTO categories (transaction_type_pattern, description_pattern, category)
            VALUES (?, ?, ?)
        ''', (row['transaction_type_pattern'], row['description_pattern'], row['category']))

    print(f"[INFO] Loaded {len(df)} categories.")


def categorise_transactions(cursor):
    cursor.execute("DELETE FROM categorised")  # Clear existing categorisation

    cursor.execute('SELECT id, transaction_type, description FROM transactions')
    transactions = cursor.fetchall()

    cursor.execute('SELECT transaction_type_pattern, description_pattern, category FROM categories')
    category_rules = cursor.fetchall()

    uncategorised = 0

    for txn_id, txn_type, desc in transactions:
        matched_category = 'Uncategorised'
        for type_pattern, desc_pattern, category in category_rules:
            if re.search(type_pattern, txn_type, re.IGNORECASE) and re.search(desc_pattern, desc, re.IGNORECASE):
                matched_category = category
                break

        cursor.execute('''
            INSERT INTO categorised (transaction_id, category)
            VALUES (?, ?)
        ''', (txn_id, matched_category))

        if matched_category == 'Uncategorised':
            uncategorised += 1

    print(f"[INFO] Categorisation complete. Uncategorised transactions: {uncategorised}")


def main():
    parser = argparse.ArgumentParser(description="Reload and apply transaction categorisation rules.")
    parser.add_argument('--truncate', action='store_true', help="Truncate categories before loading")
    parser.add_argument('--db', default=DB_FILE, help="Path to the SQLite database")
    parser.add_argument('--csv', default=CATEGORY_CSV, help="CSV file with category patterns")

    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    cursor = conn.cursor()

    load_categories(cursor, truncate=args.truncate)
    categorise_transactions(cursor)

    conn.commit()
    conn.close()
    print("[DONE] Database updated with new categorisations.")

if __name__ == '__main__':
    main()

