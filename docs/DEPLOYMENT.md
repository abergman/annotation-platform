# 🚀 Digital Ocean App Platform Deployment Guide

## Academic Annotation Platform - Multi-Service Deployment

This guide walks you through deploying the Academic Annotation Platform to Digital Ocean App Platform with all required services.

## 📋 Architecture Overview

The platform consists of three main services:

1. **🐍 Python FastAPI Backend** (`api-backend`)
   - Port: 8000
   - Routes: `/api/*`, `/health`, `/`
   - Docker: `Dockerfile.production`

2. **🔌 Node.js WebSocket Server** (`websocket-server`)  
   - Port: 8001
   - Routes: `/ws/*`
   - Docker: `Dockerfile.websocket`
   - Real-time features for collaborative annotation

3. **⚛️ React Frontend** (`frontend`)
   - Static site served via CDN
   - Vite build system
   - Routes: `/` (with fallback routing)

4. **🗄️ Managed Services**
   - PostgreSQL 15 database
   - Redis 7 cache (optional for scaling)

## 🚨 Prerequisites

### Required Software
- [doctl CLI](https://docs.digitalocean.com/reference/doctl/how-to/install/) installed and authenticated
- Git repository on GitHub
- DigitalOcean account with sufficient credits

### Required Account Setup
1. **DigitalOcean Authentication:**
   ```bash
   doctl auth init
   ```

2. **GitHub Repository:**
   - Push your code to a GitHub repository
   - The repository must be public or you need to configure access

## ⚙️ Pre-Deployment Setup

### 1. Update Configuration Files

**🔧 Update app.yaml:**
```yaml
# In .do/app.yaml, replace:
repo: YOUR_GITHUB_USERNAME/annotation
# With your actual GitHub username/organization
```

**🔐 Environment Variables:**
Copy and customize the environment template:
```bash
cp .env.production.template .env.production
# Edit .env.production with your actual values
```

**Critical variables to set:**
- `SECRET_KEY`: Generate a secure random string (32+ characters)
- `JWT_SECRET`: Generate a different secure random string
- Database credentials (if using existing managed database)

### 2. Generate Secure Keys

```bash
# Generate SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate JWT_SECRET
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## 🚀 Deployment Steps

### Method 1: Automated Script (Recommended)

```bash
# Run the deployment script
.do/deploy.sh
```

The script will:
- ✅ Validate prerequisites 
- ✅ Check required files
- ✅ Create the app on DigitalOcean
- ✅ Provide post-deployment instructions

### Method 2: Manual Deployment

```bash
# Validate configuration
doctl auth list

# Create app from specification
doctl apps create --spec .do/app.yaml

# Get app ID and status
APP_ID=$(doctl apps list --format ID --no-header | head -1)
doctl apps get $APP_ID
```

## 🔧 Post-Deployment Configuration

### 1. Set Environment Variables in DigitalOcean Dashboard

Navigate to: `Apps → Your App → Settings → Environment Variables`

**🚨 Required Variables:**
```bash
SECRET_KEY=your_generated_secret_key_here
JWT_SECRET=your_generated_jwt_secret_here
```

**🗄️ Database Variables (if using existing database):**
```bash
DATABASE_URL=postgresql://user:pass@host:port/db?sslmode=require
DB_HOST=your_db_host
DB_PORT=25060
DB_USER=your_db_user  
DB_PASSWORD=your_db_password
DB_NAME=your_db_name
```

### 2. Trigger Deployment

After setting environment variables:
1. Go to `Apps → Your App → Deployments`
2. Click "Create Deployment" to redeploy with new environment variables

## 📊 Monitoring Deployment

### Using doctl CLI

```bash
# Get app status
doctl apps get $APP_ID

# View build logs
doctl apps logs $APP_ID --type build --follow

# View deployment logs  
doctl apps logs $APP_ID --type deploy --follow

# View runtime logs
doctl apps logs $APP_ID --type run --follow
```

### Using DigitalOcean Dashboard

1. Navigate to [DigitalOcean Apps](https://cloud.digitalocean.com/apps)
2. Click your app name
3. View deployment status, logs, and metrics

## 🏥 Health Checks

The deployment includes comprehensive health checks:

- **Backend API**: `GET /health`
- **WebSocket Server**: `GET /health` 
- **Database**: Connection test via backend
- **Cache**: Redis connectivity (if enabled)

## 🔗 Service URLs

After successful deployment, your services will be available at:

```
Frontend:    https://your-app-12345.ondigitalocean.app/
Backend API: https://your-app-12345.ondigitalocean.app/api/
WebSocket:   wss://your-app-12345.ondigitalocean.app/ws/
Docs:        https://your-app-12345.ondigitalocean.app/api/docs
```

## 🐛 Troubleshooting

### Common Issues

**❌ Build Failure - Docker Issues:**
```bash
# Check if Docker files exist
ls -la Dockerfile.production Dockerfile.websocket

# Test build locally (optional)
docker build -f Dockerfile.production -t annotation-backend .
docker build -f Dockerfile.websocket -t annotation-websocket .
```

**❌ Environment Variables Not Set:**
- Ensure `SECRET_KEY` and `JWT_SECRET` are set in DigitalOcean dashboard
- Check variable names match exactly (case-sensitive)
- Trigger new deployment after setting variables

**❌ Database Connection Issues:**
- Verify DATABASE_URL format: `postgresql://user:pass@host:port/db?sslmode=require`
- Ensure database allows connections from App Platform
- Check database credentials in DigitalOcean dashboard

**❌ GitHub Repository Access:**
- Ensure repository is public or properly configured for access
- Verify branch name in app.yaml (usually `main` or `master`)
- Check repository URL format in app.yaml

### Debug Commands

```bash
# Check app status
doctl apps get $APP_ID --format ID,Spec.Name,Phase,CreatedAt

# List app deployments
doctl apps list-deployments $APP_ID

# Get detailed deployment info
doctl apps get-deployment $APP_ID $DEPLOYMENT_ID

# Check app configuration
doctl apps get $APP_ID --format Spec
```

## 📈 Scaling & Performance

### Initial Configuration
- **Backend**: 1x basic-xs instance (1 CPU, 512MB RAM)
- **WebSocket**: 1x basic-xs instance 
- **Frontend**: 1x basic-xxs instance (static content)
- **Database**: db-s-1vcpu-1gb (1 CPU, 1GB RAM)

### Scaling Options
```bash
# Scale backend service
doctl apps update $APP_ID --spec modified-app.yaml

# Monitor resource usage
doctl apps get $APP_ID --format Spec.Services[*].InstanceSizeSlug
```

## 💰 Cost Estimation

**Monthly Costs (approximate):**
- Backend service: $12/month (basic-xs)
- WebSocket service: $12/month (basic-xs)  
- Frontend service: $3/month (basic-xxs)
- PostgreSQL database: $15/month (db-s-1vcpu-1gb)
- Redis cache: $15/month (db-s-1vcpu-1gb)

**Total: ~$57/month** (excluding bandwidth)

## 🔒 Security Best Practices

1. **✅ Environment Variables**: Use DigitalOcean's encrypted environment variables
2. **✅ HTTPS**: Automatic SSL termination by App Platform
3. **✅ Database**: Managed database with automatic backups
4. **✅ Secrets**: Never commit secrets to Git repository
5. **✅ Access Control**: Use strong JWT secrets and secure passwords

## 📚 Additional Resources

- [DigitalOcean App Platform Documentation](https://docs.digitalocean.com/products/app-platform/)
- [App Platform Pricing](https://www.digitalocean.com/pricing/app-platform)
- [doctl CLI Reference](https://docs.digitalocean.com/reference/doctl/)

## 🆘 Support

If you encounter issues:

1. Check the deployment logs in DigitalOcean dashboard
2. Verify all environment variables are set correctly  
3. Ensure your GitHub repository is accessible
4. Review this documentation for common solutions
5. Contact DigitalOcean support if needed

---

**🎉 Congratulations!** Your Academic Annotation Platform should now be running on DigitalOcean App Platform with full multi-service architecture support.