"""
Cache Management API Endpoints

Provides administrative endpoints for cache management:
- Cache statistics and monitoring
- Cache invalidation and warming
- Configuration management
- Performance metrics
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from ..core.database import get_db
from ..services.cache_manager import get_cache_manager
from ..utils.cache_decorators import CacheWarmer
from ..utils.auth import get_current_user
from ..utils.logger import get_logger
from ..models.user import User


logger = get_logger(__name__)
router = APIRouter(prefix="/api/cache", tags=["Cache Management"])
security = HTTPBearer()


class CacheStatsResponse(BaseModel):
    """Cache statistics response model"""
    service_metrics: Dict[str, Any]
    redis_info: Dict[str, Any]
    key_distribution: Dict[str, int]
    health_status: str
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class CacheInvalidationRequest(BaseModel):
    """Cache invalidation request model"""
    patterns: List[str] = Field(..., description="Cache key patterns to invalidate")
    cascade: bool = Field(default=False, description="Whether to cascade invalidation")


class CacheWarmingRequest(BaseModel):
    """Cache warming request model"""
    user_ids: Optional[List[int]] = Field(None, description="User IDs to warm")
    project_ids: Optional[List[int]] = Field(None, description="Project IDs to warm")
    text_ids: Optional[List[int]] = Field(None, description="Text IDs for annotation warming")
    warm_all_active: bool = Field(default=False, description="Warm all active entities")


class CacheConfigUpdate(BaseModel):
    """Cache configuration update model"""
    default_ttl: Optional[int] = Field(None, ge=60, le=86400, description="Default TTL in seconds")
    max_ttl: Optional[int] = Field(None, ge=300, le=604800, description="Maximum TTL in seconds")
    compression_threshold: Optional[int] = Field(None, ge=100, description="Compression threshold in bytes")


@router.get("/stats", response_model=CacheStatsResponse)
async def get_cache_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get comprehensive cache statistics and health information"""
    try:
        cache_manager = get_cache_manager()
        
        # Get basic stats
        stats = await cache_manager.get_cache_stats()
        
        # Get health status
        health = await cache_manager.health_check()
        
        return CacheStatsResponse(
            service_metrics=stats["service_metrics"],
            redis_info=stats["redis_info"],
            key_distribution=stats["key_distribution"],
            health_status=health["status"]
        )
        
    except Exception as e:
        logger.error(f"Error getting cache stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get cache stats: {str(e)}")


@router.get("/health")
async def cache_health_check():
    """Quick cache health check endpoint"""
    try:
        cache_manager = get_cache_manager()
        health = await cache_manager.health_check()
        
        if health["status"] == "healthy":
            return {
                "status": "healthy",
                "message": "Cache is operational",
                "metrics": health["metrics"]
            }
        else:
            raise HTTPException(
                status_code=503,
                detail={
                    "status": "unhealthy",
                    "error": health.get("error", "Unknown error"),
                    "operations": health.get("operations", {})
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cache health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Cache health check failed: {str(e)}")


@router.post("/invalidate")
async def invalidate_cache(
    request: CacheInvalidationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Invalidate cache entries by patterns"""
    # Only admin users can invalidate cache
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        cache_manager = get_cache_manager()
        
        total_invalidated = 0
        results = {}
        
        for pattern in request.patterns:
            count = await cache_manager.invalidate_query_cache(pattern)
            results[pattern] = count
            total_invalidated += count
            
            logger.info(f"User {current_user.id} invalidated {count} cache entries for pattern: {pattern}")
        
        # Log the invalidation for audit
        background_tasks.add_task(
            _log_cache_operation,
            "invalidate",
            current_user.id,
            {"patterns": request.patterns, "total_invalidated": total_invalidated}
        )
        
        return {
            "message": f"Invalidated {total_invalidated} cache entries",
            "details": results,
            "total_invalidated": total_invalidated
        }
        
    except Exception as e:
        logger.error(f"Cache invalidation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Cache invalidation failed: {str(e)}")


@router.post("/warm")
async def warm_cache(
    request: CacheWarmingRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Warm cache with specified data"""
    # Only admin users can warm cache
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        # Execute cache warming in background
        background_tasks.add_task(
            _execute_cache_warming,
            request,
            current_user.id,
            db
        )
        
        return {
            "message": "Cache warming initiated in background",
            "request": request.dict()
        }
        
    except Exception as e:
        logger.error(f"Cache warming error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Cache warming failed: {str(e)}")


@router.post("/flush")
async def flush_cache(
    pattern: str = Query(default="*", description="Pattern to flush (default: all)"),
    confirm: bool = Query(default=False, description="Confirmation required for flush"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Flush cache entries by pattern"""
    # Only admin users can flush cache
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if not confirm:
        raise HTTPException(status_code=400, detail="Confirmation required (set confirm=true)")
    
    try:
        cache_manager = get_cache_manager()
        
        if pattern == "*":
            # Flush all
            success = await cache_manager.cache.flush_all()
            count = "all" if success else 0
        else:
            # Flush by pattern
            count = await cache_manager.cache.flush_pattern(pattern)
        
        logger.warning(f"User {current_user.id} flushed cache with pattern: {pattern} (count: {count})")
        
        return {
            "message": f"Flushed cache entries for pattern: {pattern}",
            "pattern": pattern,
            "count": count
        }
        
    except Exception as e:
        logger.error(f"Cache flush error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Cache flush failed: {str(e)}")


@router.get("/keys")
async def get_cache_keys(
    pattern: str = Query(default="*", description="Pattern to match"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum keys to return"),
    current_user: User = Depends(get_current_user)
):
    """Get cache keys matching pattern"""
    # Only admin users can view cache keys
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        cache_manager = get_cache_manager()
        
        keys = await cache_manager.cache.keys(pattern)
        
        # Limit results
        if len(keys) > limit:
            keys = keys[:limit]
            truncated = True
        else:
            truncated = False
        
        # Get additional info for each key
        key_info = []
        for key in keys:
            ttl = await cache_manager.cache.ttl(key)
            key_info.append({
                "key": key,
                "ttl": ttl,
                "exists": ttl > -2
            })
        
        return {
            "pattern": pattern,
            "total_found": len(keys),
            "truncated": truncated,
            "keys": key_info
        }
        
    except Exception as e:
        logger.error(f"Cache keys error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get cache keys: {str(e)}")


@router.get("/metrics/detailed")
async def get_detailed_metrics(
    current_user: User = Depends(get_current_user)
):
    """Get detailed cache metrics and performance data"""
    # Only admin users can view detailed metrics
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        cache_manager = get_cache_manager()
        
        # Get service metrics
        service_metrics = cache_manager.cache.get_metrics()
        
        # Get Redis info
        redis_info = await cache_manager.cache.get_info()
        
        # Get key distribution
        key_distribution = await cache_manager._get_key_distribution()
        
        # Calculate additional metrics
        memory_info = {
            "used_memory": redis_info.get("used_memory", 0),
            "used_memory_human": redis_info.get("used_memory_human", "0B"),
            "used_memory_peak": redis_info.get("used_memory_peak", 0),
            "used_memory_peak_human": redis_info.get("used_memory_peak_human", "0B"),
            "memory_fragmentation_ratio": redis_info.get("mem_fragmentation_ratio", 0)
        }
        
        performance_info = {
            "total_operations": service_metrics.get("total_operations", 0),
            "hit_rate": service_metrics.get("hit_rate", 0),
            "miss_rate": service_metrics.get("miss_rate", 0),
            "avg_response_time_ms": service_metrics.get("avg_response_time", 0),
            "uptime_seconds": service_metrics.get("uptime_seconds", 0)
        }
        
        return {
            "service_metrics": service_metrics,
            "memory_info": memory_info,
            "performance_info": performance_info,
            "key_distribution": key_distribution,
            "redis_version": redis_info.get("redis_version", "unknown"),
            "connected_clients": redis_info.get("connected_clients", 0),
            "keyspace": {k: v for k, v in redis_info.items() if k.startswith("db")}
        }
        
    except Exception as e:
        logger.error(f"Detailed metrics error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get detailed metrics: {str(e)}")


@router.post("/reset-metrics")
async def reset_metrics(
    current_user: User = Depends(get_current_user)
):
    """Reset cache performance metrics"""
    # Only admin users can reset metrics
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        cache_manager = get_cache_manager()
        cache_manager.cache.reset_metrics()
        
        logger.info(f"User {current_user.id} reset cache metrics")
        
        return {"message": "Cache metrics reset successfully"}
        
    except Exception as e:
        logger.error(f"Reset metrics error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to reset metrics: {str(e)}")


# Background task functions

async def _execute_cache_warming(request: CacheWarmingRequest, user_id: int, db: Session):
    """Execute cache warming in background"""
    try:
        warmer = CacheWarmer()
        results = {}
        
        if request.user_ids:
            results["users"] = await warmer.warm_user_caches(request.user_ids, db)
            
        if request.project_ids:
            results["projects"] = await warmer.warm_project_caches(request.project_ids, db)
            
        if request.text_ids:
            results["annotations"] = await warmer.warm_annotation_caches(request.text_ids, db)
        
        if request.warm_all_active:
            # Warm active entities (implement based on your business logic)
            pass
        
        total_warmed = sum(r.get("success", 0) for r in results.values())
        total_failed = sum(r.get("failed", 0) for r in results.values())
        
        logger.info(
            f"Cache warming completed by user {user_id}: "
            f"{total_warmed} successful, {total_failed} failed"
        )
        
        # Log the operation
        await _log_cache_operation(
            "warm",
            user_id,
            {"results": results, "total_warmed": total_warmed, "total_failed": total_failed}
        )
        
    except Exception as e:
        logger.error(f"Background cache warming failed: {str(e)}")


async def _log_cache_operation(operation: str, user_id: int, details: Dict[str, Any]):
    """Log cache operation for audit purposes"""
    try:
        # You could store this in your audit log table
        logger.info(
            f"Cache operation logged",
            extra={
                "operation": operation,
                "user_id": user_id,
                "details": details,
                "timestamp": datetime.now().isoformat()
            }
        )
    except Exception as e:
        logger.warning(f"Failed to log cache operation: {str(e)}")


# Health check for monitoring systems
@router.get("/ping")
async def ping_cache():
    """Simple ping endpoint for monitoring systems"""
    try:
        cache_manager = get_cache_manager()
        
        # Test basic operation
        test_key = f"ping_test_{datetime.now().timestamp()}"
        
        # Test set
        await cache_manager.cache.set(test_key, "pong", ttl=60)
        
        # Test get
        result = await cache_manager.cache.get(test_key)
        
        # Test delete
        await cache_manager.cache.delete(test_key)
        
        if result == "pong":
            return {"status": "ok", "message": "Cache is responding"}
        else:
            raise HTTPException(status_code=503, detail="Cache ping test failed")
            
    except Exception as e:
        logger.error(f"Cache ping failed: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Cache ping failed: {str(e)}")