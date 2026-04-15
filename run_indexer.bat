@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo Nagase Drawing Indexer
echo ==========================================
echo.
echo Scanning drawing and process folders...
echo Building search index.
echo.

:: Check virtual environment
if not exist "%~dp0env\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found.
    echo %~dp0env\Scripts\python.exe
    pause
    exit /b
)

echo Starting indexing...
echo.
"%~dp0env\Scripts\python.exe" -m modules.indexer

echo.
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Indexing failed.
) else (
    echo Indexing completed successfully.
)
echo.
pause
endlocal
