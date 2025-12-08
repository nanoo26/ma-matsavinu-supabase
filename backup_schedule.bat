@echo off
REM סקריפט להפעלת גיבוי יומי אוטומטי
REM הפעל אותו דרך Task Scheduler של Windows

cd /d "%~dp0"

REM הפעלת הסביבה הוירטואלית
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else (
    echo ERROR: Virtual environment not found
    exit /b 1
)

REM הרצת סקריפט הגיבוי
python backup_daily.py

REM רישום לקובץ לוג
echo Backup completed at %date% %time% >> backup_log.txt

REM סגירה
deactivate
