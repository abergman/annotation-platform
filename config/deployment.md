# Digital Ocean App Platform Deployment Guide

## Architecture Overview

This configuration deploys the Academic Annotation Platform as a multi-service application on Digital Ocean App Platform:

### Services:

1. **Backend API** (Python FastAPI)
   - Main application server
   - Handles REST API endpoints
   - Runs on port 8000
   - Routes: `/api/*`, `/health`, `/docs`

2. **WebSocket Server** (Node.js)
   - Real-time communication
   - Handles WebSocket connections
   - Runs on port 3001
   - Routes: `/ws/*`

3. **Frontend** (React Static Site)
   - User interface
   - Built with Vite
   - Served as static files
   - Routes: `/*` (with fallback to index.html)

4. **Cache Worker** (Python Background Worker)
   - Cache warming and maintenance
   - Background task processing
   - Connects to Redis for caching

### Database:
- **PostgreSQL 15** (managed database)
- Basic XXS size for development
- Automatic backups and scaling

## Environment Variables

### Required Secrets (set in App Platform):
- `DATABASE_URL` - PostgreSQL connection string (auto-provided)
- `SECRET_KEY` - JWT signing secret
- `REDIS_URL` - Redis connection string (auto-provided)

### App Configuration:
- `ALLOWED_ORIGINS` - Frontend URL for CORS
- `DEBUG` - Set to "false" for production
- `UPLOAD_DIR` - "/tmp/uploads" (ephemeral storage)
- `EXPORT_DIR` - "/tmp/exports" (ephemeral storage)

## Deployment Steps

1. **Prepare Repository**
   ```bash
   # Copy configuration files to project root
   cp config/app.yaml ./
   cp config/Dockerfile.backend ./Dockerfile
   ```

2. **Create App on Digital Ocean**
   ```bash
   doctl apps create --spec app.yaml
   ```

3. **Set Environment Secrets**
   ```bash
   # Generate a strong secret key
   export SECRET_KEY=$(openssl rand -base64 32)
   
   # Set via doctl or App Platform console
   doctl apps update APP_ID --spec app.yaml
   ```

4. **Database Setup**
   - Database will be automatically created
   - Run migrations after first deployment:
   ```bash
   # Via App Platform console or CLI
   alembic upgrade head
   ```

## File Structure

```
/config/
├── app.yaml                 # Main App Platform configuration
├── Dockerfile.backend       # Python FastAPI container
├── Dockerfile.websocket     # Node.js WebSocket container
├── .env.production         # Production environment template
├── cache_worker.py         # Background cache worker
├── websocket/
│   ├── package.json        # WebSocket server dependencies
│   ├── server.js          # WebSocket server implementation
└── deployment.md          # This guide
```

## Health Checks

Each service includes comprehensive health checks:

- **Backend**: `GET /health` - Database connectivity, cache status
- **WebSocket**: `GET /health` - Connection stats, Redis connectivity
- **Worker**: Built-in Redis connectivity checks

## Scaling

### Vertical Scaling:
- Upgrade instance sizes in app.yaml
- Available sizes: basic-xxs, basic-xs, basic-s, basic-m

### Horizontal Scaling:
- Increase `instance_count` for services
- WebSocket server supports multiple instances
- Cache worker should remain at 1 instance

## Monitoring

### Built-in Monitoring:
- App Platform provides metrics dashboard
- Health check status monitoring
- Resource usage tracking

### Custom Metrics:
- WebSocket connections: `GET /ws/stats`
- Cache statistics: Available in Redis
- Application metrics: `/api/monitoring/*`

## Troubleshooting

### Common Issues:

1. **Database Connection Errors**
   - Check DATABASE_URL environment variable
   - Verify database is running and accessible

2. **WebSocket Connection Failures**
   - Verify WebSocket service is healthy
   - Check CORS configuration for frontend

3. **Cache Issues**
   - Check Redis connection in worker logs
   - Verify REDIS_URL environment variable

4. **Build Failures**
   - Check build logs in App Platform console
   - Verify all dependencies in requirements.txt/package.json

### Log Access:
```bash
# View application logs
doctl apps logs APP_ID --type build
doctl apps logs APP_ID --type deploy
doctl apps logs APP_ID --type run
```

## Performance Optimization

### Frontend:
- Static site is served via CDN
- Assets are automatically compressed
- Enable browser caching headers

### Backend:
- Use Redis for session storage
- Implement database connection pooling
- Cache frequently accessed data

### WebSocket:
- Connection pooling for multiple instances
- Message throttling for high-traffic projects
- Automatic cleanup of stale connections

## Security

### Network Security:
- All services communicate within private network
- HTTPS enforced for external connections
- Environment variables encrypted at rest

### Application Security:
- JWT tokens for authentication
- CORS configured for frontend domain
- Input validation on all endpoints
- SQL injection protection via ORM

## Cost Optimization

### Resource Sizing:
- Start with basic-xxs instances
- Monitor usage and scale as needed
- Use worker instances only when necessary

### Database:
- Basic XXS suitable for development
- Upgrade based on connection/storage needs
- Enable automated backups

## Backup Strategy

### Database:
- Automated daily backups via App Platform
- Point-in-time recovery available
- Manual backups via pg_dump if needed

### Application Data:
- User uploads stored in `/tmp` (ephemeral)
- Implement external storage (S3) for persistence
- Export functionality for data portability