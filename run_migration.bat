@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo Running Path Migration Script...
echo Pythonアプリ -> Python.app
echo ==========================================

if not exist "env\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found.
    pause
    exit /b
)

env\Scripts\python.exe migrate_paths.py

echo.
echo Processing completed.
pause
