# Deployment Fixes Applied

## Summary
Fixed multiple deployment configuration issues to enable consistent deployments like the working API service.

## Key Issues Identified & Fixed

### 1. Repository Reference Inconsistencies
- **Issue**: Mixed repository references (`annotation-platform` vs `abergman/annotation-platform`)
- **Fix**: Standardized all deployment configs to use `abergman/annotation-platform`
- **Files**: `.do/app.production.yaml`, `.do/app.staging.yaml`, `app.yaml`

### 2. Frontend Build Configuration Missing
- **Issue**: Frontend deployment failed due to missing build scripts and configuration
- **Fix**: 
  - Added `build:production` script to frontend/package.json
  - Created proper static site configuration in app deployment specs
  - Added frontend Dockerfile and nginx configuration

### 3. Complex Multi-Service vs Simple Deployment
- **Issue**: Production configs had complex multi-service setup while API worked as simple service
- **Fix**: Created `app-simple.yaml` with API + Frontend configuration matching working API pattern

### 4. CI/CD Workflow Inconsistencies  
- **Issue**: Deploy workflow referenced non-existent or incorrect app specs
- **Fix**: Updated workflow to use simplified `app-simple.yaml` configuration

### 5. Docker Configuration Issues
- **Issue**: Missing directories and permissions in Dockerfile
- **Fix**: Added proper directory creation and ownership in `Dockerfile.production`

## Files Created/Modified

### New Files:
- `app-simple.yaml` - Simplified working deployment configuration
- `frontend/Dockerfile.frontend` - Frontend container configuration  
- `frontend/nginx.conf` - Static site server configuration
- `scripts/deploy-setup.sh` - Deployment validation script
- `docs/deployment-fixes.md` - This documentation

### Modified Files:
- `app.yaml` - Updated with frontend service and correct routing
- `frontend/package.json` - Added production build script
- `Dockerfile.production` - Fixed directory creation
- `.github/workflows/deploy.yml` - Updated to use app-simple.yaml
- `.do/app.production.yaml` - Fixed repository references and branch names
- `.do/app.staging.yaml` - Fixed repository references

## Deployment Strategy

The fix implements a two-tier approach:

1. **API Service** (Node.js) - Routes: `/api/*`, `/health`
   - Uses existing working Dockerfile.production
   - MongoDB backend with environment secrets
   - Health check at `/api/health`

2. **Frontend Service** (React/Vite) - Routes: `/`
   - Static site build using buildpack deployment
   - Environment variables for API connection
   - Client-side routing support

## Testing

Use the deployment setup script:
```bash
./scripts/deploy-setup.sh staging
```

This validates:
- Docker build success
- Package.json scripts
- Frontend build process
- Required files presence

## Next Steps

1. Commit all changes to main branch
2. Push to trigger GitHub Actions deployment
3. Monitor Digital Ocean dashboard for successful deployment
4. Test endpoints:
   - API: https://annotat.ee/api/health
   - Frontend: https://annotat.ee/
5. If successful, the same pattern can be used for staging environment

## Architecture

```
annotat.ee
├── / (frontend - React static site)
├── /api/* (Node.js API with MongoDB)
└── /health (API health check)
```

This matches the working API deployment pattern while adding the frontend as a separate service with proper routing.