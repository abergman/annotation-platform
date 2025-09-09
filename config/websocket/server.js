/**
 * WebSocket Server for Academic Annotation Platform
 * Handles real-time updates for annotation sessions
 */

const express = require('express');
const WebSocket = require('ws');
const http = require('http');
const cors = require('cors');
const redis = require('redis');
const { v4: uuidv4 } = require('uuid');

// Configuration
const PORT = process.env.PORT || 3001;
const REDIS_URL = process.env.REDIS_URL || 'redis://localhost:6379';
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

// Initialize Express app
const app = express();
app.use(cors());
app.use(express.json());

// Create HTTP server
const server = http.createServer(app);

// Initialize Redis client
let redisClient;
try {
  redisClient = redis.createClient({ url: REDIS_URL });
  redisClient.connect();
  console.log('✅ Connected to Redis');
} catch (error) {
  console.warn('⚠️  Redis connection failed, running without caching:', error.message);
}

// WebSocket server
const wss = new WebSocket.Server({ 
  server,
  path: '/ws'
});

// Store active connections
const connections = new Map();
const projectRooms = new Map();

// WebSocket connection handler
wss.on('connection', (ws, req) => {
  const connectionId = uuidv4();
  const userAgent = req.headers['user-agent'] || 'Unknown';
  
  console.log(`🔌 New WebSocket connection: ${connectionId}`);
  
  // Store connection
  connections.set(connectionId, {
    socket: ws,
    userId: null,
    projectId: null,
    connectedAt: new Date(),
    userAgent
  });

  // Handle incoming messages
  ws.on('message', async (data) => {
    try {
      const message = JSON.parse(data.toString());
      await handleMessage(connectionId, message);
    } catch (error) {
      console.error('❌ Error handling message:', error);
      ws.send(JSON.stringify({
        type: 'error',
        message: 'Invalid message format'
      }));
    }
  });

  // Handle connection close
  ws.on('close', () => {
    console.log(`🔌 Connection closed: ${connectionId}`);
    cleanupConnection(connectionId);
  });

  // Handle errors
  ws.on('error', (error) => {
    console.error(`❌ WebSocket error for ${connectionId}:`, error);
    cleanupConnection(connectionId);
  });

  // Send welcome message
  ws.send(JSON.stringify({
    type: 'connected',
    connectionId,
    message: 'Connected to annotation WebSocket server'
  }));
});

// Message handler
async function handleMessage(connectionId, message) {
  const connection = connections.get(connectionId);
  if (!connection) return;

  const { socket } = connection;

  switch (message.type) {
    case 'auth':
      // Authenticate user
      connection.userId = message.userId;
      connection.projectId = message.projectId;
      
      // Join project room
      if (message.projectId) {
        joinProjectRoom(connectionId, message.projectId);
      }
      
      socket.send(JSON.stringify({
        type: 'auth_success',
        userId: message.userId,
        projectId: message.projectId
      }));
      break;

    case 'join_project':
      // Join specific project room
      if (connection.projectId && connection.projectId !== message.projectId) {
        leaveProjectRoom(connectionId, connection.projectId);
      }
      
      connection.projectId = message.projectId;
      joinProjectRoom(connectionId, message.projectId);
      
      socket.send(JSON.stringify({
        type: 'joined_project',
        projectId: message.projectId
      }));
      break;

    case 'annotation_update':
      // Broadcast annotation updates to project room
      if (connection.projectId) {
        broadcastToProject(connection.projectId, {
          type: 'annotation_updated',
          data: message.data,
          userId: connection.userId,
          timestamp: new Date().toISOString()
        }, connectionId);
      }
      break;

    case 'batch_progress':
      // Broadcast batch operation progress
      if (connection.projectId && message.operationId) {
        broadcastToProject(connection.projectId, {
          type: 'batch_progress_update',
          operationId: message.operationId,
          progress: message.progress,
          timestamp: new Date().toISOString()
        }, connectionId);
      }
      break;

    case 'ping':
      // Respond to ping
      socket.send(JSON.stringify({
        type: 'pong',
        timestamp: new Date().toISOString()
      }));
      break;

    default:
      socket.send(JSON.stringify({
        type: 'error',
        message: `Unknown message type: ${message.type}`
      }));
  }

  // Cache message in Redis if available
  if (redisClient && message.type !== 'ping') {
    try {
      await redisClient.hSet(
        `ws:messages:${connectionId}`,
        Date.now().toString(),
        JSON.stringify(message)
      );
      await redisClient.expire(`ws:messages:${connectionId}`, 3600); // 1 hour TTL
    } catch (error) {
      console.warn('⚠️  Redis caching failed:', error.message);
    }
  }
}

// Join project room
function joinProjectRoom(connectionId, projectId) {
  if (!projectRooms.has(projectId)) {
    projectRooms.set(projectId, new Set());
  }
  projectRooms.get(projectId).add(connectionId);
  console.log(`👥 Connection ${connectionId} joined project ${projectId}`);
}

// Leave project room
function leaveProjectRoom(connectionId, projectId) {
  if (projectRooms.has(projectId)) {
    projectRooms.get(projectId).delete(connectionId);
    if (projectRooms.get(projectId).size === 0) {
      projectRooms.delete(projectId);
    }
  }
  console.log(`👥 Connection ${connectionId} left project ${projectId}`);
}

// Broadcast message to all connections in a project
function broadcastToProject(projectId, message, excludeConnectionId = null) {
  const room = projectRooms.get(projectId);
  if (!room) return;

  const messageStr = JSON.stringify(message);
  let sentCount = 0;

  room.forEach(connectionId => {
    if (connectionId === excludeConnectionId) return;
    
    const connection = connections.get(connectionId);
    if (connection && connection.socket.readyState === WebSocket.OPEN) {
      try {
        connection.socket.send(messageStr);
        sentCount++;
      } catch (error) {
        console.error(`❌ Failed to send to ${connectionId}:`, error);
        cleanupConnection(connectionId);
      }
    }
  });

  console.log(`📢 Broadcasted to ${sentCount} connections in project ${projectId}`);
}

// Cleanup connection
function cleanupConnection(connectionId) {
  const connection = connections.get(connectionId);
  if (connection && connection.projectId) {
    leaveProjectRoom(connectionId, connection.projectId);
  }
  connections.delete(connectionId);
}

// Health check endpoint
app.get('/health', (req, res) => {
  const stats = {
    status: 'healthy',
    timestamp: new Date().toISOString(),
    connections: {
      total: connections.size,
      by_project: {}
    },
    uptime: process.uptime(),
    memory: process.memoryUsage()
  };

  // Count connections by project
  projectRooms.forEach((connectionIds, projectId) => {
    stats.connections.by_project[projectId] = connectionIds.size;
  });

  res.json(stats);
});

// Connection stats endpoint
app.get('/stats', (req, res) => {
  const stats = {
    total_connections: connections.size,
    active_projects: projectRooms.size,
    project_rooms: {}
  };

  projectRooms.forEach((connectionIds, projectId) => {
    stats.project_rooms[projectId] = connectionIds.size;
  });

  res.json(stats);
});

// Broadcast endpoint for backend integration
app.post('/broadcast/:projectId', (req, res) => {
  const { projectId } = req.params;
  const message = req.body;

  broadcastToProject(projectId, {
    type: 'backend_notification',
    data: message,
    timestamp: new Date().toISOString()
  });

  res.json({ 
    success: true, 
    project: projectId,
    message: 'Broadcast sent'
  });
});

// Error handling
process.on('unhandledRejection', (reason, promise) => {
  console.error('❌ Unhandled Rejection at:', promise, 'reason:', reason);
});

process.on('uncaughtException', (error) => {
  console.error('❌ Uncaught Exception:', error);
  process.exit(1);
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('🛑 Received SIGTERM, shutting down gracefully');
  server.close(() => {
    if (redisClient) {
      redisClient.quit();
    }
    process.exit(0);
  });
});

// Start server
server.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 WebSocket server running on port ${PORT}`);
  console.log(`📊 Health check available at http://localhost:${PORT}/health`);
  console.log(`📈 Stats available at http://localhost:${PORT}/stats`);
});