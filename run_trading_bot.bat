@echo off
echo DEBUG: Starting run_trading_bot.bat

echo DEBUG: Checking for Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not available. Please ensure Python is installed and in your PATH.
    pause
    goto :eof
)
echo DEBUG: Python found.

echo DEBUG: Checking for required files...
if not exist live_signal_bot.py (
    echo ERROR: live_signal_bot.py not found in the current directory.
    pause
    goto :eof
)
if not exist config.ini (
    echo ERROR: config.ini not found. Please ensure it is configured correctly.
    pause
    goto :eof
)
echo DEBUG: All required files found.

echo DEBUG: Starting the trading bot...
python live_signal_bot.py

if errorlevel 1 (
    echo ERROR: Trading bot exited with an error. Check bot.log for details.
    pause
    goto :eof
)

:script_end
echo.
echo Press any key to exit...
pause > nul
