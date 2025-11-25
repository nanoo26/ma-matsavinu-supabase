from flask import Flask, render_template, request, redirect, url_for
import os
import requests
from datetime import datetime  # חדש - בשביל המיון לפי תאריך

app = Flask(__name__)

# =========================
# Supabase config
# =========================
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_API_KEY")  # גיבוי אם ישן יישאר בטעות
    or ""
)

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "SUPABASE_URL או SUPABASE_KEY לא מוגדרים ב-Environment של Render"
    )


def supabase_headers(extra=None):
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if extra:
        headers.update(extra)
    return headers


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


def expense_sort_key(e: dict):
    """
    מחזיר מפתח מיון:
    קודם לפי תאריך אמיתי (DD/MM/YYYY),
    ואם אין/לא תקין - לפי id.
    """
    raw_date = e.get("date") or ""
    try:
        dt = datetime.strptime(raw_date, "%d/%m/%Y")
    except ValueError:
        dt = datetime.min

    return (dt, e.get("id", 0))


# =========================
# Routes
# =========================
@app.route("/")
def index():
    url = f"{SUPABASE_URL}/rest/v1/expenses"
    params = {
        "select": "id,date,category,amount,payment_method,description",
        # נשאיר גם order בצד Supabase, אבל נמיין שוב בצד פייתון ליתר ביטחון
        "order": "id.desc",
    }

    resp = requests.get(url, headers=supabase_headers(), params=params)
    print("DEBUG / index status:", resp.status_code)
    if not resp.ok:
        print("DEBUG / index body:", resp.text)
        return f"Supabase error {resp.status_code}", 500

    expenses = resp.json()

    # מיון סופי - מהחדש לישן לפי תאריך (ואז לפי id)
    expenses.sort(key=expense_sort_key, reverse=True)

    categories = sorted({e.get("category") for e in expenses if e.get("category")})

    return render_template(
        "expenses.html",
        expenses=expenses,
        categories=categories,
        selected_category=""
    )


@app.route("/add", methods=["GET", "POST"])
def add_expense():
    if request.method == "POST":
        date = normalize_date(request.form["date"])
        category = request.form["category"]
        amount = float(request.form["amount"])
        payment_method = request.form["payment_method"]
        description = request.form["description"]

        url = f"{SUPABASE_URL}/rest/v1/expenses"
        payload = {
            "date": date,
            "category": category,
            "amount": amount,
            "payment_method": payment_method,
            "description": description,
        }

        resp = requests.post(
            url,
            headers=supabase_headers({"Prefer": "return=minimal"}),
            json=payload,
        )
        print("DEBUG /add status:", resp.status_code, resp.text)
        if not resp.ok:
            return f"Supabase insert error {resp.status_code}", 500

        return redirect(url_for("index"))

    categories = ["מזון", "בילויים", "בית", "ילדים", "רכב",
                  "בריאות", "חוגים", "קניות", "שונות", "טבק"]

    return render_template("add_expense.html", categories=categories)


@app.route("/edit/<int:expense_id>", methods=["GET", "POST"])
def edit_expense(expense_id):
    url = f"{SUPABASE_URL}/rest/v1/expenses"

    if request.method == "POST":
        date = normalize_date(request.form["date"])
        category = request.form["category"]
        amount = float(request.form["amount"])
        payment_method = request.form["payment_method"]
        description = request.form["description"]

        params = {"id": f"eq.{expense_id}"}
        payload = {
            "date": date,
            "category": category,
            "amount": amount,
            "payment_method": payment_method,
            "description": description,
        }

        resp = requests.patch(
            url,
            headers=supabase_headers({"Prefer": "return=minimal"}),
            params=params,
            json=payload,
        )
        print("DEBUG /edit status:", resp.status_code, resp.text)
        if not resp.ok:
            return f"Supabase update error {resp.status_code}", 500

        return redirect(url_for("index"))

    params = {
        "select": "id,date,category,amount,payment_method,description",
        "id": f"eq.{expense_id}",
        "limit": 1,
    }
    resp = requests.get(url, headers=supabase_headers(), params=params)
    print("DEBUG /edit GET status:", resp.status_code)
    if not resp.ok:
        print("DEBUG /edit GET body:", resp.text)
        return f"Supabase get error {resp.status_code}", 500

    rows = resp.json()
    if not rows:
        return redirect(url_for("index"))

    expense = rows[0]

    categories = ["מזון", "בילויים", "בית", "ילדים", "רכב",
                  "בריאות", "חוגים", "קניות", "שונות", "טבק"]

    return render_template(
        "edit_expense.html",
        expense=expense,
        categories=categories,
        date_for_input=date_for_input,
    )


@app.route("/delete/<int:expense_id>")
def delete_expense(expense_id):
    url = f"{SUPABASE_URL}/rest/v1/expenses"
    params = {"id": f"eq.{expense_id}"}

    resp = requests.delete(
        url,
        headers=supabase_headers({"Prefer": "return=minimal"}),
        params=params,
    )
    print("DEBUG /delete status:", resp.status_code, resp.text)
    if not resp.ok:
        return f"Supabase delete error {resp.status_code}", 500

    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
