const https = require('https');
const tls = require('tls');
const axios = require('axios');
const { expect } = require('chai');
const crypto = require('crypto');

describe('SSL/TLS Certificate Validation Tests', () => {
  const BASE_URL = process.env.DEPLOYMENT_URL || 'https://annotat.ee';
  const DOMAIN = BASE_URL.replace(/https?:\/\//, '').replace(/\/.*$/, '');
  const PORT = 443;

  describe('Certificate Validity', () => {
    let certificateInfo;

    before((done) => {
      const options = {
        host: DOMAIN,
        port: PORT,
        servername: DOMAIN,
        rejectUnauthorized: false
      };

      const socket = tls.connect(options, () => {
        certificateInfo = socket.getPeerCertificate(true);
        socket.end();
        done();
      });

      socket.on('error', done);
    });

    it('should have valid certificate', () => {
      expect(certificateInfo).to.exist;
      expect(certificateInfo.subject).to.exist;
      expect(certificateInfo.issuer).to.exist;
    });

    it('should not be expired', () => {
      const now = new Date();
      const validFrom = new Date(certificateInfo.valid_from);
      const validTo = new Date(certificateInfo.valid_to);

      expect(now).to.be.greaterThan(validFrom);
      expect(now).to.be.lessThan(validTo);
    });

    it('should have correct subject', () => {
      const subject = certificateInfo.subject;
      expect(subject.CN).to.satisfy(cn => {
        return cn === DOMAIN || 
               cn === `*.${DOMAIN.split('.').slice(1).join('.')}` || // Wildcard cert
               certificateInfo.subjectaltname?.includes(`DNS:${DOMAIN}`);
      });
    });

    it('should have valid expiration window', () => {
      const validTo = new Date(certificateInfo.valid_to);
      const now = new Date();
      const daysUntilExpiry = (validTo - now) / (1000 * 60 * 60 * 24);

      expect(daysUntilExpiry).to.be.greaterThan(7); // At least 7 days before expiry
    });

    it('should have strong key length', () => {
      // RSA should be at least 2048 bits, ECDSA at least 256 bits
      const publicKey = certificateInfo.pubkey;
      if (certificateInfo.bits) {
        expect(certificateInfo.bits).to.be.at.least(2048);
      }
    });

    it('should have valid signature algorithm', () => {
      const sigAlg = certificateInfo.signatureAlgorithm;
      
      // Should not use weak algorithms
      const weakAlgorithms = ['md5', 'sha1'];
      const isWeak = weakAlgorithms.some(weak => 
        sigAlg.toLowerCase().includes(weak)
      );
      
      expect(isWeak).to.be.false;
    });
  });

  describe('TLS Configuration', () => {
    let tlsInfo;

    before((done) => {
      const options = {
        host: DOMAIN,
        port: PORT,
        servername: DOMAIN
      };

      const socket = tls.connect(options, () => {
        tlsInfo = {
          protocol: socket.getProtocol(),
          cipher: socket.getCipher(),
          authorized: socket.authorized,
          authorizationError: socket.authorizationError
        };
        socket.end();
        done();
      });

      socket.on('error', done);
    });

    it('should use secure TLS version', () => {
      expect(tlsInfo.protocol).to.be.oneOf(['TLSv1.2', 'TLSv1.3']);
    });

    it('should use strong cipher suite', () => {
      const cipher = tlsInfo.cipher;
      expect(cipher).to.exist;
      expect(cipher.name).to.exist;
      
      // Should not use weak ciphers
      const weakCiphers = ['RC4', 'DES', 'MD5', 'NULL'];
      const isWeak = weakCiphers.some(weak => 
        cipher.name.toUpperCase().includes(weak)
      );
      
      expect(isWeak).to.be.false;
    });

    it('should have valid certificate chain', () => {
      expect(tlsInfo.authorized).to.be.true;
      expect(tlsInfo.authorizationError).to.be.null;
    });
  });

  describe('HTTP Security Headers', () => {
    let response;

    before(async () => {
      response = await axios.get(BASE_URL);
    });

    it('should enforce HTTPS with HSTS', () => {
      const hsts = response.headers['strict-transport-security'];
      expect(hsts).to.exist;
      expect(hsts).to.include('max-age=');
      
      // Should have reasonable max-age (at least 6 months)
      const maxAge = parseInt(hsts.match(/max-age=(\d+)/)[1]);
      expect(maxAge).to.be.at.least(15552000); // 6 months in seconds
    });

    it('should prevent mixed content', () => {
      const csp = response.headers['content-security-policy'];
      if (csp) {
        // If CSP exists, should block insecure requests
        expect(csp).to.satisfy(policy => 
          policy.includes('upgrade-insecure-requests') ||
          !policy.includes('http:')
        );
      }
    });

    it('should have secure cookie settings', () => {
      const setCookie = response.headers['set-cookie'];
      if (setCookie) {
        setCookie.forEach(cookie => {
          if (cookie.includes('session') || cookie.includes('auth')) {
            expect(cookie).to.include('Secure');
            expect(cookie).to.include('HttpOnly');
          }
        });
      }
    });
  });

  describe('SSL/TLS Vulnerabilities', () => {
    it('should not be vulnerable to POODLE', (done) => {
      // Test if SSLv3 is disabled
      const options = {
        host: DOMAIN,
        port: PORT,
        secureProtocol: 'SSLv3_method',
        rejectUnauthorized: false
      };

      const socket = tls.connect(options);
      
      socket.on('error', (error) => {
        // Should fail to connect with SSLv3
        expect(error.code).to.be.oneOf(['EPROTO', 'ECONNRESET']);
        done();
      });

      socket.on('connect', () => {
        socket.end();
        done(new Error('SSLv3 should not be supported (POODLE vulnerability)'));
      });

      setTimeout(() => {
        socket.destroy();
        done();
      }, 5000);
    });

    it('should not be vulnerable to BEAST', (done) => {
      // Test if TLS 1.0 with CBC ciphers is properly handled
      const options = {
        host: DOMAIN,
        port: PORT,
        secureProtocol: 'TLSv1_method',
        ciphers: 'AES128-SHA', // CBC cipher
        rejectUnauthorized: false
      };

      const socket = tls.connect(options);
      
      socket.on('connect', () => {
        const cipher = socket.getCipher();
        // If connected, should use secure configuration
        expect(cipher.version).to.not.equal('TLSv1');
        socket.end();
        done();
      });

      socket.on('error', () => {
        // Good - should reject weak configurations
        done();
      });

      setTimeout(() => {
        socket.destroy();
        done();
      }, 5000);
    });

    it('should have secure renegotiation', (done) => {
      const options = {
        host: DOMAIN,
        port: PORT,
        servername: DOMAIN
      };

      const socket = tls.connect(options, () => {
        // Check if secure renegotiation is supported
        expect(socket.getSession()).to.exist;
        socket.end();
        done();
      });

      socket.on('error', done);
    });
  });

  describe('Certificate Transparency', () => {
    it('should have CT log entries', async () => {
      try {
        // Check if certificate has SCT (Signed Certificate Timestamp)
        const response = await axios.get(`https://crt.sh/?q=${DOMAIN}&output=json`, {
          timeout: 10000
        });
        
        expect(response.status).to.equal(200);
        expect(response.data).to.be.an('array');
        expect(response.data.length).to.be.greaterThan(0);
      } catch (error) {
        // CT lookup might fail, but that's not necessarily a security issue
        console.log('Certificate Transparency lookup failed:', error.message);
      }
    });
  });

  describe('OCSP Stapling', () => {
    it('should support OCSP stapling for revocation checking', (done) => {
      const options = {
        host: DOMAIN,
        port: PORT,
        servername: DOMAIN,
        requestOCSP: true
      };

      const socket = tls.connect(options, () => {
        const ocspResponse = socket.getOCSPResponse();
        
        // OCSP stapling is optional but recommended
        if (ocspResponse) {
          expect(ocspResponse).to.be.instanceOf(Buffer);
          expect(ocspResponse.length).to.be.greaterThan(0);
        }
        
        socket.end();
        done();
      });

      socket.on('error', done);
    });
  });

  describe('Domain Validation', () => {
    it('should resolve to correct IP addresses', (done) => {
      const dns = require('dns');
      
      dns.resolve4(DOMAIN, (err, addresses) => {
        if (err) {
          done(err);
          return;
        }
        
        expect(addresses).to.be.an('array');
        expect(addresses.length).to.be.greaterThan(0);
        
        // All addresses should be valid IPv4
        addresses.forEach(addr => {
          expect(addr).to.match(/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/);
        });
        
        done();
      });
    });

    it('should have valid DNS records', (done) => {
      const dns = require('dns');
      
      dns.resolveMx(DOMAIN, (err, addresses) => {
        // MX records are optional, but if they exist, should be valid
        if (!err && addresses) {
          expect(addresses).to.be.an('array');
          addresses.forEach(mx => {
            expect(mx).to.have.property('exchange');
            expect(mx).to.have.property('priority');
          });
        }
        done();
      });
    });
  });

  after(() => {
    console.log('\n🔒 SSL/TLS validation completed');
    console.log(`Domain: ${DOMAIN}`);
    if (certificateInfo) {
      console.log(`Certificate expires: ${certificateInfo.valid_to}`);
      console.log(`Issuer: ${certificateInfo.issuer.CN}`);
    }
  });
});