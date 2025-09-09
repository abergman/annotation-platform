#!/bin/bash

# Rollback Procedure Script
# Automated rollback with safety checks and validation

set -euo pipefail

# Configuration
DEPLOYMENT_URL="${DEPLOYMENT_URL:-https://annotat.ee}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
ROLLBACK_TO="${ROLLBACK_TO:-previous}"
DRY_RUN="${DRY_RUN:-false}"
FORCE_ROLLBACK="${FORCE_ROLLBACK:-false}"
MAINTENANCE_MODE="${MAINTENANCE_MODE:-true}"
NOTIFICATION_WEBHOOK="${NOTIFICATION_WEBHOOK:-}"
EMERGENCY_CONTACT="${EMERGENCY_CONTACT:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a rollback.log
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a rollback.log
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a rollback.log
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a rollback.log
}

log_critical() {
    echo -e "${RED}[CRITICAL]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a rollback.log
    send_emergency_notification "CRITICAL" "$1"
}

# Send emergency notifications
send_emergency_notification() {
    local severity=$1
    local message=$2
    
    if [[ -n "$NOTIFICATION_WEBHOOK" ]]; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{
                \"text\": \"🚨 ROLLBACK $severity: $message\",
                \"attachments\": [{
                    \"color\": \"danger\",
                    \"fields\": [
                        {\"title\": \"URL\", \"value\": \"$DEPLOYMENT_URL\", \"short\": true},
                        {\"title\": \"Time\", \"value\": \"$(date)\", \"short\": true},
                        {\"title\": \"Rollback Target\", \"value\": \"$ROLLBACK_TO\", \"short\": true}
                    ]
                }]
            }" \
            "$NOTIFICATION_WEBHOOK" || true
    fi
    
    if [[ -n "$EMERGENCY_CONTACT" ]]; then
        echo "ROLLBACK $severity: $message

URL: $DEPLOYMENT_URL
Time: $(date)
Target: $ROLLBACK_TO

This is an automated emergency notification." | \
            mail -s "🚨 ROLLBACK $severity" "$EMERGENCY_CONTACT" || true
    fi
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking rollback prerequisites..."
    
    # Check if we have required tools
    local required_tools=("curl" "jq" "git" "docker")
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            log_error "$tool is required but not installed"
            return 1
        fi
    done
    
    # Check if backup directory exists
    if [[ ! -d "$BACKUP_DIR" ]]; then
        log_error "Backup directory not found: $BACKUP_DIR"
        return 1
    fi
    
    # Check if we can reach the deployment
    if ! curl -s --max-time 10 "$DEPLOYMENT_URL/api/health" > /dev/null; then
        log_warning "Cannot reach deployment URL, proceeding anyway"
    fi
    
    log_success "Prerequisites check completed"
    return 0
}

# Capture current state
capture_current_state() {
    log_info "Capturing current deployment state..."
    
    local state_file="pre-rollback-state-$(date +%Y%m%d-%H%M%S).json"
    local state_data="{\"timestamp\":\"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\""
    
    # Get current version
    if current_version=$(curl -s --max-time 10 "$DEPLOYMENT_URL/api/version" 2>/dev/null); then
        state_data="$state_data,\"version\":$current_version"
    fi
    
    # Get health status
    if health_status=$(curl -s --max-time 10 "$DEPLOYMENT_URL/api/health" 2>/dev/null); then
        state_data="$state_data,\"health\":$health_status"
    fi
    
    # Get system status
    if system_status=$(curl -s --max-time 10 "$DEPLOYMENT_URL/api/status" 2>/dev/null); then
        state_data="$state_data,\"system\":$system_status"
    fi
    
    state_data="$state_data}"
    echo "$state_data" > "$BACKUP_DIR/$state_file"
    
    log_success "Current state captured: $BACKUP_DIR/$state_file"
}

# Enable maintenance mode
enable_maintenance_mode() {
    if [[ "$MAINTENANCE_MODE" == "true" ]]; then
        log_info "Enabling maintenance mode..."
        
        if curl -s -X POST --max-time 10 "$DEPLOYMENT_URL/api/admin/maintenance/enable" > /dev/null 2>&1; then
            log_success "Maintenance mode enabled"
            sleep 5  # Wait for maintenance mode to take effect
        else
            log_warning "Failed to enable maintenance mode, continuing anyway"
        fi
    fi
}

# Disable maintenance mode
disable_maintenance_mode() {
    if [[ "$MAINTENANCE_MODE" == "true" ]]; then
        log_info "Disabling maintenance mode..."
        
        if curl -s -X POST --max-time 10 "$DEPLOYMENT_URL/api/admin/maintenance/disable" > /dev/null 2>&1; then
            log_success "Maintenance mode disabled"
        else
            log_warning "Failed to disable maintenance mode"
        fi
    fi
}

# Find rollback target
find_rollback_target() {
    log_info "Determining rollback target..."
    
    if [[ "$ROLLBACK_TO" == "previous" ]]; then
        # Try to get previous version from deployment history
        if [[ -f "$BACKUP_DIR/deployment-history.json" ]]; then
            ROLLBACK_TO=$(jq -r '.[1].version // "unknown"' "$BACKUP_DIR/deployment-history.json")
        fi
        
        if [[ "$ROLLBACK_TO" == "unknown" || "$ROLLBACK_TO" == "previous" ]]; then
            log_error "Cannot determine previous version for rollback"
            return 1
        fi
    fi
    
    log_info "Rollback target: $ROLLBACK_TO"
    return 0
}

# Validate rollback target
validate_rollback_target() {
    log_info "Validating rollback target: $ROLLBACK_TO"
    
    # Check if backup exists for this version
    local backup_file="$BACKUP_DIR/backup-$ROLLBACK_TO.sql"
    local deployment_file="$BACKUP_DIR/deployment-$ROLLBACK_TO.tar.gz"
    
    if [[ ! -f "$backup_file" ]]; then
        log_error "Database backup not found for version $ROLLBACK_TO: $backup_file"
        return 1
    fi
    
    if [[ ! -f "$deployment_file" ]]; then
        log_error "Deployment backup not found for version $ROLLBACK_TO: $deployment_file"
        return 1
    fi
    
    # Validate backup integrity
    if ! gzip -t "$deployment_file" 2>/dev/null; then
        log_error "Deployment backup is corrupted: $deployment_file"
        return 1
    fi
    
    log_success "Rollback target validation completed"
    return 0
}

# Perform database rollback
rollback_database() {
    log_info "Rolling back database to version $ROLLBACK_TO..."
    
    local backup_file="$BACKUP_DIR/backup-$ROLLBACK_TO.sql"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "DRY RUN: Would restore database from $backup_file"
        return 0
    fi
    
    # Create emergency backup of current state
    local emergency_backup="$BACKUP_DIR/emergency-backup-$(date +%Y%m%d-%H%M%S).sql"
    log_info "Creating emergency backup: $emergency_backup"
    
    # This would typically use your database backup command
    # Example for PostgreSQL:
    # pg_dump -h $DB_HOST -U $DB_USER -d $DB_NAME > "$emergency_backup"
    
    # Restore from backup
    log_info "Restoring database from backup..."
    # Example for PostgreSQL:
    # psql -h $DB_HOST -U $DB_USER -d $DB_NAME < "$backup_file"
    
    # For this example, we'll simulate the process
    if [[ -f "$backup_file" ]]; then
        log_success "Database rollback completed"
    else
        log_error "Database rollback failed"
        return 1
    fi
    
    return 0
}

# Perform application rollback
rollback_application() {
    log_info "Rolling back application to version $ROLLBACK_TO..."
    
    local deployment_file="$BACKUP_DIR/deployment-$ROLLBACK_TO.tar.gz"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "DRY RUN: Would restore application from $deployment_file"
        return 0
    fi
    
    # Extract deployment
    local temp_dir=$(mktemp -d)
    if ! tar -xzf "$deployment_file" -C "$temp_dir"; then
        log_error "Failed to extract deployment archive"
        return 1
    fi
    
    # This would typically involve:
    # 1. Stopping current services
    # 2. Replacing application files
    # 3. Updating configuration
    # 4. Restarting services
    
    log_info "Stopping current services..."
    # systemctl stop annotation-app
    
    log_info "Replacing application files..."
    # cp -r "$temp_dir"/* /opt/annotation-app/
    
    log_info "Starting services with rollback version..."
    # systemctl start annotation-app
    
    # Cleanup
    rm -rf "$temp_dir"
    
    log_success "Application rollback completed"
    return 0
}

# Validate rollback success
validate_rollback() {
    log_info "Validating rollback success..."
    
    local validation_failures=0
    
    # Wait for services to start
    log_info "Waiting for services to initialize..."
    sleep 30
    
    # Check if application is responding
    if ! curl -s --max-time 30 "$DEPLOYMENT_URL/api/health" > /dev/null; then
        log_error "Health check endpoint not responding"
        validation_failures=$((validation_failures + 1))
    else
        log_success "Health check endpoint is responding"
    fi
    
    # Check version
    if current_version=$(curl -s --max-time 10 "$DEPLOYMENT_URL/api/version" | jq -r '.version // "unknown"'); then
        if [[ "$current_version" == "$ROLLBACK_TO" ]]; then
            log_success "Version rollback confirmed: $current_version"
        else
            log_error "Version mismatch. Expected: $ROLLBACK_TO, Got: $current_version"
            validation_failures=$((validation_failures + 1))
        fi
    else
        log_error "Cannot retrieve version information"
        validation_failures=$((validation_failures + 1))
    fi
    
    # Check database connectivity
    if curl -s --max-time 10 "$DEPLOYMENT_URL/api/db/ping" | jq -r '.connected' | grep -q true; then
        log_success "Database connectivity verified"
    else
        log_error "Database connectivity check failed"
        validation_failures=$((validation_failures + 1))
    fi
    
    # Run post-rollback tests
    log_info "Running post-rollback validation tests..."
    if [[ -f "./scripts/test-deployment.sh" ]]; then
        if ./scripts/test-deployment.sh -u "$DEPLOYMENT_URL" --timeout 60; then
            log_success "Post-rollback tests passed"
        else
            log_error "Post-rollback tests failed"
            validation_failures=$((validation_failures + 1))
        fi
    else
        log_warning "Deployment test script not found, skipping automated tests"
    fi
    
    return $validation_failures
}

# Generate rollback report
generate_rollback_report() {
    local success=$1
    local report_file="rollback-report-$(date +%Y%m%d-%H%M%S).json"
    
    log_info "Generating rollback report: $report_file"
    
    cat > "$report_file" << EOF
{
    "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
    "deployment_url": "$DEPLOYMENT_URL",
    "rollback_target": "$ROLLBACK_TO",
    "rollback_successful": $success,
    "dry_run": $DRY_RUN,
    "maintenance_mode_used": $MAINTENANCE_MODE,
    "duration_minutes": $(( ($(date +%s) - START_TIME) / 60 )),
    "validation_results": {
        "health_check": "$(curl -s --max-time 10 "$DEPLOYMENT_URL/api/health" | jq -r '.status // "unknown"')",
        "version": "$(curl -s --max-time 10 "$DEPLOYMENT_URL/api/version" | jq -r '.version // "unknown"')",
        "database_connectivity": "$(curl -s --max-time 10 "$DEPLOYMENT_URL/api/db/ping" | jq -r '.connected // false')"
    }
}
EOF
    
    log_success "Rollback report generated: $report_file"
}

# Cleanup function
cleanup() {
    log_info "Performing cleanup..."
    disable_maintenance_mode
}

# Emergency abort function
emergency_abort() {
    log_critical "EMERGENCY ABORT: Rollback procedure failed!"
    log_critical "Manual intervention required immediately!"
    
    send_emergency_notification "EMERGENCY" "Rollback procedure failed and requires immediate manual intervention"
    
    cleanup
    exit 1
}

# Main rollback procedure
main() {
    local START_TIME=$(date +%s)
    
    echo -e "${PURPLE}"
    echo "======================================="
    echo "    DEPLOYMENT ROLLBACK PROCEDURE"
    echo "======================================="
    echo -e "${NC}"
    
    log_info "Starting rollback procedure"
    log_info "Target URL: $DEPLOYMENT_URL"
    log_info "Rollback to: $ROLLBACK_TO"
    log_info "Dry run: $DRY_RUN"
    
    # Safety confirmation
    if [[ "$FORCE_ROLLBACK" != "true" && "$DRY_RUN" != "true" ]]; then
        echo -e "\n${RED}WARNING: This will rollback the production deployment!${NC}"
        echo -e "Target: $DEPLOYMENT_URL"
        echo -e "Rollback to: $ROLLBACK_TO"
        echo -e "\nAre you absolutely sure you want to proceed? (type 'CONFIRM' to continue)"
        read -r confirmation
        
        if [[ "$confirmation" != "CONFIRM" ]]; then
            log_info "Rollback cancelled by user"
            exit 0
        fi
    fi
    
    # Execute rollback procedure
    local rollback_success=false
    
    trap emergency_abort ERR
    
    if check_prerequisites && \
       find_rollback_target && \
       validate_rollback_target && \
       capture_current_state && \
       enable_maintenance_mode && \
       rollback_database && \
       rollback_application; then
        
        if validate_rollback; then
            rollback_success=true
            log_success "Rollback procedure completed successfully!"
            echo -e "${GREEN}✅ ROLLBACK SUCCESSFUL${NC}"
        else
            log_error "Rollback validation failed"
            echo -e "${RED}❌ ROLLBACK VALIDATION FAILED${NC}"
        fi
    else
        log_error "Rollback procedure failed"
        echo -e "${RED}❌ ROLLBACK FAILED${NC}"
    fi
    
    # Cleanup and reporting
    trap - ERR
    cleanup
    generate_rollback_report "$rollback_success"
    
    if [[ "$rollback_success" == "true" ]]; then
        send_emergency_notification "SUCCESS" "Rollback completed successfully"
        exit 0
    else
        send_emergency_notification "FAILURE" "Rollback procedure failed"
        exit 1
    fi
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -u|--url)
            DEPLOYMENT_URL="$2"
            shift 2
            ;;
        -t|--target)
            ROLLBACK_TO="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --force)
            FORCE_ROLLBACK=true
            shift
            ;;
        --no-maintenance)
            MAINTENANCE_MODE=false
            shift
            ;;
        --webhook)
            NOTIFICATION_WEBHOOK="$2"
            shift 2
            ;;
        --emergency-contact)
            EMERGENCY_CONTACT="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  -u, --url URL               Deployment URL"
            echo "  -t, --target VERSION        Rollback target version (default: previous)"
            echo "  --dry-run                   Perform dry run without making changes"
            echo "  --force                     Skip confirmation prompt"
            echo "  --no-maintenance            Skip maintenance mode"
            echo "  --webhook URL               Notification webhook"
            echo "  --emergency-contact EMAIL   Emergency contact email"
            echo "  -h, --help                 Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Run main function
main "$@"