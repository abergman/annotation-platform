#!/bin/bash

# Availability Monitoring Script
# Comprehensive availability monitoring with detailed metrics

set -euo pipefail

# Configuration
DEPLOYMENT_URL="${DEPLOYMENT_URL:-https://annotat.ee}"
CHECK_INTERVAL="${CHECK_INTERVAL:-30}"  # seconds
REPORT_INTERVAL="${REPORT_INTERVAL:-300}"  # seconds (5 minutes)
METRICS_DIR="${METRICS_DIR:-./logs/availability}"
ALERT_THRESHOLD="${ALERT_THRESHOLD:-95.0}"  # availability percentage
RESPONSE_TIME_THRESHOLD="${RESPONSE_TIME_THRESHOLD:-2000}"  # ms
SLACK_WEBHOOK="${SLACK_WEBHOOK:-}"
EMAIL_ALERTS="${EMAIL_ALERTS:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Global tracking variables
declare -A ENDPOINT_STATS
declare -A RESPONSE_TIMES
TOTAL_CHECKS=0
START_TIME=$(date +%s)

# Endpoints to monitor
ENDPOINTS=(
    "/:Homepage"
    "/api/health:Health Check"
    "/api/status:System Status"
    "/api/auth/validate:Authentication"
)

# Initialize tracking
initialize_monitoring() {
    mkdir -p "$METRICS_DIR"
    
    for endpoint_pair in "${ENDPOINTS[@]}"; do
        local endpoint=$(echo "$endpoint_pair" | cut -d: -f1)
        ENDPOINT_STATS["${endpoint}_total"]=0
        ENDPOINT_STATS["${endpoint}_success"]=0
        ENDPOINT_STATS["${endpoint}_failures"]=0
        RESPONSE_TIMES["${endpoint}_sum"]=0
        RESPONSE_TIMES["${endpoint}_count"]=0
        RESPONSE_TIMES["${endpoint}_max"]=0
        RESPONSE_TIMES["${endpoint}_min"]=999999
    done
    
    echo -e "${BLUE}Availability monitoring initialized${NC}"
    echo -e "Target: $DEPLOYMENT_URL"
    echo -e "Endpoints: ${#ENDPOINTS[@]}"
    echo -e "Check interval: ${CHECK_INTERVAL}s"
    echo -e "Report interval: ${REPORT_INTERVAL}s"
    echo ""
}

# Perform single endpoint check
check_endpoint() {
    local endpoint=$1
    local name=$2
    local start_time=$(date +%s%3N)
    local status_code=0
    local response_time=0
    local error=""
    
    # Perform the check
    if result=$(curl -s -w "%{http_code}:%{time_total}" --max-time 10 "${DEPLOYMENT_URL}${endpoint}" 2>/dev/null); then
        status_code=$(echo "$result" | tail -1 | cut -d: -f1)
        response_time_seconds=$(echo "$result" | tail -1 | cut -d: -f2)
        response_time=$(echo "$response_time_seconds * 1000" | bc -l | cut -d. -f1)
    else
        error="Connection failed"
    fi
    
    local end_time=$(date +%s%3N)
    local actual_time=$((end_time - start_time))
    
    # Use actual measured time if curl timing failed
    if [[ $response_time -eq 0 ]]; then
        response_time=$actual_time
    fi
    
    # Update statistics
    ENDPOINT_STATS["${endpoint}_total"]=$((ENDPOINT_STATS["${endpoint}_total"] + 1))
    
    if [[ $status_code -ge 200 && $status_code -lt 400 ]]; then
        ENDPOINT_STATS["${endpoint}_success"]=$((ENDPOINT_STATS["${endpoint}_success"] + 1))
        
        # Update response time stats
        RESPONSE_TIMES["${endpoint}_sum"]=$((RESPONSE_TIMES["${endpoint}_sum"] + response_time))
        RESPONSE_TIMES["${endpoint}_count"]=$((RESPONSE_TIMES["${endpoint}_count"] + 1))
        
        if [[ $response_time -gt ${RESPONSE_TIMES["${endpoint}_max"]} ]]; then
            RESPONSE_TIMES["${endpoint}_max"]=$response_time
        fi
        
        if [[ $response_time -lt ${RESPONSE_TIMES["${endpoint}_min"]} ]]; then
            RESPONSE_TIMES["${endpoint}_min"]=$response_time
        fi
        
        echo -e "${GREEN}✓${NC} $name ($status_code, ${response_time}ms)"
    else
        ENDPOINT_STATS["${endpoint}_failures"]=$((ENDPOINT_STATS["${endpoint}_failures"] + 1))
        echo -e "${RED}✗${NC} $name (${status_code:-FAIL}, ${response_time}ms) $error"
    fi
    
    # Log individual check
    echo "{\"timestamp\":\"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\",\"endpoint\":\"$endpoint\",\"name\":\"$name\",\"status_code\":$status_code,\"response_time_ms\":$response_time,\"error\":\"$error\"}" >> "$METRICS_DIR/checks.jsonl"
    
    return $([ $status_code -ge 200 ] && [ $status_code -lt 400 ] && echo 0 || echo 1)
}

# Run all endpoint checks
run_availability_checks() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${YELLOW}[$timestamp] Running availability checks...${NC}"
    
    local all_success=true
    
    for endpoint_pair in "${ENDPOINTS[@]}"; do
        local endpoint=$(echo "$endpoint_pair" | cut -d: -f1)
        local name=$(echo "$endpoint_pair" | cut -d: -f2)
        
        if ! check_endpoint "$endpoint" "$name"; then
            all_success=false
        fi
    done
    
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    echo ""
    
    return $([ "$all_success" == "true" ] && echo 0 || echo 1)
}

# Calculate availability metrics
calculate_availability() {
    local endpoint=$1
    local total=${ENDPOINT_STATS["${endpoint}_total"]}
    local success=${ENDPOINT_STATS["${endpoint}_success"]}
    
    if [[ $total -eq 0 ]]; then
        echo "0.00"
    else
        echo "scale=2; $success / $total * 100" | bc -l
    fi
}

# Calculate average response time
calculate_avg_response_time() {
    local endpoint=$1
    local sum=${RESPONSE_TIMES["${endpoint}_sum"]}
    local count=${RESPONSE_TIMES["${endpoint}_count"]}
    
    if [[ $count -eq 0 ]]; then
        echo "0"
    else
        echo "$sum / $count" | bc -l | cut -d. -f1
    fi
}

# Generate detailed report
generate_report() {
    local runtime=$(($(date +%s) - START_TIME))
    local report_file="$METRICS_DIR/availability-report-$(date +%Y%m%d-%H%M%S).json"
    
    echo -e "${PURPLE}=== AVAILABILITY REPORT ===${NC}"
    echo -e "Runtime: $(($runtime / 3600))h $(($runtime % 3600 / 60))m $(($runtime % 60))s"
    echo -e "Total Check Cycles: $TOTAL_CHECKS"
    echo ""
    
    # Calculate overall availability
    local total_all_checks=0
    local success_all_checks=0
    local availability_data="{"
    
    echo -e "${BLUE}Endpoint Details:${NC}"
    for endpoint_pair in "${ENDPOINTS[@]}"; do
        local endpoint=$(echo "$endpoint_pair" | cut -d: -f1)
        local name=$(echo "$endpoint_pair" | cut -d: -f2)
        
        local total=${ENDPOINT_STATS["${endpoint}_total"]}
        local success=${ENDPOINT_STATS["${endpoint}_success"]}
        local failures=${ENDPOINT_STATS["${endpoint}_failures"]}
        local availability=$(calculate_availability "$endpoint")
        local avg_response=$(calculate_avg_response_time "$endpoint")
        local max_response=${RESPONSE_TIMES["${endpoint}_max"]}
        local min_response=${RESPONSE_TIMES["${endpoint}_min"]}
        
        # Handle case where no successful requests
        if [[ ${RESPONSE_TIMES["${endpoint}_count"]} -eq 0 ]]; then
            min_response=0
            max_response=0
        fi
        
        total_all_checks=$((total_all_checks + total))
        success_all_checks=$((success_all_checks + success))
        
        # Color code availability
        local color=$GREEN
        if (( $(echo "$availability < $ALERT_THRESHOLD" | bc -l) )); then
            color=$RED
        elif (( $(echo "$availability < 99.0" | bc -l) )); then
            color=$YELLOW
        fi
        
        echo -e "  $name ($endpoint):"
        echo -e "    Availability: ${color}${availability}%${NC} ($success/$total)"
        echo -e "    Failures: $failures"
        echo -e "    Response Time: avg ${avg_response}ms, min ${min_response}ms, max ${max_response}ms"
        
        # Build JSON data
        availability_data="$availability_data\"$(echo "$endpoint" | sed 's/\//_/g')\":{"
        availability_data="$availability_data\"name\":\"$name\","
        availability_data="$availability_data\"endpoint\":\"$endpoint\","
        availability_data="$availability_data\"total_checks\":$total,"
        availability_data="$availability_data\"successful_checks\":$success,"
        availability_data="$availability_data\"failed_checks\":$failures,"
        availability_data="$availability_data\"availability_percentage\":$availability,"
        availability_data="$availability_data\"response_times\":{"
        availability_data="$availability_data\"average_ms\":$avg_response,"
        availability_data="$availability_data\"minimum_ms\":$min_response,"
        availability_data="$availability_data\"maximum_ms\":$max_response"
        availability_data="$availability_data}}"
        
        if [[ "$endpoint_pair" != "${ENDPOINTS[-1]}" ]]; then
            availability_data="$availability_data,"
        fi
        echo ""
    done
    
    # Overall availability
    local overall_availability="0.00"
    if [[ $total_all_checks -gt 0 ]]; then
        overall_availability=$(echo "scale=2; $success_all_checks / $total_all_checks * 100" | bc -l)
    fi
    
    local overall_color=$GREEN
    if (( $(echo "$overall_availability < $ALERT_THRESHOLD" | bc -l) )); then
        overall_color=$RED
    elif (( $(echo "$overall_availability < 99.0" | bc -l) )); then
        overall_color=$YELLOW
    fi
    
    echo -e "${BLUE}Overall Availability: ${overall_color}${overall_availability}%${NC}"
    echo -e "========================"
    
    # Generate JSON report
    availability_data="$availability_data}"
    cat > "$report_file" << EOF
{
    "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
    "deployment_url": "$DEPLOYMENT_URL",
    "monitoring_duration_seconds": $runtime,
    "total_check_cycles": $TOTAL_CHECKS,
    "overall_availability_percentage": $overall_availability,
    "alert_threshold": $ALERT_THRESHOLD,
    "response_time_threshold_ms": $RESPONSE_TIME_THRESHOLD,
    "endpoints": $availability_data
}
EOF
    
    echo -e "Report saved: $report_file"
    
    # Check if alerting is needed
    check_availability_alerts "$overall_availability"
}

# Check for availability alerts
check_availability_alerts() {
    local overall_availability=$1
    
    if (( $(echo "$overall_availability < $ALERT_THRESHOLD" | bc -l) )); then
        send_availability_alert "CRITICAL" "Overall availability ($overall_availability%) below threshold ($ALERT_THRESHOLD%)"
    fi
    
    # Check individual endpoints
    for endpoint_pair in "${ENDPOINTS[@]}"; do
        local endpoint=$(echo "$endpoint_pair" | cut -d: -f1)
        local name=$(echo "$endpoint_pair" | cut -d: -f2)
        local availability=$(calculate_availability "$endpoint")
        local avg_response=$(calculate_avg_response_time "$endpoint")
        
        if (( $(echo "$availability < $ALERT_THRESHOLD" | bc -l) )); then
            send_availability_alert "WARNING" "$name availability ($availability%) below threshold"
        fi
        
        if [[ $avg_response -gt $RESPONSE_TIME_THRESHOLD ]]; then
            send_availability_alert "WARNING" "$name response time (${avg_response}ms) above threshold (${RESPONSE_TIME_THRESHOLD}ms)"
        fi
    done
}

# Send availability alert
send_availability_alert() {
    local severity=$1
    local message=$2
    
    echo -e "${RED}🚨 AVAILABILITY ALERT [$severity]: $message${NC}"
    
    # Slack notification
    if [[ -n "$SLACK_WEBHOOK" ]]; then
        local color="warning"
        if [[ "$severity" == "CRITICAL" ]]; then
            color="danger"
        fi
        
        curl -X POST -H 'Content-type: application/json' \
            --data "{
                \"attachments\": [{
                    \"color\": \"$color\",
                    \"title\": \"🚨 Availability Alert: $severity\",
                    \"fields\": [
                        {\"title\": \"URL\", \"value\": \"$DEPLOYMENT_URL\", \"short\": true},
                        {\"title\": \"Message\", \"value\": \"$message\", \"short\": false},
                        {\"title\": \"Timestamp\", \"value\": \"$(date)\", \"short\": true}
                    ]
                }]
            }" \
            "$SLACK_WEBHOOK" > /dev/null 2>&1
    fi
    
    # Email notification
    if [[ -n "$EMAIL_ALERTS" ]]; then
        echo "AVAILABILITY ALERT: $severity

URL: $DEPLOYMENT_URL
Message: $message
Timestamp: $(date)

This is an automated alert from the availability monitoring system." | \
            mail -s "🚨 Availability Alert: $severity - $DEPLOYMENT_URL" "$EMAIL_ALERTS"
    fi
}

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}Stopping availability monitoring...${NC}"
    generate_report
    echo -e "${BLUE}Availability monitoring session completed${NC}"
}

# Signal handlers
handle_signal() {
    echo -e "\n${YELLOW}Received signal, generating final report...${NC}"
    cleanup
    exit 0
}

trap handle_signal SIGINT SIGTERM

# Main monitoring loop
main() {
    initialize_monitoring
    
    local last_report_time=$(date +%s)
    
    echo -e "${GREEN}Starting availability monitoring...${NC}"
    echo -e "Press Ctrl+C to stop and generate final report\n"
    
    while true; do
        run_availability_checks
        
        # Generate periodic reports
        local current_time=$(date +%s)
        if [[ $((current_time - last_report_time)) -ge $REPORT_INTERVAL ]]; then
            generate_report
            last_report_time=$current_time
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
        -i|--check-interval)
            CHECK_INTERVAL="$2"
            shift 2
            ;;
        -r|--report-interval)
            REPORT_INTERVAL="$2"
            shift 2
            ;;
        -d|--metrics-dir)
            METRICS_DIR="$2"
            shift 2
            ;;
        -a|--alert-threshold)
            ALERT_THRESHOLD="$2"
            shift 2
            ;;
        -t|--response-threshold)
            RESPONSE_TIME_THRESHOLD="$2"
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
            echo "  -u, --url URL                   Deployment URL to monitor"
            echo "  -i, --check-interval SECONDS   Check interval in seconds (default: 30)"
            echo "  -r, --report-interval SECONDS  Report interval in seconds (default: 300)"
            echo "  -d, --metrics-dir DIR          Metrics directory (default: ./logs/availability)"
            echo "  -a, --alert-threshold PERCENT  Availability alert threshold (default: 95.0)"
            echo "  -t, --response-threshold MS    Response time threshold in ms (default: 2000)"
            echo "  --slack-webhook URL            Slack webhook for notifications"
            echo "  --email-alerts EMAIL           Email address for alerts"
            echo "  -h, --help                     Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Check dependencies
for cmd in curl jq bc mail; do
    if ! command -v "$cmd" &> /dev/null; then
        echo "Warning: $cmd is not installed (some features may not work)"
    fi
done

# Run main function
main "$@"