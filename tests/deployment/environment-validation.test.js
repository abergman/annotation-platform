/**
 * Environment Variable Validation Tests
 * Validates all required environment variables are properly set and secure
 */

const request = require('supertest');

describe('Environment Variable Validation', () => {
  let baseUrl;
  
  beforeAll(() => {
    baseUrl = process.env.DEPLOY_URL || 'http://localhost:8080';
    jest.setTimeout(30000);
  });

  describe('Required Environment Variables', () => {
    test('should validate NODE_ENV is set to production', async () => {
      const response = await request(baseUrl)
        .get('/health')
        .expect(200);

      expect(response.body.environment.NODE_ENV).toBe('production');
    });

    test('should validate PORT configuration', async () => {
      const response = await request(baseUrl)
        .get('/health')
        .expect(200);

      expect(response.body.environment.PORT).toBe('8080');
      expect(response.body.environment.HOST).toBe('0.0.0.0');
    });

    test('should validate domain configuration', async () => {
      const response = await request(baseUrl)
        .get('/health')
        .expect(200);

      expect(response.body.environment.DOMAIN).toBe('annotat.ee');
    });

    test('should validate database connection string format (without exposing credentials)', async () => {
      const response = await request(baseUrl)
        .get('/api/v1/status/database')
        .expect(200);

      // Should confirm MongoDB is connected without exposing connection string
      expect(response.body.mongodb.status).toBe('connected');
      expect(response.body.mongodb.host).toMatch(/mongodb/i);
      
      // Should NOT expose credentials
      expect(response.body).not.toHaveProperty('connectionString');
      expect(JSON.stringify(response.body)).not.toMatch(/password|secret|key/i);
    });
  });

  describe('Security Configuration', () => {
    test('should validate JWT_SECRET is configured (without exposing it)', async () => {
      // Test JWT functionality works (proves JWT_SECRET is set correctly)
      const loginResponse = await request(baseUrl)
        .post('/api/v1/auth/test-token')
        .send({ test: true })
        .expect(200);

      expect(loginResponse.body).toHaveProperty('token');
      expect(loginResponse.body.token).toMatch(/^eyJ/); // JWT format
    });

    test('should validate SESSION_SECRET is configured', async () => {
      // Test session functionality
      const agent = request.agent(baseUrl);
      
      const response = await agent
        .post('/api/v1/auth/test-session')
        .send({ test: true })
        .expect(200);

      expect(response.headers['set-cookie']).toBeDefined();
      expect(response.headers['set-cookie'][0]).toMatch(/connect\.sid/);
    });

    test('should validate secure headers are configured', async () => {
      const response = await request(baseUrl)
        .get('/health')
        .expect(200);

      // Security headers should be present
      expect(response.headers).toHaveProperty('x-content-type-options', 'nosniff');
      expect(response.headers).toHaveProperty('x-frame-options', 'DENY');
      expect(response.headers).toHaveProperty('x-xss-protection', '1; mode=block');
      expect(response.headers).toHaveProperty('strict-transport-security');
    });
  });

  describe('Digital Ocean Specific Configuration', () => {
    test('should validate deployment is running on Digital Ocean App Platform', async () => {
      const response = await request(baseUrl)
        .get('/health')
        .expect(200);

      // Check for Digital Ocean specific environment indicators
      expect(response.body).toHaveProperty('platform');
      expect(response.body.platform).toMatch(/digital.?ocean|app.?platform/i);
    });

    test('should validate managed MongoDB connection', async () => {
      const response = await request(baseUrl)
        .get('/api/v1/status/database')
        .expect(200);

      expect(response.body.mongodb.status).toBe('connected');
      expect(response.body.mongodb.host).toMatch(/mongo\.ondigitalocean\.com/);
      expect(response.body.mongodb).toHaveProperty('replicaSet');
      expect(response.body.mongodb.ssl).toBe(true);
    });

    test('should validate proper SSL/TLS configuration', async () => {
      // If testing HTTPS endpoint
      if (baseUrl.startsWith('https://')) {
        const response = await request(baseUrl)
          .get('/health')
          .expect(200);

        expect(response.headers).toHaveProperty('strict-transport-security');
      }
    });
  });

  describe('Resource Limits and Configuration', () => {
    test('should validate memory usage within limits', async () => {
      const response = await request(baseUrl)
        .get('/health')
        .expect(200);

      expect(response.body.system.memory.usage).toBeLessThan(80); // Less than 80%
      expect(response.body.system.memory.available).toBeGreaterThan(0);
    });

    test('should validate CPU usage is reasonable', async () => {
      const response = await request(baseUrl)
        .get('/health')
        .expect(200);

      expect(response.body.system.cpu.usage).toBeLessThan(90); // Less than 90%
    });

    test('should validate file system permissions', async () => {
      const response = await request(baseUrl)
        .get('/api/v1/status/filesystem')
        .expect(200);

      expect(response.body.writable).toBe(true);
      expect(response.body.tempDir).toBeDefined();
      expect(response.body.logsDir).toBeDefined();
    });
  });

  describe('Environment Variable Security', () => {
    test('should not expose sensitive environment variables in any endpoint', async () => {
      // Test health endpoint
      const healthResponse = await request(baseUrl)
        .get('/health')
        .expect(200);

      const healthBody = JSON.stringify(healthResponse.body).toLowerCase();
      expect(healthBody).not.toMatch(/jwt_secret|session_secret|mongodb.*password/);

      // Test any debug/info endpoints
      const endpoints = ['/api/v1/info', '/api/v1/debug', '/api/v1/config'];
      
      for (const endpoint of endpoints) {
        try {
          const response = await request(baseUrl).get(endpoint);
          const responseBody = JSON.stringify(response.body).toLowerCase();
          
          expect(responseBody).not.toMatch(/jwt_secret|session_secret|password|secret|key.*=|token.*=/);
        } catch (error) {
          // Endpoint doesn't exist, which is fine
          if (error.status !== 404) {
            throw error;
          }
        }
      }
    });

    test('should validate environment variable validation endpoint security', async () => {
      // This endpoint should be protected or non-existent in production
      const response = await request(baseUrl)
        .get('/api/v1/env')
        .expect([401, 403, 404]); // Should be unauthorized, forbidden, or not found

      if (response.status !== 404) {
        // If endpoint exists, ensure it requires authentication
        expect(response.status).toBeOneOf([401, 403]);
      }
    });
  });
});