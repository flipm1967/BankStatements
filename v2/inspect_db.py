import sqlite3
import sys

DB = 'load_statement.db'

def main():
    try:
        conn = sqlite3.connect(DB)
        cur = conn.cursor()
    except Exception as e:
        print('ERROR: cannot open database', DB, e)
        sys.exit(1)

    try:
        tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    except Exception as e:
        print('ERROR reading sqlite_master:', e)
        sys.exit(1)

    print('tables:', tables)

    def safe_count(tbl):
        try:
            return cur.execute(f"SELECT count(*) FROM {tbl}").fetchone()[0]
        except Exception:
            return '<missing>'

    print('transactions:', safe_count('transactions'))
    print('categories:', safe_count('categories'))
    print('categorised:', safe_count('categorised'))

    try:
        sample = [r[0] for r in cur.execute('SELECT date FROM transactions LIMIT 10').fetchall()]
        print('sample transaction dates:', sample)
    except Exception as e:
        print('No transactions or error querying dates:', e)

    conn.close()

if __name__ == '__main__':
    main()
