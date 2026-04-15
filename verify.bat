@echo off
setlocal
cd /d "%~dp0"
echo Running Migration Status Check...
env\Scripts\python.exe check_db_status.py
if exist migration_report.txt (
    echo [RESULT] Found report file.
    type migration_report.txt
) else (
    echo [ERROR] Report file not found.
)
pause
