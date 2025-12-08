"""
סקריפט שחזור גיבוי
משחזר נתונים מתיקיית גיבוי חזרה ל-Supabase
"""

import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

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


def restore_table(table_name, backup_folder, clear_existing=False):
    """שחזור טבלה מגיבוי"""
    backup_file = backup_folder / f"{table_name}.json"
    
    if not backup_file.exists():
        print(f"⚠️  לא נמצא גיבוי עבור {table_name}")
        return 0
    
    with open(backup_file, encoding="utf-8") as f:
        data = json.load(f)
    
    if not data:
        print(f"⚠️  {table_name} ריק")
        return 0
    
    url = f"{SUPABASE_URL}/rest/v1/{table_name}"
    
    # מחיקת נתונים קיימים (אם נדרש)
    if clear_existing:
        confirm = input(f"⚠️  האם למחוק את כל הנתונים הקיימים ב-{table_name}? (yes/no): ")
        if confirm.lower() == "yes":
            try:
                # מחיקה לפי ID (נניח שיש ID)
                for record in data:
                    if "id" in record:
                        requests.delete(
                            url,
                            headers=supabase_headers(),
                            params={"id": f"eq.{record['id']}"},
                            timeout=10
                        )
                print(f"🗑️  נתונים קיימים נמחקו מ-{table_name}")
            except Exception as e:
                print(f"⚠️  שגיאה במחיקה: {e}")
    
    # הוספת הנתונים
    try:
        resp = requests.post(
            url,
            headers=supabase_headers(),
            json=data,
            timeout=30
        )
        
        if resp.ok:
            print(f"✅ {table_name}: {len(data)} רשומות שוחזרו")
            return len(data)
        else:
            print(f"❌ שגיאה בשחזור {table_name}: {resp.status_code}")
            print(f"   {resp.text}")
            return 0
            
    except Exception as e:
        print(f"❌ שגיאה בשחזור {table_name}: {e}")
        return 0


def main():
    """תפריט שחזור אינטראקטיבי"""
    print("\n" + "="*50)
    print("♻️  שחזור גיבוי - Ma Matsavinu")
    print("="*50 + "\n")
    
    # הצגת גיבויים זמינים
    backups = list_backups()
    
    if not backups:
        print("❌ לא נמצאו גיבויים")
        return
    
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
        if choice == 0 or choice > len(backups):
            print("בוטל.")
            return
        
        selected_backup = backups[choice - 1]
        
    except ValueError:
        print("❌ בחירה לא תקינה")
        return
    
    print(f"\n📂 נבחר: {selected_backup['name']}\n")
    
    # אישור
    confirm = input("⚠️  האם לשחזר את הגיבוי הזה? (yes/no): ")
    if confirm.lower() != "yes":
        print("בוטל.")
        return
    
    clear = input("האם למחוק נתונים קיימים לפני השחזור? (yes/no): ")
    clear_existing = (clear.lower() == "yes")
    
    # שחזור
    print("\n🔄 מתחיל שחזור...\n")
    
    tables = ["expenses", "budgets", "payment_plans"]
    stats = {}
    
    for table in tables:
        count = restore_table(table, selected_backup["path"], clear_existing)
        stats[table] = count
    
    print("\n" + "="*50)
    print("✅ שחזור הושלם!")
    print(f"📊 סה\"כ רשומות ששוחזרו: {sum(stats.values())}")
    print("="*50 + "\n")


if __name__ == "__main__":
    main()
