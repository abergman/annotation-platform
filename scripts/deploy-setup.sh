#!/bin/bash
# Deployment Setup Script
# Prepares environment for Digital Ocean App Platform deployment

set -e

# Configuration
ENVIRONMENT=${1:-staging}
echo "🚀 Setting up deployment for: $ENVIRONMENT"

# Validate required files
echo "📋 Validating deployment files..."
REQUIRED_FILES=(
    "Dockerfile.production"
    "app-simple.yaml"
    "package.json"
    "src/index.js"
    "frontend/package.json"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [[ ! -f "$file" ]]; then
        echo "❌ Missing required file: $file"
        exit 1
    fi
done
echo "✅ All required files present"

# Validate package.json scripts
echo "📦 Validating package.json scripts..."
if ! jq -e '.scripts.start' package.json > /dev/null; then
    echo "❌ Missing 'start' script in package.json"
    exit 1
fi

if ! jq -e '.scripts["build:production"]' frontend/package.json > /dev/null; then
    echo "❌ Missing 'build:production' script in frontend/package.json"
    exit 1
fi
echo "✅ Package.json scripts validated"

# Check Docker build
echo "🐳 Testing Docker build..."
if docker build -f Dockerfile.production -t annotation-test . --no-cache; then
    echo "✅ Docker build successful"
    docker rmi annotation-test || true
else
    echo "❌ Docker build failed"
    exit 1
fi

# Validate environment variables
echo "🔧 Checking environment configuration..."
ENV_VARS=("MONGODB_URI" "JWT_SECRET" "SESSION_SECRET")
MISSING_VARS=()

for var in "${ENV_VARS[@]}"; do
    if [[ -z "${!var}" ]]; then
        MISSING_VARS+=("$var")
    fi
done

if [[ ${#MISSING_VARS[@]} -gt 0 ]]; then
    echo "⚠️  Missing environment variables (need to be set in DO secrets):"
    printf "   - %s\n" "${MISSING_VARS[@]}"
else
    echo "✅ Environment variables configured"
fi

# Frontend build test
echo "🎨 Testing frontend build..."
cd frontend
if npm run build:production; then
    echo "✅ Frontend build successful"
    cd ..
else
    echo "❌ Frontend build failed"
    cd ..
    exit 1
fi

# Generate deployment summary
echo ""
echo "📊 DEPLOYMENT SUMMARY"
echo "====================="
echo "Environment: $ENVIRONMENT"
echo "API Port: 8080"
echo "Health Check: /api/health"
echo "Frontend: Static build with Vite"
echo "Docker: Dockerfile.production"
echo "Config: app-simple.yaml"
echo ""
echo "✅ Deployment setup complete!"
echo ""
echo "Next steps:"
echo "1. Commit changes to main branch"
echo "2. Push to trigger GitHub Actions"
echo "3. Monitor deployment in Digital Ocean dashboard"
echo "4. Test endpoints: https://annotat.ee/api/health"