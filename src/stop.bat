@echo off
setlocal enabledelayedexpansion
rem Stop the OBS Marker Tool daemon (ports 8765-8770).
rem Reads port.txt when present, then sweeps the range.
rem Strict loopback match avoids killing e.g. :18765.
rem tasklist guard ensures we only kill python processes.

set "SCRIPT_DIR=%~dp0"
set "SAVED_PORT="
if exist "%SCRIPT_DIR%port.txt" (
    set /p SAVED_PORT=<"%SCRIPT_DIR%port.txt"
)

call :kill_on_port !SAVED_PORT!
for %%p in (8765 8766 8767 8768 8769 8770) do (
    if /i not "%%p"=="!SAVED_PORT!" (
        call :kill_on_port %%p
    )
)

if exist "%SCRIPT_DIR%port.txt" (
    del "%SCRIPT_DIR%port.txt" >nul 2>&1
)
echo OBS Marker Server stopped.
exit /b 0

:kill_on_port
set "PORT_ARG=%~1"
if "%PORT_ARG%"=="" exit /b 0
echo %PORT_ARG% | findstr /R "^[0-9][0-9]*$" >nul
if %ERRORLEVEL% NEQ 0 exit /b 0
for /f "tokens=5" %%a in ('netstat -aon ^| find "127.0.0.1:%PORT_ARG%" ^| find "LISTENING"') do (
    set "PID=%%a"
    tasklist /FI "PID eq !PID!" /NH | find /I "python" >nul
    if !ERRORLEVEL! EQU 0 (
        taskkill /f /pid !PID! >nul 2>&1
    )
)
exit /b 0
