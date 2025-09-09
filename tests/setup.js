/**
 * Jest Global Test Setup
 * Configures test environment for academic annotation platform
 */

import { MongoMemoryServer } from 'mongodb-memory-server';
import mongoose from 'mongoose';

// Global test configuration
global.testTimeout = 10000;
global.mongoServer = null;

// Setup before all tests
beforeAll(async () => {
  // Start in-memory MongoDB for testing
  global.mongoServer = await MongoMemoryServer.create();
  const uri = global.mongoServer.getUri();
  
  await mongoose.connect(uri, {
    useNewUrlParser: true,
    useUnifiedTopology: true,
  });

  // Set test environment variables
  process.env.NODE_ENV = 'test';
  process.env.JWT_SECRET = 'test-jwt-secret-key';
  process.env.BCRYPT_ROUNDS = '1'; // Fast hashing for tests
});

// Cleanup after each test
afterEach(async () => {
  const collections = mongoose.connection.collections;
  
  // Clear all collections after each test
  for (const key in collections) {
    const collection = collections[key];
    await collection.deleteMany({});
  }
});

// Cleanup after all tests
afterAll(async () => {
  await mongoose.connection.dropDatabase();
  await mongoose.connection.close();
  
  if (global.mongoServer) {
    await global.mongoServer.stop();
  }
});

// Extend Jest matchers for better assertions
expect.extend({
  toBeValidObjectId(received) {
    const pass = mongoose.Types.ObjectId.isValid(received);
    return {
      message: () => `expected ${received} ${pass ? 'not ' : ''}to be a valid ObjectId`,
      pass,
    };
  },
  
  toHaveValidationError(received, field) {
    const pass = received.errors && received.errors[field];
    return {
      message: () => `expected validation error for field "${field}"`,
      pass: !!pass,
    };
  }
});

// Global test utilities
global.testUtils = {
  generateUserId: () => new mongoose.Types.ObjectId(),
  generateTestEmail: () => `test-${Date.now()}@example.com`,
  sleep: (ms) => new Promise(resolve => setTimeout(resolve, ms)),
  
  // Mock user data
  createMockUser: (overrides = {}) => ({
    name: 'Test User',
    email: 'test@example.com',
    password: 'SecurePassword123!',
    role: 'student',
    ...overrides
  }),
  
  // Mock annotation data
  createMockAnnotation: (overrides = {}) => ({
    text: 'This is a sample text for annotation',
    content: 'This is an important note about the text',
    startPosition: 0,
    endPosition: 20,
    tags: ['important', 'review'],
    type: 'highlight',
    ...overrides
  }),
  
  // Mock document data
  createMockDocument: (overrides = {}) => ({
    title: 'Sample Academic Paper',
    content: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit...',
    type: 'pdf',
    metadata: {
      author: 'Dr. Test Author',
      journal: 'Test Journal',
      year: 2023
    },
    ...overrides
  })
};

// Console warnings for test debugging
const originalWarn = console.warn;
console.warn = (...args) => {
  if (
    args[0]?.includes?.('deprecated') ||
    args[0]?.includes?.('warning')
  ) {
    return; // Suppress known warnings during tests
  }
  originalWarn.apply(console, args);
};