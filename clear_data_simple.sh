#!/bin/bash

# Quick clear database and state files
echo "🧹 Quick clearing Docker data..."

# Stop containers and remove volumes
docker compose down && \
docker volume rm houzz-scraper_houzz_data houzz-scraper_houzz_logs 2>/dev/null && \
docker volume prune -f

echo "✅ Data cleared! Run 'docker compose up --build' to start fresh."