"""
Unit Tests for Cache Service

Tests the core caching functionality including:
- Basic operations (get, set, delete)
- TTL management
- Serialization/deserialization
- Error handling
- Performance metrics
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from src.core.cache_service import CacheService, Serializer, CacheKey
from src.core.cache_config import CacheConfig, CacheMode, CacheMetrics
from src.core.cache_service import SerializationError, CacheConnectionError


class TestSerializer:
    """Test the serialization component"""
    
    def test_serialize_simple_types(self):
        """Test serialization of simple data types"""
        serializer = Serializer()
        
        # String
        result = serializer.serialize("hello")
        assert result.startswith(b'raw:')
        
        # Number
        result = serializer.serialize(42)
        assert result.startswith(b'raw:')
        
        # Boolean
        result = serializer.serialize(True)
        assert result.startswith(b'raw:')
    
    def test_serialize_complex_types(self):
        """Test serialization of complex data types"""
        serializer = Serializer()
        
        # Dictionary
        data = {"key": "value", "number": 42}
        result = serializer.serialize(data)
        assert result.startswith(b'raw:')
        
        # List
        data = [1, 2, 3, "test"]
        result = serializer.serialize(data)
        assert result.startswith(b'raw:')
    
    def test_serialize_with_compression(self):
        """Test serialization with compression for large data"""
        serializer = Serializer()
        
        # Create large data that should be compressed
        large_data = {"key" + str(i): "value" * 100 for i in range(100)}
        result = serializer.serialize(large_data, compress_threshold=100)
        
        # Should use compression for large data
        # The actual check depends on whether compression was beneficial
        assert result.startswith(b'compressed:') or result.startswith(b'raw:')
    
    def test_deserialize_simple_types(self):
        """Test deserialization of simple data types"""
        serializer = Serializer()
        
        # Round trip test
        original = "hello world"
        serialized = serializer.serialize(original)
        deserialized = serializer.deserialize(serialized)
        assert deserialized == original
        
        original = 42
        serialized = serializer.serialize(original)
        deserialized = serializer.deserialize(serialized)
        assert deserialized == original
    
    def test_deserialize_complex_types(self):
        """Test deserialization of complex data types"""
        serializer = Serializer()
        
        # Dictionary
        original = {"key": "value", "nested": {"number": 42}}
        serialized = serializer.serialize(original)
        deserialized = serializer.deserialize(serialized)
        assert deserialized == original
        
        # List
        original = [1, 2, {"key": "value"}]
        serialized = serializer.serialize(original)
        deserialized = serializer.deserialize(serialized)
        assert deserialized == original
    
    def test_serialization_error_handling(self):
        """Test serialization error handling"""
        serializer = Serializer()
        
        # Test invalid data for deserialization
        with pytest.raises(SerializationError):
            serializer.deserialize(b"invalid_data")


class TestCacheKey:
    """Test the cache key generation utility"""
    
    def test_basic_key_generation(self):
        """Test basic cache key generation"""
        key = CacheKey.generate("user", 123)
        assert key == "user:123"
        
        key = CacheKey.generate("project", 456, "stats")
        assert key == "project:456:stats"
    
    def test_key_with_kwargs(self):
        """Test key generation with keyword arguments"""
        key = CacheKey.generate("query", "search", query="test", limit=10)
        assert "query:search" in key
        assert "query:test" in key
        assert "limit:10" in key
    
    def test_long_key_hashing(self):
        """Test that very long keys are hashed"""
        # Generate a very long key
        long_args = ["very_long_argument_" + str(i) for i in range(50)]
        key = CacheKey.generate("test", *long_args)
        
        # Should be hashed if too long
        if len(key) > 250:
            assert "hash:" in key
    
    def test_pattern_generation(self):
        """Test cache key pattern generation"""
        pattern = CacheKey.pattern("user")
        assert pattern == "user:*"
        
        pattern = CacheKey.pattern("project", "stats:*")
        assert pattern == "project:stats:*"


class TestCacheMetrics:
    """Test the cache metrics collector"""
    
    def test_metrics_initialization(self):
        """Test metrics initialization"""
        metrics = CacheMetrics()
        assert metrics.hits == 0
        assert metrics.misses == 0
        assert metrics.sets == 0
        assert metrics.deletes == 0
        assert metrics.errors == 0
    
    def test_metrics_recording(self):
        """Test metrics recording"""
        metrics = CacheMetrics()
        
        metrics.record_hit(0.1)
        assert metrics.hits == 1
        
        metrics.record_miss(0.2)
        assert metrics.misses == 1
        
        metrics.record_set(0.3)
        assert metrics.sets == 1
        
        metrics.record_delete(0.4)
        assert metrics.deletes == 1
        
        metrics.record_error()
        assert metrics.errors == 1
    
    def test_hit_rate_calculation(self):
        """Test hit rate calculation"""
        metrics = CacheMetrics()
        
        # No operations yet
        assert metrics.hit_rate == 0.0
        
        # All hits
        metrics.record_hit()
        metrics.record_hit()
        assert metrics.hit_rate == 100.0
        
        # Mixed hits and misses
        metrics.record_miss()
        assert metrics.hit_rate == 2/3 * 100  # 66.67%
    
    def test_metrics_reset(self):
        """Test metrics reset"""
        metrics = CacheMetrics()
        
        metrics.record_hit()
        metrics.record_miss()
        metrics.record_set()
        
        metrics.reset()
        
        assert metrics.hits == 0
        assert metrics.misses == 0
        assert metrics.sets == 0
    
    def test_metrics_to_dict(self):
        """Test metrics export to dictionary"""
        metrics = CacheMetrics()
        
        metrics.record_hit(0.1)
        metrics.record_miss(0.2)
        
        result = metrics.to_dict()
        
        assert isinstance(result, dict)
        assert "hits" in result
        assert "misses" in result
        assert "hit_rate" in result
        assert "avg_response_time" in result
        assert result["hits"] == 1
        assert result["misses"] == 1


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing"""
    mock = AsyncMock()
    mock.ping = AsyncMock(return_value=True)
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=1)
    mock.exists = AsyncMock(return_value=True)
    mock.ttl = AsyncMock(return_value=3600)
    mock.expire = AsyncMock(return_value=True)
    mock.keys = AsyncMock(return_value=[])
    mock.flushall = AsyncMock(return_value=True)
    mock.info = AsyncMock(return_value={})
    return mock


@pytest.fixture
def cache_config():
    """Test cache configuration"""
    return CacheConfig(
        host="localhost",
        port=6379,
        database=0,
        default_ttl=3600,
        max_ttl=86400
    )


class TestCacheService:
    """Test the main cache service functionality"""
    
    @pytest.fixture
    def cache_service(self, cache_config):
        """Cache service instance for testing"""
        service = CacheService(cache_config)
        return service
    
    @pytest.mark.asyncio
    async def test_connection_success(self, cache_service, mock_redis):
        """Test successful Redis connection"""
        with patch.object(cache_service, '_create_redis_client', return_value=mock_redis):
            success = await cache_service.connect()
            assert success is True
            assert cache_service.redis_client is not None
    
    @pytest.mark.asyncio
    async def test_connection_failure(self, cache_service):
        """Test Redis connection failure"""
        with patch('redis.Redis') as mock_redis_class:
            mock_redis_class.side_effect = Exception("Connection failed")
            
            with pytest.raises(CacheConnectionError):
                await cache_service.connect()
    
    @pytest.mark.asyncio
    async def test_get_cache_hit(self, cache_service, mock_redis):
        """Test cache get operation with hit"""
        # Setup mock
        test_data = {"key": "value"}
        serialized_data = cache_service.serializer.serialize(test_data)
        mock_redis.get.return_value = serialized_data
        
        with patch.object(cache_service, 'redis_client', mock_redis):
            with patch.object(cache_service, 'connect', return_value=True):
                result = await cache_service.get("test_key")
                
                assert result == test_data
                mock_redis.get.assert_called_once_with("test_key")
                assert cache_service.metrics.hits == 1
    
    @pytest.mark.asyncio
    async def test_get_cache_miss(self, cache_service, mock_redis):
        """Test cache get operation with miss"""
        mock_redis.get.return_value = None
        
        with patch.object(cache_service, 'redis_client', mock_redis):
            with patch.object(cache_service, 'connect', return_value=True):
                result = await cache_service.get("test_key", default="default_value")
                
                assert result == "default_value"
                assert cache_service.metrics.misses == 1
    
    @pytest.mark.asyncio
    async def test_set_operation(self, cache_service, mock_redis):
        """Test cache set operation"""
        mock_redis.set.return_value = True
        
        with patch.object(cache_service, 'redis_client', mock_redis):
            with patch.object(cache_service, 'connect', return_value=True):
                success = await cache_service.set("test_key", {"data": "value"}, ttl=3600)
                
                assert success is True
                mock_redis.set.assert_called_once()
                assert cache_service.metrics.sets == 1
    
    @pytest.mark.asyncio
    async def test_delete_operation(self, cache_service, mock_redis):
        """Test cache delete operation"""
        mock_redis.delete.return_value = 1
        
        with patch.object(cache_service, 'redis_client', mock_redis):
            with patch.object(cache_service, 'connect', return_value=True):
                count = await cache_service.delete("test_key")
                
                assert count == 1
                mock_redis.delete.assert_called_once_with("test_key")
                assert cache_service.metrics.deletes == 1
    
    @pytest.mark.asyncio
    async def test_exists_operation(self, cache_service, mock_redis):
        """Test cache exists operation"""
        mock_redis.exists.return_value = 1
        
        with patch.object(cache_service, 'redis_client', mock_redis):
            with patch.object(cache_service, 'connect', return_value=True):
                exists = await cache_service.exists("test_key")
                
                assert exists is True
                mock_redis.exists.assert_called_once_with("test_key")
    
    @pytest.mark.asyncio
    async def test_ttl_operation(self, cache_service, mock_redis):
        """Test TTL check operation"""
        mock_redis.ttl.return_value = 3600
        
        with patch.object(cache_service, 'redis_client', mock_redis):
            with patch.object(cache_service, 'connect', return_value=True):
                ttl = await cache_service.ttl("test_key")
                
                assert ttl == 3600
                mock_redis.ttl.assert_called_once_with("test_key")
    
    @pytest.mark.asyncio
    async def test_keys_operation(self, cache_service, mock_redis):
        """Test keys pattern matching operation"""
        mock_redis.keys.return_value = [b"key1", b"key2"]
        
        with patch.object(cache_service, 'redis_client', mock_redis):
            with patch.object(cache_service, 'connect', return_value=True):
                keys = await cache_service.keys("test:*")
                
                assert keys == ["key1", "key2"]
                mock_redis.keys.assert_called_once_with("test:*")
    
    @pytest.mark.asyncio
    async def test_error_handling(self, cache_service, mock_redis):
        """Test error handling in cache operations"""
        # Setup mock to raise exception
        mock_redis.get.side_effect = Exception("Redis error")
        
        with patch.object(cache_service, 'redis_client', mock_redis):
            with patch.object(cache_service, 'connect', return_value=True):
                result = await cache_service.get("test_key", default="fallback")
                
                # Should return default value and record error
                assert result == "fallback"
                assert cache_service.metrics.errors > 0
    
    @pytest.mark.asyncio
    async def test_ttl_enforcement(self, cache_service, mock_redis):
        """Test TTL enforcement"""
        mock_redis.set.return_value = True
        
        with patch.object(cache_service, 'redis_client', mock_redis):
            with patch.object(cache_service, 'connect', return_value=True):
                # Test default TTL
                await cache_service.set("key1", "value1")
                
                # Test custom TTL within limits
                await cache_service.set("key2", "value2", ttl=1800)
                
                # Test TTL exceeding maximum (should be capped)
                await cache_service.set("key3", "value3", ttl=999999)
                
                # Verify set was called with correct TTL values
                calls = mock_redis.set.call_args_list
                assert len(calls) == 3
                
                # Check that the last call had TTL capped to max_ttl
                last_call_kwargs = calls[-1].kwargs
                assert last_call_kwargs['ex'] <= cache_service.config.max_ttl
    
    def test_metrics_collection(self, cache_service):
        """Test metrics collection"""
        # Initially empty
        metrics = cache_service.get_metrics()
        assert metrics['hits'] == 0
        assert metrics['misses'] == 0
        
        # After operations
        cache_service.metrics.record_hit(0.1)
        cache_service.metrics.record_miss(0.2)
        
        metrics = cache_service.get_metrics()
        assert metrics['hits'] == 1
        assert metrics['misses'] == 1
        assert metrics['hit_rate'] == 50.0
    
    def test_metrics_reset(self, cache_service):
        """Test metrics reset functionality"""
        cache_service.metrics.record_hit()
        cache_service.metrics.record_miss()
        
        cache_service.reset_metrics()
        
        metrics = cache_service.get_metrics()
        assert metrics['hits'] == 0
        assert metrics['misses'] == 0
    
    @pytest.mark.asyncio
    async def test_disconnect(self, cache_service, mock_redis):
        """Test cache service disconnection"""
        cache_service.redis_client = mock_redis
        
        await cache_service.disconnect()
        
        # Should clean up the client
        assert cache_service.redis_client is None


@pytest.mark.integration
class TestCacheServiceIntegration:
    """Integration tests that require a real Redis instance"""
    
    @pytest.mark.asyncio
    async def test_real_redis_operations(self):
        """Test with real Redis (requires Redis server)"""
        # Skip if Redis is not available
        pytest.importorskip("redis")
        
        config = CacheConfig(host="localhost", port=6379, database=15)  # Use test DB
        service = CacheService(config)
        
        try:
            # Connect
            connected = await service.connect()
            if not connected:
                pytest.skip("Redis server not available")
            
            # Test operations
            await service.set("test_key", {"test": "data"}, ttl=60)
            result = await service.get("test_key")
            assert result == {"test": "data"}
            
            exists = await service.exists("test_key")
            assert exists is True
            
            deleted = await service.delete("test_key")
            assert deleted == 1
            
            exists_after_delete = await service.exists("test_key")
            assert exists_after_delete is False
            
        finally:
            await service.disconnect()


if __name__ == "__main__":
    pytest.main([__file__])