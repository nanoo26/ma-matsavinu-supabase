import os
import requests
from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import datetime, date

# =========================
# Categories & payment methods
# =========================

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

PAYMENT_METHODS = [
    "מקס שלום",
    "מקס חגית",
    "כאל ויזה",
    "לאומי שלום",
    "עו\"ש",
]

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

# =========================
# פונקציות עזר בסיסיות
# =========================
def display_date(date_str):
    """המרת תאריך מאחסון (טקסט) לתצוגה DD/MM/YYYY"""
    if not date_str:
        return ""
    s = str(date_str).strip()
    # אם כבר בפורמט DD/MM/YYYY
    try:
        dt = datetime.strptime(s, "%d/%m/%Y")
        return dt.strftime("%d/%m/%Y")
    except ValueError:
        pass
    # אם בפורמט HTML YYYY-MM-DD
    try:
        dt = datetime.strptime(s, "%Y-%m-%d")
        return dt.strftime("%d/%m/%Y")
    except ValueError:
        pass
    return s


def date_for_input(date_str):
    """המרת תאריך מאחסון (טקסט) לפורמט HTML YYYY-MM-DD"""
    if not date_str:
        return ""
    s = str(date_str).strip()
    # מאחסון DD/MM/YYYY
    try:
        dt = datetime.strptime(s, "%d/%m/%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass
    # כבר בפורמט HTML
    try:
        dt = datetime.strptime(s, "%Y-%m-%d")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass
    return ""


def parse_amount(val) -> float:
    """ניקוי ערך סכום לפורמט מספרי"""
    try:
        return float(str(val).replace(",", "").strip())
    except Exception:
        return 0.0


def current_month():
    """מפתח חודש בצורה YYYY-MM"""
    return date.today().strftime("%Y-%m")


# =========================
# הגדרות Supabase
# =========================
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_API_KEY")
    or ""
)

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "❌ חסרים משתני סביבה SUPABASE_URL או SUPABASE_KEY. "
        "הגדר אותם לפני הרצת האפליקציה."
    )

SUPABASE_EXPENSES_TABLE = "expenses"
SUPABASE_BUDGETS_TABLE = "budgets"
PAYMENT_PLANS_TABLE = "payment_plans"

SUPABASE_EXPENSES_URL = f"{SUPABASE_URL}/rest/v1/{SUPABASE_EXPENSES_TABLE}"
SUPABASE_BUDGETS_URL = f"{SUPABASE_URL}/rest/v1/{SUPABASE_BUDGETS_TABLE}"


def supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def normalize_date(date_str: str) -> str:
    """
    מקבל תאריך בפורמט HTML (YYYY-MM-DD) ומחזיר DD/MM/YYYY לשמירה ב-DB
    """
    if not date_str:
        return ""
    parts = str(date_str).split("-")
    if len(parts) == 3:
        year, month, day = parts
        return f"{day}/{month}/{year}"
    return str(date_str)


def current_month_key() -> str:
    return datetime.now().strftime("%Y-%m")


# =========================
# Supabase config (שכפול כמו בקוד שלך)
# =========================

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_API_KEY")
    or ""
)

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "❌ חסרים משתני סביבה SUPABASE_URL או SUPABASE_KEY. "
        "הגדר אותם לפני הרצת האפליקציה."
    )

SUPABASE_EXPENSES_TABLE = "expenses"
SUPABASE_BUDGETS_TABLE = "budgets"

SUPABASE_EXPENSES_URL = f"{SUPABASE_URL}/rest/v1/{SUPABASE_EXPENSES_TABLE}"
SUPABASE_BUDGETS_URL = f"{SUPABASE_URL}/rest/v1/{SUPABASE_BUDGETS_TABLE}"


def supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

# =========================
# CRUD על הוצאות
# =========================

def fetch_expenses():
    """שליפת כל ההוצאות מ-Supabase, כולל is_fixed ו-description."""
    try:
        resp = requests.get(
            SUPABASE_EXPENSES_URL,
            headers=supabase_headers(),
            params={
                "select": "*",
                "order": "created_at.desc"
            },
            timeout=10,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print("❌ שגיאה בשליפת הוצאות מ-Supabase:", e)
        return []

    data = resp.json()
    expenses = []
    for row in data:
        amount_val = parse_amount(row.get("amount", 0))
        raw_date = row.get("date") or ""
        expenses.append(
            {
                "id": row.get("id"),
                "raw_date": raw_date,
                "date": display_date(raw_date),
                "category": row.get("category") or "",
                "amount": amount_val,
                "payment_method": row.get("payment_method") or "",
                "notes": row.get("description") or "",
                "is_fixed": bool(row.get("is_fixed")),
                "expense_type": row.get("expense_type") or "",
            }
        )
    return expenses


def get_expense_by_id(expense_id: int):
    """שליפת הוצאה בודדת לפורמט טופס עריכה"""
    try:
        resp = requests.get(
            SUPABASE_EXPENSES_URL,
            headers=supabase_headers(),
            params={"select": "*", "id": f"eq.{expense_id}"},
            timeout=10,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print("❌ שגיאה בשליפת הוצאה בודדת:", e)
        return None

    data = resp.json()
    if not data:
        return None

    row = data[0]
    raw_date = row.get("date") or ""
    desc = row.get("description") or row.get("note") or ""

    amount_raw = row.get("amount")
    try:
        amount_val = float(amount_raw) if amount_raw not in (None, "") else 0.0
    except ValueError:
        amount_val = 0.0

    return {
        "id": row.get("id"),
        "date": display_date(raw_date),
        "date_for_input": date_for_input(raw_date),
        "category": row.get("category") or "",
        "amount": amount_val,
        "payment_method": row.get("payment_method") or "",
        "note": desc,
        "expense_type": row.get("expense_type") or "",
        "is_fixed": bool(row.get("is_fixed")) if "is_fixed" in row else False,
    }


def insert_expense(date, category, amount, payment_method, note, expense_type=None, is_fixed=False):
    """הכנסת הוצאה חדשה לטבלת expenses.

    note נכתב לעמודה description
    is_fixed נכתב לעמודה is_fixed
    expense_type נשמר בעמודה expense_type (טקסט) אם קיימת בטבלה.
    """
    url = SUPABASE_EXPENSES_URL
    payload = {
        "date": normalize_date(date),
        "category": category,
        "amount": parse_amount(amount),
        "payment_method": payment_method,
        "description": (note or "").strip(),
        "is_fixed": bool(is_fixed),
    }

    # שמירת סוג ההוצאה בעמודה החדשה
    if expense_type:
        payload["expense_type"] = expense_type
    else:
        payload["expense_type"] = None

    r = requests.post(url, headers=supabase_headers(), json=payload, timeout=20)
    r.raise_for_status()
    return r.json() if r.text else None


def update_expense(expense_id, date, category, amount, payment_method, note_text, expense_type=None, is_fixed=False):
    """עדכון הוצאה קיימת"""
    payload = {
        "date": normalize_date(date),
        "category": category,
        "amount": parse_amount(amount),
        "payment_method": payment_method,
        "description": (note_text or "").strip(),
    }

    if expense_type:
        payload["expense_type"] = expense_type
    else:
        payload["expense_type"] = None

    payload["is_fixed"] = bool(is_fixed)

    resp = requests.patch(
        SUPABASE_EXPENSES_URL,
        headers=supabase_headers(),
        params={"id": f"eq.{expense_id}"},
        json=payload,
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json() if resp.text else None


def delete_expense_record(expense_id):
    """מחיקת הוצאה לפי ID"""
    resp = requests.delete(
        SUPABASE_EXPENSES_URL,
        headers=supabase_headers(),
        params={"id": f"eq.{expense_id}"},
        timeout=10,
    )
    resp.raise_for_status()
    return True


# =========================
# תקציב חודשי
# =========================

def fetch_budgets_for_month(month):
    """שליפת כל התקציבים עבור חודש מסוים"""
    try:
        resp = requests.get(
            SUPABASE_BUDGETS_URL,
            headers=supabase_headers(),
            params={"select": "*", "month": f"eq.{month}"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            {
                "category": row.get("category", ""),
                "amount": float(row.get("amount") or 0),
                "previous_amount": float(row.get("previous_amount") or 0),
            }
            for row in data
        ]
    except Exception as e:
        print("שגיאה בשליפת תקציב:", e)
        return []


# =========================
# ראוטים
# =========================

@app.route("/")
def home_redirect():
    return redirect(url_for("expenses"))


# ------- הוצאות (רשימה) -------

@app.route("/expenses")
def expenses():
    expenses_raw = fetch_expenses()
    month = current_month()

    budgets = fetch_budgets_for_month(month)
    total_budget = sum(b["amount"] for b in budgets)

    # הוצאות חד פעמיות בלבד (לסוללה)
    spent_single = sum(e["amount"] for e in expenses_raw if not e["is_fixed"])

    battery_percent = 0
    if total_budget > 0:
        battery_percent = min(100, round((spent_single / total_budget) * 100, 1))

    # מיון לפי תאריך, מהחדש לישן
    expenses_sorted = sorted(
        expenses_raw,
        key=lambda e: datetime.strptime(e.get("date", "01/01/2000"), "%d/%m/%Y"),
        reverse=True,
    )

    amounts = [parse_amount(e.get("amount", 0)) for e in expenses_sorted]
    total_amount = sum(amounts)
    max_expense_amount = max(amounts) if amounts else 0

    # 3 קטגוריות מובילות
    category_map = {}
    for e in expenses_sorted:
        cat = e.get("category") or "לא מסווג"
        amt = parse_amount(e.get("amount", 0))
        category_map[cat] = category_map.get(cat, 0.0) + amt

    top_categories = []
    if total_amount > 0:
        sorted_items = sorted(category_map.items(), key=lambda x: x[1], reverse=True)
        for cat, amt in sorted_items[:3]:
            top_categories.append(
                {"category": cat, "amount": amt, "percent": (amt / total_amount) * 100}
            )

    return render_template(
        "expenses.html",
        expenses=expenses_sorted,
        total_amount=total_amount,
        max_expense_amount=max_expense_amount,
        top_categories=top_categories,
        total_budget=total_budget,
        spent_single=spent_single,
        battery_percent=battery_percent,
        active_tab="expenses",
    )


# ------- הוספת הוצאה -------

@app.route("/add", methods=["GET", "POST"])
def add_expense():
    if request.method == "POST":
        try:
            expense_type = request.form.get("expense_type", "single")
            note = request.form.get("note", "")
            is_fixed = bool(request.form.get("is_fixed"))

            insert_expense(
                request.form.get("date", ""),
                request.form.get("category", ""),
                request.form.get("amount", ""),
                request.form.get("payment_method", ""),
                note,
                expense_type,
                is_fixed,
            )
            return redirect(url_for("expenses"))
        except Exception as ex:
            print("❌ שגיאה בהוספה:", ex)
            flash(f"שגיאה בהוספה: {ex}", "error")

    return render_template(
        "add_expense.html",
        categories=CATEGORIES,
        payment_methods=PAYMENT_METHODS,
        active_tab="expenses",
        today=date.today().strftime("%Y-%m-%d"),
        error_message=None,
    )


# ------- עריכת הוצאה -------

@app.route("/edit/<int:expense_id>", methods=["GET", "POST"])
def edit_expense(expense_id):
    exp = get_expense_by_id(expense_id)
    if not exp:
        flash("הוצאה לא נמצאה", "error")
        return redirect(url_for("expenses"))

    if request.method == "POST":
        try:
            expense_type = request.form.get("expense_type", "")
            is_fixed = request.form.get("is_fixed") == "1"

            update_expense(
                expense_id,
                request.form.get("date", ""),
                request.form.get("category", ""),
                request.form.get("amount", ""),
                request.form.get("payment_method", ""),
                request.form.get("note", ""),
                expense_type,
                is_fixed,
            )
            return redirect(url_for("expenses"))
        except Exception as ex:
            print("❌ שגיאה בעדכון:", ex)
            flash(f"שגיאה בעדכון: {ex}", "error")

    return render_template(
        "edit_expense.html",
        expense=exp,
        categories=CATEGORIES,
        payment_methods=PAYMENT_METHODS,
        active_tab="expenses",
    )


# ------- מחיקת הוצאה -------

@app.route("/delete/<int:expense_id>", methods=["POST"])
def delete_expense(expense_id):
    try:
        delete_expense_record(expense_id)
    except Exception as e:
        print("❌ שגיאה במחיקת הוצאה:", e)
    return redirect(url_for("expenses"))


# ------- תקציב -------

@app.route("/budget", methods=["GET", "POST"])
def budget():
    month = request.args.get("month") or request.form.get("month") or current_month()

    # שליפת נתוני תקציב קיים
    try:
        resp = requests.get(
            SUPABASE_BUDGETS_URL,
            headers=supabase_headers(),
            params={"select": "*", "month": f"eq.{month}"},
            timeout=10,
        )
        resp.raise_for_status()
        budgets_data = resp.json()
    except Exception as e:
        print("שגיאה בשליפת תקציב:", e)
        budgets_data = []

    categories = [
        "מזון", "בריאות", "חינוך", "תחבורה", "בילויים",
        "ביגוד", "בית", "רכב", "ילדים", "חוגים",
        "קניות", "טבק", "שונות",
    ]

    existing_cats = {b["category"]: b for b in budgets_data}
    budgets = []
    for cat in categories:
        budgets.append({
            "category": cat,
            "amount": float(existing_cats.get(cat, {}).get("amount", 0) or 0),
            "previous_amount": float(existing_cats.get(cat, {}).get("previous_amount", 0) or 0),
        })

    if request.method == "POST":
        updates = []
        for cat in categories:
            amount_str = request.form.get(f"budget_{cat}", "0").strip()
            try:
                amount_val = float(amount_str) if amount_str else 0.0
            except ValueError:
                amount_val = 0.0

            updates.append({
                "month": month,
                "category": cat,
                "amount": amount_val,
            })

        # מוחקים את התקציב הישן לחודש
        try:
            requests.delete(
                SUPABASE_BUDGETS_URL,
                headers=supabase_headers(),
                params={"month": f"eq.{month}"},
                timeout=10,
            )
        except Exception as e:
            print("שגיאה במחיקת תקציב קודם:", e)

        # מוסיפים את כל הרשומות החדשות בבת אחת
        try:
            resp = requests.post(
                SUPABASE_BUDGETS_URL,
                headers=supabase_headers(),
                json=updates,
                timeout=20,
            )
            resp.raise_for_status()
        except Exception as e:
            print("שגיאה בעדכון תקציב:", e)

        return redirect(url_for("budget", month=month))

    total_budget = sum(b["amount"] for b in budgets)

    return render_template(
        "budget.html",
        budgets=budgets,
        month=month,
        active_tab="budget",
    )


# ------- דוחות -------

@app.route("/reports", methods=["GET"])
def reports():
    import re

    # חודשים אחרונים (שנה אחורה)
    today = date.today()
    months = []
    for i in range(12):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        months.append(f"{y}-{m:02d}")

    selected_month = request.args.get("month") or months[0]
    category_filter = request.args.get("category_filter", "")
    payment_filter = request.args.get("payment_filter", "")

    # תקציבים
    budgets = fetch_budgets_for_month(selected_month)
    budgets_map = {row["category"]: parse_amount(row["amount"]) for row in budgets}

    # הוצאות
    expenses_list = fetch_expenses()

    # סינון לפי חודש
    filtered_expenses = []
    year_int, month_int = map(int, selected_month.split("-"))
    for e in expenses_list:
        raw = e.get("raw_date") or e.get("date")
        if not raw:
            continue
        parsed_date = None
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                parsed_date = datetime.strptime(str(raw), fmt)
                break
            except ValueError:
                continue
        if parsed_date and parsed_date.year == year_int and parsed_date.month == month_int:
            e["_parsed_date"] = parsed_date
            filtered_expenses.append(e)

    def normalize(text):
        if not text:
            return ""
        return re.sub(r"[^א-תA-Za-z0-9]", "", str(text)).strip()

    # סינון קטגוריה
    if category_filter:
        norm_cat = normalize(category_filter)
        filtered_expenses = [
            e for e in filtered_expenses if normalize(e.get("category")) == norm_cat
        ]

    # סינון אמצעי תשלום
    if payment_filter:
        norm_pay = normalize(payment_filter)
        filtered_expenses = [
            e for e in filtered_expenses if normalize(e.get("payment_method")) == norm_pay
        ]

    # מיון טבלת "כל ההוצאות בחודש ..."
    filtered_expenses = sorted(
        filtered_expenses,
        key=lambda e: e.get("_parsed_date") or datetime(2000, 1, 1),
        reverse=False,
    )

    # סיכום לפי קטגוריות
    category_rows = []
    totals_by_cat = {}
    for e in filtered_expenses:
        cat = e.get("category") or "ללא קטגוריה"
        totals_by_cat[cat] = totals_by_cat.get(cat, 0) + e.get("amount", 0)
    for cat, spent in totals_by_cat.items():
        budget_val = budgets_map.get(cat, 0)
        category_rows.append({
            "category": cat,
            "spent": spent,
            "budget": budget_val,
            "diff": budget_val - spent,
        })

    # סיכום לפי אמצעי תשלום
    payment_rows = []
    totals_by_method = {}
    for e in filtered_expenses:
        method = e.get("payment_method") or "לא צוין"
        totals_by_method[method] = totals_by_method.get(method, 0) + e.get("amount", 0)
    for method, total in totals_by_method.items():
        payment_rows.append({"method": method, "total": total})

    # סיכום כללי
    total_budget = sum(budgets_map.values())
    total_spent = sum(e["amount"] for e in filtered_expenses)
    total_diff = total_budget - total_spent
    summary = {
        "total_budget": total_budget,
        "total_spent": total_spent,
        "total_diff": total_diff,
    }

    return render_template(
        "reports.html",
        months=months,
        selected_month=selected_month,
        category_filter=category_filter,
        payment_filter=payment_filter,
        categories=CATEGORIES,
        payment_methods=PAYMENT_METHODS,
        summary=summary,
        category_rows=category_rows,
        payment_rows=payment_rows,
        expenses=filtered_expenses,
        active_tab="reports",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
