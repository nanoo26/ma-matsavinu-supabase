from flask import Flask, render_template, request, redirect, url_for
import os
import requests
from datetime import datetime, date, timedelta

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
PAYMENT_PLANS_TABLE = "payment_plans"
PAYMENT_PLANS_URL = f"{SUPABASE_URL}/rest/v1/{PAYMENT_PLANS_TABLE}"
SUPABASE_EXPENSES_URL = f"{SUPABASE_URL}/rest/v1/{SUPABASE_EXPENSES_TABLE}"
SUPABASE_BUDGETS_URL = f"{SUPABASE_URL}/rest/v1/{SUPABASE_BUDGETS_TABLE}"


def supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }

def insert_payment_plan(payload: dict) -> bool:
    """הכנסת הוראת קבע / תשלומים ל payment_plans."""
    try:
        resp = requests.post(
            PAYMENT_PLANS_URL,
            headers=supabase_headers(),
            params={"select": "*"},
            json=payload,
            timeout=10,
        )
        if not resp.ok:
            print("=== Supabase PAYMENT_PLAN INSERT ERROR ===")
            print("Status:", resp.status_code)
            try:
                print("Body:", resp.json())
            except Exception:
                print("Raw text:", resp.text)
            resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print("שגיאה בהוספת תוכנית תשלום ל Supabase:", e)
        return False
    return True

def fetch_payment_plans_for_month(selected_month: str):
    """
    מחזיר רשימת 'הוצאות וירטואליות' מחושבות מהוראות קבע ותשלומים
    עבור חודש בפורמט YYYY-MM.
    כל רשומה יחידה מייצגת תשלום אחד בחודש.
    """
    try:
        resp = requests.get(
            PAYMENT_PLANS_URL,
            headers=supabase_headers(),
            params={
                "select": "*",
                "is_active": "eq.true",
            },
            timeout=10,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print("שגיאה בשליפת תוכניות תשלום מ Supabase:", e)
        return []

    data = resp.json()

    # selected_month בסגנון "2025-11"
    try:
        year_str, month_str = selected_month.split("-")
        year = int(year_str)
        month = int(month_str)
    except Exception:
        return []

    # נשתמש בתאריך 10 לחודש כתאריך תשלום וירטואלי
    month_first = date(year, month, 1)

    virtual_expenses = []

    for row in data:
        expense_type = (row.get("expense_type") or "standing").strip()

        start_str = row.get("start_date")
        if not start_str:
            continue

        try:
            start_dt = datetime.strptime(start_str, "%Y-%m-%d").date()
        except Exception:
            continue

        # אם החודש הנבחר לפני חודש ההתחלה - לא רלוונטי
        if month_first < start_dt.replace(day=1):
            continue

        # טיפול ב end_date אם קיים
        end_dt = None
        end_str = row.get("end_date")
        if end_str:
            try:
                end_dt = datetime.strptime(end_str, "%Y-%m-%d").date()
            except Exception:
                end_dt = None

        if end_dt and month_first > end_dt.replace(day=1):
            continue

        installments_count = row.get("installments_count")

        # אם זו רכישה בתשלומים - בודקים שלא עבר מספר התשלומים
        if expense_type == "installments" and installments_count:
            try:
                installments_count_int = int(installments_count)
            except Exception:
                installments_count_int = None

            if installments_count_int is not None:
                start_index = start_dt.year * 12 + start_dt.month
                current_index = year * 12 + month
                diff_months = current_index - start_index

                # diff_months מתחיל מ 0 בתשלום הראשון
                if diff_months < 0 or diff_months >= installments_count_int:
                    continue

        # סכום חודשי
        monthly_amount = row.get("monthly_amount")
        total_amount = row.get("total_amount")

        try:
            if monthly_amount is not None:
                amount_val = float(monthly_amount)
            elif total_amount is not None and installments_count:
                amount_val = float(total_amount) / float(installments_count)
            else:
                # אין לנו איך לחשב סכום
                continue
        except Exception:
            continue

        # תאריך לתצוגה DD/MM/YYYY
        display_date_str = f"10/{month:02d}/{year}"

        virtual_expenses.append(
            {
                "id": row.get("id"),
                "raw_date": f"{year}-{month:02d}-10",
                "date": display_date_str,
                "category": row.get("category") or "",
                "amount": amount_val,
                "payment_method": row.get("payment_method") or "",
                "notes": row.get("description") or "",
            }
        )

    return virtual_expenses


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


def current_month_key():
    today = date.today()
    return f"{today.year}-{today.month:02d}"

def previous_month_of(month_key: str) -> str:
    """
    מקבל מחרוזת בפורמט YYYY-MM ומחזיר את החודש הקודם באותו פורמט.
    אם יש בעיה בפענוח - מחזיר את המחרוזת כמו שהיא.
    """
    try:
        year_str, month_str = month_key.split("-")
        year = int(year_str)
        month = int(month_str)
    except Exception:
        return month_key

    month -= 1
    if month == 0:
        month = 12
        year -= 1

    return f"{year}-{month:02d}"


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
    amounts = [parse_amount(e.get("amount", 0)) for e in expenses_sorted]
    total_amount = sum(amounts)
    max_expense_amount = max(amounts) if amounts else 0

    # כרטיס סיכום עליון (אם תרצה להשתמש בו בהמשך)
    main_summary = {
        "month_key": current_month_key(),
        "spent_total": total_amount,
        "used_percent": 0,
    }

    # סיכום לפי קטגוריות לגרף העליון
    category_map: dict[str, float] = {}
    for e in expenses_sorted:
        cat = e.get("category") or "לא מסווג"
        amt = parse_amount(e.get("amount", 0))
        category_map[cat] = category_map.get(cat, 0.0) + amt

    top_categories = []
    if total_amount > 0:
        # מיון לפי סכום מהגבוה לנמוך
        sorted_items = sorted(
            category_map.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        # לוקחים רק שלוש קטגוריות ראשונות
        for idx, (cat, amt) in enumerate(sorted_items, start=1):
            if idx > 3:
                break
            top_categories.append(
                {
                    "category": cat,
                    "amount": amt,
                    "percent": (amt / total_amount) * 100,
                }
            )

    return render_template(
        "expenses.html",
        expenses=expenses_sorted,
        main_summary=main_summary,
        total_amount=total_amount,
        max_expense_amount=max_expense_amount,
        top_categories=top_categories,
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

def fetch_all_budgets():
    """שליפת כל התקציבים מטבלת budgets (אם קיימת)"""
    url = f"{SUPABASE_URL}/rest/v1/budgets?select=*"
    try:
        r = requests.get(url, headers=supabase_headers(), timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print("שגיאה בשליפת budgets מ-Supabase:", e)
        # אם אין טבלה או שיש שגיאה - נסתדר בלי תקציבים
        return []


@app.route("/reports")
def reports():
    # כל ההוצאות הקיימות (כמו למסך הראשי)
    all_db_expenses = fetch_expenses()

    # פונקציה לפירוק תאריך DD/MM/YYYY לחודש
    def month_key(date_str: str) -> str:
        try:
            dt = datetime.strptime(date_str, "%d/%m/%Y")
            return dt.strftime("%Y-%m")
        except Exception:
            return ""

    # רשימת כל החודשים שיש עבורם הוצאות
    month_set = set()
    for e in all_db_expenses:
        mk = month_key(e.get("date", ""))
        if mk:
            month_set.add(mk)
    months = sorted(month_set, reverse=True)

    if months:
        default_month = months[0]
    else:
        default_month = datetime.now().strftime("%Y-%m")

    selected_month = request.args.get("month") or default_month

    # הוצאות רגילות לחודש הנבחר
    month_expenses = [
        e for e in all_db_expenses
        if month_key(e.get("date", "")) == selected_month
    ]

    # הוצאות וירטואליות מהוראות קבע ותשלומים לחודש הנבחר
    plan_expenses = fetch_payment_plans_for_month(selected_month)

    # מחברים הכל לרשימה אחת שעל בסיסה נסכם את הכל
    all_expenses = month_expenses + plan_expenses

    # -----------------------------
    # תקציבים לחודש הנבחר
    # -----------------------------
    budgets_rows = fetch_budgets_for_month(selected_month)
    budgets_map = {}
    total_budget = 0.0

    for row in budgets_rows:
        cat = row.get("category") or "לא מסווג"
        amt = parse_amount(row.get("amount", 0))
        budgets_map[cat] = budgets_map.get(cat, 0.0) + amt
        total_budget += amt

    # -----------------------------
    # סיכום לפי קטגוריות
    # -----------------------------
    category_totals = {}
    for e in all_expenses:
        cat = e.get("category") or "לא מסווג"
        amt = parse_amount(e.get("amount", 0))
        category_totals[cat] = category_totals.get(cat, 0.0) + amt

    category_rows = []
    total_spent = 0.0

    for cat, spent in category_totals.items():
        total_spent += spent
        budget_cat = budgets_map.get(cat, 0.0)
        diff = budget_cat - spent
        percent = (spent / budget_cat * 100) if budget_cat > 0 else 0.0

        category_rows.append(
            {
                "category": cat,
                "budget": budget_cat,
                "spent": spent,
                "diff": diff,
                "percent": percent,
            }
        )

    # -----------------------------
    # סיכום עליון כללי
    # -----------------------------
    summary = {
        "total_budget": total_budget,
        "total_spent": total_spent,
        "total_diff": total_budget - total_spent,
        "total_percent": (total_spent / total_budget * 100) if total_budget > 0 else 0.0,
    }

    # -----------------------------
    # סיכום לפי אמצעי תשלום
    # -----------------------------
    payments_map = {}
    for e in all_expenses:
        pm = e.get("payment_method") or "לא ידוע"
        amt = parse_amount(e.get("amount", 0))
        payments_map[pm] = payments_map.get(pm, 0.0) + amt

    payment_rows = [
        {"method": m, "total": t} for m, t in payments_map.items()
    ]

    # -----------------------------
    # רשימת הוצאות מלאה לטבלת "כל ההוצאות בחודש"
    # -----------------------------
    report_expenses = []
    for e in all_expenses:
        report_expenses.append(
            {
                "date": e.get("date", ""),
                "category": e.get("category", ""),
                "note": (e.get("notes") or e.get("note") or ""),
                "payment_method": e.get("payment_method", ""),
                "amount": parse_amount(e.get("amount", 0)),
            }
        )

    # אם משום מה אין חודשים, שלא יישבר התפריט
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
        active_tab="reports",   # לא חובה כי ה־HTML משתמש ב-request.path, אבל זה נקי
    )

@app.route("/budget", methods=["GET", "POST"])
def budget():
    """מסך עריכת תקציב חודשי על בסיס טבלת budgets."""
    month_from_query = request.args.get("month")
    month_hidden = request.form.get("month") if request.method == "POST" else None

    # בחירת חודש נוכחי לעריכה:
    # - אם המשתמש בחר ידנית (GET/POST) - נכבד את הבחירה
    # - אחרת: עד ה־9 בחודש נציג את החודש הקודם, מה־10 ומעלה את החודש הנוכחי
    if month_from_query or month_hidden:
        selected_month = month_from_query or month_hidden
    else:
        today = date.today()
        if today.day < 10:
            # עדיין "מסיימים" את החודש הקודם
            first_of_this_month = date(today.year, today.month, 1)
            prev = first_of_this_month - timedelta(days=1)
            selected_month = f"{prev.year}-{prev.month:02d}"
        else:
            # מה־10 בחודש - מתחילים אוטומטית תקציב חדש
            selected_month = f"{today.year}-{today.month:02d}"

    # =========================
    # POST - שמירת התקציב לחודש
    # =========================
    if request.method == "POST":
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

    # =========================
    # GET - טעינת נתונים למסך
    # =========================

    # תקציב קיים לחודש הנבחר
    existing = fetch_budgets_for_month(selected_month)
    existing_map = {
        row.get("category"): float(row.get("amount") or 0)
        for row in existing
    }

    # תקציב של החודש הקודם (עבור החודש שנבחר במסך)
    prev_month = previous_month_of(selected_month)
    prev_existing = fetch_budgets_for_month(prev_month)
    prev_map = {
        row.get("category"): float(row.get("amount") or 0)
        for row in prev_existing
    }

    # בניית רשימת תקציבים למסך:
    # - אם אין ערך לחודש הנבחר ויש ערך לחודש הקודם -> נשתמש בערך של החודש הקודם כברירת מחדל
    budgets_for_template = []
    for cat in CATEGORIES:
        prev_amount = prev_map.get(cat, 0.0)
        current_amount = existing_map.get(cat)

        if current_amount is None:
            # אין שורה קיימת לחודש הזה - נמלא אוטומטית מהחודש הקודם (אם קיים)
            if prev_amount > 0:
                current_amount = prev_amount
            else:
                current_amount = 0.0

        budgets_for_template.append(
            {
                "category": cat,
                "amount": current_amount,
                "previous_amount": prev_amount,
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
