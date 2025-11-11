# 🎯 PhilAgent - Automated Lead Scraping & Enrichment

PhilAgent is an AI-powered tool that automatically scrapes job postings from CV-Library and enriches them with company information using Google Gemini.

![PhilAgent Logo](icon.png)

## ✨ Features

- 🔍 Automated job posting scraping from CV-Library
- 🤖 AI-powered company name extraction and enrichment
- 🎨 Beautiful web interface with real-time progress tracking
- 💾 Automatic saving of results to your computer
- 🖥️ Works on both Mac and Windows
- ⚡ One-click launcher with desktop shortcut

## 📥 Quick Download

**Download PhilAgent:** [Click here to download](https://github.com/Louisamayh/philagent/archive/refs/heads/main.zip)

## 🚀 Installation Guide

### For Non-Coders (Complete Beginners)

Don't worry if you've never used Python or coding tools before! Just follow these steps:

#### Step 1: Install Python

**On Mac:**
1. Open Safari and go to [python.org/downloads](https://www.python.org/downloads/)
2. Click the big yellow "Download Python" button
3. Open the downloaded file and follow the installer
4. When asked, check the box that says "Add Python to PATH"

**On Windows:**
1. Open your web browser and go to [python.org/downloads](https://www.python.org/downloads/)
2. Click the big yellow "Download Python" button
3. Open the downloaded file
4. **IMPORTANT:** Check the box "Add Python to PATH" at the bottom
5. Click "Install Now"

#### Step 2: Download PhilAgent

1. Click this link: [Download PhilAgent](https://github.com/Louisamayh/philagent/archive/refs/heads/main.zip)
2. Your browser will download a ZIP file
3. Find the downloaded file (usually in your Downloads folder)
4. **On Mac:** Double-click the ZIP file to unzip it
5. **On Windows:** Right-click the ZIP file and choose "Extract All"

#### Step 3: Get Your Google API Key

PhilAgent uses Google's Gemini AI. You need a free API key:

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Click "Get API Key" or "Create API Key"
3. Copy the key (it looks like: `AIzaSy...`)
4. Keep this somewhere safe - you'll need it in the next step

#### Step 4: Run Setup

**On Mac:**
1. Open Finder and find the "philagent-main" folder you unzipped
2. Double-click the file called **SETUP.sh**
3. If it says "Cannot open", right-click it and choose "Open"
4. When asked, paste your Google API Key and press Enter
5. Wait for setup to finish (takes 1-2 minutes)

**On Windows:**
1. Open File Explorer and find the "philagent-main" folder you unzipped
2. Double-click the file called **SETUP.bat**
3. When asked, paste your Google API Key and press Enter
4. Wait for setup to finish (takes 1-2 minutes)

#### Step 5: Launch PhilAgent

After setup completes, you'll find a **PhilAgent shortcut on your desktop**!

**On Mac:**
- Double-click the **PhilAgent** icon on your desktop
- Your web browser will open automatically to PhilAgent

**On Windows:**
- Double-click the **PhilAgent** icon on your desktop
- Your web browser will open automatically to PhilAgent

## 📖 How to Use PhilAgent

### 1. Upload Your Input File

- Click "Click to Upload" or drag and drop your CSV file
- Your CSV should have columns like: `job_title`, `location`, `miles`
- Example:
  ```
  job_title,location,miles
  Software Developer,London,30
  Data Analyst,Manchester,20
  ```

### 2. Start the Job

- Click the "Start Job" button
- PhilAgent will automatically:
  - Search CV-Library for your criteria
  - Scrape job postings
  - Extract company names using AI
  - Save everything to your computer

### 3. View Results

- Results are automatically saved to the `output` folder in PhilAgent
- You'll see two files:
  - `{job-id}_jobs_raw.csv` - All scraped job postings
  - `{job-id}_jobs_enriched.csv` - Jobs with company names added

### 4. Exit PhilAgent

- Click the "✕ Exit PhilAgent" button in the top-right corner
- Or close your browser and the terminal window

## 🔧 Troubleshooting

### "Python is not installed"
- Make sure you installed Python from python.org
- On Windows, check that you selected "Add Python to PATH" during installation
- Try restarting your computer and running SETUP again

### "Virtual environment not found"
- You need to run SETUP.sh (Mac) or SETUP.bat (Windows) first
- Make sure you're in the philagent-main folder

### ".env file not found"
- You need your Google API Key
- Get it from [Google AI Studio](https://aistudio.google.com/app/apikey)
- Run SETUP again and enter your API key

### "Port 8000 already in use"
- PhilAgent is already running
- Close all terminal/command prompt windows
- Try launching again

### Still having issues?
- Create an issue on [GitHub](https://github.com/Louisamayh/philagent/issues)
- Or contact support

## 💻 For Developers

If you're familiar with coding:

```bash
# Clone the repository
git clone https://github.com/Louisamayh/philagent.git
cd philagent

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
echo "GOOGLE_API_KEY=your_key_here" > .env

# Run the application
python api_server.py
```

Then open http://localhost:8000 in your browser.

## 📁 Project Structure

```
philagent/
├── api_server.py           # FastAPI web server
├── scraping_agent.py       # Browser automation for CV-Library
├── company_matcher.py      # AI-powered company extraction
├── launcher.py            # Application launcher
├── static/                # Web interface files
├── requirements.txt       # Python dependencies
├── PhilAgent.app         # Mac launcher
├── PhilAgent.bat         # Windows launcher
├── SETUP.sh              # Mac setup script
└── SETUP.bat             # Windows setup script
```

## 🤝 Support

- **Issues:** [GitHub Issues](https://github.com/Louisamayh/philagent/issues)
- **Repository:** [github.com/Louisamayh/philagent](https://github.com/Louisamayh/philagent)

## 📄 License

This project is private and proprietary.

---

Made with ❤️ by PhilAgent Team
