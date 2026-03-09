@echo off
REM ============================================================
REM Mini-Splunk Test Runner
REM Runs unit tests and integration tests
REM ============================================================

cd /d "%~dp0"

echo ============================================================
echo Mini-Splunk Test Runner
echo ============================================================
echo.

REM ============================================================
REM PHASE 1: Unit Tests (no server required)
REM ============================================================
echo [PHASE 1] Running Unit Tests...
echo ------------------------------------------------------------
python -m unittest test_commands -v
echo.

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ============================================================
    echo UNIT TESTS FAILED! Stopping.
    echo ============================================================
    pause
    exit /b 1
)

echo.
echo ============================================================
echo Unit tests passed! Starting integration tests...
echo ============================================================
echo.

REM ============================================================
REM PHASE 2: Integration Tests (requires server)
REM ============================================================
echo [PHASE 2] Running Integration Tests...
echo ------------------------------------------------------------

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
echo   2. Test client window - Running integration tests
echo.
echo Close the server window when done testing.
echo ============================================================
echo.
pause
