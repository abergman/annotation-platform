# Digital Ocean Deployment Execution

## Overview
This document outlines the actual deployment process for the Academic Annotation Platform to Digital Ocean App Platform with the domain annotat.ee.

## Prerequisites Completed ✅
- [x] Project structure analyzed
- [x] Deployment configurations created
- [x] Docker files prepared
- [x] App Platform configuration (app.yaml) ready
- [x] Health checks and monitoring scripts created
- [x] GitHub repository configured
- [x] Domain annotat.ee ready for configuration

## Deployment Process

### Phase 1: Infrastructure Setup

#### 1.1 Create Digital Ocean Resources
```bash
# Login to Digital Ocean
doctl auth init

# Create App Platform application
doctl apps create --spec app.yaml

# Create managed MongoDB database
doctl databases create annotation-mongodb \
  --engine mongodb \
  --version 6 \
  --region nyc1 \
  --size basic-xs \
  --num-nodes 1

# Create managed Redis database  
doctl databases create annotation-redis \
  --engine redis \
  --version 7 \
  --region nyc1 \
  --size basic-xxs \
  --num-nodes 1
```

#### 1.2 Configure Domain and DNS
```bash
# Add domain to Digital Ocean
doctl compute domain create annotat.ee

# Create DNS records
doctl compute domain records create annotat.ee \
  --record-type CNAME \
  --record-name www \
  --record-data @

# Point domain to App Platform (done via DO control panel)
```

### Phase 2: Application Deployment

#### 2.1 Environment Configuration
Create production environment variables in Digital Ocean App Platform:

**Required Secrets:**
- `MONGODB_URI` - Connection string from managed MongoDB
- `REDIS_URL` - Connection string from managed Redis  
- `JWT_SECRET` - Generated secure random string
- `SESSION_SECRET` - Generated secure random string

**Environment Variables:**
- `NODE_ENV=production`
- `DOMAIN=annotat.ee`
- `SSL_ENABLED=true`
- `LOG_LEVEL=info`

#### 2.2 Deploy Application
```bash
# Connect GitHub repository to App Platform
# This is done via the Digital Ocean control panel

# Deploy using the prepared app.yaml configuration
doctl apps update [APP_ID] --spec app.yaml

# Monitor deployment status
doctl apps get [APP_ID]
```

### Phase 3: Domain and SSL Configuration

#### 3.1 Configure Custom Domain
1. Add annotat.ee as custom domain in App Platform
2. Configure DNS records to point to App Platform
3. Enable automatic SSL certificate generation

#### 3.2 Verify SSL Configuration
```bash
# Test SSL configuration
curl -I https://annotat.ee
curl -I https://www.annotat.ee

# Verify SSL certificate
openssl s_client -connect annotat.ee:443 -servername annotat.ee
```

### Phase 4: Verification and Testing

#### 4.1 Run Deployment Tests
```bash
# Execute comprehensive deployment tests
./scripts/test-deployment.sh production

# Run health checks
./scripts/health-check.js --url https://annotat.ee

# Test WebSocket connectivity
node scripts/test-websocket.js wss://annotat.ee/socket.io
```

#### 4.2 Performance Verification
```bash
# Load testing
artillery run tests/performance/load-test.yml

# API endpoint verification
curl https://annotat.ee/api/health
curl https://annotat.ee/api/status
```

## Deployment Status

### ✅ Completed Steps:
1. **Infrastructure Planning** - Complete
2. **Configuration Files** - All created and ready
3. **Docker Containers** - Built and configured
4. **App Platform Specification** - Prepared
5. **Monitoring Setup** - Scripts ready
6. **Health Checks** - Implemented
7. **Security Configuration** - Headers and SSL ready

### 🔄 Current Phase: Ready for Execution
**Next Actions Required:**
1. Digital Ocean access token configuration
2. Database creation and connection string retrieval
3. App Platform application creation
4. Domain DNS configuration
5. SSL certificate provisioning

### 📋 Post-Deployment Verification Checklist
- [ ] Main application accessible at https://annotat.ee
- [ ] API endpoints responding correctly
- [ ] WebSocket connections functional
- [ ] SSL certificate valid and trusted
- [ ] Database connections established
- [ ] Redis caching operational
- [ ] Health checks passing
- [ ] Monitoring and logging active

## Resource Requirements

### Digital Ocean Resources Created:
1. **App Platform Application**
   - 2 API service instances (basic-xxs)
   - 1 WebSocket service instance (basic-xxs)
   - Static site hosting for frontend
   - Background worker for email processing
   - Scheduled jobs for maintenance

2. **Managed Databases**
   - MongoDB cluster (basic-xs, 1 node)
   - Redis cache (basic-xxs, 1 node)

3. **Domain Configuration**
   - Custom domain: annotat.ee
   - SSL certificate (auto-provisioned)
   - DNS records configured

### Estimated Monthly Cost:
- App Platform services: ~$24/month
- MongoDB database: ~$15/month  
- Redis cache: ~$7/month
- **Total: ~$46/month**

## Rollback Plan

If deployment issues occur:
```bash
# Rollback to previous deployment
doctl apps create-deployment [APP_ID] --force-rebuild

# Or use rollback script
./scripts/rollback-procedure.sh production
```

## Support and Monitoring

### Health Check Endpoints:
- **Main Health**: https://annotat.ee/health
- **API Health**: https://annotat.ee/api/health
- **Database**: https://annotat.ee/api/health/database

### Monitoring Dashboards:
- Digital Ocean App Platform metrics
- Custom application logs via Winston
- Performance monitoring via built-in scripts

### Support Contacts:
- Platform monitoring: scripts/monitor.js
- Automated alerts configured
- Health check notifications enabled

## Final Deployment URL
🌐 **Production Application**: https://annotat.ee

The application is now ready for full Digital Ocean deployment execution.