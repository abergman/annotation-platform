/**
 * Integration Tests - Authentication & Authorization
 * Tests for user authentication, JWT tokens, and access control
 */

import jwt from 'jsonwebtoken';
import bcrypt from 'bcryptjs';
import { testUsers } from '../../fixtures/test-data.js';

// Mock authentication database
const mockAuthDatabase = {
  users: [
    { 
      id: 'user1', 
      ...testUsers.student, 
      password: '$2a$01$hashedpassword123' // Mock hashed password
    },
    { 
      id: 'user2', 
      ...testUsers.instructor, 
      password: '$2a$01$hashedpassword456'
    },
    { 
      id: 'user3', 
      ...testUsers.admin, 
      password: '$2a$01$hashedpassword789'
    }
  ],
  sessions: [],
  refreshTokens: []
};

// Mock authentication handlers
const mockAuthHandlers = {
  async register(req, res) {
    const { name, email, password, role = 'student' } = req.body;

    // Validation
    if (!name || !email || !password) {
      return res.status(400).json({
        success: false,
        error: 'Missing required fields',
        details: { required: ['name', 'email', 'password'] }
      });
    }

    // Email format validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      return res.status(400).json({
        success: false,
        error: 'Invalid email format'
      });
    }

    // Password strength validation
    if (password.length < 8) {
      return res.status(400).json({
        success: false,
        error: 'Password must be at least 8 characters long'
      });
    }

    // Check if user already exists
    const existingUser = mockAuthDatabase.users.find(u => u.email === email);
    if (existingUser) {
      return res.status(409).json({
        success: false,
        error: 'User with this email already exists'
      });
    }

    // Create new user
    const hashedPassword = await bcrypt.hash(password, 1);
    const newUser = {
      id: Date.now().toString(),
      name,
      email,
      password: hashedPassword,
      role,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      isVerified: false
    };

    mockAuthDatabase.users.push(newUser);

    // Generate tokens
    const accessToken = jwt.sign(
      { id: newUser.id, email: newUser.email, role: newUser.role },
      process.env.JWT_SECRET,
      { expiresIn: '15m' }
    );

    const refreshToken = jwt.sign(
      { id: newUser.id, type: 'refresh' },
      process.env.JWT_SECRET,
      { expiresIn: '7d' }
    );

    // Store refresh token
    mockAuthDatabase.refreshTokens.push({
      token: refreshToken,
      userId: newUser.id,
      createdAt: new Date()
    });

    // Remove password from response
    const userResponse = { ...newUser };
    delete userResponse.password;

    res.status(201).json({
      success: true,
      data: {
        user: userResponse,
        accessToken,
        refreshToken
      },
      message: 'User registered successfully'
    });
  },

  async login(req, res) {
    const { email, password } = req.body;

    if (!email || !password) {
      return res.status(400).json({
        success: false,
        error: 'Email and password are required'
      });
    }

    // Find user
    const user = mockAuthDatabase.users.find(u => u.email === email);
    if (!user) {
      return res.status(401).json({
        success: false,
        error: 'Invalid credentials'
      });
    }

    // Compare password
    const isValidPassword = await bcrypt.compare(password, user.password);
    if (!isValidPassword) {
      return res.status(401).json({
        success: false,
        error: 'Invalid credentials'
      });
    }

    // Generate tokens
    const accessToken = jwt.sign(
      { id: user.id, email: user.email, role: user.role },
      process.env.JWT_SECRET,
      { expiresIn: '15m' }
    );

    const refreshToken = jwt.sign(
      { id: user.id, type: 'refresh' },
      process.env.JWT_SECRET,
      { expiresIn: '7d' }
    );

    // Store session
    mockAuthDatabase.sessions.push({
      userId: user.id,
      token: accessToken,
      createdAt: new Date(),
      lastActive: new Date()
    });

    // Store refresh token
    mockAuthDatabase.refreshTokens.push({
      token: refreshToken,
      userId: user.id,
      createdAt: new Date()
    });

    const userResponse = { ...user };
    delete userResponse.password;

    res.status(200).json({
      success: true,
      data: {
        user: userResponse,
        accessToken,
        refreshToken
      },
      message: 'Login successful'
    });
  },

  async refreshToken(req, res) {
    const { refreshToken } = req.body;

    if (!refreshToken) {
      return res.status(400).json({
        success: false,
        error: 'Refresh token is required'
      });
    }

    try {
      const decoded = jwt.verify(refreshToken, process.env.JWT_SECRET);
      
      // Check if refresh token exists in database
      const storedToken = mockAuthDatabase.refreshTokens.find(
        t => t.token === refreshToken && t.userId === decoded.id
      );

      if (!storedToken) {
        return res.status(401).json({
          success: false,
          error: 'Invalid refresh token'
        });
      }

      // Find user
      const user = mockAuthDatabase.users.find(u => u.id === decoded.id);
      if (!user) {
        return res.status(401).json({
          success: false,
          error: 'User not found'
        });
      }

      // Generate new access token
      const newAccessToken = jwt.sign(
        { id: user.id, email: user.email, role: user.role },
        process.env.JWT_SECRET,
        { expiresIn: '15m' }
      );

      res.status(200).json({
        success: true,
        data: {
          accessToken: newAccessToken
        }
      });

    } catch (error) {
      return res.status(401).json({
        success: false,
        error: 'Invalid or expired refresh token'
      });
    }
  },

  async logout(req, res) {
    const authHeader = req.headers.authorization;
    if (!authHeader) {
      return res.status(400).json({
        success: false,
        error: 'Authorization header required'
      });
    }

    try {
      const token = authHeader.replace('Bearer ', '');
      const decoded = jwt.verify(token, process.env.JWT_SECRET);

      // Remove session
      mockAuthDatabase.sessions = mockAuthDatabase.sessions.filter(
        s => s.userId !== decoded.id || s.token !== token
      );

      // Remove refresh tokens for this user
      mockAuthDatabase.refreshTokens = mockAuthDatabase.refreshTokens.filter(
        t => t.userId !== decoded.id
      );

      res.status(200).json({
        success: true,
        message: 'Logout successful'
      });

    } catch (error) {
      return res.status(401).json({
        success: false,
        error: 'Invalid token'
      });
    }
  },

  async validateToken(req, res) {
    const authHeader = req.headers.authorization;
    if (!authHeader) {
      return res.status(401).json({
        success: false,
        error: 'Authorization header required'
      });
    }

    try {
      const token = authHeader.replace('Bearer ', '');
      const decoded = jwt.verify(token, process.env.JWT_SECRET);

      // Find user
      const user = mockAuthDatabase.users.find(u => u.id === decoded.id);
      if (!user) {
        return res.status(401).json({
          success: false,
          error: 'User not found'
        });
      }

      const userResponse = { ...user };
      delete userResponse.password;

      res.status(200).json({
        success: true,
        data: {
          user: userResponse,
          tokenInfo: {
            issuedAt: new Date(decoded.iat * 1000),
            expiresAt: new Date(decoded.exp * 1000)
          }
        }
      });

    } catch (error) {
      return res.status(401).json({
        success: false,
        error: 'Invalid or expired token'
      });
    }
  }
};

// Mock authorization middleware
const mockAuthMiddleware = {
  requireAuth(req, res, next) {
    const authHeader = req.headers.authorization;
    if (!authHeader) {
      return res.status(401).json({
        success: false,
        error: 'Authorization header required'
      });
    }

    try {
      const token = authHeader.replace('Bearer ', '');
      const decoded = jwt.verify(token, process.env.JWT_SECRET);
      req.user = decoded;
      next();
    } catch (error) {
      return res.status(401).json({
        success: false,
        error: 'Invalid or expired token'
      });
    }
  },

  requireRole(roles) {
    return (req, res, next) => {
      if (!req.user) {
        return res.status(401).json({
          success: false,
          error: 'Authentication required'
        });
      }

      if (!roles.includes(req.user.role)) {
        return res.status(403).json({
          success: false,
          error: 'Insufficient permissions'
        });
      }

      next();
    };
  }
};

// Mock request helper for authentication tests
class MockAuthRequest {
  constructor(path, method = 'POST') {
    this.path = path;
    this.method = method;
    this._status = 200;
    this._body = null;
    this.headers = {};
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
    const handler = this.getHandler();
    if (!handler) {
      throw new Error(`No handler found for ${this.method}:${this.path}`);
    }

    const req = {
      body: this._body,
      headers: this.headers
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
    const handlers = {
      'POST:/auth/register': mockAuthHandlers.register,
      'POST:/auth/login': mockAuthHandlers.login,
      'POST:/auth/refresh': mockAuthHandlers.refreshToken,
      'POST:/auth/logout': mockAuthHandlers.logout,
      'GET:/auth/validate': mockAuthHandlers.validateToken
    };

    return handlers[`${this.method}:${this.path}`];
  }
}

function mockAuthRequest(path, method = 'POST') {
  return new MockAuthRequest(path, method);
}

describe('Authentication & Authorization Integration Tests', () => {
  beforeEach(() => {
    // Reset database state
    mockAuthDatabase.users = [
      { 
        id: 'user1', 
        ...testUsers.student, 
        password: '$2a$01$hashedpassword123'
      },
      { 
        id: 'user2', 
        ...testUsers.instructor, 
        password: '$2a$01$hashedpassword456'
      },
      { 
        id: 'user3', 
        ...testUsers.admin, 
        password: '$2a$01$hashedpassword789'
      }
    ];
    mockAuthDatabase.sessions = [];
    mockAuthDatabase.refreshTokens = [];
  });

  describe('User Registration', () => {
    it('should register a new user successfully', async () => {
      const newUser = {
        name: 'John Doe',
        email: 'john.doe@university.edu',
        password: 'SecurePassword123!',
        role: 'student'
      };

      const response = await mockAuthRequest('/auth/register')
        .send(newUser)
        .expect(201)
        .end();

      expect(response.body.success).toBe(true);
      expect(response.body.data.user.name).toBe(newUser.name);
      expect(response.body.data.user.email).toBe(newUser.email);
      expect(response.body.data.user.role).toBe(newUser.role);
      expect(response.body.data.user.password).toBeUndefined();
      expect(response.body.data.accessToken).toBeDefined();
      expect(response.body.data.refreshToken).toBeDefined();
    });

    it('should validate required fields', async () => {
      const incompleteUser = {
        name: 'John Doe'
        // Missing email and password
      };

      const response = await mockAuthRequest('/auth/register')
        .send(incompleteUser)
        .expect(400)
        .end();

      expect(response.body.success).toBe(false);
      expect(response.body.error).toBe('Missing required fields');
      expect(response.body.details.required).toContain('email');
      expect(response.body.details.required).toContain('password');
    });

    it('should validate email format', async () => {
      const invalidEmailUser = {
        name: 'John Doe',
        email: 'invalid-email',
        password: 'SecurePassword123!'
      };

      const response = await mockAuthRequest('/auth/register')
        .send(invalidEmailUser)
        .expect(400)
        .end();

      expect(response.body.success).toBe(false);
      expect(response.body.error).toBe('Invalid email format');
    });

    it('should validate password strength', async () => {
      const weakPasswordUser = {
        name: 'John Doe',
        email: 'john@university.edu',
        password: '123'
      };

      const response = await mockAuthRequest('/auth/register')
        .send(weakPasswordUser)
        .expect(400)
        .end();

      expect(response.body.success).toBe(false);
      expect(response.body.error).toBe('Password must be at least 8 characters long');
    });

    it('should prevent duplicate email registration', async () => {
      const duplicateUser = {
        name: 'Another User',
        email: testUsers.student.email,
        password: 'SecurePassword123!'
      };

      const response = await mockAuthRequest('/auth/register')
        .send(duplicateUser)
        .expect(409)
        .end();

      expect(response.body.success).toBe(false);
      expect(response.body.error).toBe('User with this email already exists');
    });

    it('should default to student role', async () => {
      const userWithoutRole = {
        name: 'Default Role User',
        email: 'default@university.edu',
        password: 'SecurePassword123!'
      };

      const response = await mockAuthRequest('/auth/register')
        .send(userWithoutRole)
        .expect(201)
        .end();

      expect(response.body.success).toBe(true);
      expect(response.body.data.user.role).toBe('student');
    });
  });

  describe('User Login', () => {
    it('should login with valid credentials', async () => {
      const loginData = {
        email: testUsers.student.email,
        password: testUsers.student.password
      };

      const response = await mockAuthRequest('/auth/login')
        .send(loginData)
        .expect(200)
        .end();

      expect(response.body.success).toBe(true);
      expect(response.body.data.user.email).toBe(loginData.email);
      expect(response.body.data.user.password).toBeUndefined();
      expect(response.body.data.accessToken).toBeDefined();
      expect(response.body.data.refreshToken).toBeDefined();
    });

    it('should reject invalid email', async () => {
      const loginData = {
        email: 'nonexistent@university.edu',
        password: 'anypassword'
      };

      const response = await mockAuthRequest('/auth/login')
        .send(loginData)
        .expect(401)
        .end();

      expect(response.body.success).toBe(false);
      expect(response.body.error).toBe('Invalid credentials');
    });

    it('should reject invalid password', async () => {
      const loginData = {
        email: testUsers.student.email,
        password: 'wrongpassword'
      };

      const response = await mockAuthRequest('/auth/login')
        .send(loginData)
        .expect(401)
        .end();

      expect(response.body.success).toBe(false);
      expect(response.body.error).toBe('Invalid credentials');
    });

    it('should require email and password', async () => {
      const response = await mockAuthRequest('/auth/login')
        .send({})
        .expect(400)
        .end();

      expect(response.body.success).toBe(false);
      expect(response.body.error).toBe('Email and password are required');
    });

    it('should generate valid JWT tokens', async () => {
      const loginData = {
        email: testUsers.student.email,
        password: testUsers.student.password
      };

      const response = await mockAuthRequest('/auth/login')
        .send(loginData)
        .expect(200)
        .end();

      const { accessToken, refreshToken } = response.body.data;

      // Verify access token
      const accessDecoded = jwt.verify(accessToken, process.env.JWT_SECRET);
      expect(accessDecoded.email).toBe(loginData.email);
      expect(accessDecoded.role).toBe('student');

      // Verify refresh token
      const refreshDecoded = jwt.verify(refreshToken, process.env.JWT_SECRET);
      expect(refreshDecoded.type).toBe('refresh');
    });
  });

  describe('Token Refresh', () => {
    let validRefreshToken;

    beforeEach(async () => {
      // Login to get a refresh token
      const loginResponse = await mockAuthRequest('/auth/login')
        .send({
          email: testUsers.student.email,
          password: testUsers.student.password
        })
        .end();

      validRefreshToken = loginResponse.body.data.refreshToken;
    });

    it('should refresh access token with valid refresh token', async () => {
      const response = await mockAuthRequest('/auth/refresh')
        .send({ refreshToken: validRefreshToken })
        .expect(200)
        .end();

      expect(response.body.success).toBe(true);
      expect(response.body.data.accessToken).toBeDefined();

      // Verify new token is valid
      const decoded = jwt.verify(response.body.data.accessToken, process.env.JWT_SECRET);
      expect(decoded.email).toBe(testUsers.student.email);
    });

    it('should reject invalid refresh token', async () => {
      const response = await mockAuthRequest('/auth/refresh')
        .send({ refreshToken: 'invalid.token.here' })
        .expect(401)
        .end();

      expect(response.body.success).toBe(false);
      expect(response.body.error).toBe('Invalid or expired refresh token');
    });

    it('should require refresh token', async () => {
      const response = await mockAuthRequest('/auth/refresh')
        .send({})
        .expect(400)
        .end();

      expect(response.body.success).toBe(false);
      expect(response.body.error).toBe('Refresh token is required');
    });

    it('should reject revoked refresh token', async () => {
      // Remove refresh token from database (simulating revocation)
      mockAuthDatabase.refreshTokens = [];

      const response = await mockAuthRequest('/auth/refresh')
        .send({ refreshToken: validRefreshToken })
        .expect(401)
        .end();

      expect(response.body.success).toBe(false);
      expect(response.body.error).toBe('Invalid refresh token');
    });
  });

  describe('Token Validation', () => {
    let validAccessToken;

    beforeEach(async () => {
      const loginResponse = await mockAuthRequest('/auth/login')
        .send({
          email: testUsers.instructor.email,
          password: testUsers.instructor.password
        })
        .end();

      validAccessToken = loginResponse.body.data.accessToken;
    });

    it('should validate valid access token', async () => {
      const response = await mockAuthRequest('/auth/validate', 'GET')
        .set('Authorization', `Bearer ${validAccessToken}`)
        .expect(200)
        .end();

      expect(response.body.success).toBe(true);
      expect(response.body.data.user.email).toBe(testUsers.instructor.email);
      expect(response.body.data.user.role).toBe('instructor');
      expect(response.body.data.tokenInfo.issuedAt).toBeDefined();
      expect(response.body.data.tokenInfo.expiresAt).toBeDefined();
    });

    it('should reject missing authorization header', async () => {
      const response = await mockAuthRequest('/auth/validate', 'GET')
        .expect(401)
        .end();

      expect(response.body.success).toBe(false);
      expect(response.body.error).toBe('Authorization header required');
    });

    it('should reject invalid token', async () => {
      const response = await mockAuthRequest('/auth/validate', 'GET')
        .set('Authorization', 'Bearer invalid.token.here')
        .expect(401)
        .end();

      expect(response.body.success).toBe(false);
      expect(response.body.error).toBe('Invalid or expired token');
    });

    it('should reject expired token', async () => {
      // Create an expired token
      const expiredToken = jwt.sign(
        { id: 'user1', email: testUsers.student.email, role: 'student' },
        process.env.JWT_SECRET,
        { expiresIn: '-1h' }
      );

      const response = await mockAuthRequest('/auth/validate', 'GET')
        .set('Authorization', `Bearer ${expiredToken}`)
        .expect(401)
        .end();

      expect(response.body.success).toBe(false);
      expect(response.body.error).toBe('Invalid or expired token');
    });
  });

  describe('Logout', () => {
    let validAccessToken;

    beforeEach(async () => {
      const loginResponse = await mockAuthRequest('/auth/login')
        .send({
          email: testUsers.student.email,
          password: testUsers.student.password
        })
        .end();

      validAccessToken = loginResponse.body.data.accessToken;
    });

    it('should logout successfully', async () => {
      const response = await mockAuthRequest('/auth/logout')
        .set('Authorization', `Bearer ${validAccessToken}`)
        .expect(200)
        .end();

      expect(response.body.success).toBe(true);
      expect(response.body.message).toBe('Logout successful');
    });

    it('should clear user sessions on logout', async () => {
      const initialSessions = mockAuthDatabase.sessions.length;
      const initialRefreshTokens = mockAuthDatabase.refreshTokens.length;

      await mockAuthRequest('/auth/logout')
        .set('Authorization', `Bearer ${validAccessToken}`)
        .end();

      expect(mockAuthDatabase.sessions.length).toBeLessThan(initialSessions);
      expect(mockAuthDatabase.refreshTokens.length).toBeLessThan(initialRefreshTokens);
    });

    it('should require authorization header for logout', async () => {
      const response = await mockAuthRequest('/auth/logout')
        .expect(400)
        .end();

      expect(response.body.success).toBe(false);
      expect(response.body.error).toBe('Authorization header required');
    });
  });

  describe('Authorization Middleware', () => {
    it('should allow access with valid token', () => {
      const mockReq = {
        headers: {
          authorization: `Bearer ${jwt.sign({ id: 'user1', role: 'student' }, process.env.JWT_SECRET)}`
        }
      };
      const mockRes = {};
      const mockNext = jest.fn();

      mockAuthMiddleware.requireAuth(mockReq, mockRes, mockNext);

      expect(mockNext).toHaveBeenCalled();
      expect(mockReq.user).toBeDefined();
      expect(mockReq.user.id).toBe('user1');
    });

    it('should enforce role-based access', () => {
      const mockReq = {
        user: { id: 'user1', role: 'student' }
      };
      const mockRes = {
        status: jest.fn().mockReturnThis(),
        json: jest.fn()
      };
      const mockNext = jest.fn();

      const requireInstructor = mockAuthMiddleware.requireRole(['instructor', 'admin']);
      requireInstructor(mockReq, mockRes, mockNext);

      expect(mockRes.status).toHaveBeenCalledWith(403);
      expect(mockRes.json).toHaveBeenCalledWith({
        success: false,
        error: 'Insufficient permissions'
      });
      expect(mockNext).not.toHaveBeenCalled();
    });

    it('should allow access with correct role', () => {
      const mockReq = {
        user: { id: 'user2', role: 'instructor' }
      };
      const mockRes = {};
      const mockNext = jest.fn();

      const requireInstructor = mockAuthMiddleware.requireRole(['instructor', 'admin']);
      requireInstructor(mockReq, mockRes, mockNext);

      expect(mockNext).toHaveBeenCalled();
    });
  });

  describe('Security Features', () => {
    it('should hash passwords before storage', async () => {
      const newUser = {
        name: 'Security Test',
        email: 'security@university.edu',
        password: 'PlainTextPassword123!'
      };

      await mockAuthRequest('/auth/register')
        .send(newUser)
        .end();

      const storedUser = mockAuthDatabase.users.find(u => u.email === newUser.email);
      expect(storedUser.password).not.toBe(newUser.password);
      expect(storedUser.password).toMatch(/^\$2[ab]\$\d+\$/); // bcrypt hash format
    });

    it('should not expose sensitive data in responses', async () => {
      const loginData = {
        email: testUsers.student.email,
        password: testUsers.student.password
      };

      const response = await mockAuthRequest('/auth/login')
        .send(loginData)
        .end();

      expect(response.body.data.user.password).toBeUndefined();
      expect(response.body.data.user.id).toBeDefined();
      expect(response.body.data.user.email).toBeDefined();
    });

    it('should handle concurrent login attempts', async () => {
      const loginData = {
        email: testUsers.student.email,
        password: testUsers.student.password
      };

      const concurrentLogins = Array.from({ length: 5 }, () =>
        mockAuthRequest('/auth/login').send(loginData).end()
      );

      const responses = await Promise.all(concurrentLogins);

      responses.forEach(response => {
        expect(response.body.success).toBe(true);
        expect(response.body.data.accessToken).toBeDefined();
      });
    });
  });
});