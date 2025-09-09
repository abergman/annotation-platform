"""
Cache Initialization and Startup

Handles cache system initialization, connection setup, and startup tasks:
- Redis connection management
- Cache warming strategies
- Health check integration
- Graceful shutdown
"""

import asyncio
from typing import Optional, Dict, Any
from datetime import datetime

from .cache_config import load_cache_config, CacheConfigManager
from .cache_service import get_cache_service
from ..services.cache_manager import get_cache_manager
from ..utils.logger import get_logger


logger = get_logger(__name__)


class CacheInitializer:
    """Manages cache system initialization and lifecycle"""
    
    def __init__(self):
        self.cache_service = get_cache_service()
        self.cache_manager = get_cache_manager()
        self.initialized = False
        self.startup_time = None
    
    async def initialize(self, warm_cache: bool = True) -> bool:
        """Initialize cache system"""
        try:
            self.startup_time = datetime.now()
            logger.info("Initializing cache system...")
            
            # Load and validate configuration
            config = load_cache_config()
            issues = CacheConfigManager.validate_config(config)
            
            if issues:
                logger.warning("Cache configuration issues detected:")
                for issue in issues:
                    logger.warning(f"  - {issue}")
            
            # Test connection
            success = await self.cache_service.connect()
            if not success:
                logger.error("Failed to connect to Redis")
                return False
            
            # Perform health check
            health = await self.cache_manager.health_check()
            if health["status"] != "healthy":
                logger.error(f"Cache health check failed: {health}")
                return False
            
            logger.info(f"Cache system initialized successfully ({config.mode.value} mode)")
            
            # Warm cache if requested
            if warm_cache:
                await self._perform_startup_cache_warming()
            
            self.initialized = True
            return True
            
        except Exception as e:
            logger.error(f"Cache initialization failed: {str(e)}")
            return False
    
    async def _perform_startup_cache_warming(self):
        """Perform initial cache warming"""
        try:
            logger.info("Starting cache warming...")
            
            # This would typically warm frequently accessed data
            # Implement based on your application's usage patterns
            
            # Example: Warm public projects (most frequently accessed)
            warming_tasks = []
            
            # Add warming tasks here based on your needs
            # warming_tasks.append(self._warm_public_projects())
            # warming_tasks.append(self._warm_active_users())
            # warming_tasks.append(self._warm_recent_annotations())
            
            if warming_tasks:
                await asyncio.gather(*warming_tasks, return_exceptions=True)
                logger.info("Cache warming completed")
            else:
                logger.info("No cache warming tasks configured")
                
        except Exception as e:
            logger.warning(f"Cache warming failed (non-critical): {str(e)}")
    
    async def _warm_public_projects(self):
        """Warm cache for public projects"""
        try:
            # This would load and cache public projects
            # Implementation depends on your database access patterns
            pass
        except Exception as e:
            logger.warning(f"Failed to warm public projects cache: {str(e)}")
    
    async def _warm_active_users(self):
        """Warm cache for active users"""
        try:
            # This would load and cache recently active users
            # Implementation depends on your user activity tracking
            pass
        except Exception as e:
            logger.warning(f"Failed to warm active users cache: {str(e)}")
    
    async def _warm_recent_annotations(self):
        """Warm cache for recent annotations"""
        try:
            # This would load and cache recent annotations
            # Implementation depends on your annotation access patterns
            pass
        except Exception as e:
            logger.warning(f"Failed to warm recent annotations cache: {str(e)}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive cache system health check"""
        if not self.initialized:
            return {
                "status": "not_initialized",
                "message": "Cache system not initialized"
            }
        
        try:
            # Perform health check
            health = await self.cache_manager.health_check()
            
            # Add initialization info
            uptime = (datetime.now() - self.startup_time).total_seconds() if self.startup_time else 0
            
            health.update({
                "initialized": self.initialized,
                "startup_time": self.startup_time.isoformat() if self.startup_time else None,
                "uptime_seconds": round(uptime, 2)
            })
            
            return health
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "initialized": self.initialized
            }
    
    async def shutdown(self):
        """Gracefully shutdown cache system"""
        try:
            logger.info("Shutting down cache system...")
            
            # Disconnect from Redis
            await self.cache_service.disconnect()
            
            self.initialized = False
            logger.info("Cache system shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during cache shutdown: {str(e)}")
    
    async def get_system_info(self) -> Dict[str, Any]:
        """Get comprehensive system information"""
        try:
            info = {
                "initialized": self.initialized,
                "startup_time": self.startup_time.isoformat() if self.startup_time else None
            }
            
            if self.initialized:
                # Get cache stats
                stats = await self.cache_manager.get_cache_stats()
                info.update(stats)
                
                # Get health status
                health = await self.health_check()
                info["health"] = health
            
            return info
            
        except Exception as e:
            return {
                "initialized": self.initialized,
                "error": str(e)
            }


# Global initializer instance
_cache_initializer: Optional[CacheInitializer] = None


def get_cache_initializer() -> CacheInitializer:
    """Get global cache initializer instance"""
    global _cache_initializer
    if _cache_initializer is None:
        _cache_initializer = CacheInitializer()
    return _cache_initializer


# Convenience functions for FastAPI integration

async def init_cache_system(warm_cache: bool = True) -> bool:
    """Initialize cache system (for use in FastAPI lifespan)"""
    initializer = get_cache_initializer()
    return await initializer.initialize(warm_cache=warm_cache)


async def shutdown_cache_system():
    """Shutdown cache system (for use in FastAPI lifespan)"""
    initializer = get_cache_initializer()
    await initializer.shutdown()


async def cache_health_check() -> Dict[str, Any]:
    """Cache health check (for use in health endpoints)"""
    initializer = get_cache_initializer()
    return await initializer.health_check()


async def get_cache_system_info() -> Dict[str, Any]:
    """Get cache system info (for use in admin endpoints)"""
    initializer = get_cache_initializer()
    return await initializer.get_system_info()


# Environment-specific initialization

async def init_cache_for_development():
    """Initialize cache for development environment"""
    logger.info("Initializing cache for development environment")
    
    # Use lighter cache warming for development
    success = await init_cache_system(warm_cache=False)
    
    if success:
        logger.info("Development cache initialization complete")
    else:
        logger.warning("Development cache initialization failed - continuing without cache")
    
    return success


async def init_cache_for_production():
    """Initialize cache for production environment"""
    logger.info("Initializing cache for production environment")
    
    # Use full cache warming for production
    success = await init_cache_system(warm_cache=True)
    
    if not success:
        logger.error("Production cache initialization failed - this may impact performance")
        # In production, you might want to raise an exception here
        # raise RuntimeError("Cache initialization failed")
    else:
        logger.info("Production cache initialization complete")
    
    return success


async def init_cache_for_testing():
    """Initialize cache for testing environment"""
    logger.info("Initializing cache for testing environment")
    
    # Use minimal cache setup for testing
    success = await init_cache_system(warm_cache=False)
    
    if success:
        # Clear any existing data in test cache
        cache_manager = get_cache_manager()
        await cache_manager.cache.flush_all()
        logger.info("Testing cache initialization complete")
    else:
        logger.warning("Testing cache initialization failed - tests may run slower")
    
    return success