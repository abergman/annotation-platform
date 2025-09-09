/**
 * WebSocket Authentication Middleware
 * 
 * Handles authentication and authorization for WebSocket connections
 */

import jwt from 'jsonwebtoken';
import { setupLogging } from '../utils/logger.js';

const logger = setupLogging('websocket-auth');

/**
 * Authentication middleware for Socket.IO connections
 * Validates JWT tokens and attaches user information to socket
 */
export const authenticate = async (socket, next) => {
  try {
    // Extract token from handshake auth or query
    const token = socket.handshake.auth?.token || 
                  socket.handshake.query?.token ||
                  socket.request.headers.authorization?.replace('Bearer ', '');

    if (!token) {
      logger.warn(`Authentication failed - no token provided for socket ${socket.id}`);
      return next(new Error('Authentication token required'));
    }

    // Verify JWT token
    const decoded = jwt.verify(token, process.env.JWT_SECRET || 'your-secret-key');
    
    if (!decoded.userId) {
      logger.warn(`Authentication failed - invalid token payload for socket ${socket.id}`);
      return next(new Error('Invalid token payload'));
    }

    // Fetch user details from the main API
    const user = await fetchUserDetails(decoded.userId, token);
    if (!user) {
      logger.warn(`Authentication failed - user not found: ${decoded.userId}`);
      return next(new Error('User not found'));
    }

    // Attach user info to socket
    socket.user = {
      id: user.id,
      email: user.email,
      username: user.username,
      role: user.role,
      permissions: user.permissions || []
    };

    // Log successful authentication
    logger.info(`User authenticated: ${user.username} (${user.id}) - Socket: ${socket.id}`);
    
    next();
  } catch (error) {
    if (error.name === 'JsonWebTokenError') {
      logger.warn(`JWT verification failed for socket ${socket.id}: ${error.message}`);
      return next(new Error('Invalid authentication token'));
    }
    
    if (error.name === 'TokenExpiredError') {
      logger.warn(`Expired token for socket ${socket.id}`);
      return next(new Error('Authentication token expired'));
    }

    logger.error(`Authentication error for socket ${socket.id}:`, error);
    return next(new Error('Authentication failed'));
  }
};

/**
 * Authorization middleware for specific room/project access
 */
export const authorizeProjectAccess = (requiredRole = 'user') => {
  return async (socket, projectId, next) => {
    try {
      const user = socket.user;
      
      if (!user) {
        return next(new Error('User not authenticated'));
      }

      // Check if user has access to the project
      const hasAccess = await validateProjectAccess(user.id, projectId, user.permissions);
      
      if (!hasAccess) {
        logger.warn(`Access denied to project ${projectId} for user ${user.username}`);
        return next(new Error('Insufficient permissions for this project'));
      }

      // Check role requirements
      if (requiredRole && !hasRequiredRole(user.role, requiredRole)) {
        logger.warn(`Role access denied to project ${projectId} for user ${user.username} (role: ${user.role}, required: ${requiredRole})`);
        return next(new Error('Insufficient role permissions'));
      }

      logger.debug(`Access granted to project ${projectId} for user ${user.username}`);
      next();
    } catch (error) {
      logger.error(`Authorization error for project ${projectId}:`, error);
      next(new Error('Authorization failed'));
    }
  };
};

/**
 * Middleware to rate limit WebSocket events per user
 */
export const rateLimitEvents = (maxEvents = 100, windowMs = 60000) => {
  const userEventCounts = new Map();

  return (socket, next) => {
    const userId = socket.user?.id;
    if (!userId) return next();

    const now = Date.now();
    const userKey = userId;
    
    // Clean up expired windows
    if (userEventCounts.has(userKey)) {
      const userData = userEventCounts.get(userKey);
      userData.events = userData.events.filter(timestamp => now - timestamp < windowMs);
    }

    // Initialize or get user data
    const userData = userEventCounts.get(userKey) || { events: [], blocked: false };
    
    // Check if user is currently blocked
    if (userData.blocked && userData.blockExpiry > now) {
      return next(new Error('Rate limit exceeded - temporarily blocked'));
    }

    // Add current event
    userData.events.push(now);
    
    // Check rate limit
    if (userData.events.length > maxEvents) {
      userData.blocked = true;
      userData.blockExpiry = now + windowMs;
      userEventCounts.set(userKey, userData);
      
      logger.warn(`Rate limit exceeded for user ${socket.user.username} (${userId})`);
      return next(new Error('Rate limit exceeded'));
    }

    userEventCounts.set(userKey, userData);
    next();
  };
};

/**
 * Fetch user details from the main FastAPI backend
 */
async function fetchUserDetails(userId, token) {
  try {
    const response = await fetch(`${process.env.API_URL || 'http://localhost:8000'}/api/users/${userId}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      logger.warn(`Failed to fetch user details for ${userId}: ${response.status}`);
      return null;
    }

    return await response.json();
  } catch (error) {
    logger.error(`Error fetching user details for ${userId}:`, error);
    return null;
  }
}

/**
 * Validate if user has access to a specific project
 */
async function validateProjectAccess(userId, projectId, userPermissions = []) {
  try {
    // Check if user has global admin permissions
    if (userPermissions.includes('admin') || userPermissions.includes('super_admin')) {
      return true;
    }

    // Call FastAPI backend to check project access
    const response = await fetch(
      `${process.env.API_URL || 'http://localhost:8000'}/api/projects/${projectId}/members/${userId}`,
      {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json'
        }
      }
    );

    return response.ok;
  } catch (error) {
    logger.error(`Error validating project access for user ${userId}, project ${projectId}:`, error);
    return false;
  }
}

/**
 * Check if user has required role
 */
function hasRequiredRole(userRole, requiredRole) {
  const roleHierarchy = {
    'admin': 4,
    'moderator': 3,
    'annotator': 2,
    'user': 1,
    'guest': 0
  };

  const userLevel = roleHierarchy[userRole] || 0;
  const requiredLevel = roleHierarchy[requiredRole] || 1;

  return userLevel >= requiredLevel;
}

/**
 * Extract user IP address for logging and rate limiting
 */
export function getUserIP(socket) {
  return socket.request.headers['x-forwarded-for'] || 
         socket.request.headers['x-real-ip'] || 
         socket.request.connection.remoteAddress || 
         socket.handshake.address;
}

/**
 * Create secure room ID with user validation
 */
export function createSecureRoomId(projectId, textId = null, userId) {
  const baseRoomId = textId ? `project:${projectId}:text:${textId}` : `project:${projectId}`;
  
  // Add hash for additional security (prevents room enumeration)
  const crypto = require('crypto');
  const hash = crypto.createHash('sha256')
    .update(`${baseRoomId}:${process.env.ROOM_SALT || 'default-salt'}`)
    .digest('hex')
    .substring(0, 8);
  
  return `${baseRoomId}:${hash}`;
}

export default {
  authenticate,
  authorizeProjectAccess,
  rateLimitEvents,
  getUserIP,
  createSecureRoomId
};