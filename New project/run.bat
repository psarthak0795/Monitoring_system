@echo off
REM ============================================================
REM  THE ONE FILE TO RUN. Double-click this and Org Tracker starts.
REM
REM  First time on a computer: automatically builds what's needed
REM  (venvs + dependencies) and installs Windows autostart, which takes a
REM  minute or two.
REM  Every time after that: starts in a few seconds, silently,
REM  with no visible windows (check the system tray for the agent).
REM ============================================================

cd /d "%~dp0"

set "TRACKER_ALREADY_RUNNING="
set "PORT=8000"
set "DASHBOARD_PORT=5173"
if exist "backend\.env" (
    for /f "usebackq tokens=1,2 delims==" %%A in ("backend\.env") do (
        if /I "%%A"=="PORT" set "PORT=%%B"
    )
)
set "TRACKER_BACKEND_PORT=%PORT%"
set "TRACKER_DASHBOARD_PORT=%DASHBOARD_PORT%"

REM Install desktop-agent requirements before the already-running check so
REM newly pulled packages such as pynput are never skipped.
if exist "desktop-agent\venv\Scripts\python.exe" (
    "desktop-agent\venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r "desktop-agent\requirements.txt"
    if errorlevel 1 (
        echo ERROR: failed to install desktop-agent requirements.
        pause
        exit /b 1
    )
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -EncodedCommand ZgB1AG4AYwB0AGkAbwBuACAAUgBlAGEAZAAtAFUAcgBsACgAJAB1AHIAbAApACAAewAKACAAIAAgACAAdAByAHkAIAB7AAoAIAAgACAAIAAgACAAIAAgACQAcgBlAHEAdQBlAHMAdAAgAD0AIABbAE4AZQB0AC4AVwBlAGIAUgBlAHEAdQBlAHMAdABdADoAOgBDAHIAZQBhAHQAZQAoACQAdQByAGwAKQAKACAAIAAgACAAIAAgACAAIAAkAHIAZQBxAHUAZQBzAHQALgBUAGkAbQBlAG8AdQB0ACAAPQAgADEAMAAwADAACgAgACAAIAAgACAAIAAgACAAJAByAGUAcwBwAG8AbgBzAGUAIAA9ACAAJAByAGUAcQB1AGUAcwB0AC4ARwBlAHQAUgBlAHMAcABvAG4AcwBlACgAKQAKACAAIAAgACAAIAAgACAAIAAkAHIAZQBhAGQAZQByACAAPQAgAE4AZQB3AC0ATwBiAGoAZQBjAHQAIABJAE8ALgBTAHQAcgBlAGEAbQBSAGUAYQBkAGUAcgAoACQAcgBlAHMAcABvAG4AcwBlAC4ARwBlAHQAUgBlAHMAcABvAG4AcwBlAFMAdAByAGUAYQBtACgAKQApAAoAIAAgACAAIAAgACAAIAAgACQAdABlAHgAdAAgAD0AIAAkAHIAZQBhAGQAZQByAC4AUgBlAGEAZABUAG8ARQBuAGQAKAApAAoAIAAgACAAIAAgACAAIAAgACQAcgBlAGEAZABlAHIALgBDAGwAbwBzAGUAKAApAAoAIAAgACAAIAAgACAAIAAgACQAcgBlAHMAcABvAG4AcwBlAC4AQwBsAG8AcwBlACgAKQAKACAAIAAgACAAIAAgACAAIAByAGUAdAB1AHIAbgAgACQAdABlAHgAdAAKACAAIAAgACAAfQAgAGMAYQB0AGMAaAAgAHsACgAgACAAIAAgACAAIAAgACAAcgBlAHQAdQByAG4AIAAnACcACgAgACAAIAAgAH0ACgB9AAoACgAkAGIAYQBjAGsAZQBuAGQAUABvAHIAdAAgAD0AIAA4ADAAMAAwAAoAJABkAGEAcwBoAGIAbwBhAHIAZABQAG8AcgB0ACAAPQAgADUAMQA3ADMACgBbAGkAbgB0AF0AOgA6AFQAcgB5AFAAYQByAHMAZQAoACQAZQBuAHYAOgBUAFIAQQBDAEsARQBSAF8AQgBBAEMASwBFAE4ARABfAFAATwBSAFQALAAgAFsAcgBlAGYAXQAkAGIAYQBjAGsAZQBuAGQAUABvAHIAdAApACAAfAAgAE8AdQB0AC0ATgB1AGwAbAAKAFsAaQBuAHQAXQA6ADoAVAByAHkAUABhAHIAcwBlACgAJABlAG4AdgA6AFQAUgBBAEMASwBFAFIAXwBEAEEAUwBIAEIATwBBAFIARABfAFAATwBSAFQALAAgAFsAcgBlAGYAXQAkAGQAYQBzAGgAYgBvAGEAcgBkAFAAbwByAHQAKQAgAHwAIABPAHUAdAAtAE4AdQBsAGwACgAKACQAaABlAGEAbAB0AGgAIAA9ACAAUgBlAGEAZAAtAFUAcgBsACAAIgBoAHQAdABwADoALwAvADEAMgA3AC4AMAAuADAALgAxADoAJABiAGEAYwBrAGUAbgBkAFAAbwByAHQALwBoAGUAYQBsAHQAaAAiAAoAaQBmACAAKAAkAGgAZQBhAGwAdABoACAALQBtAGEAdABjAGgAIAAnACIAcwB0AGEAdAB1AHMAIgBcAHMAKgA6AFwAcwAqACIAbwBrACIAJwApACAAewAgAGUAeABpAHQAIAAwACAAfQAKAAoAJABkAGEAcwBoAGIAbwBhAHIAZAAgAD0AIABSAGUAYQBkAC0AVQByAGwAIAAiAGgAdABwADoALwAvADEAMgA3AC4AMAAuADAALgAxADoAJABkAGEAcwBoAGIAbwBhAHIAZABQAG8AcgB0AC8AIgAKAGkAZgAgACgAJABkAGEAcwBoAGIAbwBhAHIAZAAgAC0AbABpAGsAZQAgACcAKgA8AHQAaQB0AGwAZQA+AE8AcgBnACAAVAByAGEAYwBrAGUAcgA8AC8AdABpAHQAbABlAD4AKgAnACkAIAB7ACAAZQB4AGkAdAAgADAAIAB9AAoACgBlAHgAaQB0ACAAMQA= >nul 2>nul
if not errorlevel 1 set "TRACKER_ALREADY_RUNNING=1"

if "%TRACKER_ALREADY_RUNNING%"=="1" (
    REM Stop the existing tracker before starting a fresh instance.
    echo Org Tracker is already running - stopping it before restart...
    call "%~dp0stop-all.bat" >nul 2>nul
    timeout /t 2 >nul 2>nul

    if not exist "%APPDATA%\OrgTracker" mkdir "%APPDATA%\OrgTracker" >nul 2>nul
    type nul > "%APPDATA%\OrgTracker\start_tracking.request"
    call "%~dp0start-all-background.bat"
    echo Org Tracker was restarted with your latest changes.
    echo.
    exit /b 0
)

set "NEED_SETUP="
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "AUTOSTART_SHORTCUT=%STARTUP_DIR%\OrgTrackerLocal.lnk"

if not exist "backend\venv\Scripts\python.exe" set "NEED_SETUP=1"
if not exist "desktop-agent\venv\Scripts\python.exe" set "NEED_SETUP=1"
if not exist "frontend\node_modules" set "NEED_SETUP=1"

REM Even if the venv files exist, they may be broken (e.g. this project
REM folder was copied from a different computer). Check they actually run
REM - using the console python.exe, not pythonw.exe, so a broken venv
REM prints an error here instead of risking a silent blocking popup.
if not defined NEED_SETUP (
    "backend\venv\Scripts\python.exe" --version >nul 2>nul
    if errorlevel 1 set "NEED_SETUP=1"
)
if not defined NEED_SETUP (
    "desktop-agent\venv\Scripts\python.exe" --version >nul 2>nul
    if errorlevel 1 set "NEED_SETUP=1"
)

REM A copied venv can exist on disk but still be unusable here: the Python
REM executable may be missing, the venv may be stale, or the files may be locked
REM by an antivirus or a previous failed install. In those cases, rebuild from
REM scratch instead of trying to keep using the broken environment.
if not defined NEED_SETUP (
    "backend\venv\Scripts\python.exe" -c "import sys; print(sys.executable)" >nul 2>nul
    if errorlevel 1 set "NEED_SETUP=1"
)
if not defined NEED_SETUP (
    "desktop-agent\venv\Scripts\python.exe" -c "import sys; print(sys.executable)" >nul 2>nul
    if errorlevel 1 set "NEED_SETUP=1"
)

if defined NEED_SETUP (
    echo First run on this computer - setting up now, this only happens once
    echo and may take a minute or two. Please wait...
    echo.
    call "%~dp0setup.bat" --auto
    if errorlevel 1 (
        echo.
        echo Setup failed - see the messages above, fix the issue, and run
        echo run.bat again.
        pause
        exit /b 1
    )
    echo.
)

REM Keep an existing installation synchronized after pulling new requirements.
REM setup.bat creates fresh environments; this lightweight step updates them
REM without deleting the user's existing environment or configuration.
echo Checking Python and frontend requirements...
"backend\venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r "backend\requirements.txt"
if errorlevel 1 (
    echo The backend venv appears stale, broken, or locked by Windows.
    echo Rebuilding the backend environment from scratch so the project works
    echo correctly on this machine.
    call "%~dp0stop-all.bat" >nul 2>nul
    rmdir /s /q "backend\venv"
    if exist "backend\venv" (
        echo ERROR: backend\venv is still locked by another process.
        echo Close any Python, VS Code, or terminal windows using this project,
        echo then run run.bat again.
        pause
        exit /b 1
    )
    call "%~dp0setup.bat" --auto
    if errorlevel 1 (
        echo ERROR: failed to rebuild the backend environment.
        pause
        exit /b 1
    )
)
"desktop-agent\venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r "desktop-agent\requirements.txt"
if errorlevel 1 (
    echo The desktop-agent venv appears stale, broken, or locked by Windows.
    echo Rebuilding the desktop-agent environment from scratch.
    call "%~dp0stop-all.bat" >nul 2>nul
    rmdir /s /q "desktop-agent\venv"
    if exist "desktop-agent\venv" (
        echo ERROR: desktop-agent\venv is still locked by another process.
        echo Close any Python, VS Code, or terminal windows using this project,
        echo then run run.bat again.
        pause
        exit /b 1
    )
    call "%~dp0setup.bat" --auto
    if errorlevel 1 (
        echo ERROR: failed to rebuild the desktop-agent environment.
        pause
        exit /b 1
    )
)
pushd frontend
call npm install
set "FRONTEND_INSTALL_EXIT=%ERRORLEVEL%"
popd
if not "%FRONTEND_INSTALL_EXIT%"=="0" (
    echo ERROR: failed to install frontend requirements.
    pause
    exit /b %FRONTEND_INSTALL_EXIT%
)

if not exist "%AUTOSTART_SHORTCUT%" (
    echo Installing automatic startup for this Windows user...
    call "%~dp0install-local-autostart.bat"
    if errorlevel 1 (
        echo WARNING: automatic startup could not be installed.
        echo Run install-local-autostart.bat manually after fixing the issue.
    )
    echo.
)

echo Ensuring the PostgreSQL database and tables are ready...
pushd "backend"
"venv\Scripts\python.exe" -c "from app.database import engine; from app import models; models.Base.metadata.create_all(bind=engine); print('PostgreSQL schema ready')"
set "SCHEMA_EXIT=%ERRORLEVEL%"
popd
if not "%SCHEMA_EXIT%"=="0" (
    echo ERROR: could not initialize the backend database schema.
    echo Run setup.bat to install the backend dependencies, then run run.bat again.
    pause
    exit /b %SCHEMA_EXIT%
)

echo If you have not created the first admin account yet, run:
    echo   backend\venv\Scripts\python.exe backend\create_admin.py
    echo.

echo Starting Org Tracker...
call "%~dp0start-all-background.bat"

echo.
echo Org Tracker is now running in the background.
echo   Dashboard: http://localhost:5173
echo   Look for the tracker icon in the system tray.
echo   To stop it, run stop-all.bat.
echo.
echo This window will close automatically in a few seconds.
timeout /t 6 >nul 2>nul
