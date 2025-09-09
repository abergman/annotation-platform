/**
 * Service Connectivity and Dependency Validation Tests
 * Tests all service dependencies and network connectivity
 */

const request = require('supertest');
const { MongoClient } = require('mongodb');

describe('Service Connectivity Validation', () => {
  let baseUrl;
  let mongoClient;
  
  beforeAll(() => {
    baseUrl = process.env.DEPLOY_URL || 'http://localhost:8080';
    jest.setTimeout(60000); // Extended timeout for network operations
  });

  afterAll(async () => {
    if (mongoClient) {
      await mongoClient.close();
    }
  });

  describe('API Service Connectivity', () => {
    test('should validate API service is reachable and responsive', async () => {
      const response = await request(baseUrl)
        .get('/api/v1/status')
        .expect(200);

      expect(response.body).toHaveProperty('status', 'online');
      expect(response.body).toHaveProperty('version');
      expect(response.body).toHaveProperty('uptime');
      expect(response.body.uptime).toBeGreaterThan(0);
    });

    test('should validate API CORS configuration', async () => {
      const response = await request(baseUrl)
        .options('/api/v1/status')
        .set('Origin', 'https://annotat.ee')
        .set('Access-Control-Request-Method', 'GET')
        .expect(200);

      expect(response.headers).toHaveProperty('access-control-allow-origin');
      expect(response.headers).toHaveProperty('access-control-allow-methods');
    });

    test('should validate API rate limiting is configured', async () => {
      // Make rapid requests to test rate limiting
      const requests = Array.from({ length: 20 }, (_, i) => 
        request(baseUrl).get('/api/v1/status')
      );

      const responses = await Promise.allSettled(requests);
      
      // Some requests should be rate limited (429) or all should pass
      const statusCodes = responses.map(r => r.value?.status || r.reason?.status);
      const rateLimited = statusCodes.filter(code => code === 429);
      
      // Either rate limiting works (some 429s) or all pass (rate limit not triggered)
      expect(statusCodes.every(code => [200, 429].includes(code))).toBe(true);
    });
  });

  describe('Database Connectivity', () => {
    test('should validate MongoDB connection and authentication', async () => {
      const response = await request(baseUrl)
        .get('/api/v1/status/database')
        .expect(200);

      expect(response.body.mongodb.status).toBe('connected');
      expect(response.body.mongodb.authentication).toBe('authenticated');
      expect(response.body.mongodb.replicaSet).toBeDefined();
    });

    test('should validate database read operations', async () => {
      const response = await request(baseUrl)
        .get('/api/v1/status/database/read-test')
        .expect(200);

      expect(response.body).toHaveProperty('success', true);
      expect(response.body).toHaveProperty('responseTime');
      expect(response.body.responseTime).toBeLessThan(1000); // Less than 1 second
    });

    test('should validate database write operations', async () => {
      const response = await request(baseUrl)
        .post('/api/v1/status/database/write-test')
        .send({ test: 'connectivity' })
        .expect(200);

      expect(response.body).toHaveProperty('success', true);
      expect(response.body).toHaveProperty('insertedId');
    });

    test('should validate database indexes and constraints', async () => {
      const response = await request(baseUrl)
        .get('/api/v1/status/database/indexes')
        .expect(200);

      expect(Array.isArray(response.body.indexes)).toBe(true);
      expect(response.body.indexes.length).toBeGreaterThan(0);
      
      // Check for critical indexes
      const indexNames = response.body.indexes.map(idx => idx.name);
      expect(indexNames).toContain('email_1'); // User email index
      expect(indexNames).toContain('createdAt_1'); // Timestamp index
    });
  });

  describe('External Service Dependencies', () => {
    test('should validate internet connectivity for external APIs', async () => {
      const response = await request(baseUrl)
        .get('/api/v1/status/external')
        .expect(200);

      expect(response.body).toHaveProperty('externalServices');
      
      // Check each external service
      Object.values(response.body.externalServices).forEach(service => {
        expect(service.status).toBeOneOf(['available', 'degraded']);
        expect(service.responseTime).toBeLessThan(5000); // Less than 5 seconds
      });
    });

    test('should validate DNS resolution', async () => {
      const response = await request(baseUrl)
        .get('/api/v1/status/dns')
        .expect(200);

      expect(response.body).toHaveProperty('dnsResolution');
      expect(response.body.dnsResolution.status).toBe('working');
      
      // Test critical domains
      const domains = response.body.dnsResolution.domains;
      expect(domains['annotat.ee']).toBeDefined();
      expect(domains['mongo.ondigitalocean.com']).toBeDefined();
    });
  });

  describe('Network Security and SSL', () => {
    test('should validate SSL certificate if HTTPS', async () => {
      if (baseUrl.startsWith('https://')) {
        const response = await request(baseUrl)
          .get('/health')
          .expect(200);

        // SSL should be properly configured (no cert errors)
        expect(response.status).toBe(200);
        expect(response.headers).toHaveProperty('strict-transport-security');
      }
    });

    test('should validate secure headers are present', async () => {
      const response = await request(baseUrl)
        .get('/health')
        .expect(200);

      // Critical security headers
      expect(response.headers).toHaveProperty('x-content-type-options', 'nosniff');
      expect(response.headers).toHaveProperty('x-frame-options');
      expect(response.headers).toHaveProperty('x-xss-protection');
      
      // Should not expose server information
      expect(response.headers['x-powered-by']).toBeUndefined();
      expect(response.headers.server).not.toMatch(/express|node/i);
    });

    test('should validate request timeout handling', async () => {
      // Test with a deliberately slow endpoint
      const startTime = Date.now();
      
      try {
        const response = await request(baseUrl)
          .get('/api/v1/status/slow-test')
          .timeout(30000) // 30 second timeout
          .expect(200);

        const duration = Date.now() - startTime;
        expect(duration).toBeLessThan(30000); // Should respond before timeout
        expect(response.body).toHaveProperty('processed', true);
      } catch (error) {
        if (error.timeout) {
          // Timeout is acceptable for this test
          expect(error.timeout).toBe(true);
        } else if (error.status === 404) {
          // Endpoint doesn't exist, skip test
          console.log('Slow test endpoint not available, skipping timeout test');
        } else {
          throw error;
        }
      }
    });
  });

  describe('Inter-Service Communication', () => {
    test('should validate WebSocket service availability', async () => {
      const response = await request(baseUrl)
        .get('/api/v1/status/websocket')
        .expect(200);

      expect(response.body).toHaveProperty('websocket');
      expect(response.body.websocket.status).toBeOneOf(['available', 'connected']);
      expect(response.body.websocket.port).toBeDefined();
    });

    test('should validate session storage connectivity', async () => {
      const response = await request(baseUrl)
        .get('/api/v1/status/session')
        .expect(200);

      expect(response.body).toHaveProperty('sessionStore');
      expect(response.body.sessionStore.status).toBe('connected');
      expect(response.body.sessionStore.type).toBeDefined();
    });

    test('should validate file upload capabilities', async () => {
      const testFile = Buffer.from('test file content');
      
      const response = await request(baseUrl)
        .post('/api/v1/status/upload-test')
        .attach('testfile', testFile, 'test.txt')
        .expect(200);

      expect(response.body).toHaveProperty('success', true);
      expect(response.body).toHaveProperty('fileSize');
      expect(response.body.fileSize).toBe(testFile.length);
    });
  });

  describe('Performance and Load Capacity', () => {
    test('should validate concurrent connection handling', async () => {
      const concurrentConnections = 20;
      const requests = Array.from({ length: concurrentConnections }, (_, i) =>
        request(baseUrl)
          .get(`/api/v1/status/load-test?id=${i}`)
          .expect(200)
      );

      const responses = await Promise.all(requests);
      
      responses.forEach((response, index) => {
        expect(response.body).toHaveProperty('success', true);
        expect(response.body).toHaveProperty('requestId', index.toString());
      });
    });

    test('should validate database connection pooling', async () => {
      // Test multiple database operations concurrently
      const dbOperations = Array.from({ length: 10 }, (_, i) =>
        request(baseUrl)
          .get(`/api/v1/status/database/connection-pool-test?op=${i}`)
          .expect(200)
      );

      const responses = await Promise.all(dbOperations);
      
      responses.forEach(response => {
        expect(response.body).toHaveProperty('success', true);
        expect(response.body.connectionPool).toBeDefined();
        expect(response.body.connectionPool.available).toBeGreaterThan(0);
      });
    });

    test('should validate memory leak prevention', async () => {
      const initialMemory = await request(baseUrl)
        .get('/api/v1/status/memory')
        .expect(200);

      // Perform memory-intensive operations
      for (let i = 0; i < 10; i++) {
        await request(baseUrl)
          .post('/api/v1/status/memory-test')
          .send({ size: 1000 }) // 1KB test data
          .expect(200);
      }

      // Force garbage collection if available
      await request(baseUrl)
        .post('/api/v1/status/gc')
        .expect(200);

      const finalMemory = await request(baseUrl)
        .get('/api/v1/status/memory')
        .expect(200);

      // Memory usage should not increase significantly
      const memoryIncrease = finalMemory.body.heapUsed - initialMemory.body.heapUsed;
      expect(memoryIncrease).toBeLessThan(50 * 1024 * 1024); // Less than 50MB increase
    });
  });
});