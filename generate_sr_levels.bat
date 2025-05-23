@echo off
echo DEBUG: Starting generate_sr_levels.bat

echo DEBUG: Checking for Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not available. Please ensure Python is installed and in your PATH.
    pause
    goto :eof
)
echo DEBUG: Python found.

echo DEBUG: Checking for required Python files...
if not exist data_fetcher.py (
    echo ERROR: data_fetcher.py not found in the current directory.
    pause
    goto :eof
)
if not exist support_resistance.py (
    echo ERROR: support_resistance.py not found in the current directory.
    pause
    goto :eof
)
echo DEBUG: All required Python files found.

echo DEBUG: Checking for config.ini...
if not exist config.ini (
    echo ERROR: config.ini not found. Please ensure it is configured correctly.
    pause
    goto :eof
)
echo DEBUG: config.ini found.

echo DEBUG: Fetching LINK market data...
python data_fetcher.py --output market_data.csv --symbol LINKUSDT_UMCBL --timeframe 5m --limit 1000
if errorlevel 1 (
    echo ERROR: Failed to fetch market data. Please check data_fetcher.py output.
    pause
    goto :eof
)
echo DEBUG: LINK market data fetched successfully.

echo DEBUG: About to run support_resistance.py. Press any key to continue...
pause 

echo INFO: Running support_resistance.py to generate S/R levels CSV...
python support_resistance.py

echo DEBUG: Python script execution finished. Error level from Python was: %errorlevel%
if %errorlevel% NEQ 0 ( goto :script_error ) else ( goto :script_success )

:script_error
echo.
echo ERROR: support_resistance.py likely exited with an error (Error Level: %errorlevel%).
echo Please check the output above for any Python error messages.
echo If no Python errors are visible, ensure all dependencies (pandas, scipy, numpy) are correctly installed.
goto :script_end

:script_success
echo.
echo SUCCESS: support_resistance.py finished (Error Level: %errorlevel%).
echo INFO: Check for the S/R levels CSV file (sr_levels.csv, or as configured in config.ini).
goto :script_end

:script_end
echo.
echo DEBUG: End of batch script. Press any key to close this window.
pause 