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


def financial_label_for_date(d: date):
    """
    מחזיר 'חודש פיננסי' עבור תאריך:
    10 בחודש עד 9 בחודש הבא שייך לחודש של היום ה־10.
    לדוגמה:
    - 07/11 -> שייך לאוקטובר (2025-10)
    - 15/11 -> שייך לנובמבר (2025-11)
    """
    if d.day >= 10:
        return d.year, d.month
    # ימים 1–9 שייכים לחודש הקודם
    if d.month == 1:
        return d.year - 1, 12
    return d.year, d.month - 1


def current_month() -> str:
    """
    מחזיר את החודש הפיננסי הנוכחי בפורמט YYYY-MM,
    לפי כלל 10 בחודש עד 9 בחודש הבא.
    """
    today = date.today()
    y, m = financial_label_for_date(today)
    return f"{y}-{m:02d}"


def financial_range_for_month(month_str: str):
    """
    מקבל מחרוזת חודש פיננסי 'YYYY-MM' ומחזיר טווח תאריכים:
    start_date = 10 בחודש
    end_date   = 9 בחודש הבא
    """
    y, m = map(int, month_str.split("-"))
    start_date = date(y, m, 10)
    if m == 12:
        end_date = date(y + 1, 1, 9)
    else:
        end_date = date(y, m + 1, 9)
    return start_date, end_date


def normalize_expense_type_code(raw: str) -> str:
    """
    מאחד ערכים שונים של סוג הוצאה (עברית או אנגלית) לקוד אחד:
    single / standing / installments
    """
    s = (raw or "").strip()
    if s in ("single", "חד פעמית", "חד פעמי", "single_expense"):
        return "single"
    if s in ("standing", "הוראת קבע חודשית", "הוראת קבע", "קבועה"):
        return "standing"
    if s in ("installments", "רכישה בתשלומים", "תשלומים"):
        return "installments"
    return "single"


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
                # בלי מיון לפי created_at - נמיין בעצמנו לפי date
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
            "payment_method": payment_method or None,
            "is_active": True,
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
        # כאן אנחנו מנרמלים לקוד פנימי
        "expense_type": normalize_expense_type_code(row.get("expense_type")),
        "is_fixed": bool(row.get("is_fixed")) if "is_fixed" in row else False,
        "installments_count": 0,
    }

    plan = get_payment_plan_for_expense(expense_id)
    if plan:
        exp["installments_count"] = plan.get("installments_count", 0)

    return exp


# =========================
# CRUD ליצירה/עדכון הוצאה
# =========================

def insert_expense(date_str, category, amount, payment_method, note, expense_type=None, is_fixed=False):
    """הכנסת הוצאה חדשה לטבלת expenses."""
    # מנרמלים לקוד פנימי
    expense_type_code = normalize_expense_type_code(expense_type) if expense_type else "single"

    payload = {
        "date": normalize_date(date_str),
        "category": category,
        "amount": parse_amount(amount),
        "payment_method": payment_method,
        "description": (note or "").strip(),
        "is_fixed": bool(is_fixed),
        "expense_type": expense_type_code,
    }

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
    expense_type_code = normalize_expense_type_code(expense_type) if expense_type else "single"

    payload = {
        "date": normalize_date(date_str),
        "category": category,
        "amount": parse_amount(amount),
        "payment_method": payment_method,
        "description": (note_text or "").strip(),
        "is_fixed": bool(is_fixed),
        "expense_type": expense_type_code,
    }

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

@app.route("/expenses")
def expenses():
    """מסך הוצאות - כולל סינון לפי חודש, קטגוריה, אמצעי תשלום וסוג הוצאה."""

    # חודש פיננסי נבחר מה-URL או ברירת מחדל (10 עד 9)
    selected_month = request.args.get("month") or current_month()

    # פילטרים כמו בדוחות
    category_filter = request.args.get("category_filter", "")
    payment_filter = request.args.get("payment_filter", "")
    expense_type_filter = request.args.get("expense_type", "")

    print("DEBUG selected_month in /expenses:", selected_month)
    print("DEBUG filters:", category_filter, payment_filter, expense_type_filter)

    expenses_raw = fetch_expenses()

    # טווח תאריכים של החודש הפיננסי
    try:
        target_year, target_month = map(int, selected_month.split("-"))
    except ValueError:
        target_year, target_month = financial_label_for_date(date.today())

    start_date, end_date = financial_range_for_month(selected_month)

    # ניסיון לפרש תאריך לכל הוצאה
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

        # ניסיון נוסף לפורמט DD/MM/YY
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

    adjusted_expenses = []
    for e in enriched:
        exp_id = e.get("id")
        plan = plans_map.get(int(exp_id)) if exp_id else None
        dt = e.get("_parsed_date")

        # אם אין תאריך מפוענח - לא מסננים לפי טווח (נכניס כמו שהוא)
        if not dt:
            adjusted_expenses.append(e)
            continue

        base_date = dt.date()
        is_fixed = bool(e.get("is_fixed"))

        # 🔹 בלי תכנית תשלומים
        if not plan:
            if is_fixed:
                # הוצאה קבועה - מופיעה בכל חודש פיננסי מאותו חודש והלאה
                start_label_year, start_label_month = financial_label_for_date(base_date)
                months_diff = (
                    (target_year - start_label_year) * 12
                    + (target_month - start_label_month)
                )
                if months_diff >= 0:
                    adjusted_expenses.append(e)
            else:
                # הוצאה רגילה - רק אם נופלת בתוך החודש הפיננסי
                if start_date <= base_date <= end_date:
                    adjusted_expenses.append(e)
            continue

        # 🔹 יש תכנית תשלומים
        num_payments = plan.get("installments_count", 0)

        # אם התכנית מוגדרת כ"תשלומים" אבל רק 1 תשלום - נתייחס אליה כמו רגילה/קבועה
        if num_payments <= 1:
            if is_fixed:
                start_label_year, start_label_month = financial_label_for_date(base_date)
                months_diff = (
                    (target_year - start_label_year) * 12
                    + (target_month - start_label_month)
                )
                if months_diff >= 0:
                    adjusted_expenses.append(e)
            else:
                if start_date <= base_date <= end_date:
                    adjusted_expenses.append(e)
            continue

        # כמה חודשים עברו מאז תחילת הפריסה (לפי חודש פיננסי)
        start_label_year, start_label_month = financial_label_for_date(base_date)
        months_diff = (
            (target_year - start_label_year) * 12
            + (target_month - start_label_month)
        )

        # לפני תחילת פריסה או אחרי סיום - לא נכנס לרשימה של החודש הזה
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
            total_amount_plan = plan.get("total_amount") or 0
            try:
                total_amount_plan = float(total_amount_plan)
            except ValueError:
                total_amount_plan = 0.0
            monthly_amount = round(total_amount_plan / num_payments, 2) if num_payments > 0 else 0.0

        new_e = e.copy()
        new_e["amount"] = monthly_amount
        new_e["current_installment"] = current_installment
        new_e["total_installments"] = num_payments
        adjusted_expenses.append(new_e)

    # 🔹 פילטרים (קטגוריה / קבועות / אמצעי תשלום / סוג הוצאה)
    filtered_expenses = []
    for e in adjusted_expenses:
        # פילטר קטגוריה
        if category_filter:
            if category_filter == "fixed":
                # רק הוצאות מסומנות כקבועות
                if not e.get("is_fixed"):
                    continue
            else:
                if (e.get("category") or "") != category_filter:
                    continue

        # פילטר אמצעי תשלום
        if payment_filter:
            if (e.get("payment_method") or "") != payment_filter:
                continue

        # פילטר סוג הוצאה
        if expense_type_filter:
            et = normalize_expense_type_code(e.get("expense_type"))
            if et != normalize_expense_type_code(expense_type_filter):
                continue

        filtered_expenses.append(e)

    expenses_for_view = filtered_expenses

    # תקציב לחודש הנבחר - רק קטגוריות תקציב, בלי "הכנסות"
    budgets = fetch_budgets_for_month(selected_month)
    total_budget = sum(
        b["amount"]
        for b in budgets
        if b.get("category") not in ("הכנסות", "💰 הכנסות")
    )

    # הוצאות חד פעמיות בלבד (לסוללה) - כלומר לא is_fixed
    spent_single = sum(e.get("amount", 0) for e in expenses_for_view if not e.get("is_fixed"))

    battery_percent = 0
    if total_budget > 0:
        battery_percent = min(100, round((spent_single / total_budget) * 100, 1))

    # מיון לפי תאריך, מהחדש לישן
    def sort_key_by_date(e):
        if e.get("_parsed_date"):
            return e["_parsed_date"]
        raw = e.get("raw_date") or e.get("date") or ""
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y", "%Y/%m/%d"):
            try:
                return datetime.strptime(str(raw), fmt)
            except ValueError:
                continue
        return datetime(2000, 1, 1)

    expenses_sorted = sorted(
        expenses_for_view,
        key=sort_key_by_date,
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
        selected_month=selected_month,
        category_filter=category_filter,
        payment_filter=payment_filter,
        expense_type=expense_type_filter,
        categories=CATEGORIES,
        payment_methods=PAYMENT_METHODS,
    )





@app.route("/add", methods=["GET", "POST"])
def add_expense():
    """
    הוספת הוצאה חדשה:
    - POST: שומר הוצאה + תכנית תשלומים אם צריך, ומפנה חזרה לרשימת הוצאות.
    - בשגיאה: מציג שוב את הטופס עם הודעת שגיאה.
    - GET: מציג טופס ריק.
    """
    error_message = None

    if request.method == "POST":
        try:
            # סוג הוצאה מהטופס, מנורמל לקוד פנימי
            raw_type = request.form.get("expense_type")
            expense_type = normalize_expense_type_code(raw_type)

            note = request.form.get("note", "")
            is_fixed = "is_fixed" in request.form
            installments_count = int(request.form.get("installments_count", "0") or 0)
            amount_str = request.form.get("amount", "0")
            payment_method = request.form.get("payment_method", "")
            date_str = request.form.get("date", "")
            category = request.form.get("category", "")

            # יצירת ההוצאה ב-Supabase
            inserted = insert_expense(
                date_str,
                category,
                amount_str,
                payment_method,
                note,
                expense_type,  # single / standing / installments
                is_fixed,
            )

            # תכנית תשלומים אם צריך
            if expense_type == "installments" and installments_count > 1 and inserted:
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
                        payment_method=payment_method,
                    )

            print(
                "📦 DEBUG add_expense:",
                "type:", expense_type,
                "installments:", installments_count,
                "amount:", amount_str,
            )

            # חזרה לחודש שממנו הגענו אם קיים
            month = request.args.get("month") or request.form.get("month")
            if month:
                return redirect(url_for("expenses", month=month))
            return redirect(url_for("expenses"))

        except Exception as ex:
            print("❌ שגיאה בהוספת הוצאה:", ex)
            error_message = f"שגיאה בהוספת הוצאה: {ex}"
            flash(error_message, "error")

    # GET או POST שנכשל – מציגים את הטופס
    today_str = date.today().strftime("%Y-%m-%d")
    return render_template(
        "add_expense.html",
        categories=CATEGORIES,
        payment_methods=PAYMENT_METHODS,
        active_tab="expenses",
        error_message=error_message,
        today=today_str,
    )


@app.route("/edit/<int:expense_id>", methods=["GET", "POST"])
def edit_expense(expense_id):
    exp = get_expense_by_id(expense_id)
    if not exp:
        flash("הוצאה לא נמצאה", "error")
        # אם לא מצאנו - חוזרים לעמוד הקודם או להוצאות
        return redirect(request.referrer or url_for("expenses"))

    if request.method == "POST":
        try:
            # סוג הוצאה - אם לא נשלח מהטופס, נשמור את הקיים
            raw_type = request.form.get("expense_type")
            if not raw_type:
                expense_type = exp.get("expense_type") or "single"
            else:
                expense_type = normalize_expense_type_code(raw_type)

            is_fixed = "is_fixed" in request.form
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
                expense_type,   # תמיד ערך תקין
                is_fixed,
            )

            # טיפול בתכנית תשלומים
            if expense_type == "installments":
                upsert_payment_plan(
                    expense_id=int(expense_id),
                    total_amount=parse_amount(amount_str),
                    installments_count=installments_count,
                    payment_method=request.form.get("payment_method", ""),
                )
            else:
                # אם כבר לא תשלומים - מנטרלים את התכנית
                upsert_payment_plan(
                    expense_id=expense_id,
                    total_amount=0,
                    installments_count=1,
                )

            # ✅ חזרה חכמה אחרי שמירה:
            # קודם כל לוקחים next מהטופס, אם יש
            next_url = request.form.get("next") or request.args.get("next")

            # אם אין next - ננסה פשוט לחזור לדף שממנו הגענו
            if not next_url:
                next_url = request.referrer or url_for("expenses")

            return redirect(next_url)

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


@app.route("/budget", methods=["GET", "POST"])
def budget():
    month = request.args.get("month") or request.form.get("month") or current_month()

    # שליפת נתוני תקציב לחודש מה-DB
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

    # קטגוריות תקציב (בלי הכנסות)
    categories = [
        "מזון", "בריאות", "חינוך", "תחבורה", "בילויים",
        "ביגוד", "בית", "רכב", "ילדים", "חוגים",
        "קניות", "טבק", "שונות",
    ]

    # קטגוריות ההכנסה החדשות
    INCOME_CATEGORIES = [
        "שכר שלום",
        "שכר חגית",
        "ביטוח לאומי",
        "קצבת ילדים",
    ]

    # מיפוי לפי קטגוריה מתוך מה שחזר מסופבייס
    existing_cats = {row.get("category", ""): row for row in budgets_data}

    # בניית רשימת תקציבים מסודרת ל-template
    budgets = []
    for cat in categories:
        row = existing_cats.get(cat, {})
        try:
            amount_val = float(row.get("amount") or 0)
        except (TypeError, ValueError):
            amount_val = 0.0

        try:
            prev_val = float(row.get("previous_amount") or 0)
        except (TypeError, ValueError):
            prev_val = 0.0

        budgets.append(
            {
                "category": cat,
                "amount": amount_val,
                "previous_amount": prev_val,
            }
        )

    # שליפת ערכי ההכנסות לפי מקורות שונים
    def get_income_value(cat_name: str) -> float:
        row = existing_cats.get(cat_name)
        if not row:
            return 0.0
        try:
            return float(row.get("amount") or 0)
        except (TypeError, ValueError):
            return 0.0

    income_shalom = get_income_value("שכר שלום")
    income_hagit = get_income_value("שכר חגית")
    income_bitua = get_income_value("ביטוח לאומי")
    income_kids = get_income_value("קצבת ילדים")

    # תמיכה לאחור - אם יש "הכנסות" ישנות ואין כלום בארבע החדשות
    legacy_income = 0.0
    for row in budgets_data:
        cat = row.get("category", "")
        if cat in ("💰 הכנסות", "הכנסות"):
            try:
                legacy_income = float(row.get("amount") or 0)
            except (TypeError, ValueError):
                legacy_income = 0.0
            break

    if (income_shalom + income_hagit + income_bitua + income_kids) == 0 and legacy_income > 0:
        # אם הכל אפס אבל יש הכנסה ישנה - נשים אותה באופן זמני כשכר שלום
        income_shalom = legacy_income

    total_income = income_shalom + income_hagit + income_bitua + income_kids

    # חישוב סה"כ תקציב (סכום כל הקטגוריות, בלי ההכנסות)
    total_budget = sum(b["amount"] for b in budgets)

    # כמה נשאר אחרי התקציבים (הכנסה פחות מה שתיקצבתי)
    net_after_budget = total_income - total_budget

    # ============ POST - שמירת תקציב ============ #
    if request.method == "POST":
        updates = []

        # 1. שדות ההכנסה מהטופס
        def parse_income_field(name: str) -> float:
            raw = (request.form.get(name) or "0").strip()
            try:
                return float(raw) if raw else 0.0
            except ValueError:
                return 0.0

        income_shalom_val = parse_income_field("income_shalom")
        income_hagit_val = parse_income_field("income_hagit")
        income_bitua_val = parse_income_field("income_bitua")
        income_kids_val = parse_income_field("income_kids")

        # שורות נפרדות להכנסות בטבלה
        updates.append(
            {
                "month": month,
                "category": "שכר שלום",
                "amount": income_shalom_val,
            }
        )
        updates.append(
            {
                "month": month,
                "category": "שכר חגית",
                "amount": income_hagit_val,
            }
        )
        updates.append(
            {
                "month": month,
                "category": "ביטוח לאומי",
                "amount": income_bitua_val,
            }
        )
        updates.append(
            {
                "month": month,
                "category": "קצבת ילדים",
                "amount": income_kids_val,
            }
        )

        # 2. כל קטגוריות התקציב
        for cat in categories:
            amount_str = (request.form.get(f"budget_{cat}") or "0").strip()
            try:
                amount_val = float(amount_str) if amount_str else 0.0
            except ValueError:
                amount_val = 0.0

            updates.append(
                {
                    "month": month,
                    "category": cat,
                    "amount": amount_val,
                }
            )

        # 3. מחיקת התקציב הקודם לחודש
        try:
            requests.delete(
                SUPABASE_BUDGETS_URL,
                headers=supabase_headers(),
                params={"month": f"eq.{month}"},
                timeout=10,
            )
        except Exception as e:
            print("שגיאה במחיקת תקציב קודם:", e)

        # 4. הוספת התקציב החדש
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

        # אחרי שמירה - חזרה לעמוד התקציב (GET)
        return redirect(url_for("budget", month=month))

    # ============ GET - הצגה ============ #
    return render_template(
        "budget.html",
        budgets=budgets,
        month=month,
        income=total_income,          # סה"כ הכנסות
        income_shalom=income_shalom,
        income_hagit=income_hagit,
        income_bitua=income_bitua,
        income_kids=income_kids,
        total_income=total_income,
        total_budget=total_budget,
        net_after_budget=net_after_budget,
        active_tab="budget",
    )


def fetch_fixed_expenses():
    """מחזיר רשימת הוצאות קבועות בלבד (is_fixed או הוראות קבע)."""
    try:
        resp = requests.get(
            SUPABASE_EXPENSES_URL,
            headers=supabase_headers(),
            params={
                "select": "*",
                "or": "(expense_type.eq.הוראת קבע חודשית,expense_type.eq.standing)",
                "order": "created_at.desc",
            },
            timeout=10,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print("שגיאה בשליפת הוצאות קבועות:", e)
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
                "expense_type": row.get("expense_type") or "",
            }
        )

    return expenses


def build_payment_rows(filtered_expenses):
    """יוצר טבלת סכומים לפי אמצעי תשלום לדוחות."""
    payment_rows = []
    totals_by_method = {}

    for e in filtered_expenses:
        method = e.get("payment_method") or "לא צוין"
        totals_by_method[method] = totals_by_method.get(method, 0) + e.get("amount", 0)

    for method, total in totals_by_method.items():
        payment_rows.append({"method": method, "total": total})

    return payment_rows


@app.route("/reports", methods=["GET"])
def reports():
    import re

    # ---------------------------------------------------------
    # בניית רשימת חודשים לבחירה (תוויות YYYY-MM)
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

    selected_month = request.args.get("month") or current_month()
    category_filter = request.args.get("category_filter", "")
    payment_filter = request.args.get("payment_filter", "")
    expense_type_filter = request.args.get("expense_type", "")

    # תאריך התחלה/סיום של החודש הפיננסי שנבחר
    try:
        target_year, target_month = map(int, selected_month.split("-"))
    except ValueError:
        target_year, target_month = financial_label_for_date(today)

    start_date, end_date = financial_range_for_month(selected_month)
    display_range = f"{start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}"

    # ---------------------------------------------------------
    # שליפת תקציב לפי החודש הפיננסי הנבחר
    # ---------------------------------------------------------
    budgets = fetch_budgets_for_month(selected_month)
    budgets_map = {row["category"]: parse_amount(row["amount"]) for row in budgets}

    # חישוב סה"כ הכנסות – תופס גם שורת "הכנסות" אחת וגם פירוק לפי סוגי הכנסה
    total_income = 0.0
    for row in budgets:
        cat = (row.get("category") or "").strip()
        if cat in (
            "💰 הכנסות",
            "הכנסות",
            "שכר שלום",
            "שכר חגית",
            "ביטוח לאומי",
            "קצבת ילדים",
        ):
            total_income += parse_amount(row.get("amount", 0))

    # ---------------------------------------------------------
    # שליפת הוצאות
    # ---------------------------------------------------------
    expenses_list = fetch_expenses()

    def normalize_expense_type(t):
        t = (str(t) if t is not None else "").strip().lower()
        if t in ("singel", "single", "חד פעמית", "חד-פעמית", "חדפעמית"):
            return "single"
        if t in ("standing", "קבועה", "קבוע", "הוראתקבע", "הוראת קבע"):
            return "standing"
        if t in ("installments", "installment", "תשלומים", "תשלום", "תשלומי"):
            return "installments"
        return t

    def normalize(text):
        if not text:
            return ""
        return re.sub(r"[^א-תA-Za-z0-9]", "", str(text)).strip()

    # פרסינג תאריך + חישוב חודש פיננסי לכל הוצאה
    base_expenses = []
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

        if not parsed_date:
            continue

        fy, fm = financial_label_for_date(parsed_date.date())
        e = e.copy()
        e["_parsed_date"] = parsed_date
        e["_fin_year"] = fy
        e["_fin_month"] = fm
        e["expense_type"] = normalize_expense_type(e.get("expense_type"))
        try:
            e["amount"] = float(e.get("amount") or 0)
        except (TypeError, ValueError):
            e["amount"] = 0.0
        base_expenses.append(e)

    # ---------------------------------------------------------
    # טיפול בתשלומים (טבלת תוכנית תשלומים)
    # ---------------------------------------------------------
    plans_map = fetch_payment_plans_map()

    all_month_expenses = []
    remaining_installments_total = 0.0
    installments_current_month = 0.0
    fixed_monthly = 0.0

    def month_diff(y1, m1, y2, m2):
        return (y2 - y1) * 12 + (m2 - m1)

    for e in base_expenses:
        etype = e.get("expense_type") or "single"
        fy = e["_fin_year"]
        fm = e["_fin_month"]

        # חד פעמית - רק אם שייכת לחודש הזה
        if etype == "single":
            if fy == target_year and fm == target_month:
                all_month_expenses.append(e)
            continue

        # הוראת קבע - בכל חודש מההתחלה והלאה
        if etype == "standing":
            diff = month_diff(fy, fm, target_year, target_month)
            if diff >= 0:
                em = e.copy()
                em["_parsed_date"] = datetime.combine(end_date, datetime.min.time())
                em["date"] = end_date.strftime("%d/%m/%Y")
                all_month_expenses.append(em)
                fixed_monthly += em["amount"]
            continue

        # תשלומים
        if etype == "installments":
            exp_id = e.get("id")
            plan = plans_map.get(int(exp_id)) if exp_id is not None else None

            if not plan:
                if fy == target_year and fm == target_month:
                    all_month_expenses.append(e)
                continue

            num_payments = plan.get("installments_count", 0) or 0
            if num_payments <= 0:
                continue

            monthly_amount = plan.get("payment_amount") or 0
            try:
                monthly_amount = float(monthly_amount)
            except (TypeError, ValueError):
                monthly_amount = 0.0

            if monthly_amount <= 0:
                total_amount = plan.get("total_amount") or 0
                try:
                    total_amount = float(total_amount)
                except (TypeError, ValueError):
                    total_amount = 0.0
                monthly_amount = round(total_amount / num_payments, 2) if num_payments > 0 else 0.0

            diff = month_diff(fy, fm, target_year, target_month)
            if diff < 0 or diff >= num_payments:
                continue

            current_index = diff
            em = e.copy()
            em["amount"] = monthly_amount
            em["current_installment"] = current_index + 1
            em["total_installments"] = num_payments
            em["_parsed_date"] = datetime.combine(end_date, datetime.min.time())
            em["date"] = end_date.strftime("%d/%m/%Y")
            all_month_expenses.append(em)

            installments_current_month += monthly_amount
            remaining_after = num_payments - (current_index + 1)
            if remaining_after > 0:
                remaining_installments_total += remaining_after * monthly_amount

    all_month_expenses = sorted(
        all_month_expenses,
        key=lambda e: e.get("_parsed_date") or datetime(2000, 1, 1),
        reverse=False,
    )

    # פילטרים
    expenses_for_display = list(all_month_expenses)

    if category_filter:
        if category_filter == "fixed":
            expenses_for_display = [
                e for e in expenses_for_display if e.get("is_fixed") is True
            ]
        else:
            norm_cat = normalize(category_filter)
            expenses_for_display = [
                e
                for e in expenses_for_display
                if normalize(e.get("category")) == norm_cat
            ]

    if payment_filter:
        norm_pay = normalize(payment_filter)
        expenses_for_display = [
            e
            for e in expenses_for_display
            if normalize(e.get("payment_method")) == norm_pay
        ]

    if expense_type_filter:
        expenses_for_display = [
            e
            for e in expenses_for_display
            if e.get("expense_type") == normalize_expense_type(expense_type_filter)
        ]

    # סיכומים לטבלאות
    category_rows = []
    totals_by_cat = {}
    for e in expenses_for_display:
        cat = e.get("category") or "ללא קטגוריה"
        totals_by_cat[cat] = totals_by_cat.get(cat, 0) + e.get("amount", 0)

    for cat, spent in totals_by_cat.items():
        budget_val = budgets_map.get(cat, 0)
        category_rows.append(
            {
                "category": cat,
                "spent": spent,
                "budget": budget_val,
                "diff": budget_val - spent,
            }
        )

    payment_rows = build_payment_rows(expenses_for_display)

    # סיכומים כלליים לחודש
    total_spent = sum(e["amount"] for e in all_month_expenses)
    total_spent_filtered = sum(e["amount"] for e in expenses_for_display)

    # הירוק: הוצאות קבועות חודשיות + כל התשלומים של החודש בלבד
    total_fixed_this_month = fixed_monthly + installments_current_month

    # ✅ סה"כ תקציב חודשי לפי קטגוריות, בלי כל סוגי ההכנסות
    monthly_budget = sum(
        val
        for cat, val in budgets_map.items()
        if cat not in (
            "💰 הכנסות",
            "הכנסות",
            "שכר שלום",
            "שכר חגית",
            "ביטוח לאומי",
            "קצבת ילדים",
        )
    )

    # ורוד: כמה נשאר אחרי קבועות ותשלומים של החודש
    luxury_amount = total_income - total_fixed_this_month

    summary = {
        "total_income": total_income,
        "total_spent": total_spent,
        "total_spent_filtered": total_spent_filtered,
        "total_fixed": total_fixed_this_month,
        "monthly_budget": monthly_budget,
        "luxury_amount": luxury_amount,
        "total_budget": monthly_budget,
        "total_diff": total_income - total_spent,
    }

    now_local = datetime.now()
    return render_template(
        "reports.html",
        months=months,
        selected_month=selected_month,
        category_filter=category_filter,
        payment_filter=payment_filter,
        expense_type=expense_type_filter,
        categories=CATEGORIES,
        payment_methods=PAYMENT_METHODS,
        summary=summary,
        category_rows=category_rows,
        payment_rows=payment_rows,
        expenses=expenses_for_display,
        display_range=display_range,
        active_tab="reports",
        now=now_local,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
