#!/bin/bash

# PhilAgent Startup Script (Mac/Linux)
# This script starts the web interface for PhilAgent

echo "=========================================="
echo "🚀 Starting PhilAgent Web Interface"
echo "=========================================="
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "⚠️  Virtual environment not found. Creating one..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
fi

# Activate virtual environment
echo "📦 Activating virtual environment..."
source venv/bin/activate

# Check if dependencies are installed
if ! python -c "import fastapi" 2>/dev/null; then
    echo "📥 Installing dependencies..."
    pip install -r requirements.txt
    echo "✅ Dependencies installed"
fi

# Check for .env file
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found!"
    echo "Please create a .env file with your GOOGLE_API_KEY"
    echo ""
    read -p "Do you want to create it now? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "Enter your Google API Key: " api_key
        echo "GOOGLE_API_KEY=$api_key" > .env
        echo "✅ .env file created"
    fi
fi

echo ""
echo "=========================================="
echo "🌐 Starting web server..."
echo "=========================================="
echo ""
echo "📱 Open your browser to:"
echo "   http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop the server"
echo "=========================================="
echo ""

# Start the server
python api_server.py
