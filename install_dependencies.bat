@echo off
echo Installing Python dependencies from requirements.txt...

REM Check if pip is available
python -m pip --version >nul 2>&1
if errorlevel 1 (
    echo Error: pip is not available. Please ensure Python and pip are installed and in your PATH.
    goto :eof
)

REM Update pip first
python -m pip install --upgrade pip

REM Clean up any temporary directories
rmdir /s /q "%APPDATA%\Python\Python312\site-packages\~andas.libs" 2>nul
rmdir /s /q "%APPDATA%\Python\Python312\site-packages\~andas" 2>nul

REM Uninstall potentially conflicting packages
python -m pip uninstall -y pandas numpy

REM Install packages with --no-deps first for core dependencies
python -m pip install --no-deps -r requirements.txt

REM Then install all dependencies
python -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo Error: Failed to install one or more packages.
    echo Please check the output above for details.
    echo You might need to run this script as an administrator.
) else (
    echo.
    echo Dependencies installed successfully.
)

echo.
pause 