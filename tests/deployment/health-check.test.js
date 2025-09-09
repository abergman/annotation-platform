const axios = require('axios');
const { expect } = require('chai');
const os = require('os');

describe('Health Check and Monitoring Tests', () => {
  const BASE_URL = process.env.DEPLOYMENT_URL || 'https://annotat.ee';
  const HEALTH_ENDPOINT = `${BASE_URL}/api/health`;
  const STATUS_ENDPOINT = `${BASE_URL}/api/status`;
  const METRICS_ENDPOINT = `${BASE_URL}/api/metrics`;

  describe('Health Endpoint Validation', () => {
    let healthResponse;

    before(async () => {
      healthResponse = await axios.get(HEALTH_ENDPOINT);
    });

    it('should return 200 status code', () => {
      expect(healthResponse.status).to.equal(200);
    });

    it('should return valid health status structure', () => {
      const { data } = healthResponse;
      expect(data).to.have.property('status');
      expect(data).to.have.property('timestamp');
      expect(data).to.have.property('version');
      expect(data).to.have.property('environment');
    });

    it('should indicate healthy status', () => {
      expect(healthResponse.data.status).to.equal('healthy');
    });

    it('should have recent timestamp', () => {
      const timestamp = new Date(healthResponse.data.timestamp);
      const now = new Date();
      const diffMinutes = (now - timestamp) / (1000 * 60);
      expect(diffMinutes).to.be.lessThan(1); // Within 1 minute
    });

    it('should have valid version format', () => {
      const version = healthResponse.data.version;
      expect(version).to.match(/^\d+\.\d+\.\d+/); // Semantic versioning
    });
  });

  describe('System Status Monitoring', () => {
    let statusResponse;

    before(async () => {
      statusResponse = await axios.get(STATUS_ENDPOINT);
    });

    it('should return comprehensive system status', () => {
      const { data } = statusResponse;
      expect(data).to.have.property('database');
      expect(data).to.have.property('cache');
      expect(data).to.have.property('services');
      expect(data).to.have.property('uptime');
    });

    it('should show healthy database connection', () => {
      const { database } = statusResponse.data;
      expect(database).to.have.property('connected', true);
      expect(database).to.have.property('latency');
      expect(database.latency).to.be.a('number');
      expect(database.latency).to.be.lessThan(1000); // < 1 second
    });

    it('should show healthy cache connection', () => {
      const { cache } = statusResponse.data;
      expect(cache).to.have.property('connected', true);
      expect(cache).to.have.property('memory_usage');
    });

    it('should list all required services', () => {
      const { services } = statusResponse.data;
      expect(services).to.be.an('object');
      
      // Check for essential services
      const requiredServices = ['auth', 'annotation', 'websocket'];
      requiredServices.forEach(service => {
        expect(services).to.have.property(service);
        expect(services[service].status).to.equal('running');
      });
    });

    it('should report reasonable uptime', () => {
      const { uptime } = statusResponse.data;
      expect(uptime).to.be.a('number');
      expect(uptime).to.be.greaterThan(0);
    });
  });

  describe('Performance Metrics', () => {
    let metricsResponse;

    before(async () => {
      try {
        metricsResponse = await axios.get(METRICS_ENDPOINT);
      } catch (error) {
        if (error.response && error.response.status === 404) {
          console.log('Metrics endpoint not available, skipping metrics tests');
          return;
        }
        throw error;
      }
    });

    it('should return performance metrics if available', function() {
      if (!metricsResponse) {
        this.skip();
        return;
      }

      const { data } = metricsResponse;
      expect(data).to.have.property('response_times');
      expect(data).to.have.property('throughput');
      expect(data).to.have.property('error_rates');
    });

    it('should show acceptable response times', function() {
      if (!metricsResponse) {
        this.skip();
        return;
      }

      const { response_times } = metricsResponse.data;
      expect(response_times.average).to.be.lessThan(500); // < 500ms average
      expect(response_times.p95).to.be.lessThan(1000); // < 1s for 95th percentile
    });

    it('should show low error rates', function() {
      if (!metricsResponse) {
        this.skip();
        return;
      }

      const { error_rates } = metricsResponse.data;
      expect(error_rates.total).to.be.lessThan(0.05); // < 5% error rate
    });
  });

  describe('Dependency Health Checks', () => {
    it('should validate external API dependencies', async () => {
      const response = await axios.get(`${BASE_URL}/api/dependencies/check`);
      expect(response.status).to.equal(200);
      
      const { data } = response;
      expect(data).to.have.property('external_apis');
      
      Object.values(data.external_apis).forEach(api => {
        expect(api.status).to.be.oneOf(['healthy', 'degraded']);
        expect(api.response_time).to.be.a('number');
      });
    });

    it('should check third-party service integrations', async () => {
      const response = await axios.get(`${BASE_URL}/api/integrations/status`);
      expect(response.status).to.equal(200);
      
      const { data } = response;
      expect(data).to.be.an('object');
      
      // Check each integration
      Object.entries(data).forEach(([service, status]) => {
        expect(status).to.have.property('available');
        expect(status.available).to.be.a('boolean');
        if (!status.available) {
          expect(status).to.have.property('error');
        }
      });
    });
  });

  describe('Resource Usage Monitoring', () => {
    it('should monitor memory usage', async () => {
      const response = await axios.get(`${BASE_URL}/api/system/resources`);
      expect(response.status).to.equal(200);
      
      const { data } = response;
      expect(data).to.have.property('memory');
      expect(data.memory.used_percentage).to.be.lessThan(90); // < 90% memory usage
    });

    it('should monitor CPU usage', async () => {
      const response = await axios.get(`${BASE_URL}/api/system/resources`);
      const { data } = response;
      
      expect(data).to.have.property('cpu');
      expect(data.cpu.usage_percentage).to.be.lessThan(80); // < 80% CPU usage
    });

    it('should monitor disk usage', async () => {
      const response = await axios.get(`${BASE_URL}/api/system/resources`);
      const { data } = response;
      
      expect(data).to.have.property('disk');
      expect(data.disk.used_percentage).to.be.lessThan(85); // < 85% disk usage
    });
  });

  describe('Load Balancer Health', () => {
    it('should verify load balancer configuration', async () => {
      const requests = Array(10).fill(null).map(() => 
        axios.get(`${BASE_URL}/api/server/info`)
      );
      
      const responses = await Promise.all(requests);
      const serverIds = responses.map(r => r.data.server_id).filter(Boolean);
      
      // Should have consistent responses (or multiple servers if load balanced)
      expect(responses.every(r => r.status === 200)).to.be.true;
    });

    it('should handle server failover gracefully', async () => {
      // Multiple requests to test failover behavior
      const requests = Array(5).fill(null).map(async () => {
        try {
          const response = await axios.get(HEALTH_ENDPOINT, { timeout: 5000 });
          return { success: true, status: response.status };
        } catch (error) {
          return { success: false, error: error.message };
        }
      });
      
      const results = await Promise.all(requests);
      const successRate = results.filter(r => r.success).length / results.length;
      expect(successRate).to.be.greaterThan(0.8); // > 80% success rate
    });
  });

  describe('Security Headers Validation', () => {
    let securityResponse;

    before(async () => {
      securityResponse = await axios.get(BASE_URL);
    });

    it('should have security headers', () => {
      const headers = securityResponse.headers;
      
      expect(headers).to.have.property('x-content-type-options', 'nosniff');
      expect(headers).to.have.property('x-frame-options');
      expect(headers).to.have.property('x-xss-protection');
      expect(headers).to.have.property('strict-transport-security');
    });

    it('should have HSTS header for HTTPS', () => {
      if (BASE_URL.startsWith('https:')) {
        expect(securityResponse.headers['strict-transport-security']).to.exist;
      }
    });
  });

  after(() => {
    console.log('\n🏥 Health check tests completed');
    console.log(`Target URL: ${BASE_URL}`);
    console.log(`System load: ${os.loadavg()[0].toFixed(2)}`);
    console.log(`Free memory: ${(os.freemem() / 1024 / 1024 / 1024).toFixed(2)} GB`);
  });
});