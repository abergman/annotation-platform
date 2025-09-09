/**
 * Digital Ocean App Platform Specific Validation Tests
 * Tests specific to Digital Ocean App Platform deployment features
 */

const request = require('supertest');
const https = require('https');

describe('Digital Ocean App Platform Deployment Validation', () => {
  let baseUrl;
  let appId;
  
  beforeAll(() => {
    baseUrl = process.env.DEPLOY_URL || 'http://localhost:8080';
    appId = process.env.DO_APP_ID || '58c46a38-9d6b-41d8-a54c-e80663ef5226';
    jest.setTimeout(120000); // Extended timeout for platform operations
  });

  describe('App Platform Configuration Validation', () => {
    test('should validate app is running on Digital Ocean infrastructure', async () => {
      const response = await request(baseUrl)
        .get('/health')
        .expect(200);

      expect(response.body).toHaveProperty('platform');
      expect(response.body.platform).toMatch(/digital.?ocean|app.?platform/i);
      
      // Check for DO-specific environment indicators
      expect(response.body.environment).toHaveProperty('NODE_ENV', 'production');
      expect(response.body.environment).toHaveProperty('PORT', '8080');
    });

    test('should validate managed MongoDB connection', async () => {
      const response = await request(baseUrl)
        .get('/api/v1/status/database')
        .expect(200);

      expect(response.body.mongodb.status).toBe('connected');
      expect(response.body.mongodb.host).toMatch(/mongo\.ondigitalocean\.com/);
      expect(response.body.mongodb.ssl).toBe(true);
      expect(response.body.mongodb.replicaSet).toBe('annotation-mongodb');
    });

    test('should validate app specification compliance', async () => {
      const response = await request(baseUrl)
        .get('/api/v1/status/app-spec')
        .expect(200);

      // Validate app spec configuration
      expect(response.body).toHaveProperty('name', 'annotation-platform');
      expect(response.body).toHaveProperty('region', 'ams3');
      expect(response.body).toHaveProperty('instanceSize', 'basic-xxs');
      expect(response.body).toHaveProperty('instanceCount', 1);
      
      // Validate domain configuration
      expect(response.body.domains).toBeDefined();
      expect(response.body.domains).toContainEqual({
        domain: 'annotat.ee',
        type: 'PRIMARY'
      });
    });

    test('should validate environment variables from app spec', async () => {
      const response = await request(baseUrl)
        .get('/api/v1/status/environment')
        .expect(200);

      // Required environment variables from app-update.yaml
      expect(response.body.validated).toHaveProperty('NODE_ENV', 'production');
      expect(response.body.validated).toHaveProperty('PORT', '8080');
      expect(response.body.validated).toHaveProperty('HOST', '0.0.0.0');
      expect(response.body.validated).toHaveProperty('DOMAIN', 'annotat.ee');
      
      // Sensitive variables should be masked
      expect(response.body.validated).not.toHaveProperty('JWT_SECRET');
      expect(response.body.validated).not.toHaveProperty('MONGODB_URI');
      expect(response.body.validated).not.toHaveProperty('SESSION_SECRET');
      
      // But should indicate they are set
      expect(response.body.masked).toContain('JWT_SECRET');
      expect(response.body.masked).toContain('MONGODB_URI');
      expect(response.body.masked).toContain('SESSION_SECRET');
    });
  });

  describe('Domain and SSL Configuration', () => {
    test('should validate primary domain configuration', async () => {
      if (baseUrl.includes('annotat.ee')) {
        const response = await request(baseUrl)
          .get('/health')
          .set('Host', 'annotat.ee')
          .expect(200);

        expect(response.body.status).toBe('healthy');
      }
    });

    test('should validate SSL certificate for production domain', async () => {
      if (baseUrl.startsWith('https://annotat.ee')) {
        // Test SSL certificate validity
        const response = await request(baseUrl)
          .get('/health')
          .expect(200);

        expect(response.headers).toHaveProperty('strict-transport-security');
        
        // Additional SSL validation
        const sslResponse = await request(baseUrl)
          .get('/api/v1/status/ssl')
          .expect(200);

        expect(sslResponse.body.ssl).toBe(true);
        expect(sslResponse.body.certificate).toHaveProperty('valid', true);
        expect(sslResponse.body.certificate.issuer).toMatch(/let.s.encrypt|digicert/i);
      }
    });

    test('should redirect HTTP to HTTPS in production', async () => {
      if (baseUrl.startsWith('https://')) {
        const httpUrl = baseUrl.replace('https://', 'http://');
        
        try {
          const response = await request(httpUrl)
            .get('/health')
            .expect(301);

          expect(response.headers.location).toMatch(/^https:/);
        } catch (error) {
          // HTTP might not be available, which is acceptable
          if (error.code !== 'ENOTFOUND') {
            throw error;
          }
        }
      }
    });
  });

  describe('App Platform Health Checks', () => {
    test('should validate health check endpoint matches app spec', async () => {
      // Health check configuration from app-update.yaml:
      // http_path: /health
      // initial_delay_seconds: 30
      // period_seconds: 10
      // timeout_seconds: 5
      // success_threshold: 1
      // failure_threshold: 3
      
      const startTime = Date.now();
      const response = await request(baseUrl)
        .get('/health')
        .expect(200);

      const responseTime = Date.now() - startTime;
      
      // Should respond within timeout_seconds (5s)
      expect(responseTime).toBeLessThan(5000);
      
      expect(response.body).toHaveProperty('status', 'healthy');
    });

    test('should validate health check response format', async () => {
      const response = await request(baseUrl)
        .get('/health')
        .expect(200);

      // App Platform expects specific format
      expect(response.body).toHaveProperty('status');
      expect(response.body.status).toBeOneOf(['healthy', 'unhealthy']);
      
      if (response.body.status === 'healthy') {
        expect(response.body).toHaveProperty('checks');
        Object.values(response.body.checks).forEach(check => {
          expect(check).toHaveProperty('status');
        });
      }
    });

    test('should handle health check during startup', async () => {
      // Simulate startup scenario
      const response = await request(baseUrl)
        .get('/health')
        .set('X-Test-Startup', 'true')
        .expect(200);

      // During startup, some checks might be pending
      expect(response.body.status).toBeOneOf(['healthy', 'starting']);
      
      if (response.body.status === 'starting') {
        expect(response.body).toHaveProperty('startupTime');
        expect(response.body.startupTime).toBeLessThan(30000); // Less than initial_delay_seconds
      }
    });
  });

  describe('Auto-Scaling and Performance', () => {
    test('should validate instance size and resource limits', async () => {
      const response = await request(baseUrl)
        .get('/api/v1/status/resources')
        .expect(200);

      // basic-xxs instance limits
      expect(response.body.limits).toHaveProperty('memory');
      expect(response.body.limits).toHaveProperty('cpu');
      
      // Current usage should be within limits
      expect(response.body.usage.memory.percentage).toBeLessThan(90);
      expect(response.body.usage.cpu.percentage).toBeLessThan(90);
    });

    test('should validate horizontal scaling readiness', async () => {
      const response = await request(baseUrl)
        .get('/api/v1/status/scaling')
        .expect(200);

      expect(response.body).toHaveProperty('scalable', true);
      expect(response.body).toHaveProperty('instanceCount', 1);
      expect(response.body).toHaveProperty('healthyInstances', 1);
      
      // Should be ready for scaling
      expect(response.body.readyForScaling).toBe(true);
      expect(response.body.sharedState).toBe(true); // No local state dependencies
    });

    test('should validate load balancing compatibility', async () => {
      // Test session handling for load balancing
      const agent = request.agent(baseUrl);
      
      const response1 = await agent
        .post('/api/v1/auth/test-session')
        .send({ test: true })
        .expect(200);

      expect(response1.body).toHaveProperty('sessionId');
      
      const response2 = await agent
        .get('/api/v1/auth/session-info')
        .expect(200);

      expect(response2.body).toHaveProperty('sessionId', response1.body.sessionId);
      
      // Session should be stored externally (not in memory)
      expect(response2.body.sessionStore).toBeOneOf(['redis', 'database', 'external']);
    });
  });

  describe('Deployment and Build Process', () => {
    test('should validate Docker build configuration', async () => {
      const response = await request(baseUrl)
        .get('/api/v1/status/build-info')
        .expect(200);

      expect(response.body).toHaveProperty('dockerfile', 'Dockerfile.production');
      expect(response.body).toHaveProperty('nodeVersion');
      expect(response.body.nodeVersion).toMatch(/^20\./); // Node 20
      
      // Validate security configurations
      expect(response.body.user).toBe('app'); // Non-root user
      expect(response.body.healthCheck).toBe(true);
    });

    test('should validate deployment source configuration', async () => {
      const response = await request(baseUrl)
        .get('/api/v1/status/deployment')
        .expect(200);

      expect(response.body.source).toHaveProperty('type', 'github');
      expect(response.body.source).toHaveProperty('repo', 'abergman/annotation-platform');
      expect(response.body.source).toHaveProperty('branch', 'main');
      expect(response.body.deployOnPush).toBe(true);
    });

    test('should validate build optimization', async () => {
      const response = await request(baseUrl)
        .get('/api/v1/status/build-optimization')
        .expect(200);

      expect(response.body).toHaveProperty('productionBuild', true);
      expect(response.body).toHaveProperty('dependenciesOptimized', true);
      expect(response.body).toHaveProperty('cacheCleared', true);
      
      // Check bundle size is reasonable
      expect(response.body.bundleSize).toBeLessThan(100 * 1024 * 1024); // Less than 100MB
    });
  });

  describe('Monitoring and Logging Integration', () => {
    test('should validate logging configuration', async () => {
      const response = await request(baseUrl)
        .get('/api/v1/status/logging')
        .expect(200);

      expect(response.body).toHaveProperty('level', 'info');
      expect(response.body).toHaveProperty('output', 'stdout');
      expect(response.body).toHaveProperty('structured', true);
      
      // Should be compatible with App Platform log aggregation
      expect(response.body.format).toBeOneOf(['json', 'structured']);
    });

    test('should validate metrics collection', async () => {
      const response = await request(baseUrl)
        .get('/api/v1/status/metrics')
        .expect(200);

      expect(response.body).toHaveProperty('enabled', true);
      expect(response.body).toHaveProperty('endpoint', '/metrics');
      
      // Test metrics endpoint
      const metricsResponse = await request(baseUrl)
        .get('/metrics')
        .expect(200);

      expect(metricsResponse.text).toMatch(/# HELP/);
      expect(metricsResponse.text).toMatch(/http_requests_total/);
    });

    test('should validate integration with App Platform monitoring', async () => {
      const response = await request(baseUrl)
        .get('/api/v1/status/platform-monitoring')
        .expect(200);

      expect(response.body).toHaveProperty('platformIntegration', true);
      expect(response.body).toHaveProperty('alerting');
      expect(response.body).toHaveProperty('uptime');
      
      // Should report to platform monitoring
      expect(response.body.platformIntegration).toBe(true);
    });
  });

  describe('Security and Compliance', () => {
    test('should validate network security configuration', async () => {
      const response = await request(baseUrl)
        .get('/api/v1/status/security')
        .expect(200);

      expect(response.body.network).toHaveProperty('privateNetworking', true);
      expect(response.body.network).toHaveProperty('firewallEnabled', true);
      
      // Should only allow necessary ports
      expect(response.body.network.openPorts).toEqual(['8080']);
    });

    test('should validate data encryption configuration', async () => {
      const response = await request(baseUrl)
        .get('/api/v1/status/encryption')
        .expect(200);

      expect(response.body.inTransit).toBe(true); // HTTPS
      expect(response.body.atRest).toBe(true); // Database encryption
      expect(response.body.secrets).toBe(true); // Environment variable encryption
    });

    test('should validate compliance with security best practices', async () => {
      const response = await request(baseUrl)
        .get('/api/v1/status/security-compliance')
        .expect(200);

      const compliance = response.body.compliance;
      
      expect(compliance.nonRootUser).toBe(true);
      expect(compliance.secretsManagement).toBe(true);
      expect(compliance.networkSegmentation).toBe(true);
      expect(compliance.updateStrategy).toBeDefined();
      
      // Overall compliance score
      expect(compliance.score).toBeGreaterThanOrEqual(90);
    });
  });
});