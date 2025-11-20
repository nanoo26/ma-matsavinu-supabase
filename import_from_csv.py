import sqlite3
import csv
import os

DB_PATH = "expenses.db"
CSV_PATH = "expenses_export.csv"


def recreate_db_from_csv():
    # Check CSV exists
    if not os.path.exists(CSV_PATH):
        print(f"CSV file '{CSV_PATH}' not found. Put it next to this script.")
        return

    # Delete old DB if exists
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Deleted old {DB_PATH}")

    # Create new database and table
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            payment_method TEXT NOT NULL,
            description TEXT NOT NULL
        )
    """)
    conn.commit()

    # Read rows from CSV (UTF-8 with BOM)
    rows = []
    with open(CSV_PATH, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            amount = float(row["amount"])
            rows.append((
                row["date"],
                row["category"],
                amount,
                row["payment_method"],
                row["description"],
            ))

    # Insert rows into DB
    cur.executemany("""
        INSERT INTO expenses (date, category, amount, payment_method, description)
        VALUES (?, ?, ?, ?, ?)
    """, rows)
    conn.commit()
    conn.close()

    print(f"Imported {len(rows)} rows from {CSV_PATH} into {DB_PATH}")


if __name__ == "__main__":
    recreate_db_from_csv()
