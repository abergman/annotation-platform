#!/bin/bash

# Configure Digital Ocean App Platform deployment
APP_ID="58c46a38-9d6b-41d8-a54c-e80663ef5226"

# MongoDB connection with actual password
MONGODB_URI="mongodb+srv://doadmin:mr4lxVN7p269W351@annotation-mongodb-e44da03f.mongo.ondigitalocean.com/admin?replicaSet=annotation-mongodb&tls=true&authSource=admin"

# Generated secrets
JWT_SECRET="udp3A+gLnb28DtGAW2c4I+V/mUdiJOMXBZTmssKFOgI="
SESSION_SECRET="pG0DjFMQ7N4pQPT7sDD9MAXbpNCly6jhIp84fQ6NULo="

echo "🚀 Configuring deployment for annotat.ee..."

# Update app spec with environment variables
cat > app-update.yaml << EOF
name: annotation-platform
region: ams3

domains:
  - domain: annotat.ee
    type: PRIMARY

services:
  - name: api
    source_dir: /
    dockerfile_path: Dockerfile.production
    github:
      repo: abergman/annotation-platform
      branch: main
      deploy_on_push: true
    
    instance_count: 1
    instance_size_slug: basic-xxs
    
    envs:
      - key: NODE_ENV
        value: production
      - key: PORT
        value: "8080"
      - key: HOST
        value: "0.0.0.0"
      - key: DOMAIN
        value: annotat.ee
      - key: MONGODB_URI
        value: "$MONGODB_URI"
      - key: JWT_SECRET  
        value: "$JWT_SECRET"
      - key: SESSION_SECRET
        value: "$SESSION_SECRET"
    
    http_port: 8080
    
    routes:
      - path: /
    
    health_check:
      http_path: /health
      initial_delay_seconds: 30
      period_seconds: 10
      timeout_seconds: 5
      success_threshold: 1
      failure_threshold: 3
EOF

# Update the app
doctl apps update $APP_ID --spec app-update.yaml

echo "✅ App configuration updated!"
echo "📊 Checking deployment status..."

# Monitor deployment
doctl apps get $APP_ID

echo ""
echo "🌐 Once deployment completes, your app will be available at:"
echo "   https://annotat.ee"
echo ""
echo "📝 Monitor deployment: doctl apps get $APP_ID"
echo "📋 View logs: doctl apps logs $APP_ID --type deployment"