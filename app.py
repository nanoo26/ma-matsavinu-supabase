from flask import Flask, render_template, request, redirect, url_for
import os
import requests
from datetime import datetime, date

def parse_amount(val) -> float:
    """קלט (עם פסיקים/רווחים) -> מספר float נקי."""
    try:
        return float(str(val).replace(",", "").strip())
    except Exception:
        return 0.0

app = Flask(__name__)

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
        "חסרים משתני סביבה SUPABASE_URL או SUPABASE_KEY. "
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
    }


# =========================
# קבועים - קטגוריות ותשלומים
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


# =========================
# פונקציות עזר לתאריכים
# =========================
def display_date(value: str) -> str:
    """תאריך לתצוגה: ממיר מ-yyyy-mm-dd ל-dd/mm/yyyy אם צריך."""
    if not value:
        return ""
    if "-" in value:
        parts = value.split("-")
        if len(parts) == 3:
            year, month, day = parts
            return f"{day}/{month}/{year}"
    return value


def date_for_input(db_value: str) -> str:
    """
    תאריך לשדה input type=date.
    אם בפורמט dd/mm/yyyy - יומר ל-yyyy-mm-dd.
    אם כבר yyyy-mm-dd - יוחזר כמו שהוא.
    """
    if not db_value:
        return ""
    if "-" in db_value:
        return db_value
    if "/" in db_value:
        parts = db_value.split("/")
        if len(parts) == 3:
            day, month, year = parts
            return f"{year}-{month}-{day}"
    return db_value


def current_month_key() -> str:
    """YYYY-MM של החודש הנוכחי."""
    today = date.today()
    return f"{today.year}-{today.month:02d}"


# =========================
# קריאות ל-Supabase - הוצאות
# =========================
def fetch_expenses():
    """שליפת כל ההוצאות מ-Supabase, ממויין לפי created_at מהחדש לישן."""
    try:
        resp = requests.get(
            SUPABASE_EXPENSES_URL,
            headers=supabase_headers(),
            params={
                "select": "*",
                "order": "created_at.desc",
            },
            timeout=10,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print("שגיאה בשליפת הוצאות מ-Supabase:", e)
        return []

    data = resp.json()
    expenses = []
    for row in data:
        amount_raw = row.get("amount")
        try:
            amount_val = float(amount_raw) if amount_raw not in (None, "") else 0.0
        except ValueError:
            amount_val = 0.0

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
            }
        )
    return expenses


def get_expense_by_id(expense_id: int):
    """שליפת הוצאה בודדת לפי מזהה."""
    try:
        resp = requests.get(
            SUPABASE_EXPENSES_URL,
            headers=supabase_headers(),
            params={
                "id": f"eq.{expense_id}",
                "select": "*",
            },
            timeout=10,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print("שגיאה בשליפת הוצאה בודדת מ-Supabase:", e)
        return None

    data = resp.json()
    if not data:
        return None

    row = data[0]
    raw_date = row.get("date") or ""
    amount_raw = row.get("amount")
    try:
        amount_val = float(amount_raw) if amount_raw not in (None, "") else 0.0
    except ValueError:
        amount_val = 0.0

    expense = {
        "id": row.get("id"),
        "raw_date": raw_date,
        "date_for_input": date_for_input(raw_date),
        "category": row.get("category") or "",
        "amount": amount_val,
        "payment_method": row.get("payment_method") or "",
        "notes": row.get("description") or "",
    }
    return expense


def insert_expense(payload: dict) -> bool:
    """הכנסת הוצאה חדשה ל-Supabase."""
    try:
        resp = requests.post(
            SUPABASE_EXPENSES_URL,
            headers=supabase_headers(),
            params={"select": "*"},
            json=payload,
            timeout=10,
        )
        if not resp.ok:
            print("=== Supabase INSERT ERROR ===")
            print("Status:", resp.status_code)
            try:
                print("Body:", resp.json())
            except Exception:
                print("Raw text:", resp.text)
            resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print("שגיאה בהוספת הוצאה ל-Supabase:", e)
        return False
    return True


def update_expense(expense_id: int, payload: dict) -> bool:
    """עדכון הוצאה קיימת ב-Supabase."""
    try:
        resp = requests.patch(
            SUPABASE_EXPENSES_URL,
            headers=supabase_headers(),
            params={"id": f"eq.{expense_id}"},
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print("שגיאה בעדכון הוצאה ב-Supabase:", e)
        return False
    return True


def delete_expense(expense_id: int) -> bool:
    """מחיקת הוצאה מ-Supabase."""
    try:
        resp = requests.delete(
            SUPABASE_EXPENSES_URL,
            headers=supabase_headers(),
            params={"id": f"eq.{expense_id}"},
            timeout=10,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print("שגיאה במחיקת הוצאה מ-Supabase:", e)
        return False
    return True


# =========================
# קריאות ל-Supabase - תקציבים
# =========================
def fetch_budgets_for_month(month_str: str):
    """מחזיר רשימת תקציבים לחודש מסוים, לפי טבלת budgets."""
    try:
        resp = requests.get(
            SUPABASE_BUDGETS_URL,
            headers=supabase_headers(),
            params={
                "select": "*",
                "month": f"eq.{month_str}",
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        print("שגיאה בשליפת תקציבים מ-Supabase:", e)
        return []


def save_budgets_for_month(month_str: str, rows: list[dict]) -> bool:
    """שומר תקציבים לחודש: מוחק קודמים ומכניס את החדשים."""
    # מחיקת התקציבים הקיימים לחודש
    try:
        delete_resp = requests.delete(
            SUPABASE_BUDGETS_URL,
            headers=supabase_headers(),
            params={"month": f"eq.{month_str}"},
            timeout=10,
        )
        delete_resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print("שגיאה במחיקת תקציבים קיימים:", e)
        return False

    # הוספת השורות החדשות
    if not rows:
        return True

    try:
        insert_resp = requests.post(
            SUPABASE_BUDGETS_URL,
            headers=supabase_headers(),
            json=rows,
            timeout=10,
        )
        insert_resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print("שגיאה בעדכון תקציבים:", e)
        return False

    return True


# =========================
# ראוטים
# =========================
@app.route("/")
def root():
    return redirect(url_for("expenses"))


@app.route("/expenses")
def expenses():
    # מביא את כל ההוצאות מה-Supabase
    expenses_raw = fetch_expenses()

    # מיון מהחדש לישן לפי תאריך DD/MM/YYYY
    def to_dt(e):
        try:
            return datetime.strptime(e.get("date", ""), "%d/%m/%Y")
        except Exception:
            return datetime.min

    expenses_sorted = sorted(expenses_raw, key=to_dt, reverse=True)

    # סכום כולל של כל ההוצאות
    total_amount = sum(
        parse_amount(e.get("amount", 0)) for e in expenses_sorted
    )

    # כרטיס סיכום עליון
    main_summary = {
        "month_key": current_month_key(),
        "spent_total": total_amount,
        "used_percent": 0,
    }

    return render_template(
        "expenses.html",
        expenses=expenses_sorted,
        main_summary=main_summary,
        total_amount=total_amount,
        active_tab="expenses",
    )




@app.route("/add", methods=["GET", "POST"])
def add_expense():
    if request.method == "POST":
        date_str = request.form.get("date", "").strip()
        category = request.form.get("category", "").strip()
        amount_str = request.form.get("amount", "").strip()
        payment_method = request.form.get("payment_method", "").strip()
        notes = request.form.get("notes", "").strip()

        try:
            amount_val = float(amount_str) if amount_str else 0.0
        except ValueError:
            amount_val = 0.0

        payload = {
            "date": date_str,
            "category": category,
            "amount": amount_val,
            "payment_method": payment_method,
            "description": notes,
        }

        ok = insert_expense(payload)
        if ok:
            return redirect(url_for("expenses"))
        else:
            return render_template(
                "add_expense.html",
                categories=CATEGORIES,
                payment_methods=PAYMENT_METHODS,
                today=date_str or date.today().isoformat(),
                error_message="אירעה שגיאה בשמירת ההוצאה. נסה שוב.",
            )

    # GET
    today_str = date.today().isoformat()
    return render_template(
        "add_expense.html",
        categories=CATEGORIES,
        payment_methods=PAYMENT_METHODS,
        today=today_str,
        error_message=None,
    )


@app.route("/edit/<int:expense_id>", methods=["GET", "POST"])
def edit_expense_view(expense_id):
    if request.method == "POST":
        date_str = request.form.get("date", "").strip()
        category = request.form.get("category", "").strip()
        amount_str = request.form.get("amount", "").strip()
        payment_method = request.form.get("payment_method", "").strip()
        notes = request.form.get("notes", "").strip()

        try:
            amount_val = float(amount_str) if amount_str else 0.0
        except ValueError:
            amount_val = 0.0

        payload = {
            "date": date_str,
            "category": category,
            "amount": amount_val,
            "payment_method": payment_method,
            "description": notes,
        }

        ok = update_expense(expense_id, payload)
        if ok:
            return redirect(url_for("expenses"))
        else:
            expense = get_expense_by_id(expense_id)
            if not expense:
                return redirect(url_for("expenses"))
            return render_template(
                "edit_expense.html",
                expense=expense,
                categories=CATEGORIES,
                payment_methods=PAYMENT_METHODS,
                error_message="אירעה שגיאה בעדכון ההוצאה. נסה שוב.",
            )

    # GET
    expense = get_expense_by_id(expense_id)
    if not expense:
        return redirect(url_for("expenses"))

    return render_template(
        "edit_expense.html",
        expense=expense,
        categories=CATEGORIES,
        payment_methods=PAYMENT_METHODS,
        error_message=None,
    )


@app.route("/delete/<int:expense_id>", methods=["POST"])
def delete_expense_view(expense_id):
    delete_expense(expense_id)
    return redirect(url_for("expenses"))


@app.route("/reports")
def reports():
    # כל ההוצאות הקיימות (כמו למסך הראשי)
    expenses = fetch_expenses()

    # פונקציה שמחזירה מפתח חודש בפורמט YYYY-MM מתוך תאריך DD/MM/YYYY
    def month_key(date_str: str) -> str:
        try:
            dt = datetime.strptime(date_str, "%d/%m/%Y")
            return dt.strftime("%Y-%m")
        except Exception:
            return ""

    # כל החודשים שקיימים בנתונים
    month_set = set()
    for e in expenses:
        mk = month_key(e.get("date", ""))
        if mk:
            month_set.add(mk)
    months = sorted(month_set, reverse=True)

    # חודש ברירת מחדל
    if months:
        default_month = months[0]
    else:
        default_month = datetime.now().strftime("%Y-%m")

    # מה שנבחר ב־URL או ברירת המחדל
    selected_month = request.args.get("month") or default_month

    # סינון הוצאות לחודש הנבחר
    month_expenses = [
        e for e in expenses
        if month_key(e.get("date", "")) == selected_month
    ]

    # --- תקציבים לחודש הנבחר מטבלת budgets ---
    budgets_rows = fetch_budgets_for_month(selected_month)
    budgets_map = {
        row.get("category"): parse_amount(row.get("amount", 0))
        for row in budgets_rows
    }

    # סיכום הוצאות לפי קטגוריות
    category_totals = {}
    for e in month_expenses:
        cat = e.get("category") or "לא מסווג"
        amt = parse_amount(e.get("amount", 0))
        category_totals[cat] = category_totals.get(cat, 0.0) + amt

    category_rows = []
    total_spent = 0.0
    total_budget = 0.0

    for cat, spent in category_totals.items():
        budget = budgets_map.get(cat, 0.0)
        diff = budget - spent
        percent = (spent / budget * 100) if budget > 0 else 0.0

        total_spent += spent
        total_budget += budget

        category_rows.append(
            {
                "category": cat,
                "budget": budget,
                "spent": spent,
                "diff": diff,
                "percent": percent,
            }
        )

    # אם יש קטגוריות עם תקציב אבל בלי הוצאות - נוסיף גם אותן
    for cat, budget in budgets_map.items():
        if cat not in category_totals:
            total_budget += budget
            category_rows.append(
                {
                    "category": cat,
                    "budget": budget,
                    "spent": 0.0,
                    "diff": budget,
                    "percent": 0.0,
                }
            )

    # סיכום עליון
    total_diff = total_budget - total_spent
    total_percent = (total_spent / total_budget * 100) if total_budget > 0 else 0.0

    summary = {
        "total_budget": total_budget,   # זה מה שמופיע ב"תקציב חודשי"
        "total_spent": total_spent,
        "total_diff": total_diff,
        "total_percent": total_percent,
    }

    # סיכום לפי אמצעי תשלום
    payments_map = {}
    for e in month_expenses:
        pm = e.get("payment_method") or "לא ידוע"
        amt = parse_amount(e.get("amount", 0))
        payments_map[pm] = payments_map.get(pm, 0.0) + amt

    payment_rows = [
        {"method": m, "total": t} for m, t in payments_map.items()
    ]

    # רשימת הוצאות למסך הדוחות
    report_expenses = []
    for e in month_expenses:
        report_expenses.append(
            {
                "date": e.get("date", ""),
                "category": e.get("category", ""),
                "note": (e.get("notes") or e.get("note") or ""),
                "payment_method": e.get("payment_method", ""),
                "amount": parse_amount(e.get("amount", 0)),
            }
        )

    if not months:
        months = [selected_month]

    return render_template(
    "reports.html",
    months=months,
    selected_month=selected_month,
    summary=summary,
    category_rows=category_rows,
    payment_rows=payment_rows,
    expenses=report_expenses,
    active_tab="reports",
)




@app.route("/budget", methods=["GET", "POST"])
def budget():
    """מסך עריכת תקציב חודשי על בסיס טבלת budgets."""
    month_from_query = request.args.get("month")
    month_hidden = request.form.get("month") if request.method == "POST" else None
    selected_month = month_from_query or month_hidden or current_month_key()

    if request.method == "POST":
        # קריאת תקציב מכל שורה בטופס
        rows = []
        for cat in CATEGORIES:
            field_name = f"budget_{cat}"
            val_str = request.form.get(field_name, "").strip()
            amount_val = parse_amount(val_str) if val_str else 0.0
            rows.append(
                {
                    "month": selected_month,
                    "category": cat,
                    "amount": amount_val,
                }
            )

        ok = save_budgets_for_month(selected_month, rows)
        if ok:
            return redirect(url_for("budget", month=selected_month))

    # GET - טוען תקציבים לחודש
    existing = fetch_budgets_for_month(selected_month)
    existing_map = {
        row.get("category"): float(row.get("amount") or 0)
        for row in existing
    }

    budgets_for_template = []
    for cat in CATEGORIES:
        budgets_for_template.append(
            {
                "category": cat,
                "amount": existing_map.get(cat, 0.0),
            }
        )

    return render_template(
    "budget.html",
    month=selected_month,
    budgets=budgets_for_template,
    active_tab="budget",
)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
