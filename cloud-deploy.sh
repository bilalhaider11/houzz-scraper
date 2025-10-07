#!/bin/bash

# =====================================================
# Google Cloud Run Deployment Script
# =====================================================
# This script automates the deployment of the Houzz scraper to Google Cloud Run
# =====================================================

set -e  # Exit on any error

echo "🚀 Google Cloud Run Deployment Script"
echo "======================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ gcloud CLI is not installed.${NC}"
    echo "Please install it from: https://cloud.google.com/sdk/docs/install"
    echo ""
    echo "Quick install:"
    echo "  curl https://sdk.cloud.google.com | bash"
    echo "  exec -l \$SHELL"
    exit 1
fi

echo -e "${GREEN}✅ gcloud CLI found${NC}"

# Check if user is logged in
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
    echo -e "${YELLOW}⚠️  Not logged in to Google Cloud${NC}"
    echo "Logging in..."
    gcloud auth login
fi

ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -n 1)
echo -e "${GREEN}✅ Logged in as: $ACCOUNT${NC}"

# Get or set project ID
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)

if [ -z "$PROJECT_ID" ]; then
    echo -e "${YELLOW}⚠️  No project set${NC}"
    echo ""
    echo "Available projects:"
    gcloud projects list --format="table(projectId,name,projectNumber)"
    echo ""
    read -p "Enter your Google Cloud Project ID: " PROJECT_ID
    gcloud config set project $PROJECT_ID
fi

echo -e "${GREEN}✅ Using project: $PROJECT_ID${NC}"
echo ""

# Configuration
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-houzz-scraper}"

echo "Configuration:"
echo "  Project ID: $PROJECT_ID"
echo "  Region: $REGION"
echo "  Service Name: $SERVICE_NAME"
echo ""

# Ask user what they want to do
echo "What would you like to do?"
echo "1) Fresh deployment (enable APIs, build, and deploy)"
echo "2) Quick redeploy (just rebuild and deploy)"
echo "3) Update environment variables only"
echo "4) View service logs"
echo "5) Get service URL"
echo "6) Delete service"
echo ""
read -p "Enter your choice (1-6): " CHOICE

case $CHOICE in
    1)
        echo ""
        echo -e "${BLUE}📋 Starting fresh deployment...${NC}"
        echo ""
        
        # Enable required APIs
        echo "Enabling required Google Cloud APIs..."
        gcloud services enable cloudbuild.googleapis.com
        gcloud services enable run.googleapis.com
        gcloud services enable containerregistry.googleapis.com
        gcloud services enable artifactregistry.googleapis.com
        echo -e "${GREEN}✅ APIs enabled${NC}"
        echo ""
        
        # Build and deploy
        echo "Building and deploying to Cloud Run..."
        echo "This may take 5-10 minutes..."
        gcloud builds submit --config cloudbuild.yaml
        
        echo ""
        echo -e "${GREEN}🎉 Deployment successful!${NC}"
        echo ""
        
        # Get service URL
        SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)' 2>/dev/null || echo "")
        
        if [ -n "$SERVICE_URL" ]; then
            echo -e "${GREEN}Service URL: $SERVICE_URL${NC}"
        fi
        
        echo ""
        echo -e "${YELLOW}⚠️  IMPORTANT: You need to set environment variables!${NC}"
        echo ""
        echo "Run this command to set your environment variables:"
        echo ""
        echo "gcloud run services update $SERVICE_NAME \\"
        echo "  --region $REGION \\"
        echo "  --update-env-vars \"ZEROBOUNCE_API_KEY=your_key\" \\"
        echo "  --update-env-vars \"GOOGLE_SEARCH_API_KEY=your_key\" \\"
        echo "  --update-env-vars \"GOOGLE_SEARCH_CX=your_cx\" \\"
        echo "  --update-env-vars \"GOOGLE_SHEETS_CLIENT_EMAIL=your_email\" \\"
        echo "  --update-env-vars \"GOOGLE_SHEETS_PROJECT_ID=your_project_id\" \\"
        echo "  --update-env-vars \"GOOGLE_SHEETS_PRIVATE_KEY=your_private_key\" \\"
        echo "  --update-env-vars \"GOOGLE_SHEETS_SPREADSHEET_ID=your_sheet_id\" \\"
        echo "  --update-env-vars \"PROXY_USERNAME=your_proxy_user\" \\"
        echo "  --update-env-vars \"PROXY_PASSWORD=your_proxy_pass\""
        echo ""
        echo "Or run: ./cloud-deploy.sh  (and choose option 3)"
        ;;
        
    2)
        echo ""
        echo -e "${BLUE}📋 Redeploying service...${NC}"
        echo ""
        
        gcloud builds submit --config cloudbuild.yaml
        
        echo ""
        echo -e "${GREEN}🎉 Redeployment successful!${NC}"
        
        SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)' 2>/dev/null || echo "")
        
        if [ -n "$SERVICE_URL" ]; then
            echo -e "${GREEN}Service URL: $SERVICE_URL${NC}"
        fi
        ;;
        
    3)
        echo ""
        echo -e "${BLUE}📋 Updating environment variables...${NC}"
        echo ""
        
        # Check if .env file exists
        if [ ! -f ".env" ]; then
            echo -e "${RED}❌ .env file not found${NC}"
            echo "Please create a .env file with your environment variables"
            echo "You can copy from env.example: cp env.example .env"
            exit 1
        fi
        
        echo "Reading environment variables from .env file..."
        
        # Read .env and build the update command
        ENV_VARS=""
        while IFS='=' read -r key value; do
            # Skip empty lines and comments
            if [[ -z "$key" ]] || [[ "$key" == \#* ]]; then
                continue
            fi
            
            # Remove quotes from value
            value="${value%\"}"
            value="${value#\"}"
            
            # Skip placeholder values
            if [[ "$value" == *"your_"* ]] || [[ "$value" == *"_here"* ]]; then
                echo -e "${YELLOW}⚠️  Skipping placeholder: $key${NC}"
                continue
            fi
            
            # Add to env vars
            if [ -n "$ENV_VARS" ]; then
                ENV_VARS="$ENV_VARS,$key=$value"
            else
                ENV_VARS="$key=$value"
            fi
            
            echo -e "${GREEN}✓ $key${NC}"
        done < .env
        
        if [ -z "$ENV_VARS" ]; then
            echo -e "${RED}❌ No valid environment variables found in .env${NC}"
            exit 1
        fi
        
        echo ""
        echo "Updating Cloud Run service with environment variables..."
        
        gcloud run services update $SERVICE_NAME \
            --region $REGION \
            --set-env-vars "$ENV_VARS"
        
        echo ""
        echo -e "${GREEN}✅ Environment variables updated!${NC}"
        ;;
        
    4)
        echo ""
        echo -e "${BLUE}📋 Viewing service logs...${NC}"
        echo "Press Ctrl+C to exit"
        echo ""
        
        gcloud logs tail --service=$SERVICE_NAME --region=$REGION --follow
        ;;
        
    5)
        echo ""
        SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)' 2>/dev/null || echo "")
        
        if [ -n "$SERVICE_URL" ]; then
            echo -e "${GREEN}Service URL: $SERVICE_URL${NC}"
            echo ""
            echo "Test endpoints:"
            echo "  Health check: curl $SERVICE_URL/health"
            echo "  API docs: $SERVICE_URL/docs"
            echo ""
            echo "Test scraping:"
            echo "  curl -X POST $SERVICE_URL/scrape \\"
            echo "    -H 'Content-Type: application/json' \\"
            echo "    -d '{\"platform\":\"houzz\",\"location\":\"california\",\"professional_type\":\"interior-designer\",\"max_pages\":2}'"
        else
            echo -e "${RED}❌ Service not found or not deployed${NC}"
        fi
        ;;
        
    6)
        echo ""
        echo -e "${RED}⚠️  WARNING: This will delete the Cloud Run service!${NC}"
        read -p "Are you sure? (yes/no): " CONFIRM
        
        if [ "$CONFIRM" = "yes" ]; then
            echo ""
            echo "Deleting service..."
            gcloud run services delete $SERVICE_NAME --region $REGION --quiet
            echo -e "${GREEN}✅ Service deleted${NC}"
        else
            echo "Cancelled"
        fi
        ;;
        
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

echo ""
echo "Done! 🎉"

