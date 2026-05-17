import sqlite3
import re
import sys
import os
from pathlib import Path


def parse_ofx_transactions(ofx_text):
    # Find all <STMTTRN>...</STMTTRN> blocks
    blocks = re.findall(r'<STMTTRN>(.*?)</STMTTRN>', ofx_text, re.S | re.I)
    txns = []
    for b in blocks:
        # get date
        m = re.search(r'<DTPOSTED>([^<\r\n]+)', b, re.I)
        date_raw = m.group(1).strip() if m else ''
        date = ''
        if len(date_raw) >= 8:
            # YYYYMMDD...
            try:
                date = f"{date_raw[0:4]}-{date_raw[4:6]}-{date_raw[6:8]}"
            except Exception:
                date = date_raw
        else:
            date = date_raw

        # transaction amount
        m = re.search(r'<TRNAMT>([^<\r\n]+)', b, re.I)
        amt_raw = m.group(1).strip() if m else '0'
        try:
            amt = float(amt_raw)
        except Exception:
            # sometimes amounts have commas
            amt = float(amt_raw.replace(',', '')) if amt_raw else 0.0

        # name / description (NAME or MEMO)
        m = re.search(r'<NAME>([^<\r\n]+)', b, re.I)
        if m:
            desc = m.group(1).strip()
        else:
            m = re.search(r'<MEMO>([^<\r\n]+)', b, re.I)
            desc = m.group(1).strip() if m else ''

        # transaction type
        m = re.search(r'<TRNTYPE>([^<\r\n]+)', b, re.I)
        trn_type = m.group(1).strip() if m else ''

        # compute paid_in / paid_out
        if amt < 0:
            paid_out = abs(amt)
            paid_in = 0.0
        else:
            paid_in = amt
            paid_out = 0.0

        txns.append({
            'date': date,
            'transaction_type': trn_type,
            'description': desc,
            'paid_out': paid_out,
            'paid_in': paid_in,
            'balance': 0.0,
        })

    return txns


def main():
    if len(sys.argv) < 2:
        print("Usage: python load_statement_ofx.py path/to/file.ofx")
        sys.exit(1)

    ofx_path = sys.argv[1]
    if not os.path.exists(ofx_path):
        print(f"Error: File '{ofx_path}' does not exist.")
        sys.exit(1)

    print(f"Loading OFX data from: {ofx_path}")

    with open(ofx_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    transactions = parse_ofx_transactions(content)

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

    # Insert transactions
    for t in transactions:
        cursor.execute('''
            INSERT INTO transactions (date, transaction_type, description, paid_out, paid_in, balance)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            t['date'],
            t['transaction_type'],
            t['description'],
            t['paid_out'],
            t['paid_in'],
            t['balance']
        ))

    # === INSERT DEFAULT CATEGORY ===
    cursor.execute('''
    INSERT INTO categories (transaction_type_pattern, description_pattern, main_category, sub1, sub2, sub3, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', ('.*', '.*', 'Uncategorised', '', '', '', ''))

    # === CATEGORISE TRANSACTIONS ===
    cursor.execute('SELECT id, transaction_type, description FROM transactions')
    transactions_db = cursor.fetchall()

    cursor.execute('SELECT transaction_type_pattern, description_pattern, main_category, sub1, sub2, sub3, notes FROM categories')
    category_rules = cursor.fetchall()

    for txn_id, txn_type, desc in transactions_db:
        matched_main_category = 'Uncategorised'
        matched_sub1 = ''
        matched_sub2 = ''
        matched_sub3 = ''
        matched_notes = ''
        for type_pattern, desc_pattern, main_category, sub1, sub2, sub3, notes in category_rules:
            try:
                if re.match(type_pattern, txn_type) and re.match(desc_pattern, desc):
                    matched_main_category = main_category
                    matched_sub1 = sub1
                    matched_sub2 = sub2
                    matched_sub3 = sub3
                    matched_notes = notes
                    break
            except re.error:
                # skip invalid regex patterns
                continue
        cursor.execute('''
            INSERT INTO categorised (transaction_id, main_category, sub1, sub2, sub3, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (txn_id, matched_main_category, matched_sub1, matched_sub2, matched_sub3, matched_notes))

    conn.commit()
    conn.close()

    print("Database created and populated successfully from OFX.")


if __name__ == '__main__':
    main()
