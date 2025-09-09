/**
 * Redis Adapter for WebSocket System
 * 
 * Provides distributed state management and scaling capabilities
 * Handles room state, user presence, and message distribution across multiple server instances
 */

import { createClient } from 'redis';
import { setupLogging } from '../utils/logger.js';

const logger = setupLogging('redis-adapter');

export class RedisAdapter {
  constructor(redisUrl, options = {}) {
    this.redisUrl = redisUrl;
    this.options = {
      retryDelayOnFailover: 100,
      enableAutoPipelining: true,
      maxRetriesPerRequest: 3,
      ...options
    };
    
    this.client = null;
    this.subscriber = null;
    this.publisher = null;
    
    this.isConnected = false;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 10;
    
    // Key prefixes
    this.prefixes = {
      room: 'ws:room:',
      user: 'ws:user:',
      presence: 'ws:presence:',
      message: 'ws:message:',
      metrics: 'ws:metrics:',
      session: 'ws:session:',
      lock: 'ws:lock:'
    };

    this.initialize();
  }

  /**
   * Initialize Redis connections
   */
  async initialize() {
    try {
      // Main client for general operations
      this.client = createClient({
        url: this.redisUrl,
        ...this.options
      });

      // Subscriber client for pub/sub
      this.subscriber = this.client.duplicate();
      
      // Publisher client for pub/sub
      this.publisher = this.client.duplicate();

      // Set up error handlers
      this.setupErrorHandlers();

      // Connect all clients
      await Promise.all([
        this.client.connect(),
        this.subscriber.connect(),
        this.publisher.connect()
      ]);

      this.isConnected = true;
      this.reconnectAttempts = 0;

      logger.info('Redis adapter initialized successfully', {
        url: this.redisUrl.replace(/\/\/.*@/, '//***@') // Hide credentials in logs
      });

      // Set up pub/sub listeners
      this.setupPubSub();

    } catch (error) {
      logger.error('Failed to initialize Redis adapter:', error);
      this.handleConnectionError(error);
    }
  }

  /**
   * Set up error handlers for all Redis clients
   */
  setupErrorHandlers() {
    const clients = [this.client, this.subscriber, this.publisher].filter(Boolean);
    
    clients.forEach((client, index) => {
      const clientName = ['client', 'subscriber', 'publisher'][index];
      
      client.on('error', (error) => {
        logger.error(`Redis ${clientName} error:`, error);
        this.handleConnectionError(error);
      });

      client.on('connect', () => {
        logger.info(`Redis ${clientName} connected`);
      });

      client.on('ready', () => {
        logger.info(`Redis ${clientName} ready`);
        this.isConnected = true;
      });

      client.on('end', () => {
        logger.warn(`Redis ${clientName} connection ended`);
        this.isConnected = false;
      });

      client.on('reconnecting', () => {
        logger.info(`Redis ${clientName} reconnecting...`);
      });
    });
  }

  /**
   * Handle connection errors and implement reconnection logic
   */
  async handleConnectionError(error) {
    this.isConnected = false;
    this.reconnectAttempts++;

    if (this.reconnectAttempts <= this.maxReconnectAttempts) {
      const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
      
      logger.warn(`Attempting to reconnect to Redis (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`, {
        delay,
        error: error.message
      });

      setTimeout(() => {
        this.initialize();
      }, delay);
    } else {
      logger.error('Max reconnection attempts reached. Redis adapter is offline.');
    }
  }

  /**
   * Set up pub/sub system for cross-server communication
   */
  setupPubSub() {
    // Subscribe to WebSocket events
    const channels = [
      'websocket:room:*',
      'websocket:user:*',
      'websocket:presence:*',
      'websocket:annotation:*'
    ];

    channels.forEach(pattern => {
      this.subscriber.pSubscribe(pattern, (message, channel) => {
        this.handlePubSubMessage(message, channel);
      });
    });

    logger.debug('Pub/Sub channels subscribed', { channels });
  }

  /**
   * Handle incoming pub/sub messages
   */
  handlePubSubMessage(message, channel) {
    try {
      const data = JSON.parse(message);
      const [, category, action] = channel.split(':');

      logger.debug('Received pub/sub message', { channel, category, action });

      // Emit to local event handlers (would be connected to Socket.IO)
      if (this.eventHandlers && this.eventHandlers[category]) {
        this.eventHandlers[category](action, data);
      }

    } catch (error) {
      logger.error('Error handling pub/sub message:', error);
    }
  }

  /**
   * Room management methods
   */
  async setRoom(roomId, roomData) {
    if (!this.isConnected) {
      throw new Error('Redis adapter is not connected');
    }

    try {
      const key = this.prefixes.room + roomId;
      const serializedData = JSON.stringify(roomData);
      
      await this.client.setEx(key, 3600, serializedData); // 1 hour TTL
      
      // Publish room update
      await this.publisher.publish('websocket:room:update', JSON.stringify({
        roomId,
        data: roomData,
        timestamp: new Date().toISOString()
      }));

      logger.debug('Room data set in Redis', { roomId });

    } catch (error) {
      logger.error(`Error setting room data for ${roomId}:`, error);
      throw error;
    }
  }

  async getRoom(roomId) {
    if (!this.isConnected) {
      return null;
    }

    try {
      const key = this.prefixes.room + roomId;
      const data = await this.client.get(key);
      
      return data ? JSON.parse(data) : null;

    } catch (error) {
      logger.error(`Error getting room data for ${roomId}:`, error);
      return null;
    }
  }

  async deleteRoom(roomId) {
    if (!this.isConnected) {
      return false;
    }

    try {
      const key = this.prefixes.room + roomId;
      const result = await this.client.del(key);
      
      // Publish room deletion
      await this.publisher.publish('websocket:room:delete', JSON.stringify({
        roomId,
        timestamp: new Date().toISOString()
      }));

      return result > 0;

    } catch (error) {
      logger.error(`Error deleting room ${roomId}:`, error);
      return false;
    }
  }

  async addUserToRoom(roomId, userId, socketId) {
    if (!this.isConnected) return false;

    try {
      const roomKey = this.prefixes.room + roomId + ':users';
      const userKey = this.prefixes.user + userId + ':rooms';
      
      // Add user to room set
      await this.client.sAdd(roomKey, userId);
      
      // Add room to user set
      await this.client.sAdd(userKey, roomId);
      
      // Set user's socket ID with TTL
      await this.client.setEx(this.prefixes.user + userId + ':socket', 300, socketId);

      return true;

    } catch (error) {
      logger.error(`Error adding user ${userId} to room ${roomId}:`, error);
      return false;
    }
  }

  async removeUserFromRoom(roomId, userId) {
    if (!this.isConnected) return false;

    try {
      const roomKey = this.prefixes.room + roomId + ':users';
      const userKey = this.prefixes.user + userId + ':rooms';
      
      // Remove user from room set
      await this.client.sRem(roomKey, userId);
      
      // Remove room from user set
      await this.client.sRem(userKey, roomId);

      return true;

    } catch (error) {
      logger.error(`Error removing user ${userId} from room ${roomId}:`, error);
      return false;
    }
  }

  /**
   * Presence management methods
   */
  async setUserPresence(userId, presenceData, ttl = 300) {
    if (!this.isConnected) return false;

    try {
      const key = this.prefixes.presence + userId;
      const data = JSON.stringify({
        ...presenceData,
        lastUpdate: new Date().toISOString()
      });
      
      await this.client.setEx(key, ttl, data);
      
      // Publish presence update
      await this.publisher.publish('websocket:presence:update', JSON.stringify({
        userId,
        presence: presenceData,
        timestamp: new Date().toISOString()
      }));

      return true;

    } catch (error) {
      logger.error(`Error setting presence for user ${userId}:`, error);
      return false;
    }
  }

  async getUserPresence(userId) {
    if (!this.isConnected) return null;

    try {
      const key = this.prefixes.presence + userId;
      const data = await this.client.get(key);
      
      return data ? JSON.parse(data) : null;

    } catch (error) {
      logger.error(`Error getting presence for user ${userId}:`, error);
      return null;
    }
  }

  async getRoomPresence(roomId) {
    if (!this.isConnected) return [];

    try {
      const userIds = await this.client.sMembers(this.prefixes.room + roomId + ':users');
      const presenceData = [];

      for (const userId of userIds) {
        const presence = await this.getUserPresence(userId);
        if (presence) {
          presenceData.push({ userId, ...presence });
        }
      }

      return presenceData;

    } catch (error) {
      logger.error(`Error getting room presence for ${roomId}:`, error);
      return [];
    }
  }

  /**
   * Message queue methods for offline users
   */
  async queueMessage(userId, message, priority = 0) {
    if (!this.isConnected) return false;

    try {
      const key = this.prefixes.message + userId;
      const messageData = JSON.stringify({
        ...message,
        timestamp: new Date().toISOString(),
        priority
      });

      // Use sorted set for priority-based queue
      await this.client.zAdd(key, {
        score: priority,
        value: messageData
      });

      // Set TTL for message queue
      await this.client.expire(key, 86400); // 24 hours

      return true;

    } catch (error) {
      logger.error(`Error queuing message for user ${userId}:`, error);
      return false;
    }
  }

  async getQueuedMessages(userId, limit = 100) {
    if (!this.isConnected) return [];

    try {
      const key = this.prefixes.message + userId;
      
      // Get messages by priority (highest first)
      const messages = await this.client.zRevRange(key, 0, limit - 1);
      
      return messages.map(msg => JSON.parse(msg));

    } catch (error) {
      logger.error(`Error getting queued messages for user ${userId}:`, error);
      return [];
    }
  }

  async clearQueuedMessages(userId) {
    if (!this.isConnected) return false;

    try {
      const key = this.prefixes.message + userId;
      await this.client.del(key);
      return true;

    } catch (error) {
      logger.error(`Error clearing queued messages for user ${userId}:`, error);
      return false;
    }
  }

  /**
   * Distributed locking for conflict resolution
   */
  async acquireLock(resource, ttl = 10000) {
    if (!this.isConnected) return null;

    try {
      const lockKey = this.prefixes.lock + resource;
      const lockValue = `${Date.now()}_${Math.random()}`;
      
      const result = await this.client.set(lockKey, lockValue, {
        PX: ttl, // TTL in milliseconds
        NX: true // Only set if key doesn't exist
      });

      if (result === 'OK') {
        return {
          key: lockKey,
          value: lockValue,
          release: async () => {
            // Use Lua script for atomic unlock
            const script = `
              if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
              else
                return 0
              end
            `;
            
            return await this.client.eval(script, {
              keys: [lockKey],
              arguments: [lockValue]
            });
          }
        };
      }

      return null;

    } catch (error) {
      logger.error(`Error acquiring lock for ${resource}:`, error);
      return null;
    }
  }

  /**
   * Session management
   */
  async setSession(sessionId, sessionData, ttl = 3600) {
    if (!this.isConnected) return false;

    try {
      const key = this.prefixes.session + sessionId;
      const data = JSON.stringify(sessionData);
      
      await this.client.setEx(key, ttl, data);
      return true;

    } catch (error) {
      logger.error(`Error setting session ${sessionId}:`, error);
      return false;
    }
  }

  async getSession(sessionId) {
    if (!this.isConnected) return null;

    try {
      const key = this.prefixes.session + sessionId;
      const data = await this.client.get(key);
      
      return data ? JSON.parse(data) : null;

    } catch (error) {
      logger.error(`Error getting session ${sessionId}:`, error);
      return null;
    }
  }

  /**
   * Metrics and monitoring
   */
  async incrementMetric(metric, value = 1) {
    if (!this.isConnected) return false;

    try {
      const key = this.prefixes.metrics + metric;
      await this.client.incrBy(key, value);
      
      // Set TTL for metrics (reset daily)
      await this.client.expire(key, 86400);
      
      return true;

    } catch (error) {
      logger.error(`Error incrementing metric ${metric}:`, error);
      return false;
    }
  }

  async getMetrics(pattern = '*') {
    if (!this.isConnected) return {};

    try {
      const keys = await this.client.keys(this.prefixes.metrics + pattern);
      const metrics = {};

      for (const key of keys) {
        const metricName = key.replace(this.prefixes.metrics, '');
        const value = await this.client.get(key);
        metrics[metricName] = parseInt(value) || 0;
      }

      return metrics;

    } catch (error) {
      logger.error(`Error getting metrics:`, error);
      return {};
    }
  }

  /**
   * Pub/sub methods for cross-server communication
   */
  async publishEvent(channel, data) {
    if (!this.isConnected) return false;

    try {
      await this.publisher.publish(channel, JSON.stringify(data));
      return true;

    } catch (error) {
      logger.error(`Error publishing to channel ${channel}:`, error);
      return false;
    }
  }

  /**
   * Health check
   */
  async healthCheck() {
    if (!this.isConnected) {
      return { status: 'unhealthy', error: 'Not connected' };
    }

    try {
      const start = Date.now();
      await this.client.ping();
      const latency = Date.now() - start;

      return {
        status: 'healthy',
        latency: `${latency}ms`,
        connected: true,
        reconnectAttempts: this.reconnectAttempts
      };

    } catch (error) {
      return {
        status: 'unhealthy',
        error: error.message,
        connected: false
      };
    }
  }

  /**
   * Set event handlers for pub/sub messages
   */
  setEventHandlers(handlers) {
    this.eventHandlers = handlers;
  }

  /**
   * Close all Redis connections
   */
  async close() {
    try {
      const clients = [this.client, this.subscriber, this.publisher].filter(Boolean);
      
      await Promise.all(clients.map(client => {
        if (client && client.isOpen) {
          return client.disconnect();
        }
      }));

      this.isConnected = false;
      logger.info('Redis adapter closed');

    } catch (error) {
      logger.error('Error closing Redis adapter:', error);
    }
  }
}