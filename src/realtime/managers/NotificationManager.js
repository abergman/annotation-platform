/**
 * Notification Manager
 * 
 * Handles real-time notifications for annotation updates, conflicts, comments, and system events
 */

import { setupLogging } from '../utils/logger.js';

const logger = setupLogging('notification-manager');

export class NotificationManager {
  constructor(io) {
    this.io = io;
    this.notifications = new Map(); // Room ID -> Array of notifications
    this.userNotifications = new Map(); // User ID -> Array of notifications
    this.subscriptions = new Map(); // User ID -> Set of subscription types
    this.notificationQueue = new Map(); // User ID -> Array of queued notifications
    this.deliveryStatus = new Map(); // Notification ID -> Delivery status
    this.templates = this.initializeTemplates();
    
    // Notification cleanup interval
    this.cleanupInterval = setInterval(() => {
      this.cleanupOldNotifications();
    }, 300000); // Every 5 minutes
  }

  /**
   * Initialize notification templates
   */
  initializeTemplates() {
    return {
      'annotation-created': {
        title: 'New Annotation',
        message: '{username} added a new annotation to "{textTitle}"',
        icon: 'annotation',
        priority: 'normal',
        category: 'annotation'
      },
      'annotation-updated': {
        title: 'Annotation Updated',
        message: '{username} updated an annotation in "{textTitle}"',
        icon: 'edit',
        priority: 'normal',
        category: 'annotation'
      },
      'annotation-deleted': {
        title: 'Annotation Removed',
        message: '{username} removed an annotation from "{textTitle}"',
        icon: 'delete',
        priority: 'normal',
        category: 'annotation'
      },
      'annotation-commented': {
        title: 'New Comment',
        message: '{username} commented on your annotation: "{commentPreview}"',
        icon: 'comment',
        priority: 'high',
        category: 'comment'
      },
      'annotation-conflict': {
        title: 'Annotation Conflict',
        message: 'Conflicting changes detected in annotation by {username}',
        icon: 'warning',
        priority: 'critical',
        category: 'conflict'
      },
      'user-joined': {
        title: 'User Joined',
        message: '{username} joined the project',
        icon: 'user-plus',
        priority: 'low',
        category: 'presence'
      },
      'user-left': {
        title: 'User Left',
        message: '{username} left the project',
        icon: 'user-minus',
        priority: 'low',
        category: 'presence'
      },
      'project-update': {
        title: 'Project Updated',
        message: 'Project "{projectName}" has been updated',
        icon: 'project',
        priority: 'normal',
        category: 'project'
      },
      'system-maintenance': {
        title: 'System Maintenance',
        message: 'System maintenance scheduled for {time}',
        icon: 'maintenance',
        priority: 'high',
        category: 'system'
      },
      'export-completed': {
        title: 'Export Ready',
        message: 'Your data export is ready for download',
        icon: 'download',
        priority: 'normal',
        category: 'export'
      }
    };
  }

  /**
   * Send notification to specific users or room
   */
  async sendNotification(roomId, notification, targetUsers = null) {
    try {
      const notificationId = this.generateNotificationId();
      const timestamp = new Date().toISOString();

      // Process notification data
      const processedNotification = {
        id: notificationId,
        type: notification.type,
        title: notification.title,
        message: notification.message,
        data: notification.data || {},
        priority: notification.priority || 'normal',
        category: notification.category || 'general',
        from: notification.from,
        roomId: roomId,
        timestamp: timestamp,
        read: false,
        delivered: false,
        actions: notification.actions || []
      };

      // Apply template if exists
      if (this.templates[notification.type]) {
        processedNotification = this.applyTemplate(processedNotification, notification.templateData || {});
      }

      // Store notification in room
      if (!this.notifications.has(roomId)) {
        this.notifications.set(roomId, []);
      }
      this.notifications.get(roomId).push(processedNotification);

      // Send to specific users or all users in room
      if (targetUsers && targetUsers.length > 0) {
        await this.sendToUsers(processedNotification, targetUsers);
      } else {
        await this.sendToRoom(processedNotification, roomId);
      }

      // Store in user notifications for persistence
      await this.storeUserNotifications(processedNotification, targetUsers, roomId);

      logger.info(`Notification sent: ${notification.type} in room ${roomId}`, {
        id: notificationId,
        targetUsers: targetUsers?.length || 'all'
      });

      return processedNotification;

    } catch (error) {
      logger.error('Error sending notification:', error);
      throw error;
    }
  }

  /**
   * Send notification to specific users
   */
  async sendToUsers(notification, userIds) {
    try {
      for (const userId of userIds) {
        // Check if user is subscribed to this notification type
        if (!this.isUserSubscribed(userId, notification.category, notification.type)) {
          continue;
        }

        // Try to deliver in real-time
        const delivered = await this.deliverToUser(userId, notification);
        
        if (!delivered) {
          // Queue for offline delivery
          await this.queueNotification(userId, notification);
        }

        // Update delivery status
        this.updateDeliveryStatus(notification.id, userId, delivered);
      }
    } catch (error) {
      logger.error('Error sending notifications to users:', error);
    }
  }

  /**
   * Send notification to all users in a room
   */
  async sendToRoom(notification, roomId) {
    try {
      this.io.to(roomId).emit('notification', notification);
      
      // Mark as delivered for tracking
      this.deliveryStatus.set(notification.id, {
        roomId: roomId,
        deliveredAt: new Date().toISOString(),
        method: 'broadcast'
      });

    } catch (error) {
      logger.error(`Error sending notification to room ${roomId}:`, error);
    }
  }

  /**
   * Deliver notification to specific user
   */
  async deliverToUser(userId, notification) {
    try {
      // Find user's socket(s)
      const userSockets = this.findUserSockets(userId);
      
      if (userSockets.length === 0) {
        return false; // User not online
      }

      // Send to all user's connected devices
      for (const socket of userSockets) {
        socket.emit('notification', notification);
      }

      notification.delivered = true;
      notification.deliveredAt = new Date().toISOString();

      return true;
    } catch (error) {
      logger.error(`Error delivering notification to user ${userId}:`, error);
      return false;
    }
  }

  /**
   * Queue notification for offline user
   */
  async queueNotification(userId, notification) {
    try {
      if (!this.notificationQueue.has(userId)) {
        this.notificationQueue.set(userId, []);
      }

      const userQueue = this.notificationQueue.get(userId);
      
      // Add to queue with expiration
      const queuedNotification = {
        ...notification,
        queuedAt: new Date().toISOString(),
        expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString() // 7 days
      };

      userQueue.push(queuedNotification);

      // Limit queue size
      if (userQueue.length > 100) {
        userQueue.splice(0, userQueue.length - 100);
      }

      logger.debug(`Notification queued for offline user ${userId}`, {
        notificationId: notification.id,
        queueSize: userQueue.length
      });

    } catch (error) {
      logger.error(`Error queuing notification for user ${userId}:`, error);
    }
  }

  /**
   * Deliver queued notifications when user comes online
   */
  async deliverQueuedNotifications(userId, socketId) {
    try {
      const userQueue = this.notificationQueue.get(userId);
      if (!userQueue || userQueue.length === 0) {
        return;
      }

      const socket = this.io.sockets.sockets.get(socketId);
      if (!socket) return;

      // Filter out expired notifications
      const now = new Date();
      const validNotifications = userQueue.filter(notification => {
        return new Date(notification.expiresAt) > now;
      });

      if (validNotifications.length > 0) {
        // Send queued notifications
        socket.emit('queued-notifications', {
          notifications: validNotifications,
          count: validNotifications.length,
          timestamp: new Date().toISOString()
        });

        logger.info(`Delivered ${validNotifications.length} queued notifications to user ${userId}`);
      }

      // Clear the queue
      this.notificationQueue.delete(userId);

    } catch (error) {
      logger.error(`Error delivering queued notifications to user ${userId}:`, error);
    }
  }

  /**
   * Mark notification as read
   */
  async markAsRead(notificationId, userId) {
    try {
      // Update in user notifications
      const userNotifications = this.userNotifications.get(userId) || [];
      const notification = userNotifications.find(n => n.id === notificationId);
      
      if (notification) {
        notification.read = true;
        notification.readAt = new Date().toISOString();
      }

      // Update in room notifications
      for (const roomNotifications of this.notifications.values()) {
        const roomNotification = roomNotifications.find(n => n.id === notificationId);
        if (roomNotification) {
          if (!roomNotification.readBy) {
            roomNotification.readBy = [];
          }
          roomNotification.readBy.push({
            userId: userId,
            readAt: new Date().toISOString()
          });
          break;
        }
      }

      logger.debug(`Notification ${notificationId} marked as read by user ${userId}`);
      return true;

    } catch (error) {
      logger.error('Error marking notification as read:', error);
      return false;
    }
  }

  /**
   * Get user's notifications
   */
  getUserNotifications(userId, options = {}) {
    const userNotifications = this.userNotifications.get(userId) || [];
    let filtered = [...userNotifications];

    // Apply filters
    if (options.unreadOnly) {
      filtered = filtered.filter(n => !n.read);
    }

    if (options.category) {
      filtered = filtered.filter(n => n.category === options.category);
    }

    if (options.priority) {
      filtered = filtered.filter(n => n.priority === options.priority);
    }

    if (options.since) {
      const sinceDate = new Date(options.since);
      filtered = filtered.filter(n => new Date(n.timestamp) > sinceDate);
    }

    // Sort by timestamp (newest first)
    filtered.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

    // Apply pagination
    const limit = options.limit || 50;
    const offset = options.offset || 0;
    
    return {
      notifications: filtered.slice(offset, offset + limit),
      total: filtered.length,
      unread: userNotifications.filter(n => !n.read).length
    };
  }

  /**
   * Get room notifications
   */
  getRoomNotifications(roomId, options = {}) {
    const roomNotifications = this.notifications.get(roomId) || [];
    let filtered = [...roomNotifications];

    // Apply filters
    if (options.category) {
      filtered = filtered.filter(n => n.category === options.category);
    }

    if (options.since) {
      const sinceDate = new Date(options.since);
      filtered = filtered.filter(n => new Date(n.timestamp) > sinceDate);
    }

    // Sort by timestamp (newest first)
    filtered.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

    return filtered.slice(0, options.limit || 100);
  }

  /**
   * Subscribe user to notification types
   */
  async subscribeUser(userId, subscriptions) {
    try {
      if (!this.subscriptions.has(userId)) {
        this.subscriptions.set(userId, new Set());
      }

      const userSubscriptions = this.subscriptions.get(userId);
      
      // Add new subscriptions
      if (Array.isArray(subscriptions)) {
        subscriptions.forEach(sub => userSubscriptions.add(sub));
      } else {
        userSubscriptions.add(subscriptions);
      }

      logger.debug(`User ${userId} subscribed to notifications:`, Array.from(userSubscriptions));
      return true;

    } catch (error) {
      logger.error(`Error subscribing user ${userId}:`, error);
      return false;
    }
  }

  /**
   * Unsubscribe user from notification types
   */
  async unsubscribeUser(userId, subscriptions) {
    try {
      const userSubscriptions = this.subscriptions.get(userId);
      if (!userSubscriptions) return true;

      // Remove subscriptions
      if (Array.isArray(subscriptions)) {
        subscriptions.forEach(sub => userSubscriptions.delete(sub));
      } else {
        userSubscriptions.delete(subscriptions);
      }

      return true;

    } catch (error) {
      logger.error(`Error unsubscribing user ${userId}:`, error);
      return false;
    }
  }

  /**
   * Check if user is subscribed to notification type
   */
  isUserSubscribed(userId, category, type) {
    const userSubscriptions = this.subscriptions.get(userId);
    if (!userSubscriptions) return true; // Default to subscribed

    // Check specific type subscription
    if (userSubscriptions.has(type)) return true;
    
    // Check category subscription
    if (userSubscriptions.has(category)) return true;
    
    // Check for 'all' subscription
    if (userSubscriptions.has('all')) return true;

    // Check for 'none' subscription (opt-out)
    if (userSubscriptions.has('none')) return false;

    return true; // Default to subscribed
  }

  /**
   * Apply notification template
   */
  applyTemplate(notification, templateData) {
    const template = this.templates[notification.type];
    if (!template) return notification;

    // Apply template properties
    if (!notification.title && template.title) {
      notification.title = this.interpolateTemplate(template.title, templateData);
    }
    
    if (!notification.message && template.message) {
      notification.message = this.interpolateTemplate(template.message, templateData);
    }

    notification.icon = notification.icon || template.icon;
    notification.priority = notification.priority || template.priority;
    notification.category = notification.category || template.category;

    return notification;
  }

  /**
   * Interpolate template strings with data
   */
  interpolateTemplate(template, data) {
    return template.replace(/\{(\w+)\}/g, (match, key) => {
      return data[key] || match;
    });
  }

  /**
   * Find all sockets for a user
   */
  findUserSockets(userId) {
    const userSockets = [];
    
    for (const socket of this.io.sockets.sockets.values()) {
      if (socket.user && socket.user.id === userId) {
        userSockets.push(socket);
      }
    }
    
    return userSockets;
  }

  /**
   * Store notification in user's notification history
   */
  async storeUserNotifications(notification, targetUsers, roomId) {
    try {
      const usersToNotify = targetUsers || await this.getRoomUsers(roomId);
      
      for (const userId of usersToNotify) {
        if (!this.userNotifications.has(userId)) {
          this.userNotifications.set(userId, []);
        }
        
        const userNotifications = this.userNotifications.get(userId);
        userNotifications.push({ ...notification });
        
        // Limit user notification history
        if (userNotifications.length > 500) {
          userNotifications.splice(0, userNotifications.length - 500);
        }
      }

    } catch (error) {
      logger.error('Error storing user notifications:', error);
    }
  }

  /**
   * Get users in a room (helper method)
   */
  async getRoomUsers(roomId) {
    try {
      const room = this.io.sockets.adapter.rooms.get(roomId);
      if (!room) return [];

      const users = [];
      for (const socketId of room) {
        const socket = this.io.sockets.sockets.get(socketId);
        if (socket && socket.user) {
          users.push(socket.user.id);
        }
      }

      return [...new Set(users)]; // Remove duplicates
    } catch (error) {
      logger.error(`Error getting room users for ${roomId}:`, error);
      return [];
    }
  }

  /**
   * Update delivery status
   */
  updateDeliveryStatus(notificationId, userId, delivered) {
    if (!this.deliveryStatus.has(notificationId)) {
      this.deliveryStatus.set(notificationId, {});
    }

    const status = this.deliveryStatus.get(notificationId);
    if (!status.users) status.users = {};

    status.users[userId] = {
      delivered: delivered,
      timestamp: new Date().toISOString()
    };
  }

  /**
   * Generate unique notification ID
   */
  generateNotificationId() {
    return `notif_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
  }

  /**
   * Clean up old notifications
   */
  cleanupOldNotifications() {
    const now = new Date();
    const maxAge = 7 * 24 * 60 * 60 * 1000; // 7 days

    // Clean up room notifications
    for (const [roomId, notifications] of this.notifications.entries()) {
      const filtered = notifications.filter(notification => {
        const age = now - new Date(notification.timestamp);
        return age < maxAge;
      });
      
      if (filtered.length !== notifications.length) {
        this.notifications.set(roomId, filtered);
        logger.debug(`Cleaned up ${notifications.length - filtered.length} old notifications in room ${roomId}`);
      }
    }

    // Clean up user notifications
    for (const [userId, notifications] of this.userNotifications.entries()) {
      const filtered = notifications.filter(notification => {
        const age = now - new Date(notification.timestamp);
        return age < maxAge;
      });
      
      if (filtered.length !== notifications.length) {
        this.userNotifications.set(userId, filtered);
      }
    }

    // Clean up queued notifications
    for (const [userId, queue] of this.notificationQueue.entries()) {
      const filtered = queue.filter(notification => {
        return new Date(notification.expiresAt) > now;
      });
      
      if (filtered.length !== queue.length) {
        if (filtered.length === 0) {
          this.notificationQueue.delete(userId);
        } else {
          this.notificationQueue.set(userId, filtered);
        }
      }
    }
  }

  /**
   * Get notification statistics
   */
  getNotificationStats() {
    let totalNotifications = 0;
    let totalUnread = 0;
    let totalQueued = 0;

    // Count room notifications
    for (const notifications of this.notifications.values()) {
      totalNotifications += notifications.length;
    }

    // Count user notifications and unread
    for (const notifications of this.userNotifications.values()) {
      totalNotifications += notifications.length;
      totalUnread += notifications.filter(n => !n.read).length;
    }

    // Count queued notifications
    for (const queue of this.notificationQueue.values()) {
      totalQueued += queue.length;
    }

    return {
      total: totalNotifications,
      unread: totalUnread,
      queued: totalQueued,
      rooms: this.notifications.size,
      subscribedUsers: this.subscriptions.size,
      timestamp: new Date().toISOString()
    };
  }

  /**
   * Clean up user data on disconnect
   */
  cleanup(userId) {
    // Keep user notifications and subscriptions for when they return
    // Only clean up delivery status
    for (const [notificationId, status] of this.deliveryStatus.entries()) {
      if (status.users && status.users[userId]) {
        delete status.users[userId];
        
        if (Object.keys(status.users).length === 0) {
          this.deliveryStatus.delete(notificationId);
        }
      }
    }

    logger.debug(`Notification cleanup completed for user ${userId}`);
  }

  /**
   * Destroy notification manager
   */
  destroy() {
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
    }

    this.notifications.clear();
    this.userNotifications.clear();
    this.subscriptions.clear();
    this.notificationQueue.clear();
    this.deliveryStatus.clear();

    logger.info('Notification Manager destroyed');
  }
}