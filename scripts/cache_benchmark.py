"""
Cache Performance Benchmark Script

Benchmarks cache performance to demonstrate improvements:
- Database query time vs cache hit time
- Memory usage optimization
- Batch operation performance
- Cache warming effectiveness
"""

import asyncio
import time
import statistics
import random
from typing import List, Dict, Any
from datetime import datetime

# Mock imports for demonstration (would use real modules in production)
from src.core.cache_service import get_cache_service
from src.services.cache_manager import get_cache_manager
from src.utils.logger import get_logger


logger = get_logger(__name__)


class CacheBenchmark:
    """Comprehensive cache performance benchmark"""
    
    def __init__(self):
        self.cache_service = get_cache_service()
        self.cache_manager = get_cache_manager()
        self.results = {}
    
    async def run_all_benchmarks(self) -> Dict[str, Any]:
        """Run all benchmark tests"""
        logger.info("Starting cache performance benchmarks...")
        
        # Initialize cache
        await self.cache_service.connect()
        
        try:
            # Run individual benchmarks
            self.results["basic_operations"] = await self.benchmark_basic_operations()
            self.results["cache_vs_db"] = await self.benchmark_cache_vs_db()
            self.results["batch_operations"] = await self.benchmark_batch_operations()
            self.results["memory_efficiency"] = await self.benchmark_memory_efficiency()
            self.results["cache_warming"] = await self.benchmark_cache_warming()
            self.results["serialization"] = await self.benchmark_serialization()
            
            # Generate summary
            self.results["summary"] = self.generate_summary()
            
            return self.results
            
        finally:
            await self.cache_service.disconnect()
    
    async def benchmark_basic_operations(self) -> Dict[str, Any]:
        """Benchmark basic cache operations (get, set, delete)"""
        logger.info("Benchmarking basic cache operations...")
        
        results = {}
        iterations = 1000
        
        # Benchmark SET operations
        set_times = []
        test_data = {"test": "data", "number": 42, "list": [1, 2, 3]}
        
        for i in range(iterations):
            start_time = time.perf_counter()
            await self.cache_service.set(f"benchmark_set_{i}", test_data, ttl=3600)
            end_time = time.perf_counter()
            set_times.append((end_time - start_time) * 1000)  # Convert to ms
        
        results["set_operations"] = {
            "iterations": iterations,
            "avg_time_ms": round(statistics.mean(set_times), 3),
            "median_time_ms": round(statistics.median(set_times), 3),
            "min_time_ms": round(min(set_times), 3),
            "max_time_ms": round(max(set_times), 3),
            "operations_per_second": round(1000 / statistics.mean(set_times), 2)
        }
        
        # Benchmark GET operations (cache hits)
        get_times = []
        
        for i in range(iterations):
            start_time = time.perf_counter()
            result = await self.cache_service.get(f"benchmark_set_{i}")
            end_time = time.perf_counter()
            get_times.append((end_time - start_time) * 1000)
            
            assert result == test_data  # Verify data integrity
        
        results["get_operations"] = {
            "iterations": iterations,
            "avg_time_ms": round(statistics.mean(get_times), 3),
            "median_time_ms": round(statistics.median(get_times), 3),
            "min_time_ms": round(min(get_times), 3),
            "max_time_ms": round(max(get_times), 3),
            "operations_per_second": round(1000 / statistics.mean(get_times), 2)
        }
        
        # Benchmark DELETE operations
        delete_times = []
        
        for i in range(iterations):
            start_time = time.perf_counter()
            count = await self.cache_service.delete(f"benchmark_set_{i}")
            end_time = time.perf_counter()
            delete_times.append((end_time - start_time) * 1000)
            
            assert count == 1  # Verify deletion
        
        results["delete_operations"] = {
            "iterations": iterations,
            "avg_time_ms": round(statistics.mean(delete_times), 3),
            "median_time_ms": round(statistics.median(delete_times), 3),
            "operations_per_second": round(1000 / statistics.mean(delete_times), 2)
        }
        
        logger.info(f"Basic operations benchmark completed: "
                   f"SET {results['set_operations']['operations_per_second']} ops/sec, "
                   f"GET {results['get_operations']['operations_per_second']} ops/sec")
        
        return results
    
    async def benchmark_cache_vs_db(self) -> Dict[str, Any]:
        """Benchmark cache performance vs simulated database queries"""
        logger.info("Benchmarking cache vs database performance...")
        
        # Simulate database query times (would be real DB queries in production)
        async def simulate_db_query(query_id: int) -> Dict[str, Any]:
            # Simulate DB query delay
            await asyncio.sleep(random.uniform(0.01, 0.05))  # 10-50ms
            return {
                "id": query_id,
                "data": f"Database result for query {query_id}",
                "timestamp": datetime.now().isoformat(),
                "metadata": {"source": "database", "query_time": "simulated"}
            }
        
        results = {}
        iterations = 100
        
        # Benchmark database queries
        db_times = []
        for i in range(iterations):
            start_time = time.perf_counter()
            result = await simulate_db_query(i)
            end_time = time.perf_counter()
            db_times.append((end_time - start_time) * 1000)
            
            # Cache the result for comparison
            await self.cache_service.set(f"db_result_{i}", result, ttl=3600)
        
        # Benchmark cache retrieval
        cache_times = []
        for i in range(iterations):
            start_time = time.perf_counter()
            result = await self.cache_service.get(f"db_result_{i}")
            end_time = time.perf_counter()
            cache_times.append((end_time - start_time) * 1000)
            
            assert result is not None  # Verify cache hit
        
        # Calculate performance improvement
        avg_db_time = statistics.mean(db_times)
        avg_cache_time = statistics.mean(cache_times)
        improvement_factor = avg_db_time / avg_cache_time
        
        results = {
            "database_queries": {
                "avg_time_ms": round(avg_db_time, 3),
                "operations_per_second": round(1000 / avg_db_time, 2)
            },
            "cache_hits": {
                "avg_time_ms": round(avg_cache_time, 3),
                "operations_per_second": round(1000 / avg_cache_time, 2)
            },
            "performance_improvement": {
                "speed_improvement_factor": round(improvement_factor, 2),
                "time_saved_percentage": round((1 - avg_cache_time/avg_db_time) * 100, 1),
                "estimated_daily_time_saved_hours": round(
                    (avg_db_time - avg_cache_time) * 10000 / 1000 / 3600, 2  # Assuming 10k queries/day
                )
            }
        }
        
        logger.info(f"Cache vs DB benchmark: {improvement_factor:.1f}x speed improvement")
        
        return results
    
    async def benchmark_batch_operations(self) -> Dict[str, Any]:
        """Benchmark batch operations vs individual operations"""
        logger.info("Benchmarking batch operations...")
        
        results = {}
        batch_size = 100
        
        # Individual operations
        individual_times = []
        test_data = [{"id": i, "data": f"item_{i}"} for i in range(batch_size)]
        
        start_time = time.perf_counter()
        for i, item in enumerate(test_data):
            await self.cache_service.set(f"individual_{i}", item, ttl=3600)
        end_time = time.perf_counter()
        individual_time = (end_time - start_time) * 1000
        
        # Batch-style operations (simulated)
        start_time = time.perf_counter()
        # In a real implementation, this would use Redis pipeline
        # For now, we'll simulate batch efficiency
        batch_tasks = []
        for i, item in enumerate(test_data):
            batch_tasks.append(
                self.cache_service.set(f"batch_{i}", item, ttl=3600)
            )
        await asyncio.gather(*batch_tasks)
        end_time = time.perf_counter()
        batch_time = (end_time - start_time) * 1000
        
        results = {
            "individual_operations": {
                "total_time_ms": round(individual_time, 3),
                "avg_per_item_ms": round(individual_time / batch_size, 3),
                "operations_per_second": round(batch_size * 1000 / individual_time, 2)
            },
            "batch_operations": {
                "total_time_ms": round(batch_time, 3),
                "avg_per_item_ms": round(batch_time / batch_size, 3),
                "operations_per_second": round(batch_size * 1000 / batch_time, 2)
            },
            "batch_improvement": {
                "time_ratio": round(individual_time / batch_time, 2),
                "time_saved_percentage": round((1 - batch_time/individual_time) * 100, 1)
            }
        }
        
        logger.info(f"Batch operations: {results['batch_improvement']['time_ratio']:.1f}x faster")
        
        return results
    
    async def benchmark_memory_efficiency(self) -> Dict[str, Any]:
        """Benchmark memory efficiency with compression"""
        logger.info("Benchmarking memory efficiency...")
        
        from src.core.cache_service import Serializer
        serializer = Serializer()
        
        results = {}
        
        # Test different data sizes
        test_cases = [
            ("small", {"data": "x" * 100}),
            ("medium", {"data": "x" * 1000}),
            ("large", {"data": "x" * 10000}),
            ("extra_large", {"data": "x" * 100000})
        ]
        
        for size_name, data in test_cases:
            # Serialize without compression
            uncompressed = serializer.serialize(data, compress_threshold=999999)
            
            # Serialize with compression
            compressed = serializer.serialize(data, compress_threshold=500)
            
            # Test deserialization performance
            decomp_times = []
            for _ in range(10):
                start_time = time.perf_counter()
                result = serializer.deserialize(compressed)
                end_time = time.perf_counter()
                decomp_times.append((end_time - start_time) * 1000)
            
            compression_ratio = len(uncompressed) / len(compressed)
            
            results[size_name] = {
                "original_size_bytes": len(uncompressed),
                "compressed_size_bytes": len(compressed),
                "compression_ratio": round(compression_ratio, 2),
                "space_saved_percentage": round((1 - len(compressed)/len(uncompressed)) * 100, 1),
                "decompression_time_ms": round(statistics.mean(decomp_times), 3)
            }
        
        logger.info("Memory efficiency benchmark completed")
        
        return results
    
    async def benchmark_cache_warming(self) -> Dict[str, Any]:
        """Benchmark cache warming performance"""
        logger.info("Benchmarking cache warming...")
        
        results = {}
        
        # Simulate warming different amounts of data
        warming_sizes = [10, 50, 100, 500]
        
        for size in warming_sizes:
            # Generate test data
            test_data = [
                {"id": i, "name": f"item_{i}", "data": f"content_{i}" * 10}
                for i in range(size)
            ]
            
            # Benchmark warming time
            start_time = time.perf_counter()
            
            # Simulate cache warming
            warming_tasks = []
            for i, item in enumerate(test_data):
                warming_tasks.append(
                    self.cache_service.set(f"warm_{size}_{i}", item, ttl=7200)
                )
            
            await asyncio.gather(*warming_tasks)
            
            end_time = time.perf_counter()
            warming_time = (end_time - start_time) * 1000
            
            # Test cache hit performance after warming
            hit_times = []
            for i in range(min(size, 50)):  # Test first 50 items
                start_time = time.perf_counter()
                result = await self.cache_service.get(f"warm_{size}_{i}")
                end_time = time.perf_counter()
                hit_times.append((end_time - start_time) * 1000)
                
                assert result is not None
            
            results[f"size_{size}"] = {
                "warming_time_ms": round(warming_time, 3),
                "items_per_second": round(size * 1000 / warming_time, 2),
                "avg_hit_time_ms": round(statistics.mean(hit_times), 3),
                "hit_rate_ops_per_second": round(1000 / statistics.mean(hit_times), 2)
            }
        
        logger.info("Cache warming benchmark completed")
        
        return results
    
    async def benchmark_serialization(self) -> Dict[str, Any]:
        """Benchmark serialization performance"""
        logger.info("Benchmarking serialization performance...")
        
        from src.core.cache_service import Serializer
        serializer = Serializer()
        
        results = {}
        iterations = 1000
        
        # Test different data types
        test_data = {
            "string": "This is a test string with some content",
            "number": 12345,
            "float": 123.456,
            "boolean": True,
            "list": [1, 2, 3, "test", {"nested": "object"}],
            "dict": {
                "key1": "value1",
                "key2": {"nested": "data"},
                "key3": [1, 2, 3]
            }
        }
        
        for data_type, data in test_data.items():
            # Benchmark serialization
            serialize_times = []
            deserialize_times = []
            
            serialized_data = None
            
            for _ in range(iterations):
                # Serialize
                start_time = time.perf_counter()
                serialized_data = serializer.serialize(data)
                end_time = time.perf_counter()
                serialize_times.append((end_time - start_time) * 1000)
                
                # Deserialize
                start_time = time.perf_counter()
                result = serializer.deserialize(serialized_data)
                end_time = time.perf_counter()
                deserialize_times.append((end_time - start_time) * 1000)
                
                assert result == data  # Verify data integrity
            
            results[data_type] = {
                "serialize_avg_ms": round(statistics.mean(serialize_times), 4),
                "deserialize_avg_ms": round(statistics.mean(deserialize_times), 4),
                "total_avg_ms": round(statistics.mean(serialize_times) + statistics.mean(deserialize_times), 4),
                "serialized_size_bytes": len(serialized_data),
                "round_trips_per_second": round(1000 / (statistics.mean(serialize_times) + statistics.mean(deserialize_times)), 2)
            }
        
        logger.info("Serialization benchmark completed")
        
        return results
    
    def generate_summary(self) -> Dict[str, Any]:
        """Generate benchmark summary"""
        summary = {
            "benchmark_timestamp": datetime.now().isoformat(),
            "key_performance_indicators": {}
        }
        
        if "basic_operations" in self.results:
            basic = self.results["basic_operations"]
            summary["key_performance_indicators"]["get_ops_per_second"] = basic["get_operations"]["operations_per_second"]
            summary["key_performance_indicators"]["set_ops_per_second"] = basic["set_operations"]["operations_per_second"]
        
        if "cache_vs_db" in self.results:
            cache_db = self.results["cache_vs_db"]
            summary["key_performance_indicators"]["speed_improvement_factor"] = cache_db["performance_improvement"]["speed_improvement_factor"]
            summary["key_performance_indicators"]["time_saved_percentage"] = cache_db["performance_improvement"]["time_saved_percentage"]
        
        if "memory_efficiency" in self.results:
            memory = self.results["memory_efficiency"]
            if "large" in memory:
                summary["key_performance_indicators"]["compression_ratio"] = memory["large"]["compression_ratio"]
                summary["key_performance_indicators"]["space_saved_percentage"] = memory["large"]["space_saved_percentage"]
        
        # Calculate overall performance score
        score_factors = []
        if "get_ops_per_second" in summary["key_performance_indicators"]:
            score_factors.append(min(summary["key_performance_indicators"]["get_ops_per_second"] / 1000, 10))
        if "speed_improvement_factor" in summary["key_performance_indicators"]:
            score_factors.append(min(summary["key_performance_indicators"]["speed_improvement_factor"], 10))
        
        if score_factors:
            summary["overall_performance_score"] = round(statistics.mean(score_factors), 1)
        
        return summary
    
    def print_results(self):
        """Print formatted benchmark results"""
        print("\n" + "="*80)
        print("CACHE PERFORMANCE BENCHMARK RESULTS")
        print("="*80)
        
        if "summary" in self.results:
            summary = self.results["summary"]
            print(f"\n📊 PERFORMANCE SUMMARY")
            print("-" * 40)
            
            kpis = summary["key_performance_indicators"]
            if "get_ops_per_second" in kpis:
                print(f"Cache GET Operations: {kpis['get_ops_per_second']:,} ops/second")
            if "set_ops_per_second" in kpis:
                print(f"Cache SET Operations: {kpis['set_ops_per_second']:,} ops/second")
            if "speed_improvement_factor" in kpis:
                print(f"Speed vs Database: {kpis['speed_improvement_factor']:.1f}x faster")
            if "time_saved_percentage" in kpis:
                print(f"Time Savings: {kpis['time_saved_percentage']:.1f}%")
            if "compression_ratio" in kpis:
                print(f"Compression Ratio: {kpis['compression_ratio']:.1f}:1")
            
            if "overall_performance_score" in summary:
                score = summary["overall_performance_score"]
                print(f"\n🎯 Overall Performance Score: {score}/10")
                if score >= 8:
                    print("   ✅ Excellent performance!")
                elif score >= 6:
                    print("   ✅ Good performance")
                elif score >= 4:
                    print("   ⚠️  Acceptable performance")
                else:
                    print("   ❌ Performance needs improvement")
        
        print("\n" + "="*80)


async def main():
    """Run cache benchmarks"""
    benchmark = CacheBenchmark()
    
    try:
        print("Starting comprehensive cache performance benchmarks...")
        print("This may take a few minutes...\n")
        
        results = await benchmark.run_all_benchmarks()
        
        # Print results
        benchmark.print_results()
        
        # Save results to file
        import json
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"cache_benchmark_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n📁 Detailed results saved to: {filename}")
        
    except Exception as e:
        logger.error(f"Benchmark failed: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(main())