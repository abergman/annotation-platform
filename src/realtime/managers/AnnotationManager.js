/**
 * Annotation Manager
 * 
 * Manages real-time annotation operations, synchronization, and conflict resolution
 */

import { setupLogging } from '../utils/logger.js';
import { ValidationError, ConflictError } from '../utils/errors.js';

const logger = setupLogging('annotation-manager');

export class AnnotationManager {
  constructor(io) {
    this.io = io;
    this.roomAnnotations = new Map(); // Room ID -> Map of annotations
    this.annotationHistory = new Map(); // Annotation ID -> History array
    this.pendingOperations = new Map(); // Room ID -> Queue of pending operations
    this.locks = new Map(); // Annotation ID -> Lock info
    this.commentThreads = new Map(); // Annotation ID -> Comments array
    this.versionVectors = new Map(); // Room ID -> Version vectors for conflict resolution
  }

  /**
   * Create a new annotation in real-time
   */
  async createAnnotation(annotation, roomId) {
    try {
      // Validate annotation data
      this.validateAnnotation(annotation);

      // Generate server-side ID and version
      const annotationId = this.generateAnnotationId();
      const version = this.getNextVersion(roomId, annotation.createdBy);
      const timestamp = new Date().toISOString();

      const processedAnnotation = {
        id: annotationId,
        textId: annotation.textId,
        startOffset: annotation.startOffset,
        endOffset: annotation.endOffset,
        text: annotation.text,
        labels: annotation.labels || [],
        confidence: annotation.confidence,
        notes: annotation.notes || '',
        createdAt: timestamp,
        updatedAt: timestamp,
        createdBy: annotation.createdBy,
        version: version,
        status: 'active',
        metadata: {
          source: 'realtime',
          roomId: roomId,
          clientId: annotation.clientId,
          localId: annotation.localId
        }
      };

      // Store in room annotations
      if (!this.roomAnnotations.has(roomId)) {
        this.roomAnnotations.set(roomId, new Map());
      }
      
      this.roomAnnotations.get(roomId).set(annotationId, processedAnnotation);

      // Initialize history
      this.annotationHistory.set(annotationId, [{
        action: 'create',
        annotation: { ...processedAnnotation },
        timestamp: timestamp,
        userId: annotation.createdBy,
        version: version
      }]);

      // Persist to backend API
      await this.persistAnnotationToAPI(processedAnnotation, 'create');

      logger.info(`Annotation created: ${annotationId} in room ${roomId}`, {
        creator: annotation.createdBy,
        textRange: `${annotation.startOffset}-${annotation.endOffset}`
      });

      return processedAnnotation;

    } catch (error) {
      logger.error('Error creating annotation:', error);
      throw error;
    }
  }

  /**
   * Update an existing annotation in real-time
   */
  async updateAnnotation(annotation, roomId) {
    try {
      const annotationId = annotation.id;
      
      if (!annotationId) {
        throw new ValidationError('Annotation ID is required for updates');
      }

      // Check if annotation exists
      const roomAnnotations = this.roomAnnotations.get(roomId);
      if (!roomAnnotations || !roomAnnotations.has(annotationId)) {
        throw new ValidationError(`Annotation ${annotationId} not found in room ${roomId}`);
      }

      // Check for concurrent editing locks
      if (this.isLocked(annotationId, annotation.updatedBy)) {
        throw new ConflictError(`Annotation ${annotationId} is currently being edited by another user`);
      }

      const existingAnnotation = roomAnnotations.get(annotationId);
      const version = this.getNextVersion(roomId, annotation.updatedBy);
      const timestamp = new Date().toISOString();

      // Create updated annotation
      const updatedAnnotation = {
        ...existingAnnotation,
        ...annotation,
        id: annotationId, // Ensure ID doesn't change
        updatedAt: timestamp,
        updatedBy: annotation.updatedBy,
        version: version
      };

      // Validate updated annotation
      this.validateAnnotation(updatedAnnotation);

      // Update in memory
      roomAnnotations.set(annotationId, updatedAnnotation);

      // Add to history
      const history = this.annotationHistory.get(annotationId) || [];
      history.push({
        action: 'update',
        changes: this.calculateChanges(existingAnnotation, updatedAnnotation),
        annotation: { ...updatedAnnotation },
        timestamp: timestamp,
        userId: annotation.updatedBy,
        version: version
      });
      this.annotationHistory.set(annotationId, history);

      // Persist to backend API
      await this.persistAnnotationToAPI(updatedAnnotation, 'update');

      logger.info(`Annotation updated: ${annotationId} in room ${roomId}`, {
        updater: annotation.updatedBy,
        version: version
      });

      return updatedAnnotation;

    } catch (error) {
      logger.error('Error updating annotation:', error);
      throw error;
    }
  }

  /**
   * Delete an annotation in real-time
   */
  async deleteAnnotation(annotationId, userId, roomId) {
    try {
      const roomAnnotations = this.roomAnnotations.get(roomId);
      if (!roomAnnotations || !roomAnnotations.has(annotationId)) {
        throw new ValidationError(`Annotation ${annotationId} not found`);
      }

      // Check permissions (only creator or admin can delete)
      const annotation = roomAnnotations.get(annotationId);
      if (annotation.createdBy !== userId) {
        // TODO: Check if user has admin permissions
        throw new ValidationError('Insufficient permissions to delete annotation');
      }

      // Check for locks
      if (this.isLocked(annotationId, userId)) {
        throw new ConflictError('Cannot delete annotation that is being edited');
      }

      const timestamp = new Date().toISOString();
      const version = this.getNextVersion(roomId, userId);

      // Mark as deleted (soft delete for real-time sync)
      annotation.status = 'deleted';
      annotation.deletedAt = timestamp;
      annotation.deletedBy = userId;
      annotation.version = version;

      // Add to history
      const history = this.annotationHistory.get(annotationId) || [];
      history.push({
        action: 'delete',
        annotation: { ...annotation },
        timestamp: timestamp,
        userId: userId,
        version: version
      });
      this.annotationHistory.set(annotationId, history);

      // Persist deletion to backend API
      await this.persistAnnotationToAPI(annotation, 'delete');

      logger.info(`Annotation deleted: ${annotationId} in room ${roomId}`, {
        deleter: userId
      });

      return { annotationId, deletedAt: timestamp };

    } catch (error) {
      logger.error('Error deleting annotation:', error);
      throw error;
    }
  }

  /**
   * Add comment to an annotation
   */
  async addComment(annotationId, comment) {
    try {
      if (!this.commentThreads.has(annotationId)) {
        this.commentThreads.set(annotationId, []);
      }

      const commentId = this.generateCommentId();
      const timestamp = new Date().toISOString();

      const processedComment = {
        id: commentId,
        annotationId: annotationId,
        content: comment.content,
        authorId: comment.authorId,
        authorName: comment.authorName,
        createdAt: timestamp,
        updatedAt: timestamp,
        status: 'active',
        replies: []
      };

      this.commentThreads.get(annotationId).push(processedComment);

      // Persist to backend
      await this.persistCommentToAPI(processedComment);

      logger.info(`Comment added to annotation ${annotationId}`, {
        commentId,
        author: comment.authorName
      });

      return processedComment;

    } catch (error) {
      logger.error('Error adding comment:', error);
      throw error;
    }
  }

  /**
   * Get all annotations for a room
   */
  getRoomAnnotations(roomId) {
    const roomAnnotations = this.roomAnnotations.get(roomId);
    if (!roomAnnotations) return [];

    return Array.from(roomAnnotations.values())
      .filter(annotation => annotation.status === 'active')
      .sort((a, b) => a.startOffset - b.startOffset);
  }

  /**
   * Get specific annotation by ID
   */
  getAnnotation(roomId, annotationId) {
    const roomAnnotations = this.roomAnnotations.get(roomId);
    return roomAnnotations ? roomAnnotations.get(annotationId) : null;
  }

  /**
   * Get annotation history
   */
  getAnnotationHistory(annotationId) {
    return this.annotationHistory.get(annotationId) || [];
  }

  /**
   * Get comments for an annotation
   */
  getAnnotationComments(annotationId) {
    return this.commentThreads.get(annotationId) || [];
  }

  /**
   * Lock annotation for editing
   */
  async lockAnnotation(annotationId, userId, duration = 30000) {
    const lockInfo = {
      userId,
      lockedAt: Date.now(),
      duration,
      expires: Date.now() + duration
    };

    this.locks.set(annotationId, lockInfo);

    // Auto-unlock after duration
    setTimeout(() => {
      if (this.locks.get(annotationId) === lockInfo) {
        this.locks.delete(annotationId);
      }
    }, duration);

    logger.debug(`Annotation ${annotationId} locked by user ${userId}`);
  }

  /**
   * Unlock annotation
   */
  async unlockAnnotation(annotationId, userId) {
    const lock = this.locks.get(annotationId);
    if (lock && lock.userId === userId) {
      this.locks.delete(annotationId);
      logger.debug(`Annotation ${annotationId} unlocked by user ${userId}`);
    }
  }

  /**
   * Check if annotation is locked
   */
  isLocked(annotationId, userId) {
    const lock = this.locks.get(annotationId);
    if (!lock) return false;

    // Check if lock expired
    if (Date.now() > lock.expires) {
      this.locks.delete(annotationId);
      return false;
    }

    // Allow owner to edit
    return lock.userId !== userId;
  }

  /**
   * Validate annotation data
   */
  validateAnnotation(annotation) {
    if (!annotation.textId) {
      throw new ValidationError('Text ID is required');
    }

    if (typeof annotation.startOffset !== 'number' || annotation.startOffset < 0) {
      throw new ValidationError('Valid start offset is required');
    }

    if (typeof annotation.endOffset !== 'number' || annotation.endOffset <= annotation.startOffset) {
      throw new ValidationError('Valid end offset is required');
    }

    if (!annotation.text || annotation.text.trim().length === 0) {
      throw new ValidationError('Annotation text cannot be empty');
    }

    if (!annotation.createdBy && !annotation.updatedBy) {
      throw new ValidationError('User ID is required');
    }

    // Validate labels if provided
    if (annotation.labels && !Array.isArray(annotation.labels)) {
      throw new ValidationError('Labels must be an array');
    }

    // Validate confidence score
    if (annotation.confidence !== undefined) {
      if (typeof annotation.confidence !== 'number' || annotation.confidence < 0 || annotation.confidence > 1) {
        throw new ValidationError('Confidence must be a number between 0 and 1');
      }
    }
  }

  /**
   * Generate unique annotation ID
   */
  generateAnnotationId() {
    return `ann_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
  }

  /**
   * Generate unique comment ID
   */
  generateCommentId() {
    return `comment_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
  }

  /**
   * Get next version number for conflict resolution
   */
  getNextVersion(roomId, userId) {
    if (!this.versionVectors.has(roomId)) {
      this.versionVectors.set(roomId, new Map());
    }

    const roomVersions = this.versionVectors.get(roomId);
    const currentVersion = roomVersions.get(userId) || 0;
    const nextVersion = currentVersion + 1;
    
    roomVersions.set(userId, nextVersion);
    
    return nextVersion;
  }

  /**
   * Calculate changes between annotations
   */
  calculateChanges(oldAnnotation, newAnnotation) {
    const changes = {};
    
    const fields = ['text', 'labels', 'confidence', 'notes', 'startOffset', 'endOffset'];
    
    for (const field of fields) {
      if (JSON.stringify(oldAnnotation[field]) !== JSON.stringify(newAnnotation[field])) {
        changes[field] = {
          old: oldAnnotation[field],
          new: newAnnotation[field]
        };
      }
    }
    
    return changes;
  }

  /**
   * Persist annotation to backend API
   */
  async persistAnnotationToAPI(annotation, operation) {
    try {
      const apiUrl = process.env.API_URL || 'http://localhost:8000';
      let url, method;

      switch (operation) {
        case 'create':
          url = `${apiUrl}/api/annotations/`;
          method = 'POST';
          break;
        case 'update':
          url = `${apiUrl}/api/annotations/${annotation.id}`;
          method = 'PUT';
          break;
        case 'delete':
          url = `${apiUrl}/api/annotations/${annotation.id}`;
          method = 'DELETE';
          break;
      }

      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json'
        },
        body: operation !== 'delete' ? JSON.stringify(annotation) : undefined
      });

      if (!response.ok) {
        throw new Error(`API request failed: ${response.status} ${response.statusText}`);
      }

      logger.debug(`Annotation persisted to API: ${operation} ${annotation.id}`);

    } catch (error) {
      logger.error(`Failed to persist annotation to API:`, error);
      // Don't throw - allow real-time operation to continue
      // TODO: Queue for retry
    }
  }

  /**
   * Persist comment to backend API
   */
  async persistCommentToAPI(comment) {
    try {
      const apiUrl = process.env.API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/annotations/${comment.annotationId}/comments`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(comment)
      });

      if (!response.ok) {
        throw new Error(`Comment API request failed: ${response.status}`);
      }

    } catch (error) {
      logger.error('Failed to persist comment to API:', error);
    }
  }

  /**
   * Sync room annotations from backend API
   */
  async syncRoomAnnotations(roomId, projectId, textId) {
    try {
      const apiUrl = process.env.API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/projects/${projectId}/texts/${textId}/annotations`);
      
      if (response.ok) {
        const annotations = await response.json();
        
        if (!this.roomAnnotations.has(roomId)) {
          this.roomAnnotations.set(roomId, new Map());
        }

        const roomAnnotations = this.roomAnnotations.get(roomId);
        
        annotations.forEach(annotation => {
          roomAnnotations.set(annotation.id, annotation);
        });

        logger.info(`Synced ${annotations.length} annotations for room ${roomId}`);
      }

    } catch (error) {
      logger.error(`Failed to sync annotations for room ${roomId}:`, error);
    }
  }

  /**
   * Get annotation statistics for a room
   */
  getRoomAnnotationStats(roomId) {
    const roomAnnotations = this.roomAnnotations.get(roomId);
    if (!roomAnnotations) return null;

    const annotations = Array.from(roomAnnotations.values());
    const activeAnnotations = annotations.filter(a => a.status === 'active');

    const stats = {
      total: annotations.length,
      active: activeAnnotations.length,
      deleted: annotations.filter(a => a.status === 'deleted').length,
      byUser: {},
      byLabel: {},
      averageConfidence: 0
    };

    let totalConfidence = 0;
    let confidenceCount = 0;

    activeAnnotations.forEach(annotation => {
      // Count by user
      const creator = annotation.createdBy;
      stats.byUser[creator] = (stats.byUser[creator] || 0) + 1;

      // Count by labels
      annotation.labels?.forEach(label => {
        stats.byLabel[label] = (stats.byLabel[label] || 0) + 1;
      });

      // Calculate average confidence
      if (annotation.confidence !== undefined) {
        totalConfidence += annotation.confidence;
        confidenceCount++;
      }
    });

    if (confidenceCount > 0) {
      stats.averageConfidence = totalConfidence / confidenceCount;
    }

    return stats;
  }

  /**
   * Clean up room data
   */
  cleanup(roomId) {
    this.roomAnnotations.delete(roomId);
    
    // Clean up version vectors
    this.versionVectors.delete(roomId);
    
    // Clean up pending operations
    this.pendingOperations.delete(roomId);

    logger.debug(`Annotation manager cleanup completed for room ${roomId}`);
  }

  /**
   * Destroy annotation manager
   */
  destroy() {
    this.roomAnnotations.clear();
    this.annotationHistory.clear();
    this.pendingOperations.clear();
    this.locks.clear();
    this.commentThreads.clear();
    this.versionVectors.clear();

    logger.info('Annotation Manager destroyed');
  }
}