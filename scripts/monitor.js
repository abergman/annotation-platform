#!/usr/bin/env node

/**
 * Monitoring Script for Annotation Platform
 * Provides real-time monitoring and alerting for production systems
 */

import http from 'http';
import https from 'https';
import { URL } from 'url';
import { EventEmitter } from 'events';
import dotenv from 'dotenv';

// Load environment variables
dotenv.config();

const MONITOR_INTERVAL = parseInt(process.env.MONITOR_INTERVAL || '30000', 10); // 30 seconds
const ALERT_THRESHOLD = parseInt(process.env.ALERT_THRESHOLD || '5', 10); // 5 failures
const NOTIFICATION_WEBHOOK = process.env.SLACK_WEBHOOK_URL;

class SystemMonitor extends EventEmitter {
    constructor(options = {}) {
        super();
        this.interval = options.interval || MONITOR_INTERVAL;
        this.alertThreshold = options.alertThreshold || ALERT_THRESHOLD;
        this.webhookUrl = options.webhookUrl || NOTIFICATION_WEBHOOK;
        this.endpoints = options.endpoints || this.getDefaultEndpoints();
        this.failureCounts = new Map();
        this.lastSuccessful = new Map();
        this.isRunning = false;
        this.monitorTimer = null;
    }

    getDefaultEndpoints() {
        const domain = process.env.DOMAIN || 'localhost:3000';
        const protocol = process.env.SSL_ENABLED === 'true' ? 'https' : 'http';
        
        return [
            {
                name: 'Main API',
                url: `${protocol}://${domain}/health`,
                type: 'http',
                timeout: 10000,
                critical: true
            },
            {
                name: 'API Endpoint',
                url: `${protocol}://${domain}/api/health`,
                type: 'http',
                timeout: 10000,
                critical: true
            },
            {
                name: 'WebSocket',
                url: `${protocol.replace('http', 'ws')}://${domain}/socket.io`,
                type: 'websocket',
                timeout: 15000,
                critical: true
            },
            {
                name: 'Database Status',
                url: `${protocol}://${domain}/api/status/db`,
                type: 'http',
                timeout: 5000,
                critical: true
            }
        ];
    }

    log(message, level = 'info') {
        const timestamp = new Date().toISOString();
        const prefix = `[${timestamp}] [${level.toUpperCase()}]`;
        console.log(`${prefix} ${message}`);
    }

    async checkEndpoint(endpoint) {
        const startTime = Date.now();
        
        try {
            let result;
            
            if (endpoint.type === 'websocket') {
                result = await this.checkWebSocket(endpoint.url, endpoint.timeout);
            } else {
                result = await this.checkHttp(endpoint.url, endpoint.timeout);
            }
            
            result.responseTime = Date.now() - startTime;
            result.endpoint = endpoint.name;
            result.critical = endpoint.critical;
            
            return result;
        } catch (error) {
            return {
                endpoint: endpoint.name,
                url: endpoint.url,
                healthy: false,
                error: error.message,
                responseTime: Date.now() - startTime,
                critical: endpoint.critical
            };
        }
    }

    async checkHttp(url, timeout) {
        return new Promise((resolve, reject) => {
            const urlObj = new URL(url);
            const isHttps = urlObj.protocol === 'https:';
            const client = isHttps ? https : http;
            
            const options = {
                hostname: urlObj.hostname,
                port: urlObj.port || (isHttps ? 443 : 80),
                path: urlObj.pathname + urlObj.search,
                method: 'GET',
                timeout: timeout,
                headers: {
                    'User-Agent': 'SystemMonitor/1.0'
                }
            };

            const req = client.request(options, (res) => {
                let data = '';
                
                res.on('data', (chunk) => {
                    data += chunk;
                });
                
                res.on('end', () => {
                    resolve({
                        url,
                        status: res.statusCode,
                        healthy: res.statusCode >= 200 && res.statusCode < 400,
                        body: data
                    });
                });
            });

            req.on('error', (err) => {
                reject(new Error(`HTTP request failed: ${err.message}`));
            });

            req.on('timeout', () => {
                req.destroy();
                reject(new Error(`Request timed out after ${timeout}ms`));
            });

            req.end();
        });
    }

    async checkWebSocket(url, timeout) {
        // For WebSocket monitoring, we'll do a simple HTTP check to the base URL
        // In a real implementation, you'd use the 'ws' package
        const httpUrl = url.replace(/^ws/, 'http');
        return this.checkHttp(httpUrl, timeout);
    }

    async runHealthChecks() {
        const results = await Promise.allSettled(
            this.endpoints.map(endpoint => this.checkEndpoint(endpoint))
        );

        const checkResults = results.map((result, index) => {
            const endpoint = this.endpoints[index];
            
            if (result.status === 'fulfilled') {
                return result.value;
            } else {
                return {
                    endpoint: endpoint.name,
                    url: endpoint.url,
                    healthy: false,
                    error: result.reason.message,
                    critical: endpoint.critical
                };
            }
        });

        return checkResults;
    }

    updateFailureCounts(results) {
        results.forEach(result => {
            const endpointName = result.endpoint;
            
            if (result.healthy) {
                this.failureCounts.delete(endpointName);
                this.lastSuccessful.set(endpointName, new Date());
            } else {
                const currentCount = this.failureCounts.get(endpointName) || 0;
                this.failureCounts.set(endpointName, currentCount + 1);
            }
        });
    }

    analyzeResults(results) {
        const analysis = {
            totalEndpoints: results.length,
            healthyEndpoints: results.filter(r => r.healthy).length,
            unhealthyEndpoints: results.filter(r => !r.healthy).length,
            criticalFailures: results.filter(r => !r.healthy && r.critical).length,
            averageResponseTime: 0,
            alerts: []
        };

        // Calculate average response time
        const responseTimes = results.filter(r => r.responseTime).map(r => r.responseTime);
        if (responseTimes.length > 0) {
            analysis.averageResponseTime = Math.round(
                responseTimes.reduce((sum, time) => sum + time, 0) / responseTimes.length
            );
        }

        // Check for alerts
        results.forEach(result => {
            if (!result.healthy) {
                const failureCount = this.failureCounts.get(result.endpoint) || 0;
                
                if (failureCount >= this.alertThreshold) {
                    analysis.alerts.push({
                        type: result.critical ? 'CRITICAL' : 'WARNING',
                        endpoint: result.endpoint,
                        message: `${result.endpoint} has failed ${failureCount} consecutive times`,
                        error: result.error,
                        url: result.url
                    });
                }
            }
        });

        return analysis;
    }

    async sendAlert(alert) {
        if (!this.webhookUrl) {
            this.log('No webhook URL configured, skipping alert notification', 'warning');
            return;
        }

        const message = {
            text: `🚨 ${alert.type}: ${alert.message}`,
            attachments: [{
                color: alert.type === 'CRITICAL' ? 'danger' : 'warning',
                fields: [
                    {
                        title: 'Endpoint',
                        value: alert.endpoint,
                        short: true
                    },
                    {
                        title: 'URL',
                        value: alert.url,
                        short: true
                    },
                    {
                        title: 'Error',
                        value: alert.error,
                        short: false
                    },
                    {
                        title: 'Time',
                        value: new Date().toISOString(),
                        short: true
                    }
                ]
            }]
        };

        try {
            const { URL } = await import('url');
            const webhookUrl = new URL(this.webhookUrl);
            const isHttps = webhookUrl.protocol === 'https:';
            const client = isHttps ? https : http;
            
            const postData = JSON.stringify(message);
            
            const options = {
                hostname: webhookUrl.hostname,
                port: webhookUrl.port || (isHttps ? 443 : 80),
                path: webhookUrl.pathname,
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Content-Length': Buffer.byteLength(postData)
                }
            };

            const req = client.request(options, (res) => {
                if (res.statusCode === 200) {
                    this.log(`Alert sent successfully for ${alert.endpoint}`, 'info');
                } else {
                    this.log(`Failed to send alert: HTTP ${res.statusCode}`, 'error');
                }
            });

            req.on('error', (err) => {
                this.log(`Error sending alert: ${err.message}`, 'error');
            });

            req.write(postData);
            req.end();
        } catch (error) {
            this.log(`Alert sending failed: ${error.message}`, 'error');
        }
    }

    async performMonitoringCycle() {
        this.log('Starting monitoring cycle...');
        
        try {
            const results = await this.runHealthChecks();
            this.updateFailureCounts(results);
            const analysis = this.analyzeResults(results);
            
            // Log summary
            this.log(`Health check completed: ${analysis.healthyEndpoints}/${analysis.totalEndpoints} healthy, avg response: ${analysis.averageResponseTime}ms`);
            
            // Log individual results
            results.forEach(result => {
                const status = result.healthy ? '✅' : '❌';
                const time = result.responseTime ? `${result.responseTime}ms` : 'N/A';
                this.log(`${status} ${result.endpoint}: ${time}`);
                
                if (!result.healthy) {
                    this.log(`   Error: ${result.error}`, 'error');
                }
            });
            
            // Send alerts for critical failures
            for (const alert of analysis.alerts) {
                await this.sendAlert(alert);
                this.emit('alert', alert);
            }
            
            // Emit monitoring event
            this.emit('monitoring-cycle', {
                results,
                analysis,
                timestamp: new Date()
            });
            
        } catch (error) {
            this.log(`Monitoring cycle failed: ${error.message}`, 'error');
            this.emit('error', error);
        }
    }

    start() {
        if (this.isRunning) {
            this.log('Monitor is already running', 'warning');
            return;
        }
        
        this.log(`Starting system monitor with ${this.interval}ms interval`);
        this.log(`Monitoring ${this.endpoints.length} endpoints:`);
        
        this.endpoints.forEach(endpoint => {
            this.log(`  - ${endpoint.name}: ${endpoint.url} (${endpoint.type})`);
        });
        
        this.isRunning = true;
        
        // Run first check immediately
        this.performMonitoringCycle();
        
        // Schedule regular checks
        this.monitorTimer = setInterval(() => {
            this.performMonitoringCycle();
        }, this.interval);
        
        this.emit('started');
    }

    stop() {
        if (!this.isRunning) {
            this.log('Monitor is not running', 'warning');
            return;
        }
        
        this.log('Stopping system monitor');
        
        if (this.monitorTimer) {
            clearInterval(this.monitorTimer);
            this.monitorTimer = null;
        }
        
        this.isRunning = false;
        this.emit('stopped');
    }

    getStatus() {
        return {
            isRunning: this.isRunning,
            interval: this.interval,
            endpoints: this.endpoints.length,
            failureCounts: Object.fromEntries(this.failureCounts),
            lastSuccessful: Object.fromEntries(this.lastSuccessful)
        };
    }
}

// Command line interface
async function main() {
    const args = process.argv.slice(2);
    const command = args[0] || 'start';
    
    const monitor = new SystemMonitor();
    
    // Handle graceful shutdown
    process.on('SIGINT', () => {
        console.log('\nReceived SIGINT, shutting down gracefully...');
        monitor.stop();
        process.exit(0);
    });
    
    process.on('SIGTERM', () => {
        console.log('\nReceived SIGTERM, shutting down gracefully...');
        monitor.stop();
        process.exit(0);
    });
    
    switch (command) {
        case 'start':
            monitor.start();
            break;
            
        case 'check':
            {
                console.log('Running single health check...');
                const results = await monitor.runHealthChecks();
                const analysis = monitor.analyzeResults(results);
                
                console.log(`\n=== Health Check Results ===`);
                console.log(`Status: ${analysis.healthyEndpoints}/${analysis.totalEndpoints} healthy`);
                console.log(`Average Response Time: ${analysis.averageResponseTime}ms`);
                
                results.forEach(result => {
                    const status = result.healthy ? '✅' : '❌';
                    const time = result.responseTime ? ` (${result.responseTime}ms)` : '';
                    console.log(`${status} ${result.endpoint}${time}`);
                    
                    if (!result.healthy) {
                        console.log(`   Error: ${result.error}`);
                    }
                });
                
                process.exit(analysis.unhealthyEndpoints > 0 ? 1 : 0);
            }
            break;
            
        case 'status':
            {
                const status = monitor.getStatus();
                console.log('Monitor Status:', JSON.stringify(status, null, 2));
            }
            break;
            
        default:
            console.log(`
System Monitor for Annotation Platform

Usage:
  node monitor.js [command]

Commands:
  start        # Start continuous monitoring (default)
  check        # Run single health check and exit
  status       # Show monitor status

Environment Variables:
  MONITOR_INTERVAL     # Check interval in ms (default: 30000)
  ALERT_THRESHOLD      # Failures before alert (default: 5)
  SLACK_WEBHOOK_URL    # Webhook for alerts
  DOMAIN               # Domain to monitor (default: localhost:3000)
  SSL_ENABLED          # Use HTTPS/WSS (default: false)

Examples:
  node monitor.js                    # Start monitoring
  node monitor.js check              # Single check
  MONITOR_INTERVAL=10000 node monitor.js start  # 10s interval
            `);
            break;
    }
}

// Export for use as a module
export { SystemMonitor };

// Run if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
    main().catch(console.error);
}