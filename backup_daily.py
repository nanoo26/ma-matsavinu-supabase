"""
סקריפט גיבוי יומי אוטומטי
מגבה את כל נתוני ההוצאות מ-Supabase לקבצים מקומיים
"""

import os
import json
import re
import requests
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

PAGE_SIZE = 1000

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
    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S-%f")
    backup_folder = Path("backups") / timestamp
    backup_folder.mkdir(parents=True, exist_ok=False)
    return backup_folder


def backup_table(table_name, backup_folder):
    """גיבוי כל העמודים; כשל או תשובה חלקית אינם גיבוי מוצלח."""
    url = f"{SUPABASE_URL}/rest/v1/{table_name}"
    headers = supabase_headers()
    headers["Prefer"] = "count=exact"
    data = []
    expected_count = None
    last_id = None

    while True:
        offset = len(data)
        resp = requests.get(
            url,
            headers=headers,
            params={"select": "*", "order": "id.asc", "limit": PAGE_SIZE, "offset": offset},
            timeout=30,
        )
        resp.raise_for_status()
        page = resp.json()
        content_range = re.fullmatch(r"(?:(\d+)-(\d+)|\*)/(\d+)", resp.headers.get("Content-Range", ""))
        if not isinstance(page, list) or not content_range or len(page) > PAGE_SIZE:
            raise ValueError("Invalid backup page or missing exact count")

        total = int(content_range.group(3))
        if expected_count is None:
            expected_count = total
        if total != expected_count:
            raise ValueError("Table count changed during backup")
        if page:
            start, end = content_range.group(1, 2)
            if start is None or int(start) != offset or int(end) != offset + len(page) - 1:
                raise ValueError("Unexpected backup range")
        elif total != offset or content_range.group(1) is not None:
            raise ValueError("Backup ended before all rows were received")

        for row in page:
            row_id = row.get("id") if isinstance(row, dict) else None
            if type(row_id) is not int or (last_id is not None and row_id <= last_id):
                raise ValueError("Missing, duplicate or unordered backup ID")
            last_id = row_id
        data.extend(page)
        if len(data) > expected_count:
            raise ValueError("Backup exceeds the reported count")
        if len(data) == expected_count:
            break

    output_file = backup_folder / f"{table_name}.json"
    temporary_file = output_file.with_suffix(".json.part")
    with open(temporary_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    temporary_file.replace(output_file)
    print(f"✅ {table_name}: {len(data)} רשומות נשמרו")
    return len(data)


def create_code_archive(backup_folder):
    """ארכיון קבצי Git מנוהלים בלבד, ללא קבצי סודות או נתוני גיבוי."""
    project_root = Path(__file__).parent.resolve()
    tracked = subprocess.run(
        ["git", "-C", str(project_root), "ls-files", "-z"],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout.decode("utf-8").split("\0")
    excluded_dirs = {
        "backups", "backup", "archive", "old", ".git", ".fly", ".aws", ".ssh",
        ".codex", ".agents", ".venv", "venv", "env", "__pycache__", "node_modules",
        "secrets", "credentials",
    }
    excluded_suffixes = {
        ".pem", ".key", ".p12", ".pfx", ".keystore", ".db", ".sqlite", ".sqlite3",
        ".csv", ".log", ".zip", ".bak", ".backup", ".pyc", ".pyo",
    }
    excluded_names = {
        "setup_and_deploy.bat", "quick_deploy.bat", ".netrc", ".npmrc", ".pypirc",
        "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
    }
    zip_path = backup_folder / f"ma-matsavinu-backup-{backup_folder.name}.zip"
    temporary_zip = zip_path.with_suffix(".zip.part")
    archived_count = 0
    with zipfile.ZipFile(temporary_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
        for name in tracked:
            if not name:
                continue
            relative = Path(name)
            parts = [part.lower() for part in relative.parts]
            filename = parts[-1]
            if relative.is_absolute() or ".." in parts:
                raise ValueError("Invalid archive path")
            if (
                any(part in excluded_dirs for part in parts[:-1])
                or filename in excluded_names
                or filename.startswith(".env")
                or any(word in filename for word in ("secret", "credential", "token"))
                or relative.suffix.lower() in excluded_suffixes
            ):
                continue
            file_path = project_root / relative
            if file_path.is_symlink() or any((project_root / parent).is_symlink() for parent in relative.parents):
                continue
            if not file_path.resolve().is_relative_to(project_root):
                continue
            if not file_path.is_file():
                raise ValueError("Tracked archive file is missing")
            zipf.write(file_path, arcname=relative.as_posix())
            archived_count += 1
        if not archived_count:
            raise ValueError("No safe tracked files to archive")
    temporary_zip.replace(zip_path)
    return zip_path


def create_backup_summary(backup_folder, stats):
    """יצירת קובץ סיכום לגיבוי"""
    now = datetime.now()
    summary = {
        "backup_date": now.strftime("%Y-%m-%d"),
        "backup_time": now.strftime("%H:%M:%S"),
        "backup_timestamp": now.isoformat(),
        "status": "complete",
        "tables": stats,
        "total_records": sum(stats.values()),
    }
    
    summary_file = backup_folder / "backup_summary.json"
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

    # הסיכום מתפרסם אחרון, כדי ששחזור לא יזהה גיבוי חלקי כמושלם.
    temporary_summary = summary_file.with_suffix(".json.part")
    with open(temporary_summary, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    temporary_summary.replace(summary_file)


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
    
    try:
        backup_folder = create_backup_folder()
        print(f"📁 תיקיית גיבוי: {backup_folder}\n")
        tables = {
            "expenses": "הוצאות",
            "budgets": "תקציבים",
            "payment_plans": "תוכניות תשלומים",
        }
        stats = {}
        for table_name, hebrew_name in tables.items():
            print(f"📊 מגבה {hebrew_name} ({table_name})...")
            stats[table_name] = backup_table(table_name, backup_folder)

        print("\n📦 יוצר ארכיון קוד מנוהל ללא קבצי סודות...")
        zip_path = create_code_archive(backup_folder)
        create_backup_summary(backup_folder, stats)
        print(f"✅ נוצר ארכיון קוד: {zip_path}")
    except Exception as exc:
        # אין להדפיס תשובות API, נתונים או פרטי credentials מתוך החריגה.
        print(f"❌ הגיבוי נכשל ולא סומן כמושלם ({type(exc).__name__}).")
        return 1
    
    print("\n" + "="*50)
    print(f"✅ גיבוי הושלם בהצלחה!")
    print(f"📂 מיקום: {backup_folder.absolute()}")
    print(f"📊 סה\"כ רשומות: {sum(stats.values())}")
    print("="*50 + "\n")
    
    # ניקוי גיבויים ישנים
    print("🧹 בודק גיבויים ישנים...")
    try:
        cleanup_old_backups(keep_days=30)
    except OSError:
        print("⚠️ הגיבוי הושלם, אך ניקוי גיבויים ישנים נכשל.")
    
    print("\n✨ הכל מוכן!\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
