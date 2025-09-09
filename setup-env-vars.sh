#!/bin/bash

# Digital Ocean App Environment Variables Setup Script
# Run this to configure environment variables for the deployed app

APP_ID="58c46a38-9d6b-41d8-a54c-e80663ef5226"

# MongoDB connection (update with actual password from doctl databases connection command)
MONGODB_URI="mongodb+srv://doadmin:ACTUAL_PASSWORD_HERE@annotation-mongodb-e44da03f.mongo.ondigitalocean.com/admin?tls=true&authSource=admin&replicaSet=annotation-mongodb"

# Generated secrets
JWT_SECRET="udp3A+gLnb28DtGAW2c4I+V/mUdiJOMXBZTmssKFOgI="
SESSION_SECRET="pG0DjFMQ7N4pQPT7sDD9MAXbpNCly6jhIp84fQ6NULo="

echo "Setting up environment variables for app $APP_ID..."

# Set environment variables
doctl apps update-config $APP_ID --set-env "MONGODB_URI=$MONGODB_URI"
doctl apps update-config $APP_ID --set-env "JWT_SECRET=$JWT_SECRET"
doctl apps update-config $APP_ID --set-env "SESSION_SECRET=$SESSION_SECRET"

echo "Environment variables configured!"
echo "Check deployment status: doctl apps get $APP_ID"