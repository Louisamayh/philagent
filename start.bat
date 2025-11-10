@echo off
REM PhilAgent Startup Script (Windows)
REM This script starts the web interface for PhilAgent

echo ==========================================
echo 🚀 Starting PhilAgent Web Interface
echo ==========================================
echo.

REM Check if virtual environment exists
if not exist "venv" (
    echo ⚠️  Virtual environment not found. Creating one...
    python -m venv venv
    echo ✅ Virtual environment created
)

REM Activate virtual environment
echo 📦 Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if dependencies are installed
python -c "import fastapi" 2>nul
if errorlevel 1 (
    echo 📥 Installing dependencies...
    pip install -r requirements.txt
    echo ✅ Dependencies installed
)

REM Check for .env file
if not exist ".env" (
    echo ⚠️  Warning: .env file not found!
    echo Please create a .env file with your GOOGLE_API_KEY
    echo.
    set /p api_key="Enter your Google API Key (or press Enter to skip): "
    if not "!api_key!"=="" (
        echo GOOGLE_API_KEY=!api_key! > .env
        echo ✅ .env file created
    )
)

echo.
echo ==========================================
echo 🌐 Starting web server...
echo ==========================================
echo.
echo 📱 Open your browser to:
echo    http://localhost:8000
echo.
echo Press Ctrl+C to stop the server
echo ==========================================
echo.

REM Start the server
python api_server.py

pause
