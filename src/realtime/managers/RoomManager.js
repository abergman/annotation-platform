/**
 * Room Manager
 * 
 * Manages WebSocket rooms for project-based collaboration
 * Handles room creation, joining, leaving, and cleanup
 */

import { setupLogging } from '../utils/logger.js';
import { RedisAdapter } from '../adapters/RedisAdapter.js';

const logger = setupLogging('room-manager');

export class RoomManager {
  constructor(io) {
    this.io = io;
    this.rooms = new Map(); // Room ID -> Room data
    this.userRooms = new Map(); // Socket ID -> Set of room IDs
    this.roomUsers = new Map(); // Room ID -> Set of user IDs
    this.redis = process.env.REDIS_URL ? new RedisAdapter(process.env.REDIS_URL) : null;
    
    // Room cleanup interval
    this.cleanupInterval = setInterval(() => {
      this.cleanupEmptyRooms();
    }, 30000); // Every 30 seconds
  }

  /**
   * Create or get room information
   */
  async createRoom(roomId, metadata = {}) {
    if (!this.rooms.has(roomId)) {
      const room = {
        id: roomId,
        created: new Date(),
        lastActivity: new Date(),
        metadata: {
          projectId: metadata.projectId,
          textId: metadata.textId,
          ...metadata
        },
        users: new Map(), // User ID -> User data
        settings: {
          maxUsers: metadata.maxUsers || 50,
          isPublic: metadata.isPublic || false,
          requiresApproval: metadata.requiresApproval || false
        },
        stats: {
          totalJoins: 0,
          totalMessages: 0,
          peakUsers: 0
        }
      };

      this.rooms.set(roomId, room);
      this.roomUsers.set(roomId, new Set());

      // Persist to Redis if available
      if (this.redis) {
        await this.redis.setRoom(roomId, room);
      }

      logger.info(`Room created: ${roomId}`, { metadata });
    }

    return this.rooms.get(roomId);
  }

  /**
   * User joins a room
   */
  async joinRoom(socket, roomId, userData = {}) {
    try {
      const userId = socket.user.id;
      const username = socket.user.username;

      // Create room if it doesn't exist
      const room = await this.createRoom(roomId, userData);

      // Check room capacity
      if (room.users.size >= room.settings.maxUsers) {
        throw new Error(`Room ${roomId} is at maximum capacity`);
      }

      // Join Socket.IO room
      socket.join(roomId);

      // Update room data
      room.users.set(userId, {
        id: userId,
        username,
        socketId: socket.id,
        joinedAt: new Date(),
        lastActivity: new Date(),
        ...userData
      });

      room.lastActivity = new Date();
      room.stats.totalJoins++;
      room.stats.peakUsers = Math.max(room.stats.peakUsers, room.users.size);

      // Update user-room mappings
      if (!this.userRooms.has(socket.id)) {
        this.userRooms.set(socket.id, new Set());
      }
      this.userRooms.get(socket.id).add(roomId);
      this.roomUsers.get(roomId).add(userId);

      // Persist updates to Redis
      if (this.redis) {
        await this.redis.setRoom(roomId, room);
        await this.redis.addUserToRoom(roomId, userId, socket.id);
      }

      logger.info(`User ${username} joined room ${roomId}`, {
        roomUsers: room.users.size,
        userRooms: this.userRooms.get(socket.id).size
      });

      return room;
    } catch (error) {
      logger.error(`Error joining room ${roomId}:`, error);
      throw error;
    }
  }

  /**
   * User leaves a room
   */
  async leaveRoom(socket, roomId) {
    try {
      const userId = socket.user.id;
      const username = socket.user.username;

      // Leave Socket.IO room
      socket.leave(roomId);

      // Update room data
      const room = this.rooms.get(roomId);
      if (room) {
        room.users.delete(userId);
        room.lastActivity = new Date();
      }

      // Update user-room mappings
      if (this.userRooms.has(socket.id)) {
        this.userRooms.get(socket.id).delete(roomId);
        if (this.userRooms.get(socket.id).size === 0) {
          this.userRooms.delete(socket.id);
        }
      }

      if (this.roomUsers.has(roomId)) {
        this.roomUsers.get(roomId).delete(userId);
      }

      // Persist updates to Redis
      if (this.redis) {
        if (room) {
          await this.redis.setRoom(roomId, room);
        }
        await this.redis.removeUserFromRoom(roomId, userId);
      }

      logger.info(`User ${username} left room ${roomId}`, {
        roomUsers: room?.users.size || 0
      });

      return room;
    } catch (error) {
      logger.error(`Error leaving room ${roomId}:`, error);
      throw error;
    }
  }

  /**
   * Get all rooms a user (socket) is in
   */
  getUserRooms(socketId) {
    return Array.from(this.userRooms.get(socketId) || []);
  }

  /**
   * Get all users in a room
   */
  getRoomUsers(roomId) {
    const room = this.rooms.get(roomId);
    return room ? Array.from(room.users.values()) : [];
  }

  /**
   * Get room information
   */
  getRoom(roomId) {
    return this.rooms.get(roomId);
  }

  /**
   * Get room statistics
   */
  getRoomStats(roomId) {
    const room = this.rooms.get(roomId);
    if (!room) return null;

    return {
      ...room.stats,
      currentUsers: room.users.size,
      lastActivity: room.lastActivity,
      created: room.created,
      uptime: Date.now() - room.created.getTime()
    };
  }

  /**
   * Update room activity timestamp
   */
  updateRoomActivity(roomId, activityType = 'message') {
    const room = this.rooms.get(roomId);
    if (room) {
      room.lastActivity = new Date();
      room.stats.totalMessages++;
      
      // Update user activity
      const users = Array.from(room.users.values());
      users.forEach(user => {
        if (user.socketId) {
          user.lastActivity = new Date();
        }
      });

      // Persist to Redis
      if (this.redis) {
        this.redis.setRoom(roomId, room).catch(err => 
          logger.error('Failed to persist room activity to Redis:', err)
        );
      }
    }
  }

  /**
   * Broadcast message to all users in a room except sender
   */
  async broadcastToRoom(roomId, event, data, excludeSocketId = null) {
    try {
      const room = this.rooms.get(roomId);
      if (!room) {
        logger.warn(`Attempted to broadcast to non-existent room: ${roomId}`);
        return;
      }

      this.updateRoomActivity(roomId);

      if (excludeSocketId) {
        this.io.to(roomId).except(excludeSocketId).emit(event, data);
      } else {
        this.io.to(roomId).emit(event, data);
      }

      logger.debug(`Broadcast to room ${roomId}: ${event}`, {
        userCount: room.users.size,
        excluded: !!excludeSocketId
      });

    } catch (error) {
      logger.error(`Error broadcasting to room ${roomId}:`, error);
      throw error;
    }
  }

  /**
   * Send message to specific user in room
   */
  async sendToUser(roomId, userId, event, data) {
    try {
      const room = this.rooms.get(roomId);
      if (!room || !room.users.has(userId)) {
        logger.warn(`User ${userId} not found in room ${roomId}`);
        return false;
      }

      const user = room.users.get(userId);
      const socket = this.io.sockets.sockets.get(user.socketId);
      
      if (socket) {
        socket.emit(event, data);
        this.updateRoomActivity(roomId);
        return true;
      }

      return false;
    } catch (error) {
      logger.error(`Error sending message to user ${userId} in room ${roomId}:`, error);
      return false;
    }
  }

  /**
   * Get all active rooms
   */
  getAllRooms() {
    return Array.from(this.rooms.entries()).map(([id, room]) => ({
      id,
      userCount: room.users.size,
      lastActivity: room.lastActivity,
      created: room.created,
      metadata: room.metadata,
      stats: room.stats
    }));
  }

  /**
   * Cleanup empty rooms periodically
   */
  cleanupEmptyRooms() {
    const now = new Date();
    const inactivityThreshold = 30 * 60 * 1000; // 30 minutes

    for (const [roomId, room] of this.rooms.entries()) {
      const inactive = now - room.lastActivity > inactivityThreshold;
      const empty = room.users.size === 0;

      if (empty && inactive) {
        this.rooms.delete(roomId);
        this.roomUsers.delete(roomId);

        // Remove from Redis
        if (this.redis) {
          this.redis.deleteRoom(roomId).catch(err => 
            logger.error(`Failed to delete room ${roomId} from Redis:`, err)
          );
        }

        logger.info(`Cleaned up empty room: ${roomId}`);
      }
    }
  }

  /**
   * Cleanup socket connections
   */
  async cleanup(socketId) {
    try {
      const userRooms = this.userRooms.get(socketId);
      if (userRooms) {
        for (const roomId of userRooms) {
          const room = this.rooms.get(roomId);
          if (room) {
            // Find and remove user by socket ID
            for (const [userId, user] of room.users.entries()) {
              if (user.socketId === socketId) {
                room.users.delete(userId);
                this.roomUsers.get(roomId)?.delete(userId);
                break;
              }
            }

            // Persist to Redis
            if (this.redis) {
              await this.redis.setRoom(roomId, room);
            }
          }
        }

        this.userRooms.delete(socketId);
      }

      logger.debug(`Cleaned up socket ${socketId}`);
    } catch (error) {
      logger.error(`Error during cleanup for socket ${socketId}:`, error);
    }
  }

  /**
   * Get detailed room analytics
   */
  getRoomAnalytics(roomId) {
    const room = this.rooms.get(roomId);
    if (!room) return null;

    const users = Array.from(room.users.values());
    const now = new Date();

    return {
      id: roomId,
      metadata: room.metadata,
      userCount: users.length,
      stats: room.stats,
      activity: {
        created: room.created,
        lastActivity: room.lastActivity,
        uptime: now - room.created,
        inactiveTime: now - room.lastActivity
      },
      users: users.map(user => ({
        id: user.id,
        username: user.username,
        joinedAt: user.joinedAt,
        lastActivity: user.lastActivity,
        sessionTime: now - user.joinedAt
      }))
    };
  }

  /**
   * Destroy room manager and cleanup resources
   */
  destroy() {
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
    }

    if (this.redis) {
      this.redis.close();
    }

    this.rooms.clear();
    this.userRooms.clear();
    this.roomUsers.clear();

    logger.info('Room Manager destroyed');
  }
}