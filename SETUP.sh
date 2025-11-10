#!/bin/bash
# PhilAgent Setup Script for Mac/Linux
# Run this once to install PhilAgent

echo "=========================================="
echo "🔧 PhilAgent Setup"
echo "=========================================="
echo ""

# Check Python
echo "📋 Checking Python..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed!"
    echo "Please install Python 3.11 or higher from python.org"
    exit 1
fi

python3 --version
echo "✅ Python found"

# Create virtual environment
echo ""
echo "📦 Creating virtual environment..."
if [ -d "venv" ]; then
    echo "⚠️  Virtual environment already exists. Recreating..."
    rm -rf venv
fi

python3 -m venv venv
echo "✅ Virtual environment created"

# Activate and install dependencies
echo ""
echo "📥 Installing dependencies..."
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
echo "✅ Dependencies installed"

# Check for .env file
echo ""
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found"
    read -p "Do you want to enter your Google API Key now? (y/n): " create_env
    if [ "$create_env" = "y" ] || [ "$create_env" = "Y" ]; then
        read -p "Enter your Google API Key: " api_key
        echo "GOOGLE_API_KEY=$api_key" > .env
        echo "✅ .env file created"
    else
        echo "ℹ️  You can create .env later with your GOOGLE_API_KEY"
    fi
else
    echo "✅ .env file found"
fi

# Create desktop shortcut (alias to .app)
echo ""
echo "🖥️  Creating desktop shortcut..."
DESKTOP="$HOME/Desktop"
APP_PATH="$(pwd)/PhilAgent.app"

if [ -d "$APP_PATH" ]; then
    # Create an alias (symlink) on the desktop
    if [ -L "$DESKTOP/PhilAgent.app" ]; then
        rm "$DESKTOP/PhilAgent.app"
    fi
    ln -s "$APP_PATH" "$DESKTOP/PhilAgent.app"

    if [ -L "$DESKTOP/PhilAgent.app" ]; then
        echo "✅ Desktop shortcut created"
    else
        echo "⚠️  Could not create desktop shortcut"
        echo "    You can manually drag PhilAgent.app to your desktop"
    fi
else
    echo "⚠️  PhilAgent.app not found"
fi

echo ""
echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo ""
echo "📱 To start PhilAgent:"
echo "   1. Double-click the PhilAgent icon on your desktop"
echo "   2. Or double-click: PhilAgent.app (in this folder)"
echo "   3. Or run: ./start.sh"
echo "=========================================="
