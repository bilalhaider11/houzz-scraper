# 🚀 Deploy to Google Cloud Run - Simple Guide

## Prerequisites (5 minutes)

### 1. Install Google Cloud CLI

```bash
# Install gcloud CLI
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
```

Or on Ubuntu/Debian:
```bash
sudo apt-get install google-cloud-cli
```

### 2. Prepare Your API Keys

You need these API keys ready:
- **ZeroBounce API Key** - Get from https://www.zerobounce.net/
- **Proxy Credentials** (optional but recommended)

---

## Deployment Steps (10 minutes)

### Step 1: Login to Google Cloud

```bash
# Login to your Google account
gcloud auth login

# Set or create your project
gcloud config set project YOUR_PROJECT_ID

# If you don't have a project, create one:
gcloud projects create houzz-scraper-prod --name="Houzz Scraper"
gcloud config set project houzz-scraper-prod

# Enable billing at: https://console.cloud.google.com/billing
```

### Step 2: Configure Your API Keys

```bash
# Create .env file from template
cp env.example .env

# Edit the file and add your REAL API keys
nano .env
```

**Important**: Replace ALL placeholder values:
- Replace `your_zerobounce_api_key_here` with your actual ZeroBounce key
- Replace `your-service-account@your-project.iam.gserviceaccount.com` with your service account email
- Replace `-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY_HERE\n-----END PRIVATE KEY-----\n` with your actual private key
- And so on for all other values

**Verify no placeholders remain:**
```bash
grep -E "your_|_here" .env
# This should return nothing if all placeholders are replaced
```

### Step 3: Deploy to Cloud Run

```bash
# Run the deployment script
./cloud-deploy.sh
```

When prompted, **choose option 1** (Fresh deployment)

The script will:
- Enable required Google Cloud APIs (2 minutes)
- Build your Docker container (5-8 minutes)
- Deploy to Cloud Run (1-2 minutes)
- Display your service URL

**Total time: 5-10 minutes**

### Step 4: Upload Environment Variables

```bash
# Upload your API keys to Cloud Run
./setup-env-vars.sh
```

When prompted, **choose option 1** (Load from .env file)

This will upload all your API keys from the `.env` file to Cloud Run.

---

## Test Your Deployment (2 minutes)

### Get Your Service URL

```bash
# Option 1: Use the deployment script
./cloud-deploy.sh
# Choose option 5

# Option 2: Manual command
gcloud run services describe houzz-scraper \
  --region us-central1 \
  --format='value(status.url)'
```

### Test the Service

```bash
# Set your service URL (replace with your actual URL)
SERVICE_URL="https://houzz-scraper-xxxxx-uc.a.run.app"

# Test health endpoint
curl $SERVICE_URL/health

# Expected response:
# {"status":"healthy","timestamp":"..."}
```

### Test Scraping

```bash
# Run a test scrape
curl -X POST $SERVICE_URL/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "houzz",
    "location": "california",
    "professional_type": "interior-designer",
    "max_pages": 1,
    "row_number": 5
  }'

# This should return JSON with scraping results
```

### View API Documentation

Open in your browser:
```
https://YOUR-SERVICE-URL/docs
```

---

## Set Up Automated Scraping (Optional, 5 minutes)

### Create Hourly Scheduler

```bash
# Enable Cloud Scheduler
gcloud services enable cloudscheduler.googleapis.com

# Get your service URL
SERVICE_URL=$(gcloud run services describe houzz-scraper \
  --region us-central1 --format='value(status.url)')

# Create hourly job for Houzz
gcloud scheduler jobs create http houzz-hourly \
  --location us-central1 \
  --schedule "0 * * * *" \
  --uri "$SERVICE_URL/scrape" \
  --http-method POST \
  --message-body '{
    "platform": "houzz",
    "location": "usa",
    "professional_type": "interior-designer",
    "max_pages": 2,
    "row_number": 5
  }' \
  --headers "Content-Type=application/json"

# Test the scheduler
gcloud scheduler jobs run houzz-hourly --location us-central1
```

### Schedule Options

- `0 * * * *` - Every hour at minute 0
- `*/30 * * * *` - Every 30 minutes
- `0 9 * * *` - Daily at 9:00 AM
- `0 9 * * 1` - Every Monday at 9:00 AM

---

## Common Operations

### Redeploy After Code Changes

```bash
./cloud-deploy.sh
# Choose option 2 (Quick redeploy)
```

### View Live Logs

```bash
./cloud-deploy.sh
# Choose option 4

# Or manually:
gcloud logs tail --service=houzz-scraper --region=us-central1 --follow
```

### Update Environment Variables

```bash
# Edit your .env file
nano .env

# Upload changes
./setup-env-vars.sh
# Choose option 1
```

### Check Service Status

```bash
gcloud run services describe houzz-scraper --region us-central1
```

### Delete Service

```bash
./cloud-deploy.sh
# Choose option 6

# Or manually:
gcloud run services delete houzz-scraper --region us-central1
```

---

## Cost Optimization

### Current Configuration
- **Memory**: 8 GB
- **CPU**: 2 cores
- **Min Instances**: 1 (always running)
- **Cost**: ~$30-50/month

### Reduce Costs (Scale to Zero)

```bash
# Scale to zero when not in use
gcloud run services update houzz-scraper \
  --region us-central1 \
  --min-instances 0 \
  --max-instances 10

# New cost: ~$5-15/month
# Trade-off: 10-30 second cold start delay
```

### Budget Mode

```bash
# Reduce resources
gcloud run services update houzz-scraper \
  --region us-central1 \
  --memory 4Gi \
  --cpu 1 \
  --min-instances 0

# New cost: ~$2-8/month
# Trade-off: Slower scraping
```

---

## Troubleshooting

### Build Fails

```bash
# Check build logs
gcloud builds list --limit=5

# View specific build
gcloud builds log BUILD_ID
```

### Service Crashes

```bash
# View error logs
gcloud logs read --service=houzz-scraper \
  --region=us-central1 \
  --filter="severity>=ERROR" \
  --limit=50
```

### Out of Memory

```bash
# Increase memory
gcloud run services update houzz-scraper \
  --region us-central1 \
  --memory 16Gi
```

### Timeout Errors

```bash
# Increase timeout (max 3600 seconds)
gcloud run services update houzz-scraper \
  --region us-central1 \
  --timeout 3600
```

### Environment Variables Not Working

```bash
# Check current environment variables
gcloud run services describe houzz-scraper \
  --region us-central1 \
  --format="value(spec.template.spec.containers[0].env)"

# Re-upload from .env file
./setup-env-vars.sh
```

---

## Quick Reference

### Essential Commands

```bash
# Deploy
./cloud-deploy.sh → option 1 or 2

# Update env vars
./setup-env-vars.sh → option 1

# View logs
./cloud-deploy.sh → option 4

# Get URL
./cloud-deploy.sh → option 5

# Test health
curl $(gcloud run services describe houzz-scraper --region us-central1 --format='value(status.url)')/health
```

### Important URLs

- **Cloud Console**: https://console.cloud.google.com/run
- **Billing**: https://console.cloud.google.com/billing
- **Service Logs**: https://console.cloud.google.com/logs
- **Cloud Scheduler**: https://console.cloud.google.com/cloudscheduler

---

## Summary

**To deploy in 3 commands:**

```bash
gcloud auth login                 # 1. Login
./cloud-deploy.sh                 # 2. Deploy (option 1)
./setup-env-vars.sh               # 3. Configure (option 1)
```

**That's it!** Your scraper is now live at `https://YOUR-URL`

**Need help?** Run `./cloud-deploy.sh` for the interactive menu.

