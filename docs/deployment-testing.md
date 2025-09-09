# Deployment Testing Documentation

## Overview

This document outlines the comprehensive testing suite for deployment validation of the annotation platform. The testing framework ensures that deployments are healthy, secure, and performant before going live.

## Test Suite Structure

```
tests/deployment/
├── smoke-tests.js              # Basic functionality validation
├── health-check.test.js        # System health monitoring
├── ssl-validation.test.js      # Security and certificate validation
└── performance-baseline.test.js # Performance benchmarks

scripts/
├── test-deployment.sh          # Main test runner
├── monitor-uptime.sh           # Continuous uptime monitoring
└── monitor-availability.sh     # Detailed availability monitoring
```

## Test Categories

### 1. Smoke Tests (`smoke-tests.js`)

**Purpose**: Validate basic functionality immediately after deployment.

**Coverage**:
- Basic connectivity to main domain
- API endpoint availability
- Database connectivity
- WebSocket functionality
- Static asset serving
- Error handling
- CORS configuration
- HTTP to HTTPS redirection

**Execution Time**: ~2-3 minutes

**Critical Endpoints**:
- `GET /` - Homepage
- `GET /api/health` - Health check
- `GET /api/status` - System status
- `GET /api/db/ping` - Database connectivity
- `WebSocket /ws` - Real-time communication

### 2. Health Check Tests (`health-check.test.js`)

**Purpose**: Comprehensive system health validation and monitoring.

**Coverage**:
- Health endpoint structure validation
- System status monitoring (database, cache, services)
- Performance metrics collection
- Resource usage validation (CPU, memory, disk)
- External dependency health
- Load balancer configuration
- Security headers validation

**Execution Time**: ~3-5 minutes

**Key Metrics**:
- Database latency < 1 second
- Memory usage < 90%
- CPU usage < 80%
- Disk usage < 85%
- Service availability
- Response time averages

### 3. SSL Validation Tests (`ssl-validation.test.js`)

**Purpose**: Ensure secure communication and certificate validity.

**Coverage**:
- Certificate validity and expiration
- TLS version and cipher strength
- Certificate chain validation
- Security header presence
- Vulnerability assessments (POODLE, BEAST)
- OCSP stapling
- DNS resolution validation

**Execution Time**: ~2-4 minutes

**Security Requirements**:
- TLS 1.2+ only
- Strong cipher suites
- Valid certificate chain
- HSTS headers
- Secure cookie settings
- Certificate expiry > 7 days

### 4. Performance Baseline Tests (`performance-baseline.test.js`)

**Purpose**: Establish performance benchmarks and validate response times.

**Coverage**:
- Response time measurements
- Throughput testing
- Concurrent request handling
- Database performance
- WebSocket latency
- Resource usage monitoring
- CDN performance (if applicable)

**Execution Time**: ~5-10 minutes

**Performance Thresholds**:
- Average response time < 500ms
- 95th percentile < 1000ms
- Throughput > 10 req/s
- Database queries < 100ms
- WebSocket latency < 100ms

## Test Runner Script

### Usage

```bash
# Basic usage
./scripts/test-deployment.sh

# Custom URL
./scripts/test-deployment.sh -u https://staging.annotat.ee

# Verbose output with custom report directory
./scripts/test-deployment.sh -v -r ./custom-reports

# With notifications
./scripts/test-deployment.sh \
  --slack-webhook https://hooks.slack.com/... \
  --email-alerts ops@example.com
```

### Command Line Options

```bash
-u, --url URL               Deployment URL to test
-v, --verbose               Enable verbose output
-r, --report-dir DIR        Report directory
-t, --timeout SECONDS       Test timeout
--slack-webhook URL         Slack webhook for notifications
--email-alerts EMAIL        Email address for alerts
-h, --help                  Show help message
```

### Output Files

The test runner generates several output files:

```
test-reports/
├── smoke-test-results.xml      # JUnit XML format
├── health-test-results.xml
├── ssl-test-results.xml
├── performance-test-results.xml
├── deployment-test-summary.html # Human-readable report
├── deployment-test-summary.json # Machine-readable summary
└── *.log                       # Individual test logs
```

## Monitoring Scripts

### Uptime Monitoring (`monitor-uptime.sh`)

**Purpose**: Continuous monitoring of service availability.

**Features**:
- Configurable check intervals
- Consecutive failure tracking
- Automatic alerting
- Metrics collection
- Recovery notifications

**Usage**:
```bash
# Basic monitoring
./scripts/monitor-uptime.sh

# Custom configuration
./scripts/monitor-uptime.sh \
  -u https://annotat.ee \
  -i 30 \
  -t 5 \
  --slack-webhook https://hooks.slack.com/...
```

### Availability Monitoring (`monitor-availability.sh`)

**Purpose**: Detailed availability tracking with comprehensive metrics.

**Features**:
- Multiple endpoint monitoring
- Response time tracking
- Availability percentage calculation
- Periodic reporting
- Threshold-based alerting

**Monitored Endpoints**:
- Homepage (`/`)
- Health check (`/api/health`)
- System status (`/api/status`)
- Authentication (`/api/auth/validate`)

## Integration with CI/CD

### GitHub Actions Integration

```yaml
name: Deployment Tests
on:
  deployment_status:
    
jobs:
  test-deployment:
    if: github.event.deployment_status.state == 'success'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - run: npm install
      - name: Run deployment tests
        run: |
          ./scripts/test-deployment.sh \
            -u ${{ github.event.deployment.payload.web_url }} \
            --slack-webhook ${{ secrets.SLACK_WEBHOOK }}
        env:
          DEPLOYMENT_URL: ${{ github.event.deployment.payload.web_url }}
```

### Manual Verification Checklist

After automated tests pass, manually verify:

- [ ] Login functionality works
- [ ] Annotation creation and editing
- [ ] File upload and download
- [ ] Real-time collaboration
- [ ] Email notifications
- [ ] Admin panel access
- [ ] Mobile responsiveness

## Troubleshooting

### Common Issues

#### 1. Connection Timeouts
```bash
# Check DNS resolution
dig annotat.ee

# Verify SSL certificate
openssl s_client -connect annotat.ee:443 -servername annotat.ee

# Test connectivity
curl -v https://annotat.ee
```

#### 2. SSL Certificate Issues
```bash
# Check certificate expiry
echo | openssl s_client -servername annotat.ee -connect annotat.ee:443 2>/dev/null | openssl x509 -noout -dates

# Verify certificate chain
curl -I https://annotat.ee
```

#### 3. Performance Issues
```bash
# Check server resources
curl https://annotat.ee/api/system/resources

# Monitor response times
./scripts/monitor-availability.sh -i 10 -r 60
```

### Debug Mode

Enable verbose logging for detailed troubleshooting:

```bash
export VERBOSE=true
export DEBUG=true
./scripts/test-deployment.sh -v
```

## Alerts and Notifications

### Slack Integration

Configure Slack webhook for real-time notifications:

```bash
export SLACK_WEBHOOK="https://hooks.slack.com/services/..."
./scripts/test-deployment.sh
```

### Email Alerts

Set up email notifications for critical issues:

```bash
export EMAIL_ALERTS="ops@example.com,dev@example.com"
./scripts/monitor-uptime.sh
```

### Alert Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Availability | < 99% | < 95% |
| Response Time | > 1s | > 2s |
| Error Rate | > 2% | > 5% |
| Consecutive Failures | 3 | 5 |

## Maintenance

### Regular Tasks

1. **Weekly**: Review test results and performance trends
2. **Monthly**: Update performance baselines
3. **Quarterly**: Review and update test cases
4. **Before major releases**: Run full test suite

### Test Data Cleanup

```bash
# Clean up old reports (keep last 30 days)
find test-reports/ -name "*.xml" -mtime +30 -delete
find logs/ -name "*.log" -mtime +30 -delete
```

## Best Practices

1. **Run tests in staging first** before production deployment
2. **Monitor continuously** after deployment
3. **Set up proper alerting** for rapid incident response
4. **Review metrics regularly** to identify trends
5. **Update baselines** as system evolves
6. **Document any manual verification steps**
7. **Keep test dependencies up to date**

## Support and Contact

- **Development Team**: dev@example.com
- **Operations Team**: ops@example.com
- **On-call Escalation**: +1-555-0123

For urgent deployment issues, contact the on-call engineer immediately.