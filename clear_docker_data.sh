#!/bin/bash

# Clear Database and State Manager Files from Docker
# This script removes persistent data volumes and rebuilds the Docker container

echo "🧹 Clearing Docker database and state files..."

# Stop and remove containers
echo "📦 Stopping Docker containers..."
docker-compose down

# Remove named volumes (this clears all persistent data)
echo "🗑️  Removing persistent data volumes..."
docker volume rm houzz-scraper_houzz_data 2>/dev/null || echo "   Volume houzz-scraper_houzz_data not found"
docker volume rm houzz-scraper_houzz_logs 2>/dev/null || echo "   Volume houzz-scraper_houzz_logs not found"

# Remove any dangling volumes
echo "🧽 Cleaning up dangling volumes..."
docker volume prune -f

# Remove the Docker image to force rebuild
echo "🔄 Removing Docker image to force rebuild..."
docker image rm houzz-scraper_houzz-scraper 2>/dev/null || echo "   Image houzz-scraper_houzz-scraper not found"

# Clean up any dangling images
echo "🧽 Cleaning up dangling images..."
docker image prune -f

echo ""
echo "✅ Docker data cleared successfully!"
echo ""
echo "📋 What was cleared:"
echo "   • SQLite database (data/scraper.db)"
echo "   • State manager file (scraping_state.json)"
echo "   • All log files"
echo "   • All persistent data volumes"
echo ""
echo "🚀 To rebuild and start fresh:"
echo "   docker-compose up --build"
echo ""
echo "⚠️  Note: This will start with a completely fresh database and state."