@echo off
REM ============================================================
REM Mini-Splunk Interactive Mode
REM Starts server in one window and client shell in another
REM ============================================================

cd /d "%~dp0"

echo ============================================================
echo Mini-Splunk Interactive Mode
echo ============================================================
echo.

REM Start the server in a new window
echo Starting server in new window...
start "Mini-Splunk Server" cmd /k "cd /d "%~dp0" && python server.py --host localhost --port 5514"

REM Wait for server to start
echo Waiting 3 seconds for server to initialize...
timeout /t 3 /nobreak >nul

REM Start the interactive client in a new window
echo Starting interactive client in new window...
start "Mini-Splunk Client" cmd /k "cd /d "%~dp0" && python client.py"

echo.
echo ============================================================
echo Two windows have been opened:
echo   1. Server window - Running on localhost:5514
echo   2. Client window - Interactive shell
echo.
echo In the client window, try these commands:
echo   ingest sample_logs.txt
echo   search host SYSSVR1
echo   search keyword error
echo   count failed
echo   stats
echo   help
echo   quit
echo.
echo Close the server window when done.
echo ============================================================
echo.
pause
