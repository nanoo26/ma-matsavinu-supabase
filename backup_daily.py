"""
סקריפט גיבוי יומי אוטומטי
מגבה את כל נתוני ההוצאות מ-Supabase לקבצים מקומיים
"""

import os
import json
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# טעינת משתני סביבה
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_API_KEY") or ""

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ חסרים משתני סביבה SUPABASE_URL או SUPABASE_KEY")
    exit(1)


def supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def create_backup_folder():
    """יצירת תיקיית גיבויים עם תאריך ושעה"""
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d_%H-%M")
    backup_folder = Path("backups") / timestamp
    backup_folder.mkdir(parents=True, exist_ok=True)
    return backup_folder


def backup_table(table_name, backup_folder):
    """גיבוי טבלה מסופבייס לקובץ JSON"""
    try:
        url = f"{SUPABASE_URL}/rest/v1/{table_name}"
        resp = requests.get(
            url,
            headers=supabase_headers(),
            params={"select": "*"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        
        # שמירה לקובץ JSON
        output_file = backup_folder / f"{table_name}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ {table_name}: {len(data)} רשומות נשמרו")
        return len(data)
        
    except Exception as e:
        print(f"❌ שגיאה בגיבוי {table_name}: {e}")
        return 0


def create_backup_summary(backup_folder, stats):
    """יצירת קובץ סיכום לגיבוי"""
    now = datetime.now()
    summary = {
        "backup_date": now.strftime("%Y-%m-%d"),
        "backup_time": now.strftime("%H:%M:%S"),
        "backup_timestamp": now.isoformat(),
        "tables": stats,
        "total_records": sum(stats.values()),
    }
    
    summary_file = backup_folder / "backup_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    # גם קובץ טקסט קריא
    readme_file = backup_folder / "README.txt"
    with open(readme_file, "w", encoding="utf-8") as f:
        f.write(f"גיבוי מ-Matsavinu\n")
        f.write(f"================\n\n")
        f.write(f"תאריך: {summary['backup_date']}\n")
        f.write(f"שעה: {summary['backup_time']}\n\n")
        f.write(f"טבלאות:\n")
        for table, count in stats.items():
            f.write(f"  - {table}: {count} רשומות\n")
        f.write(f"\nסה\"כ: {summary['total_records']} רשומות\n")


def cleanup_old_backups(keep_days=30):
    """מחיקת גיבויים ישנים (שומר רק X ימים אחרונים)"""
    backups_folder = Path("backups")
    if not backups_folder.exists():
        return
    
    now = datetime.now()
    deleted_count = 0
    
    for backup_dir in backups_folder.iterdir():
        if not backup_dir.is_dir():
            continue
        
        try:
            # ניתוח התאריך מהשם התיקייה
            dir_name = backup_dir.name
            backup_date_str = dir_name.split("_")[0]  # YYYY-MM-DD
            backup_date = datetime.strptime(backup_date_str, "%Y-%m-%d")
            
            # מחיקה אם ישן מדי
            days_old = (now - backup_date).days
            if days_old > keep_days:
                import shutil
                shutil.rmtree(backup_dir)
                deleted_count += 1
                print(f"🗑️  נמחק גיבוי ישן: {dir_name} (בן {days_old} ימים)")
                
        except Exception as e:
            print(f"⚠️  לא ניתן לעבד תיקייה: {backup_dir.name}")
    
    if deleted_count > 0:
        print(f"\n🧹 נמחקו {deleted_count} גיבויים ישנים")


def main():
    """הפעלת גיבוי מלא"""
    print("\n" + "="*50)
    print("🔄 מתחיל גיבוי יומי...")
    print("="*50 + "\n")
    
    # יצירת תיקיית גיבוי
    backup_folder = create_backup_folder()
    print(f"📁 תיקיית גיבוי: {backup_folder}\n")
    
    # גיבוי כל הטבלאות
    tables = {
        "expenses": "הוצאות",
        "budgets": "תקציבים",
        "payment_plans": "תוכניות תשלומים",
    }
    
    stats = {}
    for table_name, hebrew_name in tables.items():
        print(f"📊 מגבה {hebrew_name} ({table_name})...")
        count = backup_table(table_name, backup_folder)
        stats[table_name] = count
    
    # יצירת סיכום
    create_backup_summary(backup_folder, stats)

    # גיבוי ZIP של כל תיקיית הפרויקט
    print("\n📦 יוצר ZIP של כל תיקיית הפרויקט...")
    import zipfile
    project_root = Path(__file__).parent.resolve()
    zip_name = f"ma-matsavinu-backup-{datetime.now().strftime('%Y-%m-%d_%H-%M')}.zip"
    zip_path = backup_folder / zip_name
    exclude_dirs = {"backups"}
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for foldername, subfolders, filenames in os.walk(project_root):
            rel_folder = os.path.relpath(foldername, project_root)
            # מדלג על תיקיית backups וכל תת-תיקיה שלה
            if any(part in exclude_dirs for part in Path(rel_folder).parts):
                continue
            for filename in filenames:
                file_path = Path(foldername) / filename
                rel_path = os.path.relpath(file_path, project_root)
                zipf.write(file_path, arcname=rel_path)
    print(f"✅ נוצר ZIP מלא: {zip_path}")
    
    print("\n" + "="*50)
    print(f"✅ גיבוי הושלם בהצלחה!")
    print(f"📂 מיקום: {backup_folder.absolute()}")
    print(f"📊 סה\"כ רשומות: {sum(stats.values())}")
    print("="*50 + "\n")
    
    # ניקוי גיבויים ישנים
    print("🧹 בודק גיבויים ישנים...")
    cleanup_old_backups(keep_days=30)
    
    print("\n✨ הכל מוכן!\n")


if __name__ == "__main__":
    main()
