#!/bin/bash

# Digital Ocean Deployment Simulation Script
# This script simulates the deployment process and provides the exact commands
# needed to deploy the Academic Annotation Platform to Digital Ocean

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
}

info() {
    echo -e "${CYAN}ℹ️  $1${NC}"
}

# Display banner
display_banner() {
    echo -e "${CYAN}"
    echo "============================================================="
    echo "    🚀 Digital Ocean Deployment Simulation"
    echo "    📦 Academic Annotation Platform"
    echo "    🌐 Domain: annotat.ee"
    echo "============================================================="
    echo -e "${NC}"
}

# Check prerequisites
check_prerequisites() {
    log "Checking deployment prerequisites..."
    
    local issues=0
    
    # Check if doctl is installed
    if command -v doctl &> /dev/null; then
        success "doctl CLI is installed"
        local version=$(doctl version 2>/dev/null | head -n1 || echo "unknown")
        info "Version: $version"
    else
        error "doctl CLI is not installed"
        info "Install with: curl -sL https://github.com/digitalocean/doctl/releases/download/v1.109.0/doctl-1.109.0-linux-amd64.tar.gz | tar -xzv && sudo mv doctl /usr/local/bin/"
        ((issues++))
    fi
    
    # Check for Node.js
    if command -v node &> /dev/null; then
        local node_version=$(node --version)
        success "Node.js is installed: $node_version"
    else
        error "Node.js is not installed"
        ((issues++))
    fi
    
    # Check for Docker
    if command -v docker &> /dev/null; then
        success "Docker is installed"
    else
        warning "Docker is not installed (optional for local testing)"
    fi
    
    # Check for required files
    local required_files=(
        "app.yaml"
        "package.json"
        "Dockerfile.production"
        ".env.production.template"
        "scripts/deploy.sh"
    )
    
    for file in "${required_files[@]}"; do
        if [[ -f "$file" ]]; then
            success "Required file exists: $file"
        else
            error "Missing required file: $file"
            ((issues++))
        fi
    done
    
    if [[ $issues -eq 0 ]]; then
        success "All prerequisites satisfied!"
        return 0
    else
        error "Found $issues issues that need to be resolved"
        return 1
    fi
}

# Simulate Digital Ocean resource creation
simulate_do_resources() {
    log "Simulating Digital Ocean resource creation..."
    
    echo
    echo -e "${CYAN}=== Step 1: Create Managed Databases ===${NC}"
    echo "🔧 MongoDB Database:"
    echo "   doctl databases create annotation-mongodb \\"
    echo "     --engine mongodb \\"
    echo "     --version 6 \\"
    echo "     --region nyc1 \\"
    echo "     --size basic-xs \\"
    echo "     --num-nodes 1"
    echo
    echo "🔧 Redis Cache:"
    echo "   doctl databases create annotation-redis \\"
    echo "     --engine redis \\"
    echo "     --version 7 \\"
    echo "     --region nyc1 \\"
    echo "     --size basic-xxs \\"
    echo "     --num-nodes 1"
    
    echo
    echo -e "${CYAN}=== Step 2: Create App Platform Application ===${NC}"
    echo "🚀 Create Application:"
    echo "   doctl apps create --spec app.yaml"
    echo
    echo "📊 Monitor Deployment:"
    echo "   doctl apps list"
    echo "   doctl apps get [APP_ID]"
    
    echo
    echo -e "${CYAN}=== Step 3: Configure Domain ===${NC}"
    echo "🌐 Add Custom Domain:"
    echo "   doctl compute domain create annotat.ee"
    echo "   # Then add domain in App Platform UI"
    echo "   # Point DNS to App Platform endpoints"
    
    success "Resource creation simulation complete"
}

# Show environment configuration
show_environment_config() {
    log "Environment configuration setup..."
    
    echo
    echo -e "${CYAN}=== Required Environment Variables ===${NC}"
    echo "📝 Set these in Digital Ocean App Platform:"
    echo
    echo "🔐 Secrets (RUN_TIME scope):"
    echo "   - MONGODB_URI: [from managed database connection string]"
    echo "   - REDIS_URL: [from managed Redis connection string]"
    echo "   - JWT_SECRET: [generate 32+ char random string]"
    echo "   - SESSION_SECRET: [generate 32+ char random string]"
    echo
    echo "🔧 Environment Variables:"
    echo "   - NODE_ENV: production"
    echo "   - DOMAIN: annotat.ee"
    echo "   - SSL_ENABLED: true"
    echo "   - LOG_LEVEL: info"
    echo "   - PORT: 8080"
    echo
    echo "💡 Generate secrets with:"
    echo "   node -e \"console.log(require('crypto').randomBytes(32).toString('hex'))\""
}

# Simulate deployment steps
simulate_deployment() {
    log "Simulating deployment process..."
    
    echo
    echo -e "${CYAN}=== Deployment Commands ===${NC}"
    echo "1️⃣ Authenticate with Digital Ocean:"
    echo "   doctl auth init"
    echo
    echo "2️⃣ Create and configure resources:"
    echo "   # Run the resource creation commands from above"
    echo
    echo "3️⃣ Deploy the application:"
    echo "   git push origin main  # Triggers automatic deployment"
    echo "   # OR use the deployment script:"
    echo "   ./scripts/deploy.sh production"
    echo
    echo "4️⃣ Monitor deployment:"
    echo "   doctl apps get [APP_ID] --format Phase"
    echo "   doctl apps logs [APP_ID] --follow"
    echo
    echo "5️⃣ Verify deployment:"
    echo "   curl -I https://annotat.ee"
    echo "   curl https://annotat.ee/health"
    echo "   ./scripts/test-deployment.sh production"
}

# Show cost estimation
show_cost_estimation() {
    log "Cost estimation for Digital Ocean deployment..."
    
    echo
    echo -e "${CYAN}=== Monthly Cost Breakdown ===${NC}"
    echo "💰 App Platform Services:"
    echo "   - API Service (basic-xxs, 2 instances): ~$12/month"
    echo "   - WebSocket Service (basic-xxs): ~$6/month"
    echo "   - Worker Service (basic-xxs): ~$6/month"
    echo "   - Static Site Hosting: Free"
    echo "   Subtotal: ~$24/month"
    echo
    echo "💾 Managed Databases:"
    echo "   - MongoDB (basic-xs, 1 node): ~$15/month"
    echo "   - Redis (basic-xxs, 1 node): ~$7/month"
    echo "   Subtotal: ~$22/month"
    echo
    echo "🌐 Domain & SSL:"
    echo "   - Custom domain: Free"
    echo "   - SSL certificate: Free (auto-provisioned)"
    echo
    echo -e "${GREEN}💵 Total Estimated Cost: ~$46/month${NC}"
    echo
    echo "📊 Cost Optimization Tips:"
    echo "   - Start with smaller instance sizes"
    echo "   - Use single database nodes initially"
    echo "   - Scale up based on traffic"
}

# Show post-deployment steps
show_post_deployment() {
    log "Post-deployment verification steps..."
    
    echo
    echo -e "${CYAN}=== Verification Checklist ===${NC}"
    echo "✅ Application Health:"
    echo "   curl https://annotat.ee/health"
    echo "   curl https://annotat.ee/api/health"
    echo
    echo "✅ SSL Certificate:"
    echo "   curl -I https://annotat.ee | grep -i 'strict-transport'"
    echo "   openssl s_client -connect annotat.ee:443 -servername annotat.ee"
    echo
    echo "✅ WebSocket Connection:"
    echo "   # Test in browser console:"
    echo "   # const socket = io('wss://annotat.ee');"
    echo "   # socket.on('connect', () => console.log('Connected!'));"
    echo
    echo "✅ Database Connectivity:"
    echo "   # Check app logs for successful database connections"
    echo "   doctl apps logs [APP_ID] | grep -i 'database\\|mongodb\\|redis'"
    echo
    echo "✅ Performance Testing:"
    echo "   ./scripts/test-deployment.sh production"
    echo "   # Run load tests if needed"
    echo
    echo -e "${GREEN}🎉 Deployment Complete!${NC}"
    echo -e "${CYAN}🌐 Your app should be live at: https://annotat.ee${NC}"
}

# Show GitHub integration
show_github_integration() {
    log "GitHub integration setup..."
    
    echo
    echo -e "${CYAN}=== GitHub Integration ===${NC}"
    echo "🔗 Repository: https://github.com/abergman/annotation-platform.git"
    echo
    echo "⚙️ Automatic Deployments:"
    echo "   - Enabled on main branch pushes"
    echo "   - GitHub Actions workflow configured"
    echo "   - App Platform auto-deploys on code changes"
    echo
    echo "🔄 Deployment Workflow:"
    echo "   1. Push code to main branch"
    echo "   2. GitHub Actions runs tests"
    echo "   3. App Platform builds and deploys"
    echo "   4. Health checks verify deployment"
    echo
    echo "📊 CI/CD Pipeline includes:"
    echo "   - Code linting and type checking"
    echo "   - Unit and integration tests"
    echo "   - Security scanning"
    echo "   - Performance testing"
    echo "   - Automatic rollback on failure"
}

# Main simulation function
run_simulation() {
    display_banner
    
    echo "This simulation will guide you through the complete deployment process"
    echo "for the Academic Annotation Platform to Digital Ocean App Platform."
    echo
    
    # Check prerequisites
    if ! check_prerequisites; then
        error "Please resolve the prerequisite issues before proceeding"
        exit 1
    fi
    
    echo
    read -p "Press Enter to continue with the deployment simulation..."
    
    # Run simulation steps
    simulate_do_resources
    echo
    read -p "Press Enter to continue..."
    
    show_environment_config
    echo
    read -p "Press Enter to continue..."
    
    simulate_deployment
    echo
    read -p "Press Enter to continue..."
    
    show_github_integration
    echo
    read -p "Press Enter to continue..."
    
    show_cost_estimation
    echo
    read -p "Press Enter to continue..."
    
    show_post_deployment
    
    echo
    echo -e "${GREEN}===========================================${NC}"
    echo -e "${GREEN}🎉 Deployment Simulation Complete!${NC}"
    echo -e "${GREEN}===========================================${NC}"
    echo
    echo -e "${CYAN}Next Steps:${NC}"
    echo "1. Set up your Digital Ocean access token"
    echo "2. Run the resource creation commands"
    echo "3. Configure environment variables"
    echo "4. Deploy using the provided scripts"
    echo "5. Verify the deployment"
    echo
    echo -e "${YELLOW}Need help?${NC}"
    echo "- Review docs/digital-ocean-deployment-execution.md"
    echo "- Check scripts/deploy.sh for automated deployment"
    echo "- Run scripts/test-deployment.sh for verification"
    echo
    echo -e "${CYAN}🌐 Target URL: https://annotat.ee${NC}"
}

# Run the simulation
run_simulation "$@"