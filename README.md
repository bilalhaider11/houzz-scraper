# 🏠 Houzz Lead Generation Pipeline v2.0 - FastAPI Application

**Latest Update: September 2025** - Complete FastAPI refactoring with HTTP endpoints for all scraping functionality

A production-ready FastAPI application for scraping and enriching leads from **Houzz** and **Architizer** across all 50 U.S. states and 7+ professional types. Features advanced ZeroBounce integration, Playwright-based website mining, and intelligent email prioritization - all accessible through HTTP endpoints.

## ✨ Core Features

### 🎯 Multi-Platform Support
- **🏠 Houzz Integration**: Scrapes 50+ US states and 7 professional types
- **🏗️ Architizer Integration**: Scrapes architectural firms and professionals
- **🔄 Unified Pipeline**: Same 3-phase process for both platforms

### 🚀 3-Phase Pipeline Architecture
- **Phase 1**: Platform Profile Scraping (Houzz/Architizer)
- **Phase 2**: Advanced Website Email Mining (Playwright)
- **Phase 3**: Email Validation & Processing

### 🔧 Advanced Features
- **✅ ZeroBounce Integration**: Production-grade email verification with smart credit management
- **🌐 Playwright Automation**: JavaScript-heavy website scraping with browser automation
- **📊 Intelligent Email Selection**: Smart selection (max 2, min 1) prioritizing personal > business emails
- **💾 SQLite Database**: Persistent storage with progress tracking and resume capability
- **🛡️ Anti-Detection**: CAPTCHA handling, proxy support, rate limiting, user-agent rotation
- **⚡ High Performance**: Concurrent processing, efficient database operations, memory optimization
- **🎛️ Flexible Execution**: Run individual phases or complete pipeline with granular control

## ☁️ Cloud Deployment

> **🚀 READY TO DEPLOY TO GOOGLE CLOUD RUN?**
> 
> **Read the deployment guide:** [DEPLOY.md](DEPLOY.md)
>
> **Three commands to deploy:**
> ```bash
> gcloud auth login        # 1. Login to Google Cloud
> ./cloud-deploy.sh        # 2. Choose option 1 (Fresh deployment)
> ./setup-env-vars.sh      # 3. Choose option 1 (Load from .env)
> ```
>
> **Time:** 10 minutes | **Cost:** $30-50/month (or $5-15 with scale-to-zero)

---

## 📋 Prerequisites

### System Requirements

- **Python**: Version 3.8 or higher
- **Memory**: Minimum 8GB RAM (16GB+ recommended for production)
- **Storage**: At least 5GB free space (10GB+ recommended for large datasets)
- **Internet**: Stable broadband connection (minimum 50 Mbps recommended)

### Required Software Installation

#### 1. Install Python 3.8+ (if not already installed)

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv python3-dev
```

**CentOS/RHEL/Fedora:**
```bash
# CentOS/RHEL
sudo yum install -y python3 python3-pip python3-venv python3-devel
# Fedora
sudo dnf install -y python3 python3-pip python3-venv python3-devel
```

**macOS:**
```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
# Install Python
brew install python@3.10
```

**Windows (WSL recommended):**
```bash
# Enable WSL and install Ubuntu from Microsoft Store
# Then follow Ubuntu instructions above
```

#### 2. Install Git (if not already installed)

**Ubuntu/Debian:**
```bash
sudo apt install -y git
```

**CentOS/RHEL:**
```bash
sudo yum install -y git
```

**macOS:**
```bash
brew install git
```

#### 3. Install System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt install -y curl wget build-essential libssl-dev libffi-dev
```

**CentOS/RHEL:**
```bash
sudo yum groupinstall -y "Development Tools"
sudo yum install -y curl wget openssl-devel libffi-devel
```

### Verify Installation

```bash
# Check Python version (should be 3.8+)
python3 --version

# Check pip
pip3 --version

# Check git
git --version
```

## 🚀 Quick Start

### Option 1: Docker (Recommended - No venv needed)

Docker provides complete isolation, so you don't need a virtual environment:

```bash
# Clone and navigate to the project
git clone <repository-url>
cd houzz-scraper

# Copy environment template
cp env.example .env

# Edit .env with your API keys (optional)
nano .env

# Build and run with Docker
docker build -t houzz-scraper .
docker run -p 8000:8000 --env-file .env houzz-scraper

# Test the API
curl http://localhost:8000/health

# Access the API at http://localhost:8000/docs
```

**Note**: Docker handles all dependencies and isolation - no venv needed!

### Option 2: Local Development (venv required)

For local development outside Docker, you need a virtual environment:

```bash
# Clone and navigate to the project
git clone <repository-url>
cd houzz-scraper

# Create virtual environment (required for local development)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Copy environment template
cp env.example .env

# Edit .env with your API keys (optional)
nano .env

# Start the API server
uvicorn main:app --host 0.0.0.0 --port 8000

# Test the API
curl http://localhost:8000/health

# Access the API at http://localhost:8000/docs
```

**Note**: Use Docker for production and local testing. Use venv only for development.

### 2. Configure API Keys

**IMPORTANT**: Create a `.env` file in the project root with your API keys:

```bash
# Copy the example environment file
cp env.example .env

# Edit the .env file with your actual API keys
nano .env
```

**Required API Keys:**
- **ZeroBounce API Key**: For production-grade email verification ([Get API key](https://www.zerobounce.net/))

**Note**: The pipeline can run without API keys but with reduced functionality:
- Without ZeroBounce: Basic email validation only (use `--no-email-verification`)

### 3. Activate Virtual Environment (Local Installation Only)

**IMPORTANT**: For local installation (without Docker), always activate the virtual environment before running any commands:

```bash
# Activate the virtual environment
source venv/bin/activate

# Your terminal prompt should now show (venv) at the beginning
# (venv) user@hostname:~/houzz-scraper$
```

### 4. Start the API Server

**For Docker users:**
```bash
# Build and run with Docker (no virtual environment needed)
docker build -t houzz-scraper .
docker run -p 8000:8000 --env-file .env houzz-scraper
```

**For local installation:**
```bash
# Make sure virtual environment is activated first!
source venv/bin/activate

# Start the FastAPI server
uvicorn main:app --host 0.0.0.0 --port 8000
```

**The API will be available at:**
- API Documentation: http://localhost:8000/docs
- ReDoc Documentation: http://localhost:8000/redoc
- Health Check: http://localhost:8000/health

### 5. Test the API

```bash
# Get API information
curl http://localhost:8000/

# Health check
curl http://localhost:8000/health

# List available professional types
curl http://localhost:8000/list-professional-types

# Get scraping statistics
curl http://localhost:8000/stats

# Check proxy status
curl http://localhost:8000/proxy-status

# Run a test scrape
curl -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "houzz",
    "location": "usa",
    "professional_type": "interior-designer",
    "max_pages": 5
  }'
```

### 6. Production Usage

```bash
# Full production pipeline (USA, Houzz platform)
curl -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "houzz",
    "location": "usa",
    "professional_type": "interior-designer"
  }'

# Architizer platform (architectural firms)
curl -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "architizer",
    "location": "United States",
    "max_pages": 10
  }'
```

## 🔄 3-Phase Pipeline Process

The Lead Generation Pipeline operates in 3 distinct phases, each designed for optimal data extraction and enrichment:

### Phase 1: 🏠 Platform Profile Scraping
**What it does:**
- Extracts professional profiles from Houzz.com or Architizer.com
- Scrapes 50+ US states and 7+ professional types (Houzz) or architectural firms (Architizer)
- Collects basic profile data: name, location, website, phone, social links
- Stores all profiles in SQLite database for persistence and progress tracking
- Supports resume capability if interrupted

**API Call:**
```bash
# Houzz platform
curl -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "houzz",
    "location": "usa",
    "professional_type": "interior-designer"
  }'

# Architizer platform
curl -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "architizer",
    "location": "United States",
    "max_pages": 10
  }'
```

**Output:** Database populated with professional profiles and basic contact information.

---

### Phase 2: 🌐 Advanced Website Email Mining 
**What it does:**
- Uses Playwright browser automation to visit each professional's website
- Intelligently extracts personal and business email addresses from web pages
- Categorizes emails (personal: Gmail, Yahoo vs. business: company domains)
- Processes websites in parallel batches for maximum efficiency
- Handles JavaScript-heavy sites and various email formats
- Extracts phone numbers from websites (Architizer platform)

**Note:** This phase runs automatically as part of the complete pipeline.

**Output:** Enhanced profiles with personal and business emails extracted from professional websites.

---

### Phase 3: ✅ Email Validation & Processing
**What it does:**
**Email Validation (ZeroBounce):**
- Verifies email deliverability using ZeroBounce API
- Validates all personal and business emails found in previous phases
- Removes invalid/undeliverable emails to improve data quality
- Uses smart caching to avoid duplicate API calls (saves credits)

**Smart Email Selection:**
- Selects the best emails for each profile (max 2, min 1 required)
- Prioritizes personal emails (Gmail, Yahoo, etc.) over business emails
- Removes profiles with no valid emails (data quality control)
- Marks validated profiles as completed in the database

- Includes columns: email, name, status tracking fields

**Profile Data Management:**
- Marks profiles as completed after successful validation
- Removes profiles with zero valid emails
- Tracks detailed statistics (profiles processed, removed, invalid emails)

**Note:** This phase runs automatically as part of the complete pipeline.

**Output:** Database profiles marked as completed with validated contact data.

---

### 🚀 Complete Pipeline Execution

Run the complete pipeline for end-to-end lead generation:

```bash
# Full pipeline with ZeroBounce verification (Houzz)
curl -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "houzz",
    "location": "usa",
    "professional_type": "interior-designer"
  }'


# Architizer platform (architectural firms)
curl -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "architizer",
    "location": "United States"
  }'
```

**Phase Execution Order:**
```
1. Platform Scraping → 2. Website Email Mining → 3. Validation & Processing
```

**Key Benefits:**
- **Modularity**: Run individual phases as needed
- **Resume Capability**: Pick up where you left off if interrupted
- **Data Quality**: Each phase builds upon and enhances the previous
- **Efficiency**: Parallel processing and smart caching throughout

## 📋 Usage Examples

### Basic Usage
```bash
# Production run for USA (Houzz)
curl -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "houzz",
    "location": "usa",
    "professional_type": "interior-designer",
    "start_page": 1,
    "max_pages": 10
  }'

### Advanced Options
```bash
# Architizer platform (no professional_type required)
curl -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "architizer",
    "location": "United States",
    "max_pages": 5,
    "start_page": 1
  }'


# Check scraping progress statistics
curl http://localhost:8000/stats

# Get available professional types
curl http://localhost:8000/list-professional-types

# Check proxy status
curl http://localhost:8000/proxy-status
```

### Platform-Specific Pagination

#### Houzz Pagination
Houzz uses URL-based pagination with `?fi=` parameters:
```bash
# Scrape first 10 pages (pages 1-10)
curl -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "houzz",
    "start_page": 1,
    "max_pages": 10
  }'

# Scrape pages 11-20
curl -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "houzz",
    "start_page": 11,
    "max_pages": 10
  }'
```

#### Architizer Pagination
Architizer uses infinite scroll with "Load More" button clicks:
```bash
# Scrape first 5 pages (load 4 more times after initial page)
curl -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "architizer",
    "start_page": 1,
    "max_pages": 5
  }'

# Scrape pages 11-15 (load 10 times to reach page 11, then scrape 5 pages)
curl -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "architizer",
    "start_page": 11,
    "max_pages": 5
  }'

# Scrape all available pages (no max_pages limit)
curl -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "architizer",
    "start_page": 1
  }'
```

## 💾 Data Persistence: SQLite Database

All scraped profiles are automatically stored in a local SQLite database file to ensure data persistence and allow for easy analysis.

- **Database File**: `data/scraper.db`
- **Location**: The database is stored in the `data` directory within your project.
- **Format**: The `professionals` table contains all the scraped data, with social links and emails stored as JSON strings.

### Database Schema

The `professionals` table includes the following columns:

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PRIMARY KEY | Auto-incrementing unique identifier |
| `profile_url` | TEXT UNIQUE | Generic URL field for any platform |
| `platform` | TEXT | Platform identifier (houzz, architizer) |
| `name` | TEXT | Professional's full name |
| `website` | TEXT | Professional's website URL |
| `professional_type` | TEXT | Type of professional (interior-designer, architect, etc.) |
| `phone` | TEXT | Phone number (formatted) |
| `emails` | TEXT | JSON string: `{"personal": [...], "business": [...]}` |
| `address` | TEXT | Full address |
| `zip_code` | TEXT | ZIP code |
| `rating` | REAL | Professional rating |
| `reviews_count` | INTEGER | Number of reviews |
| `linkedin_links` | TEXT | JSON array of LinkedIn URLs |
| `facebook_links` | TEXT | JSON array of Facebook URLs |
| `instagram_links` | TEXT | JSON array of Instagram URLs |
| `twitter_links` | TEXT | JSON array of Twitter/X URLs |
| `pinterest_links` | TEXT | JSON array of Pinterest URLs |
| `youtube_links` | TEXT | JSON array of YouTube URLs |
| `other_social_links` | TEXT | JSON array of other social media URLs |
| `typical_job_cost` | TEXT | Typical job cost range |
| `followers_count` | INTEGER | Number of followers |
| `is_email_verified` | INTEGER | Email verification status (0/1) |
| `website_scraped` | INTEGER | Website scraping status (0/1) |
| `is_completed` | INTEGER | Export completion status (0/1) |
| `created_at` | TIMESTAMP | Record creation timestamp |
| `updated_at` | TIMESTAMP | Record update timestamp |

### Accessing the Database

You can access the database using any standard SQLite client:

**Command-Line `sqlite3` client:**
```bash
# Open the database
sqlite3 data/scraper.db

#-- In the SQLite prompt --#

-- List tables
.tables

-- View table schema
.schema professionals

-- Count total profiles
SELECT COUNT(*) FROM professionals;

-- View first 10 profiles
SELECT profile_url, name, website, phone, emails FROM professionals LIMIT 10;

-- Check scraping progress
SELECT 
  COUNT(*) as total_profiles,
  SUM(website_scraped) as websites_scraped,
  SUM(is_email_verified) as emails_verified,
  SUM(is_completed) as completed_profiles
FROM professionals;

-- Exit
.quit
```

## 📁 Project Structure

```
houzz-scraper/
├── main.py                 # FastAPI application (main entry point)
├── requirements.txt        # Python dependencies
├── deploy.sh              # Deployment script
├── env.example            # Environment variables template (copy to .env)
├── README.md              # Complete documentation (single source of truth)
├── Dockerfile             # Docker container configuration
├── .dockerignore          # Docker ignore file
├── cloudbuild.yaml        # Google Cloud Build configuration
├── docker-compose.yml     # Docker Compose configuration
├── docker-compose.dev.yml # Development Docker Compose
├── dev.sh                 # Development script
├── config/
│   └── config.py          # Configuration settings
├── src/
│   ├── models.py          # Data models and validation
│   ├── pipeline.py        # Main 3-phase orchestration pipeline
│   ├── houzz_scraper.py   # Houzz website scraper
│   ├── architizer_scraper.py # Architizer website scraper
│   ├── website_scraper.py # Professional website scraper (Playwright)
│   ├── zerobounce_verifier.py # ZeroBounce email verification
│   ├── database_manager.py # SQLite database manager
│   ├── database_pool.py   # Database connection pooling
│   ├── email_service.py   # Email processing utilities
│   ├── phone_formatter.py # Phone number formatting
│   ├── url_cleaner.py     # URL cleaning utility
│   ├── cache_manager.py   # Caching system
│   └── common_utils.py    # Common utilities
├── data/                  # Output CSV files and SQLite database
│   └── scraper.db         # SQLite database (created automatically)
└── logs/                  # Log files
```

## 🔌 API Endpoints

The FastAPI application provides the following endpoints:

### General Endpoints
- **GET `/`** - API information and status
- **GET `/health`** - Health check endpoint

### Professional Types
- **GET `/list-professional-types`** - List all available professional types

### Statistics & Monitoring
- **GET `/stats`** - Get scraping statistics and progress
- **GET `/proxy-status`** - Get proxy rotation status and configuration

### Scraping Operations
- **POST `/scrape`** - Start a scraping job with the complete 3-phase pipeline

### Request/Response Models

#### ScrapeRequest
```json
{
  "platform": "houzz|architizer",
  "location": "string",
  "professional_type": "string (required for Houzz, optional for Architizer)",
  "max_pages": 50,
  "start_page": 1
}
```

#### ScrapeResponse
```json
{
  "success": true,
  "message": "string",
  "profiles_scraped": 150,
  "execution_time": 125.5,
  "stats": {
    "total_profiles_processed": 150,
    "profiles_marked_completed": 145,
    "profiles_removed": 5,
    "invalid_emails_removed": 3,
    "profiles": []
    "profiles_with_valid_emails": 142,
    "profiles_without_emails": 3
  }
}
```

#### StatsResponse
```json
{
  "stats": {
    "total_profiles": 1250,
    "websites_scraped": 890,
    "completed_profiles": 1200,
    "websites_pending": 50,
    "profiles_pending_completion": 30
  }
}
```

## 🐳 Docker Deployment

### Local Docker

```bash
# Copy environment template
cp env.example .env

# Edit with your API keys
nano .env

# Build and run
docker build -t houzz-scraper .
docker run -p 8000:8000 --env-file .env houzz-scraper

# Access API at http://localhost:8000/docs
```

### Google Cloud Run Deployment

**Simple deployment with automated script:**

```bash
./cloud-deploy.sh  # Choose option 1 (Fresh deployment)
```

**Or use Cloud Build directly:**

```bash
gcloud builds submit --config cloudbuild.yaml
```

**For complete step-by-step instructions, see [DEPLOY.md](DEPLOY.md)**

## 🔧 Configuration

### Environment Variables (.env file)

Create a `.env` file in the project root with the following variables:

```bash
# Required API Keys
ZEROBOUNCE_API_KEY=your_zerobounce_api_key_here


# Optional Proxy Settings
PROXY_USERNAME=your_proxy_username
PROXY_PASSWORD=your_proxy_password
USE_PROXY_ROTATION=false
PROXY_ROTATION_INTERVAL=10
WEBSHARE_API_KEY=your_webshare_api_key
WEBSHARE_PROXY_LIST=your_proxy_list_url

# Environment Settings
HEADLESS=true
TIMEOUT=45
MAX_PAGES_PER_STATE=50
OUTPUT_DIR=data
LOG_DIR=logs
```

### Configuration Features

The system supports comprehensive configuration through `config/config.py` and environment variables:


#### Location Support
- **USA Nationwide**: `location: "usa"` for all US states
- **State-Specific**: Individual states like `"california"`, `"texas"`, `"florida"`
- **City-Specific**: Major cities within states (automatically mapped)

#### Professional Types (Houzz)
- `interior-designer` - Interior Designers
- `architect` - Architects  
- `general-contractor` - General Contractors
- `design-build` - Design-Build Firms
- `landscape-architect` - Landscape Architects
- `kitchen-and-bath` - Kitchen & Bath Designers
- `home-builders` - Home Builders
- `fireplace` - Fireplace Specialists

#### Platform Support
- **Houzz**: Requires `location` and `professional_type`
- **Architizer**: Requires `location` only (scrapes architectural firms)

### Email Prioritization Logic

The system prioritizes emails in the following order:

1. **Personal Emails** (gmail.com, yahoo.com, hotmail.com, outlook.com, icloud.com)
2. **Company Emails** (info@, contact@, hello@, office@, admin@)
3. **Any Other Valid Email** (if no personal/company email found)
4. **Blacklisted** (noreply@, no-reply@, donotreply@, support@, sales@)

### Professional Types Scraped (Houzz)

- Interior Designers (`interior-designer`)
- Architects (`architect`)
- General Contractors (`general-contractor`)
- Design-Build Firms (`design-build`)
- Landscape Architects (`landscape-architect`)
- Kitchen and Bath Designers (`kitchen-and-bath`)
- Home Builders (`home-builders`)

### Data Fields Exported

| Field | Description |
|-------|-------------|
| `profile_url` | Original profile URL |
| `name` | Professional's full name |
| `website` | Professional's website |
| `emails` | JSON string of all emails |
| `phone` | Phone number (formatted) |
| `address` | Full address |
| `professional_type` | Type of professional |
| `linkedin_links` | JSON array of LinkedIn URLs |
| `facebook_links` | JSON array of Facebook URLs |
| `instagram_links` | JSON array of Instagram URLs |
| `twitter_links` | JSON array of Twitter/X URLs |
| `pinterest_links` | JSON array of Pinterest URLs |
| `youtube_links` | JSON array of YouTube URLs |
| `other_social_links` | JSON array of other social media URLs |
| `is_email_verified` | Email verification status |
| `zip_code` | ZIP code |
| `website_scraped` | Website scraping status |
| `created_at` | Record creation timestamp |
| `updated_at` | Record update timestamp |

## 🛡️ Anti-Detection Features

- **Dynamic User Agents**: Rotates user agents to avoid detection
- **Request Delays**: Random delays between requests
- **Proxy Support**: Built-in proxy rotation capabilities
- **Browser Automation**: Uses Playwright for JavaScript-heavy sites
- **CAPTCHA Handling**: Automatic retry with delays
- **Session Management**: Maintains realistic browsing patterns
- **Rate Limiting**: Respects website rate limits
- **Error Handling**: Graceful failure handling

## 📊 Production Monitoring

### Logging
- **File Logs**: Rotating daily logs in `logs/` directory
- **Console Output**: Real-time progress updates
- **Error Tracking**: Detailed error logging with stack traces

### Progress Tracking
- **State Management**: Saves progress to resume interrupted sessions
- **Batch Processing**: Processes leads in configurable batches
- **Completion Tracking**: Tracks completed URLs and states

### Performance Metrics
- **Scraping Speed**: ~50-100 profiles per minute
- **Success Rate**: Typically 80-90% successful extraction
- **Email Verification**: Real-time validation with ZeroBounce
- **Website Mining**: ~10-20 websites per minute with Playwright

## 🎯 Expected Output

### Sample Output Statistics
- **Total Profiles**: 50,000-100,000+ (depending on scope)
- **Complete Contacts**: ~60-80% with all required fields
- **Personal Emails**: ~20-30% of total (extracted from websites)
- **Company Emails**: ~40-50% of total  
- **Phone Numbers**: ~70-85% coverage
- **Zip Codes**: ~80-90% coverage
- **Social Media Profiles**: ~30-50% coverage across 7+ platforms (extracted from websites)

### CSV File Format
```csv
profile_url,name,website,emails,phone,address,professional_type,linkedin_links,facebook_links,instagram_links,twitter_links,pinterest_links,youtube_links,other_social_links,is_email_verified,zip_code,website_scraped,created_at,updated_at
https://www.houzz.com/pro/example,John Smith,https://example.com,"{""personal"":[""john.smith@gmail.com""],""business"":[""info@example.com""]}",+15551234567,123 Main St,interior-designer,"[""https://linkedin.com/in/johnsmith""]","[""https://facebook.com/johnsmith""]","[""https://instagram.com/johnsmith""]","[""https://twitter.com/johnsmith""]","[""https://pinterest.com/johnsmith""]","[""https://youtube.com/johnsmith""]","[]",1,90210,1,2024-01-15T10:30:00,2024-01-15T10:30:00
```

## 🐛 Troubleshooting

### Common Issues

1. **"No API key configured"**
   - Solution: Add required API keys to `.env` file

2. **"Playwright browser not found"**  
   - Solution: Run `playwright install chromium`

3. **"Module not found"**
   - Solution: For local installation, ensure virtual environment is activated: `source venv/bin/activate`
   - For Docker: Ensure you're running the container with the correct image

4. **"Environment file not found"**
   - Solution: Copy `env.example` to `.env` and configure your API keys

5. **"Invalid location"**
   - Solution: Use valid locations like `"usa"`, `"california"`, `"texas"`, etc. Check available locations in config

6. **"Invalid professional type"**
   - Solution: Use valid professional types like `"interior-designer"`, `"architect"`, etc. Check available types with `/list-professional-types`

7. **"Rate limit exceeded"**
   - Solution: Increase delays in config or use proxy service

8. **"Database locked"**
   - Solution: Ensure no other processes are accessing the database

### Check System Status
```bash
# Check scraping progress
curl http://localhost:8000/stats

# Check database status
sqlite3 data/scraper.db "SELECT COUNT(*) FROM professionals;"
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## 📄 License

This project is for educational and legitimate business use only. Please respect website terms of service and rate limits.

## ⚠️ Disclaimer

This tool is designed for legitimate lead generation purposes. Users are responsible for:
- Complying with website terms of service
- Respecting rate limits and robots.txt
- Following applicable data privacy laws
- Using collected data ethically and legally

---

**Need help?** Check the logs in `logs/` directory or run with `--log-level DEBUG` for detailed output.