/**
 * Presence Manager
 * 
 * Manages user presence and status for real-time collaboration
 * Tracks who is online, active, idle, and provides presence indicators
 */

import { setupLogging } from '../utils/logger.js';

const logger = setupLogging('presence-manager');

export class PresenceManager {
  constructor(io) {
    this.io = io;
    this.presence = new Map(); // Room ID -> Map of User presence data
    this.userStatus = new Map(); // User ID -> Current status
    this.userLastActivity = new Map(); // User ID -> Last activity timestamp
    this.heartbeatInterval = null;
    
    // Initialize presence tracking
    this.initializePresenceTracking();
  }

  /**
   * Initialize presence tracking system
   */
  initializePresenceTracking() {
    // Heartbeat system to track idle/away users
    this.heartbeatInterval = setInterval(() => {
      this.checkIdleUsers();
    }, 30000); // Check every 30 seconds

    logger.info('Presence tracking system initialized');
  }

  /**
   * User joined a room - update presence
   */
  async userJoined(roomId, userId, username, socketId, metadata = {}) {
    try {
      // Initialize room presence if doesn't exist
      if (!this.presence.has(roomId)) {
        this.presence.set(roomId, new Map());
      }

      const roomPresence = this.presence.get(roomId);
      const now = new Date();

      // Set user presence data
      const presenceData = {
        userId,
        username,
        socketId,
        status: 'online',
        joinedAt: now,
        lastActivity: now,
        lastSeen: now,
        location: {
          roomId,
          projectId: metadata.projectId,
          textId: metadata.textId
        },
        device: {
          userAgent: metadata.userAgent || '',
          platform: metadata.platform || 'unknown',
          browser: metadata.browser || 'unknown'
        },
        activity: {
          annotating: false,
          viewing: true,
          cursorPosition: null,
          selectedText: null
        },
        permissions: metadata.permissions || []
      };

      roomPresence.set(userId, presenceData);
      this.userStatus.set(userId, 'online');
      this.userLastActivity.set(userId, now);

      // Broadcast presence update to room
      await this.broadcastPresenceUpdate(roomId, userId, 'joined', presenceData);

      logger.info(`User presence updated - ${username} joined room ${roomId}`);
      return presenceData;

    } catch (error) {
      logger.error(`Error updating user presence for ${userId} in room ${roomId}:`, error);
      throw error;
    }
  }

  /**
   * User left a room - update presence
   */
  async userLeft(roomId, userId) {
    try {
      const roomPresence = this.presence.get(roomId);
      if (!roomPresence) return;

      const userPresence = roomPresence.get(userId);
      if (!userPresence) return;

      // Remove user from room presence
      roomPresence.delete(userId);
      
      // Update global user status if not in other rooms
      const isInOtherRooms = this.isUserInOtherRooms(userId, roomId);
      if (!isInOtherRooms) {
        this.userStatus.set(userId, 'offline');
      }

      // Broadcast presence update
      await this.broadcastPresenceUpdate(roomId, userId, 'left', userPresence);

      logger.info(`User presence updated - ${userPresence.username} left room ${roomId}`);

    } catch (error) {
      logger.error(`Error removing user presence for ${userId} from room ${roomId}:`, error);
    }
  }

  /**
   * Update user activity status
   */
  async updateUserActivity(roomId, userId, activityType, data = {}) {
    try {
      const roomPresence = this.presence.get(roomId);
      if (!roomPresence || !roomPresence.has(userId)) {
        return;
      }

      const userPresence = roomPresence.get(userId);
      const now = new Date();

      // Update activity data
      userPresence.lastActivity = now;
      userPresence.lastSeen = now;
      this.userLastActivity.set(userId, now);

      // Update specific activity
      switch (activityType) {
        case 'annotating':
          userPresence.activity.annotating = true;
          userPresence.activity.viewing = true;
          break;
        case 'viewing':
          userPresence.activity.viewing = true;
          userPresence.activity.annotating = false;
          break;
        case 'cursor-move':
          userPresence.activity.cursorPosition = data.position;
          break;
        case 'text-select':
          userPresence.activity.selectedText = data.selection;
          break;
        case 'idle':
          userPresence.status = 'idle';
          userPresence.activity.annotating = false;
          break;
        case 'away':
          userPresence.status = 'away';
          userPresence.activity.annotating = false;
          userPresence.activity.viewing = false;
          break;
      }

      // Ensure user is marked as online if they're active
      if (activityType !== 'idle' && activityType !== 'away' && userPresence.status !== 'online') {
        userPresence.status = 'online';
        this.userStatus.set(userId, 'online');
      }

      // Broadcast activity update to room (throttled)
      await this.throttledActivityBroadcast(roomId, userId, activityType, userPresence);

    } catch (error) {
      logger.error(`Error updating user activity for ${userId} in room ${roomId}:`, error);
    }
  }

  /**
   * Get presence data for a room
   */
  getRoomPresence(roomId) {
    const roomPresence = this.presence.get(roomId);
    if (!roomPresence) return [];

    return Array.from(roomPresence.values()).map(presence => ({
      userId: presence.userId,
      username: presence.username,
      status: presence.status,
      joinedAt: presence.joinedAt,
      lastActivity: presence.lastActivity,
      activity: presence.activity,
      device: presence.device
    }));
  }

  /**
   * Get specific user's presence in a room
   */
  getUserPresence(roomId, userId) {
    const roomPresence = this.presence.get(roomId);
    return roomPresence ? roomPresence.get(userId) : null;
  }

  /**
   * Get all rooms where a user is present
   */
  getUserRooms(userId) {
    const userRooms = [];
    
    for (const [roomId, roomPresence] of this.presence.entries()) {
      if (roomPresence.has(userId)) {
        userRooms.push({
          roomId,
          presence: roomPresence.get(userId)
        });
      }
    }
    
    return userRooms;
  }

  /**
   * Get user's global status
   */
  getUserStatus(userId) {
    return this.userStatus.get(userId) || 'offline';
  }

  /**
   * Set user's status explicitly (online, idle, away, offline)
   */
  async setUserStatus(roomId, userId, status) {
    try {
      const roomPresence = this.presence.get(roomId);
      if (!roomPresence || !roomPresence.has(userId)) {
        return;
      }

      const userPresence = roomPresence.get(userId);
      const previousStatus = userPresence.status;
      
      userPresence.status = status;
      userPresence.lastActivity = new Date();
      this.userStatus.set(userId, status);

      // Update activity based on status
      if (status === 'offline' || status === 'away') {
        userPresence.activity.annotating = false;
        userPresence.activity.viewing = false;
      } else if (status === 'online') {
        userPresence.activity.viewing = true;
      }

      // Broadcast status change if different
      if (previousStatus !== status) {
        await this.broadcastPresenceUpdate(roomId, userId, 'status-change', userPresence);
      }

      logger.debug(`User ${userPresence.username} status changed: ${previousStatus} -> ${status}`);

    } catch (error) {
      logger.error(`Error setting user status for ${userId}:`, error);
    }
  }

  /**
   * Check for idle users and update their status
   */
  checkIdleUsers() {
    const now = new Date();
    const idleThreshold = 5 * 60 * 1000; // 5 minutes
    const awayThreshold = 15 * 60 * 1000; // 15 minutes

    for (const [roomId, roomPresence] of this.presence.entries()) {
      for (const [userId, presence] of roomPresence.entries()) {
        const timeSinceActivity = now - presence.lastActivity;
        
        let newStatus = presence.status;
        
        if (timeSinceActivity > awayThreshold && presence.status !== 'away') {
          newStatus = 'away';
        } else if (timeSinceActivity > idleThreshold && presence.status === 'online') {
          newStatus = 'idle';
        } else if (timeSinceActivity < idleThreshold && presence.status !== 'online') {
          // User became active again
          newStatus = 'online';
        }

        if (newStatus !== presence.status) {
          this.setUserStatus(roomId, userId, newStatus).catch(error => 
            logger.error('Error updating idle user status:', error)
          );
        }
      }
    }
  }

  /**
   * Broadcast presence update to room
   */
  async broadcastPresenceUpdate(roomId, userId, eventType, presenceData) {
    try {
      const payload = {
        type: eventType,
        userId,
        presence: {
          userId: presenceData.userId,
          username: presenceData.username,
          status: presenceData.status,
          activity: presenceData.activity,
          lastActivity: presenceData.lastActivity
        },
        timestamp: new Date().toISOString()
      };

      this.io.to(roomId).emit('presence-update', payload);

      logger.debug(`Presence update broadcast to room ${roomId}:`, {
        event: eventType,
        user: presenceData.username,
        status: presenceData.status
      });

    } catch (error) {
      logger.error(`Error broadcasting presence update to room ${roomId}:`, error);
    }
  }

  /**
   * Throttled activity broadcast to prevent spam
   */
  async throttledActivityBroadcast(roomId, userId, activityType, presence) {
    const throttleKey = `${roomId}-${userId}-${activityType}`;
    const now = Date.now();
    
    if (!this.lastBroadcast) {
      this.lastBroadcast = new Map();
    }

    const lastBroadcast = this.lastBroadcast.get(throttleKey) || 0;
    const throttleInterval = this.getThrottleInterval(activityType);

    if (now - lastBroadcast > throttleInterval) {
      await this.broadcastPresenceUpdate(roomId, userId, 'activity-update', presence);
      this.lastBroadcast.set(throttleKey, now);
    }
  }

  /**
   * Get throttle interval based on activity type
   */
  getThrottleInterval(activityType) {
    const intervals = {
      'cursor-move': 100,    // 100ms for cursor movements
      'text-select': 200,    // 200ms for text selection
      'annotating': 1000,    // 1s for annotation activity
      'viewing': 5000,       // 5s for viewing activity
      'idle': 30000,         // 30s for idle status
      'away': 60000          // 1min for away status
    };

    return intervals[activityType] || 1000;
  }

  /**
   * Check if user is present in other rooms
   */
  isUserInOtherRooms(userId, excludeRoomId) {
    for (const [roomId, roomPresence] of this.presence.entries()) {
      if (roomId !== excludeRoomId && roomPresence.has(userId)) {
        return true;
      }
    }
    return false;
  }

  /**
   * Get presence analytics for a room
   */
  getRoomPresenceAnalytics(roomId) {
    const roomPresence = this.presence.get(roomId);
    if (!roomPresence) return null;

    const users = Array.from(roomPresence.values());
    const now = new Date();

    const statusCounts = {
      online: 0,
      idle: 0,
      away: 0,
      offline: 0
    };

    const activityCounts = {
      annotating: 0,
      viewing: 0,
      inactive: 0
    };

    let totalSessionTime = 0;
    let averageSessionTime = 0;

    users.forEach(user => {
      statusCounts[user.status]++;
      
      if (user.activity.annotating) activityCounts.annotating++;
      else if (user.activity.viewing) activityCounts.viewing++;
      else activityCounts.inactive++;

      totalSessionTime += now - user.joinedAt;
    });

    if (users.length > 0) {
      averageSessionTime = totalSessionTime / users.length;
    }

    return {
      roomId,
      timestamp: now.toISOString(),
      userCount: users.length,
      statusDistribution: statusCounts,
      activityDistribution: activityCounts,
      sessionMetrics: {
        totalSessionTime,
        averageSessionTime,
        activeUsers: statusCounts.online + statusCounts.idle
      }
    };
  }

  /**
   * Cleanup presence data for disconnected users
   */
  cleanup(socketId) {
    try {
      for (const [roomId, roomPresence] of this.presence.entries()) {
        for (const [userId, presence] of roomPresence.entries()) {
          if (presence.socketId === socketId) {
            this.userLeft(roomId, userId).catch(error => 
              logger.error(`Error during presence cleanup for user ${userId}:`, error)
            );
          }
        }
      }

      logger.debug(`Presence cleanup completed for socket ${socketId}`);
    } catch (error) {
      logger.error(`Error during presence cleanup:`, error);
    }
  }

  /**
   * Get all presence data (for debugging/monitoring)
   */
  getAllPresenceData() {
    const data = {};
    
    for (const [roomId, roomPresence] of this.presence.entries()) {
      data[roomId] = Array.from(roomPresence.values());
    }
    
    return data;
  }

  /**
   * Destroy presence manager
   */
  destroy() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
    }

    this.presence.clear();
    this.userStatus.clear();
    this.userLastActivity.clear();

    if (this.lastBroadcast) {
      this.lastBroadcast.clear();
    }

    logger.info('Presence Manager destroyed');
  }
}