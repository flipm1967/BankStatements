import sqlite3
import csv
import re
import sys
import os
from pathlib import Path


def parse_md_table(path):
    rules = []
    with open(path, encoding='utf-8') as f:
        lines = [l.rstrip('\n') for l in f]

    sep_idx = None
    for i, line in enumerate(lines):
        if re.match(r"^\s*\|?\s*-{3,}", line):
            sep_idx = i
            break
    if sep_idx is None:
        return rules

    for line in lines[sep_idx+1:]:
        line = line.strip()
        if not line or not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.split('|')]
        if cells and cells[0] == '':
            cells = cells[1:]
        if cells and cells[-1] == '':
            cells = cells[:-1]
        if len(cells) < 2:
            continue
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
    return rules


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


def main():
    if len(sys.argv) < 2:
        print("Usage: python load_and_categorise.py path/to/transactions.csv [categories.md|categories.csv]")
        sys.exit(1)

    csv_filename = sys.argv[1]
    if not os.path.exists(csv_filename):
        print(f"Error: File '{csv_filename}' does not exist.")
        sys.exit(1)

    # determine categories file
    categories_file = sys.argv[2] if len(sys.argv) >= 3 else None
    if not categories_file:
        if Path('categories.md').exists():
            categories_file = 'categories.md'
        elif Path('categories.csv').exists():
            categories_file = 'categories.csv'

    DB_FILE = 'load_statement.db'

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.executescript('''
    DROP TABLE IF EXISTS transactions;
    DROP TABLE IF EXISTS categories;
    DROP TABLE IF EXISTS categorised;
    ''')

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

    # import transactions CSV
    with open(csv_filename, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        # try to find a date-like column if it's not exactly 'Date'
        fieldnames = reader.fieldnames or []
        date_field = None
        for f in fieldnames:
            if f and 'date' in f.lower():
                date_field = f
                break
        if not date_field:
            date_field = 'Date'

        inserted = 0
        empty_dates = 0
        for row in reader:
            date_val = (row.get(date_field) or '').strip()
            if not date_val:
                empty_dates += 1
            cursor.execute('''
                INSERT INTO transactions (date, transaction_type, description, paid_out, paid_in, balance)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                date_val,
                row.get('Transaction type') or row.get('transaction_type') or row.get('Type') or '',
                row.get('Description') or row.get('description') or '',
                float(row.get('Paid out') or row.get('Debit') or 0),
                float(row.get('Paid in') or row.get('Credit') or 0),
                float(row.get('Balance') or 0)
            ))
            inserted += 1

        print(f"Imported {inserted} transactions ({empty_dates} with empty date field '{date_field}').")

    # load categories
    if categories_file:
        print(f"Loading categories from: {categories_file}")
        if categories_file.lower().endswith('.md'):
            md_rules = parse_md_table(categories_file)
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
            with open(categories_file, newline='', encoding='utf-8') as catfile:
                reader = csv.DictReader(catfile)
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
    else:
        cursor.execute('''
        INSERT INTO categories (transaction_type_pattern, description_pattern, main_category, sub1, sub2, sub3, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ('.*', '.*', 'Uncategorised', '', '', '', ''))

    # apply categorisation
    cursor.execute('SELECT id, transaction_type, description FROM transactions')
    transactions = cursor.fetchall()

    cursor.execute('SELECT transaction_type_pattern, description_pattern, main_category, sub1, sub2, sub3, notes FROM categories')
    category_rules = cursor.fetchall()

    for txn_id, txn_type, desc in transactions:
        matched_main_category = 'Uncategorised'
        matched_sub1 = ''
        matched_sub2 = ''
        matched_sub3 = ''
        matched_notes = ''
        matched = False
        for type_pattern, desc_pattern, main_category, sub1, sub2, sub3, notes in category_rules:
            type_pattern = type_pattern or ''
            desc_pattern = desc_pattern or ''
            try:
                type_match = regex_search(type_pattern, txn_type)
                desc_match = regex_search(desc_pattern, desc)
            except re.error:
                type_match = False
                desc_match = False
            if type_match and desc_match:
                matched_main_category = main_category or ''
                matched_sub1 = sub1 or ''
                matched_sub2 = sub2 or ''
                matched_sub3 = sub3 or ''
                matched_notes = notes or ''
                matched = True
                break
        cursor.execute('''
            INSERT INTO categorised (transaction_id, main_category, sub1, sub2, sub3, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (txn_id, matched_main_category, matched_sub1, matched_sub2, matched_sub3, matched_notes))

    conn.commit()
    conn.close()
    print("Database created and categorised successfully.")


if __name__ == '__main__':
    main()
