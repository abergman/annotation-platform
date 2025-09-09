/**
 * WebSocket Server Tests
 * 
 * Test the real-time WebSocket functionality
 */

import { describe, test, expect, beforeAll, afterAll, beforeEach, afterEach } from '@jest/globals';
import { createServer } from 'http';
import { Server } from 'socket.io';
import { io as Client } from 'socket.io-client';
import jwt from 'jsonwebtoken';

describe('WebSocket Server', () => {
  let httpServer;
  let io;
  let serverSocket;
  let clientSocket;
  const testPort = 8002;
  const testUser = {
    id: 'test-user-123',
    username: 'testuser',
    email: 'test@example.com',
    role: 'annotator'
  };

  beforeAll((done) => {
    // Create HTTP server
    httpServer = createServer();
    
    // Create Socket.IO server
    io = new Server(httpServer, {
      cors: {
        origin: "http://localhost:3000",
        methods: ["GET", "POST"]
      }
    });

    // Mock authentication middleware
    io.use((socket, next) => {
      const token = socket.handshake.auth.token;
      if (!token) {
        return next(new Error('Authentication token required'));
      }

      try {
        const decoded = jwt.verify(token, process.env.JWT_SECRET || 'test-secret');
        socket.user = testUser;
        next();
      } catch (error) {
        next(new Error('Invalid token'));
      }
    });

    // Basic connection handler
    io.on('connection', (socket) => {
      serverSocket = socket;
      
      socket.on('join-project', (data) => {
        const roomId = data.textId ? 
          `project:${data.projectId}:text:${data.textId}` : 
          `project:${data.projectId}`;
        
        socket.join(roomId);
        socket.emit('room-state', {
          roomId,
          users: [testUser],
          annotations: [],
          cursors: [],
          timestamp: new Date().toISOString()
        });
      });

      socket.on('annotation-create', (data) => {
        const annotation = {
          ...data.annotation,
          id: `ann_${Date.now()}`,
          createdBy: socket.user.id,
          createdAt: new Date().toISOString()
        };

        socket.to(data.roomId).emit('annotation-created', {
          annotation,
          createdBy: { id: socket.user.id, username: socket.user.username },
          timestamp: new Date().toISOString()
        });

        socket.emit('annotation-created-confirm', {
          localId: data.annotation.localId,
          annotation
        });
      });

      socket.on('cursor-position', (data) => {
        socket.to(data.roomId).emit('cursor-update', {
          userId: socket.user.id,
          username: socket.user.username,
          position: data.position,
          textId: data.textId
        });
      });
    });

    httpServer.listen(testPort, done);
  });

  beforeEach((done) => {
    // Create test JWT token
    const token = jwt.sign(testUser, process.env.JWT_SECRET || 'test-secret');
    
    // Create client socket
    clientSocket = Client(`http://localhost:${testPort}`, {
      auth: { token }
    });

    clientSocket.on('connect', done);
  });

  afterEach(() => {
    if (clientSocket.connected) {
      clientSocket.disconnect();
    }
  });

  afterAll(() => {
    if (io) {
      io.close();
    }
    if (httpServer) {
      httpServer.close();
    }
  });

  describe('Connection', () => {
    test('should connect with valid token', (done) => {
      expect(clientSocket.connected).toBe(true);
      done();
    });

    test('should reject connection with invalid token', (done) => {
      const badClient = Client(`http://localhost:${testPort}`, {
        auth: { token: 'invalid-token' }
      });

      badClient.on('connect_error', (error) => {
        expect(error.message).toContain('Invalid token');
        badClient.disconnect();
        done();
      });
    });

    test('should reject connection without token', (done) => {
      const noAuthClient = Client(`http://localhost:${testPort}`);

      noAuthClient.on('connect_error', (error) => {
        expect(error.message).toContain('Authentication token required');
        noAuthClient.disconnect();
        done();
      });
    });
  });

  describe('Room Management', () => {
    test('should join project room', (done) => {
      const projectId = 'test-project-123';
      const textId = 'test-text-456';

      clientSocket.emit('join-project', { projectId, textId });

      clientSocket.on('room-state', (roomState) => {
        expect(roomState.roomId).toBe(`project:${projectId}:text:${textId}`);
        expect(roomState.users).toHaveLength(1);
        expect(roomState.users[0].id).toBe(testUser.id);
        done();
      });
    });

    test('should handle project-only room', (done) => {
      const projectId = 'test-project-789';

      clientSocket.emit('join-project', { projectId });

      clientSocket.on('room-state', (roomState) => {
        expect(roomState.roomId).toBe(`project:${projectId}`);
        expect(roomState.users).toHaveLength(1);
        done();
      });
    });
  });

  describe('Real-time Annotations', () => {
    const projectId = 'test-project-ann';
    const textId = 'test-text-ann';
    const roomId = `project:${projectId}:text:${textId}`;

    beforeEach((done) => {
      clientSocket.emit('join-project', { projectId, textId });
      clientSocket.on('room-state', () => done());
    });

    test('should create annotation and receive confirmation', (done) => {
      const annotation = {
        localId: 'local-123',
        textId: textId,
        startOffset: 10,
        endOffset: 20,
        text: 'test annotation',
        labels: ['important']
      };

      clientSocket.emit('annotation-create', { annotation, roomId });

      clientSocket.on('annotation-created-confirm', (data) => {
        expect(data.localId).toBe(annotation.localId);
        expect(data.annotation.id).toBeDefined();
        expect(data.annotation.createdBy).toBe(testUser.id);
        expect(data.annotation.text).toBe(annotation.text);
        done();
      });
    });

    test('should broadcast annotation to other users', (done) => {
      // Create second client to receive broadcast
      const token = jwt.sign(testUser, process.env.JWT_SECRET || 'test-secret');
      const client2 = Client(`http://localhost:${testPort}`, {
        auth: { token }
      });

      client2.on('connect', () => {
        client2.emit('join-project', { projectId, textId });
        
        client2.on('annotation-created', (data) => {
          expect(data.annotation.text).toBe('broadcast test');
          expect(data.createdBy.id).toBe(testUser.id);
          client2.disconnect();
          done();
        });

        // Create annotation from first client
        const annotation = {
          localId: 'broadcast-123',
          textId: textId,
          startOffset: 0,
          endOffset: 10,
          text: 'broadcast test',
          labels: ['test']
        };

        clientSocket.emit('annotation-create', { annotation, roomId });
      });
    });
  });

  describe('Cursor Tracking', () => {
    const projectId = 'test-project-cursor';
    const textId = 'test-text-cursor';
    const roomId = `project:${projectId}:text:${textId}`;

    beforeEach((done) => {
      clientSocket.emit('join-project', { projectId, textId });
      clientSocket.on('room-state', () => done());
    });

    test('should track cursor position', (done) => {
      // Create second client to receive cursor updates
      const token = jwt.sign({ ...testUser, id: 'user-2' }, process.env.JWT_SECRET || 'test-secret');
      const client2 = Client(`http://localhost:${testPort}`, {
        auth: { token }
      });

      client2.on('connect', () => {
        client2.emit('join-project', { projectId, textId });
        
        client2.on('cursor-update', (data) => {
          expect(data.userId).toBe(testUser.id);
          expect(data.username).toBe(testUser.username);
          expect(data.position.offset).toBe(25);
          expect(data.textId).toBe(textId);
          client2.disconnect();
          done();
        });

        // Send cursor position from first client
        clientSocket.emit('cursor-position', {
          roomId,
          position: { offset: 25 },
          textId
        });
      });
    });
  });

  describe('Error Handling', () => {
    test('should handle malformed data gracefully', (done) => {
      clientSocket.on('error', (error) => {
        expect(error.message).toBeDefined();
        done();
      });

      // Send malformed annotation data
      clientSocket.emit('annotation-create', {
        annotation: { invalid: 'data' }
        // Missing roomId
      });
    });
  });

  describe('Performance', () => {
    test('should handle multiple rapid cursor updates', (done) => {
      const projectId = 'perf-test';
      const roomId = `project:${projectId}`;
      let updateCount = 0;
      const totalUpdates = 10;

      clientSocket.emit('join-project', { projectId });

      clientSocket.on('room-state', () => {
        // Send rapid cursor updates
        for (let i = 0; i < totalUpdates; i++) {
          setTimeout(() => {
            clientSocket.emit('cursor-position', {
              roomId,
              position: { offset: i * 5 },
              textId: 'test-text'
            });
            
            updateCount++;
            if (updateCount === totalUpdates) {
              // Allow time for processing
              setTimeout(() => {
                done();
              }, 100);
            }
          }, i * 10);
        }
      });
    });

    test('should handle concurrent annotation creation', async () => {
      const projectId = 'concurrent-test';
      const roomId = `project:${projectId}`;
      
      // Join room
      await new Promise((resolve) => {
        clientSocket.emit('join-project', { projectId });
        clientSocket.on('room-state', resolve);
      });

      // Create multiple annotations concurrently
      const promises = Array.from({ length: 5 }, (_, i) => {
        return new Promise((resolve) => {
          const annotation = {
            localId: `concurrent-${i}`,
            textId: 'test-text',
            startOffset: i * 10,
            endOffset: (i * 10) + 5,
            text: `annotation ${i}`,
            labels: ['test']
          };

          clientSocket.emit('annotation-create', { annotation, roomId });
          
          clientSocket.on('annotation-created-confirm', (data) => {
            if (data.localId === annotation.localId) {
              resolve(data);
            }
          });
        });
      });

      const results = await Promise.all(promises);
      expect(results).toHaveLength(5);
      results.forEach((result, i) => {
        expect(result.annotation.text).toBe(`annotation ${i}`);
      });
    });
  });
});