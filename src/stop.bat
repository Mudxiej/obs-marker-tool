@echo off
setlocal enabledelayedexpansion
rem Stop only the OBS Marker Tool daemon on 127.0.0.1:8765.
rem Strict loopback match avoids killing e.g. :18765.
rem tasklist guard ensures we only kill python processes.

for /f "tokens=5" %%a in ('netstat -aon ^| find "127.0.0.1:8765" ^| find "LISTENING"') do (
    set "PID=%%a"
    tasklist /FI "PID eq !PID!" /NH | find /I "python" >nul
    if !ERRORLEVEL! EQU 0 (
        taskkill /f /pid !PID! >nul 2>&1
    )
)
echo OBS Marker Server stopped.
