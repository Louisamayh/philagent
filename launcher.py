#!/usr/bin/env python3
"""
PhilAgent Launcher
Double-click this to start the PhilAgent web interface
"""

import os
import sys
import time
import subprocess
import webbrowser
from pathlib import Path

def main():
    # Get the directory where this script is located
    script_dir = Path(__file__).parent.absolute()
    os.chdir(script_dir)

    print("=" * 60)
    print("🚀 PhilAgent Starting...")
    print("=" * 60)

    # Check if virtual environment exists
    venv_path = script_dir / "venv"
    if not venv_path.exists():
        print("❌ Virtual environment not found!")
        print("Please run setup first:")
        print("  Mac/Linux: ./start.sh")
        print("  Windows: start.bat")
        input("\nPress Enter to exit...")
        return

    # Get Python executable from venv
    if sys.platform == "win32":
        python_exe = venv_path / "Scripts" / "python.exe"
    else:
        python_exe = venv_path / "bin" / "python"

    if not python_exe.exists():
        print("❌ Python not found in virtual environment!")
        input("\nPress Enter to exit...")
        return

    # Check for .env file
    env_file = script_dir / ".env"
    if not env_file.exists():
        print("⚠️  Warning: .env file not found!")
        print("Please create a .env file with your GOOGLE_API_KEY")
        api_key = input("\nEnter your Google API Key (or press Enter to exit): ")
        if api_key.strip():
            with open(env_file, 'w') as f:
                f.write(f"GOOGLE_API_KEY={api_key.strip()}\n")
            print("✅ .env file created")
        else:
            return

    print("\n🌐 Starting web server...")
    print("📂 Working directory:", script_dir)
    print("\n" + "=" * 60)
    print("PhilAgent will open in your browser shortly...")
    print("=" * 60)
    print("\n⚠️  DO NOT CLOSE THIS WINDOW")
    print("    Close your browser tab to stop PhilAgent")
    print("    Or press Ctrl+C here to stop the server")
    print("\n" + "=" * 60 + "\n")

    # Start the server process
    server_process = subprocess.Popen(
        [str(python_exe), "api_server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    # Wait a moment for server to start
    time.sleep(3)

    # Open browser
    webbrowser.open("http://localhost:8000")
    print("✅ Browser opened to http://localhost:8000\n")

    # Stream server output
    try:
        for line in server_process.stdout:
            print(line, end='')
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping PhilAgent...")
        server_process.terminate()
        server_process.wait()
        print("✅ PhilAgent stopped")

    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()
