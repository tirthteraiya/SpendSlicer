@echo off
REM Run SpendSlicer from a source checkout: create a venv, install, serve.
REM Prefer the desktop build or `pip install spendslicer[web,cur]` for normal use.
cd /d "%~dp0"
echo ============================================
echo   SpendSlicer
echo ============================================
echo.

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH.
    pause
    exit /b 1
)

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if %errorlevel% neq 0 (
    echo ERROR: Python 3.10 or newer is required.
    pause
    exit /b 1
)

if not exist "venv\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 exit /b 1
)
if not exist "venv\Scripts\python.exe" (
    echo ERROR: venv is not a Windows virtual environment. Remove it and rerun.
    exit /b 1
)

echo Installing dependencies...
"venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
if errorlevel 1 exit /b 1
"venv\Scripts\python.exe" -m pip install --quiet -e ".[web,cur]"
if errorlevel 1 exit /b 1

echo.
echo Starting SpendSlicer. Your local browser connects automatically.
echo Your default browser opens after the server starts.
echo Press Ctrl+C to stop.
echo.
"venv\Scripts\spendslicer.exe" %*
