/**
 * Unit Tests - User Model
 * Tests for user model, authentication, and authorization logic
 */

import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';
import mongoose from 'mongoose';
import { testUsers } from '../../fixtures/test-data.js';

// Mock User model
class MockUser {
  constructor(data) {
    this.data = data;
    this._id = new mongoose.Types.ObjectId();
    this.createdAt = new Date();
    this.updatedAt = new Date();
  }

  static async create(data) {
    const user = new MockUser(data);
    if (data.password) {
      user.data.password = await bcrypt.hash(data.password, 1);
    }
    return user;
  }

  static async findById(id) {
    return new MockUser({ _id: id });
  }

  static async findOne(query) {
    if (query.email === 'existing@example.com') {
      return new MockUser({ email: query.email });
    }
    return null;
  }

  async comparePassword(candidatePassword) {
    if (!this.data.password) return false;
    return bcrypt.compare(candidatePassword, this.data.password);
  }

  generateToken() {
    return jwt.sign(
      { 
        id: this._id, 
        email: this.data.email, 
        role: this.data.role 
      },
      process.env.JWT_SECRET,
      { expiresIn: '7d' }
    );
  }

  hasPermission(permission) {
    const rolePermissions = {
      admin: ['manage_users', 'system_config', 'data_export', 'read', 'write', 'moderate'],
      instructor: ['read', 'write', 'moderate', 'export'],
      researcher: ['read', 'write', 'export'],
      student: ['read', 'write']
    };
    
    return rolePermissions[this.data.role]?.includes(permission) || false;
  }

  canAccessProject(project) {
    if (this.data.role === 'admin') return true;
    
    const projectPermissions = project.permissions || {};
    const userPermissions = projectPermissions[this.data.role] || [];
    
    return userPermissions.includes('read');
  }

  validate() {
    const required = ['name', 'email', 'password', 'role'];
    for (const field of required) {
      if (!this.data[field]) {
        throw new Error(`Validation failed: ${field} is required`);
      }
    }

    // Email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(this.data.email)) {
      throw new Error('Validation failed: invalid email format');
    }

    // Password strength validation
    if (this.data.password && this.data.password.length < 8) {
      throw new Error('Validation failed: password must be at least 8 characters');
    }

    // Role validation
    const validRoles = ['student', 'instructor', 'researcher', 'admin'];
    if (!validRoles.includes(this.data.role)) {
      throw new Error('Validation failed: invalid role');
    }

    return true;
  }

  async save() {
    this.updatedAt = new Date();
    return this;
  }

  toJSON() {
    const userObject = { ...this.data };
    delete userObject.password;
    userObject._id = this._id;
    userObject.createdAt = this.createdAt;
    userObject.updatedAt = this.updatedAt;
    return userObject;
  }
}

describe('User Model', () => {
  let mockUser;

  beforeEach(() => {
    mockUser = testUsers.student;
  });

  describe('Validation', () => {
    it('should validate a valid user', () => {
      const user = new MockUser(mockUser);
      expect(() => user.validate()).not.toThrow();
    });

    it('should require name field', () => {
      const invalidData = { ...mockUser };
      delete invalidData.name;
      
      const user = new MockUser(invalidData);
      expect(() => user.validate()).toThrow('name is required');
    });

    it('should require email field', () => {
      const invalidData = { ...mockUser };
      delete invalidData.email;
      
      const user = new MockUser(invalidData);
      expect(() => user.validate()).toThrow('email is required');
    });

    it('should validate email format', () => {
      const invalidEmails = [
        'invalid-email',
        '@example.com',
        'user@',
        'user.example.com',
        'user @example.com'
      ];

      invalidEmails.forEach(email => {
        const invalidData = { ...mockUser, email };
        const user = new MockUser(invalidData);
        expect(() => user.validate()).toThrow('invalid email format');
      });
    });

    it('should accept valid email formats', () => {
      const validEmails = [
        'user@example.com',
        'test.user@university.edu',
        'user+tag@domain.co.uk',
        'user123@sub.domain.org'
      ];

      validEmails.forEach(email => {
        const validData = { ...mockUser, email };
        const user = new MockUser(validData);
        expect(() => user.validate()).not.toThrow();
      });
    });

    it('should require password field', () => {
      const invalidData = { ...mockUser };
      delete invalidData.password;
      
      const user = new MockUser(invalidData);
      expect(() => user.validate()).toThrow('password is required');
    });

    it('should validate password length', () => {
      const shortPassword = { ...mockUser, password: '1234567' };
      const user = new MockUser(shortPassword);
      expect(() => user.validate()).toThrow('password must be at least 8 characters');
    });

    it('should require role field', () => {
      const invalidData = { ...mockUser };
      delete invalidData.role;
      
      const user = new MockUser(invalidData);
      expect(() => user.validate()).toThrow('role is required');
    });

    it('should validate user roles', () => {
      const invalidRole = { ...mockUser, role: 'invalid_role' };
      const user = new MockUser(invalidRole);
      expect(() => user.validate()).toThrow('invalid role');
    });

    it('should accept valid user roles', () => {
      const validRoles = ['student', 'instructor', 'researcher', 'admin'];
      
      validRoles.forEach(role => {
        const validData = { ...mockUser, role };
        const user = new MockUser(validData);
        expect(() => user.validate()).not.toThrow();
      });
    });
  });

  describe('Password Handling', () => {
    it('should hash password on creation', async () => {
      const user = await MockUser.create(mockUser);
      
      expect(user.data.password).toBeDefined();
      expect(user.data.password).not.toBe(mockUser.password);
      expect(user.data.password.length).toBeGreaterThan(mockUser.password.length);
    });

    it('should compare passwords correctly', async () => {
      const user = await MockUser.create(mockUser);
      
      const isValid = await user.comparePassword(mockUser.password);
      const isInvalid = await user.comparePassword('wrong-password');
      
      expect(isValid).toBe(true);
      expect(isInvalid).toBe(false);
    });

    it('should handle missing password in comparison', async () => {
      const userWithoutPassword = new MockUser({ ...mockUser });
      delete userWithoutPassword.data.password;
      
      const result = await userWithoutPassword.comparePassword('any-password');
      expect(result).toBe(false);
    });
  });

  describe('JWT Token Generation', () => {
    it('should generate valid JWT token', () => {
      const user = new MockUser(mockUser);
      const token = user.generateToken();
      
      expect(token).toBeDefined();
      expect(typeof token).toBe('string');
      expect(token.split('.').length).toBe(3); // JWT has 3 parts
    });

    it('should include user data in token', () => {
      const user = new MockUser(mockUser);
      const token = user.generateToken();
      
      const decoded = jwt.verify(token, process.env.JWT_SECRET);
      
      expect(decoded.id).toBe(user._id.toString());
      expect(decoded.email).toBe(mockUser.email);
      expect(decoded.role).toBe(mockUser.role);
    });

    it('should set token expiration', () => {
      const user = new MockUser(mockUser);
      const token = user.generateToken();
      
      const decoded = jwt.verify(token, process.env.JWT_SECRET);
      
      expect(decoded.exp).toBeDefined();
      expect(decoded.iat).toBeDefined();
      expect(decoded.exp - decoded.iat).toBe(7 * 24 * 60 * 60); // 7 days in seconds
    });
  });

  describe('Permissions', () => {
    it('should grant admin full permissions', () => {
      const adminUser = new MockUser(testUsers.admin);
      const permissions = ['manage_users', 'system_config', 'data_export', 'read', 'write', 'moderate'];
      
      permissions.forEach(permission => {
        expect(adminUser.hasPermission(permission)).toBe(true);
      });
    });

    it('should grant instructor appropriate permissions', () => {
      const instructorUser = new MockUser(testUsers.instructor);
      
      expect(instructorUser.hasPermission('read')).toBe(true);
      expect(instructorUser.hasPermission('write')).toBe(true);
      expect(instructorUser.hasPermission('moderate')).toBe(true);
      expect(instructorUser.hasPermission('export')).toBe(true);
      expect(instructorUser.hasPermission('manage_users')).toBe(false);
    });

    it('should grant student basic permissions', () => {
      const studentUser = new MockUser(testUsers.student);
      
      expect(studentUser.hasPermission('read')).toBe(true);
      expect(studentUser.hasPermission('write')).toBe(true);
      expect(studentUser.hasPermission('moderate')).toBe(false);
      expect(studentUser.hasPermission('export')).toBe(false);
    });

    it('should deny unknown permissions', () => {
      const user = new MockUser(mockUser);
      expect(user.hasPermission('unknown_permission')).toBe(false);
    });
  });

  describe('Project Access', () => {
    it('should allow admin access to all projects', () => {
      const adminUser = new MockUser(testUsers.admin);
      const project = { permissions: { student: ['read'] } };
      
      expect(adminUser.canAccessProject(project)).toBe(true);
    });

    it('should check role-based project permissions', () => {
      const studentUser = new MockUser(testUsers.student);
      const project = { 
        permissions: { 
          student: ['read', 'write'],
          instructor: ['read', 'write', 'moderate']
        } 
      };
      
      expect(studentUser.canAccessProject(project)).toBe(true);
    });

    it('should deny access without proper permissions', () => {
      const studentUser = new MockUser(testUsers.student);
      const project = { 
        permissions: { 
          instructor: ['read', 'write', 'moderate']
        } 
      };
      
      expect(studentUser.canAccessProject(project)).toBe(false);
    });

    it('should handle projects without permissions', () => {
      const studentUser = new MockUser(testUsers.student);
      const project = {};
      
      expect(studentUser.canAccessProject(project)).toBe(false);
    });
  });

  describe('User Creation and Queries', () => {
    it('should create user with hashed password', async () => {
      const user = await MockUser.create(mockUser);
      
      expect(user._id).toBeValidObjectId();
      expect(user.data.email).toBe(mockUser.email);
      expect(user.data.password).not.toBe(mockUser.password);
    });

    it('should find user by ID', async () => {
      const testId = new mongoose.Types.ObjectId();
      const user = await MockUser.findById(testId);
      
      expect(user).toBeDefined();
      expect(user._id).toBeValidObjectId();
    });

    it('should find user by email', async () => {
      const user = await MockUser.findOne({ email: 'existing@example.com' });
      expect(user).toBeDefined();
      expect(user.data.email).toBe('existing@example.com');
    });

    it('should return null for non-existent user', async () => {
      const user = await MockUser.findOne({ email: 'nonexistent@example.com' });
      expect(user).toBeNull();
    });
  });

  describe('JSON Serialization', () => {
    it('should exclude password from JSON output', () => {
      const user = new MockUser(mockUser);
      const json = user.toJSON();
      
      expect(json.password).toBeUndefined();
      expect(json.name).toBe(mockUser.name);
      expect(json.email).toBe(mockUser.email);
      expect(json.role).toBe(mockUser.role);
    });

    it('should include timestamps in JSON output', () => {
      const user = new MockUser(mockUser);
      const json = user.toJSON();
      
      expect(json.createdAt).toBeInstanceOf(Date);
      expect(json.updatedAt).toBeInstanceOf(Date);
      expect(json._id).toBeValidObjectId();
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty profile object', () => {
      const userWithEmptyProfile = { ...mockUser, profile: {} };
      const user = new MockUser(userWithEmptyProfile);
      
      expect(() => user.validate()).not.toThrow();
      expect(user.data.profile).toEqual({});
    });

    it('should handle missing optional fields', () => {
      const minimalUser = {
        name: 'Test User',
        email: 'test@example.com',
        password: 'password123',
        role: 'student'
      };
      
      const user = new MockUser(minimalUser);
      expect(() => user.validate()).not.toThrow();
    });

    it('should handle unicode characters in name', () => {
      const unicodeUser = { 
        ...mockUser, 
        name: 'José María García-López' 
      };
      
      const user = new MockUser(unicodeUser);
      expect(() => user.validate()).not.toThrow();
      expect(user.data.name).toBe('José María García-López');
    });

    it('should handle special characters in institution', () => {
      const universityUser = { 
        ...mockUser, 
        institution: 'University of California, San Francisco (UCSF)' 
      };
      
      const user = new MockUser(universityUser);
      expect(user.data.institution).toBe('University of California, San Francisco (UCSF)');
    });
  });
});