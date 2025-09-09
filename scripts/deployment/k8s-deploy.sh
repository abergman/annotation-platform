#!/bin/bash

# Kubernetes deployment script for annotation platform
# Usage: ./scripts/deployment/k8s-deploy.sh [environment] [namespace] [image-tag]

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENVIRONMENT=${1:-production}
NAMESPACE=${2:-annotation-prod}
IMAGE_TAG=${3:-latest}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        error "kubectl is not installed"
        exit 1
    fi
    
    # Check cluster connection
    if ! kubectl cluster-info &> /dev/null; then
        error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    
    # Check if namespace exists
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log "Creating namespace: $NAMESPACE"
        kubectl create namespace "$NAMESPACE"
    fi
    
    success "Prerequisites check passed"
}

# Create or update secrets
manage_secrets() {
    log "Managing secrets..."
    
    # Check if secret exists
    if kubectl get secret annotation-secrets -n "$NAMESPACE" &> /dev/null; then
        log "Secrets already exist"
    else
        log "Creating secrets..."
        
        # Generate JWT secret if not provided
        JWT_SECRET=${JWT_SECRET:-$(openssl rand -base64 32)}
        
        kubectl create secret generic annotation-secrets \
            --namespace="$NAMESPACE" \
            --from-literal=database-url="${DATABASE_URL:-}" \
            --from-literal=jwt-secret="$JWT_SECRET" \
            --from-literal=redis-url="${REDIS_URL:-}" \
            --dry-run=client -o yaml | kubectl apply -f -
        
        success "Secrets created"
    fi
}

# Deploy application
deploy_application() {
    log "Deploying application to Kubernetes..."
    
    CONFIG_FILE="$PROJECT_ROOT/config/deployment/$ENVIRONMENT.yml"
    
    if [ ! -f "$CONFIG_FILE" ]; then
        error "Configuration file not found: $CONFIG_FILE"
        exit 1
    fi
    
    # Update image tag in deployment
    sed "s|image: ghcr.io/your-org/annotation-app:latest|image: ghcr.io/your-org/annotation-app:$IMAGE_TAG|g" \
        "$CONFIG_FILE" | kubectl apply -f -
    
    success "Application deployed"
}

# Wait for deployment
wait_for_deployment() {
    log "Waiting for deployment to be ready..."
    
    kubectl rollout status deployment/annotation-app -n "$NAMESPACE" --timeout=300s
    
    success "Deployment is ready"
}

# Verify deployment
verify_deployment() {
    log "Verifying deployment..."
    
    # Check pod status
    kubectl get pods -n "$NAMESPACE" -l app=annotation
    
    # Check service endpoints
    kubectl get svc -n "$NAMESPACE"
    
    # Test health endpoint if available
    POD_NAME=$(kubectl get pods -n "$NAMESPACE" -l app=annotation -o jsonpath='{.items[0].metadata.name}')
    if [ -n "$POD_NAME" ]; then
        log "Testing health endpoint..."
        kubectl exec -n "$NAMESPACE" "$POD_NAME" -- curl -f http://localhost:3000/health || warn "Health check failed"
    fi
    
    success "Deployment verification completed"
}

# Setup monitoring (if Prometheus is available)
setup_monitoring() {
    log "Setting up monitoring..."
    
    # Check if Prometheus operator is available
    if kubectl get crd servicemonitors.monitoring.coreos.com &> /dev/null; then
        cat <<EOF | kubectl apply -f -
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: annotation-monitor
  namespace: $NAMESPACE
  labels:
    app: annotation
spec:
  selector:
    matchLabels:
      app: annotation
  endpoints:
  - port: http
    path: /metrics
    interval: 30s
EOF
        success "Monitoring setup completed"
    else
        warn "Prometheus operator not found, skipping monitoring setup"
    fi
}

# Configure ingress
configure_ingress() {
    log "Configuring ingress..."
    
    # Update domain in ingress if provided
    if [ -n "${DOMAIN:-}" ]; then
        kubectl patch ingress annotation-ingress -n "$NAMESPACE" \
            --type='json' \
            -p="[{'op': 'replace', 'path': '/spec/rules/0/host', 'value': '$DOMAIN'}]"
        
        kubectl patch ingress annotation-ingress -n "$NAMESPACE" \
            --type='json' \
            -p="[{'op': 'replace', 'path': '/spec/tls/0/hosts/0', 'value': '$DOMAIN'}]"
        
        success "Ingress configured for domain: $DOMAIN"
    else
        log "No domain provided, using default configuration"
    fi
}

# Cleanup old resources
cleanup() {
    log "Cleaning up old resources..."
    
    # Clean up completed jobs older than 24 hours
    kubectl delete jobs -n "$NAMESPACE" --field-selector=status.successful=1 \
        --ignore-not-found=true || true
    
    # Clean up old replica sets
    kubectl delete rs -n "$NAMESPACE" \
        --field-selector=status.replicas=0 \
        --ignore-not-found=true || true
    
    success "Cleanup completed"
}

# Main deployment workflow
main() {
    log "Starting Kubernetes deployment..."
    log "Environment: $ENVIRONMENT"
    log "Namespace: $NAMESPACE"
    log "Image Tag: $IMAGE_TAG"
    
    check_prerequisites
    manage_secrets
    deploy_application
    wait_for_deployment
    verify_deployment
    setup_monitoring
    configure_ingress
    cleanup
    
    success "Kubernetes deployment completed successfully!"
    
    # Show useful information
    log "Useful commands:"
    log "  View pods: kubectl get pods -n $NAMESPACE"
    log "  View logs: kubectl logs -f deployment/annotation-app -n $NAMESPACE"
    log "  Port forward: kubectl port-forward svc/annotation-service 8080:80 -n $NAMESPACE"
}

# Handle script interruption
trap 'error "Deployment interrupted"; exit 1' INT TERM

# Show help if requested
if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    echo "Usage: $0 [environment] [namespace] [image-tag]"
    echo "  environment: production, staging, etc."
    echo "  namespace: Kubernetes namespace (default: annotation-prod)"
    echo "  image-tag: Docker image tag to deploy (default: latest)"
    echo
    echo "Environment variables:"
    echo "  DATABASE_URL: Database connection string"
    echo "  JWT_SECRET: JWT signing secret"
    echo "  REDIS_URL: Redis connection string"
    echo "  DOMAIN: Domain name for ingress"
    exit 0
fi

# Run main function
main "$@"