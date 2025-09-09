/**
 * Cursor Manager
 * 
 * Manages real-time cursor tracking and text selection for collaborative editing
 * Shows where users are looking and what they have selected
 */

import { setupLogging } from '../utils/logger.js';

const logger = setupLogging('cursor-manager');

export class CursorManager {
  constructor(io) {
    this.io = io;
    this.roomCursors = new Map(); // Room ID -> Map of user cursors
    this.roomSelections = new Map(); // Room ID -> Map of user selections
    this.cursorHistory = new Map(); // Room ID -> History of cursor movements
    this.throttleTimers = new Map(); // User throttling timers
    this.cursorColors = new Map(); // User ID -> Assigned color
    this.availableColors = [
      '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57',
      '#FF9FF3', '#54A0FF', '#5F27CD', '#00D2D3', '#FF9F43',
      '#10AC84', '#EE5A6F', '#C44569', '#40407A', '#706FD3'
    ];
    this.colorIndex = 0;

    // Initialize cleanup interval
    this.cleanupInterval = setInterval(() => {
      this.cleanupStaleData();
    }, 60000); // Every minute
  }

  /**
   * Update user's cursor position in a room
   */
  async updateCursor(roomId, userId, cursorData) {
    try {
      const { position, textId, username, timestamp } = cursorData;

      // Initialize room cursors if needed
      if (!this.roomCursors.has(roomId)) {
        this.roomCursors.set(roomId, new Map());
      }

      const roomCursors = this.roomCursors.get(roomId);
      
      // Assign color if user doesn't have one
      if (!this.cursorColors.has(userId)) {
        this.cursorColors.set(userId, this.getNextColor());
      }

      const cursorInfo = {
        userId,
        username,
        position: {
          ...position,
          timestamp: timestamp || new Date().toISOString()
        },
        textId,
        color: this.cursorColors.get(userId),
        lastUpdate: new Date().toISOString(),
        isActive: true
      };

      // Update cursor data
      roomCursors.set(userId, cursorInfo);

      // Add to history (keep last 10 positions per user)
      this.addCursorToHistory(roomId, userId, cursorInfo);

      // Throttle broadcasts to prevent spam
      await this.throttledCursorBroadcast(roomId, userId, cursorInfo);

      logger.debug(`Cursor updated for user ${username} in room ${roomId}`, {
        position: position,
        textId: textId
      });

    } catch (error) {
      logger.error(`Error updating cursor for user ${userId} in room ${roomId}:`, error);
    }
  }

  /**
   * Update user's text selection in a room
   */
  async updateSelection(roomId, userId, selectionData) {
    try {
      const { selection, textId, username, timestamp } = selectionData;

      // Initialize room selections if needed
      if (!this.roomSelections.has(roomId)) {
        this.roomSelections.set(roomId, new Map());
      }

      const roomSelections = this.roomSelections.get(roomId);
      
      // Get user color
      if (!this.cursorColors.has(userId)) {
        this.cursorColors.set(userId, this.getNextColor());
      }

      const selectionInfo = {
        userId,
        username,
        selection: {
          ...selection,
          timestamp: timestamp || new Date().toISOString()
        },
        textId,
        color: this.cursorColors.get(userId),
        lastUpdate: new Date().toISOString(),
        isActive: true
      };

      // Update selection data
      roomSelections.set(userId, selectionInfo);

      // Broadcast selection update
      await this.broadcastSelectionUpdate(roomId, userId, selectionInfo);

      logger.debug(`Selection updated for user ${username} in room ${roomId}`, {
        selection: selection,
        textId: textId
      });

    } catch (error) {
      logger.error(`Error updating selection for user ${userId} in room ${roomId}:`, error);
    }
  }

  /**
   * Remove user's cursor and selection from room
   */
  async removeCursor(roomId, userId) {
    try {
      const roomCursors = this.roomCursors.get(roomId);
      const roomSelections = this.roomSelections.get(roomId);

      let removed = false;

      if (roomCursors && roomCursors.has(userId)) {
        roomCursors.delete(userId);
        removed = true;
      }

      if (roomSelections && roomSelections.has(userId)) {
        roomSelections.delete(userId);
        removed = true;
      }

      if (removed) {
        // Broadcast cursor/selection removal
        this.io.to(roomId).emit('cursor-removed', {
          userId,
          timestamp: new Date().toISOString()
        });

        logger.debug(`Cursor and selection removed for user ${userId} in room ${roomId}`);
      }

    } catch (error) {
      logger.error(`Error removing cursor for user ${userId} in room ${roomId}:`, error);
    }
  }

  /**
   * Get all cursors in a room
   */
  getRoomCursors(roomId) {
    const roomCursors = this.roomCursors.get(roomId);
    const roomSelections = this.roomSelections.get(roomId);

    const cursors = [];
    const selections = [];

    if (roomCursors) {
      cursors.push(...Array.from(roomCursors.values()));
    }

    if (roomSelections) {
      selections.push(...Array.from(roomSelections.values()));
    }

    return {
      cursors: cursors.filter(c => c.isActive),
      selections: selections.filter(s => s.isActive)
    };
  }

  /**
   * Get specific user's cursor in a room
   */
  getUserCursor(roomId, userId) {
    const roomCursors = this.roomCursors.get(roomId);
    return roomCursors ? roomCursors.get(userId) : null;
  }

  /**
   * Get specific user's selection in a room
   */
  getUserSelection(roomId, userId) {
    const roomSelections = this.roomSelections.get(roomId);
    return roomSelections ? roomSelections.get(userId) : null;
  }

  /**
   * Get cursor history for analytics
   */
  getCursorHistory(roomId, userId = null) {
    const roomHistory = this.cursorHistory.get(roomId);
    if (!roomHistory) return [];

    if (userId) {
      return roomHistory.filter(entry => entry.userId === userId);
    }

    return roomHistory;
  }

  /**
   * Set user as away (cursor becomes inactive)
   */
  async setUserAway(roomId, userId) {
    try {
      const roomCursors = this.roomCursors.get(roomId);
      const roomSelections = this.roomSelections.get(roomId);

      if (roomCursors && roomCursors.has(userId)) {
        const cursor = roomCursors.get(userId);
        cursor.isActive = false;
        cursor.lastUpdate = new Date().toISOString();
      }

      if (roomSelections && roomSelections.has(userId)) {
        const selection = roomSelections.get(userId);
        selection.isActive = false;
        selection.lastUpdate = new Date().toISOString();
      }

      // Broadcast user away status
      this.io.to(roomId).emit('cursor-away', {
        userId,
        timestamp: new Date().toISOString()
      });

    } catch (error) {
      logger.error(`Error setting user ${userId} away in room ${roomId}:`, error);
    }
  }

  /**
   * Set user as active (cursor becomes active again)
   */
  async setUserActive(roomId, userId) {
    try {
      const roomCursors = this.roomCursors.get(roomId);
      const roomSelections = this.roomSelections.get(roomId);

      if (roomCursors && roomCursors.has(userId)) {
        const cursor = roomCursors.get(userId);
        cursor.isActive = true;
        cursor.lastUpdate = new Date().toISOString();
      }

      if (roomSelections && roomSelections.has(userId)) {
        const selection = roomSelections.get(userId);
        selection.isActive = true;
        selection.lastUpdate = new Date().toISOString();
      }

      // Broadcast user active status
      this.io.to(roomId).emit('cursor-active', {
        userId,
        timestamp: new Date().toISOString()
      });

    } catch (error) {
      logger.error(`Error setting user ${userId} active in room ${roomId}:`, error);
    }
  }

  /**
   * Handle collaborative text editing cursor adjustments
   */
  async adjustCursorsForTextChange(roomId, textId, operation) {
    try {
      const { type, position, length, insertedText, deletedLength } = operation;
      const roomCursors = this.roomCursors.get(roomId);
      const roomSelections = this.roomSelections.get(roomId);

      if (!roomCursors && !roomSelections) return;

      const adjustedCursors = [];
      const adjustedSelections = [];

      // Adjust cursors
      if (roomCursors) {
        for (const [userId, cursor] of roomCursors.entries()) {
          if (cursor.textId === textId && cursor.isActive) {
            const adjustedPosition = this.adjustPositionForOperation(
              cursor.position,
              operation
            );

            if (adjustedPosition) {
              cursor.position = adjustedPosition;
              cursor.lastUpdate = new Date().toISOString();
              adjustedCursors.push({ userId, cursor });
            }
          }
        }
      }

      // Adjust selections
      if (roomSelections) {
        for (const [userId, selection] of roomSelections.entries()) {
          if (selection.textId === textId && selection.isActive) {
            const adjustedSelection = this.adjustSelectionForOperation(
              selection.selection,
              operation
            );

            if (adjustedSelection) {
              selection.selection = adjustedSelection;
              selection.lastUpdate = new Date().toISOString();
              adjustedSelections.push({ userId, selection });
            }
          }
        }
      }

      // Broadcast adjusted cursors and selections
      if (adjustedCursors.length > 0 || adjustedSelections.length > 0) {
        this.io.to(roomId).emit('cursors-adjusted', {
          cursors: adjustedCursors,
          selections: adjustedSelections,
          operation: operation,
          timestamp: new Date().toISOString()
        });
      }

    } catch (error) {
      logger.error(`Error adjusting cursors for text change in room ${roomId}:`, error);
    }
  }

  /**
   * Throttled cursor broadcast to prevent spam
   */
  async throttledCursorBroadcast(roomId, userId, cursorInfo) {
    const throttleKey = `cursor-${roomId}-${userId}`;
    const throttleDelay = 100; // 100ms throttle

    // Clear existing timer
    if (this.throttleTimers.has(throttleKey)) {
      clearTimeout(this.throttleTimers.get(throttleKey));
    }

    // Set new timer
    const timer = setTimeout(() => {
      this.broadcastCursorUpdate(roomId, userId, cursorInfo);
      this.throttleTimers.delete(throttleKey);
    }, throttleDelay);

    this.throttleTimers.set(throttleKey, timer);
  }

  /**
   * Broadcast cursor update to room
   */
  async broadcastCursorUpdate(roomId, userId, cursorInfo) {
    try {
      this.io.to(roomId).emit('cursor-update', {
        userId: cursorInfo.userId,
        username: cursorInfo.username,
        position: cursorInfo.position,
        textId: cursorInfo.textId,
        color: cursorInfo.color,
        timestamp: cursorInfo.lastUpdate
      });

    } catch (error) {
      logger.error(`Error broadcasting cursor update for room ${roomId}:`, error);
    }
  }

  /**
   * Broadcast selection update to room
   */
  async broadcastSelectionUpdate(roomId, userId, selectionInfo) {
    try {
      this.io.to(roomId).emit('selection-update', {
        userId: selectionInfo.userId,
        username: selectionInfo.username,
        selection: selectionInfo.selection,
        textId: selectionInfo.textId,
        color: selectionInfo.color,
        timestamp: selectionInfo.lastUpdate
      });

    } catch (error) {
      logger.error(`Error broadcasting selection update for room ${roomId}:`, error);
    }
  }

  /**
   * Add cursor position to history
   */
  addCursorToHistory(roomId, userId, cursorInfo) {
    if (!this.cursorHistory.has(roomId)) {
      this.cursorHistory.set(roomId, []);
    }

    const history = this.cursorHistory.get(roomId);
    history.push({
      userId,
      position: cursorInfo.position,
      textId: cursorInfo.textId,
      timestamp: cursorInfo.lastUpdate
    });

    // Keep only last 1000 entries
    if (history.length > 1000) {
      history.splice(0, history.length - 1000);
    }
  }

  /**
   * Get next available color for user
   */
  getNextColor() {
    const color = this.availableColors[this.colorIndex];
    this.colorIndex = (this.colorIndex + 1) % this.availableColors.length;
    return color;
  }

  /**
   * Adjust cursor position for text operation
   */
  adjustPositionForOperation(position, operation) {
    const { type, position: opPosition, length, insertedText } = operation;

    switch (type) {
      case 'insert':
        if (position.offset >= opPosition) {
          return {
            ...position,
            offset: position.offset + insertedText.length
          };
        }
        break;

      case 'delete':
        if (position.offset > opPosition + length) {
          return {
            ...position,
            offset: position.offset - length
          };
        } else if (position.offset > opPosition) {
          return {
            ...position,
            offset: opPosition
          };
        }
        break;

      case 'replace':
        const deletedLength = operation.deletedLength || 0;
        const insertedLength = insertedText.length;
        
        if (position.offset > opPosition + deletedLength) {
          return {
            ...position,
            offset: position.offset - deletedLength + insertedLength
          };
        } else if (position.offset > opPosition) {
          return {
            ...position,
            offset: opPosition
          };
        }
        break;
    }

    return position; // No adjustment needed
  }

  /**
   * Adjust selection range for text operation
   */
  adjustSelectionForOperation(selection, operation) {
    const adjustedStart = this.adjustPositionForOperation(
      { offset: selection.startOffset },
      operation
    );
    const adjustedEnd = this.adjustPositionForOperation(
      { offset: selection.endOffset },
      operation
    );

    if (adjustedStart && adjustedEnd) {
      return {
        ...selection,
        startOffset: adjustedStart.offset,
        endOffset: adjustedEnd.offset
      };
    }

    return null; // Selection became invalid
  }

  /**
   * Get cursor analytics for a room
   */
  getCursorAnalytics(roomId) {
    const roomCursors = this.roomCursors.get(roomId);
    const roomSelections = this.roomSelections.get(roomId);
    const history = this.cursorHistory.get(roomId) || [];

    if (!roomCursors && !roomSelections) return null;

    const activeCursors = roomCursors ? Array.from(roomCursors.values()).filter(c => c.isActive) : [];
    const activeSelections = roomSelections ? Array.from(roomSelections.values()).filter(s => s.isActive) : [];

    return {
      roomId,
      timestamp: new Date().toISOString(),
      cursors: {
        total: roomCursors ? roomCursors.size : 0,
        active: activeCursors.length,
        byUser: activeCursors.reduce((acc, cursor) => {
          acc[cursor.userId] = cursor.username;
          return acc;
        }, {})
      },
      selections: {
        total: roomSelections ? roomSelections.size : 0,
        active: activeSelections.length,
        byUser: activeSelections.reduce((acc, selection) => {
          acc[selection.userId] = selection.username;
          return acc;
        }, {})
      },
      history: {
        totalMovements: history.length,
        recentMovements: history.slice(-100).length
      }
    };
  }

  /**
   * Clean up stale cursor data
   */
  cleanupStaleData() {
    const now = new Date();
    const staleThreshold = 5 * 60 * 1000; // 5 minutes

    for (const [roomId, roomCursors] of this.roomCursors.entries()) {
      for (const [userId, cursor] of roomCursors.entries()) {
        const lastUpdate = new Date(cursor.lastUpdate);
        if (now - lastUpdate > staleThreshold) {
          roomCursors.delete(userId);
        }
      }

      // Clean up empty rooms
      if (roomCursors.size === 0) {
        this.roomCursors.delete(roomId);
      }
    }

    for (const [roomId, roomSelections] of this.roomSelections.entries()) {
      for (const [userId, selection] of roomSelections.entries()) {
        const lastUpdate = new Date(selection.lastUpdate);
        if (now - lastUpdate > staleThreshold) {
          roomSelections.delete(userId);
        }
      }

      // Clean up empty rooms
      if (roomSelections.size === 0) {
        this.roomSelections.delete(roomId);
      }
    }
  }

  /**
   * Clean up room data
   */
  cleanup(roomId) {
    this.roomCursors.delete(roomId);
    this.roomSelections.delete(roomId);
    this.cursorHistory.delete(roomId);

    logger.debug(`Cursor manager cleanup completed for room ${roomId}`);
  }

  /**
   * Destroy cursor manager
   */
  destroy() {
    // Clear cleanup interval
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
    }

    // Clear all throttle timers
    for (const timer of this.throttleTimers.values()) {
      clearTimeout(timer);
    }

    // Clear all data
    this.roomCursors.clear();
    this.roomSelections.clear();
    this.cursorHistory.clear();
    this.throttleTimers.clear();
    this.cursorColors.clear();

    logger.info('Cursor Manager destroyed');
  }
}