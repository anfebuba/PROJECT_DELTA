@echo off
echo Installing required packages from requirements.txt...
python -m pip install -r requirements.txt

echo.
echo Running support/resistance test...
python test_sr.py

echo.
echo Press any key to exit...
pause > nul 