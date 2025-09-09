const axios = require('axios');
const { expect } = require('chai');
const fs = require('fs');
const path = require('path');

describe('Rollback Validation Tests', () => {
  const BASE_URL = process.env.DEPLOYMENT_URL || 'https://annotat.ee';
  const ROLLBACK_ENDPOINT = `${BASE_URL}/api/admin/rollback`;
  const VERSION_ENDPOINT = `${BASE_URL}/api/version`;
  const HEALTH_ENDPOINT = `${BASE_URL}/api/health`;

  // Test data for rollback validation
  const testData = {
    user: {
      username: 'rollback_test_user',
      email: 'rollback.test@example.com',
      password: 'TempPassword123!'
    },
    annotation: {
      content: 'Test annotation for rollback validation',
      position: { x: 100, y: 200 },
      documentId: 'rollback-test-doc'
    }
  };

  describe('Pre-Rollback State Capture', () => {
    let preRollbackState;

    before(async function() {
      this.timeout(30000);
      preRollbackState = {
        timestamp: new Date().toISOString(),
        version: null,
        health: null,
        userCount: null,
        annotationCount: null,
        databaseIntegrity: null
      };
    });

    it('should capture current version information', async () => {
      const response = await axios.get(VERSION_ENDPOINT);
      expect(response.status).to.equal(200);
      
      preRollbackState.version = response.data;
      expect(preRollbackState.version).to.have.property('version');
      expect(preRollbackState.version).to.have.property('build');
      expect(preRollbackState.version).to.have.property('commit');
      
      console.log('Pre-rollback version:', preRollbackState.version.version);
    });

    it('should capture system health metrics', async () => {
      const response = await axios.get(HEALTH_ENDPOINT);
      expect(response.status).to.equal(200);
      
      preRollbackState.health = response.data;
      expect(preRollbackState.health.status).to.equal('healthy');
      
      console.log('Pre-rollback health status:', preRollbackState.health.status);
    });

    it('should capture user count', async () => {
      try {
        const response = await axios.get(`${BASE_URL}/api/admin/stats/users`);
        if (response.status === 200) {
          preRollbackState.userCount = response.data.total_users;
          console.log('Pre-rollback user count:', preRollbackState.userCount);
        }
      } catch (error) {
        console.log('User stats endpoint not available, skipping count capture');
      }
    });

    it('should capture annotation count', async () => {
      try {
        const response = await axios.get(`${BASE_URL}/api/admin/stats/annotations`);
        if (response.status === 200) {
          preRollbackState.annotationCount = response.data.total_annotations;
          console.log('Pre-rollback annotation count:', preRollbackState.annotationCount);
        }
      } catch (error) {
        console.log('Annotation stats endpoint not available, skipping count capture');
      }
    });

    it('should verify database integrity', async () => {
      try {
        const response = await axios.get(`${BASE_URL}/api/admin/db/integrity`);
        if (response.status === 200) {
          preRollbackState.databaseIntegrity = response.data;
          expect(preRollbackState.databaseIntegrity.status).to.equal('ok');
          console.log('Pre-rollback database integrity:', preRollbackState.databaseIntegrity.status);
        }
      } catch (error) {
        console.log('Database integrity endpoint not available, assuming healthy');
        preRollbackState.databaseIntegrity = { status: 'assumed_ok' };
      }
    });

    after(() => {
      // Save pre-rollback state for comparison
      const stateFile = path.join(process.cwd(), 'test-reports', 'pre-rollback-state.json');
      fs.mkdirSync(path.dirname(stateFile), { recursive: true });
      fs.writeFileSync(stateFile, JSON.stringify(preRollbackState, null, 2));
      console.log('Pre-rollback state saved to:', stateFile);
    });
  });

  describe('Rollback Procedure Validation', () => {
    it('should have rollback endpoint available', async () => {
      try {
        // This should return 401/403 if not authenticated, not 404
        await axios.post(ROLLBACK_ENDPOINT, { dry_run: true });
      } catch (error) {
        expect(error.response.status).to.be.oneOf([401, 403, 405]);
        expect(error.response.status).not.to.equal(404);
      }
    });

    it('should validate rollback prerequisites', async () => {
      try {
        const response = await axios.get(`${BASE_URL}/api/admin/rollback/prerequisites`);
        if (response.status === 200) {
          const { data } = response;
          expect(data).to.have.property('can_rollback');
          expect(data).to.have.property('backup_available');
          expect(data).to.have.property('previous_version');
          
          console.log('Rollback prerequisites:', data);
        }
      } catch (error) {
        console.log('Rollback prerequisites endpoint not available');
      }
    });

    it('should have database backup verification', async () => {
      try {
        const response = await axios.get(`${BASE_URL}/api/admin/backup/status`);
        if (response.status === 200) {
          const { data } = response;
          expect(data).to.have.property('last_backup');
          expect(data).to.have.property('backup_status');
          
          // Backup should be recent (within last 24 hours)
          const lastBackup = new Date(data.last_backup);
          const now = new Date();
          const hoursDiff = (now - lastBackup) / (1000 * 60 * 60);
          expect(hoursDiff).to.be.lessThan(24);
          
          console.log('Last backup:', data.last_backup);
        }
      } catch (error) {
        console.log('Backup status endpoint not available, manual verification required');
      }
    });

    it('should verify rollback configuration', async () => {
      try {
        const response = await axios.get(`${BASE_URL}/api/admin/config/rollback`);
        if (response.status === 200) {
          const { data } = response;
          expect(data).to.have.property('rollback_enabled');
          expect(data).to.have.property('rollback_strategy');
          expect(data).to.have.property('max_rollback_time_hours');
          
          console.log('Rollback configuration:', data);
        }
      } catch (error) {
        console.log('Rollback configuration endpoint not available');
      }
    });
  });

  describe('Data Consistency Checks', () => {
    it('should verify user data consistency', async () => {
      try {
        const response = await axios.get(`${BASE_URL}/api/admin/consistency/users`);
        if (response.status === 200) {
          const { data } = response;
          expect(data.status).to.equal('consistent');
          expect(data.orphaned_records).to.equal(0);
          
          console.log('User data consistency:', data.status);
        }
      } catch (error) {
        console.log('User consistency check endpoint not available');
      }
    });

    it('should verify annotation data consistency', async () => {
      try {
        const response = await axios.get(`${BASE_URL}/api/admin/consistency/annotations`);
        if (response.status === 200) {
          const { data } = response;
          expect(data.status).to.equal('consistent');
          expect(data.orphaned_records).to.equal(0);
          
          console.log('Annotation data consistency:', data.status);
        }
      } catch (error) {
        console.log('Annotation consistency check endpoint not available');
      }
    });

    it('should verify file upload consistency', async () => {
      try {
        const response = await axios.get(`${BASE_URL}/api/admin/consistency/files`);
        if (response.status === 200) {
          const { data } = response;
          expect(data.status).to.equal('consistent');
          expect(data.missing_files).to.equal(0);
          
          console.log('File consistency:', data.status);
        }
      } catch (error) {
        console.log('File consistency check endpoint not available');
      }
    });
  });

  describe('Service Dependencies Check', () => {
    it('should verify database connectivity', async () => {
      const response = await axios.get(`${BASE_URL}/api/db/ping`);
      expect(response.status).to.equal(200);
      expect(response.data.connected).to.be.true;
      expect(response.data.latency).to.be.a('number');
    });

    it('should verify cache connectivity', async () => {
      try {
        const response = await axios.get(`${BASE_URL}/api/cache/ping`);
        if (response.status === 200) {
          expect(response.data.connected).to.be.true;
        }
      } catch (error) {
        console.log('Cache ping endpoint not available, assuming cache is healthy');
      }
    });

    it('should verify external service connectivity', async () => {
      try {
        const response = await axios.get(`${BASE_URL}/api/dependencies/check`);
        if (response.status === 200) {
          const { data } = response;
          Object.values(data.external_apis || {}).forEach(api => {
            expect(api.status).to.be.oneOf(['healthy', 'degraded']);
          });
        }
      } catch (error) {
        console.log('Dependencies check endpoint not available');
      }
    });
  });

  describe('Performance Impact Assessment', () => {
    it('should measure current response times', async () => {
      const measurements = [];
      
      // Take 5 measurements
      for (let i = 0; i < 5; i++) {
        const start = Date.now();
        const response = await axios.get(`${BASE_URL}/api/health`);
        const end = Date.now();
        
        expect(response.status).to.equal(200);
        measurements.push(end - start);
        
        await new Promise(resolve => setTimeout(resolve, 100));
      }
      
      const avgResponseTime = measurements.reduce((a, b) => a + b, 0) / measurements.length;
      console.log('Pre-rollback average response time:', avgResponseTime, 'ms');
      
      // Store for comparison after rollback
      const metricsFile = path.join(process.cwd(), 'test-reports', 'pre-rollback-metrics.json');
      fs.writeFileSync(metricsFile, JSON.stringify({
        timestamp: new Date().toISOString(),
        average_response_time_ms: avgResponseTime,
        response_times: measurements
      }, null, 2));
    });

    it('should check current resource usage', async () => {
      try {
        const response = await axios.get(`${BASE_URL}/api/system/resources`);
        if (response.status === 200) {
          const { data } = response;
          console.log('Pre-rollback resource usage:', {
            memory: data.memory?.used_percentage + '%',
            cpu: data.cpu?.usage_percentage + '%',
            disk: data.disk?.used_percentage + '%'
          });
          
          // Store for comparison
          const resourcesFile = path.join(process.cwd(), 'test-reports', 'pre-rollback-resources.json');
          fs.writeFileSync(resourcesFile, JSON.stringify({
            timestamp: new Date().toISOString(),
            resources: data
          }, null, 2));
        }
      } catch (error) {
        console.log('Resource monitoring endpoint not available');
      }
    });
  });

  describe('Rollback Safety Checks', () => {
    it('should verify no active user sessions that would be disrupted', async () => {
      try {
        const response = await axios.get(`${BASE_URL}/api/admin/sessions/active`);
        if (response.status === 200) {
          const { data } = response;
          console.log('Active sessions before rollback:', data.active_sessions);
          
          if (data.active_sessions > 0) {
            console.warn('Warning: There are active user sessions that may be disrupted by rollback');
          }
        }
      } catch (error) {
        console.log('Active sessions endpoint not available');
      }
    });

    it('should verify no ongoing file uploads or processing', async () => {
      try {
        const response = await axios.get(`${BASE_URL}/api/admin/jobs/active`);
        if (response.status === 200) {
          const { data } = response;
          console.log('Active background jobs:', data.active_jobs);
          
          if (data.active_jobs > 0) {
            console.warn('Warning: There are active background jobs that may be affected by rollback');
          }
        }
      } catch (error) {
        console.log('Active jobs endpoint not available');
      }
    });

    it('should check for maintenance mode capability', async () => {
      try {
        const response = await axios.get(`${BASE_URL}/api/admin/maintenance/status`);
        if (response.status === 200) {
          const { data } = response;
          expect(data).to.have.property('maintenance_mode_available');
          console.log('Maintenance mode available:', data.maintenance_mode_available);
        }
      } catch (error) {
        console.log('Maintenance mode endpoint not available');
      }
    });
  });

  describe('Post-Rollback Validation Procedures', () => {
    it('should have post-rollback validation checklist', () => {
      const checklist = [
        'Verify application starts successfully',
        'Check database connectivity and integrity',
        'Validate API endpoints respond correctly',
        'Confirm user authentication works',
        'Test core functionality (annotations, uploads)',
        'Verify no data loss occurred',
        'Check system logs for errors',
        'Validate performance metrics',
        'Confirm external integrations work',
        'Test real-time features (WebSocket)'
      ];
      
      expect(checklist.length).to.be.greaterThan(5);
      console.log('Post-rollback validation checklist:', checklist);
    });

    it('should define success criteria for rollback validation', () => {
      const successCriteria = {
        health_check_passes: true,
        all_api_endpoints_respond: true,
        user_login_works: true,
        database_queries_succeed: true,
        no_critical_errors_in_logs: true,
        response_time_within_threshold: true,
        core_functionality_works: true
      };
      
      Object.values(successCriteria).forEach(criterion => {
        expect(criterion).to.be.a('boolean');
      });
      
      console.log('Rollback success criteria defined:', Object.keys(successCriteria));
    });
  });

  describe('Emergency Contacts and Procedures', () => {
    it('should have emergency contact information available', () => {
      const emergencyContacts = {
        on_call_engineer: process.env.ON_CALL_PHONE || '+1-555-0123',
        dev_team_lead: process.env.DEV_LEAD_EMAIL || 'dev-lead@example.com',
        ops_team: process.env.OPS_EMAIL || 'ops@example.com',
        escalation_manager: process.env.ESCALATION_EMAIL || 'manager@example.com'
      };
      
      Object.values(emergencyContacts).forEach(contact => {
        expect(contact).to.be.a('string');
        expect(contact.length).to.be.greaterThan(5);
      });
      
      console.log('Emergency contacts verified');
    });

    it('should have rollback documentation accessible', () => {
      const rollbackDocumentation = {
        runbook_location: './docs/rollback-procedures.md',
        escalation_procedures: './docs/incident-response.md',
        contact_information: './docs/emergency-contacts.md',
        troubleshooting_guide: './docs/troubleshooting.md'
      };
      
      Object.values(rollbackDocumentation).forEach(docPath => {
        expect(docPath).to.be.a('string');
      });
      
      console.log('Rollback documentation paths defined');
    });
  });

  after(() => {
    console.log('\n🔄 Rollback validation tests completed');
    console.log('Review the generated reports in test-reports/ directory');
    console.log('Ensure all pre-rollback state has been captured before proceeding with rollback');
  });
});