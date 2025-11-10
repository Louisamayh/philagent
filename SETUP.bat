@echo off
REM PhilAgent Setup Script for Windows
REM Run this once to install PhilAgent

echo ==========================================
echo 🔧 PhilAgent Setup
echo ==========================================
echo.

REM Check Python
echo 📋 Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is not installed!
    echo Please install Python 3.11 or higher from python.org
    pause
    exit /b 1
)

python --version
echo ✅ Python found

REM Create virtual environment
echo.
echo 📦 Creating virtual environment...
if exist "venv" (
    echo ⚠️  Virtual environment already exists. Recreating...
    rmdir /s /q venv
)

python -m venv venv
echo ✅ Virtual environment created

REM Activate and install dependencies
echo.
echo 📥 Installing dependencies...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
echo ✅ Dependencies installed

REM Check for .env file
echo.
if not exist ".env" (
    echo ⚠️  .env file not found
    set /p create_env="Do you want to enter your Google API Key now? (y/n): "
    if /i "%create_env%"=="y" (
        set /p api_key="Enter your Google API Key: "
        echo GOOGLE_API_KEY=!api_key! > .env
        echo ✅ .env file created
    ) else (
        echo ℹ️  You can create .env later with your GOOGLE_API_KEY
    )
) else (
    echo ✅ .env file found
)

echo.
echo ==========================================
echo ✅ Setup Complete!
echo ==========================================
echo.
echo 📱 To start PhilAgent:
echo    Double-click: PhilAgent.bat
echo.
echo    Or run: start.bat
echo ==========================================
pause
