import os
import re
import math
import requests
from flask import Flask, render_template, request, redirect, url_for, flash, session, g, has_request_context
from datetime import datetime, date
from calendar import monthrange
from dotenv import load_dotenv


# טוען את קובץ .env
load_dotenv()

# ⬅️ קודם יוצרים את ה־APP
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

# ⬅️ ואז מגדירים את ה־ROUTE הראשי
@app.route("/")
def index():
    return redirect(url_for("expenses"))

@app.route("/health")
def health_check():
    return {"status": "ok"}, 200

now = datetime.now()

# =========================
# Categories & payment methods
# =========================

CATEGORIES = [
    "מזון",
    "בריאות",
    "חינוך",
    "מתנות",
    "בילויים",
    "ביגוד",
    "בית",
    "רכב",
    "ילדים",
    "חוגים",
    "קניות",
    "טבק",
    "צ'אבי",
    "שונות",
]

PAYMENT_METHODS = [
    "מקס שלום",
    "מקס חגית",
    "כאל ויזה",
    "לאומי שלום",
    "עו\"ש",
    "שופרסל",
]

INCOME_CATEGORIES = (
    "💰 הכנסות",
    "הכנסות",
    "שכר שלום",
    "שכר חגית",
    "ביטוח לאומי",
    "קצבת ילדים",
)

SAVINGS_GOAL_CATEGORY = "יעד חיסכון"


# =========================
# פונקציות עזר בסיסיות
# =========================
def display_date(date_str):
    """המרת תאריך מאחסון (טקסט) לתצוגה DD/MM"""
    if not date_str:
        return ""
    s = str(date_str).strip()
    # אם כבר בפורמט DD/MM/YYYY
    try:
        dt = datetime.strptime(s, "%d/%m/%Y")
        return dt.strftime("%d/%m")
    except ValueError:
        pass
    # אם בפורמט DD/MM/YY
    try:
        dt = datetime.strptime(s, "%d/%m/%y")
        return dt.strftime("%d/%m")
    except ValueError:
        pass
    # אם בפורמט HTML YYYY-MM-DD
    try:
        dt = datetime.strptime(s, "%Y-%m-%d")
        return dt.strftime("%d/%m")
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


def parse_any_date(raw):
    """פריסת תאריך מכל הפורמטים שאנחנו משתמשים בהם למופע datetime."""
    if not raw:
        return None
    s = str(raw).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d/%m/%y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    # תמיכה ב-DD/MM/YY (שנתיים ספרות)
    parts = s.split("/")
    if len(parts) == 3 and len(parts[2]) == 2:
        try:
            d, m, y = parts
            y_full = 2000 + int(y)
            return datetime(year=y_full, month=int(m), day=int(d))
        except Exception:
            return None
    return None


def expense_display_date_sort_key(expense):
    """מפתח מיון לפי תאריך ההוצאה שמוצג בפועל ברשימות."""
    parsed = expense.get("_parsed_date")
    if isinstance(parsed, datetime):
        return parsed

    raw = expense.get("raw_date") or expense.get("date") or expense.get("display_date") or ""
    parsed = parse_any_date(raw)
    return parsed or datetime(2000, 1, 1)


def sort_expenses_by_display_date_desc(expenses):
    """מיון יציב של שורות הוצאה לפי תאריך בפועל, מהחדש לישן."""
    return sorted(expenses, key=expense_display_date_sort_key, reverse=True)


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


def month_diff(y1, m1, y2, m2):
    """הפרש חודשים בין (y1,m1) ל-(y2,m2)."""
    return (y2 - y1) * 12 + (m2 - m1)


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


def normalize_text_for_filter(text: str) -> str:
    """ניקוי טקסט לפילטרים (קטגוריה / אמצעי תשלום)."""
    if not text:
        return ""
    return re.sub(r"[^א-תA-Za-z0-9]", "", str(text)).strip()


def calc_total_income_from_budgets(budgets):
    """חישוב סה"כ הכנסות מתוך רשימת תקציבים."""
    total = 0.0
    for row in budgets:
        cat = (row.get("category") or "").strip()
        if cat in INCOME_CATEGORIES:
            total += parse_amount(row.get("amount", 0))
    return total


def mark_financial_read_failure(source):
    """Keep existing fetch return contracts; never treat a failed read as zero spending."""
    if has_request_context() and request.endpoint in ("expenses", "reports"):
        g.financial_read_errors = getattr(g, "financial_read_errors", set()) | {source}


def financial_amount(value):
    try:
        amount = float(str(value).replace(",", "").strip())
        return amount if math.isfinite(amount) else None
    except (TypeError, ValueError):
        return None


def savings_goal_from_budgets(budgets):
    goals = [row for row in budgets if (row.get("category") or "").strip() == SAVINGS_GOAL_CATEGORY]
    if not goals:
        return 0.0
    if len(goals) != 1:
        return None
    amount = financial_amount(goals[0].get("amount"))
    return amount if amount is not None and amount >= 0 else None


def monthly_expenses(rows, plans, month, report_dates=False):
    """Resolve the same monthly charges for both screens, without guessing missing plans."""
    start, end = financial_range_for_month(month)
    year, month_number = map(int, month.split("-"))
    resolved, unresolved = [], []
    for original in rows:
        row = original.copy()
        try:
            if is_recurring_expense(row):
                row = recurring_for_month(row, month)
                if row is None:
                    continue
                if row.get("amount") != original.get("amount"):
                    row.pop("financial_amount_invalid", None)
        except RecurringEditError:
            unresolved.append(dict(original, financial_issue="היסטוריית הקבועה אינה תקינה"))
            continue
        parsed = parse_any_date(row.get("raw_date") or row.get("date"))
        if not parsed:
            unresolved.append(dict(row, financial_issue="חסר תאריך תקין לשיוך לחודש"))
            continue
        fy, fm = financial_label_for_date(parsed.date())
        offset = month_diff(fy, fm, year, month_number)
        kind = "standing" if is_recurring_expense(row) else normalize_expense_type_code(row.get("expense_type"))
        row.update(expense_type=kind, is_fixed=kind != "single", _parsed_date=parsed)
        row["display_date"] = display_date(row.get("raw_date") or row.get("date"))
        if offset < 0 or (kind == "single" and not start <= parsed.date() <= end):
            continue
        if kind == "installments":
            plan = plans.get(int(row["id"])) if row.get("id") else None
            count_value = financial_amount((plan or {}).get("installments_count"))
            count = int(count_value) if count_value is not None and count_value.is_integer() and count_value > 0 else 0
            if count and offset >= count:
                continue
            payment = financial_amount((plan or {}).get("payment_amount"))
            total = financial_amount((plan or {}).get("total_amount"))
            if count and (payment is None or payment <= 0) and total is not None and total > 0:
                payment = round(total / count, 2)
            if not count or payment is None or payment <= 0:
                unresolved.append(dict(row, financial_issue="חסרה תוכנית תשלומים תקינה: מספר תשלומים וחיוב חודשי"))
                continue
            row.update(amount=payment, current_installment=offset + 1, total_installments=count)
        else:
            amount = financial_amount(row.get("amount"))
            if amount is None or row.get("financial_amount_invalid"):
                unresolved.append(dict(row, financial_issue="חסר סכום תקין"))
                continue
            row["amount"] = amount
        if report_dates and kind != "single":
            row.update(_parsed_date=datetime.combine(end, datetime.min.time()),
                       date=end.strftime("%d/%m/%Y"), display_date=end.strftime("%d/%m/%Y"))
        resolved.append(row)
    return sort_expenses_by_display_date_desc(resolved), unresolved


def monthly_financial_summary(rows, budgets, month, unresolved):
    """Reserve savings before single expenses; filters never apply."""
    errors = getattr(g, "financial_read_errors", set()) if has_request_context() else set()
    savings_goal = savings_goal_from_budgets(budgets) if "budgets" not in errors else None
    if savings_goal is None:
        errors = errors | {"savings_goal"}
    complete = not unresolved and not errors
    income = calc_total_income_from_budgets(budgets) if "budgets" not in errors else None
    fixed = sum(e["amount"] for e in rows if e["expense_type"] == "standing")
    installments = sum(e["amount"] for e in rows if e["expense_type"] == "installments")
    singles = sum(e["amount"] for e in rows if e["expense_type"] == "single")
    commitments = fixed + installments
    available = income - commitments - savings_goal if complete else None
    remaining = available - singles if complete else None
    start, end = financial_range_for_month(month)
    today = date.today()
    current = start <= today <= end
    days = (end - today).days + 1 if current else None
    return {
        "complete": complete, "read_errors": sorted(errors),
        "total_income": income,
        "savings_goal": savings_goal,
        "fixed_expenses": fixed if complete else None,
        "installments_this_month": installments if complete else None,
        "total_commitments": commitments if complete else None,
        "available_for_luxuries": available, "already_spent": singles if complete else None,
        "known_single_spent": singles,
        "can_still_spend": remaining, "days_remaining": days,
        "daily_average": remaining / days if current and complete else None,
        "daily_average_applicable": current and complete, "is_current_financial_month": current,
        "usage_percent": singles / available * 100 if available is not None and available > 0 else None,
        "total_spent": commitments + singles if complete else None,
        "known_total_spent": commitments + singles,
        "total_fixed": commitments if complete else None, "luxury_amount": available,
        "total_diff": remaining,
    }


def apply_common_filters(expenses, category_filter, payment_filter, expense_type_filter):
    """פילטרים משותפים ל-/expenses ול-/reports."""
    filtered = list(expenses)

    # קטגוריה (כולל 'fixed_and_installments', 'fixed_only', 'installments_only')
    if category_filter:
        if category_filter == "fixed_and_installments":
            # קבועות ותשלומים - כל מה שמסומן כ-is_fixed
            filtered = [e for e in filtered if e.get("is_fixed")]
        elif category_filter == "fixed_only":
            # קבועות בלבד - is_fixed=True אבל לא תשלומים
            filtered = [e for e in filtered if e.get("is_fixed") and normalize_expense_type_code(e.get("expense_type")) != "installments"]
        elif category_filter == "installments_only":
            # תשלומים בלבד - expense_type=installments
            filtered = [e for e in filtered if normalize_expense_type_code(e.get("expense_type")) == "installments"]
        elif category_filter == "fixed":
            # תמיכה לאחור - מפנה ל-fixed_and_installments
            filtered = [e for e in filtered if e.get("is_fixed")]
        else:
            norm_cat = normalize_text_for_filter(category_filter)
            filtered = [
                e for e in filtered
                if normalize_text_for_filter(e.get("category")) == norm_cat
            ]

    # אמצעי תשלום
    if payment_filter:
        norm_pay = normalize_text_for_filter(payment_filter)
        filtered = [
            e for e in filtered
            if normalize_text_for_filter(e.get("payment_method")) == norm_pay
        ]

    # סוג הוצאה
    if expense_type_filter:
        target_type = normalize_expense_type_code(expense_type_filter)
        filtered = [
            e for e in filtered
            if normalize_expense_type_code(e.get("expense_type")) == target_type
        ]

    return filtered


def build_months_list(num_months=12):
    """בניית רשימת חודשים 'YYYY-MM' אחורה מהיום."""
    today = date.today()
    months = []
    for i in range(num_months):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        months.append(f"{y}-{m:02d}")
    return months


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


@app.route("/health/supabase")
def supabase_health_check():
    """Perform a minimal read so scheduled checks count as database activity."""
    try:
        response = requests.get(
            SUPABASE_EXPENSES_URL,
            headers=supabase_headers(),
            params={"select": "id", "limit": 1},
            timeout=10,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException:
        return {"status": "unavailable"}, 503

    return {"status": "ok"}, 200


# =========================
# CRUD על הוצאות
# =========================

class RecurringEditError(ValueError):
    """הודעה בטוחה להצגה למשתמש, ללא פרטי תשובת API."""


def is_recurring_expense(expense):
    kind = normalize_expense_type_code(expense.get("expense_type"))
    return kind == "standing" or (bool(expense.get("is_fixed")) and kind != "installments")


def recurring_month(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", value) or value[:4] == "0000":
        raise RecurringEditError("יש לבחור חודש תקין להחלת השינוי")
    return value


def recurring_start_month(expense):
    parsed = parse_any_date(expense.get("raw_date") or expense.get("date_for_input") or expense.get("date"))
    if not parsed:
        raise RecurringEditError("לא ניתן לזהות את חודש ההתחלה של ההוצאה")
    year, month = financial_label_for_date(parsed.date())
    return f"{year:04d}-{month:02d}"


def checked_recurring_history(expense):
    history = expense.get("recurring_history", [])
    if not isinstance(history, list):
        raise RecurringEditError("היסטוריית ההוצאה אינה תקינה; השינוי לא נשמר")
    previous = None
    start = recurring_start_month(expense)
    for entry in history:
        if not isinstance(entry, dict):
            raise RecurringEditError("היסטוריית ההוצאה אינה תקינה; השינוי לא נשמר")
        month = recurring_month(entry.get("from_month"))
        if month < start or (previous is not None and month <= previous) or type(entry.get("active")) is not bool:
            raise RecurringEditError("היסטוריית ההוצאה אינה תקינה; השינוי לא נשמר")
        if entry["active"]:
            try:
                amount = float(entry["amount"])
            except (KeyError, ValueError, TypeError):
                raise RecurringEditError("היסטוריית ההוצאה אינה תקינה; השינוי לא נשמר") from None
            if not math.isfinite(amount) or amount <= 0 or any(not isinstance(entry.get(key), str) for key in ("category", "payment_method", "comment")):
                raise RecurringEditError("היסטוריית ההוצאה אינה תקינה; השינוי לא נשמר")
        previous = month
    return history


def recurring_for_month(expense, month, include_inactive=False):
    """בחירת גרסה אחת לחודש, תוך שמירת שדות הבסיס המקוריים."""
    month = recurring_month(month)
    if month < recurring_start_month(expense):
        return None
    result = expense.copy()
    result.update(expense_type="standing", is_fixed=True, recurring_active=True)
    for entry in checked_recurring_history(expense):
        if entry["from_month"] > month:
            break
        result["recurring_active"] = entry["active"]
        if entry["active"]:
            result.update({key: entry[key] for key in ("category", "payment_method", "comment")})
            result["amount"] = float(entry["amount"])
    return result if result["recurring_active"] or include_inactive else None


def checked_recurring_revision(expense, submitted):
    revision = expense.get("recurring_revision")
    if "recurring_history" not in expense or type(revision) is not int or revision < 0:
        raise RecurringEditError("שמירת היסטוריית קבועות אינה זמינה עדיין")
    if revision >= 9223372036854775807:
        raise RecurringEditError("לא ניתן לשמור שינוי נוסף בהוצאה")
    if not isinstance(submitted, str) or not re.fullmatch(r"[0-9]{1,19}", submitted) or int(submitted) != revision:
        raise RecurringEditError("ההוצאה השתנתה מאז פתיחת הטופס; יש לפתוח אותה מחדש")
    return revision


def save_recurring_change(expense, month, submitted_revision, profile=None):
    """PATCH מותנה יחיד: היסטוריה ומספר גרסה מתעדכנים יחד."""
    month = recurring_month(month)
    if month < recurring_start_month(expense):
        raise RecurringEditError("חודש השינוי אינו יכול להיות לפני תחילת ההוצאה")
    revision = checked_recurring_revision(expense, submitted_revision)
    history = checked_recurring_history(expense)
    if profile is None:
        # הפסקה מבטלת גם שינויים עתידיים, אך שומרת כל גרסה קודמת לחודש הנבחר.
        updated = [entry.copy() for entry in history if entry["from_month"] < month]
        updated.append({"from_month": month, "active": False})
    else:
        amount = parse_amount(profile.get("amount"))
        if not math.isfinite(amount) or amount <= 0:
            raise RecurringEditError("סכום ההוצאה חייב להיות חיובי")
        entry = {"from_month": month, "active": True, "amount": str(amount)}
        for key in ("category", "payment_method", "comment"):
            value = profile.get(key)
            if not isinstance(value, str) or not value.strip():
                raise RecurringEditError("יש למלא תיאור, קטגוריה ואמצעי תשלום")
            entry[key] = value.strip()
        updated = [item.copy() for item in history if item["from_month"] != month] + [entry]
        updated.sort(key=lambda item: item["from_month"])
    headers = supabase_headers().copy()
    headers["Prefer"] = "return=representation"
    response = requests.patch(
        SUPABASE_EXPENSES_URL, headers=headers,
        params={"id": f"eq.{expense['id']}", "recurring_revision": f"eq.{revision}"},
        json={"recurring_history": updated, "recurring_revision": revision + 1},
        timeout=20, allow_redirects=False,
    )
    response.raise_for_status()
    if not 200 <= response.status_code < 300:
        raise RecurringEditError("לא ניתן לאשר שהשינוי נשמר; יש לרענן לפני ניסיון נוסף")
    rows = response.json()
    if rows == []:
        raise RecurringEditError("ההוצאה השתנתה במקביל; יש לפתוח אותה מחדש")
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict) or type(rows[0].get("id")) is not int or rows[0].get("id") != expense["id"] or type(rows[0].get("recurring_revision")) is not int or rows[0].get("recurring_revision") != revision + 1 or rows[0].get("recurring_history") != updated:
        raise RecurringEditError("לא ניתן לאשר שהשינוי נשמר; יש לרענן לפני ניסיון נוסף")
    return True


def fetch_expenses():
    """שליפת כל ההוצאות מ-Supabase, כולל is_fixed, description ו-created_at."""
    try:
        resp = requests.get(
            SUPABASE_EXPENSES_URL,
            headers=supabase_headers(),
            params={
                "select": "*",
                # מיון ב-DB לפי זמן יצירה - מהחדש לישן
                "order": "created_at.desc",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
            raise ValueError("Invalid expenses response")
    except (requests.exceptions.RequestException, ValueError) as e:
        mark_financial_read_failure("expenses")
        print("Expenses read failed:", type(e).__name__)
        return []

    expenses = []
    for row in data:
        amount_val = parse_amount(row.get("amount", 0))
        raw_date = row.get("date") or ""
        comment = row.get("description") or row.get("note") or row.get("notes") or ""

        expenses.append(
            {
                "id": row.get("id"),
                "raw_date": raw_date,
                "date": display_date(raw_date),
                "display_date": display_date(raw_date),
                "category": row.get("category") or "",
                "amount": amount_val,
                "financial_amount_invalid": financial_amount(row.get("amount")) is None,
                "payment_method": row.get("payment_method") or "",
                "comment": comment,
                "is_fixed": bool(row.get("is_fixed")),
                "expense_type": row.get("expense_type") or "",
                # נשמור גם את זמן היצירה כדי שנוכל למיין לפי זה
                "created_at": row.get("created_at"),
                "recurring_history": row.get("recurring_history", []),
                "recurring_revision": row.get("recurring_revision"),
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
        if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
            raise ValueError("Invalid payment plans response")
    except Exception as e:
        mark_financial_read_failure("plans")
        print("Payment plans read failed:", type(e).__name__)
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
        count_value = financial_amount(installments)
        installments = int(count_value) if count_value is not None and count_value.is_integer() and count_value > 0 else 0

        # סכום חודשי
        payment_amount = row.get("payment_amount")
        try:
            payment_amount = float(payment_amount) if payment_amount is not None else 0.0
        except (TypeError, ValueError, OverflowError):
            payment_amount = 0.0

        total_amount = row.get("total_amount")
        try:
            total_amount = float(total_amount) if total_amount is not None else 0.0
        except (TypeError, ValueError, OverflowError):
            total_amount = 0.0

        try:
            exp_id = int(exp_id)
        except (TypeError, ValueError, OverflowError):
            mark_financial_read_failure("plans")
            continue
        plans[exp_id] = {
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
        if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
            raise ValueError("Invalid budgets response")
        if any(financial_amount(row.get("amount")) is None for row in data):
            mark_financial_read_failure("budgets")
        return [
            {
                "category": row.get("category", ""),
                "amount": financial_amount(row.get("amount")) or 0,
                "previous_amount": parse_amount(row.get("previous_amount") or 0),
            }
            for row in data
        ]
    except Exception as e:
        mark_financial_read_failure("budgets")
        print("Budgets read failed:", type(e).__name__)
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
    desc = row.get("description") or row.get("note") or row.get("notes") or ""

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
        "comment": desc,
        # מנרמלים לקוד פנימי
        "expense_type": normalize_expense_type_code(row.get("expense_type")),
        "is_fixed": bool(row.get("is_fixed")) if "is_fixed" in row else False,
        "installments_count": 0,
        "recurring_history": row.get("recurring_history", []),
        "recurring_revision": row.get("recurring_revision"),
    }

    plan = None if is_recurring_expense(exp) else get_payment_plan_for_expense(expense_id)
    if plan:
        exp["installments_count"] = plan.get("installments_count", 0)

    return exp


# =========================
# CRUD ליצירה/עדכון הוצאה
# =========================

def insert_expense(date_str, category, amount, payment_method, comment, expense_type=None, is_fixed=False):
    """הכנסת הוצאה חדשה לטבלת expenses."""
    expense_type_code = normalize_expense_type_code(expense_type) if expense_type else "single"

    payload = {
        "date": normalize_date(date_str),
        "category": category,
        "amount": parse_amount(amount),
        "payment_method": payment_method,
        "description": (comment or "").strip(),
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


def update_expense(expense_id, date_str, category, amount, payment_method, comment_text, expense_type=None, is_fixed=False):
    """עדכון הוצאה קיימת בטבלת expenses."""
    expense_type_code = normalize_expense_type_code(expense_type) if expense_type else "single"

    payload = {
        "date": normalize_date(date_str),
        "category": category,
        "amount": parse_amount(amount),
        "payment_method": payment_method,
        "description": (comment_text or "").strip(),
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
    selected_month = (
        request.args.get("month")
        or session.get("selected_month")
        or current_month()
    )
    session["selected_month"] = selected_month

    # פילטרים כמו בדוחות
    category_filter = request.args.get("category_filter", "")
    payment_filter = request.args.get("payment_filter", "")
    expense_type_filter = request.args.get("expense_type", "")

    adjusted_expenses, unresolved_expenses = monthly_expenses(
        fetch_expenses(), fetch_payment_plans_map(), selected_month
    )

    # פילטרים (קטגוריה / קבועות / אמצעי תשלום / סוג הוצאה)
    filtered_expenses = apply_common_filters(
        adjusted_expenses,
        category_filter=category_filter,
        payment_filter=payment_filter,
        expense_type_filter=expense_type_filter,
    )

    expenses_for_view = filtered_expenses

    # תקציב והכנסות לחודש הנבחר
    budgets = fetch_budgets_for_month(selected_month)

    total_income = calc_total_income_from_budgets(budgets)

    # תקציב חודשי (בלי ההכנסות)
    total_budget = sum(
        b["amount"]
        for b in budgets
        if (b.get("category") or "").strip() not in (*INCOME_CATEGORIES, SAVINGS_GOAL_CATEGORY)
    )

    summary = monthly_financial_summary(adjusted_expenses, budgets, selected_month, unresolved_expenses)
    spent_single = summary["already_spent"]
    battery_percent = (spent_single / total_income * 100) if summary["complete"] and total_income > 0 else None
    commitments_list = [e for e in adjusted_expenses if e["expense_type"] != "single"]

    # מיון לפי סוג: חד פעמי -> תשלומים -> קבועות
    def get_expense_type_priority(e):
        if e.get("expense_type") == "installments":
            return 2  # תשלומים במקום שני
        elif e.get("is_fixed"):
            return 3  # קבועות בסוף
        else:
            return 1  # חד פעמי בהתחלה
    
    expenses_sorted = sort_expenses_by_display_date_desc(expenses_for_view)

    # חלוקה לקבוצות עם סיכומים
    single_expenses = [e for e in expenses_sorted if get_expense_type_priority(e) == 1]
    installment_expenses = [e for e in expenses_sorted if get_expense_type_priority(e) == 2]
    fixed_expenses = [e for e in expenses_sorted if get_expense_type_priority(e) == 3]

    single_total = sum(parse_amount(e.get("amount", 0)) for e in single_expenses)
    installment_total = sum(parse_amount(e.get("amount", 0)) for e in installment_expenses)
    fixed_total = sum(parse_amount(e.get("amount", 0)) for e in fixed_expenses)

    amounts = [parse_amount(e.get("amount", 0)) for e in expenses_sorted]
    total_amount = sum(amounts)
    max_expense_amount = max(amounts) if amounts else 0

    # 3 קטגוריות מובילות (גם אם כרגע לא מוצג - משאיר לשימוש עתידי)
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
        single_expenses=single_expenses,
        installment_expenses=installment_expenses,
        fixed_expenses=fixed_expenses,
        single_total=single_total,
        installment_total=installment_total,
        fixed_total=fixed_total,
        total_amount=total_amount,
        max_expense_amount=max_expense_amount,
        top_categories=top_categories,
        total_budget=total_budget,
        total_income=total_income,       # זה הנתון שמגיע לעמוד הוצאות
        spent_single=spent_single,
        battery_percent=battery_percent,
        summary=summary,
        unresolved_expenses=unresolved_expenses,
        commitments_list=commitments_list,
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
    # שמירת ה-URL לחזרה
    return_to = request.args.get("return_to") or request.referrer or url_for("expenses")
    
    error_message = None

    if request.method == "POST":
        try:
            # סוג הוצאה מהטופס, מנורמל לקוד פנימי
            raw_type = request.form.get("expense_type")
            expense_type = normalize_expense_type_code(raw_type)

            comment = request.form.get("comment", "")
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
                comment,
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

            # הודעת הצלחה
            flash("הוצאה נרשמה", "success")
            
            # חזרה לעמוד הקודם
            return redirect(return_to)

        except Exception as ex:
            print("❌ שגיאה בהוספת הוצאה:", ex)
            error_message = f"שגיאה בהוספת הוצאה: {ex}"
            flash(error_message, "error")

    # GET או POST שנכשל – מציגים את הטופס
    today_str = date.today().strftime("%Y-%m-%d")
    selected_month = session.get("selected_month") or current_month()
    return render_template(
        "add_expense.html",
        categories=CATEGORIES,
        payment_methods=PAYMENT_METHODS,
        active_tab="expenses",
        error_message=error_message,
        today=today_str,
        return_to=return_to,
        selected_month=selected_month,
    )


@app.route("/edit/<int:expense_id>", methods=["GET", "POST"])
def edit_expense(expense_id):
    # שמירת ה-URL המלא לחזרה (כולל פרמטרים)
    return_to = request.args.get("return_to") or request.referrer or url_for("expenses")
    
    exp = get_expense_by_id(expense_id)
    if not exp:
        flash("הוצאה לא נמצאה", "error")
        return redirect(url_for("expenses"))

    if is_recurring_expense(exp):
        selected_month = request.form.get("effective_month") or request.args.get("month") or session.get("selected_month") or current_month()
        start_month = recurring_start_month(exp)
        if request.method == "POST":
            try:
                action = request.form.get("recurring_action", "update")
                if action not in ("update", "stop"):
                    raise RecurringEditError("פעולה לא תקינה")
                profile = None
                if action == "update":
                    if normalize_expense_type_code(request.form.get("expense_type") or "standing") != "standing" or request.form.get("date") != exp["date_for_input"]:
                        raise RecurringEditError("תאריך ההתחלה וסוג ההוצאה נשמרים; להמרה יש להפסיק ולהוסיף הוצאה נפרדת")
                    profile = {key: request.form.get(key, "") for key in ("amount", "category", "payment_method", "comment")}
                save_recurring_change(exp, request.form.get("effective_month"), request.form.get("recurring_revision"), profile)
                flash("ההוצאה הקבועה הופסקה מהחודש שנבחר; ההיסטוריה נשמרה" if action == "stop" else "ההוצאה הקבועה עודכנה מהחודש שנבחר; ההיסטוריה נשמרה", "success")
                return redirect(return_to)
            except RecurringEditError as ex:
                flash(str(ex), "error")
            except Exception as ex:
                print(f"❌ שינוי הוצאה קבועה נכשל ({type(ex).__name__})")
                flash("לא ניתן לאשר שהשינוי נשמר; יש לרענן ולבדוק לפני ניסיון נוסף", "error")
        try:
            selected_month = max(recurring_month(selected_month), start_month)
        except RecurringEditError:
            selected_month = max(current_month(), start_month)
        display_exp = recurring_for_month(exp, selected_month, include_inactive=True)
        return render_template(
            "edit_expense.html", expense=display_exp, categories=CATEGORIES,
            payment_methods=PAYMENT_METHODS, active_tab="expenses", return_to=return_to,
            selected_month=selected_month, recurring=True, recurring_start=start_month,
        )

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
                request.form.get("comment", ""),
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

            # הודעת הצלחה
            flash("ההוצאה עודכנה בהצלחה", "success")
            
            # חזרה לעמוד שממנו הגענו
            return redirect(return_to)

        except Exception as ex:
            print("❌ שגיאה בעדכון הוצאה:", ex)
            flash(f"שגיאה בעדכון הוצאה: {ex}", "error")

    selected_month = session.get("selected_month") or current_month()
    return render_template(
        "edit_expense.html",
        expense=exp,
        categories=CATEGORIES,
        payment_methods=PAYMENT_METHODS,
        active_tab="expenses",
        return_to=return_to,  # מעביר את הנתיב גם לטמפלייט
        selected_month=selected_month,
    )


@app.route("/delete/<int:expense_id>", methods=["POST"])
def delete_expense(expense_id):
    """מחיקת הוצאה בודדת מכפתור האשפה בכרטיס."""
    try:
        exp = get_expense_by_id(expense_id)
        if not exp:
            raise RecurringEditError("הוצאה לא נמצאה; לא בוצעה מחיקה")
        if is_recurring_expense(exp):
            save_recurring_change(exp, request.form.get("effective_month"), request.form.get("recurring_revision"))
            flash("ההוצאה הקבועה הופסקה מהחודש שנבחר; ההיסטוריה נשמרה", "success")
        else:
            delete_expense_record(expense_id)
            flash("ההוצאה נמחקה בהצלחה", "success")
    except RecurringEditError as e:
        flash(str(e), "error")
    except Exception as e:
        print(f"❌ מחיקה או הפסקת הוצאה נכשלו ({type(e).__name__})")
        flash("אירעה שגיאה במחיקת ההוצאה", "error")
    return redirect(request.referrer or url_for("expenses"))


@app.route("/delete-selected", methods=["POST"])
def delete_selected():
    """מחיקת מספר הוצאות שנבחרו בצ'קבוקסים."""
    ids = request.form.getlist("selected_ids")

    if not ids:
        flash("לא נבחרו הוצאות למחיקה", "error")
        return redirect(request.referrer or url_for("expenses"))

    completed = 0
    try:
        selected = []
        for expense_id in dict.fromkeys(int(value) for value in ids):
            exp = get_expense_by_id(expense_id)
            if not exp:
                raise RecurringEditError("אחת ההוצאות לא נמצאה; יש לרענן לפני ניסיון נוסף")
            revision = request.form.get(f"recurring_revision_{expense_id}", request.form.get("recurring_revision"))
            if is_recurring_expense(exp):
                month = recurring_month(request.form.get("effective_month"))
                if month < recurring_start_month(exp):
                    raise RecurringEditError("חודש ההפסקה אינו יכול להיות לפני תחילת ההוצאה")
                checked_recurring_revision(exp, revision)
                checked_recurring_history(exp)
            selected.append((exp, revision))
        for exp, revision in selected:
            if is_recurring_expense(exp):
                save_recurring_change(exp, request.form.get("effective_month"), revision)
            else:
                delete_expense_record(exp["id"])
            completed += 1
        flash(f"טופלו {completed} הוצאות; קבועות הופסקו מהחודש שנבחר וההיסטוריה נשמרה", "success")
    except Exception as ex:
        print(f"❌ טיפול בהוצאות שנבחרו נעצר ({type(ex).__name__})")
        message = str(ex) if isinstance(ex, RecurringEditError) else "הפעולה נעצרה; יש לרענן ולבדוק לפני ניסיון נוסף"
        flash(f"{message}. טופלו {completed} הוצאות לפני העצירה", "error")

    return redirect(request.referrer or url_for("expenses"))


@app.route("/budget", methods=["GET", "POST"])
def budget():
    month = (
        request.args.get("month")
        or request.form.get("month")
        or session.get("selected_month")
        or current_month()
    )
    if request.method == "POST" and request.form.get("save_savings_goal") == "1":
        try:
            recurring_month(month)
            financial_range_for_month(month)
        except (ValueError, RecurringEditError):
            flash("יש לבחור חודש פיננסי תקין ליעד החיסכון", "error")
            return redirect(url_for("budget", month=current_month()))
    session["selected_month"] = month

    # שליפת נתוני תקציב לחודש מה-DB
    budget_read_ok = True
    try:
        resp = requests.get(
            SUPABASE_BUDGETS_URL,
            headers=supabase_headers(),
            params={"select": "*", "month": f"eq.{month}"},
            timeout=10,
        )

        resp.raise_for_status()
        budgets_data = resp.json()
        if not isinstance(budgets_data, list) or any(not isinstance(row, dict) for row in budgets_data):
            raise ValueError("Invalid budgets response")
    except Exception as e:
        print("Budgets read failed:", type(e).__name__)
        budgets_data = []
        budget_read_ok = False

    if request.method == "POST" and not budget_read_ok:
        flash("התקציב לא נטען; לא בוצעה שמירה כדי לשמור על הנתונים הקיימים", "error")
        target = url_for("budget", month=month)
        return redirect(target + ("#savings-goal" if request.form.get("save_savings_goal") == "1" else ""))

    savings_goal = savings_goal_from_budgets(budgets_data) if budget_read_ok else None
    if request.method == "POST" and request.form.get("save_savings_goal") == "1":
        amount = financial_amount(request.form.get("savings_goal"))
        goal_rows = [row for row in budgets_data if row.get("category") == SAVINGS_GOAL_CATEGORY]
        if amount is None or amount < 0:
            flash("יעד החיסכון חייב להיות סכום תקין של 0 או יותר", "error")
        elif not budget_read_ok or len(goal_rows) > 1:
            flash("לא ניתן לשמור יעד חיסכון עד לטעינת תקציב תקין", "error")
        else:
            headers = supabase_headers().copy()
            headers["Prefer"] = "return=representation"
            try:
                if goal_rows:
                    response = requests.patch(
                        SUPABASE_BUDGETS_URL, headers=headers,
                        params={"month": f"eq.{month}", "category": f"eq.{SAVINGS_GOAL_CATEGORY}"},
                        json={"amount": amount}, timeout=20, allow_redirects=False,
                    )
                elif amount == 0:
                    # No target: no new record is needed.
                    response = None
                else:
                    response = requests.post(
                        SUPABASE_BUDGETS_URL, headers=headers,
                        json=[{"month": month, "category": SAVINGS_GOAL_CATEGORY, "amount": amount}],
                        timeout=20, allow_redirects=False,
                    )
                if response is not None:
                    response.raise_for_status()
                    saved = response.json()
                    if (not isinstance(saved, list) or len(saved) != 1
                            or saved[0].get("month") != month
                            or saved[0].get("category") != SAVINGS_GOAL_CATEGORY
                            or financial_amount(saved[0].get("amount")) != amount):
                        raise ValueError("Savings goal save was not confirmed")
                flash("יעד החיסכון נשמר" if amount > 0 else "לא הוגדר יעד חיסכון לחודש", "success")
            except (requests.exceptions.RequestException, ValueError, TypeError, AttributeError) as error:
                print("Savings goal save failed:", type(error).__name__)
                flash("שמירת יעד החיסכון לא אושרה. יש לטעון מחדש ולבדוק את הסכום", "error")
        return redirect(url_for("budget", month=month) + "#savings-goal")

    # קטגוריות תקציב (בלי הכנסות)
    categories = [
        "מזון", "בריאות", "חינוך", "תחבורה", "בילויים",
        "ביגוד", "בית", "רכב", "ילדים", "חוגים",
        "קניות", "טבק", "צ'אבי", "שונות",
    ]

    # מיפוי לפי קטגוריה מתוך מה שחזר מסופבייס
    existing_cats = {row.get("category", ""): row for row in budgets_data}

    # חישוב החודש הקודם
    year, month_num = month.split('-')
    year = int(year)
    month_num = int(month_num)
    
    if month_num == 1:
        prev_month = f"{year - 1}-12"
    else:
        prev_month = f"{year}-{month_num - 1:02d}"
    
    # שליפת תקציב החודש הקודם
    prev_month_budgets = {}
    try:
        resp_prev = requests.get(
            SUPABASE_BUDGETS_URL,
            headers=supabase_headers(),
            params={"select": "*", "month": f"eq.{prev_month}"},
            timeout=10,
        )
        resp_prev.raise_for_status()
        prev_budgets_data = resp_prev.json()
        
        # מיפוי לפי קטגוריה
        for row in prev_budgets_data:
            cat = row.get("category", "")
            amount = parse_amount(row.get("amount") or 0)
            prev_month_budgets[cat] = amount
                
    except Exception as e:
        print("Previous budget read failed:", type(e).__name__)

    # בניית רשימת תקציבים מסודרת ל-template
    budgets = []
    for cat in categories:
        row = existing_cats.get(cat, {})
        amount_val = parse_amount(row.get("amount") or 0)
        # התקציב מהחודש הקודם
        prev_val = prev_month_budgets.get(cat, 0)

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
        return parse_amount(row.get("amount") or 0)

    income_shalom = get_income_value("שכר שלום")
    income_hagit = get_income_value("שכר חגית")
    income_bitua = get_income_value("ביטוח לאומי")
    income_kids = get_income_value("קצבת ילדים")

    # תמיכה לאחור - אם יש "הכנסות" ישנות ואין כלום בארבע החדשות
    legacy_income = 0.0
    for row in budgets_data:
        cat = row.get("category", "")
        if cat in ("💰 הכנסות", "הכנסות"):
            legacy_income = parse_amount(row.get("amount") or 0)
            break

    if (income_shalom + income_hagit + income_bitua + income_kids) == 0 and legacy_income > 0:
        income_shalom = legacy_income

    total_income = income_shalom + income_hagit + income_bitua + income_kids

    # חישוב סה"כ תקציב (סכום כל הקטגוריות, בלי ההכנסות)
    total_budget = sum(b["amount"] for b in budgets)

    # כמה נשאר אחרי התקציבים (הכנסה פחות מה שתיקצבתי)
    net_after_budget = total_income - total_budget - savings_goal if savings_goal is not None else None

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
            delete_response = requests.delete(
                SUPABASE_BUDGETS_URL,
                headers=supabase_headers(),
                params={"month": f"eq.{month}", "category": f"neq.{SAVINGS_GOAL_CATEGORY}"},
                timeout=10,
            )
            delete_response.raise_for_status()
        except Exception as e:
            print("Budget replacement failed:", type(e).__name__)
            flash("לא ניתן לשמור את התקציב כעת", "error")
            return redirect(url_for("budget", month=month))

        # 4. הוספת התקציב החדש
        try:
            resp = requests.post(
                SUPABASE_BUDGETS_URL,
                headers=supabase_headers(),
                json=updates,
                timeout=20,
            )
            resp.raise_for_status()
            
            # הודעת הצלחה
            flash("התקציב נשמר בהצלחה", "success")
        except Exception as e:
            print("שגיאה בעדכון תקציב:", e)
            flash("אירעה שגיאה בשמירת התקציב", "error")
        
        # חזרה לעמוד הקודם
        return redirect(request.referrer or url_for("budget", month=month))

    # ============ GET - הצגה ============ #
    return render_template(
        "budget.html",
        budgets=budgets,
        month=month,
        selected_month=month,
        income=total_income,          # סה"כ הכנסות
        income_shalom=income_shalom,
        income_hagit=income_hagit,
        income_bitua=income_bitua,
        income_kids=income_kids,
        total_income=total_income,
        total_budget=total_budget,
        net_after_budget=net_after_budget,
        savings_goal=savings_goal,
        budget_read_ok=budget_read_ok,
        active_tab="budget",
    )


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
    # ---------------------------------------------------------
    # בניית רשימת 12 חודשים אחורה (YYYY-MM)
    # ---------------------------------------------------------
    today = date.today()
    months = build_months_list(12)

    selected_month = (
        request.args.get("month")
        or session.get("selected_month")
        or current_month()
    )
    session["selected_month"] = selected_month
    category_filter = request.args.get("category_filter", "")
    payment_filter = request.args.get("payment_filter", "")
    expense_type_filter = request.args.get("expense_type", "")

    # ---------------------------------------------------------
    # חישוב טווח תאריכים לחודש פיננסי שנבחר
    # ---------------------------------------------------------
    try:
        target_year, target_month = map(int, selected_month.split("-"))
    except ValueError:
        target_year, target_month = financial_label_for_date(today)

    start_date, end_date = financial_range_for_month(selected_month)
    display_range = f"{start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}"

    # ---------------------------------------------------------
    # תקציב לחודש הנבחר
    # ---------------------------------------------------------
    budgets = fetch_budgets_for_month(selected_month)
    budgets_map = {row["category"]: parse_amount(row["amount"]) for row in budgets}

    report_source = sorted(fetch_expenses(), key=lambda e: e.get("created_at") or "")
    report_plans = fetch_payment_plans_map()
    all_month_expenses, unresolved_expenses = monthly_expenses(
        report_source, report_plans, selected_month, report_dates=True
    )

    category_comparison = None
    if category_filter or payment_filter:
        labels = ("ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר")
        comparison_name = {
            "fixed_and_installments": "קבועות ותשלומים", "fixed": "קבועות ותשלומים",
            "fixed_only": "קבועות בלבד", "installments_only": "תשלומים בלבד",
        }.get(category_filter, category_filter) or payment_filter
        if category_filter and payment_filter:
            comparison_name += f" · {payment_filter}"
        points = []
        read_failed = bool(getattr(g, "financial_read_errors", set()) & {"expenses", "plans"})
        for offset in (0, -1, -2):
            year, month_index = divmod(target_year * 12 + target_month - 1 + offset, 12)
            month = f"{year}-{month_index + 1:02d}"
            rows, unresolved = (all_month_expenses, unresolved_expenses) if offset == 0 else monthly_expenses(report_source, report_plans, month)
            filtered = apply_common_filters(rows, category_filter, payment_filter, expense_type_filter)
            missing = apply_common_filters(unresolved, category_filter, payment_filter, expense_type_filter)
            amount = None if read_failed or missing else sum(row["amount"] for row in filtered)
            start, end = financial_range_for_month(month)
            points.append({
                "month": month, "label": labels[month_index], "year": year, "amount": amount,
                "selected": offset == 0, "open_month": start <= today <= end,
                "range": f"{start:%d/%m/%Y} – {end:%d/%m/%Y}",
            })
        largest = max((point["amount"] or 0 for point in points), default=0)
        for point in points:
            point["bar_percent"] = round(max(0, point["amount"] or 0) / largest * 100, 2) if largest > 0 else 0
        current, previous = points[0]["amount"], points[1]["amount"]
        change = current - previous if current is not None and previous is not None else None
        category_comparison = {"label": comparison_name, "points": points, "change": change}

    # ---------------------------------------------------------
    # פילטרים
    # ---------------------------------------------------------
    expenses_for_display = apply_common_filters(
        all_month_expenses,
        category_filter=category_filter,
        payment_filter=payment_filter,
        expense_type_filter=expense_type_filter,
    )

    # ---------------------------------------------------------
    # חלוקה לקבוצות לפי סוג
    # ---------------------------------------------------------
    single_expenses_reports = sort_expenses_by_display_date_desc(
        [e for e in expenses_for_display if e.get("expense_type") == "single"]
    )
    installment_expenses_reports = sort_expenses_by_display_date_desc(
        [e for e in expenses_for_display if e.get("expense_type") == "installments"]
    )
    fixed_expenses_reports = sort_expenses_by_display_date_desc(
        [e for e in expenses_for_display if e.get("expense_type") == "standing"]
    )

    single_total_reports = sum(e.get("amount", 0) for e in single_expenses_reports)
    installment_total_reports = sum(e.get("amount", 0) for e in installment_expenses_reports)
    fixed_total_reports = sum(e.get("amount", 0) for e in fixed_expenses_reports)

    # ---------------------------------------------------------
    # סיכומי קטגוריות
    # ---------------------------------------------------------
    totals_by_cat = {}
    expenses_by_category = {}
    for e in expenses_for_display:
        cat = e.get("category") or "ללא קטגוריה"
        totals_by_cat[cat] = totals_by_cat.get(cat, 0) + e.get("amount", 0)
        if cat not in expenses_by_category:
            expenses_by_category[cat] = []
        expenses_by_category[cat].append(e)

    category_rows = [
        {
            "category": cat,
            "spent": spent,
            "budget": budgets_map.get(cat, 0),
            "diff": budgets_map.get(cat, 0) - spent,
        }
        for cat, spent in totals_by_cat.items()
    ]

    # קיבוץ לפי אמצעי תשלום
    expenses_by_payment = {}
    for e in expenses_for_display:
        method = e.get("payment_method") or "לא צוין"
        if method not in expenses_by_payment:
            expenses_by_payment[method] = []
        expenses_by_payment[method].append(e)

    payment_rows = build_payment_rows(expenses_for_display)

    summary = monthly_financial_summary(all_month_expenses, budgets, selected_month, unresolved_expenses)
    commitments_list = [e for e in all_month_expenses if e["expense_type"] != "single"]
    already_spent_list = [e for e in all_month_expenses if e["expense_type"] == "single"]
    monthly_budget = sum(val for cat, val in budgets_map.items() if cat not in (*INCOME_CATEGORIES, SAVINGS_GOAL_CATEGORY))
    summary.update(
        total_spent_filtered=sum(e["amount"] for e in expenses_for_display),
        monthly_budget=monthly_budget, total_budget=monthly_budget,
    )

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
        unresolved_expenses=unresolved_expenses,
        category_comparison=category_comparison,
        category_rows=category_rows,
        expenses_by_category=expenses_by_category,
        expenses_by_payment=expenses_by_payment,
        commitments_list=commitments_list,
        already_spent_list=already_spent_list,
        payment_rows=payment_rows,
        expenses=expenses_for_display,
        single_expenses=single_expenses_reports,
        installment_expenses=installment_expenses_reports,
        fixed_expenses=fixed_expenses_reports,
        single_total_reports=single_total_reports,
        installment_total_reports=installment_total_reports,
        fixed_total_reports=fixed_total_reports,
        display_range=display_range,
        active_tab="reports",
        now=now_local,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
