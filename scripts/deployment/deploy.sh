#!/bin/bash

# Deployment script for annotation platform
# Usage: ./scripts/deployment/deploy.sh [environment] [version]

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENVIRONMENT=${1:-staging}
VERSION=${2:-latest}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Validate environment
validate_environment() {
    case "$ENVIRONMENT" in
        development|staging|production)
            log "Deploying to $ENVIRONMENT environment"
            ;;
        *)
            error "Invalid environment: $ENVIRONMENT. Use: development, staging, or production"
            exit 1
            ;;
    esac
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check if Docker is installed and running
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        error "Docker daemon is not running"
        exit 1
    fi
    
    # Check if docker-compose is available
    if ! command -v docker-compose &> /dev/null; then
        error "docker-compose is not installed"
        exit 1
    fi
    
    success "Prerequisites check passed"
}

# Backup current deployment
backup_current() {
    log "Creating backup of current deployment..."
    
    BACKUP_DIR="$PROJECT_ROOT/deployment/backup/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    
    # Export current docker-compose state
    if docker-compose -f "$PROJECT_ROOT/deployment/docker-compose.yml" ps -q &> /dev/null; then
        docker-compose -f "$PROJECT_ROOT/deployment/docker-compose.yml" config > "$BACKUP_DIR/docker-compose.backup.yml"
        success "Backup created at $BACKUP_DIR"
    else
        warn "No existing deployment found to backup"
    fi
}

# Build images
build_images() {
    log "Building Docker images..."
    
    cd "$PROJECT_ROOT"
    
    # Build production image
    docker build -f Dockerfile.production -t "annotation-app:$VERSION" .
    
    # Build websocket image if exists
    if [ -f "Dockerfile.websocket" ]; then
        docker build -f Dockerfile.websocket -t "annotation-websocket:$VERSION" .
    fi
    
    success "Images built successfully"
}

# Deploy application
deploy_application() {
    log "Deploying application..."
    
    cd "$PROJECT_ROOT/deployment"
    
    # Set environment variables
    export COMPOSE_PROJECT_NAME="annotation-$ENVIRONMENT"
    export APP_VERSION="$VERSION"
    export ENVIRONMENT="$ENVIRONMENT"
    
    # Load environment-specific configuration
    if [ -f "environments/$ENVIRONMENT.env" ]; then
        set -a
        source "environments/$ENVIRONMENT.env"
        set +a
        log "Loaded $ENVIRONMENT environment configuration"
    fi
    
    # Stop existing containers
    docker-compose down --remove-orphans
    
    # Pull latest images (if using registry)
    # docker-compose pull
    
    # Start new deployment
    docker-compose up -d
    
    success "Application deployed successfully"
}

# Health check
health_check() {
    log "Performing health check..."
    
    # Wait for services to start
    sleep 10
    
    # Check if containers are running
    if docker-compose -f "$PROJECT_ROOT/deployment/docker-compose.yml" ps | grep -q "Up"; then
        success "Health check passed - services are running"
    else
        error "Health check failed - some services are not running"
        docker-compose -f "$PROJECT_ROOT/deployment/docker-compose.yml" logs
        exit 1
    fi
}

# Cleanup old images
cleanup() {
    log "Cleaning up old images..."
    
    # Remove dangling images
    docker image prune -f
    
    # Remove old versions (keep last 3)
    docker images "annotation-app" --format "table {{.Repository}}:{{.Tag}}" | tail -n +4 | xargs -r docker rmi
    
    success "Cleanup completed"
}

# Post-deployment tasks
post_deployment() {
    log "Running post-deployment tasks..."
    
    # Run database migrations if needed
    if [ "$ENVIRONMENT" = "production" ]; then
        log "Running production post-deployment tasks..."
        # Add production-specific tasks here
    fi
    
    success "Post-deployment tasks completed"
}

# Main deployment workflow
main() {
    log "Starting deployment process..."
    log "Environment: $ENVIRONMENT"
    log "Version: $VERSION"
    
    validate_environment
    check_prerequisites
    backup_current
    build_images
    deploy_application
    health_check
    cleanup
    post_deployment
    
    success "Deployment completed successfully!"
    log "Application is available at the configured endpoints"
}

# Handle script interruption
trap 'error "Deployment interrupted"; exit 1' INT TERM

# Run main function
main "$@"