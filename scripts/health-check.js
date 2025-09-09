#!/usr/bin/env node

/**
 * Health Check Script for Annotation Platform
 * Monitors application health across HTTP and WebSocket endpoints
 */

import http from 'http';
import https from 'https';
import { URL } from 'url';
import WebSocket from 'ws';

// Configuration
const DEFAULT_TIMEOUT = 30000; // 30 seconds
const DEFAULT_RETRIES = 3;
const DEFAULT_RETRY_DELAY = 5000; // 5 seconds

class HealthChecker {
    constructor(options = {}) {
        this.timeout = options.timeout || DEFAULT_TIMEOUT;
        this.retries = options.retries || DEFAULT_RETRIES;
        this.retryDelay = options.retryDelay || DEFAULT_RETRY_DELAY;
        this.verbose = options.verbose || false;
        this.results = [];
    }

    log(message, level = 'info') {
        const timestamp = new Date().toISOString();
        const prefix = `[${timestamp}] [${level.toUpperCase()}]`;
        
        if (this.verbose || level === 'error') {
            console.log(`${prefix} ${message}`);
        }
    }

    async delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    async checkHttp(url) {
        return new Promise((resolve, reject) => {
            const urlObj = new URL(url);
            const isHttps = urlObj.protocol === 'https:';
            const client = isHttps ? https : http;
            
            const options = {
                hostname: urlObj.hostname,
                port: urlObj.port || (isHttps ? 443 : 80),
                path: urlObj.pathname + urlObj.search,
                method: 'GET',
                timeout: this.timeout,
                headers: {
                    'User-Agent': 'HealthChecker/1.0',
                    'Accept': 'application/json, text/plain, */*'
                }
            };

            const req = client.request(options, (res) => {
                let data = '';
                
                res.on('data', (chunk) => {
                    data += chunk;
                });
                
                res.on('end', () => {
                    const result = {
                        url,
                        status: res.statusCode,
                        headers: res.headers,
                        body: data,
                        responseTime: Date.now() - startTime,
                        healthy: res.statusCode >= 200 && res.statusCode < 400
                    };
                    
                    resolve(result);
                });
            });

            req.on('error', (err) => {
                reject(new Error(`HTTP request failed: ${err.message}`));
            });

            req.on('timeout', () => {
                req.destroy();
                reject(new Error(`HTTP request timed out after ${this.timeout}ms`));
            });

            const startTime = Date.now();
            req.end();
        });
    }

    async checkWebSocket(url) {
        return new Promise((resolve, reject) => {
            const startTime = Date.now();
            let ws;

            const cleanup = () => {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.close();
                }
            };

            const timeout = setTimeout(() => {
                cleanup();
                reject(new Error(`WebSocket connection timed out after ${this.timeout}ms`));
            }, this.timeout);

            try {
                ws = new WebSocket(url, {
                    headers: {
                        'User-Agent': 'HealthChecker/1.0'
                    }
                });

                ws.on('open', () => {
                    clearTimeout(timeout);
                    const responseTime = Date.now() - startTime;
                    
                    // Send a ping to test full connectivity
                    ws.ping();
                    
                    ws.on('pong', () => {
                        cleanup();
                        resolve({
                            url,
                            status: 'connected',
                            responseTime,
                            healthy: true
                        });
                    });

                    // Fallback if pong is not received
                    setTimeout(() => {
                        cleanup();
                        resolve({
                            url,
                            status: 'connected',
                            responseTime,
                            healthy: true
                        });
                    }, 1000);
                });

                ws.on('error', (err) => {
                    clearTimeout(timeout);
                    cleanup();
                    reject(new Error(`WebSocket connection failed: ${err.message}`));
                });

                ws.on('close', (code) => {
                    clearTimeout(timeout);
                    if (code !== 1000) {
                        reject(new Error(`WebSocket closed with code: ${code}`));
                    }
                });

            } catch (err) {
                clearTimeout(timeout);
                reject(new Error(`WebSocket initialization failed: ${err.message}`));
            }
        });
    }

    async checkEndpoint(url, type = 'http') {
        this.log(`Checking ${type.toUpperCase()} endpoint: ${url}`, 'info');
        
        for (let attempt = 1; attempt <= this.retries; attempt++) {
            try {
                const result = type === 'websocket' 
                    ? await this.checkWebSocket(url)
                    : await this.checkHttp(url);
                
                this.results.push(result);
                
                if (result.healthy) {
                    this.log(`✅ ${url} is healthy (${result.responseTime}ms)`, 'info');
                    return result;
                } else {
                    this.log(`❌ ${url} is unhealthy: ${result.status}`, 'error');
                    if (attempt < this.retries) {
                        this.log(`Retrying in ${this.retryDelay}ms... (${attempt}/${this.retries})`, 'info');
                        await this.delay(this.retryDelay);
                    }
                }
            } catch (error) {
                this.log(`❌ ${url} failed: ${error.message}`, 'error');
                this.results.push({
                    url,
                    status: 'error',
                    error: error.message,
                    healthy: false
                });
                
                if (attempt < this.retries) {
                    this.log(`Retrying in ${this.retryDelay}ms... (${attempt}/${this.retries})`, 'info');
                    await this.delay(this.retryDelay);
                } else {
                    throw error;
                }
            }
        }
        
        throw new Error(`All ${this.retries} attempts failed for ${url}`);
    }

    async checkMultiple(endpoints) {
        this.log('Starting health check for multiple endpoints', 'info');
        const promises = endpoints.map(async (endpoint) => {
            try {
                return await this.checkEndpoint(endpoint.url, endpoint.type);
            } catch (error) {
                return {
                    url: endpoint.url,
                    type: endpoint.type,
                    error: error.message,
                    healthy: false
                };
            }
        });

        const results = await Promise.allSettled(promises);
        
        // Compile summary
        const summary = {
            total: results.length,
            healthy: 0,
            unhealthy: 0,
            errors: 0
        };

        results.forEach((result, index) => {
            if (result.status === 'fulfilled') {
                if (result.value.healthy) {
                    summary.healthy++;
                } else {
                    summary.unhealthy++;
                }
            } else {
                summary.errors++;
                this.log(`Endpoint ${endpoints[index].url} threw an error: ${result.reason}`, 'error');
            }
        });

        return {
            summary,
            results: results.map(r => r.status === 'fulfilled' ? r.value : r.reason),
            overallHealth: summary.healthy === summary.total
        };
    }

    generateReport(checkResults) {
        const { summary, results, overallHealth } = checkResults;
        
        console.log('\n=== Health Check Report ===');
        console.log(`Overall Status: ${overallHealth ? '✅ HEALTHY' : '❌ UNHEALTHY'}`);
        console.log(`Total Endpoints: ${summary.total}`);
        console.log(`Healthy: ${summary.healthy}`);
        console.log(`Unhealthy: ${summary.unhealthy}`);
        console.log(`Errors: ${summary.errors}`);
        console.log('\n=== Endpoint Details ===');
        
        results.forEach((result) => {
            if (result && typeof result === 'object') {
                const status = result.healthy ? '✅' : '❌';
                const time = result.responseTime ? ` (${result.responseTime}ms)` : '';
                console.log(`${status} ${result.url}${time}`);
                
                if (!result.healthy && result.error) {
                    console.log(`   Error: ${result.error}`);
                }
            }
        });
        
        console.log('=========================\n');
        
        return overallHealth;
    }
}

// Default endpoint configurations
const DEFAULT_ENDPOINTS = [
    { url: 'http://localhost:3000/health', type: 'http' },
    { url: 'http://localhost:3000/api/health', type: 'http' },
    { url: 'ws://localhost:3001', type: 'websocket' }
];

// Command line interface
async function main() {
    const args = process.argv.slice(2);
    let url = null;
    let type = 'http';
    let timeout = DEFAULT_TIMEOUT;
    let retries = DEFAULT_RETRIES;
    let verbose = false;
    let endpoints = DEFAULT_ENDPOINTS;

    // Parse command line arguments
    for (let i = 0; i < args.length; i++) {
        switch (args[i]) {
            case '--url':
                url = args[++i];
                break;
            case '--type':
                type = args[++i];
                break;
            case '--timeout':
                timeout = parseInt(args[++i], 10);
                break;
            case '--retries':
                retries = parseInt(args[++i], 10);
                break;
            case '--verbose':
                verbose = true;
                break;
            case '--help':
                console.log(`
Health Check Script for Annotation Platform

Usage: node health-check.js [options]

Options:
  --url <url>        URL to check (if not provided, checks default endpoints)
  --type <type>      Check type: http or websocket (default: http)
  --timeout <ms>     Request timeout in milliseconds (default: 30000)
  --retries <num>    Number of retry attempts (default: 3)
  --verbose          Enable verbose logging
  --help             Show this help message

Examples:
  node health-check.js                                    # Check default endpoints
  node health-check.js --url https://annotat.ee          # Check specific URL
  node health-check.js --url wss://annotat.ee/socket.io --type websocket
  node health-check.js --url https://staging.annotat.ee --timeout 60000 --verbose
                `);
                process.exit(0);
        }
    }

    const checker = new HealthChecker({ timeout, retries, verbose });

    try {
        if (url) {
            // Check single endpoint
            await checker.checkEndpoint(url, type);
            console.log('✅ Health check passed');
            process.exit(0);
        } else {
            // Check multiple default endpoints
            const results = await checker.checkMultiple(endpoints);
            const isHealthy = checker.generateReport(results);
            process.exit(isHealthy ? 0 : 1);
        }
    } catch (error) {
        console.error(`❌ Health check failed: ${error.message}`);
        if (verbose) {
            console.error(error.stack);
        }
        process.exit(1);
    }
}

// Export for use as a module
export { HealthChecker };

// Run if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
    main().catch(console.error);
}