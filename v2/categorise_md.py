import sqlite3
import re
import sys
import os


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


def read_md_table(path):
    with open(path, 'r', encoding='utf-8') as f:
        lines = [l.rstrip('\n') for l in f]

    # find first table header line (starts with | and has | separators)
    header_idx = None
    for i, l in enumerate(lines):
        if l.strip().startswith('|') and '|' in l.strip()[1:]:
            header_idx = i
            break

    if header_idx is None or header_idx + 1 >= len(lines):
        return [], []

    header_line = lines[header_idx]
    sep_line = lines[header_idx + 1]

    # headers are the cells between | ... |
    def split_row(line):
        parts = [p.strip() for p in line.split('|')]
        # remove leading/trailing empties caused by leading/trailing |
        if parts and parts[0] == '':
            parts = parts[1:]
        if parts and parts[-1] == '':
            parts = parts[:-1]
        return parts

    headers = split_row(header_line)

    rows = []
    for l in lines[header_idx + 2:]:
        if not l.strip().startswith('|'):
            # stop at first non-table line
            break
        # ignore separator-like lines
        if set(l.strip()) <= set('| -:'):
            continue
        cells = split_row(l)
        # pad to headers length
        if len(cells) < len(headers):
            cells += [''] * (len(headers) - len(cells))
        rows.append(dict(zip(headers, cells)))

    return headers, rows


def main():
    infile = sys.argv[1] if len(sys.argv) > 1 else 'categories.md'

    if not os.path.exists(infile):
        print(f"Error: '{infile}' not found")
        sys.exit(1)

    print(f"📂 Loading category rules from: {infile}")

    headers, rows = read_md_table(infile)
    if not headers:
        print('No table found in markdown')
        sys.exit(1)

    # normalize header names to expected DB column names
    # expected: transaction_type_pattern, description_pattern, main_category, sub1, sub2, sub3, notes
    expected = ['transaction_type_pattern', 'description_pattern', 'main_category', 'sub1', 'sub2', 'sub3', 'notes']

    # map header positions
    header_map = {h: h for h in headers}

    DB_FILE = 'load_statement.db'
    TRUNCATE_CATEGORIES = True

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # ensure the transactions table exists -- if not, user probably hasn't loaded statements yet
    cur_tables = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    if 'transactions' not in cur_tables:
        print("Error: 'transactions' table not found in database. Run load_statement_ofx.py or load_and_categorise.py first.")
        conn.close()
        sys.exit(1)

    if TRUNCATE_CATEGORIES:
        # create categories table if missing, then truncate
        if 'categories' not in cur_tables:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS categories (
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
        print('Truncating existing category rules...')
        cursor.execute('DELETE FROM categories')

    for r in rows:
        # extract values for expected columns, fallback to empty string
        vals = [r.get(col, '') for col in expected]
        cursor.execute('''
            INSERT INTO categories (transaction_type_pattern, description_pattern, main_category, sub1, sub2, sub3, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', tuple(vals))

    # Re-apply categorisation (same logic as categorise.py)
    cursor.execute('DELETE FROM categorised')

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
        for type_pattern, desc_pattern, main_category, sub1, sub2, sub3, notes in category_rules:
            type_pattern = type_pattern or ''
            desc_pattern = desc_pattern or ''
            type_match = regex_search(type_pattern, txn_type)
            desc_match = regex_search(desc_pattern, desc)
            if type_match and desc_match:
                matched_main_category = main_category or ''
                matched_sub1 = sub1 or ''
                matched_sub2 = sub2 or ''
                matched_sub3 = sub3 or ''
                matched_notes = notes or ''
                break

        cursor.execute('''
            INSERT INTO categorised (transaction_id, main_category, sub1, sub2, sub3, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (txn_id, matched_main_category, matched_sub1, matched_sub2, matched_sub3, matched_notes))

    conn.commit()
    conn.close()
    print('Category rules (from MD) updated and applied successfully.')


if __name__ == '__main__':
    main()
