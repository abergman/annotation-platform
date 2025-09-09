"""
Text Annotation System - Main Application Entry Point

A FastAPI-based text annotation system for academic research workflows.
Supports multi-user annotation, label management, and data export.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from src.core.database import engine, get_db
from src.models import Base
from src.api.auth import router as auth_router
from src.api.projects import router as projects_router
from src.api.texts import router as texts_router
from src.api.annotations import router as annotations_router
from src.api.labels import router as labels_router
from src.api.export import router as export_router
from src.api.batch import router as batch_router
from src.api.websocket_batch import router as websocket_batch_router
from src.api.monitoring import router as monitoring_router
from src.api.admin import router as admin_router
from src.api.cache import router as cache_router
from src.core.config import settings
from src.utils.logger import setup_logging, get_logger
from src.utils.monitoring import start_background_monitoring
from src.utils.database_logger import setup_sqlalchemy_logging
from src.middleware.logging_middleware import LoggingMiddleware
from src.core.cache_init import init_cache_system, shutdown_cache_system, cache_health_check


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    print("🚀 Starting Text Annotation System...")
    
    # Setup comprehensive logging
    setup_logging(log_level="INFO", log_dir="logs")
    logger = get_logger('main')
    logger.info("Logging system initialized")
    
    # Setup database query logging
    setup_sqlalchemy_logging(engine)
    logger.info("Database query logging enabled")
    
    # Create database tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")
    
    # Start background monitoring
    await start_background_monitoring()
    logger.info("Background monitoring started")
    
    # Initialize cache system
    cache_success = await init_cache_system(warm_cache=True)
    if cache_success:
        logger.info("Cache system initialized successfully")
    else:
        logger.warning("Cache system initialization failed - continuing without caching")
    
    # Initialize batch processing components
    try:
        from src.utils.progress_tracker import ProgressTracker
        from src.utils.batch_processor import BatchProcessor
        
        # Initialize global instances
        progress_tracker = ProgressTracker()
        batch_processor = BatchProcessor()
        
        logger.info("Batch processing system initialized")
    except Exception as e:
        logger.warning(f"Batch processing initialization failed: {str(e)}")
    
    yield
    
    # Shutdown
    logger.info("Cleaning up batch operations, monitoring, and cache")
    try:
        # Shutdown cache system
        await shutdown_cache_system()
        logger.info("Cache system shut down")
        
        # Cleanup old operations and metrics
        progress_tracker.cleanup_completed_operations(max_age_hours=1)
        batch_processor.cleanup_old_metrics(max_age_hours=1)
        
        # Cleanup monitoring data
        from src.utils.monitoring import get_metrics_collector
        metrics_collector = get_metrics_collector()
        metrics_collector.cleanup_old_metrics(hours=24)
        
        logger.info("Batch operations and monitoring cleaned up")
    except Exception as e:
        logger.warning(f"Batch/monitoring cleanup failed: {str(e)}")
    
    logger.info("Shutting down Text Annotation System")


# Initialize FastAPI application
app = FastAPI(
    title="Text Annotation System",
    description="Academic text annotation platform with multi-user support",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan
)

# Add comprehensive logging middleware
app.add_middleware(
    LoggingMiddleware,
    config={
        "log_request_body": True,
        "log_response_body": False,
        "max_body_size": 10000,
        "exclude_paths": {"/health", "/api/monitoring/health"},
        "slow_request_threshold": 5000,
        "very_slow_threshold": 10000
    }
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# API routes
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(projects_router, prefix="/api/projects", tags=["Projects"])
app.include_router(texts_router, prefix="/api/texts", tags=["Texts"])
app.include_router(annotations_router, prefix="/api/annotations", tags=["Annotations"])
app.include_router(labels_router, prefix="/api/labels", tags=["Labels"])
app.include_router(export_router, prefix="/api/export", tags=["Export"])
app.include_router(batch_router, tags=["Batch Operations"])
app.include_router(websocket_batch_router, tags=["WebSocket Batch Updates"])
app.include_router(monitoring_router, tags=["Monitoring & Health"])
app.include_router(admin_router, prefix="/api/admin", tags=["Administration"])
app.include_router(cache_router, tags=["Cache Management"])


@app.get("/")
async def root():
    """Root endpoint with comprehensive API information."""
    return {
        "message": "Text Annotation System API",
        "description": "Academic text annotation platform with advanced batch processing",
        "version": "1.0.0",
        "features": [
            "Multi-user annotation",
            "Batch operations with progress tracking",
            "Real-time WebSocket updates",
            "Multiple export formats",
            "Validation and quality control",
            "Performance optimization"
        ],
        "endpoints": {
            "api_docs": "/api/docs",
            "redoc": "/api/redoc",
            "health": "/health",
            "batch_operations": "/api/v1/batch",
            "websocket_batch": "/api/v1/batch/ws/connect"
        },
        "batch_features": {
            "bulk_create": "Create thousands of annotations efficiently",
            "bulk_update": "Update multiple annotations simultaneously",
            "bulk_delete": "Delete annotations in batch",
            "import_formats": ["CSV", "JSON", "JSONL", "XML", "COCO", "YOLO"],
            "export_formats": ["CSV", "JSON", "JSONL", "XML", "COCO", "YOLO", "CoNLL"],
            "real_time_progress": "WebSocket-based progress updates",
            "validation": "Comprehensive data validation",
            "rollback": "Error rollback capability"
        }
    }


@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint with comprehensive system status."""
    health_status = {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": None,
        "components": {}
    }
    
    from datetime import datetime
    health_status["timestamp"] = datetime.utcnow().isoformat()
    
    # Database connectivity test
    try:
        db.execute("SELECT 1")
        health_status["components"]["database"] = {
            "status": "healthy",
            "message": "Database connection successful"
        }
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["components"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Batch processing system health
    try:
        from src.utils.progress_tracker import ProgressTracker
        from src.utils.batch_processor import BatchProcessor
        
        progress_tracker = ProgressTracker()
        batch_processor = BatchProcessor()
        
        active_operations = progress_tracker.get_active_operations()
        health_status["components"]["batch_processing"] = {
            "status": "healthy",
            "active_operations": len(active_operations),
            "message": "Batch processing system operational"
        }
    except Exception as e:
        health_status["components"]["batch_processing"] = {
            "status": "degraded",
            "error": str(e)
        }
    
    # WebSocket connections health
    try:
        from src.api.websocket_batch import manager
        
        stats = manager.get_connection_stats()
        health_status["components"]["websockets"] = {
            "status": "healthy",
            "active_connections": stats["total_connections"],
            "connected_users": stats["users_connected"],
            "message": "WebSocket system operational"
        }
    except Exception as e:
        health_status["components"]["websockets"] = {
            "status": "degraded",
            "error": str(e)
        }
    
    # Cache system health
    try:
        cache_health = await cache_health_check()
        health_status["components"]["cache"] = {
            "status": cache_health.get("status", "unknown"),
            "message": cache_health.get("message", "Cache health check completed"),
            "metrics": cache_health.get("metrics", {})
        }
        
        if cache_health.get("status") == "unhealthy":
            health_status["status"] = "degraded"
            
    except Exception as e:
        health_status["components"]["cache"] = {
            "status": "degraded",
            "error": str(e)
        }
    
    return health_status


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )