/**
 * Performance and Load Validation Tests
 * Tests system performance under various load conditions
 */

const request = require('supertest');
const { performance } = require('perf_hooks');

describe('Performance and Load Validation', () => {
  let baseUrl;
  let performanceBaseline = {};
  
  beforeAll(async () => {
    baseUrl = process.env.DEPLOY_URL || 'http://localhost:8080';
    jest.setTimeout(600000); // 10 minutes for performance tests
    
    // Establish performance baseline
    await establishPerformanceBaseline();
  });

  async function establishPerformanceBaseline() {
    console.log('📊 Establishing performance baseline...');
    
    // Measure baseline response times
    const startTime = performance.now();
    const response = await request(baseUrl).get('/health').expect(200);
    const responseTime = performance.now() - startTime;
    
    performanceBaseline = {
      healthCheckResponseTime: responseTime,
      timestamp: new Date(),
      serverInfo: response.body.system || {}
    };
    
    console.log(`📈 Baseline health check response: ${responseTime.toFixed(2)}ms`);
  }

  describe('Response Time Performance', () => {
    test('should maintain fast response times for health checks', async () => {
      const measurements = [];
      const iterations = 50;
      
      for (let i = 0; i < iterations; i++) {
        const startTime = performance.now();
        await request(baseUrl).get('/health').expect(200);
        const responseTime = performance.now() - startTime;
        measurements.push(responseTime);
        
        // Small delay to avoid overwhelming the server
        await new Promise(resolve => setTimeout(resolve, 10));
      }
      
      const avgResponseTime = measurements.reduce((a, b) => a + b, 0) / measurements.length;
      const maxResponseTime = Math.max(...measurements);
      const p95ResponseTime = measurements.sort((a, b) => a - b)[Math.floor(measurements.length * 0.95)];
      
      console.log(`📊 Health check performance (${iterations} requests):`);
      console.log(`   Average: ${avgResponseTime.toFixed(2)}ms`);
      console.log(`   Max: ${maxResponseTime.toFixed(2)}ms`);
      console.log(`   P95: ${p95ResponseTime.toFixed(2)}ms`);
      
      // Performance thresholds
      expect(avgResponseTime).toBeLessThan(500); // 500ms average
      expect(p95ResponseTime).toBeLessThan(1000); // 1s P95
      expect(maxResponseTime).toBeLessThan(2000); // 2s max
    });

    test('should handle API requests efficiently', async () => {
      const endpoints = [
        '/api/v1/status',
        '/api/v1/status/database',
        '/api/v1/status/memory'
      ];
      
      const results = {};
      
      for (const endpoint of endpoints) {
        const measurements = [];
        
        for (let i = 0; i < 20; i++) {
          const startTime = performance.now();
          try {
            await request(baseUrl).get(endpoint).expect(200);
            const responseTime = performance.now() - startTime;
            measurements.push(responseTime);
          } catch (error) {
            if (error.status === 404) {
              // Endpoint doesn't exist, skip
              break;
            }
            throw error;
          }
          
          await new Promise(resolve => setTimeout(resolve, 20));
        }
        
        if (measurements.length > 0) {
          const avgResponseTime = measurements.reduce((a, b) => a + b, 0) / measurements.length;
          results[endpoint] = avgResponseTime;
          
          // API endpoints should be fast
          expect(avgResponseTime).toBeLessThan(1000); // 1 second max average
        }
      }
      
      console.log('📊 API endpoint performance:', results);
    });

    test('should maintain performance under sustained load', async () => {
      const duration = 60000; // 1 minute
      const requestInterval = 100; // 100ms between requests
      const maxResponseTime = 3000; // 3 seconds max
      
      const startTime = Date.now();
      const measurements = [];
      let requestCount = 0;
      let timeoutCount = 0;
      let errorCount = 0;
      
      console.log(`🚀 Starting sustained load test (${duration/1000}s)...`);
      
      while (Date.now() - startTime < duration) {
        const reqStartTime = performance.now();
        
        try {
          const response = await request(baseUrl).get('/health').timeout(maxResponseTime);
          const responseTime = performance.now() - reqStartTime;
          
          if (response.status === 200) {
            measurements.push(responseTime);
          } else {
            errorCount++;
          }
        } catch (error) {
          if (error.timeout) {
            timeoutCount++;
          } else {
            errorCount++;
          }
        }
        
        requestCount++;
        await new Promise(resolve => setTimeout(resolve, requestInterval));
      }
      
      const actualDuration = Date.now() - startTime;
      const successfulRequests = measurements.length;
      const successRate = (successfulRequests / requestCount * 100).toFixed(2);
      const avgResponseTime = measurements.length > 0 
        ? measurements.reduce((a, b) => a + b, 0) / measurements.length 
        : 0;
      
      console.log(`📊 Sustained load test results:`);
      console.log(`   Duration: ${actualDuration/1000}s`);
      console.log(`   Total requests: ${requestCount}`);
      console.log(`   Successful: ${successfulRequests}`);
      console.log(`   Timeouts: ${timeoutCount}`);
      console.log(`   Errors: ${errorCount}`);
      console.log(`   Success rate: ${successRate}%`);
      console.log(`   Average response time: ${avgResponseTime.toFixed(2)}ms`);
      
      // Performance requirements
      expect(parseFloat(successRate)).toBeGreaterThan(95); // 95% success rate
      expect(avgResponseTime).toBeLessThan(2000); // 2s average response time
      expect(timeoutCount / requestCount).toBeLessThan(0.02); // Less than 2% timeouts
    });
  });

  describe('Concurrent Load Handling', () => {
    test('should handle concurrent requests efficiently', async () => {
      const concurrentUsers = [5, 10, 20, 50];
      const results = {};
      
      for (const userCount of concurrentUsers) {
        console.log(`🔄 Testing ${userCount} concurrent users...`);
        
        const promises = Array.from({ length: userCount }, async (_, i) => {
          const startTime = performance.now();
          
          try {
            const response = await request(baseUrl)
              .get('/health')
              .timeout(10000); // 10 second timeout
              
            return {
              success: response.status === 200,
              responseTime: performance.now() - startTime,
              userId: i
            };
          } catch (error) {
            return {
              success: false,
              responseTime: performance.now() - startTime,
              userId: i,
              error: error.message
            };
          }
        });
        
        const responses = await Promise.all(promises);
        
        const successful = responses.filter(r => r.success);
        const failed = responses.filter(r => !r.success);
        const avgResponseTime = successful.length > 0 
          ? successful.reduce((sum, r) => sum + r.responseTime, 0) / successful.length 
          : 0;
        
        results[userCount] = {
          successful: successful.length,
          failed: failed.length,
          successRate: (successful.length / userCount * 100).toFixed(2),
          avgResponseTime: avgResponseTime.toFixed(2)
        };
        
        console.log(`   Success rate: ${results[userCount].successRate}%`);
        console.log(`   Average response time: ${results[userCount].avgResponseTime}ms`);
        
        // Requirements for concurrent load
        expect(parseFloat(results[userCount].successRate)).toBeGreaterThan(90);
        expect(avgResponseTime).toBeLessThan(5000); // 5 seconds max
      }
      
      console.log('📊 Concurrent load test summary:', results);
    });

    test('should handle database operations under load', async () => {
      const concurrentOperations = 20;
      
      const operations = Array.from({ length: concurrentOperations }, async (_, i) => {
        const startTime = performance.now();
        
        try {
          // Test database read operation
          const response = await request(baseUrl)
            .get(`/api/v1/status/database/read-test?id=${i}`)
            .timeout(15000);
            
          return {
            success: response.status === 200,
            responseTime: performance.now() - startTime,
            operationId: i
          };
        } catch (error) {
          return {
            success: false,
            responseTime: performance.now() - startTime,
            operationId: i,
            error: error.message
          };
        }
      });
      
      const results = await Promise.all(operations);
      
      const successful = results.filter(r => r.success);
      const avgResponseTime = successful.length > 0 
        ? successful.reduce((sum, r) => sum + r.responseTime, 0) / successful.length 
        : 0;
      const successRate = (successful.length / concurrentOperations * 100);
      
      console.log(`📊 Database load test:`);
      console.log(`   Concurrent operations: ${concurrentOperations}`);
      console.log(`   Successful: ${successful.length}`);
      console.log(`   Success rate: ${successRate.toFixed(2)}%`);
      console.log(`   Average response time: ${avgResponseTime.toFixed(2)}ms`);
      
      expect(successRate).toBeGreaterThan(85); // 85% success rate for database operations
      expect(avgResponseTime).toBeLessThan(3000); // 3 seconds max for database operations
    });

    test('should handle file upload operations under load', async () => {
      const concurrentUploads = 10;
      const fileSize = 1024; // 1KB test files
      
      const uploads = Array.from({ length: concurrentUploads }, async (_, i) => {
        const startTime = performance.now();
        const testData = Buffer.alloc(fileSize, `test-${i}`);
        
        try {
          const response = await request(baseUrl)
            .post('/api/v1/status/upload-test')
            .attach('file', testData, `test-${i}.txt`)
            .timeout(30000);
            
          return {
            success: response.status === 200,
            responseTime: performance.now() - startTime,
            uploadId: i,
            fileSize: testData.length
          };
        } catch (error) {
          return {
            success: false,
            responseTime: performance.now() - startTime,
            uploadId: i,
            error: error.message
          };
        }
      });
      
      const results = await Promise.all(uploads);
      
      const successful = results.filter(r => r.success);
      const avgResponseTime = successful.length > 0 
        ? successful.reduce((sum, r) => sum + r.responseTime, 0) / successful.length 
        : 0;
      const successRate = (successful.length / concurrentUploads * 100);
      
      console.log(`📊 File upload load test:`);
      console.log(`   Concurrent uploads: ${concurrentUploads}`);
      console.log(`   File size: ${fileSize} bytes each`);
      console.log(`   Successful: ${successful.length}`);
      console.log(`   Success rate: ${successRate.toFixed(2)}%`);
      console.log(`   Average response time: ${avgResponseTime.toFixed(2)}ms`);
      
      if (successful.length > 0) {
        expect(successRate).toBeGreaterThan(80); // 80% success rate for file uploads
        expect(avgResponseTime).toBeLessThan(10000); // 10 seconds max for uploads
      }
    });
  });

  describe('Memory and Resource Utilization', () => {
    test('should maintain stable memory usage under load', async () => {
      // Get initial memory usage
      const initialMemory = await request(baseUrl)
        .get('/api/v1/status/memory')
        .expect(200);
      
      console.log(`📊 Initial memory usage: ${(initialMemory.body.heapUsed / 1024 / 1024).toFixed(2)} MB`);
      
      // Generate memory pressure
      const loadTestDuration = 30000; // 30 seconds
      const requestInterval = 50; // 50ms between requests
      let requestCount = 0;
      
      const startTime = Date.now();
      const memorySnapshots = [];
      
      while (Date.now() - startTime < loadTestDuration) {
        // Make request with some data
        await request(baseUrl)
          .post('/api/v1/status/memory-test')
          .send({ data: 'x'.repeat(1000) }) // 1KB of data
          .timeout(5000);
        
        requestCount++;
        
        // Take memory snapshot every 100 requests
        if (requestCount % 100 === 0) {
          try {
            const memoryResponse = await request(baseUrl)
              .get('/api/v1/status/memory')
              .timeout(2000);
            
            memorySnapshots.push({
              timestamp: Date.now() - startTime,
              heapUsed: memoryResponse.body.heapUsed,
              heapTotal: memoryResponse.body.heapTotal,
              external: memoryResponse.body.external
            });
          } catch (error) {
            // Continue if memory endpoint fails
          }
        }
        
        await new Promise(resolve => setTimeout(resolve, requestInterval));
      }
      
      // Get final memory usage
      const finalMemory = await request(baseUrl)
        .get('/api/v1/status/memory')
        .expect(200);
      
      const initialHeapMB = initialMemory.body.heapUsed / 1024 / 1024;
      const finalHeapMB = finalMemory.body.heapUsed / 1024 / 1024;
      const memoryIncrease = finalHeapMB - initialHeapMB;
      
      console.log(`📊 Memory usage after load test:`);
      console.log(`   Initial heap: ${initialHeapMB.toFixed(2)} MB`);
      console.log(`   Final heap: ${finalHeapMB.toFixed(2)} MB`);
      console.log(`   Memory increase: ${memoryIncrease.toFixed(2)} MB`);
      console.log(`   Requests processed: ${requestCount}`);
      
      // Memory should not grow excessively
      expect(memoryIncrease).toBeLessThan(100); // Less than 100MB increase
      expect(finalHeapMB).toBeLessThan(500); // Total heap usage under 500MB
    });

    test('should handle garbage collection efficiently', async () => {
      // Trigger garbage collection test
      const response = await request(baseUrl)
        .post('/api/v1/status/gc-test')
        .send({ iterations: 1000 })
        .timeout(30000)
        .expect(200);
      
      expect(response.body).toHaveProperty('success', true);
      expect(response.body).toHaveProperty('gcStats');
      
      const gcStats = response.body.gcStats;
      console.log(`📊 Garbage collection stats:`);
      console.log(`   GC runs: ${gcStats.collections}`);
      console.log(`   GC time: ${gcStats.duration}ms`);
      console.log(`   Memory freed: ${(gcStats.memoryFreed / 1024 / 1024).toFixed(2)} MB`);
      
      // GC should be efficient
      expect(gcStats.collections).toBeGreaterThan(0);
      expect(gcStats.duration).toBeLessThan(5000); // Less than 5 seconds total GC time
    });

    test('should detect and prevent memory leaks', async () => {
      const iterations = 50;
      const memorySnapshots = [];
      
      for (let i = 0; i < iterations; i++) {
        // Create some temporary data
        await request(baseUrl)
          .post('/api/v1/status/memory-leak-test')
          .send({ iteration: i, size: 10000 })
          .timeout(5000);
        
        // Take memory snapshot every 10 iterations
        if (i % 10 === 0) {
          const memoryResponse = await request(baseUrl)
            .get('/api/v1/status/memory')
            .timeout(2000);
          
          memorySnapshots.push({
            iteration: i,
            heapUsed: memoryResponse.body.heapUsed,
            timestamp: Date.now()
          });
        }
        
        await new Promise(resolve => setTimeout(resolve, 100));
      }
      
      // Analyze memory growth trend
      if (memorySnapshots.length >= 3) {
        const firstSnapshot = memorySnapshots[0];
        const lastSnapshot = memorySnapshots[memorySnapshots.length - 1];
        const memoryGrowth = (lastSnapshot.heapUsed - firstSnapshot.heapUsed) / 1024 / 1024;
        
        console.log(`📊 Memory leak test:`);
        console.log(`   Iterations: ${iterations}`);
        console.log(`   Memory growth: ${memoryGrowth.toFixed(2)} MB`);
        console.log(`   Growth per iteration: ${(memoryGrowth / iterations * 1024).toFixed(2)} KB`);
        
        // Memory growth should be minimal
        expect(memoryGrowth).toBeLessThan(50); // Less than 50MB growth
      }
    });
  });

  describe('Performance Regression Detection', () => {
    test('should maintain baseline performance characteristics', async () => {
      // Re-measure current performance
      const currentMeasurements = [];
      
      for (let i = 0; i < 20; i++) {
        const startTime = performance.now();
        await request(baseUrl).get('/health').expect(200);
        const responseTime = performance.now() - startTime;
        currentMeasurements.push(responseTime);
        
        await new Promise(resolve => setTimeout(resolve, 20));
      }
      
      const avgCurrentTime = currentMeasurements.reduce((a, b) => a + b, 0) / currentMeasurements.length;
      const baselineTime = performanceBaseline.healthCheckResponseTime;
      
      const performanceRatio = avgCurrentTime / baselineTime;
      
      console.log(`📊 Performance regression check:`);
      console.log(`   Baseline response time: ${baselineTime.toFixed(2)}ms`);
      console.log(`   Current average time: ${avgCurrentTime.toFixed(2)}ms`);
      console.log(`   Performance ratio: ${performanceRatio.toFixed(2)}x`);
      
      // Performance should not degrade significantly
      expect(performanceRatio).toBeLessThan(3.0); // No more than 3x slower
      
      if (performanceRatio > 1.5) {
        console.warn(`⚠️  Performance degradation detected: ${performanceRatio.toFixed(2)}x slower than baseline`);
      }
    });

    test('should validate performance under realistic user patterns', async () => {
      // Simulate realistic user behavior patterns
      const userJourneys = [
        ['GET', '/health'],
        ['GET', '/api/v1/status'],
        ['GET', '/api/v1/status/database'],
        ['POST', '/api/v1/status/memory-test', { data: 'test' }]
      ];
      
      const concurrentUsers = 5;
      const journeyResults = [];
      
      const userSimulations = Array.from({ length: concurrentUsers }, async (_, userId) => {
        const userStartTime = performance.now();
        const userResults = [];
        
        for (const [method, path, data] of userJourneys) {
          const stepStartTime = performance.now();
          
          try {
            let response;
            if (method === 'POST') {
              response = await request(baseUrl)
                .post(path)
                .send(data || {})
                .timeout(10000);
            } else {
              response = await request(baseUrl)
                .get(path)
                .timeout(10000);
            }
            
            userResults.push({
              method,
              path,
              success: response.status >= 200 && response.status < 400,
              responseTime: performance.now() - stepStartTime
            });
          } catch (error) {
            userResults.push({
              method,
              path,
              success: false,
              responseTime: performance.now() - stepStartTime,
              error: error.message
            });
          }
          
          // Realistic delay between requests
          await new Promise(resolve => setTimeout(resolve, 200 + Math.random() * 800));
        }
        
        return {
          userId,
          totalTime: performance.now() - userStartTime,
          steps: userResults,
          success: userResults.every(step => step.success)
        };
      });
      
      const results = await Promise.all(userSimulations);
      
      const successfulJourneys = results.filter(r => r.success);
      const avgJourneyTime = successfulJourneys.length > 0 
        ? successfulJourneys.reduce((sum, r) => sum + r.totalTime, 0) / successfulJourneys.length
        : 0;
      
      console.log(`📊 User journey simulation:`);
      console.log(`   Concurrent users: ${concurrentUsers}`);
      console.log(`   Successful journeys: ${successfulJourneys.length}/${concurrentUsers}`);
      console.log(`   Average journey time: ${avgJourneyTime.toFixed(2)}ms`);
      
      expect(successfulJourneys.length).toBe(concurrentUsers); // All journeys should succeed
      expect(avgJourneyTime).toBeLessThan(15000); // Complete user journey under 15 seconds
    });
  });
});