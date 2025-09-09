"""
Cache Worker for Digital Ocean App Platform
Handles background cache warming and maintenance tasks
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, Any

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.core.config import settings
from src.core.cache_init import init_cache_system, get_redis_client
from src.core.database import get_db
from src.models.project import Project
from src.models.user import User

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CacheWorker:
    """Background worker for cache maintenance and warming"""
    
    def __init__(self):
        self.redis_client = None
        self.running = True
        
    async def initialize(self):
        """Initialize cache connections"""
        try:
            success = await init_cache_system(warm_cache=False)
            if success:
                self.redis_client = await get_redis_client()
                logger.info("✅ Cache worker initialized successfully")
                return True
            else:
                logger.error("❌ Failed to initialize cache system")
                return False
        except Exception as e:
            logger.error(f"❌ Cache worker initialization error: {e}")
            return False
    
    async def warm_project_cache(self):
        """Warm cache with frequently accessed project data"""
        try:
            if not self.redis_client:
                return
                
            # Get database session
            db = next(get_db())
            
            # Cache active projects
            active_projects = db.query(Project).filter(Project.is_active == True).limit(100).all()
            
            for project in active_projects:
                cache_key = f"project:{project.id}"
                project_data = {
                    "id": project.id,
                    "name": project.name,
                    "description": project.description,
                    "created_at": project.created_at.isoformat() if project.created_at else None,
                    "is_active": project.is_active
                }
                
                await self.redis_client.setex(
                    cache_key,
                    3600,  # 1 hour TTL
                    str(project_data)
                )
            
            logger.info(f"🔥 Warmed cache for {len(active_projects)} projects")
            
        except Exception as e:
            logger.error(f"❌ Error warming project cache: {e}")
    
    async def warm_user_cache(self):
        """Warm cache with user session data"""
        try:
            if not self.redis_client:
                return
                
            # Get database session
            db = next(get_db())
            
            # Cache recent active users
            recent_date = datetime.utcnow() - timedelta(days=7)
            active_users = db.query(User).filter(
                User.last_login >= recent_date
            ).limit(100).all()
            
            for user in active_users:
                cache_key = f"user:{user.id}"
                user_data = {
                    "id": user.id,
                    "email": user.email,
                    "username": user.username,
                    "is_active": user.is_active,
                    "last_login": user.last_login.isoformat() if user.last_login else None
                }
                
                await self.redis_client.setex(
                    cache_key,
                    1800,  # 30 minutes TTL
                    str(user_data)
                )
            
            logger.info(f"🔥 Warmed cache for {len(active_users)} users")
            
        except Exception as e:
            logger.error(f"❌ Error warming user cache: {e}")
    
    async def cleanup_expired_keys(self):
        """Clean up expired or old cache keys"""
        try:
            if not self.redis_client:
                return
                
            # Scan for old batch operation keys
            batch_keys = []
            async for key in self.redis_client.scan_iter(match="batch:*"):
                batch_keys.append(key)
            
            # Remove old batch operations (older than 24 hours)
            cutoff_time = datetime.utcnow() - timedelta(hours=24)
            cutoff_timestamp = int(cutoff_time.timestamp())
            
            removed_count = 0
            for key in batch_keys:
                try:
                    # Check if key has timestamp and is old
                    key_parts = key.decode('utf-8').split(':')
                    if len(key_parts) >= 3 and key_parts[2].isdigit():
                        key_timestamp = int(key_parts[2])
                        if key_timestamp < cutoff_timestamp:
                            await self.redis_client.delete(key)
                            removed_count += 1
                except Exception:
                    # If we can't parse the key, leave it alone
                    continue
            
            if removed_count > 0:
                logger.info(f"🧹 Cleaned up {removed_count} expired batch keys")
                
        except Exception as e:
            logger.error(f"❌ Error cleaning up cache: {e}")
    
    async def update_cache_stats(self):
        """Update cache statistics"""
        try:
            if not self.redis_client:
                return
                
            # Get Redis info
            info = await self.redis_client.info()
            
            stats = {
                "timestamp": datetime.utcnow().isoformat(),
                "used_memory": info.get("used_memory", 0),
                "connected_clients": info.get("connected_clients", 0),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
            }
            
            # Store stats with 24-hour TTL
            await self.redis_client.setex(
                "cache:stats",
                86400,  # 24 hours
                str(stats)
            )
            
            # Calculate hit ratio
            hits = stats["keyspace_hits"]
            misses = stats["keyspace_misses"]
            total = hits + misses
            hit_ratio = (hits / total * 100) if total > 0 else 0
            
            logger.info(f"📊 Cache stats updated - Hit ratio: {hit_ratio:.1f}%")
            
        except Exception as e:
            logger.error(f"❌ Error updating cache stats: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        try:
            if not self.redis_client:
                return {"status": "unhealthy", "error": "No Redis connection"}
                
            # Simple ping test
            await self.redis_client.ping()
            
            return {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "message": "Cache worker is operational"
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def run_maintenance_cycle(self):
        """Run a complete maintenance cycle"""
        logger.info("🔄 Starting cache maintenance cycle")
        
        # Warm caches
        await self.warm_project_cache()
        await self.warm_user_cache()
        
        # Cleanup
        await self.cleanup_expired_keys()
        
        # Update stats
        await self.update_cache_stats()
        
        logger.info("✅ Cache maintenance cycle completed")
    
    async def run(self):
        """Main worker loop"""
        logger.info("🚀 Starting cache worker")
        
        # Initialize
        if not await self.initialize():
            logger.error("❌ Failed to initialize cache worker")
            return
        
        try:
            while self.running:
                # Run maintenance cycle every 5 minutes
                await self.run_maintenance_cycle()
                
                # Sleep for 5 minutes
                await asyncio.sleep(300)
                
        except asyncio.CancelledError:
            logger.info("🛑 Cache worker cancelled")
        except Exception as e:
            logger.error(f"❌ Cache worker error: {e}")
        finally:
            logger.info("🛑 Cache worker stopped")
    
    def stop(self):
        """Stop the worker"""
        self.running = False


async def main():
    """Main entry point"""
    worker = CacheWorker()
    
    try:
        await worker.run()
    except KeyboardInterrupt:
        logger.info("🛑 Received interrupt signal")
        worker.stop()
    except Exception as e:
        logger.error(f"❌ Worker error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())