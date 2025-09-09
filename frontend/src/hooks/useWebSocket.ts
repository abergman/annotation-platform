/**
 * WebSocket Hook for React Frontend
 * 
 * Provides real-time WebSocket connectivity for the annotation system
 * Handles connection management, room joining, and real-time events
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { io, Socket } from 'socket.io-client';
import { useAuth } from './useAuth';

export interface WebSocketOptions {
  autoConnect?: boolean;
  reconnectAttempts?: number;
  reconnectDelay?: number;
}

export interface RoomState {
  roomId: string;
  users: UserPresence[];
  annotations: any[];
  cursors: CursorInfo[];
  timestamp: string;
}

export interface UserPresence {
  userId: string;
  username: string;
  status: 'online' | 'idle' | 'away' | 'offline';
  joinedAt: string;
  lastActivity: string;
  activity: {
    annotating: boolean;
    viewing: boolean;
    cursorPosition?: any;
    selectedText?: any;
  };
}

export interface CursorInfo {
  userId: string;
  username: string;
  position: {
    offset: number;
    timestamp: string;
  };
  textId: string;
  color: string;
  lastUpdate: string;
  isActive: boolean;
}

export interface NotificationData {
  id: string;
  type: string;
  title: string;
  message: string;
  priority: 'low' | 'normal' | 'high' | 'critical';
  category: string;
  from?: { id: string; username: string };
  timestamp: string;
  read: boolean;
  actions?: Array<{ label: string; action: string }>;
}

export interface WebSocketState {
  connected: boolean;
  connecting: boolean;
  error: string | null;
  roomId: string | null;
  users: UserPresence[];
  cursors: CursorInfo[];
  notifications: NotificationData[];
  unreadCount: number;
}

export interface WebSocketActions {
  connect: () => void;
  disconnect: () => void;
  joinProject: (projectId: string, textId?: string) => Promise<void>;
  leaveProject: () => Promise<void>;
  
  // Annotation actions
  createAnnotation: (annotation: any) => Promise<void>;
  updateAnnotation: (annotation: any) => Promise<void>;
  deleteAnnotation: (annotationId: string) => Promise<void>;
  
  // Cursor and selection actions
  updateCursorPosition: (position: any, textId: string) => void;
  updateTextSelection: (selection: any, textId: string) => void;
  
  // Text editing actions
  sendTextOperation: (operation: any, textId: string) => void;
  
  // Comment actions
  createComment: (annotationId: string, comment: any) => Promise<void>;
  
  // Notification actions
  markNotificationRead: (notificationId: string) => Promise<void>;
  sendNotification: (notification: any, targetUsers?: string[]) => Promise<void>;
}

const WEBSOCKET_URL = process.env.REACT_APP_WEBSOCKET_URL || 'http://localhost:8001';

export function useWebSocket(options: WebSocketOptions = {}): [WebSocketState, WebSocketActions] {
  const {
    autoConnect = true,
    reconnectAttempts = 5,
    reconnectDelay = 1000
  } = options;

  const { user, token } = useAuth();
  const socketRef = useRef<Socket | null>(null);
  
  const [state, setState] = useState<WebSocketState>({
    connected: false,
    connecting: false,
    error: null,
    roomId: null,
    users: [],
    cursors: [],
    notifications: [],
    unreadCount: 0
  });

  // Event handlers
  const eventHandlers = useRef(new Map());

  /**
   * Connect to WebSocket server
   */
  const connect = useCallback(() => {
    if (!user || !token || socketRef.current?.connected) return;

    setState(prev => ({ ...prev, connecting: true, error: null }));

    const socket = io(WEBSOCKET_URL, {
      auth: {
        token: token
      },
      transports: ['websocket', 'polling'],
      reconnectionAttempts: reconnectAttempts,
      reconnectionDelay: reconnectDelay,
      timeout: 10000
    });

    // Connection events
    socket.on('connect', () => {
      setState(prev => ({ 
        ...prev, 
        connected: true, 
        connecting: false, 
        error: null 
      }));
      console.log('WebSocket connected:', socket.id);
    });

    socket.on('disconnect', (reason) => {
      setState(prev => ({ 
        ...prev, 
        connected: false, 
        connecting: false 
      }));
      console.log('WebSocket disconnected:', reason);
    });

    socket.on('connect_error', (error) => {
      setState(prev => ({ 
        ...prev, 
        connected: false, 
        connecting: false, 
        error: error.message 
      }));
      console.error('WebSocket connection error:', error);
    });

    // Room events
    socket.on('room-state', (roomState: RoomState) => {
      setState(prev => ({
        ...prev,
        roomId: roomState.roomId,
        users: roomState.users,
        cursors: roomState.cursors
      }));
    });

    socket.on('user-joined', (data: { userId: string; username: string; timestamp: string }) => {
      setState(prev => ({
        ...prev,
        users: [...prev.users.filter(u => u.userId !== data.userId), {
          userId: data.userId,
          username: data.username,
          status: 'online',
          joinedAt: data.timestamp,
          lastActivity: data.timestamp,
          activity: { annotating: false, viewing: true }
        } as UserPresence]
      }));
    });

    socket.on('user-left', (data: { userId: string; username: string; timestamp: string }) => {
      setState(prev => ({
        ...prev,
        users: prev.users.filter(u => u.userId !== data.userId),
        cursors: prev.cursors.filter(c => c.userId !== data.userId)
      }));
    });

    // Presence events
    socket.on('presence-update', (data: any) => {
      setState(prev => ({
        ...prev,
        users: prev.users.map(user => 
          user.userId === data.userId 
            ? { ...user, ...data.presence }
            : user
        )
      }));
    });

    // Cursor events
    socket.on('cursor-update', (data: any) => {
      setState(prev => ({
        ...prev,
        cursors: [
          ...prev.cursors.filter(c => c.userId !== data.userId),
          {
            userId: data.userId,
            username: data.username,
            position: data.position,
            textId: data.textId,
            color: data.color,
            lastUpdate: data.timestamp,
            isActive: true
          }
        ]
      }));
    });

    socket.on('cursor-removed', (data: { userId: string }) => {
      setState(prev => ({
        ...prev,
        cursors: prev.cursors.filter(c => c.userId !== data.userId)
      }));
    });

    socket.on('selection-update', (data: any) => {
      // Handle text selection updates
      eventHandlers.current.get('selection-update')?.(data);
    });

    // Annotation events
    socket.on('annotation-created', (data: any) => {
      eventHandlers.current.get('annotation-created')?.(data);
    });

    socket.on('annotation-updated', (data: any) => {
      eventHandlers.current.get('annotation-updated')?.(data);
    });

    socket.on('annotation-deleted', (data: any) => {
      eventHandlers.current.get('annotation-deleted')?.(data);
    });

    socket.on('annotation-conflict', (data: any) => {
      eventHandlers.current.get('annotation-conflict')?.(data);
    });

    // Comment events
    socket.on('comment-created', (data: any) => {
      eventHandlers.current.get('comment-created')?.(data);
    });

    // Text operation events
    socket.on('text-operation-applied', (data: any) => {
      eventHandlers.current.get('text-operation-applied')?.(data);
    });

    // Notification events
    socket.on('notification', (notification: NotificationData) => {
      setState(prev => ({
        ...prev,
        notifications: [notification, ...prev.notifications].slice(0, 100), // Keep last 100
        unreadCount: prev.unreadCount + 1
      }));
    });

    socket.on('queued-notifications', (data: { notifications: NotificationData[]; count: number }) => {
      setState(prev => ({
        ...prev,
        notifications: [...data.notifications, ...prev.notifications].slice(0, 100),
        unreadCount: prev.unreadCount + data.notifications.length
      }));
    });

    // Error events
    socket.on('error', (error: any) => {
      setState(prev => ({ ...prev, error: error.message }));
      console.error('WebSocket error:', error);
    });

    // Confirmation events
    socket.on('annotation-created-confirm', (data: any) => {
      eventHandlers.current.get('annotation-created-confirm')?.(data);
    });

    socket.on('annotation-updated-confirm', (data: any) => {
      eventHandlers.current.get('annotation-updated-confirm')?.(data);
    });

    socket.on('annotation-deleted-confirm', (data: any) => {
      eventHandlers.current.get('annotation-deleted-confirm')?.(data);
    });

    socketRef.current = socket;
  }, [user, token, reconnectAttempts, reconnectDelay]);

  /**
   * Disconnect from WebSocket server
   */
  const disconnect = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.disconnect();
      socketRef.current = null;
    }
  }, []);

  /**
   * Join a project room
   */
  const joinProject = useCallback(async (projectId: string, textId?: string) => {
    if (!socketRef.current?.connected) {
      throw new Error('WebSocket not connected');
    }

    return new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Join project timeout'));
      }, 10000);

      socketRef.current!.emit('join-project', { projectId, textId });
      
      // Wait for room state to confirm join
      const handleRoomState = (roomState: RoomState) => {
        clearTimeout(timeout);
        socketRef.current!.off('room-state', handleRoomState);
        resolve();
      };

      socketRef.current!.on('room-state', handleRoomState);
    });
  }, []);

  /**
   * Leave current project room
   */
  const leaveProject = useCallback(async () => {
    if (!socketRef.current?.connected || !state.roomId) return;

    const [, projectId, , textId] = state.roomId.split(':');
    socketRef.current.emit('leave-project', { projectId, textId });
    
    setState(prev => ({
      ...prev,
      roomId: null,
      users: [],
      cursors: []
    }));
  }, [state.roomId]);

  /**
   * Create annotation
   */
  const createAnnotation = useCallback(async (annotation: any) => {
    if (!socketRef.current?.connected || !state.roomId) {
      throw new Error('WebSocket not connected or not in a room');
    }

    return new Promise<void>((resolve, reject) => {
      const localId = `local_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
      const timeout = setTimeout(() => {
        reject(new Error('Create annotation timeout'));
      }, 10000);

      const handleConfirm = (data: any) => {
        if (data.localId === localId) {
          clearTimeout(timeout);
          socketRef.current!.off('annotation-created-confirm', handleConfirm);
          resolve();
        }
      };

      const handleError = (error: any) => {
        if (error.localId === localId) {
          clearTimeout(timeout);
          socketRef.current!.off('annotation-error', handleError);
          reject(new Error(error.message));
        }
      };

      socketRef.current!.on('annotation-created-confirm', handleConfirm);
      socketRef.current!.on('annotation-error', handleError);

      socketRef.current!.emit('annotation-create', {
        annotation: { ...annotation, localId },
        roomId: state.roomId
      });
    });
  }, [state.roomId]);

  /**
   * Update annotation
   */
  const updateAnnotation = useCallback(async (annotation: any) => {
    if (!socketRef.current?.connected || !state.roomId) {
      throw new Error('WebSocket not connected or not in a room');
    }

    return new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Update annotation timeout'));
      }, 10000);

      const handleConfirm = (data: any) => {
        if (data.annotation.id === annotation.id) {
          clearTimeout(timeout);
          socketRef.current!.off('annotation-updated-confirm', handleConfirm);
          resolve();
        }
      };

      socketRef.current!.on('annotation-updated-confirm', handleConfirm);
      socketRef.current!.emit('annotation-update', {
        annotation,
        roomId: state.roomId
      });
    });
  }, [state.roomId]);

  /**
   * Delete annotation
   */
  const deleteAnnotation = useCallback(async (annotationId: string) => {
    if (!socketRef.current?.connected || !state.roomId) {
      throw new Error('WebSocket not connected or not in a room');
    }

    return new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Delete annotation timeout'));
      }, 10000);

      const handleConfirm = (data: any) => {
        if (data.annotationId === annotationId) {
          clearTimeout(timeout);
          socketRef.current!.off('annotation-deleted-confirm', handleConfirm);
          resolve();
        }
      };

      socketRef.current!.on('annotation-deleted-confirm', handleConfirm);
      socketRef.current!.emit('annotation-delete', {
        annotationId,
        roomId: state.roomId
      });
    });
  }, [state.roomId]);

  /**
   * Update cursor position
   */
  const updateCursorPosition = useCallback((position: any, textId: string) => {
    if (!socketRef.current?.connected || !state.roomId) return;

    socketRef.current.emit('cursor-position', {
      roomId: state.roomId,
      position,
      textId
    });
  }, [state.roomId]);

  /**
   * Update text selection
   */
  const updateTextSelection = useCallback((selection: any, textId: string) => {
    if (!socketRef.current?.connected || !state.roomId) return;

    socketRef.current.emit('text-selection', {
      roomId: state.roomId,
      selection,
      textId
    });
  }, [state.roomId]);

  /**
   * Send text operation for collaborative editing
   */
  const sendTextOperation = useCallback((operation: any, textId: string) => {
    if (!socketRef.current?.connected || !state.roomId) return;

    socketRef.current.emit('text-operation', {
      roomId: state.roomId,
      operation,
      textId
    });
  }, [state.roomId]);

  /**
   * Create comment on annotation
   */
  const createComment = useCallback(async (annotationId: string, comment: any) => {
    if (!socketRef.current?.connected || !state.roomId) {
      throw new Error('WebSocket not connected or not in a room');
    }

    return new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Create comment timeout'));
      }, 10000);

      const handleConfirm = (data: any) => {
        clearTimeout(timeout);
        socketRef.current!.off('comment-created-confirm', handleConfirm);
        resolve();
      };

      socketRef.current!.on('comment-created-confirm', handleConfirm);
      socketRef.current!.emit('comment-create', {
        annotationId,
        comment,
        roomId: state.roomId
      });
    });
  }, [state.roomId]);

  /**
   * Mark notification as read
   */
  const markNotificationRead = useCallback(async (notificationId: string) => {
    // Update local state immediately
    setState(prev => ({
      ...prev,
      notifications: prev.notifications.map(n => 
        n.id === notificationId ? { ...n, read: true } : n
      ),
      unreadCount: Math.max(0, prev.unreadCount - 1)
    }));

    // Notify server
    if (socketRef.current?.connected) {
      socketRef.current.emit('notification-read', { notificationId });
    }
  }, []);

  /**
   * Send notification to other users
   */
  const sendNotification = useCallback(async (notification: any, targetUsers?: string[]) => {
    if (!socketRef.current?.connected || !state.roomId) {
      throw new Error('WebSocket not connected or not in a room');
    }

    socketRef.current.emit('send-notification', {
      roomId: state.roomId,
      notification,
      targetUsers
    });
  }, [state.roomId]);

  // Auto-connect on mount if enabled
  useEffect(() => {
    if (autoConnect && user && token) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [autoConnect, user, token, connect, disconnect]);

  // Event handler registration
  const addEventListener = useCallback((event: string, handler: Function) => {
    eventHandlers.current.set(event, handler);
    
    return () => {
      eventHandlers.current.delete(event);
    };
  }, []);

  return [
    state,
    {
      connect,
      disconnect,
      joinProject,
      leaveProject,
      createAnnotation,
      updateAnnotation,
      deleteAnnotation,
      updateCursorPosition,
      updateTextSelection,
      sendTextOperation,
      createComment,
      markNotificationRead,
      sendNotification,
      addEventListener
    } as WebSocketActions & { addEventListener: (event: string, handler: Function) => () => void }
  ];
}