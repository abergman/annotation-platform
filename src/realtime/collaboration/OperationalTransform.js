/**
 * Operational Transform Engine
 * 
 * Implements operational transforms for real-time collaborative editing
 * Handles text operations and annotation position adjustments
 */

import { setupLogging } from '../utils/logger.js';

const logger = setupLogging('operational-transform');

export class OperationalTransform {
  constructor() {
    this.operationHistory = new Map(); // Room ID -> Array of operations
    this.transformCache = new Map(); // Cache for transformed operations
    this.stateVectors = new Map(); // Room ID -> State vectors for each client
    this.pendingOps = new Map(); // Room ID -> Queue of pending operations
  }

  /**
   * Transform an annotation against concurrent operations
   */
  async transformAnnotation(annotation, roomId) {
    try {
      const operations = this.getRecentOperations(roomId);
      let transformedAnnotation = { ...annotation };

      // Apply each operation to transform annotation positions
      for (const operation of operations) {
        if (this.shouldTransformAnnotation(transformedAnnotation, operation)) {
          transformedAnnotation = this.applyOperationToAnnotation(transformedAnnotation, operation);
        }
      }

      logger.debug(`Transformed annotation in room ${roomId}`, {
        original: `${annotation.startOffset}-${annotation.endOffset}`,
        transformed: `${transformedAnnotation.startOffset}-${transformedAnnotation.endOffset}`,
        operations: operations.length
      });

      return transformedAnnotation;

    } catch (error) {
      logger.error('Error transforming annotation:', error);
      throw error;
    }
  }

  /**
   * Transform a text operation against concurrent operations
   */
  async transformOperation(operation, roomId, userId) {
    try {
      // Get state vector for this client
      const clientState = this.getClientState(roomId, userId);
      const serverOperations = this.getOperationsAfterState(roomId, clientState);

      let transformedOp = { ...operation };

      // Transform against each server operation
      for (const serverOp of serverOperations) {
        transformedOp = this.transformOperationPair(transformedOp, serverOp);
      }

      // Add to operation history
      this.addOperation(roomId, {
        ...transformedOp,
        userId: userId,
        timestamp: new Date().toISOString(),
        state: this.incrementState(roomId, userId)
      });

      logger.debug(`Transformed operation in room ${roomId}`, {
        type: operation.type,
        userId: userId,
        serverOps: serverOperations.length
      });

      return transformedOp;

    } catch (error) {
      logger.error('Error transforming operation:', error);
      throw error;
    }
  }

  /**
   * Transform two operations against each other (Operational Transform core)
   */
  transformOperationPair(op1, op2) {
    const type1 = op1.type;
    const type2 = op2.type;

    // Cache key for memoization
    const cacheKey = this.getCacheKey(op1, op2);
    if (this.transformCache.has(cacheKey)) {
      return this.transformCache.get(cacheKey);
    }

    let result;

    if (type1 === 'insert' && type2 === 'insert') {
      result = this.transformInsertInsert(op1, op2);
    } else if (type1 === 'insert' && type2 === 'delete') {
      result = this.transformInsertDelete(op1, op2);
    } else if (type1 === 'delete' && type2 === 'insert') {
      result = this.transformDeleteInsert(op1, op2);
    } else if (type1 === 'delete' && type2 === 'delete') {
      result = this.transformDeleteDelete(op1, op2);
    } else if (type1 === 'replace' || type2 === 'replace') {
      result = this.transformWithReplace(op1, op2);
    } else {
      // No transformation needed
      result = op1;
    }

    // Cache the result
    this.transformCache.set(cacheKey, result);
    return result;
  }

  /**
   * Transform insert against insert operations
   */
  transformInsertInsert(op1, op2) {
    if (op1.position <= op2.position) {
      return op1; // No change needed
    } else {
      return {
        ...op1,
        position: op1.position + op2.text.length
      };
    }
  }

  /**
   * Transform insert against delete operations
   */
  transformInsertDelete(op1, op2) {
    if (op1.position <= op2.position) {
      return op1; // No change needed
    } else if (op1.position <= op2.position + op2.length) {
      return {
        ...op1,
        position: op2.position
      };
    } else {
      return {
        ...op1,
        position: op1.position - op2.length
      };
    }
  }

  /**
   * Transform delete against insert operations
   */
  transformDeleteInsert(op1, op2) {
    if (op2.position <= op1.position) {
      return {
        ...op1,
        position: op1.position + op2.text.length
      };
    } else if (op2.position < op1.position + op1.length) {
      return {
        ...op1,
        length: op1.length + op2.text.length
      };
    } else {
      return op1; // No change needed
    }
  }

  /**
   * Transform delete against delete operations
   */
  transformDeleteDelete(op1, op2) {
    if (op2.position + op2.length <= op1.position) {
      // op2 is completely before op1
      return {
        ...op1,
        position: op1.position - op2.length
      };
    } else if (op2.position >= op1.position + op1.length) {
      // op2 is completely after op1
      return op1;
    } else {
      // Operations overlap - need to adjust
      const op1End = op1.position + op1.length;
      const op2End = op2.position + op2.length;

      if (op2.position <= op1.position && op2End >= op1End) {
        // op2 completely contains op1 - op1 becomes no-op
        return {
          ...op1,
          type: 'noop',
          length: 0
        };
      } else if (op1.position <= op2.position && op1End >= op2End) {
        // op1 completely contains op2
        return {
          ...op1,
          length: op1.length - op2.length
        };
      } else {
        // Partial overlap - adjust position and length
        const newPosition = Math.min(op1.position, op2.position);
        const deletedByOp2 = Math.max(0, Math.min(op1End, op2End) - Math.max(op1.position, op2.position));
        
        return {
          ...op1,
          position: newPosition,
          length: op1.length - deletedByOp2
        };
      }
    }
  }

  /**
   * Transform operations involving replace
   */
  transformWithReplace(op1, op2) {
    // Replace operations are treated as delete + insert
    if (op1.type === 'replace') {
      const deleteOp = {
        type: 'delete',
        position: op1.position,
        length: op1.deleteLength || op1.originalText?.length || 0
      };
      const insertOp = {
        type: 'insert',
        position: op1.position,
        text: op1.text
      };

      // Transform both parts
      const transformedDelete = this.transformOperationPair(deleteOp, op2);
      const transformedInsert = this.transformOperationPair(insertOp, op2);

      return {
        ...op1,
        position: transformedDelete.position,
        deleteLength: transformedDelete.length,
        text: transformedInsert.text
      };
    } else {
      // Transform op1 against replace (treat replace as delete + insert)
      const deleteOp = {
        type: 'delete',
        position: op2.position,
        length: op2.deleteLength || op2.originalText?.length || 0
      };
      const insertOp = {
        type: 'insert',
        position: op2.position,
        text: op2.text
      };

      let result = this.transformOperationPair(op1, deleteOp);
      result = this.transformOperationPair(result, insertOp);
      
      return result;
    }
  }

  /**
   * Apply operation to annotation positions
   */
  applyOperationToAnnotation(annotation, operation) {
    const { type, position, length, text } = operation;
    let { startOffset, endOffset } = annotation;

    switch (type) {
      case 'insert':
        if (position <= startOffset) {
          startOffset += text.length;
          endOffset += text.length;
        } else if (position < endOffset) {
          endOffset += text.length;
        }
        break;

      case 'delete':
        if (position + length <= startOffset) {
          startOffset -= length;
          endOffset -= length;
        } else if (position < startOffset) {
          const deletedFromStart = Math.min(length, startOffset - position);
          const deletedFromAnnotation = Math.max(0, Math.min(length - deletedFromStart, endOffset - startOffset));
          
          startOffset = position;
          endOffset = endOffset - deletedFromStart - deletedFromAnnotation;
        } else if (position < endOffset) {
          const deletedFromAnnotation = Math.min(length, endOffset - position);
          endOffset -= deletedFromAnnotation;
        }
        break;

      case 'replace':
        const deleteLength = operation.deleteLength || operation.originalText?.length || 0;
        const insertLength = text.length;
        
        // Apply as delete then insert
        const afterDelete = this.applyOperationToAnnotation(annotation, {
          type: 'delete',
          position,
          length: deleteLength
        });
        
        return this.applyOperationToAnnotation(afterDelete, {
          type: 'insert',
          position,
          text
        });

      case 'noop':
        // No operation needed
        break;
    }

    // Ensure valid offsets
    if (startOffset < 0) startOffset = 0;
    if (endOffset < startOffset) endOffset = startOffset;

    return {
      ...annotation,
      startOffset,
      endOffset
    };
  }

  /**
   * Check if annotation should be transformed by operation
   */
  shouldTransformAnnotation(annotation, operation) {
    // Skip if annotation doesn't affect the same text
    if (annotation.textId !== operation.textId) {
      return false;
    }

    // Skip operations that are too old
    const operationTime = new Date(operation.timestamp);
    const annotationTime = new Date(annotation.updatedAt || annotation.createdAt);
    const timeDiff = Math.abs(annotationTime - operationTime);
    
    if (timeDiff > 60000) { // 1 minute threshold
      return false;
    }

    return true;
  }

  /**
   * Get recent operations for a room
   */
  getRecentOperations(roomId, limit = 100) {
    const operations = this.operationHistory.get(roomId) || [];
    return operations.slice(-limit);
  }

  /**
   * Get operations after a specific state
   */
  getOperationsAfterState(roomId, clientState) {
    const operations = this.operationHistory.get(roomId) || [];
    
    return operations.filter(op => {
      const opState = op.state || 0;
      const clientOpState = clientState[op.userId] || 0;
      return opState > clientOpState;
    });
  }

  /**
   * Get client state vector
   */
  getClientState(roomId, userId) {
    if (!this.stateVectors.has(roomId)) {
      this.stateVectors.set(roomId, new Map());
    }
    
    const roomStates = this.stateVectors.get(roomId);
    return roomStates.get(userId) || {};
  }

  /**
   * Increment client state
   */
  incrementState(roomId, userId) {
    if (!this.stateVectors.has(roomId)) {
      this.stateVectors.set(roomId, new Map());
    }
    
    const roomStates = this.stateVectors.get(roomId);
    const currentState = roomStates.get(userId) || {};
    const newState = { ...currentState };
    
    newState[userId] = (newState[userId] || 0) + 1;
    roomStates.set(userId, newState);
    
    return newState[userId];
  }

  /**
   * Add operation to history
   */
  addOperation(roomId, operation) {
    if (!this.operationHistory.has(roomId)) {
      this.operationHistory.set(roomId, []);
    }

    const operations = this.operationHistory.get(roomId);
    operations.push(operation);

    // Limit history size
    if (operations.length > 1000) {
      operations.splice(0, operations.length - 1000);
    }
  }

  /**
   * Generate cache key for operation pair
   */
  getCacheKey(op1, op2) {
    return `${op1.type}:${op1.position}:${op1.length||op1.text?.length||0}_${op2.type}:${op2.position}:${op2.length||op2.text?.length||0}`;
  }

  /**
   * Compose multiple operations into a single operation
   */
  composeOperations(operations) {
    if (operations.length === 0) return null;
    if (operations.length === 1) return operations[0];

    let result = operations[0];
    for (let i = 1; i < operations.length; i++) {
      result = this.composeTwoOperations(result, operations[i]);
    }

    return result;
  }

  /**
   * Compose two operations into one
   */
  composeTwoOperations(op1, op2) {
    // Simple composition - can be enhanced for better optimization
    if (op1.type === 'insert' && op2.type === 'insert' && op1.position + op1.text.length === op2.position) {
      // Merge adjacent inserts
      return {
        ...op1,
        text: op1.text + op2.text
      };
    }

    if (op1.type === 'delete' && op2.type === 'delete' && op1.position === op2.position) {
      // Merge adjacent deletes
      return {
        ...op1,
        length: op1.length + op2.length
      };
    }

    // Cannot compose - return as sequence
    return {
      type: 'sequence',
      operations: [op1, op2]
    };
  }

  /**
   * Invert an operation (for undo functionality)
   */
  invertOperation(operation) {
    switch (operation.type) {
      case 'insert':
        return {
          type: 'delete',
          position: operation.position,
          length: operation.text.length
        };

      case 'delete':
        return {
          type: 'insert',
          position: operation.position,
          text: operation.deletedText || '' // Need to store deleted text
        };

      case 'replace':
        return {
          type: 'replace',
          position: operation.position,
          text: operation.originalText || '',
          originalText: operation.text,
          deleteLength: operation.text.length
        };

      default:
        return operation;
    }
  }

  /**
   * Validate operation structure
   */
  validateOperation(operation) {
    const requiredFields = ['type'];
    const validTypes = ['insert', 'delete', 'replace', 'noop'];

    if (!validTypes.includes(operation.type)) {
      throw new Error(`Invalid operation type: ${operation.type}`);
    }

    for (const field of requiredFields) {
      if (!(field in operation)) {
        throw new Error(`Missing required field: ${field}`);
      }
    }

    if (operation.type !== 'noop' && typeof operation.position !== 'number') {
      throw new Error('Position must be a number');
    }

    if (operation.position < 0) {
      throw new Error('Position cannot be negative');
    }

    if (operation.type === 'insert' && !operation.text) {
      throw new Error('Insert operations must have text');
    }

    if (operation.type === 'delete' && (!operation.length || operation.length <= 0)) {
      throw new Error('Delete operations must have positive length');
    }

    return true;
  }

  /**
   * Get operation statistics
   */
  getOperationStats(roomId) {
    const operations = this.operationHistory.get(roomId) || [];
    const stats = {
      total: operations.length,
      byType: {},
      byUser: {},
      recentActivity: 0
    };

    const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000);

    operations.forEach(op => {
      // Count by type
      stats.byType[op.type] = (stats.byType[op.type] || 0) + 1;
      
      // Count by user
      stats.byUser[op.userId] = (stats.byUser[op.userId] || 0) + 1;
      
      // Count recent activity
      if (new Date(op.timestamp) > oneHourAgo) {
        stats.recentActivity++;
      }
    });

    return stats;
  }

  /**
   * Clean up room data
   */
  cleanup(roomId) {
    this.operationHistory.delete(roomId);
    this.stateVectors.delete(roomId);
    this.pendingOps.delete(roomId);

    // Clear cache entries for this room
    for (const [key, value] of this.transformCache.entries()) {
      if (key.includes(roomId)) {
        this.transformCache.delete(key);
      }
    }

    logger.debug(`Operational transform cleanup completed for room ${roomId}`);
  }

  /**
   * Destroy operational transform engine
   */
  destroy() {
    this.operationHistory.clear();
    this.transformCache.clear();
    this.stateVectors.clear();
    this.pendingOps.clear();

    logger.info('Operational Transform Engine destroyed');
  }
}