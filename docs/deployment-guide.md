# Deployment Guide for Annotation Platform

This guide provides comprehensive instructions for deploying the Academic Annotation Platform to Digital Ocean.

## Overview

The platform is deployed using Digital Ocean App Platform with the following architecture:

- **Main API Service**: Node.js/Express application
- **WebSocket Service**: Real-time collaboration features
- **Database**: MongoDB for document storage
- **Caching/Sessions**: Redis for session management
- **Reverse Proxy**: Nginx for load balancing and SSL termination
- **Monitoring**: Health checks and system monitoring

## Prerequisites

1. **Digital Ocean Account** with App Platform access
2. **GitHub Repository** with the codebase
3. **Domain Name** configured (annotat.ee)
4. **Environment Variables** configured in Digital Ocean

## Configuration Files Overview

### Docker Configuration

- **`Dockerfile.production`**: Optimized Node.js production build
- **`Dockerfile.websocket`**: WebSocket service container
- **`Dockerfile.worker`**: Background job processing
- **`docker-compose.yml`**: Local development and testing

### Digital Ocean App Platform

- **`app.yaml`**: Production app configuration
- **`.do/app.production.yaml`**: Production environment settings
- **`.do/app.staging.yaml`**: Staging environment settings

### CI/CD Pipeline

- **`.github/workflows/deploy.yml`**: Automated deployment workflow
- **`scripts/deploy.sh`**: Deployment automation script

### Infrastructure

- **`nginx.conf`**: Reverse proxy configuration
- **`scripts/health-check.js`**: Health monitoring
- **`scripts/backup.js`**: Database backup automation
- **`scripts/cleanup.js`**: System maintenance
- **`scripts/monitor.js`**: Real-time monitoring

## Environment Setup

### 1. Environment Variables

Create environment files for each deployment stage:

```bash
# Copy example files
cp .env.example .env
cp .env.example .env.staging
cp .env.example .env.production
```

### 2. Required Environment Variables

```bash
# Application
NODE_ENV=production
DOMAIN=annotat.ee
SSL_ENABLED=true

# Security
SESSION_SECRET=your-session-secret
JWT_SECRET=your-jwt-secret

# Database
MONGODB_URI=your-mongodb-connection-string
REDIS_URL=your-redis-connection-string

# Digital Ocean
DIGITALOCEAN_ACCESS_TOKEN=your-do-token
APP_ID=your-app-platform-id
REGISTRY_NAME=your-container-registry

# Email
EMAIL_SMTP_HOST=smtp.provider.com
EMAIL_SMTP_USER=your-email
EMAIL_SMTP_PASS=your-password

# Storage
STORAGE_ACCESS_KEY=your-spaces-key
STORAGE_SECRET_KEY=your-spaces-secret

# Monitoring
SLACK_WEBHOOK_URL=your-slack-webhook
SENTRY_DSN=your-sentry-dsn
```

## Deployment Methods

### Method 1: Automated GitHub Actions (Recommended)

1. **Configure GitHub Secrets**:
   ```
   DIGITALOCEAN_ACCESS_TOKEN
   STAGING_APP_ID
   PRODUCTION_APP_ID
   REGISTRY_NAME
   MONGODB_URI
   REDIS_URL
   JWT_SECRET
   SESSION_SECRET
   SLACK_WEBHOOK
   ```

2. **Deploy to Staging**:
   ```bash
   git push origin main
   ```

3. **Deploy to Production**:
   ```bash
   git push origin production
   ```

### Method 2: Manual Deployment Script

1. **Deploy to Staging**:
   ```bash
   ./scripts/deploy.sh staging
   ```

2. **Deploy to Production**:
   ```bash
   ./scripts/deploy.sh production
   ```

### Method 3: Digital Ocean CLI

1. **Install doctl**:
   ```bash
   curl -sL https://github.com/digitalocean/doctl/releases/download/v1.100.0/doctl-1.100.0-linux-amd64.tar.gz | tar -xzv
   sudo mv doctl /usr/local/bin
   ```

2. **Authenticate**:
   ```bash
   doctl auth init
   ```

3. **Deploy App**:
   ```bash
   doctl apps create --spec app.yaml
   doctl apps update YOUR_APP_ID --spec app.yaml
   ```

## Service Configuration

### Main API Service

```yaml
services:
  - name: api
    dockerfile_path: Dockerfile.production
    instance_count: 2
    instance_size_slug: basic-xxs
    http_port: 8080
    routes:
      - path: /
    health_check:
      http_path: /health
      timeout_seconds: 5
```

### WebSocket Service

```yaml
services:
  - name: websocket
    dockerfile_path: Dockerfile.websocket
    instance_count: 1
    instance_size_slug: basic-xxs
    http_port: 8081
    routes:
      - path: /socket.io
```

### Database Configuration

```yaml
databases:
  - name: annotation-db
    engine: MONGODB
    version: "6"
    size: basic-xs
    num_nodes: 1
```

## Monitoring and Maintenance

### Health Checks

```bash
# Manual health check
node scripts/health-check.js --url https://annotat.ee

# Continuous monitoring
node scripts/monitor.js start
```

### Database Backup

```bash
# Create backup
node scripts/backup.js create

# List backups
node scripts/backup.js list

# Restore from backup
node scripts/backup.js restore /path/to/backup
```

### System Cleanup

```bash
# Full cleanup
node scripts/cleanup.js

# Database only
node scripts/cleanup.js database

# Files only
node scripts/cleanup.js files
```

## SSL/TLS Configuration

Digital Ocean App Platform automatically handles SSL/TLS certificates for custom domains.

### Domain Configuration

1. **Add Domain to App**:
   ```yaml
   domains:
     - domain: annotat.ee
       type: PRIMARY
     - domain: www.annotat.ee
       type: ALIAS
   ```

2. **DNS Configuration**:
   ```
   A    annotat.ee       YOUR_APP_IP
   CNAME www.annotat.ee  annotat.ee
   ```

## Security Configuration

### Environment Variables

All sensitive data is stored as encrypted environment variables in Digital Ocean:

```yaml
envs:
  - key: JWT_SECRET
    scope: RUN_TIME
    type: SECRET
  - key: MONGODB_URI
    scope: RUN_TIME
    type: SECRET
```

### Security Headers

Nginx configuration includes comprehensive security headers:

```nginx
add_header X-Frame-Options "DENY" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header Content-Security-Policy "default-src 'self'; ..." always;
```

## Performance Optimization

### Auto-scaling Configuration

```yaml
autoscaling:
  min_instance_count: 1
  max_instance_count: 5
  metrics:
    - type: cpu
      value: 80
    - type: memory
      value: 80
```

### Caching Strategy

- **Redis**: Session storage and WebSocket scaling
- **Nginx**: Static asset caching
- **MongoDB**: Indexed queries and connection pooling

## Troubleshooting

### Common Issues

1. **Deployment Fails**:
   ```bash
   # Check app logs
   doctl apps logs YOUR_APP_ID --type build
   doctl apps logs YOUR_APP_ID --type deploy
   ```

2. **Health Check Fails**:
   ```bash
   # Test health endpoint
   curl https://annotat.ee/health
   
   # Check application logs
   doctl apps logs YOUR_APP_ID
   ```

3. **Database Connection Issues**:
   ```bash
   # Verify MongoDB connection
   mongosh "YOUR_MONGODB_URI"
   
   # Check network connectivity
   doctl apps logs YOUR_APP_ID | grep -i mongo
   ```

### Log Analysis

```bash
# View real-time logs
doctl apps logs YOUR_APP_ID --follow

# Filter logs by component
doctl apps logs YOUR_APP_ID --type run --component api

# Download logs
doctl apps logs YOUR_APP_ID > app.log
```

## Rollback Procedures

### Automated Rollback

The GitHub Actions workflow includes automatic rollback on failure:

```yaml
- name: Rollback on failure
  if: failure()
  run: ./scripts/rollback.sh production
```

### Manual Rollback

```bash
# Rollback to previous deployment
doctl apps list-deployments YOUR_APP_ID
doctl apps create-deployment YOUR_APP_ID --deployment-id PREVIOUS_ID
```

## Performance Monitoring

### Built-in Metrics

Digital Ocean provides built-in monitoring for:
- CPU utilization
- Memory usage
- Network traffic
- Request metrics

### Custom Monitoring

```bash
# Start system monitor
node scripts/monitor.js start

# Performance benchmarks
npm run test:performance
```

## Backup and Recovery

### Automated Backups

```yaml
jobs:
  - name: backup-job
    kind: CRON
    schedule: "0 4 * * *"  # Daily at 4 AM
    run_command: node scripts/backup.js create
```

### Manual Backup

```bash
# Create full backup
./scripts/backup.js create

# Backup with cloud upload
DO_SPACES_KEY=xxx DO_SPACES_SECRET=xxx ./scripts/backup.js create
```

## Support and Resources

- **Digital Ocean Docs**: https://docs.digitalocean.com/products/app-platform/
- **GitHub Repository**: Your repository URL
- **Monitoring Dashboard**: https://cloud.digitalocean.com/apps
- **Domain Management**: https://cloud.digitalocean.com/networking/domains

## Next Steps

1. Set up monitoring alerts
2. Configure backup notifications
3. Implement user authentication
4. Add performance optimization
5. Set up development/staging environments
6. Configure CI/CD pipelines
7. Add error tracking and logging