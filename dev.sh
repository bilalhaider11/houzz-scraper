#!/bin/bash

# Development setup script for Houzz Scraper
# This script sets up a local development environment without Docker

set -e

echo "🚀 Setting up Houzz Scraper development environment..."

# Check if Python 3.9+ is available
python_version=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
required_version="3.9"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python 3.9+ is required. Found: $python_version"
    exit 1
fi

echo "✅ Python version check passed: $python_version"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install/upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "📚 Installing Python dependencies..."
pip install -r requirements.txt

# Install Playwright browsers
echo "🎭 Installing Playwright browsers..."
playwright install chromium

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p data logs

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Copying from env.example..."
    cp env.example .env
    echo "📝 Please edit .env file with your API keys and configuration"
fi

echo ""
echo "✅ Development environment setup complete!"
echo ""
echo "To start development:"
echo "  1. Activate virtual environment: source venv/bin/activate"
echo "  2. Run the API server: uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
echo "  3. Open http://localhost:8000/docs for API documentation"
echo ""
echo "To run without Docker (faster for development):"
echo "  ./dev.sh && source venv/bin/activate && uvicorn main:app --reload"
