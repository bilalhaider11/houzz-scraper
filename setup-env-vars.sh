#!/bin/bash

# =====================================================
# Cloud Run Environment Variables Setup Script
# =====================================================
# Interactive script to set environment variables in Cloud Run
# =====================================================

set -e

echo "🔐 Cloud Run Environment Variables Setup"
echo "========================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-houzz-scraper}"

# Get project ID
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)

if [ -z "$PROJECT_ID" ]; then
    echo "No project set. Please run: gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

echo -e "${GREEN}Project: $PROJECT_ID${NC}"
echo -e "${GREEN}Service: $SERVICE_NAME${NC}"
echo -e "${GREEN}Region: $REGION${NC}"
echo ""

# Check if service exists
if ! gcloud run services describe $SERVICE_NAME --region $REGION &> /dev/null; then
    echo "❌ Service '$SERVICE_NAME' not found in region '$REGION'"
    echo "Please deploy the service first: ./cloud-deploy.sh"
    exit 1
fi

echo "This script will help you set up environment variables for your Cloud Run service."
echo ""
echo "Choose an option:"
echo "1) Load from .env file (recommended)"
echo "2) Enter variables manually"
echo "3) Use Secret Manager (most secure)"
echo ""
read -p "Enter your choice (1-3): " CHOICE

case $CHOICE in
    1)
        if [ ! -f ".env" ]; then
            echo "❌ .env file not found"
            echo "Please create one: cp env.example .env"
            exit 1
        fi
        
        echo ""
        echo "Reading from .env file..."
        echo ""
        
        # Build env vars string
        ENV_VARS=""
        SKIPPED=0
        ADDED=0
        
        while IFS='=' read -r key value; do
            # Skip empty lines and comments
            if [[ -z "$key" ]] || [[ "$key" == \#* ]]; then
                continue
            fi
            
            # Trim whitespace
            key=$(echo "$key" | xargs)
            value=$(echo "$value" | xargs)
            
            # Remove quotes
            value="${value%\"}"
            value="${value#\"}"
            value="${value%\'}"
            value="${value#\'}"
            
            # Skip placeholder values
            if [[ "$value" == *"your_"* ]] || [[ "$value" == *"_here"* ]] || [[ -z "$value" ]]; then
                echo -e "${YELLOW}⊘ Skipping: $key (placeholder or empty)${NC}"
                ((SKIPPED++))
                continue
            fi
            
            # Add to env vars
            if [ -n "$ENV_VARS" ]; then
                ENV_VARS="$ENV_VARS,$key=$value"
            else
                ENV_VARS="$key=$value"
            fi
            
            echo -e "${GREEN}✓ Added: $key${NC}"
            ((ADDED++))
        done < .env
        
        echo ""
        echo "Summary: $ADDED variables added, $SKIPPED skipped"
        echo ""
        
        if [ -z "$ENV_VARS" ]; then
            echo "❌ No valid environment variables found"
            echo "Please edit your .env file and replace placeholder values"
            exit 1
        fi
        
        echo "Updating Cloud Run service..."
        gcloud run services update $SERVICE_NAME \
            --region $REGION \
            --set-env-vars "$ENV_VARS"
        
        echo ""
        echo -e "${GREEN}✅ Environment variables updated successfully!${NC}"
        ;;
        
    2)
        echo ""
        echo "Enter your environment variables (press Enter to skip):"
        echo ""
        
        # Required variables
        read -p "ZeroBounce API Key: " ZEROBOUNCE_API_KEY
        read -p "Google Search API Key: " GOOGLE_SEARCH_API_KEY
        read -p "Google Search CX: " GOOGLE_SEARCH_CX
        read -p "Google Sheets Spreadsheet ID: " GOOGLE_SHEETS_SPREADSHEET_ID
        read -p "Google Sheets Worksheet Name [Sheet1]: " GOOGLE_SHEETS_WORKSHEET_NAME
        GOOGLE_SHEETS_WORKSHEET_NAME=${GOOGLE_SHEETS_WORKSHEET_NAME:-Sheet1}
        read -p "Google Sheets Client Email: " GOOGLE_SHEETS_CLIENT_EMAIL
        read -p "Google Sheets Project ID: " GOOGLE_SHEETS_PROJECT_ID
        read -p "Google Sheets Profiles Spreadsheet ID: " GOOGLE_SHEETS_PROFILES_SPREADSHEET_ID
        read -p "Google Sheets Profiles Worksheet Name [Profiles]: " GOOGLE_SHEETS_PROFILES_WORKSHEET_NAME
        GOOGLE_SHEETS_PROFILES_WORKSHEET_NAME=${GOOGLE_SHEETS_PROFILES_WORKSHEET_NAME:-Profiles}
        
        echo ""
        echo "Enter Google Sheets Private Key (paste the entire key including BEGIN/END lines):"
        echo "Press Ctrl+D when done:"
        GOOGLE_SHEETS_PRIVATE_KEY=$(cat)
        
        echo ""
        read -p "Proxy Username: " PROXY_USERNAME
        read -p "Proxy Password: " PROXY_PASSWORD
        read -p "Use Proxy Rotation (true/false) [true]: " USE_PROXY_ROTATION
        USE_PROXY_ROTATION=${USE_PROXY_ROTATION:-true}
        
        # Build command
        CMD="gcloud run services update $SERVICE_NAME --region $REGION"
        
        [ -n "$ZEROBOUNCE_API_KEY" ] && CMD="$CMD --update-env-vars ZEROBOUNCE_API_KEY=$ZEROBOUNCE_API_KEY"
        [ -n "$GOOGLE_SEARCH_API_KEY" ] && CMD="$CMD --update-env-vars GOOGLE_SEARCH_API_KEY=$GOOGLE_SEARCH_API_KEY"
        [ -n "$GOOGLE_SEARCH_CX" ] && CMD="$CMD --update-env-vars GOOGLE_SEARCH_CX=$GOOGLE_SEARCH_CX"
        [ -n "$GOOGLE_SHEETS_SPREADSHEET_ID" ] && CMD="$CMD --update-env-vars GOOGLE_SHEETS_SPREADSHEET_ID=$GOOGLE_SHEETS_SPREADSHEET_ID"
        [ -n "$GOOGLE_SHEETS_WORKSHEET_NAME" ] && CMD="$CMD --update-env-vars GOOGLE_SHEETS_WORKSHEET_NAME=$GOOGLE_SHEETS_WORKSHEET_NAME"
        [ -n "$GOOGLE_SHEETS_CLIENT_EMAIL" ] && CMD="$CMD --update-env-vars GOOGLE_SHEETS_CLIENT_EMAIL=$GOOGLE_SHEETS_CLIENT_EMAIL"
        [ -n "$GOOGLE_SHEETS_PROJECT_ID" ] && CMD="$CMD --update-env-vars GOOGLE_SHEETS_PROJECT_ID=$GOOGLE_SHEETS_PROJECT_ID"
        [ -n "$GOOGLE_SHEETS_PRIVATE_KEY" ] && CMD="$CMD --update-env-vars GOOGLE_SHEETS_PRIVATE_KEY=$GOOGLE_SHEETS_PRIVATE_KEY"
        [ -n "$GOOGLE_SHEETS_PROFILES_SPREADSHEET_ID" ] && CMD="$CMD --update-env-vars GOOGLE_SHEETS_PROFILES_SPREADSHEET_ID=$GOOGLE_SHEETS_PROFILES_SPREADSHEET_ID"
        [ -n "$GOOGLE_SHEETS_PROFILES_WORKSHEET_NAME" ] && CMD="$CMD --update-env-vars GOOGLE_SHEETS_PROFILES_WORKSHEET_NAME=$GOOGLE_SHEETS_PROFILES_WORKSHEET_NAME"
        [ -n "$PROXY_USERNAME" ] && CMD="$CMD --update-env-vars PROXY_USERNAME=$PROXY_USERNAME"
        [ -n "$PROXY_PASSWORD" ] && CMD="$CMD --update-env-vars PROXY_PASSWORD=$PROXY_PASSWORD"
        [ -n "$USE_PROXY_ROTATION" ] && CMD="$CMD --update-env-vars USE_PROXY_ROTATION=$USE_PROXY_ROTATION"
        
        echo ""
        echo "Updating Cloud Run service..."
        eval $CMD
        
        echo ""
        echo -e "${GREEN}✅ Environment variables updated successfully!${NC}"
        ;;
        
    3)
        echo ""
        echo "Setting up Secret Manager..."
        
        # Enable Secret Manager API
        gcloud services enable secretmanager.googleapis.com
        
        # Create secrets
        echo ""
        echo "Enter your secrets (or press Enter to skip):"
        echo ""
        
        read -sp "ZeroBounce API Key: " ZEROBOUNCE_KEY
        echo ""
        if [ -n "$ZEROBOUNCE_KEY" ]; then
            echo -n "$ZEROBOUNCE_KEY" | gcloud secrets create zerobounce-api-key --data-file=- --replication-policy=automatic || \
                echo -n "$ZEROBOUNCE_KEY" | gcloud secrets versions add zerobounce-api-key --data-file=-
            echo "✓ ZeroBounce secret created"
        fi
        
        read -sp "Google Search API Key: " GOOGLE_SEARCH_KEY
        echo ""
        if [ -n "$GOOGLE_SEARCH_KEY" ]; then
            echo -n "$GOOGLE_SEARCH_KEY" | gcloud secrets create google-search-api-key --data-file=- --replication-policy=automatic || \
                echo -n "$GOOGLE_SEARCH_KEY" | gcloud secrets versions add google-search-api-key --data-file=-
            echo "✓ Google Search secret created"
        fi
        
        # Get project number for service account
        PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
        SERVICE_ACCOUNT="$PROJECT_NUMBER-compute@developer.gserviceaccount.com"
        
        # Grant access
        echo ""
        echo "Granting Cloud Run access to secrets..."
        gcloud secrets add-iam-policy-binding zerobounce-api-key \
            --member="serviceAccount:$SERVICE_ACCOUNT" \
            --role="roles/secretmanager.secretAccessor" 2>/dev/null || true
        
        gcloud secrets add-iam-policy-binding google-search-api-key \
            --member="serviceAccount:$SERVICE_ACCOUNT" \
            --role="roles/secretmanager.secretAccessor" 2>/dev/null || true
        
        # Update Cloud Run to use secrets
        echo ""
        echo "Updating Cloud Run service to use secrets..."
        gcloud run services update $SERVICE_NAME \
            --region $REGION \
            --update-secrets "ZEROBOUNCE_API_KEY=zerobounce-api-key:latest,GOOGLE_SEARCH_API_KEY=google-search-api-key:latest"
        
        echo ""
        echo -e "${GREEN}✅ Secrets configured successfully!${NC}"
        echo ""
        echo "Note: For other non-sensitive variables, use option 1 or 2"
        ;;
        
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "✅ Setup complete!"
echo ""
echo "To verify, run:"
echo "  gcloud run services describe $SERVICE_NAME --region $REGION"

