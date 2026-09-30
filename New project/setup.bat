@echo off
REM Run this ONCE on every new computer, right after copying the project
REM here (see note below about what NOT to copy). It builds fresh virtual
REM environments and installs dependencies using whatever Python/Node.js
REM are already installed on THIS machine - it does not install Python or
REM Node itself, and does not download anything except the pip/npm
REM packages this project needs.
REM
REM IMPORTANT - why this script exists:
REM Python virtual environments (the "venv" folders) are NOT portable.
REM They hardcode the exact path of the Python install that created them.
REM If you zip this whole project (including backend\venv and
REM desktop-agent\venv) and copy it to a different computer, those venvs
REM will be broken there, even though the files are all present - that's
REM the "No Python at ..." error. The fix is to delete/exclude the venv
REM folders before moving the project, and run this script fresh on the
REM new machine instead. This script is safe to re-run any time - it only
REM rebuilds the venv/node_modules folders, never touches your .env files,
REM database, or captured screenshots.

cd /d "%~dp0"

REM Pass --auto (used by run.bat) to skip "press any key" prompts so setup
REM can complete without anyone needing to interact with this window.
set "AUTO_MODE="
if /I "%~1"=="--auto" set "AUTO_MODE=1"

echo === Org Tracker: one-time setup for this computer ===
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: "python" was not found on PATH.
    echo Install Python 3.11+ from python.org first ^(check "Add python.exe to PATH"
    echo during install^), open a NEW PowerShell/Command Prompt window, then re-run this script.
    if not defined AUTO_MODE pause
    exit /b 1
)

REM The pinned backend dependencies do not yet provide native wheels for
REM Python 3.14. Prefer the installed Python 3.12 runtime when available.
set "PYTHON_CMD=python"
py -3.12 --version >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py -3.12"

where node >nul 2>nul
if errorlevel 1 (
    echo ERROR: "node"/"npm" was not found on PATH.
    echo Install Node.js LTS from nodejs.org first, open a NEW PowerShell/Command
    echo Prompt window, then re-run this script.
    if not defined AUTO_MODE pause
    exit /b 1
)

echo --- Backend ---
if exist "backend\venv" (
    echo Stopping any running Org Tracker processes which may still hold the backend\venv open...
    call "%~dp0stop-all.bat" >nul 2>nul
    echo Removing existing backend\venv so it's rebuilt fresh for this computer...
    rmdir /s /q "backend\venv"
    if exist "backend\venv" (
        echo ERROR: backend\venv is still locked by another process. Close any Python,
        echo VS Code, or terminal windows using this project and run setup.bat again.
        if not defined AUTO_MODE pause
        exit /b 1
    )
)
%PYTHON_CMD% -m venv "backend\venv"
if errorlevel 1 (
    echo ERROR: failed to create backend\venv. See the error above.
    if not defined AUTO_MODE pause
    exit /b 1
)
"backend\venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r "backend\requirements.txt"
if errorlevel 1 (
    echo ERROR: failed to install backend dependencies. See the error above.
    if not defined AUTO_MODE pause
    exit /b 1
)
if not exist "backend\.env" (
    copy "backend\.env.example" "backend\.env" >nul
    echo Created backend\.env from the template - edit it if you need non-default settings.
)

echo.
echo --- Desktop agent ---
if exist "desktop-agent\venv" (
    echo Stopping any running Org Tracker processes which may still hold the desktop-agent\venv open...
    call "%~dp0stop-all.bat" >nul 2>nul
    echo Removing existing desktop-agent\venv so it's rebuilt fresh for this computer...
    rmdir /s /q "desktop-agent\venv"
    if exist "desktop-agent\venv" (
        echo ERROR: desktop-agent\venv is still locked by another process. Close any Python,
        echo VS Code, or terminal windows using this project and run setup.bat again.
        if not defined AUTO_MODE pause
        exit /b 1
    )
)
%PYTHON_CMD% -m venv "desktop-agent\venv"
if errorlevel 1 (
    echo ERROR: failed to create desktop-agent\venv. See the error above.
    if not defined AUTO_MODE pause
    exit /b 1
)
"desktop-agent\venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r "desktop-agent\requirements.txt"
if errorlevel 1 (
    echo ERROR: failed to install desktop-agent dependencies. See the error above.
    if not defined AUTO_MODE pause
    exit /b 1
)
if not exist "desktop-agent\.env" (
    copy "desktop-agent\.env.example" "desktop-agent\.env" >nul
    echo Created desktop-agent\.env from the template - edit it if BACKEND_URL needs to change.
)

echo.
echo --- Frontend ---
pushd frontend
call npm install
if errorlevel 1 (
    echo ERROR: npm install failed. See the error above.
    popd
    if not defined AUTO_MODE pause
    exit /b 1
)
popd
if not exist "frontend\.env" (
    copy "frontend\.env.example" "frontend\.env" >nul
    echo Created frontend\.env from the template - edit it if VITE_BACKEND_URL needs to change.
)

echo.
echo --- Keeping the backend port in sync everywhere ---
REM backend\.env is the ONLY place the port is ever set. This makes sure
REM desktop-agent\.env and frontend\.env always point at that SAME port,
REM on every computer, regardless of what port ends up used here - this
REM runs every time setup.bat runs, not just on first creation, so it
REM self-heals even if backend\.env's PORT is changed later. It only ever
REM touches a "http://localhost:<port>" pattern - a custom production URL
REM (a real domain, no port) is left completely untouched.
set "PORT=8000"
if exist "backend\.env" (
    for /f "usebackq tokens=1,2 delims==" %%A in ("backend\.env") do (
        if /I "%%A"=="PORT" set "PORT=%%B"
    )
)
echo Backend port: %PORT%
powershell -NoProfile -Command "(Get-Content 'desktop-agent\.env') -replace 'http://localhost:\d+', 'http://localhost:%PORT%' | Set-Content 'desktop-agent\.env'"
powershell -NoProfile -Command "(Get-Content 'frontend\.env') -replace 'http://localhost:\d+', 'http://localhost:%PORT%' | Set-Content 'frontend\.env'"

echo.
echo === Setup complete for this computer ===
echo.
echo Ensuring the PostgreSQL database and tables are ready for this project.
pushd "backend"
"venv\Scripts\python.exe" -c "from app.database import engine; from app import models; models.Base.metadata.create_all(bind=engine); print('PostgreSQL schema ready')"
set "SCHEMA_EXIT=%ERRORLEVEL%"
popd
if not "%SCHEMA_EXIT%"=="0" (
    echo ERROR: could not initialize the backend database schema.
    if not defined AUTO_MODE pause
    exit /b %SCHEMA_EXIT%
)
echo If the first admin account has not been created yet, run:
    echo   backend\venv\Scripts\python.exe backend\create_admin.py
    echo.
echo You can now use start-all.bat ^(visible windows^) or start-all-background.vbs
echo ^(silent, no windows^) to run the tracker. Run install-local-autostart.bat if
echo you want it to start automatically every time this Windows user logs in.
if not defined AUTO_MODE pause