#!/bin/bash

# Rollback script for annotation platform
# Usage: ./scripts/deployment/rollback.sh [environment] [backup_timestamp]

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENVIRONMENT=${1:-staging}
BACKUP_TIMESTAMP=${2:-}

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

# List available backups
list_backups() {
    log "Available backups:"
    BACKUP_DIR="$PROJECT_ROOT/deployment/backup"
    
    if [ -d "$BACKUP_DIR" ]; then
        ls -la "$BACKUP_DIR" | grep "^d" | awk '{print $9}' | grep -v "^\.$" | grep -v "^\.\.$" | sort -r
    else
        warn "No backup directory found"
        exit 1
    fi
}

# Select backup if not provided
select_backup() {
    if [ -z "$BACKUP_TIMESTAMP" ]; then
        log "No backup timestamp provided. Available backups:"
        list_backups
        echo
        read -p "Enter backup timestamp to restore: " BACKUP_TIMESTAMP
    fi
    
    BACKUP_PATH="$PROJECT_ROOT/deployment/backup/$BACKUP_TIMESTAMP"
    
    if [ ! -d "$BACKUP_PATH" ]; then
        error "Backup not found: $BACKUP_PATH"
        exit 1
    fi
    
    log "Selected backup: $BACKUP_TIMESTAMP"
}

# Validate environment
validate_environment() {
    case "$ENVIRONMENT" in
        development|staging|production)
            log "Rolling back $ENVIRONMENT environment"
            ;;
        *)
            error "Invalid environment: $ENVIRONMENT. Use: development, staging, or production"
            exit 1
            ;;
    esac
}

# Confirm rollback
confirm_rollback() {
    warn "This will rollback the $ENVIRONMENT environment to backup from $BACKUP_TIMESTAMP"
    read -p "Are you sure you want to proceed? (yes/no): " CONFIRMATION
    
    case "$CONFIRMATION" in
        yes|YES|y|Y)
            log "Proceeding with rollback..."
            ;;
        *)
            log "Rollback cancelled"
            exit 0
            ;;
    esac
}

# Stop current deployment
stop_current() {
    log "Stopping current deployment..."
    
    cd "$PROJECT_ROOT/deployment"
    
    export COMPOSE_PROJECT_NAME="annotation-$ENVIRONMENT"
    
    docker-compose down --remove-orphans
    
    success "Current deployment stopped"
}

# Restore from backup
restore_backup() {
    log "Restoring from backup..."
    
    BACKUP_PATH="$PROJECT_ROOT/deployment/backup/$BACKUP_TIMESTAMP"
    
    if [ -f "$BACKUP_PATH/docker-compose.backup.yml" ]; then
        cp "$BACKUP_PATH/docker-compose.backup.yml" "$PROJECT_ROOT/deployment/docker-compose.yml"
        log "Docker compose configuration restored"
    else
        error "Backup docker-compose file not found"
        exit 1
    fi
    
    # Restore environment files if they exist in backup
    if [ -f "$BACKUP_PATH/.env.backup" ]; then
        cp "$BACKUP_PATH/.env.backup" "$PROJECT_ROOT/deployment/.env"
        log "Environment configuration restored"
    fi
    
    success "Backup restored"
}

# Start restored deployment
start_deployment() {
    log "Starting restored deployment..."
    
    cd "$PROJECT_ROOT/deployment"
    
    export COMPOSE_PROJECT_NAME="annotation-$ENVIRONMENT"
    export ENVIRONMENT="$ENVIRONMENT"
    
    # Load environment-specific configuration
    if [ -f "environments/$ENVIRONMENT.env" ]; then
        set -a
        source "environments/$ENVIRONMENT.env"
        set +a
    fi
    
    docker-compose up -d
    
    success "Restored deployment started"
}

# Health check
health_check() {
    log "Performing health check..."
    
    # Wait for services to start
    sleep 15
    
    # Check if containers are running
    cd "$PROJECT_ROOT/deployment"
    if docker-compose ps | grep -q "Up"; then
        success "Health check passed - services are running"
    else
        error "Health check failed - some services are not running"
        docker-compose logs
        exit 1
    fi
}

# Create rollback record
create_rollback_record() {
    log "Creating rollback record..."
    
    ROLLBACK_LOG="$PROJECT_ROOT/deployment/backup/rollback.log"
    echo "$(date): Rolled back $ENVIRONMENT to $BACKUP_TIMESTAMP" >> "$ROLLBACK_LOG"
    
    success "Rollback record created"
}

# Main rollback workflow
main() {
    log "Starting rollback process..."
    log "Environment: $ENVIRONMENT"
    
    validate_environment
    select_backup
    confirm_rollback
    stop_current
    restore_backup
    start_deployment
    health_check
    create_rollback_record
    
    success "Rollback completed successfully!"
    log "Application has been restored to backup from $BACKUP_TIMESTAMP"
}

# Handle script interruption
trap 'error "Rollback interrupted"; exit 1' INT TERM

# Show help if requested
if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    echo "Usage: $0 [environment] [backup_timestamp]"
    echo "  environment: development, staging, or production"
    echo "  backup_timestamp: specific backup to restore (optional)"
    echo
    echo "Available backups:"
    list_backups
    exit 0
fi

# Run main function
main "$@"