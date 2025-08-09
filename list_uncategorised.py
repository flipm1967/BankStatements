import sqlite3

DB_FILE = 'load_statement.db'

def list_uncategorised_transactions():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    query = '''
    SELECT DISTINCT t.transaction_type, t.description
    FROM transactions t
    LEFT JOIN categorised c ON t.id = c.transaction_id
    WHERE c.category = 'Uncategorised' OR c.category IS NULL
    ORDER BY t.transaction_type, t.description
    '''

    cursor.execute(query)
    rows = cursor.fetchall()

    if not rows:
        print("All transactions are categorised!")
    else:
        print("Unique uncategorised transactions (transaction_type | description):")
        for txn_type, desc in rows:
            print(f"- {txn_type} | {desc}")

    conn.close()

if __name__ == "__main__":
    list_uncategorised_transactions()

