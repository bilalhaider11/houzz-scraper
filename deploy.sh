#!/bin/bash

# Houzz Lead Generation Pipeline v2.0 Deployment Script
# Optimized for hourly scraping: 1 request/hour, 2 pages per request
# with ZeroBounce email verification, Playwright automation, and enhanced features

set -e  # Exit on any error

echo "🚀 Starting Houzz Lead Generation Pipeline v2.0 Deployment"
echo "=========================================================="
echo "📋 Optimized for: 1 request/hour, 2 pages per request"
echo "💾 Memory: 8Gi, CPU: 2, Always Active"
echo "🗄️  Storage: SQLite3 (no external storage needed)"
echo "🔧 Environment: All API keys and proxy settings included"
echo ""

# Check if Python 3.8+ is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
REQUIRED_VERSION="3.8"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ Python version $PYTHON_VERSION is too old. Please install Python 3.8 or higher."
    exit 1
fi

echo "✅ Python $PYTHON_VERSION detected"

# Install system dependencies if needed
echo "🔧 Checking system dependencies..."
if ! python3 -m venv --help &> /dev/null; then
    echo "📦 Installing python3-venv package..."
    if command -v apt &> /dev/null; then
        # Ubuntu/Debian
        sudo apt update
        sudo apt install -y python3-venv python3-pip
    elif command -v yum &> /dev/null; then
        # CentOS/RHEL
        sudo yum install -y python3-venv python3-pip
    elif command -v dnf &> /dev/null; then
        # Fedora
        sudo dnf install -y python3-venv python3-pip
    else
        echo "❌ Unable to install python3-venv automatically. Please install it manually:"
        echo "   Ubuntu/Debian: sudo apt install python3-venv python3-pip"
        echo "   CentOS/RHEL: sudo yum install python3-venv python3-pip"
        echo "   Fedora: sudo dnf install python3-venv python3-pip"
        exit 1
    fi
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "❌ Failed to create virtual environment. Please try:"
        echo "   sudo apt install python3-venv python3-pip"
        echo "   Then run this script again."
        exit 1
    fi
else
    echo "✅ Virtual environment already exists"
    # Check if virtual environment is properly configured
    if [ ! -f "venv/bin/python" ]; then
        echo "❌ Virtual environment appears corrupted. Removing and recreating..."
        rm -rf venv
        python3 -m venv venv
        if [ $? -ne 0 ]; then
            echo "❌ Failed to recreate virtual environment."
            exit 1
        fi
    fi
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Verify virtual environment is active
if [ "$VIRTUAL_ENV" = "" ]; then
    echo "❌ Virtual environment activation failed. Trying alternative activation..."
    source venv/bin/activate
    if [ "$VIRTUAL_ENV" = "" ]; then
        echo "❌ Virtual environment activation failed. Please check the venv directory."
        exit 1
    fi
fi

echo "✅ Virtual environment activated: $VIRTUAL_ENV"

# Upgrade pip using the virtual environment's pip
echo "⬆️  Upgrading pip..."
venv/bin/pip install --upgrade pip

# Install dependencies
echo "📚 Installing dependencies..."
if ! venv/bin/pip install -r requirements.txt; then
    echo "❌ Failed to install dependencies. Please check your internet connection and try again."
    exit 1
fi

# Install Playwright browsers
echo "🌐 Installing Playwright browsers..."
if ! venv/bin/playwright install chromium; then
    echo "❌ Failed to install Playwright browsers. Please try manually:"
    echo "   source venv/bin/activate"
    echo "   playwright install chromium"
    exit 1
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p data logs

# Copy environment template if .env doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "⚠️  Please edit .env file with your actual API keys before running the scraper"
        echo "   nano .env"
    else
        echo "⚠️  .env.example not found. Please create .env file manually with required API keys"
        echo "   Required variables: ZEROBOUNCE_API_KEY"
    fi
else
    echo "✅ .env file already exists"
fi

# Make main script executable
chmod +x main.py

# Test the installation
echo "🧪 Testing installation..."
if ! python3 -c "import sys; sys.path.insert(0, '.'); from src.pipeline import LeadEnrichmentPipeline; print('✅ Pipeline import successful')" 2>/dev/null; then
    echo "❌ Installation test failed. Please check the error messages above."
    exit 1
fi

# Create systemd service for production (optional)
if command -v systemctl &> /dev/null && [ "$1" = "--systemd" ]; then
    echo "🔧 Setting up systemd service..."
    
    # Create service file
    sudo tee /etc/systemd/system/houzz-scraper.service > /dev/null <<EOF
[Unit]
Description=Houzz Lead Scraper
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
Environment=PATH=$(pwd)/venv/bin
ExecStart=$(pwd)/venv/bin/python $(pwd)/main.py
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

    # Enable and start service
    sudo systemctl daemon-reload
    sudo systemctl enable houzz-scraper.service
    
    echo "✅ Systemd service 'houzz-scraper' created and enabled"
    echo "   Start with: sudo systemctl start houzz-scraper"
    echo "   Check status: sudo systemctl status houzz-scraper"
    echo "   View logs: sudo journalctl -u houzz-scraper -f"
fi

echo ""
echo "🎉 Deployment completed successfully!"
echo "======================================"
echo ""
echo "⚠️  IMPORTANT: Always activate the virtual environment before running commands:"
echo "   source venv/bin/activate"
echo ""
echo "Next steps for hourly scraping:"
echo "1. Edit .env file with your API keys (ZeroBounce + Proxy settings)"
echo "2. Deploy to Cloud Run: gcloud builds submit --config cloudbuild.yaml"
echo "3. Set all environment variables:"
echo "   gcloud run services update houzz-scraper --region=us-central1 \\"
echo "     --set-env-vars ZEROBOUNCE_API_KEY=your_key \\"
echo "     --set-env-vars PROXY_USERNAME=your_proxy_user \\"
echo "     --set-env-vars PROXY_PASSWORD=your_proxy_pass"
echo "4. Test: curl -X POST https://your-service-url/scrape -H 'Content-Type: application/json' -d '{\"platform\":\"houzz\",\"location\":\"usa\",\"professional_type\":\"interior-designer\",\"max_pages\":2}'"
echo ""
echo "💰 Cost Estimate:"
echo "  - Monthly: ~$2.50-4.00 (always active with 8Gi memory)"
echo "  - Storage: $0 (SQLite3 uses container storage)"
echo ""
echo "🔧 Local Development Commands:"
echo "  python3 main.py --help                                    # Show all options"
echo "  python3 main.py --platform houzz --list-states            # List all available US states"
echo "  python3 main.py --platform houzz --stats                  # Show scraping statistics"
echo ""
echo "🚀 Production Deployment:"
echo "  gcloud builds submit --config cloudbuild.yaml            # Deploy to Cloud Run"
echo "  docker-compose up -d                                      # Run locally with Docker"
echo ""
echo "📊 Monitoring:"
echo "  gcloud logs tail --service=houzz-scraper                  # View Cloud Run logs"
echo "  docker-compose logs -f                                    # View local Docker logs"
echo ""
echo "Output will be saved in: ./data/"
echo "Logs will be saved in: ./logs/"
echo ""
echo "Troubleshooting:"
echo "  - If you get import errors, ensure virtual environment is activated"
echo "  - If Playwright fails, run: playwright install chromium"
echo "  - If API errors occur, check your .env file configuration"
