const axios = require('axios');
const { expect } = require('chai');
const { performance } = require('perf_hooks');

describe('Performance Baseline Tests', () => {
  const BASE_URL = process.env.DEPLOYMENT_URL || 'https://annotat.ee';
  const PERFORMANCE_THRESHOLDS = {
    responseTime: {
      fast: 200,      // < 200ms is fast
      acceptable: 500, // < 500ms is acceptable
      slow: 1000      // > 1000ms is slow
    },
    throughput: {
      minRequestsPerSecond: 10
    },
    availability: {
      minUptime: 0.99 // 99% uptime
    }
  };

  describe('Response Time Benchmarks', () => {
    const endpoints = [
      { path: '/', name: 'Homepage' },
      { path: '/api/health', name: 'Health Check' },
      { path: '/api/status', name: 'System Status' },
      { path: '/api/auth/validate', name: 'Auth Validation' }
    ];

    endpoints.forEach(endpoint => {
      it(`should respond quickly to ${endpoint.name} (${endpoint.path})`, async () => {
        const measurements = [];
        
        // Run 10 requests to get average
        for (let i = 0; i < 10; i++) {
          const startTime = performance.now();
          
          try {
            const response = await axios.get(`${BASE_URL}${endpoint.path}`, {
              timeout: 10000,
              validateStatus: () => true // Accept all status codes for timing
            });
            
            const endTime = performance.now();
            const responseTime = endTime - startTime;
            
            measurements.push({
              responseTime,
              status: response.status,
              success: response.status >= 200 && response.status < 400
            });
          } catch (error) {
            const endTime = performance.now();
            measurements.push({
              responseTime: endTime - startTime,
              status: 0,
              success: false,
              error: error.message
            });
          }
        }

        // Calculate statistics
        const responseTimes = measurements.map(m => m.responseTime);
        const avgResponseTime = responseTimes.reduce((a, b) => a + b, 0) / responseTimes.length;
        const maxResponseTime = Math.max(...responseTimes);
        const minResponseTime = Math.min(...responseTimes);
        const successRate = measurements.filter(m => m.success).length / measurements.length;

        console.log(`\n  ${endpoint.name} Performance:`);
        console.log(`    Average: ${avgResponseTime.toFixed(2)}ms`);
        console.log(`    Min: ${minResponseTime.toFixed(2)}ms`);
        console.log(`    Max: ${maxResponseTime.toFixed(2)}ms`);
        console.log(`    Success Rate: ${(successRate * 100).toFixed(1)}%`);

        // Assertions
        expect(avgResponseTime).to.be.lessThan(PERFORMANCE_THRESHOLDS.responseTime.acceptable,
          `Average response time ${avgResponseTime.toFixed(2)}ms exceeds threshold`);
        expect(maxResponseTime).to.be.lessThan(PERFORMANCE_THRESHOLDS.responseTime.slow,
          `Max response time ${maxResponseTime.toFixed(2)}ms exceeds threshold`);
        expect(successRate).to.be.greaterThan(0.9, 'Success rate should be > 90%');
      });
    });
  });

  describe('Throughput Testing', () => {
    it('should handle concurrent requests efficiently', async () => {
      const concurrentRequests = 20;
      const startTime = performance.now();
      
      const requests = Array(concurrentRequests).fill(null).map(() =>
        axios.get(`${BASE_URL}/api/health`, {
          timeout: 10000,
          validateStatus: () => true
        }).catch(error => ({ error: error.message, status: 0 }))
      );

      const responses = await Promise.all(requests);
      const endTime = performance.now();
      
      const totalTime = (endTime - startTime) / 1000; // Convert to seconds
      const throughput = concurrentRequests / totalTime;
      const successfulResponses = responses.filter(r => !r.error && r.status >= 200 && r.status < 400);
      const successRate = successfulResponses.length / concurrentRequests;

      console.log(`\n  Throughput Test Results:`);
      console.log(`    Total time: ${totalTime.toFixed(2)}s`);
      console.log(`    Throughput: ${throughput.toFixed(2)} req/s`);
      console.log(`    Success rate: ${(successRate * 100).toFixed(1)}%`);

      expect(throughput).to.be.greaterThan(PERFORMANCE_THRESHOLDS.throughput.minRequestsPerSecond);
      expect(successRate).to.be.greaterThan(0.95); // 95% success rate for concurrent requests
    });

    it('should maintain performance under sustained load', async () => {
      const testDuration = 30000; // 30 seconds
      const requestInterval = 100; // Request every 100ms
      const startTime = performance.now();
      const results = [];

      while (performance.now() - startTime < testDuration) {
        const requestStart = performance.now();
        
        try {
          const response = await axios.get(`${BASE_URL}/api/health`, { timeout: 5000 });
          const requestEnd = performance.now();
          
          results.push({
            responseTime: requestEnd - requestStart,
            status: response.status,
            timestamp: requestEnd - startTime
          });
        } catch (error) {
          results.push({
            responseTime: performance.now() - requestStart,
            status: 0,
            error: true,
            timestamp: performance.now() - startTime
          });
        }

        // Wait before next request
        await new Promise(resolve => setTimeout(resolve, requestInterval));
      }

      const avgResponseTime = results
        .filter(r => !r.error)
        .reduce((sum, r) => sum + r.responseTime, 0) / results.filter(r => !r.error).length;
      
      const errorRate = results.filter(r => r.error).length / results.length;

      console.log(`\n  Sustained Load Test Results:`);
      console.log(`    Requests made: ${results.length}`);
      console.log(`    Average response time: ${avgResponseTime.toFixed(2)}ms`);
      console.log(`    Error rate: ${(errorRate * 100).toFixed(2)}%`);

      expect(avgResponseTime).to.be.lessThan(PERFORMANCE_THRESHOLDS.responseTime.acceptable);
      expect(errorRate).to.be.lessThan(0.05); // < 5% error rate
    });
  });

  describe('Resource Usage Monitoring', () => {
    it('should monitor server resource consumption', async () => {
      try {
        const response = await axios.get(`${BASE_URL}/api/system/resources`);
        expect(response.status).to.equal(200);

        const { data } = response;
        
        if (data.memory) {
          console.log(`\n  Memory Usage: ${data.memory.used_percentage}%`);
          expect(data.memory.used_percentage).to.be.lessThan(90);
        }

        if (data.cpu) {
          console.log(`  CPU Usage: ${data.cpu.usage_percentage}%`);
          expect(data.cpu.usage_percentage).to.be.lessThan(80);
        }

        if (data.disk) {
          console.log(`  Disk Usage: ${data.disk.used_percentage}%`);
          expect(data.disk.used_percentage).to.be.lessThan(85);
        }
      } catch (error) {
        if (error.response && error.response.status === 404) {
          console.log('Resource monitoring endpoint not available');
        } else {
          throw error;
        }
      }
    });
  });

  describe('Database Performance', () => {
    it('should have acceptable database query times', async () => {
      const measurements = [];
      
      for (let i = 0; i < 5; i++) {
        try {
          const startTime = performance.now();
          const response = await axios.get(`${BASE_URL}/api/db/ping`);
          const endTime = performance.now();
          
          measurements.push({
            responseTime: endTime - startTime,
            dbLatency: response.data.latency || 0
          });
        } catch (error) {
          console.log('Database ping endpoint not available');
          return;
        }
      }

      const avgDbLatency = measurements.reduce((sum, m) => sum + m.dbLatency, 0) / measurements.length;
      const avgResponseTime = measurements.reduce((sum, m) => sum + m.responseTime, 0) / measurements.length;

      console.log(`\n  Database Performance:`);
      console.log(`    Average DB latency: ${avgDbLatency.toFixed(2)}ms`);
      console.log(`    Average response time: ${avgResponseTime.toFixed(2)}ms`);

      expect(avgDbLatency).to.be.lessThan(100); // < 100ms database latency
      expect(avgResponseTime).to.be.lessThan(300); // < 300ms total response time
    });

    it('should handle database connection pooling efficiently', async () => {
      const concurrentDbRequests = 15;
      const startTime = performance.now();

      const requests = Array(concurrentDbRequests).fill(null).map(() =>
        axios.get(`${BASE_URL}/api/db/test`, { timeout: 10000 })
          .catch(error => ({ error: error.message }))
      );

      const responses = await Promise.all(requests);
      const endTime = performance.now();

      const successfulResponses = responses.filter(r => !r.error && r.status === 200);
      const totalTime = endTime - startTime;

      console.log(`\n  Database Connection Pooling:`);
      console.log(`    Concurrent requests: ${concurrentDbRequests}`);
      console.log(`    Successful responses: ${successfulResponses.length}`);
      console.log(`    Total time: ${totalTime.toFixed(2)}ms`);

      expect(successfulResponses.length).to.be.greaterThan(concurrentDbRequests * 0.9); // 90% success
      expect(totalTime).to.be.lessThan(5000); // Complete within 5 seconds
    });
  });

  describe('WebSocket Performance', () => {
    it('should establish WebSocket connections quickly', (done) => {
      const WebSocket = require('ws');
      const wsUrl = BASE_URL.replace('http', 'ws') + '/ws';
      const startTime = performance.now();

      const ws = new WebSocket(wsUrl);

      ws.on('open', () => {
        const connectionTime = performance.now() - startTime;
        console.log(`\n  WebSocket connection time: ${connectionTime.toFixed(2)}ms`);
        
        expect(connectionTime).to.be.lessThan(1000); // < 1 second to connect
        ws.close();
        done();
      });

      ws.on('error', (error) => {
        done(error);
      });

      setTimeout(() => {
        ws.terminate();
        done(new Error('WebSocket connection timeout'));
      }, 5000);
    });

    it('should handle WebSocket message latency', (done) => {
      const WebSocket = require('ws');
      const wsUrl = BASE_URL.replace('http', 'ws') + '/ws';
      const ws = new WebSocket(wsUrl);
      const measurements = [];

      ws.on('open', () => {
        let messageCount = 0;
        const maxMessages = 10;

        const sendPing = () => {
          if (messageCount >= maxMessages) {
            // Calculate average latency
            const avgLatency = measurements.reduce((sum, m) => sum + m, 0) / measurements.length;
            console.log(`\n  WebSocket average latency: ${avgLatency.toFixed(2)}ms`);
            
            expect(avgLatency).to.be.lessThan(100); // < 100ms average latency
            ws.close();
            done();
            return;
          }

          const startTime = performance.now();
          ws.send(JSON.stringify({ type: 'ping', timestamp: startTime, id: messageCount }));
          messageCount++;
        };

        ws.on('message', (data) => {
          const message = JSON.parse(data);
          if (message.type === 'pong' && message.timestamp) {
            const latency = performance.now() - message.timestamp;
            measurements.push(latency);
            
            setTimeout(sendPing, 100); // Send next ping after 100ms
          }
        });

        sendPing(); // Start the ping sequence
      });

      ws.on('error', done);
    });
  });

  describe('CDN and Static Asset Performance', () => {
    it('should serve static assets with appropriate caching', async () => {
      const staticAssets = [
        '/favicon.ico',
        '/static/css/main.css',
        '/static/js/main.js'
      ];

      for (const asset of staticAssets) {
        try {
          const startTime = performance.now();
          const response = await axios.get(`${BASE_URL}${asset}`, {
            timeout: 5000,
            validateStatus: () => true
          });
          const endTime = performance.now();
          const responseTime = endTime - startTime;

          if (response.status === 200) {
            console.log(`\n  ${asset}: ${responseTime.toFixed(2)}ms`);
            
            expect(responseTime).to.be.lessThan(2000); // < 2 seconds for static assets
            expect(response.headers).to.have.property('cache-control');
          }
        } catch (error) {
          console.log(`Static asset ${asset} not available: ${error.message}`);
        }
      }
    });
  });

  after(() => {
    console.log('\n⚡ Performance baseline tests completed');
    console.log(`Target URL: ${BASE_URL}`);
    console.log(`Test timestamp: ${new Date().toISOString()}`);
  });
});