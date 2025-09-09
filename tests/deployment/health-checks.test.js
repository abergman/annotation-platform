/**
 * Deployment Health Check Validation Tests
 * Tests all health check endpoints and validates service availability
 */

const request = require('supertest');
const { execSync } = require('child_process');

describe('Deployment Health Check Validation', () => {
  let baseUrl;
  
  beforeAll(() => {
    // Determine base URL based on environment
    baseUrl = process.env.DEPLOY_URL || 'http://localhost:8080';
    
    // Wait for services to be ready
    console.log(`Testing deployment at: ${baseUrl}`);
    
    // Give services time to initialize
    if (process.env.CI) {
      jest.setTimeout(120000); // 2 minutes for CI
    } else {
      jest.setTimeout(60000); // 1 minute for local
    }
  });

  describe('Primary API Health Check', () => {
    test('should respond to /health endpoint', async () => {
      const response = await request(baseUrl)
        .get('/health')
        .expect(200);

      expect(response.body).toHaveProperty('status');
      expect(response.body.status).toBe('healthy');
      expect(response.body).toHaveProperty('timestamp');
      expect(response.body).toHaveProperty('version');
      expect(response.body).toHaveProperty('services');
    });

    test('should validate database connectivity in health check', async () => {
      const response = await request(baseUrl)
        .get('/health')
        .expect(200);

      expect(response.body.services).toHaveProperty('database');
      expect(response.body.services.database.status).toBe('connected');
    });

    test('should validate memory and CPU usage in health check', async () => {
      const response = await request(baseUrl)
        .get('/health')
        .expect(200);

      expect(response.body).toHaveProperty('system');
      expect(response.body.system).toHaveProperty('memory');
      expect(response.body.system).toHaveProperty('cpu');
      expect(response.body.system.memory.usage).toBeLessThan(90); // Less than 90% memory usage
    });
  });

  describe('Service Readiness Checks', () => {
    test('should validate API readiness endpoint', async () => {
      const response = await request(baseUrl)
        .get('/ready')
        .expect(200);

      expect(response.body).toHaveProperty('ready', true);
      expect(response.body).toHaveProperty('checks');
      
      // All readiness checks should pass
      Object.values(response.body.checks).forEach(check => {
        expect(check.status).toBe('pass');
      });
    });

    test('should validate liveness endpoint with proper response time', async () => {
      const startTime = Date.now();
      
      const response = await request(baseUrl)
        .get('/health')
        .expect(200);

      const responseTime = Date.now() - startTime;
      expect(responseTime).toBeLessThan(5000); // Should respond within 5 seconds
    });
  });

  describe('Environment Configuration Validation', () => {
    test('should validate required environment variables are loaded', async () => {
      const response = await request(baseUrl)
        .get('/health')
        .expect(200);

      expect(response.body).toHaveProperty('environment');
      expect(response.body.environment.NODE_ENV).toBe('production');
      expect(response.body.environment.PORT).toBe('8080');
      
      // Sensitive vars should not be exposed
      expect(response.body.environment).not.toHaveProperty('JWT_SECRET');
      expect(response.body.environment).not.toHaveProperty('MONGODB_URI');
    });

    test('should validate security headers are present', async () => {
      const response = await request(baseUrl)
        .get('/health')
        .expect(200);

      expect(response.headers).toHaveProperty('x-content-type-options', 'nosniff');
      expect(response.headers).toHaveProperty('x-frame-options', 'DENY');
      expect(response.headers).toHaveProperty('x-xss-protection', '1; mode=block');
    });
  });

  describe('Database Connection Validation', () => {
    test('should validate MongoDB connection', async () => {
      const response = await request(baseUrl)
        .get('/api/v1/status/database')
        .expect(200);

      expect(response.body).toHaveProperty('mongodb');
      expect(response.body.mongodb.status).toBe('connected');
      expect(response.body.mongodb).toHaveProperty('readyState', 1);
      expect(response.body.mongodb).toHaveProperty('ping');
      expect(response.body.mongodb.ping).toBeLessThan(100); // Less than 100ms ping
    });

    test('should validate database indexes are created', async () => {
      const response = await request(baseUrl)
        .get('/api/v1/status/database/indexes')
        .expect(200);

      expect(response.body).toHaveProperty('indexes');
      expect(Array.isArray(response.body.indexes)).toBe(true);
      expect(response.body.indexes.length).toBeGreaterThan(0);
    });
  });

  describe('Performance and Load Validation', () => {
    test('should handle concurrent health check requests', async () => {
      const concurrentRequests = 10;
      const requests = Array.from({ length: concurrentRequests }, () =>
        request(baseUrl).get('/health').expect(200)
      );

      const responses = await Promise.all(requests);
      
      responses.forEach(response => {
        expect(response.body.status).toBe('healthy');
      });
    });

    test('should validate response times under load', async () => {
      const testDuration = 30000; // 30 seconds
      const requestInterval = 100; // 100ms between requests
      const maxResponseTime = 2000; // 2 seconds max
      
      let requestCount = 0;
      let slowResponses = 0;
      
      const startTime = Date.now();
      
      while (Date.now() - startTime < testDuration) {
        const reqStartTime = Date.now();
        
        try {
          await request(baseUrl).get('/health').expect(200);
          
          const responseTime = Date.now() - reqStartTime;
          if (responseTime > maxResponseTime) {
            slowResponses++;
          }
          
          requestCount++;
        } catch (error) {
          // Log but don't fail test for occasional network issues
          console.warn(`Health check failed: ${error.message}`);
        }
        
        await new Promise(resolve => setTimeout(resolve, requestInterval));
      }
      
      console.log(`Completed ${requestCount} requests, ${slowResponses} slow responses`);
      
      // Less than 5% of requests should be slow
      expect(slowResponses / requestCount).toBeLessThan(0.05);
    });
  });

  describe('Error Handling and Recovery', () => {
    test('should gracefully handle database disconnection', async () => {
      // This test would simulate database connectivity issues
      // For now, we check error response format
      
      const response = await request(baseUrl)
        .get('/api/v1/test/database-error')
        .expect(503); // Service Unavailable

      expect(response.body).toHaveProperty('error');
      expect(response.body).toHaveProperty('status', 'unhealthy');
      expect(response.body).toHaveProperty('timestamp');
    });

    test('should return proper error codes for unavailable services', async () => {
      const response = await request(baseUrl)
        .get('/api/v1/nonexistent-service')
        .expect(404);

      expect(response.body).toHaveProperty('error');
      expect(response.body.error).toContain('not found');
    });
  });
});