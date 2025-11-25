from flask import Flask, render_template, request, redirect, url_for
import os
import requests

app = Flask(__name__)

# =========================
# Supabase config
# =========================
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_API_KEY")  # גיבוי אם נשאר משתנה ישן
    or ""
)

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "SUPABASE_URL או SUPABASE_KEY לא מוגדרים ב-Environment"
    )


def supabase_headers(extra=None):
    """
    מחזיר כותרות בסיס לסופבייס.
    אפשר להעביר dict נוסף שיתמזג לכותרות.
    """
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if extra:
        headers.update(extra)
    return headers


# רשימת קטגוריות קבועה לכל האפליקציה
CATEGORIES = [
    "מזון",
    "בילויים",
    "בית",
    "ילדים",
    "רכב",
    "בריאות",
    "חוגים",
    "קניות",
    "שונות",
    "טבק",
]


# =========================
# עזר לתאריכים
# =========================
def normalize_date(date_str: str) -> str:
    """
    מקבל תאריך מפורמט input type="date" (YYYY-MM-DD)
    ומחזיר DD/MM/YYYY כמו בטבלה בסופבייס.
    """
    if not date_str:
        return ""
    parts = date_str.split("-")
    if len(parts) != 3:
        return date_str
    year, month, day = parts
    return f"{day}/{month}/{year}"


def date_for_input(db_date: str) -> str:
    """
    הופך DD/MM/YYYY לפורמט של input date כלומר YYYY-MM-DD.
    """
    if not db_date:
        return ""
    parts = db_date.split("/")
    if len(parts) != 3:
        return db_date
    day, month, year = parts
    return f"{year}-{month}-{day}"


# =========================
# מסך ההוצאות
# =========================
@app.route("/")
def index():
    url = f"{SUPABASE_URL}/rest/v1/expenses"
    params = {
        "select": "id,date,category,amount,payment_method,description",
        "order": "id.desc",
    }

    resp = requests.get(url, headers=supabase_headers(), params=params)
    print("DEBUG / index status:", resp.status_code)
    if not resp.ok:
        print("DEBUG / index body:", resp.text)
        return f"Supabase error {resp.status_code}", 500

    expenses = resp.json()
    categories = sorted({e.get("category") for e in expenses if e.get("category")})

    return render_template(
        "expenses.html",
        expenses=expenses,
        categories=categories,
        selected_category="",
    )


# =========================
# הוספת הוצאה
# =========================
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

    return render_template("add_expense.html", categories=CATEGORIES)


# =========================
# עריכת הוצאה
# =========================
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

    return render_template(
        "edit_expense.html",
        expense=expense,
        categories=CATEGORIES,
        date_for_input=date_for_input,
    )


# =========================
# מחיקת הוצאה
# =========================
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


# =========================
# מסך תקציב לפי קטגוריה
# =========================
@app.route("/budget", methods=["GET", "POST"])
def budget():
    url = f"{SUPABASE_URL}/rest/v1/budgets"

    # ====== POST - שמירת תקציבים ======
    if request.method == "POST":
        rows = []

        for idx, cat in enumerate(CATEGORIES):
            raw_val = request.form.get(f"budget_{idx}", "").strip()

            if not raw_val:
                amount = 0.0
            else:
                try:
                    amount = float(raw_val.replace(",", ""))
                except ValueError:
                    amount = 0.0

            rows.append({
                "category": cat,
                "monthly_budget": amount,
            })

        resp = requests.post(
            url + "?on_conflict=category",
            headers=supabase_headers({
                "Prefer": "resolution=merge-duplicates"
            }),
            json=rows,
        )
        print("DEBUG /budget POST:", resp.status_code, resp.text)

        if not resp.ok:
            return f"Supabase upsert error {resp.status_code}", 500

        return redirect(url_for("budget"))

    # ====== GET - טעינת תקציבים ======
    resp = requests.get(
        url,
        headers=supabase_headers(),
        params={"select": "category,monthly_budget"},
    )
    print("DEBUG /budget GET:", resp.status_code)

    budgets_map = {}
    if resp.ok:
        for row in resp.json():
            budgets_map[row["category"]] = row.get("monthly_budget", 0)
    else:
        print("DEBUG /budget GET body:", resp.text)

    budget_rows = []
    for cat in CATEGORIES:
        budget_rows.append({
            "category": cat,
            "monthly_budget": budgets_map.get(cat, 0),
        })

    return render_template("budget.html", budget_rows=budget_rows)



# =========================
# main
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
