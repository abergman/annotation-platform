#!/bin/bash

# Digital Ocean Deployment Script for Annotation Platform
# Usage: ./scripts/deploy.sh [staging|production] [options]

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENVIRONMENT="${1:-staging}"
FORCE_DEPLOY="${2:-false}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

success() {
    echo -e "${GREEN}[SUCCESS] $1${NC}"
}

warning() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
    exit 1
}

# Load environment configuration
load_config() {
    local config_file="$PROJECT_ROOT/.env.$ENVIRONMENT"
    
    if [[ ! -f "$config_file" ]]; then
        error "Configuration file not found: $config_file"
    fi
    
    log "Loading configuration for $ENVIRONMENT environment"
    source "$config_file"
    
    # Validate required variables
    required_vars=(
        "DIGITALOCEAN_ACCESS_TOKEN"
        "APP_ID"
        "REGISTRY_NAME"
        "DOMAIN"
    )
    
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var:-}" ]]; then
            error "Required environment variable $var is not set"
        fi
    done
}

# Pre-deployment checks
pre_deployment_checks() {
    log "Running pre-deployment checks..."
    
    # Check if doctl is installed
    if ! command -v doctl &> /dev/null; then
        error "doctl CLI is not installed. Please install it from https://github.com/digitalocean/doctl"
    fi
    
    # Verify doctl authentication
    if ! doctl account get &> /dev/null; then
        error "doctl is not authenticated. Run: doctl auth init"
    fi
    
    # Check if app exists
    if ! doctl apps get "$APP_ID" &> /dev/null; then
        error "App with ID $APP_ID not found in Digital Ocean"
    fi
    
    # Verify Node.js version
    local node_version
    node_version=$(node --version | cut -d'v' -f2)
    if [[ "$(printf '%s\n' "18.0.0" "$node_version" | sort -V | head -n1)" != "18.0.0" ]]; then
        error "Node.js version 18.0.0 or higher is required. Current: $node_version"
    fi
    
    success "Pre-deployment checks passed"
}

# Build and test application
build_and_test() {
    log "Building and testing application..."
    
    cd "$PROJECT_ROOT"
    
    # Install dependencies
    log "Installing dependencies..."
    npm ci --production=false
    
    # Run linting
    log "Running linting..."
    npm run lint
    
    # Run type checking
    log "Running type checking..."
    npm run typecheck
    
    # Run tests (skip for production if forced)
    if [[ "$ENVIRONMENT" != "production" ]] || [[ "$FORCE_DEPLOY" != "true" ]]; then
        log "Running tests..."
        npm run test
        success "All tests passed"
    else
        warning "Skipping tests due to force deploy flag"
    fi
    
    success "Build and test completed successfully"
}

# Build Docker image
build_docker_image() {
    log "Building Docker image..."
    
    cd "$PROJECT_ROOT"
    
    # Login to Digital Ocean Container Registry
    doctl registry login
    
    # Build and push image
    local image_tag="registry.digitalocean.com/$REGISTRY_NAME/annotation-platform:$ENVIRONMENT-$(date +%Y%m%d-%H%M%S)"
    local latest_tag="registry.digitalocean.com/$REGISTRY_NAME/annotation-platform:$ENVIRONMENT-latest"
    
    log "Building image: $image_tag"
    
    docker build \
        --file Dockerfile.production \
        --tag "$image_tag" \
        --tag "$latest_tag" \
        --build-arg NODE_ENV=production \
        --build-arg BUILD_DATE="$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
        --build-arg VCS_REF="$(git rev-parse HEAD)" \
        .
    
    log "Pushing image to registry..."
    docker push "$image_tag"
    docker push "$latest_tag"
    
    success "Docker image built and pushed: $image_tag"
    echo "$image_tag" > ".last-image-$ENVIRONMENT"
}

# Database backup (production only)
backup_database() {
    if [[ "$ENVIRONMENT" == "production" ]]; then
        log "Creating database backup..."
        
        local backup_name="annotation-backup-$(date +%Y%m%d-%H%M%S)"
        
        # Create database backup using doctl
        if doctl databases backups list "$DB_CLUSTER_ID" &> /dev/null; then
            doctl databases backups create "$DB_CLUSTER_ID" --name "$backup_name"
            success "Database backup created: $backup_name"
        else
            warning "Database backup skipped - cluster not found or not accessible"
        fi
    fi
}

# Deploy to Digital Ocean App Platform
deploy_app() {
    log "Deploying to Digital Ocean App Platform..."
    
    local app_spec_file="$PROJECT_ROOT/.do/app.$ENVIRONMENT.yaml"
    
    if [[ ! -f "$app_spec_file" ]]; then
        error "App spec file not found: $app_spec_file"
    fi
    
    # Update the app
    log "Updating app configuration..."
    doctl apps update "$APP_ID" --spec "$app_spec_file"
    
    # Wait for deployment to complete
    log "Waiting for deployment to complete..."
    local timeout=900 # 15 minutes
    local start_time=$(date +%s)
    
    while true; do
        local current_time=$(date +%s)
        local elapsed=$((current_time - start_time))
        
        if [[ $elapsed -gt $timeout ]]; then
            error "Deployment timed out after $timeout seconds"
        fi
        
        local status
        status=$(doctl apps get "$APP_ID" --format "ActiveDeployment.Phase" --no-header)
        
        case "$status" in
            "ACTIVE")
                success "Deployment completed successfully"
                break
                ;;
            "ERROR"|"SUPERSEDED")
                error "Deployment failed with status: $status"
                ;;
            *)
                log "Deployment in progress... Status: $status (${elapsed}s elapsed)"
                sleep 15
                ;;
        esac
    done
}

# Health checks
run_health_checks() {
    log "Running health checks..."
    
    local base_url
    if [[ "$ENVIRONMENT" == "production" ]]; then
        base_url="https://$DOMAIN"
    else
        base_url="https://$ENVIRONMENT.$DOMAIN"
    fi
    
    # Run health check script
    node "$SCRIPT_DIR/health-check.js" --url "$base_url" --timeout 60
    
    # Test WebSocket connection
    node "$SCRIPT_DIR/health-check.js" --url "wss://$DOMAIN/socket.io" --type websocket
    
    success "Health checks passed"
}

# Post-deployment tasks
post_deployment() {
    log "Running post-deployment tasks..."
    
    # Update DNS records if needed
    if [[ -n "${DOMAIN_RECORD_ID:-}" ]]; then
        log "Updating DNS records..."
        # Update DNS record to point to the new deployment
        # This would typically update a CNAME record
    fi
    
    # Warm up the application
    log "Warming up application..."
    local warmup_urls=(
        "/"
        "/health"
        "/api/health"
    )
    
    local base_url
    if [[ "$ENVIRONMENT" == "production" ]]; then
        base_url="https://$DOMAIN"
    else
        base_url="https://$ENVIRONMENT.$DOMAIN"
    fi
    
    for url in "${warmup_urls[@]}"; do
        curl -s "$base_url$url" > /dev/null || warning "Failed to warm up $url"
    done
    
    # Send deployment notification
    if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
        local message="🚀 Deployment to $ENVIRONMENT completed successfully!"
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"$message\"}" \
            "$SLACK_WEBHOOK_URL" || warning "Failed to send Slack notification"
    fi
    
    success "Post-deployment tasks completed"
}

# Rollback function
rollback() {
    log "Initiating rollback..."
    
    local previous_image
    if [[ -f ".last-image-$ENVIRONMENT" ]]; then
        previous_image=$(cat ".last-image-$ENVIRONMENT")
        warning "Rolling back to previous image: $previous_image"
        
        # Update app spec with previous image
        # This would require updating the app spec file and redeploying
        error "Rollback functionality requires manual intervention. Please check the deployment logs and redeploy the previous version."
    else
        error "No previous image found for rollback"
    fi
}

# Cleanup old resources
cleanup() {
    log "Cleaning up old resources..."
    
    # Remove old Docker images (keep last 5)
    local images
    images=$(doctl registry repository list-tags "$REGISTRY_NAME/annotation-platform" --format "Tag,UpdatedAt" --no-header | sort -k2 -r | tail -n +6 | cut -f1)
    
    if [[ -n "$images" ]]; then
        log "Removing old Docker images..."
        echo "$images" | xargs -I {} doctl registry repository delete-tag "$REGISTRY_NAME/annotation-platform" {} --force
    fi
    
    success "Cleanup completed"
}

# Main deployment function
main() {
    log "Starting deployment to $ENVIRONMENT environment"
    
    # Trap for cleanup on exit
    trap 'error "Deployment failed. Check the logs above for details."' ERR
    
    load_config
    pre_deployment_checks
    build_and_test
    build_docker_image
    backup_database
    deploy_app
    run_health_checks
    post_deployment
    cleanup
    
    success "🎉 Deployment to $ENVIRONMENT completed successfully!"
    
    if [[ "$ENVIRONMENT" == "production" ]]; then
        success "🌐 Application is now live at https://$DOMAIN"
    else
        success "🔧 Application is now live at https://$ENVIRONMENT.$DOMAIN"
    fi
}

# Show usage information
show_usage() {
    echo "Usage: $0 [staging|production] [force]"
    echo ""
    echo "Arguments:"
    echo "  environment    Target environment (staging or production)"
    echo "  force          Skip tests (use with caution)"
    echo ""
    echo "Examples:"
    echo "  $0 staging"
    echo "  $0 production"
    echo "  $0 production force"
    echo ""
    echo "Required environment files:"
    echo "  .env.staging     - Staging environment configuration"
    echo "  .env.production  - Production environment configuration"
}

# Check arguments
if [[ "${1:-}" == "--help" ]] || [[ "${1:-}" == "-h" ]]; then
    show_usage
    exit 0
fi

if [[ "$ENVIRONMENT" != "staging" ]] && [[ "$ENVIRONMENT" != "production" ]]; then
    error "Invalid environment: $ENVIRONMENT. Must be 'staging' or 'production'"
fi

# Run main deployment
main "$@"