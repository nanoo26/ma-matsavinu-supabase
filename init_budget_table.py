import sqlite3

DB_PATH = "expenses.db"

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Create budget table if not exists
    cur.execute("""
    CREATE TABLE IF NOT EXISTS budget (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL UNIQUE,
        amount REAL NOT NULL
    );
    """)

    # Initial budget values per category (you can change the numbers)
    budgets = [
        ("מזון", 1000),
        ("בילויים", 1000),
        ("בית", 1000),
        ("ילדים", 1000),
        ("רכב", 1000),
        ("בריאות", 1000),
        ("חוגים", 500),
        ("קניות", 500),
        ("שונות", 500),
        ("טבק", 500),
    ]

    for category, amount in budgets:
        cur.execute(
            "INSERT OR IGNORE INTO budget (category, amount) VALUES (?, ?);",
            (category, amount)
        )

    conn.commit()
    conn.close()
    print("Budget table created/updated successfully.")

if __name__ == "__main__":
    main()
