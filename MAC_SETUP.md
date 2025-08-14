# 🍎 Mac Setup Guide for Houzz Lead Generation Pipeline

**Complete setup instructions for macOS users**

This guide provides step-by-step instructions to set up the Houzz Lead Generation Pipeline on macOS, including all dependencies, API configurations, and troubleshooting tips.

## 📋 Prerequisites

### System Requirements
- **macOS**: 10.15 (Catalina) or higher (recommended: macOS 11+)
- **Python**: Version 3.8 or higher
- **Memory**: Minimum 8GB RAM (16GB+ recommended for production)
- **Storage**: At least 20GB free space (30GB+ recommended for large datasets)
- **Internet**: Stable broadband connection (minimum 50 Mbps recommended)

### Required Software
- **Homebrew**: Package manager for macOS
- **Git**: Version control system
- **Xcode Command Line Tools**: Required for compiling some Python packages

## 🚀 Step-by-Step Installation

### 1. Install Homebrew (if not already installed)

```bash
# Install Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Add Homebrew to PATH (if not already done)
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zshrc
source ~/.zshrc
```

**Note**: If you're using an Intel Mac, the path might be `/usr/local/bin/brew` instead of `/opt/homebrew/bin/brew`.

### 2. Install Xcode Command Line Tools

```bash
# Install Xcode Command Line Tools
xcode-select --install

# Wait for the installation to complete (this may take several minutes)
# You'll see a popup asking to install the tools - click "Install"
```

### 3. Install Python 3.10+ via Homebrew

```bash
# Update Homebrew
brew update

# Install Python 3.10 (recommended version)
brew install python@3.10

# Add Python to PATH
echo 'export PATH="/opt/homebrew/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# Verify installation
python3 --version
# Should show: Python 3.10.x
```

### 4. Install Git (if not already installed)

```bash
# Install Git
brew install git

# Verify installation
git --version
```

### 5. Clone the Repository

```bash
# Navigate to your desired directory
cd ~/Documents  # or wherever you prefer

# Clone the repository
git clone <repository-url>
cd houzz-scraper

# Verify the project structure
ls -la
```

### 6. Run the Automated Setup Script

```bash
# Make the deployment script executable
chmod +x deploy.sh

# Run the deployment script
./deploy.sh
```

The script will automatically:
- Create a Python virtual environment
- Install all required dependencies
- Install Playwright browsers
- Create necessary directories
- Set up the environment file template

### 7. Configure API Keys

```bash
# Copy the environment template
cp .env.example .env

# Edit the environment file with your API keys
nano .env
# or use your preferred editor: code .env, vim .env, etc.
```

**Required API Keys** (add these to your `.env` file):

```bash
# ZeroBounce API Key (for email verification)
ZEROBOUNCE_API_KEY=your_zerobounce_api_key_here

# Google Custom Search API (for Gmail discovery and social media enrichment)
GOOGLE_SEARCH_API_KEY=your_google_api_key_here
GOOGLE_SEARCH_CX=your_google_custom_search_engine_id_here
```

**How to get API keys:**

#### ZeroBounce API Key
1. Go to [ZeroBounce](https://www.zerobounce.net/)
2. Sign up for a free account
3. Navigate to API section
4. Copy your API key

#### Google Custom Search API
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the Custom Search API
4. Go to "APIs & Services" > "Credentials"
5. Create an API key
6. Go to [Google Programmable Search Engine](https://programmablesearchengine.google.com/)
7. Create a custom search engine
8. Get your Search Engine ID (cx)

### 8. Activate Virtual Environment

**IMPORTANT**: Always activate the virtual environment before running any commands:

```bash
# Activate the virtual environment
source venv/bin/activate

# Your terminal prompt should now show (venv) at the beginning
# (venv) user@MacBook-Pro:~/houzz-scraper$
```

### 9. Verify Installation

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Test the installation
python3 main.py --help

# List available states
python3 main.py --platform houzz --list-states
```

## 🧪 Testing Your Setup

### 1. Test Basic Functionality

```bash
# Activate virtual environment
source venv/bin/activate

# List all available US states
python3 main.py --platform houzz --list-states

# List cities in California
python3 main.py --platform houzz --list-cities california

# Run a dry test (no actual scraping)
python3 main.py --platform houzz --dry-run --states california
```

### 2. Test with Limited Data

```bash
# Test scraping with limited pages
python3 main.py --platform houzz --states california --max-pages 3

# Test Architizer platform
python3 main.py --platform architizer --phase scrape --max-pages 2
```

### 3. Test Individual Phases

```bash
# Phase 1: Platform Profile Scraping
python3 main.py --platform houzz --phase scrape --states california --max-pages 5

# Phase 2: Website Email Mining
python3 main.py --platform houzz --phase websearch

# Phase 3: Google Search Enrichment
python3 main.py --platform houzz --phase googlesearch

# Phase 4: Email Verification & Export
python3 main.py --platform houzz --phase export
```

## 🚀 Production Usage

### Full Pipeline Execution

```bash
# Activate virtual environment
source venv/bin/activate

# Full 4-phase pipeline for all states (Houzz)
python3 main.py --platform houzz

# Specific states with ZeroBounce verification
python3 main.py --platform houzz --states california texas florida

# Skip ZeroBounce verification (faster, uses basic validation)
python3 main.py --platform houzz --states california --no-email-verification

# Architizer platform
python3 main.py --platform architizer
```

### Advanced Usage Examples

```bash
# Custom scraping parameters
python3 main.py --platform houzz --states california --max-pages 25 --start-page 1

# Specific professional types
python3 main.py --platform houzz --professional-types interior-designer architect

# Debug mode with detailed logging
python3 main.py --platform houzz --log-level DEBUG

# Check scraping progress statistics
python3 main.py --platform houzz --stats
```

## 🔧 Mac-Specific Configuration

### 1. Terminal Configuration

For better experience, consider using a modern terminal:

```bash
# Install iTerm2 (recommended terminal for Mac)
brew install --cask iterm2

# Install Oh My Zsh for better shell experience
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
```

### 2. File Permissions

If you encounter permission issues:

```bash
# Fix file permissions
chmod +x main.py
chmod +x deploy.sh

# If you get permission errors with pip
pip3 install --user -r requirements.txt
```

### 3. macOS Security Settings

You may need to allow certain applications:

1. **System Preferences** > **Security & Privacy** > **General**
2. Allow applications from "Anywhere" or specific developers
3. For Playwright, you might need to allow browser automation

### 4. Memory Management

For large scraping jobs, monitor memory usage:

```bash
# Monitor system resources
top -o mem

# Check available memory
vm_stat

# Monitor Python process
ps aux | grep python
```

## 🐛 Troubleshooting

### Common Mac-Specific Issues

#### 1. "Command not found: python3"
```bash
# Solution: Install Python via Homebrew
brew install python@3.10

# Add to PATH
echo 'export PATH="/opt/homebrew/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

#### 2. "Permission denied" errors
```bash
# Fix file permissions
chmod +x main.py
chmod +x deploy.sh

# Fix directory permissions
chmod 755 venv/
```

#### 3. "Playwright browser not found"
```bash
# Activate virtual environment first
source venv/bin/activate

# Install Playwright browsers
playwright install chromium

# If that doesn't work, try:
python3 -m playwright install chromium
```

#### 4. "Module not found" errors
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt

# Check if virtual environment is active
echo $VIRTUAL_ENV
```

#### 5. "SSL Certificate" errors
```bash
# Update certificates
pip install --upgrade certifi

# If using corporate network, you might need to configure proxy settings
```

#### 6. "Xcode Command Line Tools" errors
```bash
# Install Xcode Command Line Tools
xcode-select --install

# If already installed, reset
sudo xcode-select --reset
```

#### 7. "Homebrew" path issues
```bash
# For Apple Silicon Macs
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zshrc

# For Intel Macs
echo 'eval "$(/usr/local/bin/brew shellenv)"' >> ~/.zshrc

# Reload shell
source ~/.zshrc
```

### Performance Optimization

#### 1. Increase Terminal Buffer Size
In iTerm2:
1. **Preferences** > **Profiles** > **Terminal**
2. Increase "Scrollback Buffer" to 10000+ lines

#### 2. Monitor System Resources
```bash
# Install htop for better process monitoring
brew install htop

# Monitor system resources
htop
```

#### 3. Clean Up Disk Space
```bash
# Clean Homebrew cache
brew cleanup

# Clean pip cache
pip cache purge

# Clean system cache
sudo rm -rf /Library/Caches/*
```

## 📊 Monitoring and Logs

### View Logs
```bash
# View real-time logs
tail -f logs/scraper.log

# View error logs
grep "ERROR" logs/scraper.log

# View recent activity
tail -n 100 logs/scraper.log
```

### Check Database Status
```bash
# Activate virtual environment
source venv/bin/activate

# Check database
sqlite3 data/scraper.db "SELECT COUNT(*) FROM professionals;"

# View recent entries
sqlite3 data/scraper.db "SELECT name, website, created_at FROM professionals ORDER BY created_at DESC LIMIT 10;"
```

### Monitor Progress
```bash
# Check scraping statistics
python3 main.py --platform houzz --stats

# Check system resources
top -o mem | head -20
```

## 🔒 Security Considerations

### 1. API Key Security
- Never commit API keys to version control
- Use `.env` file for sensitive data
- Consider using macOS Keychain for additional security

### 2. Network Security
- Use VPN if scraping from corporate network
- Be aware of rate limiting and terms of service
- Monitor network usage

### 3. Data Privacy
- Ensure compliance with data privacy laws
- Secure storage of scraped data
- Regular cleanup of temporary files

## 📱 Additional Tools

### Recommended Mac Apps
```bash
# Install useful development tools
brew install --cask visual-studio-code  # Code editor
brew install --cask postman             # API testing
brew install --cask db-browser-for-sqlite  # Database browser
brew install --cask tableplus           # Database management
```

### Useful Terminal Tools
```bash
# Install additional terminal tools
brew install tree        # Directory tree visualization
brew install jq          # JSON processor
brew install httpie      # HTTP client
brew install watch       # Command monitoring
```

## 📞 Support

If you encounter issues:

1. **Check the logs**: `tail -f logs/scraper.log`
2. **Run in debug mode**: `python3 main.py --log-level DEBUG`
3. **Verify installation**: `python3 main.py --help`
4. **Check system resources**: `top -o mem`

### Common Commands Reference

```bash
# Essential commands
source venv/bin/activate                    # Activate virtual environment
python3 main.py --help                      # Show all options
python3 main.py --platform houzz --list-states  # List available states
python3 main.py --platform houzz --dry-run      # Test run
python3 main.py --platform houzz --stats        # Check progress

# Development commands
pip list                                    # List installed packages
pip install --upgrade pip                   # Upgrade pip
playwright install chromium                 # Install browsers
sqlite3 data/scraper.db                     # Access database
```

---

**Happy Scraping! 🚀**

Remember to always activate your virtual environment before running any commands:
```bash
source venv/bin/activate
``` 