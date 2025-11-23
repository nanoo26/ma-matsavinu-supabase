import sqlite3

DB_PATH = "expenses.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print("Tables in DB:")
cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
print(cur.fetchall())

print("\nRows in budget table:")
try:
    cur.execute("SELECT id, category, amount FROM budget;")
    rows = cur.fetchall()
    for row in rows:
        print(row)
except Exception as e:
    print("Error reading budget table:", e)

conn.close()
