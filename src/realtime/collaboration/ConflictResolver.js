/**
 * Conflict Resolution System
 * 
 * Handles annotation conflicts when multiple users edit the same content
 * Provides conflict detection, resolution strategies, and merge capabilities
 */

import { setupLogging } from '../utils/logger.js';
import { ValidationError, ConflictError } from '../utils/errors.js';

const logger = setupLogging('conflict-resolver');

export class ConflictResolver {
  constructor() {
    this.conflictHistory = new Map(); // Room ID -> Array of conflicts
    this.resolutionStrategies = this.initializeStrategies();
    this.conflictMetrics = new Map(); // Room ID -> Conflict metrics
    this.activeConflicts = new Map(); // Room ID -> Active conflicts
    this.resolutionCallbacks = new Map(); // Conflict ID -> Resolution callbacks
  }

  /**
   * Initialize conflict resolution strategies
   */
  initializeStrategies() {
    return {
      'last-write-wins': this.lastWriteWins.bind(this),
      'first-write-wins': this.firstWriteWins.bind(this),
      'merge-annotations': this.mergeAnnotations.bind(this),
      'user-priority': this.userPriorityResolution.bind(this),
      'confidence-based': this.confidenceBasedResolution.bind(this),
      'manual-resolution': this.manualResolution.bind(this),
      'semantic-merge': this.semanticMerge.bind(this),
      'voting-based': this.votingBasedResolution.bind(this)
    };
  }

  /**
   * Check for annotation conflicts
   */
  async checkAnnotationConflicts(annotation, roomId) {
    try {
      const conflicts = [];
      const existingAnnotations = await this.getRoomAnnotations(roomId);

      for (const existing of existingAnnotations) {
        if (existing.id === annotation.id) continue; // Skip self

        const conflict = this.detectConflict(annotation, existing);
        if (conflict) {
          conflicts.push({
            id: this.generateConflictId(),
            type: conflict.type,
            severity: conflict.severity,
            annotations: [annotation, existing],
            roomId: roomId,
            detectedAt: new Date().toISOString(),
            status: 'detected',
            metadata: conflict.metadata
          });
        }
      }

      // Store active conflicts
      if (conflicts.length > 0) {
        this.storeActiveConflicts(roomId, conflicts);
        this.updateConflictMetrics(roomId, conflicts);
      }

      logger.info(`Conflict check completed for annotation ${annotation.id}`, {
        roomId,
        conflicts: conflicts.length
      });

      return conflicts;

    } catch (error) {
      logger.error('Error checking annotation conflicts:', error);
      return [];
    }
  }

  /**
   * Detect specific conflict between two annotations
   */
  detectConflict(annotation1, annotation2) {
    const conflicts = [];

    // Position overlap conflict
    const positionConflict = this.checkPositionConflict(annotation1, annotation2);
    if (positionConflict) conflicts.push(positionConflict);

    // Content conflict (same text, different labels)
    const contentConflict = this.checkContentConflict(annotation1, annotation2);
    if (contentConflict) conflicts.push(contentConflict);

    // Label conflict (overlapping positions, conflicting labels)
    const labelConflict = this.checkLabelConflict(annotation1, annotation2);
    if (labelConflict) conflicts.push(labelConflict);

    // Temporal conflict (simultaneous edits)
    const temporalConflict = this.checkTemporalConflict(annotation1, annotation2);
    if (temporalConflict) conflicts.push(temporalConflict);

    if (conflicts.length === 0) return null;

    // Return the most severe conflict
    return conflicts.reduce((most, current) => 
      current.severity > most.severity ? current : most
    );
  }

  /**
   * Check for position overlap conflicts
   */
  checkPositionConflict(ann1, ann2) {
    // Check if annotations overlap in position
    const overlap = Math.max(0, Math.min(ann1.endOffset, ann2.endOffset) - Math.max(ann1.startOffset, ann2.startOffset));
    
    if (overlap > 0) {
      const overlapPercentage = overlap / Math.max(
        ann1.endOffset - ann1.startOffset,
        ann2.endOffset - ann2.startOffset
      );

      let severity = 'low';
      if (overlapPercentage > 0.8) severity = 'high';
      else if (overlapPercentage > 0.5) severity = 'medium';

      return {
        type: 'position-overlap',
        severity: severity,
        metadata: {
          overlapLength: overlap,
          overlapPercentage: overlapPercentage,
          positions: {
            annotation1: `${ann1.startOffset}-${ann1.endOffset}`,
            annotation2: `${ann2.startOffset}-${ann2.endOffset}`
          }
        }
      };
    }

    return null;
  }

  /**
   * Check for content conflicts
   */
  checkContentConflict(ann1, ann2) {
    // Same text content but different annotations
    if (ann1.text === ann2.text && ann1.startOffset === ann2.startOffset && ann1.endOffset === ann2.endOffset) {
      // Check if labels are different
      const labels1 = new Set(ann1.labels || []);
      const labels2 = new Set(ann2.labels || []);
      
      const hasLabelConflict = labels1.size !== labels2.size || 
        ![...labels1].every(label => labels2.has(label));

      if (hasLabelConflict) {
        return {
          type: 'content-conflict',
          severity: 'medium',
          metadata: {
            text: ann1.text,
            labels1: ann1.labels,
            labels2: ann2.labels,
            confidence1: ann1.confidence,
            confidence2: ann2.confidence
          }
        };
      }
    }

    return null;
  }

  /**
   * Check for label conflicts
   */
  checkLabelConflict(ann1, ann2) {
    // Check for conflicting labels on overlapping text
    const overlap = this.checkPositionConflict(ann1, ann2);
    if (!overlap) return null;

    const labels1 = new Set(ann1.labels || []);
    const labels2 = new Set(ann2.labels || []);

    // Define conflicting label pairs (domain-specific)
    const conflictingPairs = [
      ['positive', 'negative'],
      ['relevant', 'irrelevant'],
      ['important', 'unimportant'],
      ['correct', 'incorrect']
    ];

    for (const [label1, label2] of conflictingPairs) {
      if (labels1.has(label1) && labels2.has(label2)) {
        return {
          type: 'label-conflict',
          severity: 'high',
          metadata: {
            conflictingLabels: [label1, label2],
            annotation1Labels: ann1.labels,
            annotation2Labels: ann2.labels
          }
        };
      }
    }

    return null;
  }

  /**
   * Check for temporal conflicts (simultaneous edits)
   */
  checkTemporalConflict(ann1, ann2) {
    const time1 = new Date(ann1.updatedAt || ann1.createdAt);
    const time2 = new Date(ann2.updatedAt || ann2.createdAt);
    const timeDiff = Math.abs(time1 - time2);

    // Consider edits within 5 seconds as simultaneous
    if (timeDiff < 5000) {
      return {
        type: 'temporal-conflict',
        severity: 'medium',
        metadata: {
          timeDifference: timeDiff,
          annotation1Time: time1.toISOString(),
          annotation2Time: time2.toISOString()
        }
      };
    }

    return null;
  }

  /**
   * Resolve conflicts using specified strategy
   */
  async resolveConflict(conflictId, strategy = 'last-write-wins', options = {}) {
    try {
      const conflict = await this.getConflict(conflictId);
      if (!conflict) {
        throw new ValidationError(`Conflict ${conflictId} not found`);
      }

      if (!this.resolutionStrategies[strategy]) {
        throw new ValidationError(`Unknown resolution strategy: ${strategy}`);
      }

      const resolution = await this.resolutionStrategies[strategy](conflict, options);
      
      // Update conflict status
      conflict.status = 'resolved';
      conflict.resolvedAt = new Date().toISOString();
      conflict.resolution = resolution;
      conflict.strategy = strategy;

      // Store in history
      this.addToConflictHistory(conflict.roomId, conflict);

      // Remove from active conflicts
      this.removeActiveConflict(conflict.roomId, conflictId);

      // Execute resolution callbacks
      if (this.resolutionCallbacks.has(conflictId)) {
        const callback = this.resolutionCallbacks.get(conflictId);
        await callback(resolution);
        this.resolutionCallbacks.delete(conflictId);
      }

      logger.info(`Conflict resolved using ${strategy}`, {
        conflictId,
        roomId: conflict.roomId,
        resolution: resolution.action
      });

      return resolution;

    } catch (error) {
      logger.error(`Error resolving conflict ${conflictId}:`, error);
      throw error;
    }
  }

  /**
   * Last write wins resolution strategy
   */
  async lastWriteWins(conflict, options) {
    const annotations = conflict.annotations;
    const latest = annotations.reduce((latest, current) => {
      const latestTime = new Date(latest.updatedAt || latest.createdAt);
      const currentTime = new Date(current.updatedAt || current.createdAt);
      return currentTime > latestTime ? current : latest;
    });

    return {
      action: 'keep',
      winner: latest,
      discarded: annotations.filter(ann => ann.id !== latest.id),
      reason: 'Last modification wins',
      automatic: true
    };
  }

  /**
   * First write wins resolution strategy
   */
  async firstWriteWins(conflict, options) {
    const annotations = conflict.annotations;
    const earliest = annotations.reduce((earliest, current) => {
      const earliestTime = new Date(earliest.createdAt);
      const currentTime = new Date(current.createdAt);
      return currentTime < earliestTime ? current : earliest;
    });

    return {
      action: 'keep',
      winner: earliest,
      discarded: annotations.filter(ann => ann.id !== earliest.id),
      reason: 'First annotation wins',
      automatic: true
    };
  }

  /**
   * Merge annotations resolution strategy
   */
  async mergeAnnotations(conflict, options) {
    const annotations = conflict.annotations;
    
    // Create merged annotation
    const merged = {
      id: this.generateMergedId(annotations),
      textId: annotations[0].textId,
      startOffset: Math.min(...annotations.map(a => a.startOffset)),
      endOffset: Math.max(...annotations.map(a => a.endOffset)),
      text: this.getMergedText(annotations),
      labels: this.getMergedLabels(annotations),
      confidence: this.calculateMergedConfidence(annotations),
      notes: this.getMergedNotes(annotations),
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      createdBy: 'system',
      status: 'active',
      metadata: {
        mergedFrom: annotations.map(a => a.id),
        conflictId: conflict.id,
        mergeStrategy: 'automatic'
      }
    };

    return {
      action: 'merge',
      merged: merged,
      original: annotations,
      reason: 'Annotations merged automatically',
      automatic: true
    };
  }

  /**
   * User priority resolution strategy
   */
  async userPriorityResolution(conflict, options) {
    const { userPriorities = {} } = options;
    const annotations = conflict.annotations;

    let winner = annotations[0];
    let highestPriority = userPriorities[winner.createdBy] || 0;

    for (const annotation of annotations) {
      const priority = userPriorities[annotation.createdBy] || 0;
      if (priority > highestPriority) {
        winner = annotation;
        highestPriority = priority;
      }
    }

    return {
      action: 'keep',
      winner: winner,
      discarded: annotations.filter(ann => ann.id !== winner.id),
      reason: `User ${winner.createdBy} has higher priority (${highestPriority})`,
      automatic: true
    };
  }

  /**
   * Confidence-based resolution strategy
   */
  async confidenceBasedResolution(conflict, options) {
    const annotations = conflict.annotations;
    const winner = annotations.reduce((highest, current) => {
      const highestConf = highest.confidence || 0;
      const currentConf = current.confidence || 0;
      return currentConf > highestConf ? current : highest;
    });

    return {
      action: 'keep',
      winner: winner,
      discarded: annotations.filter(ann => ann.id !== winner.id),
      reason: `Highest confidence annotation (${winner.confidence})`,
      automatic: true
    };
  }

  /**
   * Manual resolution strategy (requires user input)
   */
  async manualResolution(conflict, options) {
    return {
      action: 'manual',
      conflict: conflict,
      reason: 'Requires manual user intervention',
      automatic: false,
      requiresInput: true
    };
  }

  /**
   * Semantic merge strategy (AI-powered)
   */
  async semanticMerge(conflict, options) {
    // Placeholder for AI-powered semantic merging
    // In a real implementation, this would use NLP models
    
    const annotations = conflict.annotations;
    const merged = await this.performSemanticMerge(annotations);

    return {
      action: 'semantic-merge',
      merged: merged,
      original: annotations,
      reason: 'Semantic analysis determined optimal merge',
      automatic: true,
      confidence: merged.semanticConfidence
    };
  }

  /**
   * Voting-based resolution strategy
   */
  async votingBasedResolution(conflict, options) {
    const { votes = {} } = options;
    const annotations = conflict.annotations;

    const voteCount = {};
    annotations.forEach(ann => {
      voteCount[ann.id] = 0;
    });

    // Count votes
    Object.values(votes).forEach(vote => {
      if (voteCount.hasOwnProperty(vote.annotationId)) {
        voteCount[vote.annotationId]++;
      }
    });

    // Find winner
    const winnerId = Object.keys(voteCount).reduce((a, b) => 
      voteCount[a] > voteCount[b] ? a : b
    );
    
    const winner = annotations.find(ann => ann.id === winnerId);

    return {
      action: 'keep',
      winner: winner,
      discarded: annotations.filter(ann => ann.id !== winner.id),
      reason: `Community vote winner (${voteCount[winnerId]} votes)`,
      automatic: false,
      voteCount: voteCount
    };
  }

  /**
   * Helper methods for merging
   */
  getMergedText(annotations) {
    // Return the longest text span
    return annotations.reduce((longest, current) => 
      current.text.length > longest.text.length ? current : longest
    ).text;
  }

  getMergedLabels(annotations) {
    const allLabels = new Set();
    annotations.forEach(ann => {
      (ann.labels || []).forEach(label => allLabels.add(label));
    });
    return Array.from(allLabels);
  }

  calculateMergedConfidence(annotations) {
    const confidences = annotations.map(ann => ann.confidence || 0);
    return confidences.reduce((sum, conf) => sum + conf, 0) / confidences.length;
  }

  getMergedNotes(annotations) {
    const notes = annotations
      .map(ann => ann.notes)
      .filter(note => note && note.trim())
      .join(' | ');
    return notes || '';
  }

  /**
   * Perform semantic merge using AI (placeholder)
   */
  async performSemanticMerge(annotations) {
    // This would integrate with NLP models in a real implementation
    // For now, return a simple merge
    return {
      ...this.mergeAnnotations({ annotations }, {}),
      semanticConfidence: 0.8
    };
  }

  /**
   * Utility methods
   */
  generateConflictId() {
    return `conflict_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
  }

  generateMergedId(annotations) {
    return `merged_${Date.now()}_${annotations.map(a => a.id.slice(-4)).join('')}`;
  }

  async getRoomAnnotations(roomId) {
    // This would fetch from the annotation manager
    // Placeholder implementation
    return [];
  }

  storeActiveConflicts(roomId, conflicts) {
    if (!this.activeConflicts.has(roomId)) {
      this.activeConflicts.set(roomId, new Map());
    }
    
    const roomConflicts = this.activeConflicts.get(roomId);
    conflicts.forEach(conflict => {
      roomConflicts.set(conflict.id, conflict);
    });
  }

  removeActiveConflict(roomId, conflictId) {
    const roomConflicts = this.activeConflicts.get(roomId);
    if (roomConflicts) {
      roomConflicts.delete(conflictId);
    }
  }

  async getConflict(conflictId) {
    for (const roomConflicts of this.activeConflicts.values()) {
      if (roomConflicts.has(conflictId)) {
        return roomConflicts.get(conflictId);
      }
    }
    return null;
  }

  addToConflictHistory(roomId, conflict) {
    if (!this.conflictHistory.has(roomId)) {
      this.conflictHistory.set(roomId, []);
    }
    
    const history = this.conflictHistory.get(roomId);
    history.push(conflict);
    
    // Limit history size
    if (history.length > 1000) {
      history.splice(0, history.length - 1000);
    }
  }

  updateConflictMetrics(roomId, conflicts) {
    if (!this.conflictMetrics.has(roomId)) {
      this.conflictMetrics.set(roomId, {
        total: 0,
        byType: {},
        bySeverity: {},
        resolved: 0,
        pending: 0
      });
    }

    const metrics = this.conflictMetrics.get(roomId);
    
    conflicts.forEach(conflict => {
      metrics.total++;
      metrics.byType[conflict.type] = (metrics.byType[conflict.type] || 0) + 1;
      metrics.bySeverity[conflict.severity] = (metrics.bySeverity[conflict.severity] || 0) + 1;
      metrics.pending++;
    });
  }

  /**
   * Get conflict statistics
   */
  getConflictStats(roomId) {
    const metrics = this.conflictMetrics.get(roomId) || {
      total: 0,
      byType: {},
      bySeverity: {},
      resolved: 0,
      pending: 0
    };

    const activeConflicts = this.activeConflicts.get(roomId) || new Map();
    
    return {
      ...metrics,
      active: activeConflicts.size,
      history: (this.conflictHistory.get(roomId) || []).length,
      timestamp: new Date().toISOString()
    };
  }

  /**
   * Clean up room data
   */
  cleanup(roomId) {
    this.activeConflicts.delete(roomId);
    this.conflictMetrics.delete(roomId);
    
    // Keep history for analytics but limit size
    const history = this.conflictHistory.get(roomId) || [];
    if (history.length > 100) {
      this.conflictHistory.set(roomId, history.slice(-100));
    }

    logger.debug(`Conflict resolver cleanup completed for room ${roomId}`);
  }

  /**
   * Destroy conflict resolver
   */
  destroy() {
    this.conflictHistory.clear();
    this.conflictMetrics.clear();
    this.activeConflicts.clear();
    this.resolutionCallbacks.clear();

    logger.info('Conflict Resolver destroyed');
  }
}