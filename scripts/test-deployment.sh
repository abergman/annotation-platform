#!/bin/bash

# Test Deployment Script
# Comprehensive deployment validation suite

set -euo pipefail

# Configuration
DEPLOYMENT_URL="${DEPLOYMENT_URL:-https://annotat.ee}"
TEST_TIMEOUT="${TEST_TIMEOUT:-300}"
VERBOSE="${VERBOSE:-false}"
REPORT_DIR="${REPORT_DIR:-./test-reports}"
SLACK_WEBHOOK="${SLACK_WEBHOOK:-}"
EMAIL_ALERTS="${EMAIL_ALERTS:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_debug() {
    if [[ "$VERBOSE" == "true" ]]; then
        echo -e "${CYAN}[DEBUG]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
    fi
}

# Create report directory
setup_reports() {
    mkdir -p "$REPORT_DIR"
    log_info "Report directory: $REPORT_DIR"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if Node.js is installed
    if ! command -v node &> /dev/null; then
        log_error "Node.js is not installed"
        exit 1
    fi
    
    # Check if npm is installed
    if ! command -v npm &> /dev/null; then
        log_error "npm is not installed"
        exit 1
    fi
    
    # Check if required packages are installed
    if [ ! -d "node_modules" ]; then
        log_info "Installing npm dependencies..."
        npm install --silent
    fi
    
    # Verify test files exist
    local test_files=(
        "tests/deployment/smoke-tests.js"
        "tests/deployment/health-check.test.js"
        "tests/deployment/ssl-validation.test.js"
        "tests/deployment/performance-baseline.test.js"
    )
    
    for file in "${test_files[@]}"; do
        if [ ! -f "$file" ]; then
            log_error "Test file not found: $file"
            exit 1
        fi
    done
    
    log_success "Prerequisites check passed"
}

# Basic connectivity test
test_basic_connectivity() {
    log_info "Testing basic connectivity to $DEPLOYMENT_URL..."
    
    if curl -s --max-time 30 --fail "$DEPLOYMENT_URL" > /dev/null 2>&1; then
        log_success "Basic connectivity test passed"
        return 0
    else
        log_error "Basic connectivity test failed"
        return 1
    fi
}

# Run smoke tests
run_smoke_tests() {
    log_info "Running smoke tests..."
    
    local output_file="$REPORT_DIR/smoke-test-results.xml"
    
    if npm test -- --grep "Post-Deployment Smoke Tests" --reporter mocha-junit-reporter --reporter-options mochaFile="$output_file" 2>&1 | tee "$REPORT_DIR/smoke-test.log"; then
        log_success "Smoke tests passed"
        return 0
    else
        log_error "Smoke tests failed"
        return 1
    fi
}

# Run health check tests
run_health_tests() {
    log_info "Running health check tests..."
    
    local output_file="$REPORT_DIR/health-test-results.xml"
    
    if npm test -- --grep "Health Check and Monitoring Tests" --reporter mocha-junit-reporter --reporter-options mochaFile="$output_file" 2>&1 | tee "$REPORT_DIR/health-test.log"; then
        log_success "Health check tests passed"
        return 0
    else
        log_error "Health check tests failed"
        return 1
    fi
}

# Run SSL validation tests
run_ssl_tests() {
    log_info "Running SSL validation tests..."
    
    local output_file="$REPORT_DIR/ssl-test-results.xml"
    
    if npm test -- --grep "SSL/TLS Certificate Validation Tests" --reporter mocha-junit-reporter --reporter-options mochaFile="$output_file" 2>&1 | tee "$REPORT_DIR/ssl-test.log"; then
        log_success "SSL validation tests passed"
        return 0
    else
        log_error "SSL validation tests failed"
        return 1
    fi
}

# Run performance tests
run_performance_tests() {
    log_info "Running performance baseline tests..."
    
    local output_file="$REPORT_DIR/performance-test-results.xml"
    
    if npm test -- --grep "Performance Baseline Tests" --reporter mocha-junit-reporter --reporter-options mochaFile="$output_file" 2>&1 | tee "$REPORT_DIR/performance-test.log"; then
        log_success "Performance tests passed"
        return 0
    else
        log_warning "Performance tests had issues (check logs)"
        return 1
    fi
}

# Generate summary report
generate_summary() {
    local start_time="$1"
    local end_time="$2"
    local test_results=("${@:3}")
    
    local summary_file="$REPORT_DIR/deployment-test-summary.html"
    local json_file="$REPORT_DIR/deployment-test-summary.json"
    
    log_info "Generating test summary..."
    
    # Calculate duration
    local duration=$((end_time - start_time))
    
    # Count results
    local total_tests=0
    local passed_tests=0
    local failed_tests=0
    
    for result in "${test_results[@]}"; do
        total_tests=$((total_tests + 1))
        if [[ "$result" == "PASS" ]]; then
            passed_tests=$((passed_tests + 1))
        else
            failed_tests=$((failed_tests + 1))
        fi
    done
    
    # Generate JSON report
    cat > "$json_file" << EOF
{
  "deployment_url": "$DEPLOYMENT_URL",
  "test_timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "duration_seconds": $duration,
  "summary": {
    "total_tests": $total_tests,
    "passed_tests": $passed_tests,
    "failed_tests": $failed_tests,
    "success_rate": $(echo "scale=2; $passed_tests / $total_tests * 100" | bc -l)
  },
  "test_results": {
    "smoke_tests": "${test_results[0]}",
    "health_tests": "${test_results[1]}",
    "ssl_tests": "${test_results[2]}",
    "performance_tests": "${test_results[3]}"
  }
}
EOF
    
    # Generate HTML report
    cat > "$summary_file" << EOF
<!DOCTYPE html>
<html>
<head>
    <title>Deployment Test Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background: #f4f4f4; padding: 20px; border-radius: 5px; }
        .summary { margin: 20px 0; }
        .test-result { margin: 10px 0; padding: 10px; border-radius: 3px; }
        .pass { background: #d4edda; color: #155724; }
        .fail { background: #f8d7da; color: #721c24; }
        .metrics { display: flex; gap: 20px; }
        .metric { text-align: center; padding: 20px; background: #e9ecef; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Deployment Test Report</h1>
        <p><strong>URL:</strong> $DEPLOYMENT_URL</p>
        <p><strong>Timestamp:</strong> $(date)</p>
        <p><strong>Duration:</strong> ${duration}s</p>
    </div>
    
    <div class="summary">
        <h2>Test Summary</h2>
        <div class="metrics">
            <div class="metric">
                <h3>$total_tests</h3>
                <p>Total Tests</p>
            </div>
            <div class="metric">
                <h3>$passed_tests</h3>
                <p>Passed</p>
            </div>
            <div class="metric">
                <h3>$failed_tests</h3>
                <p>Failed</p>
            </div>
            <div class="metric">
                <h3>$(echo "scale=1; $passed_tests / $total_tests * 100" | bc -l)%</h3>
                <p>Success Rate</p>
            </div>
        </div>
    </div>
    
    <div class="results">
        <h2>Test Results</h2>
        <div class="test-result $([ "${test_results[0]}" == "PASS" ] && echo "pass" || echo "fail")">
            <strong>Smoke Tests:</strong> ${test_results[0]}
        </div>
        <div class="test-result $([ "${test_results[1]}" == "PASS" ] && echo "pass" || echo "fail")">
            <strong>Health Tests:</strong> ${test_results[1]}
        </div>
        <div class="test-result $([ "${test_results[2]}" == "PASS" ] && echo "pass" || echo "fail")">
            <strong>SSL Tests:</strong> ${test_results[2]}
        </div>
        <div class="test-result $([ "${test_results[3]}" == "PASS" ] && echo "pass" || echo "fail")">
            <strong>Performance Tests:</strong> ${test_results[3]}
        </div>
    </div>
</body>
</html>
EOF
    
    log_success "Test summary generated: $summary_file"
}

# Send notifications
send_notifications() {
    local test_results=("$@")
    local failed_tests=0
    
    for result in "${test_results[@]}"; do
        if [[ "$result" != "PASS" ]]; then
            failed_tests=$((failed_tests + 1))
        fi
    done
    
    local status="SUCCESS"
    if [[ $failed_tests -gt 0 ]]; then
        status="FAILURE"
    fi
    
    # Slack notification
    if [[ -n "$SLACK_WEBHOOK" ]]; then
        log_info "Sending Slack notification..."
        
        local color="good"
        if [[ "$status" == "FAILURE" ]]; then
            color="danger"
        fi
        
        curl -X POST -H 'Content-type: application/json' \
            --data "{
                \"attachments\": [{
                    \"color\": \"$color\",
                    \"title\": \"Deployment Test Results - $status\",
                    \"fields\": [
                        {\"title\": \"URL\", \"value\": \"$DEPLOYMENT_URL\", \"short\": true},
                        {\"title\": \"Timestamp\", \"value\": \"$(date)\", \"short\": true},
                        {\"title\": \"Failed Tests\", \"value\": \"$failed_tests\", \"short\": true}
                    ]
                }]
            }" \
            "$SLACK_WEBHOOK"
    fi
    
    # Email notification (if configured)
    if [[ -n "$EMAIL_ALERTS" ]]; then
        log_info "Sending email notification..."
        echo "Deployment test results for $DEPLOYMENT_URL: $status" | \
            mail -s "Deployment Test Results - $status" "$EMAIL_ALERTS"
    fi
}

# Cleanup function
cleanup() {
    log_info "Cleaning up..."
    # Add any cleanup tasks here
}

# Main execution
main() {
    local start_time=$(date +%s)
    
    echo -e "${PURPLE}"
    echo "=================================="
    echo "  DEPLOYMENT VALIDATION SUITE"
    echo "=================================="
    echo -e "${NC}"
    
    log_info "Starting deployment tests for: $DEPLOYMENT_URL"
    
    # Setup
    setup_reports
    check_prerequisites
    
    # Initialize test results array
    local test_results=()
    
    # Basic connectivity test
    if ! test_basic_connectivity; then
        log_error "Basic connectivity failed. Aborting remaining tests."
        exit 1
    fi
    
    # Run test suites
    echo -e "\n${YELLOW}Running Test Suites...${NC}"
    
    # Smoke tests
    if run_smoke_tests; then
        test_results+=("PASS")
    else
        test_results+=("FAIL")
    fi
    
    # Health tests
    if run_health_tests; then
        test_results+=("PASS")
    else
        test_results+=("FAIL")
    fi
    
    # SSL tests
    if run_ssl_tests; then
        test_results+=("PASS")
    else
        test_results+=("FAIL")
    fi
    
    # Performance tests
    if run_performance_tests; then
        test_results+=("PASS")
    else
        test_results+=("FAIL")
    fi
    
    local end_time=$(date +%s)
    
    # Generate reports
    generate_summary "$start_time" "$end_time" "${test_results[@]}"
    
    # Send notifications
    send_notifications "${test_results[@]}"
    
    # Final summary
    echo -e "\n${PURPLE}=================================="
    echo "  TEST EXECUTION COMPLETE"
    echo "==================================${NC}"
    
    local failed_count=0
    for result in "${test_results[@]}"; do
        if [[ "$result" != "PASS" ]]; then
            failed_count=$((failed_count + 1))
        fi
    done
    
    if [[ $failed_count -eq 0 ]]; then
        log_success "All tests passed! Deployment is healthy."
        echo -e "${GREEN}✅ DEPLOYMENT VALIDATED SUCCESSFULLY${NC}"
        exit 0
    else
        log_error "$failed_count test suite(s) failed."
        echo -e "${RED}❌ DEPLOYMENT VALIDATION FAILED${NC}"
        exit 1
    fi
}

# Handle script interruption
trap cleanup EXIT

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -u|--url)
            DEPLOYMENT_URL="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -r|--report-dir)
            REPORT_DIR="$2"
            shift 2
            ;;
        -t|--timeout)
            TEST_TIMEOUT="$2"
            shift 2
            ;;
        --slack-webhook)
            SLACK_WEBHOOK="$2"
            shift 2
            ;;
        --email-alerts)
            EMAIL_ALERTS="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  -u, --url URL           Deployment URL to test (default: https://annotat.ee)"
            echo "  -v, --verbose           Enable verbose output"
            echo "  -r, --report-dir DIR    Report directory (default: ./test-reports)"
            echo "  -t, --timeout SECONDS  Test timeout (default: 300)"
            echo "  --slack-webhook URL     Slack webhook for notifications"
            echo "  --email-alerts EMAIL    Email address for alerts"
            echo "  -h, --help             Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Export environment variables for tests
export DEPLOYMENT_URL
export TEST_TIMEOUT

# Run main function
main "$@"