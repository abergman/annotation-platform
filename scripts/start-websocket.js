#!/usr/bin/env node
/**
 * WebSocket Server Startup Script
 * 
 * Starts the real-time WebSocket server with proper environment configuration
 */

import { config } from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Load environment variables
config({ path: path.join(__dirname, '..', '.env') });

// Set default environment variables
const env = {
  NODE_ENV: process.env.NODE_ENV || 'development',
  WEBSOCKET_PORT: process.env.WEBSOCKET_PORT || 8001,
  API_URL: process.env.API_URL || 'http://localhost:8000',
  FRONTEND_URL: process.env.FRONTEND_URL || 'http://localhost:5173',
  JWT_SECRET: process.env.JWT_SECRET || 'your-secret-key',
  REDIS_URL: process.env.REDIS_URL,
  LOG_LEVEL: process.env.LOG_LEVEL || 'info',
  LOG_DIR: process.env.LOG_DIR || 'logs'
};

// Validate required environment variables
const required = ['JWT_SECRET'];
const missing = required.filter(key => !env[key] || env[key] === 'your-secret-key');

if (missing.length > 0) {
  console.error('❌ Missing required environment variables:');
  missing.forEach(key => console.error(`   ${key}`));
  console.error('\nPlease create a .env file with the required variables.');
  process.exit(1);
}

// Apply environment variables
Object.assign(process.env, env);

console.log('🚀 Starting WebSocket Server...\n');
console.log('Configuration:');
console.log(`   Environment: ${env.NODE_ENV}`);
console.log(`   WebSocket Port: ${env.WEBSOCKET_PORT}`);
console.log(`   API URL: ${env.API_URL}`);
console.log(`   Frontend URL: ${env.FRONTEND_URL}`);
console.log(`   Redis: ${env.REDIS_URL ? '✅ Enabled' : '❌ Disabled (in-memory mode)'}`);
console.log(`   Log Level: ${env.LOG_LEVEL}`);
console.log(`   Log Directory: ${env.LOG_DIR}\n`);

// Start the WebSocket server
try {
  await import('../src/websocket-server.js');
} catch (error) {
  console.error('❌ Failed to start WebSocket server:', error);
  process.exit(1);
}