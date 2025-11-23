from flask import Flask, render_template, request, redirect, url_for, Response
import requests
import os
import io
import csv
import json
from collections import defaultdict

app = Flask(__name__)

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
    """
    טוען SUPABASE_URL ו־SUPABASE_API_KEY מה־env אם קיימים,
    אחרת משתמש בערכי ברירת המחדל.
    וגם בודק שאין תווים לא ASCII במפתח.
    """
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

    if not all(ord(ch) < 128 for ch in key):
        raise RuntimeError(
            "SUPABASE_API_KEY contains non ASCII characters. "
            "Clean your SUPABASE_API_KEY environment variable (no Hebrew / special chars)."
        )

    return supabase_url, key


SUPABASE_URL, SUPABASE_API_KEY = load_supabase_config()
SUPABASE_TABLE = "expenses"


def supabase_headers(extra=None):
    """
    כותרות בסיס לקריאות לסופבייס.
    """
    base = {
        "apikey": SUPABASE_API_KEY,
        "Authorization": f"Bearer {SUPABASE_API_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        base.update(extra)
    return base


# =========================
# Helpers - תאריכים / חודשים
# =========================

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


def month_key_from_date(date_str: str) -> str:
    try:
        day, month, year = date_str.split("/")
        return f"{year}-{month}"
    except ValueError:
        return ""


def build_months_list(expenses):
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
    """
    מוסיף הוצאה חדשה לטבלת expenses בסופבייס.
    משתמש ב-POST רגיל עם json=payload לפי הדוקומנטציה.
    """
    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}"
    payload = {
        "date": date,
        "category": category,
        "amount": amount,
        "payment_method": payment_method,
        "description": description,
    }

    headers = supabase_headers({"Prefer": "return=representation"})

    print("Supabase INSERT payload:", json.dumps(payload, ensure_ascii=False))
    try:
        r = requests.post(
            url,
            headers=headers,
            params=None,
            json=payload,          # שים לב: json=payload ולא data=
            timeout=10,
        )
        print("Supabase INSERT status:", r.status_code)
        print("Supabase INSERT response:", r.text)
        r.raise_for_status()
    except Exception as e:
        print("Supabase INSERT exception:", repr(e))
        raise



def update_expense(expense_id, date, category, amount, payment_method, description):
    """
    מעדכן הוצאה קיימת בסופבייס עם PATCH תקני.
    בלי X-HTTP-Method-Override, אלא PATCH ישיר לפי Supabase.
    """
    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}"
    payload = {
        "date": date,
        "category": category,
        "amount": amount,
        "payment_method": payment_method,
        "description": description,
    }
    params = {
        "id": f"eq.{expense_id}",
    }
    headers = supabase_headers({
        "Prefer": "return=representation",
    })
    

    print(f"Supabase UPDATE id={expense_id} payload:", json.dumps(payload, ensure_ascii=False))
    try:
        r = requests.patch(
            url,
            headers=headers,
            params=params,
            json=payload,      # שוב – json=payload
            timeout=10,
        )
        print("Supabase UPDATE status:", r.status_code)
        print("Supabase UPDATE response:", r.text)
        r.raise_for_status()
    except Exception as e:
        print("Supabase UPDATE exception:", repr(e))
        raise


def delete_expense_db(expense_id):
    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}"
    params = {"id": f"eq.{expense_id}"}
    headers = supabase_headers({"Prefer": "return=minimal"})
    r = requests.delete(url, headers=headers, params=params, timeout=10)
    print(f"Supabase DELETE id={expense_id} status:", r.status_code, "resp:", r.text)
    r.raise_for_status()


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

    return render_template(
        "expenses.html",
        expenses=filtered_expenses,
        total_rows=total_rows,
        total_amount=total_amount,
        months=months,
        selected_month=selected_month,
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

        insert_expense(date, category, amount, payment_method, description)
        return redirect(url_for("index"))

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


@app.route("/export")
def export_csv():
    expenses = fetch_all_expenses()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["date", "category", "amount", "payment_method", "description"])
    for row in expenses:
        writer.writerow([
            row.get("date", ""),
            row.get("category", ""),
            row.get("amount", 0),
            row.get("payment_method", ""),
            row.get("description", ""),
        ])

    csv_data = output.getvalue()
    output.close()

    csv_data = "\ufeff" + csv_data  # BOM בשביל אקסל בעברית

    return Response(
        csv_data,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=expenses_export.csv"
        }
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
