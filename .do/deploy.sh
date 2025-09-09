#!/bin/bash
# Digital Ocean App Platform Deployment Script
# Academic Annotation Platform

set -e  # Exit on any error

echo "🚀 Starting Digital Ocean App Platform deployment..."
echo "   Project: Academic Annotation Platform"
echo "   Services: Python FastAPI Backend + Node.js WebSocket + React Frontend"
echo

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if doctl is installed
if ! command -v doctl &> /dev/null; then
    echo -e "${RED}❌ doctl is not installed.${NC}"
    echo -e "${YELLOW}📥 Please install it first:${NC}"
    echo "   macOS: brew install doctl"
    echo "   Linux: https://docs.digitalocean.com/reference/doctl/how-to/install/"
    echo "   Windows: Use WSL or download binary"
    exit 1
fi

# Check if user is logged in
if ! doctl auth list &> /dev/null; then
    echo -e "${RED}❌ Please login to Digital Ocean first:${NC}"
    echo -e "${YELLOW}🔐 Run: doctl auth init${NC}"
    exit 1
fi

echo -e "${GREEN}✅ doctl is ready${NC}"

# Validate app.yaml exists
if [[ ! -f ".do/app.yaml" ]]; then
    echo -e "${RED}❌ app.yaml not found in .do/ directory${NC}"
    exit 1
fi

# Check Docker files exist
if [[ ! -f "Dockerfile.production" ]]; then
    echo -e "${RED}❌ Dockerfile.production not found${NC}"
    exit 1
fi

if [[ ! -f "Dockerfile.websocket" ]]; then
    echo -e "${RED}❌ Dockerfile.websocket not found${NC}"
    exit 1
fi

echo -e "${GREEN}✅ All required files found${NC}"

# Show current DigitalOcean account info
echo -e "${BLUE}📋 Current DigitalOcean Account:${NC}"
doctl account get

# Validate app.yaml syntax
echo -e "${BLUE}🔍 Validating app.yaml syntax...${NC}"
if command -v yq &> /dev/null; then
    yq eval '.name' .do/app.yaml > /dev/null
    echo -e "${GREEN}✅ app.yaml syntax is valid${NC}"
else
    echo -e "${YELLOW}⚠️ yq not found - skipping YAML validation${NC}"
fi

# Ask for confirmation
echo -e "${YELLOW}🤔 This will create a new app with the following services:${NC}"
echo "   • api-backend (Python FastAPI on port 8000)"
echo "   • websocket-server (Node.js on port 8001)" 
echo "   • frontend (React static site)"
echo "   • annotation-db (PostgreSQL 15)"
echo "   • annotation-redis (Redis 7)"
echo

read -p "Do you want to continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}❌ Deployment cancelled${NC}"
    exit 0
fi

# Create app from spec
echo -e "${BLUE}🚀 Creating Digital Ocean App Platform app...${NC}"
echo "This may take a few minutes..."

if doctl apps create --spec .do/app.yaml; then
    echo -e "${GREEN}🎉 App created successfully!${NC}"
    
    # Get app info
    echo -e "${BLUE}📊 Getting app information...${NC}"
    APP_ID=$(doctl apps list --format ID --no-header | head -1)
    
    if [[ -n "$APP_ID" ]]; then
        echo -e "${GREEN}✅ App ID: $APP_ID${NC}"
        echo -e "${BLUE}📱 App URL will be available once deployed${NC}"
        
        # Show deployment status
        echo -e "${BLUE}📋 Initial deployment status:${NC}"
        doctl apps get $APP_ID --format ID,Tier,Region,CreatedAt,UpdatedAt
        
        echo -e "${GREEN}🔗 View in DigitalOcean Dashboard:${NC}"
        echo "   https://cloud.digitalocean.com/apps/$APP_ID"
    fi
    
    echo
    echo -e "${GREEN}🎯 Next Steps:${NC}"
    echo "1. 🔐 Set environment variables in the DigitalOcean dashboard:"
    echo "   • SECRET_KEY (generate a long random string)"
    echo "   • JWT_SECRET (generate a long random string)"
    echo
    echo "2. 📝 Update GitHub repository settings:"
    echo "   • Replace 'YOUR_GITHUB_USERNAME' in app.yaml with your actual username"
    echo "   • Commit and push changes to trigger deployment"
    echo 
    echo "3. 🗄️ Database will be automatically created and connected"
    echo 
    echo "4. ⏰ Deployment typically takes 5-10 minutes"
    echo
    echo "5. 🏥 Monitor deployment:"
    echo "   doctl apps get $APP_ID"
    echo "   doctl apps logs $APP_ID --type build"
    echo "   doctl apps logs $APP_ID --type deploy"
    
else
    echo -e "${RED}❌ Failed to create app${NC}"
    echo -e "${YELLOW}💡 Common issues:${NC}"
    echo "   • Check GitHub repository URL in app.yaml"
    echo "   • Ensure you have sufficient DigitalOcean credits"
    echo "   • Verify app.yaml syntax"
    exit 1
fi

echo
echo -e "${GREEN}🚀 Deployment initiated! Check your DigitalOcean dashboard for progress.${NC}"