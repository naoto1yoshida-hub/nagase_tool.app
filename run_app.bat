@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo Starting Nagase Drawing Search Tool...
echo ==========================================

:: Check virtual environment
if not exist "%~dp0env\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found.
    echo %~dp0env\Scripts\python.exe
    pause
    exit /b
)

echo App is starting. Please wait for the browser to open...
"%~dp0env\Scripts\python.exe" -m streamlit run "%~dp0app.py"

if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to start application.
    pause
)
endlocal
