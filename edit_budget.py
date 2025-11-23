import sqlite3

DB_PATH = "expenses.db"


def show_budgets(conn):
    cur = conn.cursor()
    cur.execute("SELECT id, category, amount FROM budget ORDER BY id;")
    rows = cur.fetchall()
    print("\nCurrent budget values:\n")
    for row in rows:
        print(f"{row[0]:2d}. {row[1]} -> {row[2]:.0f} ₪")
    print()


def update_budget(conn, category, amount):
    cur = conn.cursor()
    cur.execute(
        "UPDATE budget SET amount = ? WHERE category = ?;",
        (amount, category),
    )
    conn.commit()


def main():
    conn = sqlite3.connect(DB_PATH)

    while True:
        show_budgets(conn)
        cat = input("Category to update (or ENTER to quit): ").strip()
        if not cat:
            break
        try:
            new_amount = float(input("New monthly amount: ").strip())
        except ValueError:
            print("Invalid number, try again.")
            continue

        update_budget(conn, cat, new_amount)
        print("Updated.\n")

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
