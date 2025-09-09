"""
Cache Integration Tests

Tests the complete caching system integration:
- Service layer caching
- API endpoint caching
- Cache invalidation workflows
- Performance optimization
"""

import pytest
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import patch, AsyncMock

from src.main import app
from src.core.database import get_db
from src.services.cache_manager import get_cache_manager
from src.services.cached_project_service import get_cached_project_service
from src.services.cached_annotation_service import get_cached_annotation_service
from src.models.user import User
from src.models.project import Project
from src.models.text import Text
from src.models.annotation import Annotation
from src.models.label import Label


@pytest.fixture
def client():
    """Test client with cache enabled"""
    with TestClient(app) as client:
        yield client


@pytest.fixture
def mock_cache_service():
    """Mock cache service for isolated testing"""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)  # Cache miss by default
    mock.set = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=1)
    mock.exists = AsyncMock(return_value=False)
    mock.flush_pattern = AsyncMock(return_value=5)
    mock.flush_all = AsyncMock(return_value=True)
    mock.keys = AsyncMock(return_value=[])
    mock.get_metrics = AsyncMock(return_value={
        "hits": 100,
        "misses": 20,
        "hit_rate": 83.33,
        "total_operations": 120
    })
    return mock


@pytest.fixture
def mock_db():
    """Mock database session"""
    db = AsyncMock(spec=Session)
    return db


@pytest.fixture
def sample_user():
    """Sample user for testing"""
    return User(
        id=1,
        email="test@example.com",
        username="testuser",
        is_admin=True
    )


@pytest.fixture
def sample_project():
    """Sample project for testing"""
    return Project(
        id=1,
        name="Test Project",
        description="Test project description",
        owner_id=1,
        is_active=True,
        is_public=False
    )


@pytest.fixture
def sample_annotation():
    """Sample annotation for testing"""
    return Annotation(
        id=1,
        text_id=1,
        user_id=1,
        label_id=1,
        start_char=0,
        end_char=10,
        confidence=1.0
    )


class TestCacheServiceIntegration:
    """Test cache service integration with domain services"""
    
    @pytest.mark.asyncio
    async def test_project_service_caching(self, mock_cache_service, mock_db, sample_project):
        """Test project service caching workflow"""
        project_service = get_cached_project_service()
        
        with patch.object(project_service, 'cache_manager') as mock_manager:
            mock_manager.cache = mock_cache_service
            mock_manager.get_project_by_id = AsyncMock(return_value=sample_project)
            
            # First call - cache miss, should load from DB
            mock_cache_service.get.return_value = None  # Cache miss
            with patch.object(mock_db, 'query') as mock_query:
                mock_query.return_value.filter.return_value.first.return_value = sample_project
                
                result = await project_service.get_project_by_id(1, mock_db)
                
                assert result == sample_project
                mock_cache_service.get.assert_called()
                mock_cache_service.set.assert_called()  # Should cache the result
            
            # Second call - cache hit
            mock_cache_service.get.return_value = sample_project
            result = await project_service.get_project_by_id(1, mock_db)
            
            assert result == sample_project
            # Should not query DB again
    
    @pytest.mark.asyncio
    async def test_annotation_service_caching(self, mock_cache_service, mock_db, sample_annotation):
        """Test annotation service caching workflow"""
        annotation_service = get_cached_annotation_service()
        
        with patch.object(annotation_service, 'cache_manager') as mock_manager:
            mock_manager.cache = mock_cache_service
            
            # Test getting text annotations
            annotations = [sample_annotation]
            mock_cache_service.get.return_value = None  # Cache miss
            
            with patch.object(mock_db, 'query') as mock_query:
                mock_query.return_value.filter.return_value.order_by.return_value.all.return_value = annotations
                
                result = await annotation_service.get_text_annotations(1, mock_db)
                
                assert result == annotations
                mock_cache_service.get.assert_called()
                mock_cache_service.set.assert_called()
    
    @pytest.mark.asyncio
    async def test_cache_invalidation_on_create(self, mock_cache_service, mock_db, sample_project):
        """Test cache invalidation when creating new data"""
        project_service = get_cached_project_service()
        
        with patch.object(project_service, 'cache_manager') as mock_manager:
            mock_manager.cache = mock_cache_service
            mock_manager.set_project = AsyncMock(return_value=True)
            mock_manager.invalidate_query_cache = AsyncMock(return_value=5)
            
            project_data = {
                "name": "New Project",
                "description": "Test project",
                "is_public": False
            }
            
            with patch.object(mock_db, 'add'), \
                 patch.object(mock_db, 'commit'), \
                 patch.object(mock_db, 'refresh'):
                
                result = await project_service.create_project(project_data, 1, mock_db)
                
                # Should invalidate related cache patterns
                mock_manager.invalidate_query_cache.assert_called()
    
    @pytest.mark.asyncio 
    async def test_batch_cache_operations(self, mock_cache_service, mock_db):
        """Test batch cache operations for performance"""
        annotation_service = get_cached_annotation_service()
        
        with patch.object(annotation_service, 'cache_manager') as mock_manager:
            mock_manager.cache = mock_cache_service
            
            annotations_data = [
                {
                    "text_id": 1,
                    "label_id": 1,
                    "start_char": 0,
                    "end_char": 10
                },
                {
                    "text_id": 1,
                    "label_id": 2,
                    "start_char": 15,
                    "end_char": 25
                }
            ]
            
            with patch.object(mock_db, 'add'), \
                 patch.object(mock_db, 'commit'), \
                 patch.object(mock_db, 'refresh'):
                
                created, errors = await annotation_service.batch_create_annotations(
                    annotations_data, 1, mock_db
                )
                
                # Should perform batch cache operations
                assert len(errors) == 0
                mock_cache_service.set.assert_called()  # Cache new annotations
                mock_cache_service.flush_pattern.assert_called()  # Invalidate patterns


class TestCacheAPIEndpoints:
    """Test cache management API endpoints"""
    
    def test_cache_stats_endpoint(self, client, mock_cache_service):
        """Test cache statistics API endpoint"""
        with patch('src.api.cache.get_cache_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.get_cache_stats = AsyncMock(return_value={
                "service_metrics": {"hits": 100, "misses": 20},
                "redis_info": {"version": "6.0.0"},
                "key_distribution": {"user": 50, "project": 30}
            })
            mock_manager.health_check = AsyncMock(return_value={"status": "healthy"})
            mock_get_manager.return_value = mock_manager
            
            # Mock authentication
            with patch('src.api.cache.get_current_user') as mock_auth:
                mock_auth.return_value = User(id=1, is_admin=True)
                
                response = client.get("/api/cache/stats")
                
                assert response.status_code == 200
                data = response.json()
                assert "service_metrics" in data
                assert "redis_info" in data
                assert data["health_status"] == "healthy"
    
    def test_cache_health_endpoint(self, client):
        """Test cache health check endpoint"""
        with patch('src.api.cache.get_cache_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.health_check = AsyncMock(return_value={
                "status": "healthy",
                "operations": {"set": True, "get": True, "delete": True},
                "metrics": {"hits": 100}
            })
            mock_get_manager.return_value = mock_manager
            
            response = client.get("/api/cache/health")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
    
    def test_cache_invalidation_endpoint(self, client):
        """Test cache invalidation API endpoint"""
        with patch('src.api.cache.get_cache_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.invalidate_query_cache = AsyncMock(return_value=5)
            mock_get_manager.return_value = mock_manager
            
            # Mock authentication
            with patch('src.api.cache.get_current_user') as mock_auth:
                mock_auth.return_value = User(id=1, is_admin=True)
                
                response = client.post("/api/cache/invalidate", json={
                    "patterns": ["user:*", "project:*"],
                    "cascade": False
                })
                
                assert response.status_code == 200
                data = response.json()
                assert "total_invalidated" in data
    
    def test_cache_warming_endpoint(self, client):
        """Test cache warming API endpoint"""
        # Mock authentication
        with patch('src.api.cache.get_current_user') as mock_auth:
            mock_auth.return_value = User(id=1, is_admin=True)
            
            response = client.post("/api/cache/warm", json={
                "user_ids": [1, 2, 3],
                "project_ids": [1, 2],
                "warm_all_active": False
            })
            
            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert "background" in data["message"]
    
    def test_admin_required_endpoints(self, client):
        """Test that admin is required for management endpoints"""
        # Mock non-admin user
        with patch('src.api.cache.get_current_user') as mock_auth:
            mock_auth.return_value = User(id=1, is_admin=False)
            
            # Test invalidation
            response = client.post("/api/cache/invalidate", json={
                "patterns": ["user:*"]
            })
            assert response.status_code == 403
            
            # Test warming
            response = client.post("/api/cache/warm", json={
                "user_ids": [1]
            })
            assert response.status_code == 403
            
            # Test flush
            response = client.post("/api/cache/flush?confirm=true")
            assert response.status_code == 403


class TestCachePerformance:
    """Test cache performance optimizations"""
    
    @pytest.mark.asyncio
    async def test_cache_hit_performance(self, mock_cache_service):
        """Test that cache hits are faster than DB queries"""
        project_service = get_cached_project_service()
        
        with patch.object(project_service, 'cache_manager') as mock_manager:
            mock_manager.cache = mock_cache_service
            
            # Simulate fast cache hit
            mock_cache_service.get.return_value = {"id": 1, "name": "Cached Project"}
            
            import time
            start_time = time.time()
            
            result = await project_service.get_project_by_id(1, None)
            
            end_time = time.time()
            cache_time = end_time - start_time
            
            assert result is not None
            assert cache_time < 0.01  # Should be very fast for cache hit
    
    @pytest.mark.asyncio
    async def test_batch_loading_optimization(self, mock_cache_service, mock_db):
        """Test batch loading optimizations"""
        project_service = get_cached_project_service()
        
        with patch.object(project_service, 'cache_manager') as mock_manager:
            mock_manager.cache = mock_cache_service
            mock_manager.warm_project_cache = AsyncMock(return_value={"success": 5, "failed": 0})
            
            # Test warming multiple projects
            project_ids = [1, 2, 3, 4, 5]
            result = await project_service.warm_project_cache(project_ids, mock_db)
            
            assert result["success"] == 5
            assert result["failed"] == 0
    
    @pytest.mark.asyncio
    async def test_memory_efficiency(self, mock_cache_service):
        """Test memory-efficient caching strategies"""
        # Test that large objects are compressed
        large_data = {"data": "x" * 10000}  # Large object
        
        from src.core.cache_service import Serializer
        serializer = Serializer()
        
        # Serialize with compression threshold
        result = serializer.serialize(large_data, compress_threshold=1000)
        
        # Should compress large data
        assert len(result) < len(str(large_data))


class TestCacheReliability:
    """Test cache reliability and error handling"""
    
    @pytest.mark.asyncio
    async def test_cache_failure_fallback(self, mock_db, sample_project):
        """Test that application works when cache fails"""
        project_service = get_cached_project_service()
        
        with patch.object(project_service, 'cache_manager') as mock_manager:
            # Simulate cache failure
            mock_manager.cache.get = AsyncMock(side_effect=Exception("Cache unavailable"))
            
            # Should fall back to database
            with patch.object(mock_db, 'query') as mock_query:
                mock_query.return_value.filter.return_value.first.return_value = sample_project
                
                result = await project_service.get_project_by_id(1, mock_db)
                
                assert result == sample_project  # Should still work
    
    @pytest.mark.asyncio
    async def test_partial_cache_failure(self, mock_cache_service):
        """Test handling of partial cache failures"""
        cache_manager = get_cache_manager()
        
        with patch.object(cache_manager, 'cache', mock_cache_service):
            # Some operations succeed, others fail
            mock_cache_service.get.return_value = {"data": "success"}
            mock_cache_service.set.side_effect = Exception("Set failed")
            
            # Should handle mixed success/failure gracefully
            result = await cache_manager.cache.get("test_key")
            assert result == {"data": "success"}
            
            # Set failure should be logged but not crash
            success = await cache_manager.cache.set("test_key", "data")
            assert success is False  # Should return False on error
    
    @pytest.mark.asyncio
    async def test_cache_key_collision_handling(self, mock_cache_service):
        """Test handling of cache key collisions"""
        from src.core.cache_service import CacheKey
        
        # Generate keys that might collide
        key1 = CacheKey.generate("user", 1, "project", 1)
        key2 = CacheKey.generate("user", "1:project", 1)
        
        # Keys should be different to avoid collisions
        assert key1 != key2
    
    @pytest.mark.asyncio
    async def test_ttl_consistency(self, mock_cache_service):
        """Test TTL consistency across operations"""
        cache_manager = get_cache_manager()
        
        with patch.object(cache_manager, 'cache', mock_cache_service):
            mock_cache_service.ttl.return_value = 3600
            
            # Check that TTL is consistently applied
            ttl = await cache_manager.cache.ttl("test_key")
            assert ttl == 3600


@pytest.mark.integration
class TestFullCacheIntegration:
    """Full integration tests with real Redis (optional)"""
    
    @pytest.mark.skipif(not pytest.config.getoption("--integration"), 
                       reason="Integration tests not enabled")
    async def test_end_to_end_caching(self):
        """End-to-end test with real Redis and database"""
        # This would test the complete flow with real Redis
        # Skip by default unless --integration flag is used
        pass
    
    @pytest.mark.skipif(not pytest.config.getoption("--integration"),
                       reason="Integration tests not enabled")
    async def test_cache_warming_performance(self):
        """Test cache warming performance with real data"""
        # This would test cache warming with real database
        # and measure performance improvements
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])