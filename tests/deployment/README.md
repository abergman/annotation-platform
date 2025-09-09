# Deployment Validation Test Suite

Comprehensive test suite for validating deployment health, security, performance, and reliability.

## 🚀 Quick Start

### Run All Validations
```bash
# Using the validation script (recommended)
./scripts/validate-deployment.sh https://annotat.ee production

# Using the Node.js validator directly
node tests/deployment/deployment-validator.js https://annotat.ee production
```

### Run Individual Test Suites
```bash
# Health checks (critical)
DEPLOY_URL=https://annotat.ee npm run test:deployment:health

# Environment validation (critical)
DEPLOY_URL=https://annotat.ee npm run test:deployment:environment

# Service connectivity
DEPLOY_URL=https://annotat.ee npm run test:deployment:connectivity

# Platform-specific validation
DEPLOY_URL=https://annotat.ee npm run test:deployment:platform

# Performance validation
DEPLOY_URL=https://annotat.ee npm run test:deployment:performance

# Recovery procedures
DEPLOY_URL=https://annotat.ee npm run test:deployment:recovery
```

## 📋 Test Categories

### 1. Health Checks (`health-checks.test.js`)
**Critical**: ✅ **Required for deployment**

- Primary API health endpoint validation
- Service readiness checks
- Environment configuration validation
- Database connection validation
- Performance under load
- Error handling and recovery

### 2. Environment Validation (`environment-validation.test.js`)
**Critical**: ✅ **Required for deployment**

- Required environment variables
- Security configuration
- Digital Ocean specific settings
- Resource limits validation
- Secret management verification

### 3. Service Connectivity (`service-connectivity.test.js`)
**Priority**: High ⚠️

- API service connectivity and CORS
- Database operations (read/write)
- External service dependencies
- Network security and SSL
- Inter-service communication
- Performance and load capacity

### 4. Digital Ocean Platform (`digital-ocean-platform.test.js`)
**Priority**: Medium ℹ️

- App Platform configuration compliance
- Domain and SSL configuration
- Health check endpoint compatibility
- Auto-scaling readiness
- Build and deployment validation
- Monitoring integration
- Security and compliance

### 5. Performance Validation (`performance-validation.test.js`)
**Priority**: Medium ℹ️

- Response time benchmarks
- Concurrent load handling
- Memory and resource utilization
- Performance regression detection
- Realistic user journey simulation

### 6. Rollback & Recovery (`rollback-recovery.test.js`)
**Priority**: Low 📝

- System state backup validation
- Failure simulation and detection
- Automatic recovery mechanisms
- Data recovery procedures
- Disaster recovery validation

## 🔧 Configuration

### Environment Variables
```bash
DEPLOY_URL=https://annotat.ee       # Target deployment URL
NODE_ENV=production                 # Environment type
DO_APP_ID=58c46a38-9d6b-41d8...    # Digital Ocean App ID
```

### Test Timeouts
- Health checks: 60 seconds
- Environment validation: 30 seconds
- Service connectivity: 60 seconds
- Platform validation: 120 seconds
- Performance validation: 600 seconds (10 minutes)
- Recovery validation: 300 seconds (5 minutes)

## 📊 Exit Codes

### Validation Script
- `0` - All validations passed ✅
- `1` - Some warnings but deployment may proceed ⚠️
- `2` - Critical failures, deployment should NOT proceed ❌

### Test Suite Categories
- **Critical failures** = Stop deployment immediately
- **High priority failures** = Review and fix recommended
- **Medium/Low priority failures** = Monitor and address post-deployment

## 🎯 Usage Examples

### CI/CD Pipeline Integration
```bash
# In your CI/CD pipeline
./scripts/validate-deployment.sh $DEPLOY_URL $ENVIRONMENT 600 true

if [ $? -eq 0 ]; then
  echo "✅ Deployment validation passed - proceeding"
elif [ $? -eq 1 ]; then
  echo "⚠️ Deployment has warnings - review and decide"
else
  echo "❌ Deployment validation failed - stopping"
  exit 1
fi
```

### Local Development Testing
```bash
# Test against local development
./scripts/validate-deployment.sh http://localhost:8080 development

# Test with specific timeout and sequential execution
./scripts/validate-deployment.sh http://localhost:8080 development 180 false
```

### Production Deployment Validation
```bash
# Comprehensive production validation
./scripts/validate-deployment.sh https://annotat.ee production 600 true

# Quick health check only
curl -f https://annotat.ee/health
```

## 📈 Performance Benchmarks

### Expected Response Times
- Health checks: < 500ms average, < 1s P95
- API endpoints: < 1s average
- Database operations: < 3s average
- File uploads: < 10s average

### Load Handling
- Concurrent users: 5-50 users
- Success rate: > 95% under normal load
- Memory usage: < 500MB total heap
- CPU usage: < 90% sustained

### Performance Regression Thresholds
- Response time degradation: < 3x baseline
- Memory growth: < 50MB per test cycle
- Success rate: > 90% maintained

## 🛡️ Security Validations

### Network Security
- HTTPS/SSL certificate validation
- Security headers verification
- CORS configuration
- Rate limiting functionality

### Data Protection
- Sensitive data not exposed in responses
- Environment variables properly masked
- Database connection encryption
- Session management security

### Access Control
- Authentication mechanisms
- Authorization checks
- Admin endpoint protection
- API key validation

## 🚨 Troubleshooting

### Common Issues

#### Health Check Failures
```bash
# Check basic connectivity
curl -v https://annotat.ee/health

# Check DNS resolution
nslookup annotat.ee

# Check certificate
openssl s_client -connect annotat.ee:443 -servername annotat.ee
```

#### Database Connection Issues
```bash
# Check MongoDB connectivity (if accessible)
mongosh "mongodb+srv://..."

# Check network connectivity
telnet annotation-mongodb-e44da03f.mongo.ondigitalocean.com 27017
```

#### Performance Issues
```bash
# Check system resources
curl https://annotat.ee/api/v1/status/memory
curl https://annotat.ee/api/v1/status/resources

# Run load test manually
for i in {1..10}; do curl -w "%{time_total}\n" -o /dev/null -s https://annotat.ee/health; done
```

## 📝 Extending the Test Suite

### Adding New Test Categories
1. Create new test file in `tests/deployment/`
2. Follow existing naming pattern: `new-category.test.js`
3. Update `deployment-validator.js` to include new suite
4. Add to validation script if needed
5. Update this README with new category

### Adding New Test Cases
```javascript
describe('New Test Category', () => {
  test('should validate new functionality', async () => {
    const response = await request(baseUrl)
      .get('/api/v1/new-endpoint')
      .expect(200);
    
    expect(response.body).toHaveProperty('status', 'success');
  });
});
```

### Performance Test Guidelines
- Use realistic data sizes and user patterns
- Include proper cleanup after tests
- Set appropriate timeouts
- Monitor resource usage
- Document expected performance characteristics

## 🔄 Integration with Hive Mind

This test suite integrates with the Claude Flow Hive Mind coordination system:

- **Pre-task hooks**: Initialize validation session
- **Post-edit hooks**: Save test results to swarm memory
- **Notification hooks**: Communicate status to other agents
- **Session management**: Track validation progress across agents

### Coordination Commands
```bash
# Initialize validation session
npx claude-flow@alpha hooks pre-task --description "deployment-validation"

# Store validation results
npx claude-flow@alpha hooks post-edit --file "validation-results" --memory-key "swarm/tester/results"

# Notify hive of completion
npx claude-flow@alpha hooks notify --message "Deployment validation completed"

# End validation session
npx claude-flow@alpha hooks post-task --task-id "deployment-validation"
```

---

**Created by**: Tester Agent in the Hive Mind collective  
**Last Updated**: 2025-09-09  
**Version**: 1.0.0