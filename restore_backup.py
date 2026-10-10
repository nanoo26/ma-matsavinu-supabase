"""
סקריפט שחזור גיבוי
משחזר נתונים מתיקיית גיבוי חזרה ל-Supabase
"""

import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

TABLES = ("expenses", "budgets", "payment_plans")

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_API_KEY") or ""

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ חסרים משתני סביבה")
    exit(1)


def supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Prefer": "return=representation"
    }


def list_backups():
    """רשימת כל הגיבויים הזמינים"""
    backups_folder = Path("backups")
    if not backups_folder.exists():
        print("❌ לא נמצאה תיקיית גיבויים")
        return []
    
    backups = []
    for backup_dir in sorted(backups_folder.iterdir(), reverse=True):
        if backup_dir.is_dir():
            summary_file = backup_dir / "backup_summary.json"
            if summary_file.exists():
                with open(summary_file, encoding="utf-8") as f:
                    summary = json.load(f)
                backups.append({
                    "path": backup_dir,
                    "name": backup_dir.name,
                    "summary": summary
                })
    
    return backups


def load_backup_table(table_name, backup_folder):
    """קריאת קובץ תקין; קובץ חסר אינו טבלה ריקה."""
    if table_name not in TABLES:
        raise ValueError("Unknown restore table")
    backup_file = backup_folder / f"{table_name}.json"
    with open(backup_file, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Backup table must be a list")
    ids = [row.get("id") if isinstance(row, dict) else None for row in data]
    if any(type(row_id) is not int for row_id in ids) or len(set(ids)) != len(ids):
        raise ValueError("Missing or duplicate backup ID")
    return data


def validate_backup(backup_folder, summary):
    """בדיקת כל הקבצים והספירות לפני בקשת כתיבה ראשונה."""
    if summary.get("status", "complete") != "complete":
        raise ValueError("Backup is incomplete")
    counts = summary["tables"]
    for table in TABLES:
        count = counts[table]
        if type(count) is not int or count < 0 or len(load_backup_table(table, backup_folder)) != count:
            raise ValueError("Backup count does not match")
    total = summary["total_records"]
    if type(total) is not int or total != sum(counts[table] for table in TABLES):
        raise ValueError("Backup total does not match")


def response_ids(resp):
    """אימות תשובת return=representation בלי להציג את תוכנה."""
    resp.raise_for_status()
    if not 200 <= resp.status_code < 300:
        raise ValueError("Unexpected restore HTTP status")
    rows = resp.json()
    if not isinstance(rows, list):
        raise ValueError("Invalid restore response")
    ids = [row.get("id") if isinstance(row, dict) else None for row in rows]
    if any(type(row_id) is not int for row_id in ids) or len(set(ids)) != len(ids):
        raise ValueError("Invalid response IDs")
    return set(ids)


def restore_table(table_name, backup_folder, clear_existing=False):
    """שחזור טבלה; כשל מפסיק את התהליך במקום להחזיר אפס."""
    data = load_backup_table(table_name, backup_folder)
    if not data:
        print(f"✅ {table_name}: טבלה ריקה, לא נדרשת הוספה")
        return 0
    
    url = f"{SUPABASE_URL}/rest/v1/{table_name}"
    
    # מחיקת נתונים קיימים (אם נדרש)
    if clear_existing:
        confirm = input(f"⚠️  האם למחוק ב-{table_name} את הרשומות שמזהיהן בגיבוי? (yes/no): ")
        if confirm.lower() != "yes":
            raise RuntimeError("Restore cancelled before table deletion")
        # אותה מחיקה ממוקדת לפי מזהי הגיבוי; אין הרחבה למחיקת כל הטבלה.
        for record in data:
            resp = requests.delete(
                url,
                headers=supabase_headers(),
                params={"id": f"eq.{record['id']}"},
                timeout=10,
                allow_redirects=False
            )
            if not response_ids(resp).issubset({record["id"]}):
                raise ValueError("Unexpected deleted IDs")
        print(f"🗑️  הסתיימו בקשות המחיקה לפי מזהי הגיבוי ב-{table_name}")

    resp = requests.post(
        url,
        headers=supabase_headers(),
        json=data,
        timeout=30,
        allow_redirects=False
    )
    if response_ids(resp) != {row["id"] for row in data}:
        raise ValueError("Inserted IDs do not match backup")
    print(f"✅ {table_name}: {len(data)} רשומות שוחזרו")
    return len(data)


def main():
    """תפריט שחזור אינטראקטיבי"""
    print("\n" + "="*50)
    print("♻️  שחזור גיבוי - Ma Matsavinu")
    print("="*50 + "\n")
    
    # הצגת גיבויים זמינים
    try:
        backups = list_backups()
        for backup in backups:
            summary = backup["summary"]
            if not isinstance(summary, dict) or not {"backup_date", "backup_time", "total_records", "tables"}.issubset(summary):
                raise ValueError("Invalid backup summary")
    except Exception as exc:
        print(f"❌ לא ניתן לקרוא את רשימת הגיבויים ({type(exc).__name__}).")
        return 1
    
    if not backups:
        print("❌ לא נמצאו גיבויים")
        return 1
    
    print("גיבויים זמינים:\n")
    for i, backup in enumerate(backups, 1):
        summary = backup["summary"]
        print(f"{i}. {backup['name']}")
        print(f"   תאריך: {summary['backup_date']} | שעה: {summary['backup_time']}")
        print(f"   רשומות: {summary['total_records']}")
        print()
    
    # בחירת גיבוי
    try:
        choice = int(input("בחר מספר גיבוי לשחזור (0 לביטול): "))
        if choice == 0:
            print("בוטל.")
            return 0
        if choice < 1 or choice > len(backups):
            print("❌ בחירה לא תקינה")
            return 1
        
        selected_backup = backups[choice - 1]
        
    except ValueError:
        print("❌ בחירה לא תקינה")
        return 1
    
    print(f"\n📂 נבחר: {selected_backup['name']}\n")
    
    # אישור
    confirm = input("⚠️  האם לשחזר את הגיבוי הזה? (yes/no): ")
    if confirm.lower() != "yes":
        print("בוטל.")
        return 0
    
    clear = input("האם למחוק נתונים קיימים לפני השחזור? (yes/no): ")
    clear_existing = (clear.lower() == "yes")
    
    # שחזור
    print("\n🔄 מתחיל שחזור...\n")
    
    stats = {}
    try:
        validate_backup(selected_backup["path"], selected_backup["summary"])
        for table in TABLES:
            stats[table] = restore_table(table, selected_backup["path"], clear_existing)
    except Exception as exc:
        print(f"❌ השחזור נעצר ולא סומן כמושלם ({type(exc).__name__}).")
        print("⚠️ אם נשלחו בקשות כתיבה, ייתכן שנותר שחזור חלקי; אין להריץ שוב אוטומטית.")
        return 1
    
    print("\n" + "="*50)
    print("✅ שחזור הושלם!")
    print(f"📊 סה\"כ רשומות ששוחזרו: {sum(stats.values())}")
    print("="*50 + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
