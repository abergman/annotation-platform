# Academic Annotation Platform - Deployment Requirements

## System Overview

The Academic Annotation Platform is a full-stack application designed for collaborative document analysis with real-time features. The system consists of:

- **Backend**: Python FastAPI application with PostgreSQL database
- **Real-time Layer**: Node.js WebSocket server for collaborative features
- **Database**: PostgreSQL for persistent data storage
- **Cache Layer**: Redis for session management and real-time coordination
- **Reverse Proxy**: Nginx for load balancing and SSL termination

## Architecture Analysis

### Backend Application (Python/FastAPI)
- **Framework**: FastAPI 0.104.1 with uvicorn server
- **Database ORM**: SQLAlchemy 2.0.23 with PostgreSQL
- **Authentication**: JWT tokens with bcrypt password hashing
- **File Processing**: Support for TXT, DOCX, PDF, CSV formats
- **Export Formats**: JSON, CSV, XLSX, XML, CoNLL, COCO, YOLO
- **Real-time**: WebSocket integration for batch operations
- **Caching**: Redis integration for performance optimization

### Real-time WebSocket Server (Node.js)
- **Framework**: Socket.IO 4.7.2 with Express.js
- **Features**: Real-time collaboration, cursor tracking, operational transforms
- **Scaling**: Redis adapter for multi-instance deployment
- **Conflict Resolution**: Built-in conflict detection and resolution
- **Message Queuing**: Offline user message handling

### Database Requirements
- **Primary Database**: PostgreSQL 12+ 
- **Cache Database**: Redis 7.2+
- **Connection Pooling**: SQLAlchemy connection pooling
- **Migrations**: Alembic for database versioning

## Resource Requirements

### Minimum Production Requirements

#### Hardware Specifications
- **CPU**: 4 vCPUs (Intel/AMD x64)
- **RAM**: 8GB minimum, 16GB recommended
- **Storage**: 50GB SSD minimum, 200GB recommended
- **Network**: 1Gbps network interface

#### Per-Service Resource Allocation
- **FastAPI Backend**: 2GB RAM, 1.5 vCPU
- **WebSocket Server**: 1GB RAM, 0.5 vCPU
- **PostgreSQL**: 3GB RAM, 1 vCPU, 20GB storage
- **Redis**: 1GB RAM, 0.5 vCPU
- **Nginx**: 512MB RAM, 0.5 vCPU

### Scaling Recommendations

#### Small Deployment (1-50 concurrent users)
- **Total RAM**: 8GB
- **CPU**: 4 vCPUs
- **Storage**: 100GB SSD
- **Bandwidth**: 100Mbps

#### Medium Deployment (50-200 concurrent users)
- **Total RAM**: 16GB
- **CPU**: 8 vCPUs
- **Storage**: 300GB SSD
- **Bandwidth**: 500Mbps

#### Large Deployment (200+ concurrent users)
- **Total RAM**: 32GB+
- **CPU**: 16+ vCPUs
- **Storage**: 500GB+ SSD
- **Bandwidth**: 1Gbps+
- **Load Balancing**: Multiple backend instances

## Production Dependencies

### Python Backend Dependencies
```
# Core Framework (Production)
fastapi==0.104.1
uvicorn[standard]==0.24.0
gunicorn==21.2.0  # Production WSGI server

# Database & ORM
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
alembic==1.12.1

# Authentication & Security
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.6

# Data Processing
pandas==2.1.4
numpy==1.25.2
nltk==3.8.1
spacy==3.7.2

# File Processing
python-docx==1.1.0
PyPDF2==3.0.1
openpyxl==3.1.2

# Caching & Performance
redis==5.0.1
hiredis==2.2.3

# Monitoring
structlog==23.2.0
psutil==5.9.6
```

### Node.js WebSocket Dependencies
```json
{
  "dependencies": {
    "express": "^4.18.2",
    "socket.io": "^4.7.2",
    "redis": "^4.6.8",
    "winston": "^3.11.0",
    "cors": "^2.8.5",
    "helmet": "^7.0.0",
    "jsonwebtoken": "^9.0.2",
    "uuid": "^9.0.0",
    "dotenv": "^16.3.1"
  }
}
```

## Docker Configuration Analysis

### Current Docker Setup
The application uses a multi-container Docker Compose setup with:
- **app**: Main FastAPI application (Dockerfile.production)
- **websocket**: Node.js WebSocket server (Dockerfile.websocket)
- **nginx**: Reverse proxy and load balancer
- **mongo**: Primary database (Note: Should be PostgreSQL)
- **redis**: Cache and session storage
- **prometheus**: Monitoring (optional)
- **grafana**: Metrics visualization (optional)

### Docker Configuration Issues & Improvements

#### Issue 1: Database Mismatch
**Problem**: docker-compose.yml uses MongoDB, but Python code uses PostgreSQL
**Solution**: Update docker-compose.yml to use PostgreSQL

#### Issue 2: Security Hardening
**Problem**: Containers may run as root
**Solution**: Implement non-root user in all Dockerfiles

#### Issue 3: Resource Limits
**Problem**: No memory/CPU limits defined
**Solution**: Add resource constraints

### Improved Docker Compose Configuration
```yaml
version: '3.8'

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile.production
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.5'
        reservations:
          memory: 1G
          cpus: '0.5'
    restart: unless-stopped
    environment:
      - NODE_ENV=production
      - DATABASE_URL=postgresql://annotation:${POSTGRES_PASSWORD}@postgres:5432/annotation_db
    depends_on:
      - postgres
      - redis
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  postgres:
    image: postgres:15-alpine
    deploy:
      resources:
        limits:
          memory: 3G
          cpus: '1'
    environment:
      - POSTGRES_DB=annotation_db
      - POSTGRES_USER=annotation
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U annotation"]
      interval: 10s
      timeout: 5s
      retries: 5
```

## Environment Configuration

### Production Environment Variables
```bash
# Application
NODE_ENV=production
DEBUG=false
LOG_LEVEL=info

# Database
DATABASE_URL=postgresql://annotation:${POSTGRES_PASSWORD}@postgres:5432/annotation_db
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}

# Security
SECRET_KEY=${SECRET_KEY}
JWT_SECRET=${JWT_SECRET}
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Redis
REDIS_URL=redis://redis:6379
REDIS_PASSWORD=${REDIS_PASSWORD}

# File Upload
MAX_FILE_SIZE=10485760  # 10MB
UPLOAD_DIR=/app/uploads
EXPORT_DIR=/app/exports

# CORS
ALLOWED_ORIGINS=https://your-domain.com

# WebSocket
WEBSOCKET_PORT=8001
CORS_ORIGIN=https://your-domain.com

# SSL/TLS
SSL_ENABLED=true
DOMAIN=your-domain.com
```

### Secrets Management
- Use Docker Secrets or external secret management (AWS Secrets Manager, Azure Key Vault)
- Never store secrets in environment files committed to version control
- Rotate secrets regularly (30-90 days)
- Use strong, randomly generated passwords (32+ characters)

## Database Configuration

### PostgreSQL Production Settings
```sql
# postgresql.conf optimizations
shared_buffers = 2GB                    # 25% of RAM
effective_cache_size = 6GB              # 75% of RAM
work_mem = 64MB
maintenance_work_mem = 512MB
max_connections = 200
wal_buffers = 64MB
checkpoint_segments = 64
checkpoint_completion_target = 0.9
```

### Database Backup Strategy
- **Automated Daily Backups**: pg_dump with compression
- **Point-in-Time Recovery**: WAL archiving enabled
- **Backup Retention**: 30 days daily, 12 months monthly
- **Test Restores**: Monthly backup restoration tests

## Performance Optimization

### Backend Optimizations
- **Connection Pooling**: SQLAlchemy pool_size=20, max_overflow=10
- **Query Optimization**: Database indexing on annotation queries
- **Caching Strategy**: Redis for frequently accessed data
- **Async Processing**: FastAPI async endpoints for I/O operations

### WebSocket Optimizations
- **Connection Management**: Automatic reconnection handling
- **Message Compression**: Socket.IO compression enabled
- **Room Management**: Efficient room joining/leaving
- **Redis Adapter**: Multi-instance scaling support

### Frontend Optimizations
- **CDN**: Static asset delivery via CDN
- **Compression**: Gzip/Brotli compression enabled
- **Caching**: Browser caching with appropriate headers
- **Bundle Optimization**: Code splitting and lazy loading

## Monitoring Requirements

### Application Metrics
- **Response Times**: API endpoint performance
- **Error Rates**: 4xx/5xx error tracking
- **Throughput**: Requests per second
- **WebSocket Connections**: Active connections and message rates

### System Metrics
- **CPU Usage**: Per-container CPU utilization
- **Memory Usage**: RAM usage and memory leaks
- **Disk I/O**: Database and file system performance
- **Network I/O**: Bandwidth utilization

### Business Metrics
- **Active Users**: Concurrent and daily active users
- **Annotation Activity**: Creation/update rates
- **File Processing**: Upload success rates
- **Export Usage**: Export format popularity

## Security Requirements

### Network Security
- **HTTPS Only**: TLS 1.2+ with strong cipher suites
- **CORS Configuration**: Restrictive cross-origin policies
- **Rate Limiting**: API rate limiting per user/IP
- **Firewall Rules**: Restrict unnecessary port access

### Application Security
- **Input Validation**: Comprehensive data validation
- **SQL Injection Protection**: Parameterized queries
- **XSS Protection**: Content Security Policy headers
- **Authentication**: JWT tokens with secure configuration
- **File Upload Security**: File type validation and scanning

### Data Security
- **Encryption at Rest**: Database and file storage encryption
- **Encryption in Transit**: HTTPS and WSS protocols
- **Access Controls**: Role-based access control (RBAC)
- **Audit Logging**: Comprehensive security event logging

## Deployment Strategies

### Blue-Green Deployment
- **Zero Downtime**: Seamless production updates
- **Quick Rollback**: Immediate rollback capability
- **Database Migrations**: Backward-compatible schema changes
- **Health Checks**: Comprehensive pre-switch validation

### Rolling Updates
- **Gradual Deployment**: Progressive container updates
- **Load Balancing**: Traffic distribution during updates
- **Monitoring**: Real-time health monitoring
- **Automatic Rollback**: Failure detection and rollback

### Canary Deployment
- **Traffic Splitting**: Gradual traffic routing to new version
- **A/B Testing**: Feature flag based deployment
- **Risk Mitigation**: Limited blast radius
- **Metrics Comparison**: Performance comparison between versions

## Disaster Recovery

### Backup Strategy
- **Database Backups**: Automated daily PostgreSQL backups
- **File Storage Backups**: User uploads and exports
- **Configuration Backups**: Environment and deployment configs
- **Code Repository**: Git-based version control

### Recovery Procedures
- **RTO (Recovery Time Objective)**: 4 hours maximum
- **RPO (Recovery Point Objective)**: 1 hour maximum data loss
- **Failover Process**: Documented step-by-step procedures
- **Testing Schedule**: Quarterly disaster recovery drills

### High Availability
- **Multi-Region Deployment**: Geographic redundancy
- **Load Balancing**: Multiple backend instances
- **Database Replication**: PostgreSQL streaming replication
- **Health Monitoring**: Automated failover detection

This deployment requirements document provides comprehensive guidance for successfully deploying and managing the Academic Annotation Platform in production environments.