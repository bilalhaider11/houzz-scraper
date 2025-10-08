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

# Ensure cloudbuild.yaml doesn't contain sensitive data
echo -e "${BLUE}🔧 Verifying cloudbuild.yaml...${NC}"
if [ -f ".env" ]; then
    echo -e "${GREEN}✅ Environment variables will be loaded from .env file${NC}"
else
    echo -e "${YELLOW}⚠️  No .env file found${NC}"
fi

echo ""
echo "Configuration:"
echo "  Project ID: $PROJECT_ID"
echo "  Region: $REGION"
echo "  Service Name: $SERVICE_NAME"
echo ""

# Function to clear local database and state files
clear_local_data() {
    echo ""
    echo -e "${BLUE}🧹 Clearing local database and state files...${NC}"
    
    # Remove SQLite database
    if [ -f "data/scraper.db" ]; then
        rm -f data/scraper.db
        echo -e "${GREEN}✓ Removed database: data/scraper.db${NC}"
    else
        echo -e "${YELLOW}  Database file not found (already clean)${NC}"
    fi
    
    # Remove state manager file
    if [ -f "scraping_state.json" ]; then
        rm -f scraping_state.json
        echo -e "${GREEN}✓ Removed state file: scraping_state.json${NC}"
    else
        echo -e "${YELLOW}  State file not found (already clean)${NC}"
    fi
    
    # Remove log files
    if [ -d "logs" ] && [ "$(ls -A logs 2>/dev/null)" ]; then
        rm -f logs/*.log
        echo -e "${GREEN}✓ Cleared log files${NC}"
    else
        echo -e "${YELLOW}  No log files to clear${NC}"
    fi
    
    echo -e "${GREEN}✅ Local data cleared successfully!${NC}"
    echo ""
}

# Ask user what they want to do
echo "What would you like to do?"
echo "1) Fresh deployment (enable APIs, build, and deploy)"
echo "2) Quick redeploy (just rebuild and deploy)"
echo "3) Update environment variables only"
echo "4) View service logs"
echo "5) Get service URL"
echo "6) Delete service"
echo "7) Complete cleanup and redeploy (delete + fresh deploy)"
echo "8) Clear local database and state files (without deploying)"
echo ""
read -p "Enter your choice (1-8): " CHOICE

case $CHOICE in
    1)
        echo ""
        echo -e "${BLUE}📋 Starting fresh deployment...${NC}"
        echo ""
        
        # Ask if user wants to clear local data before deploying
        read -p "Clear local database and state files before deployment? (yes/no): " CLEAR_DATA
        if [ "$CLEAR_DATA" = "yes" ] || [ "$CLEAR_DATA" = "y" ]; then
            clear_local_data
        fi
        
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
        
        # Automatically set environment variables from .env file
        if [ -f ".env" ]; then
            echo -e "${BLUE}🔧 Setting environment variables from .env file...${NC}"
            
            # Use Python to create a YAML file for gcloud
            python3 -c "
import os
import yaml

env_vars = {}
with open('.env', 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            # Remove quotes if present
            if value.startswith('\"') and value.endswith('\"'):
                value = value[1:-1]
            env_vars[key] = value

# Add base Cloud Run environment variables
env_vars['HEADLESS'] = 'true'
env_vars['TIMEOUT'] = '30'
env_vars['MAX_PAGES_PER_STATE'] = '2'
env_vars['OUTPUT_DIR'] = '/tmp/data'
env_vars['LOG_DIR'] = '/tmp/logs'

# Write to YAML file
with open('.env.yaml', 'w') as f:
    yaml.dump(env_vars, f, default_flow_style=False)
"
            
            if [ -f ".env.yaml" ]; then
                gcloud run services update $SERVICE_NAME \
                    --region=$REGION \
                    --env-vars-file=.env.yaml
                echo -e "${GREEN}✅ Environment variables updated${NC}"
                rm -f .env.yaml
            fi
        else
            echo -e "${YELLOW}⚠️  No .env file found - skipping environment variable setup${NC}"
        fi
        
        # Configure public access
        echo ""
        echo -e "${BLUE}🔓 Configuring public access...${NC}"
        if gcloud run services add-iam-policy-binding $SERVICE_NAME \
            --region=$REGION \
            --member=allUsers \
            --role=roles/run.invoker \
            --quiet 2>/dev/null; then
            echo -e "${GREEN}✅ Public access configured${NC}"
        else
            echo -e "${YELLOW}⚠️  Public access already configured or failed${NC}"
        fi
        
        # Get service URL
        SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)' 2>/dev/null || echo "")
        
        if [ -n "$SERVICE_URL" ]; then
            echo ""
            echo -e "${GREEN}Service URL: $SERVICE_URL${NC}"
            echo "API Documentation: $SERVICE_URL/docs"
            echo "Health Check: $SERVICE_URL/health"
        fi
        
        echo ""
        echo -e "${GREEN}✅ Fresh deployment completed successfully!${NC}"
        ;;
        
    2)
        echo ""
        echo -e "${BLUE}📋 Redeploying service...${NC}"
        echo ""
        
        # Ask if user wants to clear local data before deploying
        read -p "Clear local database and state files before deployment? (yes/no): " CLEAR_DATA
        if [ "$CLEAR_DATA" = "yes" ] || [ "$CLEAR_DATA" = "y" ]; then
            clear_local_data
        fi
        
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
        
    7)
        echo ""
        echo -e "${BLUE}🧹 Starting complete cleanup and redeploy...${NC}"
        echo ""
        
        # Ask if user wants to clear local data before deploying
        read -p "Clear local database and state files before deployment? (yes/no): " CLEAR_DATA
        if [ "$CLEAR_DATA" = "yes" ] || [ "$CLEAR_DATA" = "y" ]; then
            clear_local_data
        fi
        
        # Delete existing service
        echo "Deleting existing service..."
        if gcloud run services delete $SERVICE_NAME --region=$REGION --quiet; then
            echo -e "${GREEN}✅ Service deleted${NC}"
        else
            echo -e "${YELLOW}⚠️  Service deletion failed or service didn't exist${NC}"
        fi
        
        # Wait a moment for cleanup
        echo "Waiting for cleanup..."
        sleep 5
        
        # Enable required APIs
        echo "Enabling required Google Cloud APIs..."
        gcloud services enable run.googleapis.com
        gcloud services enable cloudbuild.googleapis.com
        gcloud services enable containerregistry.googleapis.com
        echo -e "${GREEN}✅ APIs enabled${NC}"
        
        # Build and deploy
        echo ""
        echo "Building and deploying to Cloud Run..."
        echo "This may take 5-10 minutes..."
        
        if gcloud builds submit --config cloudbuild.yaml; then
            echo ""
            echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
            echo ""
            
            # Automatically set environment variables from .env file
            if [ -f ".env" ]; then
                echo -e "${BLUE}🔧 Setting environment variables from .env file...${NC}"
                
                # Use Python to create a YAML file for gcloud
                python3 -c "
import os
import yaml

env_vars = {}
with open('.env', 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            # Remove quotes if present
            if value.startswith('\"') and value.endswith('\"'):
                value = value[1:-1]
            env_vars[key] = value

# Add base Cloud Run environment variables
env_vars['HEADLESS'] = 'true'
env_vars['TIMEOUT'] = '30'
env_vars['MAX_PAGES_PER_STATE'] = '2'
env_vars['OUTPUT_DIR'] = '/tmp/data'
env_vars['LOG_DIR'] = '/tmp/logs'

# Write to YAML file
with open('.env.yaml', 'w') as f:
    yaml.dump(env_vars, f, default_flow_style=False)
"
                
                if [ -f ".env.yaml" ]; then
                    gcloud run services update $SERVICE_NAME \
                        --region=$REGION \
                        --env-vars-file=.env.yaml
                    echo -e "${GREEN}✅ Environment variables updated${NC}"
                    rm -f .env.yaml
                fi
            else
                echo -e "${YELLOW}⚠️  No .env file found - skipping environment variable setup${NC}"
            fi
            
            # Configure public access
            echo ""
            echo -e "${BLUE}🔓 Configuring public access...${NC}"
            if gcloud run services add-iam-policy-binding $SERVICE_NAME \
                --region=$REGION \
                --member=allUsers \
                --role=roles/run.invoker \
                --quiet 2>/dev/null; then
                echo -e "${GREEN}✅ Public access configured${NC}"
            else
                echo -e "${YELLOW}⚠️  Public access already configured or failed${NC}"
            fi
            
            # Get service URL
            SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")
            echo ""
            echo "Service URL: $SERVICE_URL"
            echo "API Documentation: $SERVICE_URL/docs"
            echo "Health Check: $SERVICE_URL/health"
            echo ""
            echo -e "${GREEN}✅ Complete cleanup and redeploy finished!${NC}"
        else
            echo -e "${RED}❌ Deployment failed${NC}"
            exit 1
        fi
        ;;
        
    8)
        echo ""
        echo -e "${BLUE}🧹 Clearing local database and state files only...${NC}"
        echo -e "${RED}⚠️  WARNING: This will permanently delete:${NC}"
        echo "   • SQLite database (data/scraper.db)"
        echo "   • State manager file (scraping_state.json)"
        echo "   • All log files (logs/*.log)"
        echo ""
        read -p "Are you sure you want to continue? (yes/no): " CONFIRM
        
        if [ "$CONFIRM" = "yes" ]; then
            clear_local_data
            echo -e "${GREEN}✅ Local data cleared successfully!${NC}"
            echo ""
            echo "Note: This only cleared local files. Cloud Run services are stateless."
            echo "The deployed service will start fresh on next deployment."
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

