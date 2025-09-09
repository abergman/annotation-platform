/**
 * Message Queue System
 * 
 * Handles message queuing for offline users and reliable message delivery
 * Provides persistence, retry logic, and message ordering
 */

import { setupLogging } from '../utils/logger.js';
import fs from 'fs/promises';
import path from 'path';

const logger = setupLogging('message-queue');

export class MessageQueue {
  constructor(options = {}) {
    this.queues = new Map(); // User ID -> Message queue
    this.persistentQueues = new Map(); // Room ID -> Persistent message queue
    this.deliveryAttempts = new Map(); // Message ID -> Attempt count
    this.deadLetterQueue = new Map(); // Failed messages
    this.queueMetrics = new Map(); // Queue statistics
    
    // Configuration
    this.config = {
      maxQueueSize: options.maxQueueSize || 1000,
      maxRetryAttempts: options.maxRetryAttempts || 3,
      retryDelay: options.retryDelay || 5000, // 5 seconds
      messageExpiry: options.messageExpiry || 7 * 24 * 60 * 60 * 1000, // 7 days
      persistencePath: options.persistencePath || './data/message-queues',
      enablePersistence: options.enablePersistence !== false
    };

    // Initialize persistence
    if (this.config.enablePersistence) {
      this.initializePersistence();
    }

    // Start background workers
    this.startBackgroundWorkers();
  }

  /**
   * Initialize persistent storage
   */
  async initializePersistence() {
    try {
      await fs.mkdir(this.config.persistencePath, { recursive: true });
      await this.loadPersistedQueues();
      
      logger.info('Message queue persistence initialized', {
        path: this.config.persistencePath
      });
    } catch (error) {
      logger.error('Failed to initialize message queue persistence:', error);
    }
  }

  /**
   * Queue message for user
   */
  async queueMessage(userId, message, priority = 'normal') {
    try {
      const messageId = this.generateMessageId();
      const timestamp = new Date().toISOString();
      const expiresAt = new Date(Date.now() + this.config.messageExpiry).toISOString();

      const queuedMessage = {
        id: messageId,
        userId: userId,
        type: message.type,
        data: message.data || message,
        priority: priority,
        timestamp: timestamp,
        expiresAt: expiresAt,
        attempts: 0,
        maxAttempts: this.config.maxRetryAttempts,
        status: 'queued',
        roomId: message.roomId,
        metadata: message.metadata || {}
      };

      // Add to user queue
      if (!this.queues.has(userId)) {
        this.queues.set(userId, []);
      }

      const userQueue = this.queues.get(userId);
      
      // Insert based on priority
      this.insertByPriority(userQueue, queuedMessage);

      // Enforce queue size limit
      if (userQueue.length > this.config.maxQueueSize) {
        const removed = userQueue.splice(0, userQueue.length - this.config.maxQueueSize);
        this.moveToDeadLetter(removed, 'queue_overflow');
      }

      // Persist if enabled
      if (this.config.enablePersistence) {
        await this.persistQueue(userId);
      }

      // Update metrics
      this.updateQueueMetrics(userId, 'queued');

      logger.debug(`Message queued for user ${userId}`, {
        messageId,
        type: message.type,
        priority,
        queueSize: userQueue.length
      });

      return messageId;

    } catch (error) {
      logger.error(`Error queuing message for user ${userId}:`, error);
      throw error;
    }
  }

  /**
   * Queue message for room (persistent across user sessions)
   */
  async queueRoomMessage(roomId, message, targetUsers = null) {
    try {
      const messageId = this.generateMessageId();
      const timestamp = new Date().toISOString();

      const roomMessage = {
        id: messageId,
        roomId: roomId,
        type: message.type,
        data: message.data || message,
        targetUsers: targetUsers, // null means all users
        timestamp: timestamp,
        expiresAt: new Date(Date.now() + this.config.messageExpiry).toISOString(),
        delivered: new Set(), // Track delivered users
        status: 'queued'
      };

      // Add to room queue
      if (!this.persistentQueues.has(roomId)) {
        this.persistentQueues.set(roomId, []);
      }

      const roomQueue = this.persistentQueues.get(roomId);
      roomQueue.push(roomMessage);

      // Persist room queue
      if (this.config.enablePersistence) {
        await this.persistRoomQueue(roomId);
      }

      logger.debug(`Message queued for room ${roomId}`, {
        messageId,
        type: message.type,
        targetUsers: targetUsers?.length || 'all'
      });

      return messageId;

    } catch (error) {
      logger.error(`Error queuing room message for ${roomId}:`, error);
      throw error;
    }
  }

  /**
   * Get messages for user
   */
  async getMessages(userId, roomId = null) {
    try {
      const userQueue = this.queues.get(userId) || [];
      let messages = [...userQueue];

      // Filter by room if specified
      if (roomId) {
        messages = messages.filter(msg => msg.roomId === roomId);
      }

      // Also get room messages for this user
      if (roomId && this.persistentQueues.has(roomId)) {
        const roomQueue = this.persistentQueues.get(roomId);
        const roomMessages = roomQueue.filter(msg => 
          !msg.delivered.has(userId) && 
          (msg.targetUsers === null || msg.targetUsers.includes(userId))
        );
        
        messages = messages.concat(roomMessages);
      }

      // Filter out expired messages
      const now = new Date();
      messages = messages.filter(msg => new Date(msg.expiresAt) > now);

      // Sort by priority and timestamp
      messages.sort((a, b) => {
        const priorityOrder = { high: 3, normal: 2, low: 1 };
        const aPriority = priorityOrder[a.priority] || 2;
        const bPriority = priorityOrder[b.priority] || 2;
        
        if (aPriority !== bPriority) {
          return bPriority - aPriority; // Higher priority first
        }
        
        return new Date(a.timestamp) - new Date(b.timestamp); // Older first
      });

      logger.debug(`Retrieved ${messages.length} messages for user ${userId}`, {
        roomId,
        userQueue: userQueue.length,
        roomMessages: roomId ? (this.persistentQueues.get(roomId) || []).length : 0
      });

      return messages;

    } catch (error) {
      logger.error(`Error getting messages for user ${userId}:`, error);
      return [];
    }
  }

  /**
   * Mark message as delivered
   */
  async markDelivered(messageId, userId) {
    try {
      let found = false;

      // Check user queues
      const userQueue = this.queues.get(userId) || [];
      const userMessageIndex = userQueue.findIndex(msg => msg.id === messageId);
      
      if (userMessageIndex !== -1) {
        userQueue[userMessageIndex].status = 'delivered';
        userQueue[userMessageIndex].deliveredAt = new Date().toISOString();
        found = true;
      }

      // Check room queues
      for (const [roomId, roomQueue] of this.persistentQueues.entries()) {
        const roomMessage = roomQueue.find(msg => msg.id === messageId);
        if (roomMessage) {
          roomMessage.delivered.add(userId);
          found = true;
          
          // Persist room queue update
          if (this.config.enablePersistence) {
            await this.persistRoomQueue(roomId);
          }
          break;
        }
      }

      if (found) {
        this.updateQueueMetrics(userId, 'delivered');
        logger.debug(`Message ${messageId} marked as delivered for user ${userId}`);
      }

      return found;

    } catch (error) {
      logger.error(`Error marking message ${messageId} as delivered:`, error);
      return false;
    }
  }

  /**
   * Clear messages for user in specific room
   */
  async clearMessages(userId, roomId) {
    try {
      let cleared = 0;

      // Clear from user queue
      const userQueue = this.queues.get(userId) || [];
      const originalLength = userQueue.length;
      
      if (roomId) {
        this.queues.set(userId, userQueue.filter(msg => msg.roomId !== roomId));
        cleared += originalLength - userQueue.filter(msg => msg.roomId !== roomId).length;
      } else {
        this.queues.set(userId, []);
        cleared += originalLength;
      }

      // Mark room messages as delivered
      if (roomId && this.persistentQueues.has(roomId)) {
        const roomQueue = this.persistentQueues.get(roomId);
        roomQueue.forEach(msg => {
          if (msg.targetUsers === null || msg.targetUsers.includes(userId)) {
            msg.delivered.add(userId);
            cleared++;
          }
        });

        if (this.config.enablePersistence) {
          await this.persistRoomQueue(roomId);
        }
      }

      // Persist user queue
      if (this.config.enablePersistence) {
        await this.persistQueue(userId);
      }

      logger.info(`Cleared ${cleared} messages for user ${userId}`, { roomId });
      return cleared;

    } catch (error) {
      logger.error(`Error clearing messages for user ${userId}:`, error);
      return 0;
    }
  }

  /**
   * Retry failed message delivery
   */
  async retryMessage(messageId) {
    try {
      let message = null;
      let location = null;

      // Find message in dead letter queue
      for (const [key, deadMessages] of this.deadLetterQueue.entries()) {
        const index = deadMessages.findIndex(msg => msg.id === messageId);
        if (index !== -1) {
          message = deadMessages.splice(index, 1)[0];
          location = key;
          break;
        }
      }

      if (!message) {
        throw new Error(`Message ${messageId} not found in dead letter queue`);
      }

      // Reset message status
      message.status = 'queued';
      message.attempts = 0;
      delete message.lastError;

      // Re-queue based on original location
      if (message.userId) {
        await this.queueMessage(message.userId, message, message.priority);
      } else if (message.roomId) {
        await this.queueRoomMessage(message.roomId, message, message.targetUsers);
      }

      logger.info(`Message ${messageId} retried from dead letter queue`);
      return true;

    } catch (error) {
      logger.error(`Error retrying message ${messageId}:`, error);
      return false;
    }
  }

  /**
   * Queue conflict resolution
   */
  async queueConflictResolution(roomId, conflicts, annotation) {
    try {
      const message = {
        type: 'conflict-resolution',
        data: {
          conflicts: conflicts,
          annotation: annotation,
          requiresUserInput: true
        },
        roomId: roomId,
        metadata: {
          conflictCount: conflicts.length,
          severity: Math.max(...conflicts.map(c => this.getSeverityLevel(c.severity)))
        }
      };

      return await this.queueRoomMessage(roomId, message);

    } catch (error) {
      logger.error('Error queuing conflict resolution:', error);
      throw error;
    }
  }

  /**
   * Background worker for message cleanup and retry
   */
  startBackgroundWorkers() {
    // Cleanup expired messages every 5 minutes
    setInterval(() => {
      this.cleanupExpiredMessages();
    }, 5 * 60 * 1000);

    // Retry failed messages every 10 minutes
    setInterval(() => {
      this.retryFailedMessages();
    }, 10 * 60 * 1000);

    // Persist queues every minute (if dirty)
    setInterval(() => {
      this.persistDirtyQueues();
    }, 60 * 1000);

    logger.info('Message queue background workers started');
  }

  /**
   * Clean up expired messages
   */
  async cleanupExpiredMessages() {
    try {
      const now = new Date();
      let totalCleaned = 0;

      // Clean user queues
      for (const [userId, queue] of this.queues.entries()) {
        const originalLength = queue.length;
        this.queues.set(userId, queue.filter(msg => new Date(msg.expiresAt) > now));
        totalCleaned += originalLength - queue.length;
      }

      // Clean room queues
      for (const [roomId, queue] of this.persistentQueues.entries()) {
        const originalLength = queue.length;
        this.persistentQueues.set(roomId, queue.filter(msg => new Date(msg.expiresAt) > now));
        totalCleaned += originalLength - queue.length;
      }

      if (totalCleaned > 0) {
        logger.info(`Cleaned up ${totalCleaned} expired messages`);
      }

    } catch (error) {
      logger.error('Error cleaning up expired messages:', error);
    }
  }

  /**
   * Retry failed messages with exponential backoff
   */
  async retryFailedMessages() {
    try {
      const now = Date.now();
      
      for (const [userId, queue] of this.queues.entries()) {
        for (const message of queue) {
          if (message.status === 'failed' && message.nextRetryAt && now >= message.nextRetryAt) {
            if (message.attempts < message.maxAttempts) {
              message.status = 'queued';
              message.attempts++;
              message.nextRetryAt = now + (this.config.retryDelay * Math.pow(2, message.attempts));
              
              logger.debug(`Retrying message ${message.id} (attempt ${message.attempts})`);
            } else {
              // Move to dead letter queue
              this.moveToDeadLetter([message], 'max_attempts_exceeded');
              queue.splice(queue.indexOf(message), 1);
            }
          }
        }
      }

    } catch (error) {
      logger.error('Error retrying failed messages:', error);
    }
  }

  /**
   * Utility methods
   */
  insertByPriority(queue, message) {
    const priorityOrder = { high: 3, normal: 2, low: 1 };
    const messagePriority = priorityOrder[message.priority] || 2;
    
    let insertIndex = queue.length;
    for (let i = 0; i < queue.length; i++) {
      const queuePriority = priorityOrder[queue[i].priority] || 2;
      if (messagePriority > queuePriority) {
        insertIndex = i;
        break;
      }
    }
    
    queue.splice(insertIndex, 0, message);
  }

  moveToDeadLetter(messages, reason) {
    const key = `dead_letter_${Date.now()}`;
    if (!this.deadLetterQueue.has(key)) {
      this.deadLetterQueue.set(key, []);
    }
    
    messages.forEach(message => {
      message.status = 'dead_letter';
      message.deadLetterReason = reason;
      message.deadLetterAt = new Date().toISOString();
    });
    
    this.deadLetterQueue.get(key).push(...messages);
  }

  getSeverityLevel(severity) {
    const levels = { low: 1, medium: 2, high: 3, critical: 4 };
    return levels[severity] || 1;
  }

  generateMessageId() {
    return `msg_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
  }

  updateQueueMetrics(userId, action) {
    if (!this.queueMetrics.has(userId)) {
      this.queueMetrics.set(userId, {
        queued: 0,
        delivered: 0,
        failed: 0,
        lastActivity: null
      });
    }
    
    const metrics = this.queueMetrics.get(userId);
    metrics[action] = (metrics[action] || 0) + 1;
    metrics.lastActivity = new Date().toISOString();
  }

  /**
   * Persistence methods
   */
  async persistQueue(userId) {
    if (!this.config.enablePersistence) return;
    
    try {
      const queue = this.queues.get(userId) || [];
      const filePath = path.join(this.config.persistencePath, `user_${userId}.json`);
      
      await fs.writeFile(filePath, JSON.stringify({
        userId,
        messages: queue,
        lastUpdated: new Date().toISOString()
      }, null, 2));
      
    } catch (error) {
      logger.error(`Error persisting queue for user ${userId}:`, error);
    }
  }

  async persistRoomQueue(roomId) {
    if (!this.config.enablePersistence) return;
    
    try {
      const queue = this.persistentQueues.get(roomId) || [];
      const filePath = path.join(this.config.persistencePath, `room_${roomId}.json`);
      
      // Convert Sets to Arrays for JSON serialization
      const serializedQueue = queue.map(msg => ({
        ...msg,
        delivered: Array.from(msg.delivered)
      }));
      
      await fs.writeFile(filePath, JSON.stringify({
        roomId,
        messages: serializedQueue,
        lastUpdated: new Date().toISOString()
      }, null, 2));
      
    } catch (error) {
      logger.error(`Error persisting room queue for ${roomId}:`, error);
    }
  }

  async loadPersistedQueues() {
    if (!this.config.enablePersistence) return;
    
    try {
      const files = await fs.readdir(this.config.persistencePath);
      
      for (const file of files) {
        if (file.endsWith('.json')) {
          const filePath = path.join(this.config.persistencePath, file);
          const data = await fs.readFile(filePath, 'utf8');
          const parsed = JSON.parse(data);
          
          if (file.startsWith('user_')) {
            this.queues.set(parsed.userId, parsed.messages || []);
          } else if (file.startsWith('room_')) {
            // Convert Arrays back to Sets
            const messages = (parsed.messages || []).map(msg => ({
              ...msg,
              delivered: new Set(msg.delivered)
            }));
            this.persistentQueues.set(parsed.roomId, messages);
          }
        }
      }
      
      logger.info(`Loaded ${this.queues.size} user queues and ${this.persistentQueues.size} room queues`);
      
    } catch (error) {
      logger.error('Error loading persisted queues:', error);
    }
  }

  async persistDirtyQueues() {
    // This would track which queues have been modified and only persist those
    // Simplified implementation - persist all
    if (!this.config.enablePersistence) return;
    
    try {
      const promises = [];
      
      // Persist user queues
      for (const userId of this.queues.keys()) {
        promises.push(this.persistQueue(userId));
      }
      
      // Persist room queues
      for (const roomId of this.persistentQueues.keys()) {
        promises.push(this.persistRoomQueue(roomId));
      }
      
      await Promise.all(promises);
      
    } catch (error) {
      logger.error('Error persisting dirty queues:', error);
    }
  }

  /**
   * Get queue statistics
   */
  getQueueStats() {
    const stats = {
      userQueues: this.queues.size,
      roomQueues: this.persistentQueues.size,
      totalMessages: 0,
      messagesByPriority: { high: 0, normal: 0, low: 0 },
      deadLetterMessages: 0,
      timestamp: new Date().toISOString()
    };

    // Count user queue messages
    for (const queue of this.queues.values()) {
      stats.totalMessages += queue.length;
      queue.forEach(msg => {
        stats.messagesByPriority[msg.priority || 'normal']++;
      });
    }

    // Count room queue messages
    for (const queue of this.persistentQueues.values()) {
      stats.totalMessages += queue.length;
    }

    // Count dead letter messages
    for (const deadMessages of this.deadLetterQueue.values()) {
      stats.deadLetterMessages += deadMessages.length;
    }

    return stats;
  }

  /**
   * Cleanup and destroy
   */
  async close() {
    try {
      // Persist all queues before closing
      if (this.config.enablePersistence) {
        await this.persistDirtyQueues();
      }
      
      // Clear all data
      this.queues.clear();
      this.persistentQueues.clear();
      this.deliveryAttempts.clear();
      this.deadLetterQueue.clear();
      this.queueMetrics.clear();
      
      logger.info('Message queue system closed');
      
    } catch (error) {
      logger.error('Error closing message queue:', error);
    }
  }
}