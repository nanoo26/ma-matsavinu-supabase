import os
import requests
from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import datetime, date
from calendar import monthrange


now = datetime.now()

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
    # אם בפורמט DD/MM/YY
    try:
        dt = datetime.strptime(s, "%d/%m/%y")
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
    # מאחסון DD/MM/YY
    try:
        dt = datetime.strptime(s, "%d/%m/%y")
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


def add_months(src_date: date, months: int) -> date:
    """הוספת מספר חודשים לתאריך נתון (אם נרצה בעתיד לתמרן תאריכים)"""
    month = src_date.month - 1 + months
    year = src_date.year + month // 12
    month = month % 12 + 1
    day = min(src_date.day, monthrange(year, month)[1])
    return date(year, month, day)


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


def current_month() -> str:
    """החודש הנוכחי בפורמט YYYY-MM - לשימוש במסך ההוצאות"""
    return date.today().strftime("%Y-%m")


# =========================
# Supabase config
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
SUPABASE_PAYMENT_PLANS_URL = f"{SUPABASE_URL}/rest/v1/{PAYMENT_PLANS_TABLE}"


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
                "order": "created_at.desc",
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


# =========================
# payment_plans helpers
# =========================

def get_payment_plan_for_expense(expense_id: int):
    """שליפה של תכנית תשלומים להוצאה מסוימת (אם קיימת)."""
    try:
        resp = requests.get(
            SUPABASE_PAYMENT_PLANS_URL,
            headers=supabase_headers(),
            params={
                "select": "*",
                "expense_id": f"eq.{expense_id}",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return None
        plan = data[0]

        installments = (
            plan.get("installments_count")
            or plan.get("num_payments")
            or plan.get("total_payments")
            or 0
        )
        try:
            installments = int(installments or 0)
        except ValueError:
            installments = 0

        plan["installments_count"] = installments
        return plan
    except Exception as e:
        print("שגיאה בשליפת תכנית תשלומים:", e)
        return None


def fetch_payment_plans_map():
    """
    שליפה של כל תכניות התשלומים במכה אחת.
    מחזיר dict מהצורה:
    { expense_id: { "installments_count": int, "payment_amount": float, "total_amount": float } }
    """
    try:
        resp = requests.get(
            SUPABASE_PAYMENT_PLANS_URL,
            headers=supabase_headers(),
            params={"select": "*"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print("שגיאה בשליפת כל תכניות התשלומים:", e)
        return {}

    plans = {}
    for row in data:
        exp_id = row.get("expense_id")
        if exp_id is None:
            continue

        # ספירת תשלומים
        installments = (
            row.get("installments_count")
            or row.get("num_payments")
            or row.get("total_payments")
            or 0
        )
        try:
            installments = int(installments or 0)
        except ValueError:
            installments = 0

        # סכום חודשי
        payment_amount = row.get("payment_amount")
        try:
            payment_amount = float(payment_amount) if payment_amount is not None else 0.0
        except ValueError:
            payment_amount = 0.0

        total_amount = row.get("total_amount")
        try:
            total_amount = float(total_amount) if total_amount is not None else 0.0
        except ValueError:
            total_amount = 0.0

        plans[int(exp_id)] = {
            "installments_count": installments,
            "payment_amount": payment_amount,
            "total_amount": total_amount,
        }

    return plans


def upsert_payment_plan(expense_id: int, total_amount: float, installments_count: int, payment_method: str = ""):
    """
    יצירה או עדכון של תכנית תשלומים בטבלת payment_plans.
    """
    try:
        if installments_count <= 1:
            # מחיקה אם קיימת תכנית
            requests.delete(
                SUPABASE_PAYMENT_PLANS_URL,
                headers=supabase_headers(),
                params={"expense_id": f"eq.{expense_id}"},
                timeout=10,
            )
            return

        monthly_amount = round(float(total_amount) / installments_count, 2) if installments_count > 0 else 0.0

        existing = get_payment_plan_for_expense(expense_id)

        payload = {
            "expense_id": expense_id,
            "total_amount": float(total_amount),
            "num_payments": int(installments_count),
            "payment_amount": monthly_amount,
            "payment_method": payment_method or None,  # 👈 כאן התיקון
            "is_active": True
        }

        if existing:
            resp = requests.patch(
                SUPABASE_PAYMENT_PLANS_URL,
                headers=supabase_headers(),
                params={"expense_id": f"eq.{expense_id}"},
                json=payload,
                timeout=20,
            )
        else:
            resp = requests.post(
                SUPABASE_PAYMENT_PLANS_URL,
                headers=supabase_headers(),
                json=payload,
                timeout=20,
            )

        if not resp.ok:
            print("שגיאה בעדכון תכנית תשלומים ב-Supabase:")
            print("סטטוס:", resp.status_code)
            print("תוכן:", resp.text)

    except Exception as e:
        print("שגיאה בטיפול בתכנית תשלומים:", e)


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
# שליפת הוצאה בודדת (לטפסי עריכה)
# =========================

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

    exp = {
        "id": row.get("id"),
        "date": display_date(raw_date),
        "date_for_input": date_for_input(raw_date),
        "category": row.get("category") or "",
        "amount": amount_val,
        "payment_method": row.get("payment_method") or "",
        "note": desc,
        "expense_type": row.get("expense_type") or "",
        "is_fixed": bool(row.get("is_fixed")) if "is_fixed" in row else False,
        "installments_count": 0,
    }

    # אם יש תכנית תשלומים - נוסיף את ספירת התשלומים
    plan = get_payment_plan_for_expense(expense_id)
    if plan:
        exp["installments_count"] = plan.get("installments_count", 0)

    return exp


# =========================
# CRUD ליצירה/עדכון הוצאה
# =========================

def insert_expense(date_str, category, amount, payment_method, note, expense_type=None, is_fixed=False):
    """הכנסת הוצאה חדשה לטבלת expenses."""
    payload = {
        "date": normalize_date(date_str),
        "category": category,
        "amount": parse_amount(amount),
        "payment_method": payment_method,
        "description": (note or "").strip(),
        "is_fixed": bool(is_fixed),
    }

    if expense_type:
        payload["expense_type"] = expense_type

    headers = supabase_headers().copy()
    headers["Prefer"] = "return=representation"

    resp = requests.post(
        SUPABASE_EXPENSES_URL,
        headers=headers,
        json=payload,
        timeout=20,
    )

    if not resp.ok:
        print("❌ שגיאה בהוספת הוצאה ל-Supabase:")
        print("סטטוס:", resp.status_code)
        print("תוכן:", resp.text)
        resp.raise_for_status()

    return resp.json()


def update_expense(expense_id, date_str, category, amount, payment_method, note_text, expense_type=None, is_fixed=False):
    """עדכון הוצאה קיימת בטבלת expenses."""
    payload = {
        "date": normalize_date(date_str),
        "category": category,
        "amount": parse_amount(amount),
        "payment_method": payment_method,
        "description": (note_text or "").strip(),
        "is_fixed": bool(is_fixed),
    }

    if expense_type:
        payload["expense_type"] = expense_type
    else:
        payload["expense_type"] = None

    resp = requests.patch(
        SUPABASE_EXPENSES_URL,
        headers=supabase_headers(),
        params={"id": f"eq.{expense_id}"},
        json=payload,
        timeout=20,
    )

    if not resp.ok:
        print("❌ שגיאה בעדכון הוצאה ב-Supabase:")
        print("סטטוס:", resp.status_code)
        print("תוכן:", resp.text)
        resp.raise_for_status()

    return True


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
# ראוטים
# =========================

@app.route("/")
def home_redirect():
    return redirect(url_for("expenses"))


# ------- הוצאות (רשימה) -------

@app.route("/expenses")
def expenses():
    expenses_raw = fetch_expenses()

    # חודש נוכחי עבור תקציב
    month = current_month()

    # תאריך נוכחי לחישוב באיזה תשלום אנחנו נמצאים
    today_date = date.today()
    year_int = today_date.year
    month_int = today_date.month

    # ננסה לפרש תאריך לכל הוצאה
    enriched = []
    for e in expenses_raw:
        raw = e.get("raw_date") or e.get("date")
        parsed_date = None
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d/%m/%y"):
            try:
                parsed_date = datetime.strptime(str(raw), fmt)
                break
            except ValueError:
                continue

        # ניסיון אחרון ל-DD/MM/YY
        if parsed_date is None and raw:
            s = str(raw)
            parts = s.split("/")
            if len(parts) == 3 and len(parts[2]) == 2:
                try:
                    d, m, y = parts
                    y_full = 2000 + int(y)
                    parsed_date = datetime(year=y_full, month=int(m), day=int(d))
                except Exception:
                    parsed_date = None

        if parsed_date:
            e["_parsed_date"] = parsed_date

        enriched.append(e)

    # כל תכניות התשלומים
    plans_map = fetch_payment_plans_map()

    # התאמת הסכומים לפי תכניות תשלומים לחודש הנוכחי
    adjusted_expenses = []
    for e in enriched:
        exp_id = e.get("id")
        plan = plans_map.get(int(exp_id)) if exp_id else None

        if not plan:
            adjusted_expenses.append(e)
            continue

        num_payments = plan.get("installments_count", 0)
        if num_payments <= 1:
            adjusted_expenses.append(e)
            continue

        start_dt = e.get("_parsed_date")
        if not start_dt:
            adjusted_expenses.append(e)
            continue

        # כמה חודשים עברו מאז תחילת הפריסה ועד החודש הנוכחי
        months_diff = (year_int - start_dt.year) * 12 + (month_int - start_dt.month)

        # לפני תחילת פריסה או אחרי סיום - לא מציגים בכלל
        if months_diff < 0 or months_diff >= num_payments:
            continue

        current_installment = months_diff + 1

        # סכום חודשי
        monthly_amount = plan.get("payment_amount") or 0
        try:
            monthly_amount = float(monthly_amount)
        except ValueError:
            monthly_amount = 0.0

        if monthly_amount <= 0:
            total_amount = plan.get("total_amount") or 0
            try:
                total_amount = float(total_amount)
            except ValueError:
                total_amount = 0.0
            monthly_amount = round(total_amount / num_payments, 2) if num_payments > 0 else 0.0

        new_e = e.copy()
        new_e["amount"] = monthly_amount
        new_e["current_installment"] = current_installment
        new_e["total_installments"] = num_payments
        adjusted_expenses.append(new_e)

    # מכאן עובדים רק עם הרשימה המעודכנת
    expenses_for_view = adjusted_expenses

    # תקציב לחודש הנוכחי
    budgets = fetch_budgets_for_month(month)
    total_budget = sum(b["amount"] for b in budgets)

    # הוצאות חד פעמיות בלבד (לסוללה), כולל רכישות בתשלומים לפי סכום חודשי
    spent_single = sum(e["amount"] for e in expenses_for_view if not e["is_fixed"])

    battery_percent = 0
    if total_budget > 0:
        battery_percent = min(100, round((spent_single / total_budget) * 100, 1))

    # מיון לפי תאריך, מהחדש לישן
    expenses_sorted = sorted(
        expenses_for_view,
        key=lambda e: e.get("_parsed_date") or datetime.strptime(e.get("date", "01/01/2000"), "%d/%m/%Y"),
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
            expense_type = request.form.get("expense_type", "חד פעמית")
            note = request.form.get("note", "")
            is_fixed = bool(request.form.get("is_fixed"))
            installments_count = int(request.form.get("installments_count", "0") or 0)
            amount_str = request.form.get("amount", "0")

            inserted = insert_expense(
                request.form.get("date", ""),
                request.form.get("category", ""),
                amount_str,
                request.form.get("payment_method", ""),
                note,
                expense_type,
                is_fixed,
            )

            # אם זו רכישה בתשלומים - יוצרים תכנית תשלומים
            if expense_type == "רכישה בתשלומים" and installments_count > 1 and inserted:
                if isinstance(inserted, list) and inserted:
                    expense_id = inserted[0].get("id")
                elif isinstance(inserted, dict):
                    expense_id = inserted.get("id")
                else:
                    expense_id = None

                if expense_id:
                    upsert_payment_plan(
                        expense_id=int(expense_id),
                        total_amount=parse_amount(amount_str),
                        installments_count=installments_count,
                        payment_method=request.form.get("payment_method", "")
                    )


            print("📦 DEBUG add_expense:",
            "type:", expense_type,
            "installments:", installments_count)


            return redirect(url_for("expenses"))
        except Exception as ex:
            print("❌ שגיאה בהוספת הוצאה:", ex)
            flash(f"שגיאה בהוספת הוצאה: {ex}", "error")

    return render_template(
        "add_expense.html",
        categories=CATEGORIES,
        payment_methods=PAYMENT_METHODS,
        active_tab="expenses",
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
            installments_count = int(request.form.get("installments_count", "0") or 0)
            amount_str = request.form.get("amount", "0")

            # עדכון ההוצאה עצמה
            update_expense(
                expense_id,
                request.form.get("date", ""),
                request.form.get("category", ""),
                amount_str,
                request.form.get("payment_method", ""),
                request.form.get("note", ""),
                expense_type,
                is_fixed,
            )

            # טיפול בתכנית תשלומים
            if expense_type == "רכישה בתשלומים":
                  upsert_payment_plan(
                  expense_id=int(expense_id),
                  total_amount=parse_amount(amount_str),
                  installments_count=installments_count,
                  payment_method=request.form.get("payment_method", "")  # 👈 חדש
        )

            else:
                # אם כבר לא תשלומים - מוחקים את התכנית
                  upsert_payment_plan(
                    expense_id=expense_id,
                    total_amount=0,
                    installments_count=1,
                )

            return redirect(url_for("expenses"))
        except Exception as ex:
            print("❌ שגיאה בעדכון הוצאה:", ex)
            flash(f"שגיאה בעדכון הוצאה: {ex}", "error")

    return render_template(
        "edit_expense.html",
        expense=exp,
        categories=CATEGORIES,
        payment_methods=PAYMENT_METHODS,
        active_tab="expenses",
    )


# ------- מחיקת הוצאה מרובה -------

@app.route("/delete-selected", methods=["POST"])
def delete_selected():
    """מחיקת מספר הוצאות שנבחרו בצ'קבוקסים."""
    ids = request.form.getlist("selected_ids")

    if not ids:
        return redirect(url_for("expenses"))

    for id_str in ids:
        try:
            expense_id = int(id_str)
        except ValueError:
            continue

        try:
            delete_expense_record(expense_id)
        except Exception as e:
            print(f"❌ שגיאה במחיקת הוצאה {expense_id}:", e)

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

    # ✅ נוספה קטגוריה חדשה בראש הרשימה
    categories = [
        "💰 הכנסות",
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

        # טיפול בהכנסות בנפרד
            income_str = request.form.get("income", "0").strip()
            try:
                income_val = float(income_str) if income_str else 0.0
            except ValueError:
                income_val = 0.0

            updates = [{
                "month": month,
                "category": "הכנסות",
                "amount": income_val
            }]


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
    from datetime import timedelta

    # ---------------------------------------------------------
    # פונקציה לחישוב חודש פיננסי מה-10 לחודש עד ה-9 לחודש הבא
    # ---------------------------------------------------------
    def get_custom_month_range(reference_date=None):
        if not reference_date:
            reference_date = date.today()
        if reference_date.day < 10:
            if reference_date.month == 1:
                start_month = 12
                start_year = reference_date.year - 1
            else:
                start_month = reference_date.month - 1
                start_year = reference_date.year
        else:
            start_month = reference_date.month
            start_year = reference_date.year

        start_date = date(start_year, start_month, 10)
        if start_month == 12:
            end_date = date(start_year + 1, 1, 9)
        else:
            end_date = date(start_year, start_month + 1, 9)
        return start_date, end_date

    # ---------------------------------------------------------
    # יצירת רשימת חודשים אחרונים
    # ---------------------------------------------------------
    today = date.today()
    months = []
    for i in range(12):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        months.append(f"{y}-{m:02d}")

    # ---------------------------------------------------------
    # קריאת פרמטרים מה-URL (אם המשתמש בחר פילטרים)
    # ---------------------------------------------------------
    selected_month = request.args.get("month") or months[0]
    category_filter = request.args.get("category_filter", "")
    payment_filter = request.args.get("payment_filter", "")
    expense_type = request.args.get("expense_type", "")

    # ---------------------------------------------------------
    # טווח החודש הפיננסי ונתונים מה-DB
    # ---------------------------------------------------------
    start_date, end_date = get_custom_month_range()
    budgets = fetch_budgets_for_month(selected_month)
    expenses = fetch_expenses()


    # ---------------------------------------------------------
    # נתוני שליפה
    # ---------------------------------------------------------
    selected_month = request.args.get("month") or current_month()
    start_date, end_date = get_custom_month_range()
    budgets = fetch_budgets_for_month(selected_month)
    expenses = fetch_expenses()

    budgets_map = {b["category"]: parse_amount(b["amount"]) for b in budgets}

    # ---------------------------------------------------------
    # חישובי תקציב והוצאות
    # ---------------------------------------------------------
    total_budget = sum(budgets_map.values())
    total_spent = sum(e["amount"] for e in expenses)
    total_diff = total_budget - total_spent

    # ✅ הוספת חישובי הכנסות ותקציב למותרות — בלי לשנות מבנה!
    total_income = budgets_map.get("💰 הכנסות", 0) or budgets_map.get("הכנסות", 0)
    total_fixed = sum(e["amount"] for e in expenses if e.get("is_fixed"))
    total_optional = total_spent - total_fixed
    luxury_budget = total_income - total_fixed
    luxury_diff = luxury_budget - total_optional

    # ---------------------------------------------------------
    # מילון summary נשאר זהה למבנה הישן
    # ---------------------------------------------------------
    summary = {
        "total_budget": total_budget,
        "total_spent": total_spent,
        "total_diff": total_diff,
        "total_income": total_income,
        "total_fixed": total_fixed,
        "luxury_budget": luxury_budget,
        "luxury_diff": luxury_diff,
    }

    # ---------------------------------------------------------
    # חישובים וסיכומים
    # ---------------------------------------------------------
    filtered_expenses = sorted(
        expenses,
        key=lambda e: e.get("_parsed_date") if "_parsed_date" in e else datetime(2000, 1, 1),
        reverse=False,
    )

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

    payment_rows = []
    totals_by_method = {}
    for e in filtered_expenses:
        method = e.get("payment_method") or "לא צוין"
        totals_by_method[method] = totals_by_method.get(method, 0) + e.get("amount", 0)
    for method, total in totals_by_method.items():
        payment_rows.append({"method": method, "total": total})

    return render_template(
        "reports.html",
        months=months,
        selected_month=selected_month,
        category_filter=category_filter,
        payment_filter=payment_filter,
        expense_type=expense_type,
        categories=CATEGORIES,
        payment_methods=PAYMENT_METHODS,
        budgets=budgets,
        expenses=filtered_expenses,
        summary=summary,
        category_rows=category_rows,
        payment_rows=payment_rows,
        active_tab="reports",
        now=now,
    )


@app.route("/reports_old", methods=["GET"])
def reports_old():
    import re
    from datetime import timedelta

    # ---------------------------------------------------------
    # פונקציה לחישוב חודש פיננסי מה-10 לחודש עד ה-9 לחודש הבא
    # ---------------------------------------------------------
    def get_custom_month_range(reference_date=None):
        if not reference_date:
            reference_date = date.today()
        if reference_date.day < 10:
            if reference_date.month == 1:
                start_month = 12
                start_year = reference_date.year - 1
            else:
                start_month = reference_date.month - 1
                start_year = reference_date.year
        else:
            start_month = reference_date.month
            start_year = reference_date.year

        start_date = date(start_year, start_month, 10)
        if start_month == 12:
            end_date = date(start_year + 1, 1, 9)
        else:
            end_date = date(start_year, start_month + 1, 9)
        return start_date, end_date

    # ---------------------------------------------------------
    # הגדרות וסינונים
    # ---------------------------------------------------------
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
    expense_type = request.args.get("expense_type", "")

    start_date, end_date = get_custom_month_range()

    # ---------------------------------------------------------
    # שליפת נתונים
    # ---------------------------------------------------------
    budgets = fetch_budgets_for_month(selected_month)
    budgets_map = {row["category"]: parse_amount(row["amount"]) for row in budgets}
    expenses_list = fetch_expenses()

    # ---------------------------------------------------------
    # סינון הוצאות לפי תאריך בטווח החודש הפיננסי
    # ---------------------------------------------------------
    filtered_expenses = []
    for e in expenses_list:
        raw = e.get("raw_date") or e.get("date")
        if not raw:
            continue
        parsed_date = None
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d/%m/%y"):
            try:
                parsed_date = datetime.strptime(str(raw), fmt)
                break
            except ValueError:
                continue
        if parsed_date is None:
            s = str(raw)
            parts = s.split("/")
            if len(parts) == 3 and len(parts[2]) == 2:
                try:
                    d, m, y = parts
                    y_full = 2000 + int(y)
                    parsed_date = datetime(year=y_full, month=int(m), day=int(d))
                except Exception:
                    parsed_date = None

        # טווח תאריכים לפי 10 לחודש עד 9 לחודש הבא
        if parsed_date and start_date <= parsed_date.date() <= end_date:
            e["_parsed_date"] = parsed_date
            filtered_expenses.append(e)

    
    # ---------------------------------------------------------
    # טיפול בתשלומים
    # ---------------------------------------------------------
    def normalize(text):
        if not text:
            return ""
        return re.sub(r"[^א-תA-Za-z0-9]", "", str(text)).strip()
    
    plans_map = fetch_payment_plans_map()
    adjusted_expenses = []
    for e in filtered_expenses:
        exp_id = e.get("id")
        if not exp_id:
            adjusted_expenses.append(e)
            continue
        plan = plans_map.get(int(exp_id))
        if not plan:
            adjusted_expenses.append(e)
            continue
        num_payments = plan.get("installments_count", 0)
        if num_payments <= 1:
            adjusted_expenses.append(e)
            continue

        start_dt = e.get("_parsed_date")
        if not start_dt:
            adjusted_expenses.append(e)
            continue

        months_diff = (today.year - start_dt.year) * 12 + (today.month - start_dt.month)
        if months_diff < 0 or months_diff >= num_payments:
            continue

        monthly_amount = plan.get("payment_amount") or 0
        try:
            monthly_amount = float(monthly_amount)
        except ValueError:
            monthly_amount = 0.0

        if monthly_amount <= 0:
            total_amount = plan.get("total_amount") or 0
            try:
                total_amount = float(total_amount)
            except ValueError:
                total_amount = 0.0
            monthly_amount = round(total_amount / num_payments, 2) if num_payments > 0 else 0.0

        e = e.copy()
        e["amount"] = monthly_amount
        e["current_installment"] = months_diff + 1
        e["total_installments"] = num_payments
        adjusted_expenses.append(e)

    filtered_expenses = adjusted_expenses

    # ---------------------------------------------------------
    # סינון לפי קטגוריה / אמצעי תשלום / סוג הוצאה
    # ---------------------------------------------------------
    if category_filter:
        norm_cat = normalize(category_filter)
        filtered_expenses = [
            e for e in filtered_expenses if normalize(e.get("category")) == norm_cat
        ]

    if payment_filter:
        norm_pay = normalize(payment_filter)
        filtered_expenses = [
            e for e in filtered_expenses if normalize(e.get("payment_method")) == norm_pay
        ]

    if expense_type:
        filtered_expenses = [
            e for e in filtered_expenses if e.get("expense_type") == expense_type
        ]

    # ---------------------------------------------------------
    # חישובים וסיכומים
    # ---------------------------------------------------------
    filtered_expenses = sorted(
        filtered_expenses,
        key=lambda e: e.get("_parsed_date") or datetime(2000, 1, 1),
        reverse=False,
    )

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

    payment_rows = []
    totals_by_method = {}
    for e in filtered_expenses:
        method = e.get("payment_method") or "לא צוין"
        totals_by_method[method] = totals_by_method.get(method, 0) + e.get("amount", 0)
    for method, total in totals_by_method.items():
        payment_rows.append({"method": method, "total": total})

    total_budget = sum(budgets_map.values())
    total_spent = sum(e["amount"] for e in filtered_expenses)
    total_diff = total_budget - total_spent
    summary = {
        "total_budget": total_budget,
        "total_spent": total_spent,
        "total_diff": total_diff,
    }

    # ---------------------------------------------------------
    # תצוגה
    # ---------------------------------------------------------
    return render_template(
        "reports.html",
        months=months,
        selected_month=selected_month,
        category_filter=category_filter,
        payment_filter=payment_filter,
        expense_type=expense_type,
        categories=CATEGORIES,
        payment_methods=PAYMENT_METHODS,
        summary=summary,
        category_rows=category_rows,
        payment_rows=payment_rows,
        expenses=filtered_expenses,
        active_tab="reports",
        now=now,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
