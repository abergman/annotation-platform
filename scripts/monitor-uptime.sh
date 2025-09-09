#!/bin/bash

# Uptime Monitoring Script
# Continuous monitoring of deployment health and availability

set -euo pipefail

# Configuration
DEPLOYMENT_URL="${DEPLOYMENT_URL:-https://annotat.ee}"
CHECK_INTERVAL="${CHECK_INTERVAL:-60}"  # seconds
LOG_FILE="${LOG_FILE:-./logs/uptime-monitor.log}"
METRICS_FILE="${METRICS_FILE:-./logs/uptime-metrics.json}"
ALERT_THRESHOLD="${ALERT_THRESHOLD:-3}"  # consecutive failures before alert
SLACK_WEBHOOK="${SLACK_WEBHOOK:-}"
EMAIL_ALERTS="${EMAIL_ALERTS:-}"
HEALTH_ENDPOINT="${HEALTH_ENDPOINT:-/api/health}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Global variables
CONSECUTIVE_FAILURES=0
TOTAL_CHECKS=0
TOTAL_FAILURES=0
START_TIME=$(date +%s)
LAST_SUCCESS_TIME=$(date +%s)

# Logging functions
log_message() {
    local level=$1
    local message=$2
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "[$level] $timestamp - $message" | tee -a "$LOG_FILE"
}

log_info() {
    log_message "${BLUE}INFO${NC}" "$1"
}

log_success() {
    log_message "${GREEN}SUCCESS${NC}" "$1"
}

log_warning() {
    log_message "${YELLOW}WARNING${NC}" "$1"
}

log_error() {
    log_message "${RED}ERROR${NC}" "$1"
}

# Setup logging
setup_logging() {
    mkdir -p "$(dirname "$LOG_FILE")"
    mkdir -p "$(dirname "$METRICS_FILE")"
    
    log_info "Starting uptime monitoring for: $DEPLOYMENT_URL"
    log_info "Check interval: ${CHECK_INTERVAL}s"
    log_info "Alert threshold: $ALERT_THRESHOLD consecutive failures"
}

# Health check function
perform_health_check() {
    local start_time=$(date +%s%3N)  # milliseconds
    local status_code=0
    local response_time=0
    local error_message=""
    
    # Test main endpoint
    if response=$(curl -s -w "%{http_code}:%{time_total}" --max-time 30 --fail "$DEPLOYMENT_URL" 2>/dev/null); then
        status_code=$(echo "$response" | tail -1 | cut -d: -f1)
        response_time=$(echo "$response" | tail -1 | cut -d: -f2)
    else
        status_code=0
        error_message="Connection failed"
    fi
    
    # Test health endpoint if main endpoint is up
    local health_status="unknown"
    if [[ $status_code -eq 200 ]]; then
        if health_response=$(curl -s --max-time 10 "${DEPLOYMENT_URL}${HEALTH_ENDPOINT}" 2>/dev/null); then
            if echo "$health_response" | grep -q '"status":"healthy"'; then
                health_status="healthy"
            else
                health_status="degraded"
            fi
        else
            health_status="unavailable"
        fi
    fi
    
    local end_time=$(date +%s%3N)
    local total_time=$((end_time - start_time))
    
    echo "{
        \"timestamp\": \"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\",
        \"status_code\": $status_code,
        \"response_time_ms\": $total_time,
        \"health_status\": \"$health_status\",
        \"error\": \"$error_message\"
    }"
}

# Update metrics
update_metrics() {
    local check_result=$1
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    
    local status_code=$(echo "$check_result" | jq -r '.status_code')
    local response_time=$(echo "$check_result" | jq -r '.response_time_ms')
    local health_status=$(echo "$check_result" | jq -r '.health_status')
    
    # Update failure tracking
    if [[ $status_code -eq 200 && "$health_status" == "healthy" ]]; then
        CONSECUTIVE_FAILURES=0
        LAST_SUCCESS_TIME=$(date +%s)
        log_success "Health check passed (${response_time}ms)"
    else
        CONSECUTIVE_FAILURES=$((CONSECUTIVE_FAILURES + 1))
        TOTAL_FAILURES=$((TOTAL_FAILURES + 1))
        log_error "Health check failed - Status: $status_code, Health: $health_status"
    fi
    
    # Calculate uptime percentage
    local runtime=$(($(date +%s) - START_TIME))
    local uptime_percentage=$(echo "scale=4; ($TOTAL_CHECKS - $TOTAL_FAILURES) / $TOTAL_CHECKS * 100" | bc -l)
    
    # Update metrics file
    cat > "$METRICS_FILE" << EOF
{
    "monitoring_start": "$(date -d @$START_TIME -u +"%Y-%m-%dT%H:%M:%SZ")",
    "last_update": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
    "deployment_url": "$DEPLOYMENT_URL",
    "runtime_seconds": $runtime,
    "total_checks": $TOTAL_CHECKS,
    "total_failures": $TOTAL_FAILURES,
    "consecutive_failures": $CONSECUTIVE_FAILURES,
    "uptime_percentage": $uptime_percentage,
    "last_success": "$(date -d @$LAST_SUCCESS_TIME -u +"%Y-%m-%dT%H:%M:%SZ")",
    "current_status": $([ $CONSECUTIVE_FAILURES -eq 0 ] && echo "\"healthy\"" || echo "\"unhealthy\""),
    "latest_check": $check_result
}
EOF
}

# Send alert notifications
send_alert() {
    local alert_type=$1
    local message=$2
    
    log_warning "ALERT: $alert_type - $message"
    
    # Slack notification
    if [[ -n "$SLACK_WEBHOOK" ]]; then
        local color="warning"
        if [[ "$alert_type" == "CRITICAL" ]]; then
            color="danger"
        fi
        
        curl -X POST -H 'Content-type: application/json' \
            --data "{
                \"attachments\": [{
                    \"color\": \"$color\",
                    \"title\": \"🚨 Uptime Alert: $alert_type\",
                    \"fields\": [
                        {\"title\": \"URL\", \"value\": \"$DEPLOYMENT_URL\", \"short\": true},
                        {\"title\": \"Consecutive Failures\", \"value\": \"$CONSECUTIVE_FAILURES\", \"short\": true},
                        {\"title\": \"Message\", \"value\": \"$message\", \"short\": false},
                        {\"title\": \"Timestamp\", \"value\": \"$(date)\", \"short\": true}
                    ]
                }]
            }" \
            "$SLACK_WEBHOOK" > /dev/null 2>&1
    fi
    
    # Email notification
    if [[ -n "$EMAIL_ALERTS" ]]; then
        echo "UPTIME ALERT: $alert_type

URL: $DEPLOYMENT_URL
Consecutive Failures: $CONSECUTIVE_FAILURES
Message: $message
Timestamp: $(date)

This is an automated alert from the uptime monitoring system." | \
            mail -s "🚨 Uptime Alert: $alert_type - $DEPLOYMENT_URL" "$EMAIL_ALERTS"
    fi
}

# Check if alerting is needed
check_alerting() {
    # Alert on consecutive failures
    if [[ $CONSECUTIVE_FAILURES -eq $ALERT_THRESHOLD ]]; then
        send_alert "WARNING" "Service has failed $CONSECUTIVE_FAILURES consecutive health checks"
    elif [[ $CONSECUTIVE_FAILURES -eq $((ALERT_THRESHOLD * 2)) ]]; then
        send_alert "CRITICAL" "Service has been down for $CONSECUTIVE_FAILURES consecutive checks"
    elif [[ $CONSECUTIVE_FAILURES -gt 0 && $((CONSECUTIVE_FAILURES % 10)) -eq 0 ]]; then
        send_alert "CRITICAL" "Service has been down for $CONSECUTIVE_FAILURES consecutive checks"
    fi
    
    # Recovery notification
    if [[ $CONSECUTIVE_FAILURES -eq 0 ]] && [[ $TOTAL_FAILURES -gt 0 ]]; then
        local last_metrics=$(cat "$METRICS_FILE" 2>/dev/null || echo '{"consecutive_failures": 1}')
        local last_consecutive=$(echo "$last_metrics" | jq -r '.consecutive_failures // 1')
        
        if [[ $last_consecutive -ge $ALERT_THRESHOLD ]]; then
            send_alert "RECOVERY" "Service has recovered and is now healthy"
        fi
    fi
}

# Generate status report
generate_status_report() {
    local uptime_percentage=$(echo "scale=2; ($TOTAL_CHECKS - $TOTAL_FAILURES) / $TOTAL_CHECKS * 100" | bc -l)
    local runtime=$(($(date +%s) - START_TIME))
    local runtime_hours=$(echo "scale=2; $runtime / 3600" | bc -l)
    
    echo -e "\n${BLUE}=== UPTIME STATUS REPORT ===${NC}"
    echo -e "URL: $DEPLOYMENT_URL"
    echo -e "Runtime: ${runtime_hours}h"
    echo -e "Total Checks: $TOTAL_CHECKS"
    echo -e "Total Failures: $TOTAL_FAILURES"
    echo -e "Uptime: ${uptime_percentage}%"
    echo -e "Current Status: $([ $CONSECUTIVE_FAILURES -eq 0 ] && echo -e "${GREEN}HEALTHY${NC}" || echo -e "${RED}UNHEALTHY${NC}")"
    echo -e "Consecutive Failures: $CONSECUTIVE_FAILURES"
    echo -e "Last Success: $(date -d @$LAST_SUCCESS_TIME)"
    echo -e "========================\n"
}

# Cleanup function
cleanup() {
    log_info "Stopping uptime monitoring..."
    generate_status_report
    log_info "Monitoring session completed"
}

# Signal handlers
handle_signal() {
    echo -e "\n${YELLOW}Received signal, shutting down gracefully...${NC}"
    cleanup
    exit 0
}

trap handle_signal SIGINT SIGTERM

# Main monitoring loop
main() {
    setup_logging
    
    echo -e "${GREEN}Starting uptime monitoring...${NC}"
    echo -e "Press Ctrl+C to stop monitoring\n"
    
    while true; do
        local check_result
        check_result=$(perform_health_check)
        
        update_metrics "$check_result"
        check_alerting
        
        # Display periodic status
        if [[ $((TOTAL_CHECKS % 10)) -eq 0 ]]; then
            generate_status_report
        fi
        
        sleep "$CHECK_INTERVAL"
    done
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -u|--url)
            DEPLOYMENT_URL="$2"
            shift 2
            ;;
        -i|--interval)
            CHECK_INTERVAL="$2"
            shift 2
            ;;
        -l|--log-file)
            LOG_FILE="$2"
            shift 2
            ;;
        -m|--metrics-file)
            METRICS_FILE="$2"
            shift 2
            ;;
        -t|--threshold)
            ALERT_THRESHOLD="$2"
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
        --health-endpoint)
            HEALTH_ENDPOINT="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  -u, --url URL               Deployment URL to monitor (default: https://annotat.ee)"
            echo "  -i, --interval SECONDS      Check interval in seconds (default: 60)"
            echo "  -l, --log-file FILE         Log file path (default: ./logs/uptime-monitor.log)"
            echo "  -m, --metrics-file FILE     Metrics file path (default: ./logs/uptime-metrics.json)"
            echo "  -t, --threshold NUMBER      Alert threshold for consecutive failures (default: 3)"
            echo "  --slack-webhook URL         Slack webhook for notifications"
            echo "  --email-alerts EMAIL        Email address for alerts"
            echo "  --health-endpoint PATH      Health check endpoint path (default: /api/health)"
            echo "  -h, --help                 Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Check dependencies
if ! command -v curl &> /dev/null; then
    echo "Error: curl is required but not installed"
    exit 1
fi

if ! command -v jq &> /dev/null; then
    echo "Error: jq is required but not installed"
    exit 1
fi

if ! command -v bc &> /dev/null; then
    echo "Error: bc is required but not installed"
    exit 1
fi

# Run main function
main "$@"