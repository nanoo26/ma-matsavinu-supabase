from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import os

DB_PATH = "expenses.db"
app = Flask(__name__)


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def normalize_date(date_str: str) -> str:
    if not date_str:
        return ""
    parts = date_str.split("-")
    if len(parts) != 3:
        return date_str
    year, month, day = parts
    return f"{day}/{month}/{year}"


def date_for_input(db_date: str) -> str:
    if not db_date:
        return ""
    parts = db_date.split("/")
    if len(parts) != 3:
        return db_date
    day, month, year = parts
    return f"{year}-{month}-{day}"


@app.route("/")
def index():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, date, category, amount, payment_method, note
        FROM expenses
        ORDER BY id DESC
    """)
    expenses = cur.fetchall()

    cur.execute("SELECT DISTINCT category FROM expenses ORDER BY category ASC")
    categories = [row["category"] for row in cur.fetchall()]

    conn.close()

    return render_template(
        "expenses.html",
        expenses=expenses,
        categories=categories,
        selected_category=""
    )


@app.route("/add", methods=["GET", "POST"])
def add_expense():
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == "POST":
        date = normalize_date(request.form["date"])
        category = request.form["category"]
        amount = float(request.form["amount"])
        payment_method = request.form["payment_method"]
        note = request.form["note"]

        cur.execute("""
            INSERT INTO expenses (date, category, amount, payment_method, note)
            VALUES (?, ?, ?, ?, ?)
        """, (date, category, amount, payment_method, note))

        conn.commit()
        conn.close()
        return redirect(url_for("index"))

    cur.execute("SELECT DISTINCT category FROM expenses ORDER BY category ASC")
    categories = [row["category"] for row in cur.fetchall()]
    conn.close()

    return render_template("add_expense.html", categories=categories)


@app.route("/edit/<int:expense_id>", methods=["GET", "POST"])
def edit_expense(expense_id):
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == "POST":
        date = normalize_date(request.form["date"])
        category = request.form["category"]
        amount = float(request.form["amount"])
        payment_method = request.form["payment_method"]
        note = request.form["note"]

        cur.execute("""
            UPDATE expenses
            SET date = ?, category = ?, amount = ?, payment_method = ?, note = ?
            WHERE id = ?
        """, (date, category, amount, payment_method, note, expense_id))

        conn.commit()
        conn.close()
        return redirect(url_for("index"))

    cur.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,))
    expense = cur.fetchone()

    if not expense:
        conn.close()
        return redirect(url_for("index"))

    cur.execute("SELECT DISTINCT category FROM expenses ORDER BY category ASC")
    categories = [row["category"] for row in cur.fetchall()]

    conn.close()

    return render_template(
        "edit_expense.html",
        expense=expense,
        categories=categories,
        date_for_input=date_for_input
    )


@app.route("/delete/<int:expense_id>")
def delete_expense(expense_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
