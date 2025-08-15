#!/usr/bin/env python3
"""
Final Clean Guide Generator for Houzz Lead Generation Pipeline v1.0
Removes all duplicates and creates the most streamlined version
"""

import os
import sys
from pathlib import Path

def install_requirements():
    """Install required packages for PDF generation"""
    try:
        import markdown
        import weasyprint
    except ImportError:
        print("Installing required packages...")
        os.system("pip install markdown weasyprint")

def create_final_clean_markdown():
    """Create final clean markdown content without any duplicates"""
    
    content = """
# 🍎 Complete Mac Setup Guide for Houzz Lead Generation Pipeline v1.0

**Essential Setup, Usage & Reference Documentation**

> **Note**: This is the initial version (v1.0) of the Houzz Lead Generation Pipeline. The system is designed for basic to moderate scraping needs with core functionality.

---

## 📋 Table of Contents

1. [System Requirements](#system-requirements)
2. [Installation](#installation)
3. [API Configuration](#api-configuration)
4. [Testing Your Setup](#testing-your-setup)
5. [Production Usage](#production-usage)
6. [Database Management](#database-management)
7. [Troubleshooting](#troubleshooting)

---

## 🖥️ System Requirements

### Recommended Requirements
- **macOS**: 11.0 (Big Sur) or higher
- **Python**: Version 3.10 or higher
- **Memory**: 8GB RAM
- **Storage**: 20GB free space
- **Internet**: 50+ Mbps broadband connection

### Version 1.0 Limitations
- **Initial Release**: Basic functionality with core features
- **Limited Scale**: Designed for small to medium scraping projects
- **Core Platforms**: Houzz and Architizer support only
- **Essential APIs**: ZeroBounce and Google Custom Search integration

---

## 🚀 Installation

### Step 1: Install Homebrew

```bash
# Install Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Add Homebrew to PATH (Apple Silicon Macs)
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zshrc

# Add Homebrew to PATH (Intel Macs)
echo 'eval "$(/usr/local/bin/brew shellenv)"' >> ~/.zshrc

# Reload shell configuration
source ~/.zshrc

# Verify installation
brew --version
```

### Step 2: Install Python 3.10+

```bash
# Update Homebrew
brew update

# Install Python 3.10
brew install python@3.10

# Add Python to PATH
echo 'export PATH="/opt/homebrew/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# Verify Python installation
python3 --version
```

### Step 3: Install Xcode Command Line Tools

```bash
# Install Xcode Command Line Tools
xcode-select --install

# Wait for installation to complete (may take 10-15 minutes)
# You'll see a popup - click "Install" and accept the license
```

### Step 4: Install SQLite3

```bash
# SQLite3 is usually pre-installed on macOS, but let's verify
sqlite3 --version

# If not installed, install via Homebrew
brew install sqlite3

# Verify installation
sqlite3 --version
```

### Step 5: Setup Project

```bash
# Navigate to your project directory
cd /path/to/your/project

# Run the deployment script
chmod +x deploy.sh
./deploy.sh
```

**Expected Output:**
```
🚀 Starting Houzz Lead Generation Pipeline v1.0 Deployment
==========================================================
✅ Python 3.10.x detected
🔧 Checking system dependencies...
📦 Creating virtual environment...
🔄 Activating virtual environment...
✅ Virtual environment activated: /path/to/venv
⬆️  Upgrading pip...
📚 Installing dependencies...
🌐 Installing Playwright browsers...
📁 Creating directories...
📝 Creating .env file from template...
🧪 Testing installation...
✅ Pipeline import successful
🎉 Deployment completed successfully!
```

---

## 🔑 API Configuration

### Required API Keys

**Add these to your `.env` file:**

```bash
# ZeroBounce API Key (for email verification)
ZEROBOUNCE_API_KEY=your_zerobounce_api_key_here

# Google Custom Search API (for Gmail discovery and social media enrichment)
GOOGLE_SEARCH_API_KEY=your_google_api_key_here
GOOGLE_SEARCH_CX=your_google_custom_search_engine_id_here
```

### How to Get API Keys

#### ZeroBounce API Setup
1. Go to [ZeroBounce](https://www.zerobounce.net/)
2. Create a free account
3. Navigate to API section
4. Copy your API key

#### Google Custom Search API Setup
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create new project or select existing
3. Enable Custom Search API
4. Go to "APIs & Services" > "Credentials"
5. Create an API key
6. Go to [Google Programmable Search Engine](https://programmablesearchengine.google.com/)
7. Create a custom search engine
8. Get your Search Engine ID (cx)

---

## 🧪 Testing Your Setup

### Test 1: Basic Functionality

```bash
# IMPORTANT: Always activate virtual environment first
source venv/bin/activate

# Verify virtual environment is active (should show (venv) in prompt)
echo $VIRTUAL_ENV

# Test help command
python3 main.py --help
```

### Test 2: List Available States

```bash
# IMPORTANT: Activate virtual environment first
source venv/bin/activate

# List all available US states
python3 main.py --platform houzz --list-states
```

### Test 3: List Cities in a State

```bash
# IMPORTANT: Activate virtual environment first
source venv/bin/activate

# List cities in California
python3 main.py --platform houzz --list-cities california

# List cities in other states
python3 main.py --platform houzz --list-cities texas
python3 main.py --platform houzz --list-cities new-york
python3 main.py --platform houzz --list-cities florida
```

### Test 4: Dry Run Test

```bash
# IMPORTANT: Activate virtual environment first
source venv/bin/activate

# Test run without actual scraping
python3 main.py --platform houzz --dry-run --states california
```

---

## 🚀 Production Usage

### ⚠️ IMPORTANT: Virtual Environment Usage

**ALWAYS activate the virtual environment before running any commands:**

```bash
# Activate virtual environment (REQUIRED)
source venv/bin/activate

# Verify activation (should show (venv) in prompt)
echo $VIRTUAL_ENV
```

### Essential Commands

#### Full 4-Phase Pipeline
```bash
# IMPORTANT: Activate virtual environment first
source venv/bin/activate

# Complete pipeline for all states (Houzz)
python3 main.py --platform houzz

# Complete pipeline for specific states
python3 main.py --platform houzz --states california texas florida

# Complete pipeline without email verification (faster)
python3 main.py --platform houzz --states california --no-email-verification
```

#### Individual Phases
```bash
# IMPORTANT: Activate virtual environment first
source venv/bin/activate

# Phase 1: Platform Profile Scraping
python3 main.py --platform houzz --phase scrape --states california

# Phase 2: Website Email Mining
python3 main.py --platform houzz --phase websearch

# Phase 3: Google Search Enrichment
python3 main.py --platform houzz --phase googlesearch

# Phase 4: Email Verification & Export
python3 main.py --platform houzz --phase export
```

#### Architizer Platform
```bash
# IMPORTANT: Activate virtual environment first
source venv/bin/activate

# Architizer platform scraping
python3 main.py --platform architizer --phase scrape --max-pages 10

# Complete Architizer pipeline
python3 main.py --platform architizer
```

#### Advanced Commands
```bash
# IMPORTANT: Activate virtual environment first
source venv/bin/activate

# Specific professional types
python3 main.py --platform houzz --professional-types interior-designer architect

# Custom pagination
python3 main.py --platform houzz --states california --max-pages 25 --start-page 1

# Debug logging
python3 main.py --platform houzz --log-level DEBUG

# Show scraping statistics
python3 main.py --platform houzz --stats
```

---

## 🗄️ Database Management

### Basic SQLite3 Commands

```bash
# IMPORTANT: Activate virtual environment first
source venv/bin/activate

# Open the database
sqlite3 data/scraper.db

# In SQLite3 prompt, useful commands:
.tables                    # List all tables
.schema professionals      # Show table structure
.headers on               # Enable column headers
.mode csv                 # Set output mode to CSV
.quit                     # Exit SQLite3
```

### Check Data Commands

```bash
# IMPORTANT: Activate virtual environment first
source venv/bin/activate

# Check record count
sqlite3 data/scraper.db "SELECT COUNT(*) FROM professionals;"

# Check scraping progress
sqlite3 data/scraper.db "SELECT 
  COUNT(*) as total_profiles,
  SUM(website_scraped) as websites_scraped,
  SUM(google_search_done) as google_searches_done,
  SUM(is_email_verified) as emails_verified
FROM professionals;"

# View recent entries
sqlite3 data/scraper.db "SELECT name, website, created_at FROM professionals ORDER BY created_at DESC LIMIT 10;"

# Check data quality
sqlite3 data/scraper.db "SELECT 
  COUNT(*) as total,
  SUM(CASE WHEN emails IS NOT NULL AND emails != '' THEN 1 ELSE 0 END) as with_emails,
  SUM(CASE WHEN phone IS NOT NULL AND phone != '' THEN 1 ELSE 0 END) as with_phones,
  SUM(CASE WHEN website IS NOT NULL AND website != '' THEN 1 ELSE 0 END) as with_websites
FROM professionals;"

# Export data to CSV
sqlite3 data/scraper.db ".mode csv" ".headers on" "SELECT * FROM professionals;" > data/export_$(date +%Y%m%d).csv

# Backup database
cp data/scraper.db data/scraper.db.backup.$(date +%Y%m%d)
```

---

## 🐛 Troubleshooting

### Common Issues

#### "Command not found: python3"
```bash
# Install Python via Homebrew
brew install python@3.10
echo 'export PATH="/opt/homebrew/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

#### "Permission denied" errors
```bash
# Fix file permissions
chmod +x main.py
chmod +x deploy.sh
```

#### "Playwright browser not found"
```bash
# IMPORTANT: Activate virtual environment first
source venv/bin/activate
playwright install chromium
```

#### "Module not found" errors
```bash
# Ensure virtual environment is activated
source venv/bin/activate
pip install -r requirements.txt
```

#### "API key errors"
```bash
# Check .env file exists
ls -la .env
cat .env
```

### Debug Mode

```bash
# IMPORTANT: Activate virtual environment first
source venv/bin/activate

# Run with debug logging
python3 main.py --platform houzz --log-level DEBUG

# Check error logs
grep "ERROR" logs/scraper.log
```

---

## ⚠️ Important Notes

### Always Remember
1. **Activate virtual environment** before running any commands: `source venv/bin/activate`
2. **Check API keys** are properly configured in `.env` file
3. **Respect rate limits** and website terms of service

### Performance Tips
- Use `--no-email-verification` for faster scraping (saves API credits)
- Start with small states for testing
- Use debug logging for troubleshooting

---

**Happy Scraping with Version 1.0! 🚀**

*This guide provides everything you need to successfully set up and run the Houzz Lead Generation Pipeline v1.0 on macOS.*

**Remember to always activate your virtual environment before running any commands:**
```bash
source venv/bin/activate
```
"""
    
    return content

def convert_to_pdf(markdown_content, pdf_file):
    """Convert markdown to PDF format"""
    try:
        import markdown
        import weasyprint
        
        print(f"Creating final clean PDF: {pdf_file}")
        
        # Convert markdown to HTML
        html_content = markdown.markdown(markdown_content, extensions=['tables', 'fenced_code', 'codehilite'])
        
        # Create full HTML document
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Houzz Lead Generation Pipeline v1.0 - Complete Mac Setup Guide</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    line-height: 1.6;
                    margin: 40px;
                    color: #333;
                }}
                h1, h2, h3, h4, h5, h6 {{
                    color: #2c3e50;
                    margin-top: 30px;
                    margin-bottom: 15px;
                }}
                h1 {{
                    font-size: 2.5em;
                    text-align: center;
                    border-bottom: 3px solid #3498db;
                    padding-bottom: 10px;
                }}
                h2 {{
                    font-size: 1.8em;
                    border-bottom: 2px solid #ecf0f1;
                    padding-bottom: 5px;
                }}
                h3 {{
                    font-size: 1.4em;
                    color: #34495e;
                }}
                code {{
                    background-color: #f8f9fa;
                    padding: 2px 4px;
                    border-radius: 3px;
                    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
                    font-size: 0.9em;
                }}
                pre {{
                    background-color: #f8f9fa;
                    padding: 15px;
                    border-radius: 5px;
                    overflow-x: auto;
                    border-left: 4px solid #3498db;
                }}
                pre code {{
                    background-color: transparent;
                    padding: 0;
                }}
                table {{
                    border-collapse: collapse;
                    width: 100%;
                    margin: 20px 0;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 12px;
                    text-align: left;
                }}
                th {{
                    background-color: #f2f2f2;
                    font-weight: bold;
                }}
                tr:nth-child(even) {{
                    background-color: #f9f9f9;
                }}
                .highlight {{
                    background-color: #fff3cd;
                    padding: 10px;
                    border-radius: 5px;
                    border-left: 4px solid #ffc107;
                }}
                .warning {{
                    background-color: #f8d7da;
                    padding: 10px;
                    border-radius: 5px;
                    border-left: 4px solid #dc3545;
                }}
                .success {{
                    background-color: #d4edda;
                    padding: 10px;
                    border-radius: 5px;
                    border-left: 4px solid #28a745;
                }}
                ul, ol {{
                    margin-left: 20px;
                }}
                li {{
                    margin-bottom: 5px;
                }}
                blockquote {{
                    border-left: 4px solid #3498db;
                    margin: 20px 0;
                    padding-left: 20px;
                    color: #7f8c8d;
                }}
            </style>
        </head>
        <body>
            
            {html_content}
        </body>
        </html>
        """
        
        # Convert HTML to PDF
        weasyprint.HTML(string=full_html).write_pdf(pdf_file)
        
        print(f"✅ Final clean PDF created: {pdf_file}")
        
    except Exception as e:
        print(f"❌ Error creating final clean PDF: {e}")
        return False
    
    return True

def cleanup_files():
    """Remove old files"""
    files_to_remove = [
        'Houzz_Scraper_Complete_Guide_v1.0.md',
        'Houzz_Scraper_Complete_Guide_v1.0.pdf'
    ]
    
    for file in files_to_remove:
        if os.path.exists(file):
            os.remove(file)
            print(f"🗑️  Removed old: {file}")

def main():
    """Main function to create final clean guide"""
    print("🚀 Creating final clean, streamlined documentation...")
    
    # Install requirements
    install_requirements()
    
    # Remove old files
    cleanup_files()
    
    # Create final clean markdown content
    markdown_content = create_final_clean_markdown()
    
    # Save markdown content to file
    with open('Houzz_Scraper_Complete_Guide_v1.0.md', 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    
    print("✅ Final clean markdown created: Houzz_Scraper_Complete_Guide_v1.0.md")
    
    # Convert to PDF
    convert_to_pdf(markdown_content, 'Houzz_Scraper_Complete_Guide_v1.0.pdf')
    
    print("\n🎉 Final clean documentation completed!")
    print("\n📁 Final files:")
    print("  - Houzz_Scraper_Complete_Guide_v1.0.md")
    print("  - Houzz_Scraper_Complete_Guide_v1.0.pdf")

if __name__ == "__main__":
    main() 