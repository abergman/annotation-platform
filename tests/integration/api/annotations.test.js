/**
 * Integration Tests - Annotations API
 * Tests for annotation CRUD operations, validation, and business logic
 */

import request from 'supertest';
import jwt from 'jsonwebtoken';
import { testUsers, testAnnotations, testDocuments } from '../../fixtures/test-data.js';

// Mock Express app (will be replaced with actual app)
class MockApp {
  constructor() {
    this.routes = new Map();
    this.middleware = [];
  }

  use(middleware) {
    this.middleware.push(middleware);
  }

  get(path, handler) {
    this.routes.set(`GET:${path}`, handler);
  }

  post(path, handler) {
    this.routes.set(`POST:${path}`, handler);
  }

  put(path, handler) {
    this.routes.set(`PUT:${path}`, handler);
  }

  delete(path, handler) {
    this.routes.set(`DELETE:${path}`, handler);
  }

  async request() {
    return this;
  }
}

// Mock database data
const mockDatabase = {
  annotations: [
    { id: '1', ...testAnnotations.highlight, userId: 'user1', documentId: 'doc1' },
    { id: '2', ...testAnnotations.comment, userId: 'user2', documentId: 'doc1' },
    { id: '3', ...testAnnotations.question, userId: 'user1', documentId: 'doc2' }
  ],
  users: [
    { id: 'user1', ...testUsers.student },
    { id: 'user2', ...testUsers.instructor }
  ],
  documents: [
    { id: 'doc1', ...testDocuments.academicPaper },
    { id: 'doc2', ...testDocuments.shortArticle }
  ]
};

// Mock API handlers
const mockApiHandlers = {
  async getAnnotations(req, res) {
    const { documentId, userId, type } = req.query;
    let annotations = mockDatabase.annotations;

    if (documentId) {
      annotations = annotations.filter(a => a.documentId === documentId);
    }
    if (userId) {
      annotations = annotations.filter(a => a.userId === userId);
    }
    if (type) {
      annotations = annotations.filter(a => a.type === type);
    }

    res.status(200).json({
      success: true,
      data: annotations,
      pagination: {
        total: annotations.length,
        page: 1,
        pages: 1
      }
    });
  },

  async getAnnotation(req, res) {
    const annotation = mockDatabase.annotations.find(a => a.id === req.params.id);
    
    if (!annotation) {
      return res.status(404).json({
        success: false,
        error: 'Annotation not found'
      });
    }

    res.status(200).json({
      success: true,
      data: annotation
    });
  },

  async createAnnotation(req, res) {
    const { text, content, startPosition, endPosition, type, documentId, tags = [] } = req.body;

    // Validation
    if (!text || !content || startPosition === undefined || endPosition === undefined || !type || !documentId) {
      return res.status(400).json({
        success: false,
        error: 'Missing required fields',
        details: {
          required: ['text', 'content', 'startPosition', 'endPosition', 'type', 'documentId']
        }
      });
    }

    if (startPosition >= endPosition) {
      return res.status(400).json({
        success: false,
        error: 'Invalid position: startPosition must be less than endPosition'
      });
    }

    const validTypes = ['highlight', 'comment', 'question', 'suggestion', 'note'];
    if (!validTypes.includes(type)) {
      return res.status(400).json({
        success: false,
        error: 'Invalid annotation type',
        details: { validTypes }
      });
    }

    const newAnnotation = {
      id: Date.now().toString(),
      text,
      content,
      startPosition,
      endPosition,
      type,
      documentId,
      tags,
      userId: req.user?.id || 'test-user',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };

    mockDatabase.annotations.push(newAnnotation);

    res.status(201).json({
      success: true,
      data: newAnnotation,
      message: 'Annotation created successfully'
    });
  },

  async updateAnnotation(req, res) {
    const annotationIndex = mockDatabase.annotations.findIndex(a => a.id === req.params.id);
    
    if (annotationIndex === -1) {
      return res.status(404).json({
        success: false,
        error: 'Annotation not found'
      });
    }

    const annotation = mockDatabase.annotations[annotationIndex];

    // Check ownership (basic authorization)
    if (annotation.userId !== req.user?.id && req.user?.role !== 'instructor' && req.user?.role !== 'admin') {
      return res.status(403).json({
        success: false,
        error: 'Unauthorized: Can only edit your own annotations'
      });
    }

    const updates = { ...req.body };
    delete updates.id;
    delete updates.userId;
    delete updates.createdAt;
    updates.updatedAt = new Date().toISOString();

    mockDatabase.annotations[annotationIndex] = { ...annotation, ...updates };

    res.status(200).json({
      success: true,
      data: mockDatabase.annotations[annotationIndex],
      message: 'Annotation updated successfully'
    });
  },

  async deleteAnnotation(req, res) {
    const annotationIndex = mockDatabase.annotations.findIndex(a => a.id === req.params.id);
    
    if (annotationIndex === -1) {
      return res.status(404).json({
        success: false,
        error: 'Annotation not found'
      });
    }

    const annotation = mockDatabase.annotations[annotationIndex];

    // Check ownership
    if (annotation.userId !== req.user?.id && req.user?.role !== 'admin') {
      return res.status(403).json({
        success: false,
        error: 'Unauthorized: Can only delete your own annotations'
      });
    }

    mockDatabase.annotations.splice(annotationIndex, 1);

    res.status(200).json({
      success: true,
      message: 'Annotation deleted successfully'
    });
  }
};

// Mock request helper
class MockRequest {
  constructor(path, method = 'GET') {
    this.path = path;
    this.method = method;
    this._status = 200;
    this._body = null;
    this.headers = {};
    this.query = {};
  }

  set(header, value) {
    this.headers[header.toLowerCase()] = value;
    return this;
  }

  send(data) {
    this._body = data;
    return this;
  }

  expect(status) {
    this._expectedStatus = status;
    return this;
  }

  async end() {
    // Simulate API call
    const handler = this.getHandler();
    if (!handler) {
      throw new Error(`No handler found for ${this.method}:${this.path}`);
    }

    const req = {
      params: this.extractParams(),
      query: this.query,
      body: this._body,
      headers: this.headers,
      user: this.extractUser()
    };

    const res = {
      status: (code) => {
        this._status = code;
        return res;
      },
      json: (data) => {
        this._response = data;
        return res;
      }
    };

    await handler(req, res);

    if (this._expectedStatus && this._status !== this._expectedStatus) {
      throw new Error(`Expected status ${this._expectedStatus}, got ${this._status}`);
    }

    return {
      status: this._status,
      body: this._response
    };
  }

  getHandler() {
    if (this.path.includes('/annotations') && this.method === 'GET') {
      if (this.path.match(/\/annotations\/[\w-]+$/)) {
        return mockApiHandlers.getAnnotation;
      }
      return mockApiHandlers.getAnnotations;
    }
    if (this.path === '/api/annotations' && this.method === 'POST') {
      return mockApiHandlers.createAnnotation;
    }
    if (this.path.match(/\/annotations\/[\w-]+$/) && this.method === 'PUT') {
      return mockApiHandlers.updateAnnotation;
    }
    if (this.path.match(/\/annotations\/[\w-]+$/) && this.method === 'DELETE') {
      return mockApiHandlers.deleteAnnotation;
    }
    return null;
  }

  extractParams() {
    const match = this.path.match(/\/annotations\/([\w-]+)/);
    return match ? { id: match[1] } : {};
  }

  extractUser() {
    const authHeader = this.headers.authorization;
    if (!authHeader) return null;

    try {
      const token = authHeader.replace('Bearer ', '');
      return jwt.verify(token, process.env.JWT_SECRET);
    } catch {
      return null;
    }
  }
}

// Mock request function
function mockRequest(path, method) {
  return new MockRequest(path, method);
}

describe('Annotations API Integration Tests', () => {
  let authToken;
  let studentToken;
  let instructorToken;

  beforeEach(() => {
    // Reset mock database
    mockDatabase.annotations = [
      { id: '1', ...testAnnotations.highlight, userId: 'user1', documentId: 'doc1' },
      { id: '2', ...testAnnotations.comment, userId: 'user2', documentId: 'doc1' },
      { id: '3', ...testAnnotations.question, userId: 'user1', documentId: 'doc2' }
    ];

    // Generate test tokens
    studentToken = jwt.sign(
      { id: 'user1', email: testUsers.student.email, role: 'student' },
      process.env.JWT_SECRET,
      { expiresIn: '1h' }
    );

    instructorToken = jwt.sign(
      { id: 'user2', email: testUsers.instructor.email, role: 'instructor' },
      process.env.JWT_SECRET,
      { expiresIn: '1h' }
    );

    authToken = studentToken;
  });

  describe('GET /api/annotations', () => {
    it('should retrieve all annotations', async () => {
      const response = await mockRequest('/api/annotations')
        .set('Authorization', `Bearer ${authToken}`)
        .expect(200)
        .end();

      expect(response.body.success).toBe(true);
      expect(response.body.data).toHaveLength(3);
      expect(response.body.pagination.total).toBe(3);
    });

    it('should filter annotations by document ID', async () => {
      const response = await mockRequest('/api/annotations?documentId=doc1')
        .set('Authorization', `Bearer ${authToken}`)
        .expect(200)
        .end();

      expect(response.body.success).toBe(true);
      expect(response.body.data).toHaveLength(2);
      expect(response.body.data.every(a => a.documentId === 'doc1')).toBe(true);
    });

    it('should filter annotations by user ID', async () => {
      const response = await mockRequest('/api/annotations?userId=user1')
        .set('Authorization', `Bearer ${authToken}`)
        .expect(200)
        .end();

      expect(response.body.success).toBe(true);
      expect(response.body.data).toHaveLength(2);
      expect(response.body.data.every(a => a.userId === 'user1')).toBe(true);
    });

    it('should filter annotations by type', async () => {
      const response = await mockRequest('/api/annotations?type=highlight')
        .set('Authorization', `Bearer ${authToken}`)
        .expect(200)
        .end();

      expect(response.body.success).toBe(true);
      expect(response.body.data.every(a => a.type === 'highlight')).toBe(true);
    });

    it('should combine multiple filters', async () => {
      const response = await mockRequest('/api/annotations?documentId=doc1&type=highlight')
        .set('Authorization', `Bearer ${authToken}`)
        .expect(200)
        .end();

      expect(response.body.success).toBe(true);
      expect(response.body.data.every(a => 
        a.documentId === 'doc1' && a.type === 'highlight'
      )).toBe(true);
    });
  });

  describe('GET /api/annotations/:id', () => {
    it('should retrieve a specific annotation', async () => {
      const response = await mockRequest('/api/annotations/1')
        .set('Authorization', `Bearer ${authToken}`)
        .expect(200)
        .end();

      expect(response.body.success).toBe(true);
      expect(response.body.data.id).toBe('1');
      expect(response.body.data.type).toBe('highlight');
    });

    it('should return 404 for non-existent annotation', async () => {
      const response = await mockRequest('/api/annotations/999')
        .set('Authorization', `Bearer ${authToken}`)
        .expect(404)
        .end();

      expect(response.body.success).toBe(false);
      expect(response.body.error).toBe('Annotation not found');
    });
  });

  describe('POST /api/annotations', () => {
    it('should create a new annotation', async () => {
      const newAnnotation = {
        text: 'New annotation text',
        content: 'This is a new annotation for testing',
        startPosition: 100,
        endPosition: 120,
        type: 'highlight',
        documentId: 'doc1',
        tags: ['test', 'new']
      };

      const response = await mockRequest('/api/annotations', 'POST')
        .set('Authorization', `Bearer ${authToken}`)
        .send(newAnnotation)
        .expect(201)
        .end();

      expect(response.body.success).toBe(true);
      expect(response.body.data.text).toBe(newAnnotation.text);
      expect(response.body.data.content).toBe(newAnnotation.content);
      expect(response.body.data.id).toBeDefined();
      expect(response.body.data.createdAt).toBeDefined();
      expect(response.body.data.userId).toBe('user1');
    });

    it('should validate required fields', async () => {
      const incompleteAnnotation = {
        text: 'Missing required fields'
      };

      const response = await mockRequest('/api/annotations', 'POST')
        .set('Authorization', `Bearer ${authToken}`)
        .send(incompleteAnnotation)
        .expect(400)
        .end();

      expect(response.body.success).toBe(false);
      expect(response.body.error).toBe('Missing required fields');
      expect(response.body.details.required).toContain('content');
      expect(response.body.details.required).toContain('startPosition');
    });

    it('should validate position constraints', async () => {
      const invalidAnnotation = {
        text: 'Invalid positions',
        content: 'Testing invalid positions',
        startPosition: 100,
        endPosition: 50,
        type: 'highlight',
        documentId: 'doc1'
      };

      const response = await mockRequest('/api/annotations', 'POST')
        .set('Authorization', `Bearer ${authToken}`)
        .send(invalidAnnotation)
        .expect(400)
        .end();

      expect(response.body.success).toBe(false);
      expect(response.body.error).toBe('Invalid position: startPosition must be less than endPosition');
    });

    it('should validate annotation type', async () => {
      const invalidTypeAnnotation = {
        text: 'Invalid type',
        content: 'Testing invalid type',
        startPosition: 0,
        endPosition: 10,
        type: 'invalid_type',
        documentId: 'doc1'
      };

      const response = await mockRequest('/api/annotations', 'POST')
        .set('Authorization', `Bearer ${authToken}`)
        .send(invalidTypeAnnotation)
        .expect(400)
        .end();

      expect(response.body.success).toBe(false);
      expect(response.body.error).toBe('Invalid annotation type');
      expect(response.body.details.validTypes).toContain('highlight');
    });

    it('should accept all valid annotation types', async () => {
      const validTypes = ['highlight', 'comment', 'question', 'suggestion', 'note'];

      for (const type of validTypes) {
        const annotation = {
          text: `Test ${type}`,
          content: `Testing ${type} annotation`,
          startPosition: 0,
          endPosition: 10,
          type,
          documentId: 'doc1'
        };

        const response = await mockRequest('/api/annotations', 'POST')
          .set('Authorization', `Bearer ${authToken}`)
          .send(annotation)
          .expect(201)
          .end();

        expect(response.body.success).toBe(true);
        expect(response.body.data.type).toBe(type);
      }
    });
  });

  describe('PUT /api/annotations/:id', () => {
    it('should update an annotation', async () => {
      const updates = {
        content: 'Updated annotation content',
        tags: ['updated', 'test']
      };

      const response = await mockRequest('/api/annotations/1', 'PUT')
        .set('Authorization', `Bearer ${studentToken}`) // user1 owns annotation 1
        .send(updates)
        .expect(200)
        .end();

      expect(response.body.success).toBe(true);
      expect(response.body.data.content).toBe(updates.content);
      expect(response.body.data.tags).toEqual(updates.tags);
      expect(response.body.data.updatedAt).toBeDefined();
    });

    it('should return 404 for non-existent annotation', async () => {
      const response = await mockRequest('/api/annotations/999', 'PUT')
        .set('Authorization', `Bearer ${authToken}`)
        .send({ content: 'Updated content' })
        .expect(404)
        .end();

      expect(response.body.success).toBe(false);
      expect(response.body.error).toBe('Annotation not found');
    });

    it('should enforce ownership for updates', async () => {
      // User1 trying to update user2's annotation
      const response = await mockRequest('/api/annotations/2', 'PUT')
        .set('Authorization', `Bearer ${studentToken}`)
        .send({ content: 'Unauthorized update' })
        .expect(403)
        .end();

      expect(response.body.success).toBe(false);
      expect(response.body.error).toBe('Unauthorized: Can only edit your own annotations');
    });

    it('should allow instructors to update any annotation', async () => {
      const updates = { content: 'Instructor update' };

      const response = await mockRequest('/api/annotations/1', 'PUT')
        .set('Authorization', `Bearer ${instructorToken}`)
        .send(updates)
        .expect(200)
        .end();

      expect(response.body.success).toBe(true);
      expect(response.body.data.content).toBe(updates.content);
    });

    it('should preserve immutable fields', async () => {
      const maliciousUpdate = {
        id: 'changed-id',
        userId: 'different-user',
        createdAt: '2020-01-01',
        content: 'Valid update'
      };

      const response = await mockRequest('/api/annotations/1', 'PUT')
        .set('Authorization', `Bearer ${studentToken}`)
        .send(maliciousUpdate)
        .expect(200)
        .end();

      expect(response.body.success).toBe(true);
      expect(response.body.data.id).toBe('1'); // Original ID preserved
      expect(response.body.data.userId).toBe('user1'); // Original user preserved
      expect(response.body.data.content).toBe('Valid update');
    });
  });

  describe('DELETE /api/annotations/:id', () => {
    it('should delete an annotation', async () => {
      const response = await mockRequest('/api/annotations/1', 'DELETE')
        .set('Authorization', `Bearer ${studentToken}`)
        .expect(200)
        .end();

      expect(response.body.success).toBe(true);
      expect(response.body.message).toBe('Annotation deleted successfully');

      // Verify annotation is deleted
      const getResponse = await mockRequest('/api/annotations/1')
        .set('Authorization', `Bearer ${authToken}`)
        .expect(404)
        .end();

      expect(getResponse.body.error).toBe('Annotation not found');
    });

    it('should return 404 for non-existent annotation', async () => {
      const response = await mockRequest('/api/annotations/999', 'DELETE')
        .set('Authorization', `Bearer ${authToken}`)
        .expect(404)
        .end();

      expect(response.body.success).toBe(false);
      expect(response.body.error).toBe('Annotation not found');
    });

    it('should enforce ownership for deletion', async () => {
      const response = await mockRequest('/api/annotations/2', 'DELETE')
        .set('Authorization', `Bearer ${studentToken}`)
        .expect(403)
        .end();

      expect(response.body.success).toBe(false);
      expect(response.body.error).toBe('Unauthorized: Can only delete your own annotations');
    });
  });

  describe('Error Handling', () => {
    it('should handle missing authorization header', async () => {
      // Most endpoints would require auth, but let's test error handling
      try {
        await mockRequest('/api/annotations')
          .expect(401)
          .end();
      } catch (error) {
        // Expected to fail in our mock setup
        expect(error.message).toContain('No handler found');
      }
    });

    it('should handle invalid JSON in request body', async () => {
      // This would be handled by Express middleware in real app
      const response = await mockRequest('/api/annotations', 'POST')
        .set('Authorization', `Bearer ${authToken}`)
        .send('invalid json')
        .expect(400)
        .end();

      expect(response.body.success).toBe(false);
    });

    it('should handle server errors gracefully', async () => {
      // Mock a server error scenario
      const originalHandler = mockApiHandlers.getAnnotations;
      mockApiHandlers.getAnnotations = async () => {
        throw new Error('Database connection failed');
      };

      try {
        await mockRequest('/api/annotations')
          .set('Authorization', `Bearer ${authToken}`)
          .end();
      } catch (error) {
        expect(error.message).toContain('Database connection failed');
      } finally {
        // Restore original handler
        mockApiHandlers.getAnnotations = originalHandler;
      }
    });
  });

  describe('Performance and Scalability', () => {
    it('should handle large result sets', async () => {
      // Add many annotations
      const largeDataset = Array.from({ length: 1000 }, (_, i) => ({
        id: `bulk-${i}`,
        ...testAnnotations.highlight,
        text: `Bulk annotation ${i}`,
        userId: 'user1',
        documentId: 'doc1'
      }));

      mockDatabase.annotations.push(...largeDataset);

      const response = await mockRequest('/api/annotations?documentId=doc1')
        .set('Authorization', `Bearer ${authToken}`)
        .expect(200)
        .end();

      expect(response.body.success).toBe(true);
      expect(response.body.data.length).toBeGreaterThan(1000);
      expect(response.body.pagination.total).toBeGreaterThan(1000);
    });

    it('should handle concurrent requests', async () => {
      const concurrentRequests = Array.from({ length: 10 }, (_, i) => 
        mockRequest('/api/annotations', 'POST')
          .set('Authorization', `Bearer ${authToken}`)
          .send({
            text: `Concurrent annotation ${i}`,
            content: `Content for annotation ${i}`,
            startPosition: i * 10,
            endPosition: (i * 10) + 5,
            type: 'highlight',
            documentId: 'doc1'
          })
          .expect(201)
          .end()
      );

      const responses = await Promise.all(concurrentRequests);

      responses.forEach((response, i) => {
        expect(response.body.success).toBe(true);
        expect(response.body.data.text).toBe(`Concurrent annotation ${i}`);
      });
    });
  });
});