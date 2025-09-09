#!/bin/bash

# Deployment Validation Script
# Comprehensive validation of deployment health, connectivity, and performance

set -euo pipefail

# Configuration
DEPLOY_URL="${1:-${DEPLOY_URL:-http://localhost:8080}}"
ENVIRONMENT="${2:-${NODE_ENV:-production}}"
TIMEOUT="${3:-300}" # 5 minutes timeout
PARALLEL="${4:-true}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check dependencies
check_dependencies() {
    log_info "Checking dependencies..."
    
    # Check Node.js and npm
    if ! command -v node &> /dev/null; then
        log_error "Node.js not found. Please install Node.js."
        exit 1
    fi
    
    if ! command -v npm &> /dev/null; then
        log_error "npm not found. Please install npm."
        exit 1
    fi
    
    # Check Jest for running tests
    if ! npx jest --version &> /dev/null; then
        log_error "Jest not found. Please install Jest."
        exit 1
    fi
    
    log_success "All dependencies are available"
}

# Pre-validation checks
pre_validation_checks() {
    log_info "Running pre-validation checks..."
    
    # Check if target URL is reachable
    if curl -f -s -o /dev/null --max-time 10 "$DEPLOY_URL"; then
        log_success "Target URL is reachable: $DEPLOY_URL"
    else
        log_error "Cannot reach target URL: $DEPLOY_URL"
        exit 1
    fi
    
    # Check if test directory exists
    if [[ ! -d "tests/deployment" ]]; then
        log_error "Deployment test directory not found"
        exit 1
    fi
    
    log_success "Pre-validation checks completed"
}

# Run health check validation
run_health_checks() {
    log_info "Running health check validation..."
    
    DEPLOY_URL="$DEPLOY_URL" NODE_ENV="$ENVIRONMENT" npx jest \
        tests/deployment/health-checks.test.js \
        --testTimeout="$((TIMEOUT * 1000))" \
        --verbose \
        --detectOpenHandles \
        --forceExit
    
    if [[ $? -eq 0 ]]; then
        log_success "Health check validation passed"
        return 0
    else
        log_error "Health check validation failed"
        return 1
    fi
}

# Run environment validation
run_environment_validation() {
    log_info "Running environment validation..."
    
    DEPLOY_URL="$DEPLOY_URL" NODE_ENV="$ENVIRONMENT" npx jest \
        tests/deployment/environment-validation.test.js \
        --testTimeout="$((TIMEOUT * 1000))" \
        --verbose \
        --detectOpenHandles \
        --forceExit
    
    if [[ $? -eq 0 ]]; then
        log_success "Environment validation passed"
        return 0
    else
        log_error "Environment validation failed"
        return 1
    fi
}

# Run service connectivity validation
run_connectivity_validation() {
    log_info "Running service connectivity validation..."
    
    DEPLOY_URL="$DEPLOY_URL" NODE_ENV="$ENVIRONMENT" npx jest \
        tests/deployment/service-connectivity.test.js \
        --testTimeout="$((TIMEOUT * 1000))" \
        --verbose \
        --detectOpenHandles \
        --forceExit
    
    if [[ $? -eq 0 ]]; then
        log_success "Service connectivity validation passed"
        return 0
    else
        log_warning "Service connectivity validation failed"
        return 1
    fi
}

# Run Digital Ocean platform validation
run_platform_validation() {
    log_info "Running Digital Ocean platform validation..."
    
    DEPLOY_URL="$DEPLOY_URL" NODE_ENV="$ENVIRONMENT" npx jest \
        tests/deployment/digital-ocean-platform.test.js \
        --testTimeout="$((TIMEOUT * 1000))" \
        --verbose \
        --detectOpenHandles \
        --forceExit
    
    if [[ $? -eq 0 ]]; then
        log_success "Platform validation passed"
        return 0
    else
        log_warning "Platform validation failed"
        return 1
    fi
}

# Run performance validation
run_performance_validation() {
    log_info "Running performance validation..."
    
    DEPLOY_URL="$DEPLOY_URL" NODE_ENV="$ENVIRONMENT" npx jest \
        tests/deployment/performance-validation.test.js \
        --testTimeout="$((TIMEOUT * 1000))" \
        --verbose \
        --detectOpenHandles \
        --forceExit
    
    if [[ $? -eq 0 ]]; then
        log_success "Performance validation passed"
        return 0
    else
        log_warning "Performance validation failed"
        return 1
    fi
}

# Run rollback and recovery validation
run_recovery_validation() {
    log_info "Running rollback and recovery validation..."
    
    DEPLOY_URL="$DEPLOY_URL" NODE_ENV="$ENVIRONMENT" npx jest \
        tests/deployment/rollback-recovery.test.js \
        --testTimeout="$((TIMEOUT * 1000))" \
        --verbose \
        --detectOpenHandles \
        --forceExit
    
    if [[ $? -eq 0 ]]; then
        log_success "Recovery validation passed"
        return 0
    else
        log_warning "Recovery validation failed"
        return 1
    fi
}

# Run comprehensive validation using the validator
run_comprehensive_validation() {
    log_info "Running comprehensive deployment validation..."
    
    DEPLOY_URL="$DEPLOY_URL" NODE_ENV="$ENVIRONMENT" node \
        tests/deployment/deployment-validator.js \
        "$DEPLOY_URL" \
        "$ENVIRONMENT"
    
    local exit_code=$?
    
    if [[ $exit_code -eq 0 ]]; then
        log_success "Comprehensive validation passed"
        return 0
    else
        log_error "Comprehensive validation failed"
        return 1
    fi
}

# Quick health check
quick_health_check() {
    log_info "Performing quick health check..."
    
    # Basic connectivity
    if ! curl -f -s -o /dev/null --max-time 5 "$DEPLOY_URL"; then
        log_error "Basic connectivity failed"
        return 1
    fi
    
    # Health endpoint
    local health_response
    health_response=$(curl -f -s --max-time 10 "$DEPLOY_URL/health" || echo "FAILED")
    
    if [[ "$health_response" == "FAILED" ]]; then
        log_error "Health endpoint not responding"
        return 1
    fi
    
    # Check if response contains status
    if echo "$health_response" | grep -q '"status":"healthy"'; then
        log_success "Quick health check passed"
        return 0
    else
        log_warning "Health endpoint responding but status not healthy"
        echo "Response: $health_response"
        return 1
    fi
}

# Generate summary report
generate_summary() {
    local total_tests=$1
    local passed_tests=$2
    local failed_tests=$3
    local warnings=$4
    
    echo
    echo "==============================================="
    echo "🚀 DEPLOYMENT VALIDATION SUMMARY"
    echo "==============================================="
    echo "Target URL: $DEPLOY_URL"
    echo "Environment: $ENVIRONMENT"
    echo "Timestamp: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
    echo
    echo "📊 Test Results:"
    echo "Total Test Suites: $total_tests"
    echo "Passed: $passed_tests"
    echo "Failed: $failed_tests"
    echo "Warnings: $warnings"
    
    local success_rate=0
    if [[ $total_tests -gt 0 ]]; then
        success_rate=$(echo "scale=1; $passed_tests * 100 / $total_tests" | bc -l 2>/dev/null || echo "0")
    fi
    echo "Success Rate: $success_rate%"
    
    echo
    if [[ $failed_tests -eq 0 ]]; then
        log_success "✅ Deployment is ready for production"
        echo "🎯 All critical validations passed"
    elif [[ $passed_tests -ge 3 ]]; then
        log_warning "⚠️  Deployment has warnings but may proceed"
        echo "🔍 Review failed tests and warnings"
    else
        log_error "❌ Deployment is NOT ready"
        echo "🚨 Critical validation failures detected"
    fi
    
    echo "==============================================="
}

# Main execution
main() {
    echo
    log_info "🚀 Starting Deployment Validation"
    log_info "Target: $DEPLOY_URL"
    log_info "Environment: $ENVIRONMENT"
    echo "=============================================="
    
    local total_tests=0
    local passed_tests=0
    local failed_tests=0
    local warnings=0
    
    # Check dependencies first
    check_dependencies
    
    # Pre-validation checks
    pre_validation_checks
    
    # Quick health check
    if quick_health_check; then
        ((passed_tests++))
    else
        log_error "Quick health check failed - stopping validation"
        exit 1
    fi
    ((total_tests++))
    
    if [[ "$PARALLEL" == "true" ]]; then
        # Use comprehensive validator for parallel execution
        log_info "Using parallel validation mode"
        
        if run_comprehensive_validation; then
            passed_tests=6
            total_tests=6
        else
            failed_tests=6
            total_tests=6
        fi
    else
        # Run tests sequentially
        log_info "Using sequential validation mode"
        
        # Critical tests first
        ((total_tests++))
        if run_health_checks; then
            ((passed_tests++))
        else
            ((failed_tests++))
            log_error "Critical health checks failed - consider stopping"
        fi
        
        ((total_tests++))
        if run_environment_validation; then
            ((passed_tests++))
        else
            ((failed_tests++))
            log_error "Critical environment validation failed"
        fi
        
        # Non-critical tests
        ((total_tests++))
        if run_connectivity_validation; then
            ((passed_tests++))
        else
            ((warnings++))
        fi
        
        ((total_tests++))
        if run_platform_validation; then
            ((passed_tests++))
        else
            ((warnings++))
        fi
        
        ((total_tests++))
        if run_performance_validation; then
            ((passed_tests++))
        else
            ((warnings++))
        fi
        
        ((total_tests++))
        if run_recovery_validation; then
            ((passed_tests++))
        else
            ((warnings++))
        fi
    fi
    
    # Generate summary
    generate_summary $total_tests $passed_tests $failed_tests $warnings
    
    # Exit with appropriate code
    if [[ $failed_tests -eq 0 ]]; then
        exit 0
    elif [[ $passed_tests -ge 3 ]]; then
        exit 1 # Warnings but may proceed
    else
        exit 2 # Critical failures
    fi
}

# Help function
show_help() {
    echo "Deployment Validation Script"
    echo
    echo "Usage: $0 [DEPLOY_URL] [ENVIRONMENT] [TIMEOUT] [PARALLEL]"
    echo
    echo "Parameters:"
    echo "  DEPLOY_URL   Target deployment URL (default: \$DEPLOY_URL or http://localhost:8080)"
    echo "  ENVIRONMENT  Deployment environment (default: \$NODE_ENV or production)"
    echo "  TIMEOUT      Test timeout in seconds (default: 300)"
    echo "  PARALLEL     Use parallel execution (default: true)"
    echo
    echo "Examples:"
    echo "  $0                                           # Use defaults"
    echo "  $0 https://annotat.ee                       # Validate production"
    echo "  $0 http://localhost:8080 development        # Validate local dev"
    echo "  $0 https://annotat.ee production 600 false  # Full sequential validation"
    echo
    echo "Exit codes:"
    echo "  0 - All validations passed"
    echo "  1 - Some warnings but deployment may proceed"
    echo "  2 - Critical failures, deployment should not proceed"
}

# Handle help flag
if [[ "${1:-}" == "--help" ]] || [[ "${1:-}" == "-h" ]]; then
    show_help
    exit 0
fi

# Run main function
main "$@"