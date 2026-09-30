@echo off
setlocal enabledelayedexpansion
title OBS Marker Tool - Uninstaller
cls

echo =====================================================================
echo                 OBS Studio Marker Tool - Uninstaller
echo =====================================================================
echo.

set "TARGET_DIR=%APPDATA%\obs-studio\scripts\obs-marker-tool"

rem Safety assert: never wipe anything unless the path is exactly ours.
echo "%TARGET_DIR%" | find /I "obs-studio\scripts\obs-marker-tool" >nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Safety check failed. Refusing to delete "%TARGET_DIR%".
    pause
    exit /b 1
)

if not exist "%TARGET_DIR%" (
    echo [INFO] Nothing to remove: "%TARGET_DIR%" does not exist.
    timeout /t 3 >nul
    exit /b 0
)

echo [*] Stopping marker server...
call "%~dp0stop.bat" >nul 2>&1
rem taskkill is asynchronous: settle before deleting locked files.
timeout /t 2 /nobreak >nul

set /p KEEP_DATA="Keep config.json and presets.json for reinstall? (Y/N, default Y): "
if "!KEEP_DATA!"=="" set "KEEP_DATA=Y"

set "STAGING=%TEMP%\obs-marker-backup-%RANDOM%"
if /i "!KEEP_DATA!"=="Y" (
    echo [*] Staging user data...
    mkdir "%STAGING%" >nul 2>&1
    if exist "%TARGET_DIR%\config.json" copy /Y "%TARGET_DIR%\config.json" "%STAGING%\" >nul
    if exist "%TARGET_DIR%\presets.json" copy /Y "%TARGET_DIR%\presets.json" "%STAGING%\" >nul
)

rem Leave our own directory first: Windows locks the batch CWD on delete.
cd /d "%TEMP%"

echo [*] Removing "%TARGET_DIR%"...
rmdir /s /q "%TARGET_DIR%" >nul 2>&1

if exist "%TARGET_DIR%" (
    echo [ERROR] Could not remove "%TARGET_DIR%". Close OBS Studio and try again.
    pause
    exit /b 1
)

if /i "!KEEP_DATA!"=="Y" (
    echo [*] Restoring kept files...
    mkdir "%TARGET_DIR%" >nul 2>&1
    if exist "%STAGING%\config.json" copy /Y "%STAGING%\config.json" "%TARGET_DIR%\" >nul
    if exist "%STAGING%\presets.json" copy /Y "%STAGING%\presets.json" "%TARGET_DIR%\" >nul
    rmdir /s /q "%STAGING%" >nul 2>&1
    echo [OK] Kept files restored:
    if exist "%TARGET_DIR%\config.json" echo     - config.json
    if exist "%TARGET_DIR%\presets.json" echo     - presets.json
) else (
    echo [OK] All plugin files and user data removed.
)

echo.
echo Uninstall complete. Also remove the Lua entry under OBS Tools -^> Scripts if listed.
timeout /t 5 >nul
