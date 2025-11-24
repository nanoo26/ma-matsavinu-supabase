from flask import Flask, render_template, request, redirect, url_for, Response
import requests
import os
import io
import csv
import json
import sqlite3
from collections import defaultdict

# =========================
# בסיס נתונים מקומי (SQLite) לטבלת התקציב
# =========================

DB_PATH = "expenses.db"
app = Flask(__name__)


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_budget_table():
    """יוצר טבלת תקציב אם לא קיימת."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS budget (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT UNIQUE NOT NULL,
            amount REAL NOT NULL DEFAULT 0
        );
        """
    )
    conn.commit()
    conn.close()


# נריץ פעם אחת בזמן עליית האפליקציה (גם לוקאלי וגם ב־Render)
ensure_budget_table()

# =========================
# Supabase config
# =========================

DEFAULT_SUPABASE_URL = "https://rdukuqlayxpwdvyrepxe.supabase.co"
DEFAULT_SUPABASE_API_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJkdWt1cWxheXhwd2R2eXJlcHhlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjI2Mzc0OTAsImV4cCI6MjA3ODIxMzQ5MH0."
    "PFeKjEGgdxYZgXtRVAQ072jmOtW8wQqSs6gRYB3il6M"
)


def load_supabase_config():
    """טוען SUPABASE_URL ו־SUPABASE_API_KEY מה־env אם קיימים, אחרת ברירת מחדל."""
    env_url = os.environ.get("SUPABASE_URL", "").strip()
    if env_url:
        supabase_url = env_url
    else:
        supabase_url = DEFAULT_SUPABASE_URL

    env_key = os.environ.get("SUPABASE_API_KEY", "").strip()
    if env_key:
        key = env_key
    else:
        key = DEFAULT_SUPABASE_API_KEY

    # ודא שאין תווים לא ASCII
    if not all(ord(ch) < 128 for ch in key):
        raise RuntimeError(
            "SUPABASE_API_KEY contains non ASCII characters. "
            "Clean your SUPABASE_API_KEY environment variable (no Hebrew / special chars)."
        )

    return supabase_url, key


SUPABASE_URL, SUPABASE_API_KEY = load_supabase_config()
SUPABASE_TABLE = "expenses"


def supabase_headers():
    return {
        "apikey": SUPABASE_API_KEY,
        "Authorization": f"Bearer {SUPABASE_API_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


# =========================
# Helpers - תאריכים / חודשים
# =========================

def normalize_date(date_str: str) -> str:
    """YYYY-MM-DD -> DD/MM/YYYY"""
    if not date_str:
        return ""
    parts = date_str.split("-")
    if len(parts) != 3:
        return date_str
    year, month, day = parts
    return f"{day}/{month}/{year}"


def date_for_input(db_date: str) -> str:
    """DD/MM/YYYY -> YYYY-MM-DD (לטופס עריכה)"""
    if not db_date:
        return ""
    parts = db_date.split("/")
    if len(parts) != 3:
        return db_date
    day, month, year = parts
    return f"{year}-{month}-{day}"


def month_key_from_date(date_str: str) -> str:
    """DD/MM/YYYY -> YYYY-MM (מפתח חודש)"""
    try:
        day, month, year = date_str.split("/")
        return f"{year}-{month}"
    except ValueError:
        return ""


def build_months_list(expenses):
    """בונה רשימת חודשים קיימים בהוצאות."""
    seen = {}
    for exp in expenses:
        date_str = exp.get("date") or ""
        key = month_key_from_date(date_str)
        if not key:
            continue
        year, month = key.split("-")
        label = f"{month}/{year}"
        seen[key] = label

    items = [{"key": k, "label": v} for k, v in seen.items()]
    items.sort(key=lambda x: x["key"], reverse=True)
    return items


# =========================
# Supabase CRUD
# =========================

def fetch_all_expenses():
    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}"
    params = {
        "select": "*",
        "order": "date.desc,id.desc",
    }
    r = requests.get(url, headers=supabase_headers(), params=params)
    r.raise_for_status()
    return r.json()


def fetch_single_expense(expense_id: int):
    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}"
    params = {
        "id": f"eq.{expense_id}",
        "select": "*",
    }
    r = requests.get(url, headers=supabase_headers(), params=params)
    r.raise_for_status()
    data = r.json()
    return data[0] if data else None


def insert_expense(date, category, amount, payment_method, description):
    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}"
    payload = {
        "date": date,
        "category": category,
        "amount": amount,
        "payment_method": payment_method,
        "description": description,
    }

    print("Supabase INSERT payload:", json.dumps(payload, ensure_ascii=False))
    r = requests.post(url, headers=supabase_headers(), json=payload)
    print("Supabase INSERT status:", r.status_code)
    print("Supabase INSERT response:", r.text)

    if r.status_code not in (200, 201, 204):
        raise RuntimeError(f"Supabase INSERT failed: {r.status_code} {r.text}")


def update_expense(expense_id, date, category, amount, payment_method, description):
    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}"
    payload = {
        "date": date,
        "category": category,
        "amount": amount,
        "payment_method": payment_method,
        "description": description,
    }
    params = {"id": f"eq.{expense_id}"}

    print(f"Supabase UPDATE id={expense_id} payload:", json.dumps(payload, ensure_ascii=False))
    r = requests.patch(url, headers=supabase_headers(), json=payload, params=params)
    print("Supabase UPDATE status:", r.status_code)
    print("Supabase UPDATE response:", r.text)

    if r.status_code not in (200, 204):
        raise RuntimeError(f"Supabase UPDATE failed: {r.status_code} {r.text}")


def delete_expense_db(expense_id):
    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}"
    params = {"id": f"eq.{expense_id}"}

    headers = supabase_headers().copy()
    headers["Prefer"] = "return=minimal"

    print(f"Supabase DELETE id={expense_id} url={url} params={params}")
    r = requests.delete(url, headers=headers, params=params)
    print("Supabase DELETE status:", r.status_code)
    print("Supabase DELETE response:", r.text)

    if r.status_code not in (200, 204):
        raise RuntimeError(f"Supabase DELETE failed: {r.status_code} {r.text}")


# =========================
# קבועים - קטגוריות ואמצעי תשלום
# =========================

DEFAULT_CATEGORIES = [
    "בילויים",
    "בית",
    "ילדים",
    "בריאות",
    "רכב",
    "חוגים",
    "קניות",
    "שונות",
    "טבק",
]

PAYMENT_METHODS = [
    "מקס שלום",
    "מקס חגית",
    "כאל ויזה",
    "לאומי שלום",
    'עו"ש',
]


# =========================
# ראוטים
# =========================

@app.route("/")
def root():
    return redirect(url_for("index"))


@app.route("/expenses")
def index():
    """מסך רשימת הוצאות + בר גרפי תקציב מול ביצוע."""
    expenses = fetch_all_expenses()
    months = build_months_list(expenses)

    selected_month = request.args.get("month")
    valid_keys = {m["key"] for m in months}

    if months:
        if not selected_month or selected_month not in valid_keys:
            selected_month = months[0]["key"]
    else:
        selected_month = None

    if selected_month:
        filtered_expenses = [
            e for e in expenses
            if month_key_from_date(e.get("date", "")) == selected_month
        ]
    else:
        filtered_expenses = expenses

    total_rows = len(filtered_expenses)
    total_amount = sum(float(e.get("amount", 0) or 0) for e in filtered_expenses)

    # סה"כ תקציב חודשי (אותו תקציב לכל חודש כרגע)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(SUM(amount), 0) AS total_budget FROM budget;")
    row = cur.fetchone()
    conn.close()
    total_budget = row["total_budget"] if row else 0.0

    return render_template(
        "expenses.html",
        expenses=filtered_expenses,
        total_rows=total_rows,
        total_amount=total_amount,
        months=months,
        selected_month=selected_month,
        total_budget=total_budget,
    )


@app.route("/add_expenses", methods=["GET", "POST"])
def add_expense():
    categories = sorted(set(DEFAULT_CATEGORIES))
    payment_methods = PAYMENT_METHODS

    if request.method == "POST":
        raw_date = request.form.get("date", "")
        date = normalize_date(raw_date)
        category = request.form.get("category", "").strip()
        amount_raw = request.form.get("amount", "").strip()
        payment_method = request.form.get("payment_method", "").strip()
        description = request.form.get("description", "").strip()

        # ולידציה בסיסית
        if not date or not category or not amount_raw or not payment_method or not description:
            return render_template(
                "add_expense.html",
                error="נא למלא את כל השדות",
                categories=categories,
                payment_methods=payment_methods,
            )

        if payment_method not in PAYMENT_METHODS:
            return render_template(
                "add_expense.html",
                error="יש לבחור אמצעי תשלום מתוך הרשימה",
                categories=categories,
                payment_methods=payment_methods,
            )

        try:
            amount = float(amount_raw.replace(",", ""))
        except ValueError:
            return render_template(
                "add_expense.html",
                error="סכום לא תקין",
                categories=categories,
                payment_methods=payment_methods,
            )

        # שמירה ל-Supabase עם לוגים (יעזרו לנו גם ב-Render)
        print("### ADD_EXPENSE: inserting to Supabase")
        insert_expense(date, category, amount, payment_method, description)
        print("### ADD_EXPENSE: insert done")

        # מחזירים לחודש של ההוצאה החדשה, כדי שלא "תיעלם" בגלל סינון חודש
        selected_month = month_key_from_date(date)  # מחזיר משהו כמו "2025-11"
        if selected_month:
            return redirect(url_for("index", month=selected_month))
        else:
            # אם מסיבה כלשהי אין חודש תקין - נחזור לרשימה בלי פילטר
            return redirect(url_for("index"))

    # GET - טופס ריק
    return render_template(
        "add_expense.html",
        error=None,
        categories=categories,
        payment_methods=payment_methods,
    )




@app.route("/edit/<int:expense_id>", methods=["GET", "POST"])
def edit_expense(expense_id):
    expense = fetch_single_expense(expense_id)
    if not expense:
        return redirect(url_for("index"))

    categories = sorted(set(DEFAULT_CATEGORIES))
    payment_methods = PAYMENT_METHODS

    if request.method == "POST":
        raw_date = request.form.get("date", "")
        date = normalize_date(raw_date)
        category = request.form.get("category", "").strip()
        amount_raw = request.form.get("amount", "").strip()
        payment_method = request.form.get("payment_method", "").strip()
        description = request.form.get("description", "").strip()

        if not date or not category or not amount_raw or not payment_method or not description:
            return render_template(
                "edit_expense.html",
                expense=expense,
                categories=categories,
                payment_methods=payment_methods,
                date_input=raw_date,
                error="נא למלא את כל השדות",
            )

        if payment_method not in PAYMENT_METHODS:
            return render_template(
                "edit_expense.html",
                expense=expense,
                categories=categories,
                payment_methods=payment_methods,
                date_input=raw_date,
                error="יש לבחור אמצעי תשלום מתוך הרשימה",
            )

        try:
            amount = float(amount_raw.replace(",", ""))
        except ValueError:
            return render_template(
                "edit_expense.html",
                expense=expense,
                categories=categories,
                payment_methods=payment_methods,
                date_input=raw_date,
                error="סכום לא תקין",
            )

        update_expense(expense_id, date, category, amount, payment_method, description)
        return redirect(url_for("index"))

    date_input = date_for_input(expense.get("date", ""))
    return render_template(
        "edit_expense.html",
        expense=expense,
        categories=categories,
        payment_methods=payment_methods,
        date_input=date_input,
        error=None,
    )


@app.route("/delete/<int:expense_id>")
def delete_expense(expense_id):
    delete_expense_db(expense_id)
    return redirect(url_for("index"))


@app.route("/reports")
def reports():
    """דוח סיכום חודשי + לפי קטגוריה."""
    expenses = fetch_all_expenses()
    months = build_months_list(expenses)

    selected_month = request.args.get("month")
    valid_keys = {m["key"] for m in months}

    if months:
        if not selected_month or selected_month not in valid_keys:
            selected_month = months[0]["key"]
    else:
        selected_month = None

    monthly_summary = []
    category_summary = []

    if selected_month:
        filtered = [
            e for e in expenses
            if month_key_from_date(e.get("date", "")) == selected_month
        ]

        year, month = selected_month.split("-")
        total = sum(float(e.get("amount", 0) or 0) for e in filtered)

        monthly_summary = [{
            "year": year,
            "month": month,
            "total": total,
        }]

        by_cat = defaultdict(float)
        for e in filtered:
            cat = e.get("category") or "לא מוגדר"
            by_cat[cat] += float(e.get("amount", 0) or 0)

        category_summary = [
            {"category": cat, "total": amount}
            for cat, amount in sorted(by_cat.items(), key=lambda x: x[1], reverse=True)
        ]

    return render_template(
        "reports.html",
        months=months,
        selected_month=selected_month,
        monthly_summary=monthly_summary,
        category_summary=category_summary,
    )


@app.route("/reports/budget")
def report_budget():
    """דוח תקציב מול ביצוע + גרף."""
    expenses = fetch_all_expenses()
    months_items = build_months_list(expenses)
    months = months_items

    selected_month = request.args.get("month")
    valid_keys = {m["key"] for m in months_items}

    if months_items:
        if not selected_month or selected_month not in valid_keys:
            selected_month = months_items[0]["key"]
    else:
        selected_month = None

    selected_month_label = None
    if selected_month:
        for m in months_items:
            if m["key"] == selected_month:
                selected_month_label = m["label"]
                break

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT category, amount FROM budget")
    budget_rows = cur.fetchall()
    conn.close()

    budget_map = {row["category"]: row["amount"] for row in budget_rows}

    rows = []
    total_budget = 0.0
    total_spent = 0.0

    if selected_month:
        spent_by_cat = defaultdict(float)
        for e in expenses:
            if month_key_from_date(e.get("date", "")) == selected_month:
                cat = e.get("category") or "לא מוגדר"
                amt = float(e.get("amount") or 0)
                spent_by_cat[cat] += amt

        for category, budget in budget_map.items():
            spent = spent_by_cat.get(category, 0.0)
            diff = budget - spent
            rows.append(
                {
                    "category": category,
                    "budget": budget,
                    "spent": spent,
                    "diff": diff,
                }
            )
            total_budget += budget
            total_spent += spent

    categories = [row["category"] for row in rows]
    budget_values = [row["budget"] for row in rows]
    spent_values = [row["spent"] for row in rows]

    return render_template(
        "report_budget.html",
        rows=rows,
        months=months,
        selected_month=selected_month,
        selected_month_label=selected_month_label,
        total_budget=total_budget,
        total_spent=total_spent,
        categories=categories,
        budget_values=budget_values,
        spent_values=spent_values,
    )


@app.route("/budget", methods=["GET", "POST"])
def manage_budget():
    """מסך ניהול תקציב חודשי (עדכון, הוספה, מחיקה)."""
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == "POST":
        # עדכון סכומים
        cur.execute("SELECT id, category, amount FROM budget ORDER BY category;")
        existing_rows = cur.fetchall()

        for row in existing_rows:
            field_name = f"amount_{row['id']}"
            amount_raw = (request.form.get(field_name, "") or "").strip()
            delete_flag = request.form.get(f"delete_{row['id']}", "")

            # מחיקה
            if delete_flag:
                cur.execute("DELETE FROM budget WHERE id = ?;", (row["id"],))
                continue

            if not amount_raw:
                continue

            try:
                amount = float(amount_raw.replace(",", ""))
            except ValueError:
                amount = row["amount"]

            cur.execute(
                "UPDATE budget SET amount = ? WHERE id = ?;",
                (amount, row["id"]),
            )

        # הוספת קטגוריה חדשה
        new_category = (request.form.get("new_category", "") or "").strip()
        new_amount_raw = (request.form.get("new_amount", "") or "").strip()
        if new_category and new_amount_raw:
            try:
                new_amount = float(new_amount_raw.replace(",", ""))
                cur.execute(
                    "INSERT OR IGNORE INTO budget (category, amount) VALUES (?, ?);",
                    (new_category, new_amount),
                )
            except ValueError:
                pass

        conn.commit()

    cur.execute("SELECT id, category, amount FROM budget ORDER BY category;")
    rows = cur.fetchall()
    conn.close()

    return render_template("budget_manage.html", rows=rows)


@app.route("/export")
def export_csv():
    expenses = fetch_all_expenses()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["date", "category", "amount", "payment_method", "description"])
    for row in expenses:
        writer.writerow(
            [
                row.get("date", ""),
                row.get("category", ""),
                row.get("amount", 0),
                row.get("payment_method", ""),
                row.get("description", ""),
            ]
        )

    csv_data = output.getvalue()
    output.close()

    # BOM בשביל אקסל בעברית
    csv_data = "\ufeff" + csv_data

    return Response(
        csv_data,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=expenses_export.csv"
        },
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
