/**
 * WebSocket Real-time Collaboration Server
 * 
 * Handles real-time collaboration features for the text annotation system:
 * - Real-time annotation sharing
 * - Live cursor tracking and user presence
 * - Collaborative editing with operational transforms
 * - Room-based connections per project/document
 * - Message queuing for offline users
 * - Integration with conflict resolution system
 */

import { Server } from 'socket.io';
import http from 'http';
import express from 'express';
import cors from 'cors';
import { authenticate } from './realtime/middleware/auth.js';
import { RoomManager } from './realtime/managers/RoomManager.js';
import { PresenceManager } from './realtime/managers/PresenceManager.js';
import { AnnotationManager } from './realtime/managers/AnnotationManager.js';
import { CursorManager } from './realtime/managers/CursorManager.js';
import { NotificationManager } from './realtime/managers/NotificationManager.js';
import { OperationalTransform } from './realtime/collaboration/OperationalTransform.js';
import { MessageQueue } from './realtime/queue/MessageQueue.js';
import { ConflictResolver } from './realtime/collaboration/ConflictResolver.js';
import { WebSocketMetrics } from './realtime/monitoring/WebSocketMetrics.js';
import { setupLogging } from './realtime/utils/logger.js';

const app = express();
const server = http.createServer(app);

// Enable CORS for cross-origin requests
app.use(cors({
  origin: process.env.FRONTEND_URL || "http://localhost:5173",
  credentials: true
}));

// Initialize Socket.IO with comprehensive configuration
const io = new Server(server, {
  cors: {
    origin: process.env.FRONTEND_URL || "http://localhost:5173",
    methods: ["GET", "POST"],
    credentials: true
  },
  // Optimize for real-time collaboration
  transports: ['websocket', 'polling'],
  allowEIO3: true,
  pingTimeout: 60000,
  pingInterval: 25000,
  // Enable compression for better performance
  compression: true,
  // Configure adapter for scaling (Redis in production)
  adapter: process.env.NODE_ENV === 'production' ? undefined : undefined
});

// Initialize managers and services
const roomManager = new RoomManager(io);
const presenceManager = new PresenceManager(io);
const annotationManager = new AnnotationManager(io);
const cursorManager = new CursorManager(io);
const notificationManager = new NotificationManager(io);
const operationalTransform = new OperationalTransform();
const messageQueue = new MessageQueue();
const conflictResolver = new ConflictResolver();
const metrics = new WebSocketMetrics();

// Setup logging
const logger = setupLogging('websocket-server');

// Authentication middleware for Socket.IO
io.use(authenticate);

// WebSocket connection handling
io.on('connection', async (socket) => {
  const userId = socket.user.id;
  const username = socket.user.username;
  
  logger.info(`User connected: ${username} (${userId}), Socket: ${socket.id}`);
  metrics.recordConnection(userId);

  // Handle user joining a project room
  socket.on('join-project', async (data) => {
    try {
      const { projectId, textId } = data;
      const roomId = textId ? `project:${projectId}:text:${textId}` : `project:${projectId}`;
      
      // Validate user access to project
      const hasAccess = await validateProjectAccess(userId, projectId);
      if (!hasAccess) {
        socket.emit('error', { message: 'Unauthorized access to project' });
        return;
      }

      // Join room and update presence
      await roomManager.joinRoom(socket, roomId, { projectId, textId, userId, username });
      await presenceManager.userJoined(roomId, userId, username, socket.id);
      
      // Send current room state
      const roomState = await getRoomState(roomId);
      socket.emit('room-state', roomState);
      
      // Notify other users in room
      socket.to(roomId).emit('user-joined', {
        userId,
        username,
        timestamp: new Date().toISOString()
      });

      // Process any queued messages for this user
      const queuedMessages = await messageQueue.getMessages(userId, roomId);
      if (queuedMessages.length > 0) {
        socket.emit('queued-messages', queuedMessages);
        await messageQueue.clearMessages(userId, roomId);
      }

      logger.info(`User ${username} joined room: ${roomId}`);
      metrics.recordRoomJoin(roomId, userId);

    } catch (error) {
      logger.error('Error joining project:', error);
      socket.emit('error', { message: 'Failed to join project' });
    }
  });

  // Handle leaving a project room
  socket.on('leave-project', async (data) => {
    try {
      const { projectId, textId } = data;
      const roomId = textId ? `project:${projectId}:text:${textId}` : `project:${projectId}`;
      
      await roomManager.leaveRoom(socket, roomId);
      await presenceManager.userLeft(roomId, userId);
      
      // Notify other users
      socket.to(roomId).emit('user-left', {
        userId,
        username,
        timestamp: new Date().toISOString()
      });

      logger.info(`User ${username} left room: ${roomId}`);
      metrics.recordRoomLeave(roomId, userId);

    } catch (error) {
      logger.error('Error leaving project:', error);
    }
  });

  // Real-time annotation events
  socket.on('annotation-create', async (data) => {
    try {
      const { annotation, roomId } = data;
      
      // Validate and process annotation
      const processedAnnotation = await annotationManager.createAnnotation(
        { ...annotation, createdBy: userId },
        roomId
      );

      // Apply operational transform for concurrent editing
      const transformedAnnotation = await operationalTransform.transformAnnotation(
        processedAnnotation,
        roomId
      );

      // Check for conflicts
      const conflicts = await conflictResolver.checkAnnotationConflicts(
        transformedAnnotation,
        roomId
      );

      if (conflicts.length > 0) {
        // Handle conflicts - notify users
        await handleAnnotationConflicts(socket, conflicts, transformedAnnotation, roomId);
      } else {
        // Broadcast to all users in room
        socket.to(roomId).emit('annotation-created', {
          annotation: transformedAnnotation,
          createdBy: { id: userId, username },
          timestamp: new Date().toISOString()
        });

        // Send confirmation to creator
        socket.emit('annotation-created-confirm', {
          localId: annotation.localId,
          annotation: transformedAnnotation
        });
      }

      logger.info(`Annotation created by ${username} in room ${roomId}`);
      metrics.recordAnnotationEvent('create', roomId, userId);

    } catch (error) {
      logger.error('Error creating annotation:', error);
      socket.emit('annotation-error', { 
        message: 'Failed to create annotation',
        localId: data.annotation.localId 
      });
    }
  });

  socket.on('annotation-update', async (data) => {
    try {
      const { annotation, roomId } = data;
      
      const updatedAnnotation = await annotationManager.updateAnnotation(
        { ...annotation, updatedBy: userId },
        roomId
      );

      const transformedAnnotation = await operationalTransform.transformAnnotation(
        updatedAnnotation,
        roomId
      );

      // Check for conflicts
      const conflicts = await conflictResolver.checkAnnotationConflicts(
        transformedAnnotation,
        roomId
      );

      if (conflicts.length > 0) {
        await handleAnnotationConflicts(socket, conflicts, transformedAnnotation, roomId);
      } else {
        socket.to(roomId).emit('annotation-updated', {
          annotation: transformedAnnotation,
          updatedBy: { id: userId, username },
          timestamp: new Date().toISOString()
        });

        socket.emit('annotation-updated-confirm', {
          annotation: transformedAnnotation
        });
      }

      metrics.recordAnnotationEvent('update', roomId, userId);

    } catch (error) {
      logger.error('Error updating annotation:', error);
      socket.emit('annotation-error', { message: 'Failed to update annotation' });
    }
  });

  socket.on('annotation-delete', async (data) => {
    try {
      const { annotationId, roomId } = data;
      
      await annotationManager.deleteAnnotation(annotationId, userId, roomId);

      socket.to(roomId).emit('annotation-deleted', {
        annotationId,
        deletedBy: { id: userId, username },
        timestamp: new Date().toISOString()
      });

      socket.emit('annotation-deleted-confirm', { annotationId });
      metrics.recordAnnotationEvent('delete', roomId, userId);

    } catch (error) {
      logger.error('Error deleting annotation:', error);
      socket.emit('annotation-error', { message: 'Failed to delete annotation' });
    }
  });

  // Live cursor tracking
  socket.on('cursor-position', async (data) => {
    try {
      const { roomId, position, textId } = data;
      
      await cursorManager.updateCursor(roomId, userId, {
        position,
        textId,
        username,
        timestamp: new Date().toISOString()
      });

      // Broadcast cursor position to other users
      socket.to(roomId).emit('cursor-update', {
        userId,
        username,
        position,
        textId
      });

    } catch (error) {
      logger.error('Error updating cursor position:', error);
    }
  });

  socket.on('text-selection', async (data) => {
    try {
      const { roomId, selection, textId } = data;
      
      await cursorManager.updateSelection(roomId, userId, {
        selection,
        textId,
        username,
        timestamp: new Date().toISOString()
      });

      // Broadcast selection to other users
      socket.to(roomId).emit('selection-update', {
        userId,
        username,
        selection,
        textId
      });

    } catch (error) {
      logger.error('Error updating text selection:', error);
    }
  });

  // Collaborative editing events
  socket.on('text-operation', async (data) => {
    try {
      const { roomId, operation, textId } = data;
      
      // Apply operational transform
      const transformedOperation = await operationalTransform.transformOperation(
        operation,
        roomId,
        userId
      );

      // Broadcast transformed operation
      socket.to(roomId).emit('text-operation-applied', {
        operation: transformedOperation,
        appliedBy: { id: userId, username },
        textId,
        timestamp: new Date().toISOString()
      });

      metrics.recordTextOperation(roomId, userId);

    } catch (error) {
      logger.error('Error processing text operation:', error);
      socket.emit('operation-error', { message: 'Failed to apply text operation' });
    }
  });

  // Notification handling
  socket.on('send-notification', async (data) => {
    try {
      const { roomId, notification, targetUsers } = data;
      
      await notificationManager.sendNotification(roomId, {
        ...notification,
        from: { id: userId, username },
        timestamp: new Date().toISOString()
      }, targetUsers);

    } catch (error) {
      logger.error('Error sending notification:', error);
    }
  });

  // Comment system for annotations
  socket.on('comment-create', async (data) => {
    try {
      const { annotationId, comment, roomId } = data;
      
      const newComment = await annotationManager.addComment(annotationId, {
        ...comment,
        authorId: userId,
        authorName: username,
        timestamp: new Date().toISOString()
      });

      socket.to(roomId).emit('comment-created', {
        annotationId,
        comment: newComment,
        author: { id: userId, username }
      });

      socket.emit('comment-created-confirm', { comment: newComment });

    } catch (error) {
      logger.error('Error creating comment:', error);
      socket.emit('comment-error', { message: 'Failed to create comment' });
    }
  });

  // Handle disconnection
  socket.on('disconnect', async (reason) => {
    try {
      logger.info(`User ${username} disconnected: ${reason}`);
      
      // Clean up user presence in all rooms
      const userRooms = await roomManager.getUserRooms(socket.id);
      for (const roomId of userRooms) {
        await presenceManager.userLeft(roomId, userId);
        await cursorManager.removeCursor(roomId, userId);
        
        // Notify other users
        socket.to(roomId).emit('user-left', {
          userId,
          username,
          reason,
          timestamp: new Date().toISOString()
        });
      }

      await roomManager.cleanup(socket.id);
      metrics.recordDisconnection(userId, reason);

    } catch (error) {
      logger.error('Error handling disconnect:', error);
    }
  });

  // Handle connection errors
  socket.on('error', (error) => {
    logger.error(`Socket error for user ${username}:`, error);
    metrics.recordError('socket_error', userId);
  });
});

// Helper functions
async function validateProjectAccess(userId, projectId) {
  try {
    // Call FastAPI backend to validate access
    const response = await fetch(`${process.env.API_URL}/api/projects/${projectId}/access/${userId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      }
    });
    return response.ok;
  } catch (error) {
    logger.error('Error validating project access:', error);
    return false;
  }
}

async function getRoomState(roomId) {
  try {
    const [presence, annotations, cursors] = await Promise.all([
      presenceManager.getRoomPresence(roomId),
      annotationManager.getRoomAnnotations(roomId),
      cursorManager.getRoomCursors(roomId)
    ]);

    return {
      roomId,
      users: presence,
      annotations,
      cursors,
      timestamp: new Date().toISOString()
    };
  } catch (error) {
    logger.error('Error getting room state:', error);
    return { roomId, users: [], annotations: [], cursors: [] };
  }
}

async function handleAnnotationConflicts(socket, conflicts, annotation, roomId) {
  try {
    // Notify all users about the conflict
    io.to(roomId).emit('annotation-conflict', {
      conflicts,
      annotation,
      timestamp: new Date().toISOString()
    });

    // Queue conflicted annotation for resolution
    await messageQueue.queueConflictResolution(roomId, conflicts, annotation);
    
    logger.warn(`Annotation conflict detected in room ${roomId}`, { conflicts });

  } catch (error) {
    logger.error('Error handling annotation conflicts:', error);
  }
}

// Health check endpoint
app.get('/health', (req, res) => {
  const stats = metrics.getStats();
  res.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    websocket: {
      connected_users: stats.connectedUsers,
      active_rooms: stats.activeRooms,
      total_messages: stats.totalMessages,
      uptime: stats.uptime
    }
  });
});

// Metrics endpoint
app.get('/metrics', (req, res) => {
  res.json(metrics.getDetailedStats());
});

// Start server
const PORT = process.env.WEBSOCKET_PORT || 8001;
server.listen(PORT, () => {
  logger.info(`🚀 WebSocket server running on port ${PORT}`);
  logger.info(`🌐 CORS enabled for: ${process.env.FRONTEND_URL || "http://localhost:5173"}`);
});

// Graceful shutdown
process.on('SIGTERM', async () => {
  logger.info('Shutting down WebSocket server...');
  await messageQueue.close();
  server.close(() => {
    logger.info('WebSocket server closed');
    process.exit(0);
  });
});

export default server;