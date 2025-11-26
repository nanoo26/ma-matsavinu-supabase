from flask import Flask, render_template, request, redirect, url_for 
import os
import requests
from datetime import datetime
from collections import defaultdict

app = Flask(__name__)


# כל הקטגוריות במקום אחד
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

def parse_ddmmyyyy(date_str: str):
    """קולט מחרוזת 'dd/mm/yyyy' ומחזיר (day, month, year) או None אם לא תקין."""
    try:
        day, month, year = date_str.split("/")
        return int(day), int(month), int(year)
    except Exception:
        return None


def sort_by_date_desc(exp):
    """מפתח מיון להוצאות מהחדש לישן."""
    date_str = exp.get("date") or ""
    parsed = parse_ddmmyyyy(date_str)
    if not parsed:
        return (0, 0, 0, 0)
    day, month, year = parsed
    return (year, month, day, exp.get("id", 0))


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

    # כאן השתמשנו ברשימת הקטגוריות הגלובלית
    categories = CATEGORIES
    return render_template("add_expense.html", categories=categories)



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

    categories = CATEGORIES
    return render_template(
        "edit_expense.html",
        expense=expense,
        categories=categories,
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

from datetime import date

# רשימת קטגוריות מרכזית
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


@app.route("/budget", methods=["GET", "POST"])
def budget():
    # חודש נבחר מה־query string (למשל ?month=2025-11) או החודש הנוכחי כברירת מחדל
    month = request.args.get("month") or datetime.now().strftime("%Y-%m")

    url = f"{SUPABASE_URL}/rest/v1/budgets"

    if request.method == "POST":
        # קוראים את החודש גם מהטופס (יש hidden בשם month)
        month = request.form.get("month") or month

        rows = []
        for cat in CATEGORIES:
            field_name = f"budget_{cat}"
            raw_val = (request.form.get(field_name) or "").strip()

            if not raw_val:
                amount = 0.0
            else:
                try:
                    amount = float(raw_val)
                except ValueError:
                    amount = 0.0

            rows.append(
                {
                    "month": month,
                    "category": cat,
                    "amount": amount,
                }
            )

        # 1) מוחקים את כל התקציבים של החודש הזה
        delete_resp = requests.delete(
            url,
            headers=supabase_headers({"Prefer": "return=minimal"}),
            params={"month": f"eq.{month}"},
        )
        print("DEBUG /budget DELETE status:", delete_resp.status_code, delete_resp.text)
        if not delete_resp.ok:
            return (
                f"Supabase delete error {delete_resp.status_code}: {delete_resp.text}",
                500,
            )

        # 2) מכניסים מחדש את כל השורות מהטופס
        insert_resp = requests.post(
            url,
            headers=supabase_headers(),  # לא צריך Prefer מיוחד
            json=rows,
        )
        print("DEBUG /budget INSERT status:", insert_resp.status_code, insert_resp.text)
        if not insert_resp.ok:
            return (
                f"Supabase insert error {insert_resp.status_code}: {insert_resp.text}",
                500,
            )

        # חוזרים לעמוד התקציב לאותו חודש
        return redirect(url_for("budget", month=month))

    # ----- GET: טעינת תקציב קיים -----
    params = {
        "select": "category, month, amount",
        "month": f"eq.{month}",
    }
    resp = requests.get(url, headers=supabase_headers(), params=params)
    print("DEBUG /budget GET status:", resp.status_code, resp.text)
    if not resp.ok:
        return f"Supabase get error {resp.status_code}: {resp.text}", 500

    existing_rows = resp.json()
    existing_map = {row["category"]: row["amount"] for row in existing_rows}

    # בונים רשימה מסודרת לפי CATEGORIES, גם אם אין עדיין שורה בטבלה
    budgets = []
    for cat in CATEGORIES:
        budgets.append(
            {
                "category": cat,
                "amount": existing_map.get(cat, 0.0),
            }
        )

    return render_template("budget.html", month=month, budgets=budgets)



from datetime import date

# ...

@app.route("/reports")
def reports():
    # חודש נבחר כ-YYYY-MM, למשל "2025-11"
    month = request.args.get("month")
    if not month:
        today = date.today()
        month = f"{today.year}-{today.month:02d}"

    year_str, month_str = month.split("-")
    display_month = f"{month_str}/{year_str}"  # ככה התאריכים נשמרים אצלך: 11/2025

    # ---------- 1. הוצאות לפי חודש ----------
    url_exp = f"{SUPABASE_URL}/rest/v1/expenses"
    params_exp = {
        "select": "category,amount,date",
        "date": f"like.*{display_month}",
    }
    r_exp = requests.get(url_exp, headers=supabase_headers(), params=params_exp)
    if not r_exp.ok:
        print("DEBUG /reports expenses:", r_exp.status_code, r_exp.text)
        return f"Supabase expenses error {r_exp.status_code}", 400
    expenses = r_exp.json()

    spent_by_cat = {c: 0.0 for c in CATEGORIES}
    for row in expenses:
        cat = row.get("category")
        try:
            amount = float(row.get("amount") or 0)
        except (TypeError, ValueError):
            amount = 0.0
        if cat in spent_by_cat:
            spent_by_cat[cat] += amount
        else:
            spent_by_cat[cat] = amount

    # ---------- 2. תקציבים לפי חודש ----------
    url_bud = f"{SUPABASE_URL}/rest/v1/budgets"
    params_bud = {
        "select": "category,amount",
        "month": f"eq.{month}",
    }
    r_bud = requests.get(url_bud, headers=supabase_headers(), params=params_bud)
    if not r_bud.ok:
        print("DEBUG /reports budgets:", r_bud.status_code, r_bud.text)
        return f"Supabase budgets error {r_bud.status_code}", 400
    budget_rows = r_bud.json()
    budget_by_cat = {
        row["category"]: float(row.get("amount") or 0)
        for row in budget_rows
    }

    # ---------- 3. בניית שורות לדוח + סיכומים ----------
    rows = []
    total_budget = 0.0
    total_spent = 0.0

    for cat in CATEGORIES:
        b = budget_by_cat.get(cat, 0.0)
        s = spent_by_cat.get(cat, 0.0)
        diff = b - s
        percent = (s / b * 100) if b > 0 else 0.0

        rows.append({
            "category": cat,
            "budget": b,
            "spent": s,
            "diff": diff,
            "percent_used": percent,
            "overspend": (b > 0 and s > b),
        })

        total_budget += b
        total_spent += s

    used_percent = (total_spent / total_budget * 100) if total_budget > 0 else 0.0

    summary = {
        "total_budget": total_budget,
        "total_spent": total_spent,
        "used_percent": used_percent,
        "display_month": display_month,
    }

    # ---------- 4. רשימת חודשים לבחירה (6 חודשים אחרונים) ----------
    month_options = []
    today = date.today()
    cur_y, cur_m = today.year, today.month
    for i in range(6):
        y = cur_y
        m = cur_m - i
        while m <= 0:
            y -= 1
            m += 12
        value = f"{y}-{m:02d}"
        label = f"{m:02d}/{y}"
        month_options.append({"value": value, "label": label})

    return render_template(
        "reports.html",
        summary=summary,
        rows=rows,
        month=month,
        month_options=month_options,
    )



# =========================
# main
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
