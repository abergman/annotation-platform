/**
 * Performance Tests - Load Testing
 * Tests system performance under various load conditions
 */

import { testPerformanceData, testAnnotations } from '../fixtures/test-data.js';

// Mock performance monitoring utilities
class PerformanceMonitor {
  constructor() {
    this.metrics = {
      memory: [],
      cpu: [],
      responseTime: [],
      throughput: []
    };
    this.startTime = null;
  }

  start() {
    this.startTime = performance.now();
    return this;
  }

  stop() {
    if (!this.startTime) return 0;
    const duration = performance.now() - this.startTime;
    this.startTime = null;
    return duration;
  }

  recordResponseTime(duration) {
    this.metrics.responseTime.push(duration);
  }

  recordMemoryUsage() {
    const memInfo = process.memoryUsage();
    this.metrics.memory.push({
      timestamp: Date.now(),
      heapUsed: memInfo.heapUsed,
      heapTotal: memInfo.heapTotal,
      external: memInfo.external,
      rss: memInfo.rss
    });
  }

  getAverageResponseTime() {
    const times = this.metrics.responseTime;
    return times.length > 0 ? times.reduce((a, b) => a + b, 0) / times.length : 0;
  }

  getMemoryUsage() {
    if (this.metrics.memory.length === 0) return null;
    const latest = this.metrics.memory[this.metrics.memory.length - 1];
    return {
      heapUsedMB: Math.round(latest.heapUsed / 1024 / 1024),
      heapTotalMB: Math.round(latest.heapTotal / 1024 / 1024),
      rssMB: Math.round(latest.rss / 1024 / 1024)
    };
  }

  getThroughput(operationCount, timeWindow = 1000) {
    const recent = this.metrics.responseTime.slice(-operationCount);
    return recent.length / (timeWindow / 1000); // Operations per second
  }

  getPercentile(percentile) {
    const sorted = [...this.metrics.responseTime].sort((a, b) => a - b);
    const index = Math.ceil((percentile / 100) * sorted.length) - 1;
    return sorted[index] || 0;
  }
}

// Mock database operations for performance testing
class MockDatabase {
  constructor() {
    this.annotations = [];
    this.queryCount = 0;
    this.insertCount = 0;
  }

  async insertAnnotation(annotation) {
    const start = performance.now();
    
    // Simulate database operation delay
    await new Promise(resolve => setTimeout(resolve, Math.random() * 10));
    
    const newAnnotation = {
      id: Date.now().toString() + Math.random(),
      ...annotation,
      createdAt: new Date()
    };
    
    this.annotations.push(newAnnotation);
    this.insertCount++;
    
    return {
      data: newAnnotation,
      duration: performance.now() - start
    };
  }

  async queryAnnotations(filters = {}) {
    const start = performance.now();
    
    // Simulate query processing time based on result size
    const delay = Math.min(this.annotations.length / 100, 50);
    await new Promise(resolve => setTimeout(resolve, delay));
    
    let results = [...this.annotations];
    
    if (filters.documentId) {
      results = results.filter(a => a.documentId === filters.documentId);
    }
    
    if (filters.userId) {
      results = results.filter(a => a.userId === filters.userId);
    }
    
    if (filters.type) {
      results = results.filter(a => a.type === filters.type);
    }
    
    this.queryCount++;
    
    return {
      data: results,
      duration: performance.now() - start,
      count: results.length
    };
  }

  async bulkInsert(annotations) {
    const start = performance.now();
    const results = [];
    
    // Simulate batch processing
    const batchSize = 100;
    for (let i = 0; i < annotations.length; i += batchSize) {
      const batch = annotations.slice(i, i + batchSize);
      await new Promise(resolve => setTimeout(resolve, 5)); // Batch processing delay
      
      for (const annotation of batch) {
        const newAnnotation = {
          id: Date.now().toString() + Math.random(),
          ...annotation,
          createdAt: new Date()
        };
        this.annotations.push(newAnnotation);
        results.push(newAnnotation);
      }
    }
    
    this.insertCount += annotations.length;
    
    return {
      data: results,
      duration: performance.now() - start,
      count: results.length
    };
  }

  getStats() {
    return {
      totalAnnotations: this.annotations.length,
      queryCount: this.queryCount,
      insertCount: this.insertCount
    };
  }

  clear() {
    this.annotations = [];
    this.queryCount = 0;
    this.insertCount = 0;
  }
}

describe('Performance Tests', () => {
  let monitor;
  let database;

  beforeEach(() => {
    monitor = new PerformanceMonitor();
    database = new MockDatabase();
  });

  afterEach(() => {
    database.clear();
  });

  describe('Single Operation Performance', () => {
    it('should create annotations within performance thresholds', async () => {
      const annotation = {
        ...testAnnotations.highlight,
        documentId: 'doc1',
        userId: 'user1'
      };

      monitor.start();
      const result = await database.insertAnnotation(annotation);
      const duration = monitor.stop();

      monitor.recordResponseTime(duration);
      monitor.recordMemoryUsage();

      // Performance assertions
      expect(duration).toBeLessThan(100); // Less than 100ms
      expect(result.duration).toBeLessThan(50); // Database operation under 50ms
      expect(result.data.id).toBeDefined();
    });

    it('should query annotations efficiently', async () => {
      // Seed database with annotations
      const testAnnotations = Array.from({ length: 100 }, (_, i) => ({
        text: `Annotation ${i}`,
        content: `Content ${i}`,
        startPosition: i * 10,
        endPosition: (i * 10) + 5,
        type: 'highlight',
        documentId: `doc${i % 5}`,
        userId: `user${i % 10}`
      }));

      await database.bulkInsert(testAnnotations);

      // Test query performance
      monitor.start();
      const result = await database.queryAnnotations({ documentId: 'doc1' });
      const duration = monitor.stop();

      monitor.recordResponseTime(duration);
      monitor.recordMemoryUsage();

      expect(duration).toBeLessThan(200); // Query under 200ms
      expect(result.duration).toBeLessThan(100); // Database query under 100ms
      expect(result.data.length).toBeGreaterThan(0);
    });
  });

  describe('Concurrent Operations Performance', () => {
    it('should handle concurrent annotation creation', async () => {
      const concurrentOperations = 50;
      const annotations = Array.from({ length: concurrentOperations }, (_, i) => ({
        text: `Concurrent annotation ${i}`,
        content: `Content for concurrent test ${i}`,
        startPosition: i * 20,
        endPosition: (i * 20) + 10,
        type: i % 2 === 0 ? 'highlight' : 'comment',
        documentId: 'doc1',
        userId: `user${i % 5}`
      }));

      monitor.start();
      monitor.recordMemoryUsage();

      // Execute concurrent operations
      const promises = annotations.map(annotation => 
        database.insertAnnotation(annotation)
      );

      const results = await Promise.all(promises);
      const totalDuration = monitor.stop();

      results.forEach(result => {
        monitor.recordResponseTime(result.duration);
      });

      monitor.recordMemoryUsage();

      // Performance assertions
      expect(totalDuration).toBeLessThan(5000); // All operations under 5 seconds
      expect(monitor.getAverageResponseTime()).toBeLessThan(100); // Average under 100ms
      expect(results.every(r => r.data.id)).toBe(true);

      const memoryUsage = monitor.getMemoryUsage();
      expect(memoryUsage.heapUsedMB).toBeLessThan(100); // Memory under 100MB
    });

    it('should maintain performance with concurrent queries', async () => {
      // Seed with large dataset
      const seedData = Array.from({ length: 1000 }, (_, i) => ({
        text: `Annotation ${i}`,
        content: `Content ${i}`,
        startPosition: i * 10,
        endPosition: (i * 10) + 5,
        type: ['highlight', 'comment', 'question'][i % 3],
        documentId: `doc${i % 10}`,
        userId: `user${i % 20}`
      }));

      await database.bulkInsert(seedData);

      // Concurrent query operations
      const queryPromises = Array.from({ length: 20 }, (_, i) => 
        database.queryAnnotations({ 
          documentId: `doc${i % 10}`,
          type: ['highlight', 'comment'][i % 2]
        })
      );

      monitor.start();
      monitor.recordMemoryUsage();

      const results = await Promise.all(queryPromises);
      const totalDuration = monitor.stop();

      results.forEach(result => {
        monitor.recordResponseTime(result.duration);
      });

      monitor.recordMemoryUsage();

      // Performance assertions
      expect(totalDuration).toBeLessThan(3000); // All queries under 3 seconds
      expect(monitor.getAverageResponseTime()).toBeLessThan(150); // Average under 150ms
      expect(results.every(r => Array.isArray(r.data))).toBe(true);
    });
  });

  describe('Large Dataset Performance', () => {
    it('should handle large document processing', async () => {
      const largeDocument = testPerformanceData.largeDocument;
      const annotations = largeDocument.annotations;

      monitor.start();
      monitor.recordMemoryUsage();

      // Process annotations in batches
      const batchSize = 200;
      const batches = [];
      
      for (let i = 0; i < annotations.length; i += batchSize) {
        const batch = annotations.slice(i, i + batchSize);
        batches.push(batch);
      }

      // Process all batches
      for (const batch of batches) {
        const result = await database.bulkInsert(batch);
        monitor.recordResponseTime(result.duration);
      }

      const totalDuration = monitor.stop();
      monitor.recordMemoryUsage();

      // Performance assertions
      expect(totalDuration).toBeLessThan(30000); // Under 30 seconds
      expect(monitor.getAverageResponseTime()).toBeLessThan(500); // Average batch under 500ms
      
      const memoryUsage = monitor.getMemoryUsage();
      expect(memoryUsage.heapUsedMB).toBeLessThan(500); // Memory under 500MB

      const stats = database.getStats();
      expect(stats.totalAnnotations).toBe(annotations.length);
    });

    it('should efficiently query large datasets', async () => {
      // Create large dataset with varied data
      const largeDataset = Array.from({ length: 5000 }, (_, i) => ({
        text: `Text segment ${i}`,
        content: `Annotation content ${i} with additional details`,
        startPosition: i * 50,
        endPosition: (i * 50) + 25,
        type: ['highlight', 'comment', 'question', 'note'][i % 4],
        documentId: `doc${i % 50}`,
        userId: `user${i % 100}`,
        tags: [`tag${i % 20}`, `category${i % 10}`],
        priority: ['low', 'medium', 'high'][i % 3]
      }));

      await database.bulkInsert(largeDataset);

      // Test various query patterns
      const queryTests = [
        { documentId: 'doc1' },
        { userId: 'user1' },
        { type: 'highlight' },
        { documentId: 'doc1', type: 'comment' },
        { documentId: 'doc5', userId: 'user25' }
      ];

      monitor.start();

      for (const query of queryTests) {
        const result = await database.queryAnnotations(query);
        monitor.recordResponseTime(result.duration);
      }

      const totalDuration = monitor.stop();

      // Performance assertions
      expect(totalDuration).toBeLessThan(5000); // All queries under 5 seconds
      expect(monitor.getAverageResponseTime()).toBeLessThan(200); // Average under 200ms
      expect(monitor.getPercentile(95)).toBeLessThan(500); // 95th percentile under 500ms
    });
  });

  describe('Memory Performance', () => {
    it('should manage memory efficiently with large operations', async () => {
      monitor.recordMemoryUsage();
      const initialMemory = monitor.getMemoryUsage();

      // Perform memory-intensive operations
      const operations = [];
      
      for (let i = 0; i < 10; i++) {
        const batch = Array.from({ length: 500 }, (_, j) => ({
          text: `Memory test annotation ${i}-${j}`,
          content: `Content for memory test ${i}-${j}`.repeat(10),
          startPosition: (i * 500 + j) * 10,
          endPosition: (i * 500 + j) * 10 + 5,
          type: 'highlight',
          documentId: `doc${i}`,
          userId: `user${j % 10}`
        }));

        const operation = database.bulkInsert(batch);
        operations.push(operation);
      }

      await Promise.all(operations);

      monitor.recordMemoryUsage();
      const finalMemory = monitor.getMemoryUsage();

      // Force garbage collection if available
      if (global.gc) {
        global.gc();
      }

      await new Promise(resolve => setTimeout(resolve, 100));
      monitor.recordMemoryUsage();
      const afterGcMemory = monitor.getMemoryUsage();

      // Memory assertions
      const memoryIncrease = finalMemory.heapUsedMB - initialMemory.heapUsedMB;
      expect(memoryIncrease).toBeLessThan(200); // Memory increase under 200MB

      if (global.gc) {
        const memoryAfterGc = afterGcMemory.heapUsedMB - initialMemory.heapUsedMB;
        expect(memoryAfterGc).toBeLessThan(memoryIncrease * 1.5); // GC should help
      }
    });

    it('should handle memory pressure gracefully', async () => {
      const iterations = 50;
      const memorySnapshots = [];

      for (let i = 0; i < iterations; i++) {
        monitor.recordMemoryUsage();
        memorySnapshots.push(monitor.getMemoryUsage());

        // Create and process data
        const data = Array.from({ length: 100 }, (_, j) => ({
          text: `Pressure test ${i}-${j}`,
          content: `Content for pressure test ${i}-${j}`,
          startPosition: j * 10,
          endPosition: j * 10 + 5,
          type: 'highlight',
          documentId: `pressure-doc-${i}`,
          userId: `pressure-user-${j % 5}`
        }));

        await database.bulkInsert(data);

        // Periodic cleanup simulation
        if (i % 10 === 0 && global.gc) {
          global.gc();
        }
      }

      // Analyze memory growth
      const memoryGrowth = memorySnapshots.map((snapshot, i) => 
        i > 0 ? snapshot.heapUsedMB - memorySnapshots[i-1].heapUsedMB : 0
      );

      const averageGrowth = memoryGrowth.slice(1).reduce((a, b) => a + b, 0) / (memoryGrowth.length - 1);

      // Memory growth should be reasonable
      expect(averageGrowth).toBeLessThan(5); // Average growth under 5MB per iteration
      expect(memorySnapshots[memorySnapshots.length - 1].heapUsedMB).toBeLessThan(500); // Total under 500MB
    });
  });

  describe('Stress Testing', () => {
    it('should maintain performance under high load', async () => {
      const highLoadOperations = 200;
      const operationTypes = ['create', 'query', 'bulk_create'];
      const results = [];

      monitor.start();

      // Simulate mixed high-load operations
      const operations = Array.from({ length: highLoadOperations }, (_, i) => {
        const operationType = operationTypes[i % 3];
        
        switch (operationType) {
          case 'create':
            return database.insertAnnotation({
              text: `High load annotation ${i}`,
              content: `Content ${i}`,
              startPosition: i * 10,
              endPosition: i * 10 + 5,
              type: 'highlight',
              documentId: `stress-doc-${i % 10}`,
              userId: `stress-user-${i % 20}`
            });
            
          case 'query':
            return database.queryAnnotations({
              documentId: `stress-doc-${i % 10}`
            });
            
          case 'bulk_create':
            const bulkData = Array.from({ length: 10 }, (_, j) => ({
              text: `Bulk ${i}-${j}`,
              content: `Bulk content ${i}-${j}`,
              startPosition: j * 10,
              endPosition: j * 10 + 5,
              type: 'comment',
              documentId: `bulk-doc-${i}`,
              userId: `bulk-user-${j % 5}`
            }));
            return database.bulkInsert(bulkData);
            
          default:
            return Promise.resolve({ duration: 0 });
        }
      });

      // Execute with controlled concurrency
      const batchSize = 20;
      for (let i = 0; i < operations.length; i += batchSize) {
        const batch = operations.slice(i, i + batchSize);
        const batchResults = await Promise.all(batch);
        results.push(...batchResults);
        
        // Brief pause between batches
        await new Promise(resolve => setTimeout(resolve, 10));
      }

      const totalDuration = monitor.stop();

      results.forEach(result => {
        monitor.recordResponseTime(result.duration);
      });

      // Stress test assertions
      expect(totalDuration).toBeLessThan(60000); // Under 1 minute
      expect(monitor.getAverageResponseTime()).toBeLessThan(300); // Average under 300ms
      expect(monitor.getPercentile(99)).toBeLessThan(1000); // 99th percentile under 1 second
      
      const throughput = monitor.getThroughput(results.length, totalDuration);
      expect(throughput).toBeGreaterThan(10); // At least 10 operations per second
    });

    it('should recover from resource exhaustion', async () => {
      // Simulate resource exhaustion scenario
      const memoryExhaustionTest = async () => {
        const largeOperations = [];
        
        for (let i = 0; i < 100; i++) {
          const largeAnnotation = {
            text: `Large annotation ${i}`,
            content: 'Very large content '.repeat(1000), // Large content
            startPosition: i * 1000,
            endPosition: i * 1000 + 100,
            type: 'highlight',
            documentId: `large-doc-${i}`,
            userId: `large-user-${i}`
          };
          
          largeOperations.push(database.insertAnnotation(largeAnnotation));
        }

        try {
          await Promise.all(largeOperations);
        } catch (error) {
          // Expected to potentially fail under extreme conditions
        }
      };

      monitor.recordMemoryUsage();
      await memoryExhaustionTest();
      monitor.recordMemoryUsage();

      // Force cleanup
      if (global.gc) {
        global.gc();
      }

      // System should still be responsive
      const testOperation = await database.insertAnnotation({
        text: 'Recovery test',
        content: 'Testing system recovery',
        startPosition: 0,
        endPosition: 10,
        type: 'highlight',
        documentId: 'recovery-doc',
        userId: 'recovery-user'
      });

      expect(testOperation.data.id).toBeDefined();
      expect(testOperation.duration).toBeLessThan(1000);
    });
  });

  describe('Performance Benchmarking', () => {
    it('should establish performance baselines', async () => {
      const benchmarks = {
        singleInsert: [],
        singleQuery: [],
        bulkInsert: [],
        complexQuery: []
      };

      // Single insert benchmark
      for (let i = 0; i < 100; i++) {
        const result = await database.insertAnnotation({
          text: `Benchmark annotation ${i}`,
          content: `Benchmark content ${i}`,
          startPosition: i * 10,
          endPosition: i * 10 + 5,
          type: 'highlight',
          documentId: 'benchmark-doc',
          userId: 'benchmark-user'
        });
        benchmarks.singleInsert.push(result.duration);
      }

      // Single query benchmark
      for (let i = 0; i < 50; i++) {
        const result = await database.queryAnnotations({ documentId: 'benchmark-doc' });
        benchmarks.singleQuery.push(result.duration);
      }

      // Bulk insert benchmark
      for (let i = 0; i < 10; i++) {
        const bulkData = Array.from({ length: 100 }, (_, j) => ({
          text: `Bulk benchmark ${i}-${j}`,
          content: `Bulk content ${i}-${j}`,
          startPosition: j * 10,
          endPosition: j * 10 + 5,
          type: 'comment',
          documentId: `bulk-benchmark-${i}`,
          userId: `bulk-user-${j % 10}`
        }));

        const result = await database.bulkInsert(bulkData);
        benchmarks.bulkInsert.push(result.duration);
      }

      // Complex query benchmark
      for (let i = 0; i < 30; i++) {
        const result = await database.queryAnnotations({
          documentId: `bulk-benchmark-${i % 10}`,
          userId: `bulk-user-${i % 10}`
        });
        benchmarks.complexQuery.push(result.duration);
      }

      // Calculate benchmark statistics
      const calculateStats = (values) => {
        const sorted = [...values].sort((a, b) => a - b);
        return {
          min: sorted[0],
          max: sorted[sorted.length - 1],
          average: values.reduce((a, b) => a + b, 0) / values.length,
          median: sorted[Math.floor(sorted.length / 2)],
          p95: sorted[Math.floor(sorted.length * 0.95)],
          p99: sorted[Math.floor(sorted.length * 0.99)]
        };
      };

      const benchmarkResults = {
        singleInsert: calculateStats(benchmarks.singleInsert),
        singleQuery: calculateStats(benchmarks.singleQuery),
        bulkInsert: calculateStats(benchmarks.bulkInsert),
        complexQuery: calculateStats(benchmarks.complexQuery)
      };

      // Assert baseline performance requirements
      expect(benchmarkResults.singleInsert.p95).toBeLessThan(50);
      expect(benchmarkResults.singleQuery.p95).toBeLessThan(100);
      expect(benchmarkResults.bulkInsert.p95).toBeLessThan(500);
      expect(benchmarkResults.complexQuery.p95).toBeLessThan(200);

      // Log benchmark results for reference
      console.log('Performance Benchmarks:', JSON.stringify(benchmarkResults, null, 2));
    });
  });
});