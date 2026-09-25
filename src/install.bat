@echo off
setlocal enabledelayedexpansion
title OBS Marker Tool - Automated Setup
cls

echo =====================================================================
echo                  OBS Studio Marker Tool - Installer
echo =====================================================================
echo.

where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Python 3.8+ was not detected in PATH!
    echo           The marker server daemon requires Python to run.
    echo           Please install Python from https://www.python.org/
    echo           and check "Add python.exe to PATH" during installation.
    echo.
)

set "TARGET_DIR=%APPDATA%\obs-studio\scripts\obs-marker-tool"

echo [*] Target Directory: %TARGET_DIR%
echo.

if not exist "%TARGET_DIR%" (
    echo [+] Creating scripts directory...
    mkdir "%TARGET_DIR%"
)

echo [+] Copying plugin files...
copy /Y "%~dp0index.html" "%TARGET_DIR%\" >nul
copy /Y "%~dp0server.py" "%TARGET_DIR%\" >nul
copy /Y "%~dp0marker_service.lua" "%TARGET_DIR%\" >nul
copy /Y "%~dp0run_silent.vbs" "%TARGET_DIR%\" >nul
copy /Y "%~dp0run.bat" "%TARGET_DIR%\" >nul
copy /Y "%~dp0stop.bat" "%TARGET_DIR%\" >nul

if %ERRORLEVEL% EQU 0 (
    echo [OK] Files installed successfully!
) else (
    echo [ERROR] Failed to copy files. Please check permissions.
    pause
    exit /b 1
)

echo.
echo =====================================================================
echo                     Next Steps in OBS Studio
echo =====================================================================
echo.
echo 1. Add Lua Service:
echo    - Open OBS Studio.
echo    - Go to: Tools -^> Scripts.
echo    - Click '+' and select:
echo      %TARGET_DIR%\marker_service.lua
echo.
echo 2. Add Custom Browser Dock:
echo    - In OBS, go to: Docks -^> Custom Browser Docks...
echo    - Dock Name: Marker Tool
echo    - URL: http://127.0.0.1:8765/
echo    - Click Apply and dock the panel above or below your controls.
echo.
echo 3. Bind In-Game Hotkey:
echo    - In OBS, go to: Settings -^> Hotkeys.
echo    - Search for: "Marker Tool: Freeze Timestamp".
echo    - Set your preferred hotkey (or key combination).
echo.
echo =====================================================================
echo.
set /p OPEN_EXPLORER="Open installation folder in Windows Explorer? (Y/N): "
if /i "!OPEN_EXPLORER!"=="Y" (
    start "" explorer.exe "%TARGET_DIR%"
)

echo.
echo Installation complete. Happy recording!
timeout /t 5 >nul
