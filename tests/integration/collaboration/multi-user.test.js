/**
 * Integration Tests - Multi-User Collaboration
 * Tests for real-time collaboration, permissions, and conflict resolution
 */

import jwt from 'jsonwebtoken';
import { testUsers, testProjects, testAnnotations } from '../../fixtures/test-data.js';

// Mock WebSocket implementation for real-time features
class MockWebSocket {
  constructor(url) {
    this.url = url;
    this.readyState = MockWebSocket.CONNECTING;
    this.listeners = {};
    this.messageQueue = [];
    
    // Simulate connection
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN;
      this.trigger('open');
    }, 100);
  }

  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  addEventListener(event, callback) {
    if (!this.listeners[event]) {
      this.listeners[event] = [];
    }
    this.listeners[event].push(callback);
  }

  send(data) {
    if (this.readyState === MockWebSocket.OPEN) {
      // Simulate server processing and broadcast
      setTimeout(() => {
        const message = JSON.parse(data);
        this.simulateServerBroadcast(message);
      }, 10);
    }
  }

  simulateServerBroadcast(message) {
    // Simulate broadcasting to other connected clients
    const broadcastMessage = {
      type: 'broadcast',
      data: message,
      timestamp: new Date().toISOString(),
      source: 'server'
    };

    // Trigger message event
    this.trigger('message', { data: JSON.stringify(broadcastMessage) });
  }

  trigger(event, data = null) {
    if (this.listeners[event]) {
      this.listeners[event].forEach(callback => callback(data));
    }
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
    this.trigger('close');
  }
}

// Mock real-time collaboration service
class MockCollaborationService {
  constructor() {
    this.connections = new Map();
    this.documentSessions = new Map();
    this.annotationLocks = new Map();
  }

  connect(userId, documentId) {
    const connectionId = `${userId}-${documentId}-${Date.now()}`;
    const ws = new MockWebSocket(`ws://localhost:3001/collab/${documentId}`);
    
    this.connections.set(connectionId, {
      userId,
      documentId,
      ws,
      lastActivity: Date.now()
    });

    // Add user to document session
    if (!this.documentSessions.has(documentId)) {
      this.documentSessions.set(documentId, new Set());
    }
    this.documentSessions.get(documentId).add(userId);

    return { connectionId, ws };
  }

  disconnect(connectionId) {
    const connection = this.connections.get(connectionId);
    if (connection) {
      const { userId, documentId, ws } = connection;
      
      // Remove from document session
      const session = this.documentSessions.get(documentId);
      if (session) {
        session.delete(userId);
      }

      // Release any locks held by this user
      for (const [annotationId, lockInfo] of this.annotationLocks) {
        if (lockInfo.userId === userId) {
          this.annotationLocks.delete(annotationId);
        }
      }

      ws.close();
      this.connections.delete(connectionId);
    }
  }

  broadcastToDocument(documentId, message, excludeUserId = null) {
    const session = this.documentSessions.get(documentId);
    if (!session) return;

    for (const [connectionId, connection] of this.connections) {
      if (connection.documentId === documentId && 
          connection.userId !== excludeUserId) {
        connection.ws.send(JSON.stringify(message));
      }
    }
  }

  lockAnnotation(annotationId, userId, documentId) {
    if (this.annotationLocks.has(annotationId)) {
      const lockInfo = this.annotationLocks.get(annotationId);
      if (lockInfo.userId !== userId) {
        return {
          success: false,
          error: 'Annotation is locked by another user',
          lockedBy: lockInfo.userId,
          lockedAt: lockInfo.timestamp
        };
      }
    }

    this.annotationLocks.set(annotationId, {
      userId,
      timestamp: Date.now(),
      documentId
    });

    // Broadcast lock to other users
    this.broadcastToDocument(documentId, {
      type: 'annotation_locked',
      annotationId,
      userId,
      timestamp: new Date().toISOString()
    }, userId);

    return { success: true };
  }

  unlockAnnotation(annotationId, userId, documentId) {
    const lockInfo = this.annotationLocks.get(annotationId);
    if (!lockInfo || lockInfo.userId !== userId) {
      return { success: false, error: 'Cannot unlock annotation' };
    }

    this.annotationLocks.delete(annotationId);

    // Broadcast unlock to other users
    this.broadcastToDocument(documentId, {
      type: 'annotation_unlocked',
      annotationId,
      userId,
      timestamp: new Date().toISOString()
    }, userId);

    return { success: true };
  }

  getActiveUsers(documentId) {
    const session = this.documentSessions.get(documentId);
    return session ? Array.from(session) : [];
  }

  getAnnotationLocks(documentId) {
    const locks = {};
    for (const [annotationId, lockInfo] of this.annotationLocks) {
      if (lockInfo.documentId === documentId) {
        locks[annotationId] = {
          userId: lockInfo.userId,
          timestamp: lockInfo.timestamp
        };
      }
    }
    return locks;
  }
}

// Mock conflict resolution system
class MockConflictResolver {
  constructor() {
    this.pendingConflicts = new Map();
  }

  detectConflict(annotationId, changes) {
    // Simulate conflict detection based on version or timestamp
    const hasConflict = Math.random() < 0.1; // 10% chance of conflict for testing
    
    if (hasConflict) {
      const conflictId = `conflict-${Date.now()}-${Math.random()}`;
      this.pendingConflicts.set(conflictId, {
        annotationId,
        changes,
        timestamp: Date.now(),
        status: 'pending'
      });
      return { hasConflict: true, conflictId };
    }

    return { hasConflict: false };
  }

  resolveConflict(conflictId, resolution) {
    const conflict = this.pendingConflicts.get(conflictId);
    if (!conflict) {
      return { success: false, error: 'Conflict not found' };
    }

    conflict.status = 'resolved';
    conflict.resolution = resolution;
    conflict.resolvedAt = Date.now();

    return { 
      success: true, 
      resolvedAnnotation: this.applyResolution(conflict, resolution) 
    };
  }

  applyResolution(conflict, resolution) {
    // Apply resolution strategy (last-write-wins, merge, manual)
    switch (resolution.strategy) {
      case 'last-write-wins':
        return resolution.changes;
      case 'merge':
        return this.mergeChanges(conflict.changes, resolution.changes);
      case 'manual':
        return resolution.manualChanges;
      default:
        return conflict.changes;
    }
  }

  mergeChanges(original, incoming) {
    // Simple merge strategy for testing
    return {
      ...original,
      ...incoming,
      content: `${original.content} [MERGED] ${incoming.content}`,
      tags: [...(original.tags || []), ...(incoming.tags || [])]
    };
  }
}

describe('Multi-User Collaboration Integration Tests', () => {
  let collaborationService;
  let conflictResolver;
  let studentToken;
  let instructorToken;
  let researcherToken;

  beforeEach(() => {
    collaborationService = new MockCollaborationService();
    conflictResolver = new MockConflictResolver();

    // Generate test tokens
    studentToken = jwt.sign(
      { id: 'student1', email: testUsers.student.email, role: 'student' },
      process.env.JWT_SECRET,
      { expiresIn: '1h' }
    );

    instructorToken = jwt.sign(
      { id: 'instructor1', email: testUsers.instructor.email, role: 'instructor' },
      process.env.JWT_SECRET,
      { expiresIn: '1h' }
    );

    researcherToken = jwt.sign(
      { id: 'researcher1', email: testUsers.researcher.email, role: 'researcher' },
      process.env.JWT_SECRET,
      { expiresIn: '1h' }
    );
  });

  afterEach(() => {
    // Clean up connections
    for (const [connectionId] of collaborationService.connections) {
      collaborationService.disconnect(connectionId);
    }
  });

  describe('Real-time Connection Management', () => {
    it('should establish WebSocket connection for document collaboration', async () => {
      const { connectionId, ws } = collaborationService.connect('student1', 'doc1');

      return new Promise((resolve) => {
        ws.addEventListener('open', () => {
          expect(ws.readyState).toBe(MockWebSocket.OPEN);
          expect(connectionId).toBeDefined();
          resolve();
        });
      });
    });

    it('should track active users in document session', () => {
      collaborationService.connect('student1', 'doc1');
      collaborationService.connect('instructor1', 'doc1');
      collaborationService.connect('researcher1', 'doc2'); // Different document

      const doc1Users = collaborationService.getActiveUsers('doc1');
      const doc2Users = collaborationService.getActiveUsers('doc2');

      expect(doc1Users).toContain('student1');
      expect(doc1Users).toContain('instructor1');
      expect(doc1Users).not.toContain('researcher1');
      expect(doc2Users).toContain('researcher1');
    });

    it('should handle user disconnection properly', () => {
      const { connectionId: conn1 } = collaborationService.connect('student1', 'doc1');
      const { connectionId: conn2 } = collaborationService.connect('instructor1', 'doc1');

      let doc1Users = collaborationService.getActiveUsers('doc1');
      expect(doc1Users).toHaveLength(2);

      collaborationService.disconnect(conn1);
      doc1Users = collaborationService.getActiveUsers('doc1');
      expect(doc1Users).toHaveLength(1);
      expect(doc1Users).toContain('instructor1');
      expect(doc1Users).not.toContain('student1');
    });
  });

  describe('Real-time Annotation Broadcasting', () => {
    it('should broadcast annotation creation to other users', (done) => {
      const { ws: studentWs } = collaborationService.connect('student1', 'doc1');
      const { ws: instructorWs } = collaborationService.connect('instructor1', 'doc1');

      let messagesReceived = 0;
      const expectedMessages = 1;

      instructorWs.addEventListener('message', (event) => {
        const message = JSON.parse(event.data);
        
        if (message.type === 'broadcast' && 
            message.data.type === 'annotation_created') {
          expect(message.data.annotation.text).toBe('New collaborative annotation');
          expect(message.data.userId).toBe('student1');
          messagesReceived++;

          if (messagesReceived === expectedMessages) {
            done();
          }
        }
      });

      // Student creates annotation
      setTimeout(() => {
        studentWs.send(JSON.stringify({
          type: 'annotation_created',
          annotation: {
            id: 'new-annotation-1',
            text: 'New collaborative annotation',
            content: 'This annotation was created in real-time',
            startPosition: 100,
            endPosition: 130,
            type: 'highlight'
          },
          userId: 'student1',
          documentId: 'doc1'
        }));
      }, 200);
    });

    it('should broadcast annotation updates to collaborators', (done) => {
      const { ws: studentWs } = collaborationService.connect('student1', 'doc1');
      const { ws: instructorWs } = collaborationService.connect('instructor1', 'doc1');

      instructorWs.addEventListener('message', (event) => {
        const message = JSON.parse(event.data);
        
        if (message.type === 'broadcast' && 
            message.data.type === 'annotation_updated') {
          expect(message.data.changes.content).toBe('Updated content by student');
          expect(message.data.annotationId).toBe('annotation-1');
          done();
        }
      });

      setTimeout(() => {
        studentWs.send(JSON.stringify({
          type: 'annotation_updated',
          annotationId: 'annotation-1',
          changes: {
            content: 'Updated content by student',
            tags: ['updated', 'collaborative']
          },
          userId: 'student1',
          documentId: 'doc1'
        }));
      }, 200);
    });

    it('should not broadcast to sender', (done) => {
      const { ws: studentWs } = collaborationService.connect('student1', 'doc1');
      const { ws: instructorWs } = collaborationService.connect('instructor1', 'doc1');

      let studentReceived = false;
      let instructorReceived = false;

      studentWs.addEventListener('message', (event) => {
        const message = JSON.parse(event.data);
        if (message.type === 'broadcast') {
          studentReceived = true;
        }
      });

      instructorWs.addEventListener('message', (event) => {
        const message = JSON.parse(event.data);
        if (message.type === 'broadcast') {
          instructorReceived = true;
        }
      });

      setTimeout(() => {
        studentWs.send(JSON.stringify({
          type: 'annotation_created',
          annotation: { id: 'test', text: 'test' },
          userId: 'student1'
        }));
      }, 100);

      setTimeout(() => {
        expect(studentReceived).toBe(false); // Student should not receive own broadcast
        expect(instructorReceived).toBe(true); // Instructor should receive it
        done();
      }, 300);
    });
  });

  describe('Annotation Locking Mechanism', () => {
    it('should lock annotation for editing', () => {
      collaborationService.connect('student1', 'doc1');
      
      const lockResult = collaborationService.lockAnnotation('annotation-1', 'student1', 'doc1');
      
      expect(lockResult.success).toBe(true);
      
      const locks = collaborationService.getAnnotationLocks('doc1');
      expect(locks['annotation-1']).toBeDefined();
      expect(locks['annotation-1'].userId).toBe('student1');
    });

    it('should prevent double locking by different users', () => {
      collaborationService.connect('student1', 'doc1');
      collaborationService.connect('instructor1', 'doc1');
      
      const lock1 = collaborationService.lockAnnotation('annotation-1', 'student1', 'doc1');
      const lock2 = collaborationService.lockAnnotation('annotation-1', 'instructor1', 'doc1');
      
      expect(lock1.success).toBe(true);
      expect(lock2.success).toBe(false);
      expect(lock2.error).toContain('locked by another user');
      expect(lock2.lockedBy).toBe('student1');
    });

    it('should allow same user to re-lock annotation', () => {
      collaborationService.connect('student1', 'doc1');
      
      const lock1 = collaborationService.lockAnnotation('annotation-1', 'student1', 'doc1');
      const lock2 = collaborationService.lockAnnotation('annotation-1', 'student1', 'doc1');
      
      expect(lock1.success).toBe(true);
      expect(lock2.success).toBe(true);
    });

    it('should release lock properly', () => {
      collaborationService.connect('student1', 'doc1');
      
      collaborationService.lockAnnotation('annotation-1', 'student1', 'doc1');
      const unlockResult = collaborationService.unlockAnnotation('annotation-1', 'student1', 'doc1');
      
      expect(unlockResult.success).toBe(true);
      
      const locks = collaborationService.getAnnotationLocks('doc1');
      expect(locks['annotation-1']).toBeUndefined();
    });

    it('should auto-release locks on user disconnect', () => {
      const { connectionId } = collaborationService.connect('student1', 'doc1');
      
      collaborationService.lockAnnotation('annotation-1', 'student1', 'doc1');
      collaborationService.lockAnnotation('annotation-2', 'student1', 'doc1');
      
      let locks = collaborationService.getAnnotationLocks('doc1');
      expect(Object.keys(locks)).toHaveLength(2);
      
      collaborationService.disconnect(connectionId);
      
      locks = collaborationService.getAnnotationLocks('doc1');
      expect(Object.keys(locks)).toHaveLength(0);
    });
  });

  describe('Conflict Resolution', () => {
    it('should detect annotation conflicts', () => {
      const changes = {
        content: 'Conflicting change',
        tags: ['conflict']
      };
      
      const result = conflictResolver.detectConflict('annotation-1', changes);
      
      // Since we have 10% random conflict chance, we test both cases
      if (result.hasConflict) {
        expect(result.conflictId).toBeDefined();
        expect(conflictResolver.pendingConflicts.has(result.conflictId)).toBe(true);
      } else {
        expect(result.conflictId).toBeUndefined();
      }
    });

    it('should resolve conflicts with last-write-wins strategy', () => {
      const changes = {
        content: 'Original change',
        tags: ['original']
      };
      
      // Force a conflict
      const conflictId = `test-conflict-${Date.now()}`;
      conflictResolver.pendingConflicts.set(conflictId, {
        annotationId: 'annotation-1',
        changes,
        timestamp: Date.now(),
        status: 'pending'
      });
      
      const resolution = {
        strategy: 'last-write-wins',
        changes: {
          content: 'Latest change wins',
          tags: ['latest']
        }
      };
      
      const result = conflictResolver.resolveConflict(conflictId, resolution);
      
      expect(result.success).toBe(true);
      expect(result.resolvedAnnotation.content).toBe('Latest change wins');
      expect(result.resolvedAnnotation.tags).toEqual(['latest']);
    });

    it('should resolve conflicts with merge strategy', () => {
      const originalChanges = {
        content: 'Original content',
        tags: ['original']
      };
      
      const conflictId = `test-conflict-${Date.now()}`;
      conflictResolver.pendingConflicts.set(conflictId, {
        annotationId: 'annotation-1',
        changes: originalChanges,
        timestamp: Date.now(),
        status: 'pending'
      });
      
      const resolution = {
        strategy: 'merge',
        changes: {
          content: 'Incoming content',
          tags: ['incoming']
        }
      };
      
      const result = conflictResolver.resolveConflict(conflictId, resolution);
      
      expect(result.success).toBe(true);
      expect(result.resolvedAnnotation.content).toContain('Original content [MERGED] Incoming content');
      expect(result.resolvedAnnotation.tags).toEqual(['original', 'incoming']);
    });
  });

  describe('Permission-based Collaboration', () => {
    it('should enforce role-based annotation permissions', () => {
      const project = {
        ...testProjects.classProject,
        permissions: {
          student: ['read', 'write'],
          instructor: ['read', 'write', 'moderate'],
          admin: ['read', 'write', 'moderate', 'delete']
        }
      };

      // Helper function to check permissions
      const hasPermission = (userRole, permission) => {
        const userPermissions = project.permissions[userRole] || [];
        return userPermissions.includes(permission);
      };

      expect(hasPermission('student', 'read')).toBe(true);
      expect(hasPermission('student', 'write')).toBe(true);
      expect(hasPermission('student', 'moderate')).toBe(false);
      expect(hasPermission('student', 'delete')).toBe(false);

      expect(hasPermission('instructor', 'moderate')).toBe(true);
      expect(hasPermission('instructor', 'delete')).toBe(false);

      expect(hasPermission('admin', 'delete')).toBe(true);
    });

    it('should restrict editing of others annotations based on role', () => {
      const annotation = {
        id: 'annotation-1',
        userId: 'student1',
        ...testAnnotations.highlight
      };

      // Helper function to check edit permissions
      const canEdit = (currentUserId, currentUserRole, annotation) => {
        if (annotation.userId === currentUserId) return true;
        if (['instructor', 'admin'].includes(currentUserRole)) return true;
        return false;
      };

      expect(canEdit('student1', 'student', annotation)).toBe(true); // Own annotation
      expect(canEdit('student2', 'student', annotation)).toBe(false); // Others annotation
      expect(canEdit('instructor1', 'instructor', annotation)).toBe(true); // Instructor can edit
      expect(canEdit('admin1', 'admin', annotation)).toBe(true); // Admin can edit
    });

    it('should control annotation visibility based on project settings', () => {
      const privateProject = {
        ...testProjects.researchProject,
        settings: {
          ...testProjects.researchProject.settings,
          allowPublicAnnotations: false,
          requireModeration: true
        }
      };

      const publicProject = {
        ...testProjects.classProject,
        settings: {
          ...testProjects.classProject.settings,
          allowPublicAnnotations: true,
          requireModeration: false
        }
      };

      // Helper function to check visibility
      const isVisible = (annotation, project, viewerRole) => {
        if (!project.settings.allowPublicAnnotations && annotation.isPublic) {
          return false;
        }
        if (project.settings.requireModeration && !annotation.moderated && viewerRole === 'student') {
          return false;
        }
        return true;
      };

      const publicAnnotation = { ...testAnnotations.highlight, isPublic: true };
      const privateAnnotation = { ...testAnnotations.comment, isPublic: false };
      const unmoderatedAnnotation = { ...testAnnotations.question, moderated: false };

      expect(isVisible(publicAnnotation, publicProject, 'student')).toBe(true);
      expect(isVisible(publicAnnotation, privateProject, 'student')).toBe(false);
      expect(isVisible(privateAnnotation, privateProject, 'student')).toBe(true);
      expect(isVisible(unmoderatedAnnotation, privateProject, 'student')).toBe(false);
      expect(isVisible(unmoderatedAnnotation, privateProject, 'instructor')).toBe(true);
    });
  });

  describe('Collaborative Annotation Workflows', () => {
    it('should support annotation threading and replies', () => {
      const parentAnnotation = {
        id: 'parent-1',
        ...testAnnotations.question,
        replies: []
      };

      const reply1 = {
        id: 'reply-1',
        content: 'This is a good question. Let me elaborate...',
        userId: 'instructor1',
        parentId: 'parent-1',
        timestamp: new Date().toISOString()
      };

      const reply2 = {
        id: 'reply-2',
        content: 'Thank you for the clarification!',
        userId: 'student1',
        parentId: 'parent-1',
        timestamp: new Date().toISOString()
      };

      parentAnnotation.replies.push(reply1, reply2);

      expect(parentAnnotation.replies).toHaveLength(2);
      expect(parentAnnotation.replies[0].userId).toBe('instructor1');
      expect(parentAnnotation.replies[1].userId).toBe('student1');
      expect(parentAnnotation.replies.every(r => r.parentId === 'parent-1')).toBe(true);
    });

    it('should handle annotation voting and rating', () => {
      const annotation = {
        id: 'votable-1',
        ...testAnnotations.suggestion,
        votes: {
          up: [],
          down: [],
          total: 0
        }
      };

      // Helper functions for voting
      const upvote = (annotation, userId) => {
        if (!annotation.votes.up.includes(userId)) {
          annotation.votes.up.push(userId);
          annotation.votes.down = annotation.votes.down.filter(id => id !== userId);
        }
        annotation.votes.total = annotation.votes.up.length - annotation.votes.down.length;
      };

      const downvote = (annotation, userId) => {
        if (!annotation.votes.down.includes(userId)) {
          annotation.votes.down.push(userId);
          annotation.votes.up = annotation.votes.up.filter(id => id !== userId);
        }
        annotation.votes.total = annotation.votes.up.length - annotation.votes.down.length;
      };

      upvote(annotation, 'student1');
      upvote(annotation, 'student2');
      downvote(annotation, 'student3');

      expect(annotation.votes.up).toHaveLength(2);
      expect(annotation.votes.down).toHaveLength(1);
      expect(annotation.votes.total).toBe(1);

      // Test vote change
      downvote(annotation, 'student1');
      expect(annotation.votes.up).toHaveLength(1);
      expect(annotation.votes.down).toHaveLength(2);
      expect(annotation.votes.total).toBe(-1);
    });

    it('should support collaborative tagging', () => {
      const annotation = {
        id: 'collaborative-tags',
        ...testAnnotations.highlight,
        tags: ['initial'],
        collaborativeTags: {
          'student1': ['important', 'review'],
          'instructor1': ['concept', 'exam-material'],
          'student2': ['difficult', 'review']
        }
      };

      // Helper to get all unique tags
      const getAllTags = (annotation) => {
        const allTags = [...annotation.tags];
        Object.values(annotation.collaborativeTags).forEach(userTags => {
          allTags.push(...userTags);
        });
        return [...new Set(allTags)];
      };

      // Helper to get tag frequency
      const getTagFrequency = (annotation) => {
        const frequency = {};
        const allTags = getAllTags(annotation);
        
        allTags.forEach(tag => {
          frequency[tag] = 1; // Base tags count as 1
          Object.values(annotation.collaborativeTags).forEach(userTags => {
            if (userTags.includes(tag)) frequency[tag]++;
          });
        });

        return frequency;
      };

      const allTags = getAllTags(annotation);
      const frequency = getTagFrequency(annotation);

      expect(allTags).toContain('important');
      expect(allTags).toContain('concept');
      expect(frequency['review']).toBe(3); // Used by 2 users + base
      expect(frequency['important']).toBe(2); // Used by 1 user + base
    });
  });

  describe('Performance under Collaborative Load', () => {
    it('should handle multiple simultaneous users', async () => {
      const numUsers = 10;
      const connections = [];

      // Connect multiple users
      for (let i = 0; i < numUsers; i++) {
        const { connectionId, ws } = collaborationService.connect(`user${i}`, 'doc1');
        connections.push({ connectionId, ws, userId: `user${i}` });
      }

      // Wait for all connections
      await Promise.all(connections.map(({ ws }) => 
        new Promise(resolve => {
          if (ws.readyState === MockWebSocket.OPEN) {
            resolve();
          } else {
            ws.addEventListener('open', resolve);
          }
        })
      ));

      const activeUsers = collaborationService.getActiveUsers('doc1');
      expect(activeUsers).toHaveLength(numUsers);

      // Test concurrent annotation creation
      const annotationPromises = connections.map(({ ws, userId }, index) => {
        return new Promise(resolve => {
          ws.send(JSON.stringify({
            type: 'annotation_created',
            annotation: {
              id: `concurrent-${index}`,
              text: `Concurrent annotation ${index}`,
              content: `Content from ${userId}`,
              startPosition: index * 10,
              endPosition: (index * 10) + 5,
              type: 'highlight'
            },
            userId,
            documentId: 'doc1'
          }));
          resolve();
        });
      });

      await Promise.all(annotationPromises);

      // Cleanup
      connections.forEach(({ connectionId }) => {
        collaborationService.disconnect(connectionId);
      });
    });

    it('should maintain performance with high message frequency', async () => {
      const { ws: senderWs } = collaborationService.connect('sender', 'doc1');
      const receivers = [];

      // Connect multiple receivers
      for (let i = 0; i < 5; i++) {
        const { ws } = collaborationService.connect(`receiver${i}`, 'doc1');
        receivers.push(ws);
      }

      const messagesSent = 100;
      const messagesReceived = [];

      // Set up message listeners
      receivers.forEach((ws, index) => {
        ws.addEventListener('message', (event) => {
          messagesReceived.push({
            receiver: index,
            timestamp: Date.now(),
            message: JSON.parse(event.data)
          });
        });
      });

      const startTime = Date.now();

      // Send messages rapidly
      for (let i = 0; i < messagesSent; i++) {
        senderWs.send(JSON.stringify({
          type: 'rapid_update',
          sequenceId: i,
          timestamp: Date.now()
        }));
        
        // Small delay to simulate realistic timing
        await new Promise(resolve => setTimeout(resolve, 10));
      }

      // Wait for message processing
      await new Promise(resolve => setTimeout(resolve, 1000));

      const endTime = Date.now();
      const duration = endTime - startTime;

      // Performance assertions
      expect(duration).toBeLessThan(5000); // Under 5 seconds
      expect(messagesReceived.length).toBeGreaterThan(messagesSent * 3); // Multiple receivers
    });
  });
});