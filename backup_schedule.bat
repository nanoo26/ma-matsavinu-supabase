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
set "backup_exit_code=%errorlevel%"

REM רישום לקובץ לוג
if "%backup_exit_code%"=="0" (
    echo Backup completed at %date% %time% >> backup_log.txt
) else (
    echo Backup FAILED at %date% %time% ^(exit %backup_exit_code%^) >> backup_log.txt
)

REM סגירה
call deactivate
exit /b %backup_exit_code%
