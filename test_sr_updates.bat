@echo off
echo Running S/R Update Test...

echo.
echo This will show a visualization of how S/R levels update
echo with changing price action.
echo.

python test_sr_updates.py

echo.
echo Press any key to exit...
pause > nul
