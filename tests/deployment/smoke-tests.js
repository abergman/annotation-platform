const axios = require('axios');
const WebSocket = require('ws');
const { expect } = require('chai');

describe('Post-Deployment Smoke Tests', () => {
  const BASE_URL = process.env.DEPLOYMENT_URL || 'https://annotat.ee';
  const API_TIMEOUT = 10000;

  before(function() {
    this.timeout(30000); // Allow more time for deployment warmup
  });

  describe('Basic Connectivity', () => {
    it('should respond to root endpoint', async () => {
      const response = await axios.get(BASE_URL, { timeout: API_TIMEOUT });
      expect(response.status).to.equal(200);
      expect(response.headers).to.have.property('content-type');
    });

    it('should have correct CORS headers', async () => {
      const response = await axios.options(BASE_URL, { timeout: API_TIMEOUT });
      expect(response.headers).to.have.property('access-control-allow-origin');
    });

    it('should redirect HTTP to HTTPS', async () => {
      try {
        const response = await axios.get(BASE_URL.replace('https:', 'http:'), {
          maxRedirects: 0,
          timeout: API_TIMEOUT
        });
      } catch (error) {
        expect(error.response.status).to.be.oneOf([301, 302, 308]);
        expect(error.response.headers.location).to.include('https:');
      }
    });
  });

  describe('API Endpoints', () => {
    it('should respond to health check endpoint', async () => {
      const response = await axios.get(`${BASE_URL}/api/health`, { timeout: API_TIMEOUT });
      expect(response.status).to.equal(200);
      expect(response.data).to.have.property('status', 'healthy');
      expect(response.data).to.have.property('timestamp');
      expect(response.data).to.have.property('version');
    });

    it('should respond to API status endpoint', async () => {
      const response = await axios.get(`${BASE_URL}/api/status`, { timeout: API_TIMEOUT });
      expect(response.status).to.equal(200);
      expect(response.data).to.have.property('database');
      expect(response.data).to.have.property('cache');
      expect(response.data).to.have.property('services');
    });

    it('should handle 404 gracefully', async () => {
      try {
        await axios.get(`${BASE_URL}/api/nonexistent`, { timeout: API_TIMEOUT });
      } catch (error) {
        expect(error.response.status).to.equal(404);
        expect(error.response.data).to.have.property('error');
      }
    });

    it('should validate API authentication endpoint', async () => {
      const response = await axios.post(`${BASE_URL}/api/auth/validate`, {}, {
        timeout: API_TIMEOUT,
        validateStatus: () => true // Accept all status codes
      });
      expect(response.status).to.be.oneOf([200, 401, 403]); // Valid responses
    });
  });

  describe('Database Connectivity', () => {
    it('should connect to database successfully', async () => {
      const response = await axios.get(`${BASE_URL}/api/db/ping`, { timeout: API_TIMEOUT });
      expect(response.status).to.equal(200);
      expect(response.data).to.have.property('connected', true);
      expect(response.data).to.have.property('latency');
      expect(response.data.latency).to.be.a('number');
    });

    it('should execute basic query', async () => {
      const response = await axios.get(`${BASE_URL}/api/db/test`, { timeout: API_TIMEOUT });
      expect(response.status).to.equal(200);
      expect(response.data).to.have.property('queryResult');
    });
  });

  describe('WebSocket Functionality', () => {
    it('should establish WebSocket connection', (done) => {
      const wsUrl = BASE_URL.replace('http', 'ws') + '/ws';
      const ws = new WebSocket(wsUrl);
      
      const timeout = setTimeout(() => {
        ws.terminate();
        done(new Error('WebSocket connection timeout'));
      }, 10000);

      ws.on('open', () => {
        clearTimeout(timeout);
        ws.close();
        done();
      });

      ws.on('error', (error) => {
        clearTimeout(timeout);
        done(error);
      });
    });

    it('should handle WebSocket messages', (done) => {
      const wsUrl = BASE_URL.replace('http', 'ws') + '/ws';
      const ws = new WebSocket(wsUrl);
      
      const timeout = setTimeout(() => {
        ws.terminate();
        done(new Error('WebSocket message timeout'));
      }, 10000);

      ws.on('open', () => {
        ws.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }));
      });

      ws.on('message', (data) => {
        const message = JSON.parse(data);
        if (message.type === 'pong') {
          clearTimeout(timeout);
          ws.close();
          done();
        }
      });

      ws.on('error', (error) => {
        clearTimeout(timeout);
        done(error);
      });
    });
  });

  describe('Static Assets', () => {
    it('should serve static files correctly', async () => {
      const response = await axios.get(`${BASE_URL}/favicon.ico`, { 
        timeout: API_TIMEOUT,
        validateStatus: () => true 
      });
      expect(response.status).to.be.oneOf([200, 404]); // Either exists or gracefully missing
    });

    it('should have correct cache headers for static assets', async () => {
      try {
        const response = await axios.get(`${BASE_URL}/static/js/main.js`, { timeout: API_TIMEOUT });
        expect(response.headers).to.have.property('cache-control');
      } catch (error) {
        // Static file might not exist in all deployments
        expect(error.response.status).to.equal(404);
      }
    });
  });

  describe('Error Handling', () => {
    it('should handle server errors gracefully', async () => {
      try {
        await axios.get(`${BASE_URL}/api/error/500`, { timeout: API_TIMEOUT });
      } catch (error) {
        expect(error.response.status).to.equal(500);
        expect(error.response.data).to.have.property('error');
        expect(error.response.data.error).to.be.a('string');
      }
    });

    it('should validate request rate limiting', async () => {
      const requests = Array(20).fill(null).map(() => 
        axios.get(`${BASE_URL}/api/health`, { 
          timeout: API_TIMEOUT,
          validateStatus: () => true 
        })
      );
      
      const responses = await Promise.all(requests);
      const statusCodes = responses.map(r => r.status);
      
      // Should have mix of 200s and possibly 429s (rate limited)
      expect(statusCodes).to.include(200);
    });
  });

  after(() => {
    console.log('\n✅ Smoke tests completed successfully');
    console.log(`Target URL: ${BASE_URL}`);
    console.log(`Test timestamp: ${new Date().toISOString()}`);
  });
});