@echo off
REM ============================================================
REM Mini-Splunk Test Runner
REM Starts server in one window and runs tests in another
REM ============================================================

cd /d "%~dp0"

echo ============================================================
echo Mini-Splunk Test Runner
echo ============================================================
echo.

REM Start the server in a new window
echo Starting server in new window...
start "Mini-Splunk Server" cmd /k "cd /d "%~dp0" && python server.py --host localhost --port 5514"

REM Wait for server to start
echo Waiting 3 seconds for server to initialize...
timeout /t 3 /nobreak >nul

REM Start the test client in a new window
echo Starting test client in new window...
start "Mini-Splunk Test Client" cmd /k "cd /d "%~dp0" && python quickstart.py && echo. && echo Tests complete! Press any key to close. && pause >nul"

echo.
echo ============================================================
echo Two windows have been opened:
echo   1. Server window - Running on localhost:5514
echo   2. Test client window - Running automated tests
echo.
echo Close the server window when done testing.
echo ============================================================
echo.
pause
