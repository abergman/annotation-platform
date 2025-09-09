/**
 * Custom Error Classes for Real-time WebSocket System
 * 
 * Provides structured error handling with proper error codes and context
 */

/**
 * Base WebSocket Error
 */
export class WebSocketError extends Error {
  constructor(message, code = 'WEBSOCKET_ERROR', context = {}) {
    super(message);
    this.name = 'WebSocketError';
    this.code = code;
    this.context = context;
    this.timestamp = new Date().toISOString();
    
    // Maintain proper stack trace
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, this.constructor);
    }
  }

  toJSON() {
    return {
      name: this.name,
      message: this.message,
      code: this.code,
      context: this.context,
      timestamp: this.timestamp,
      stack: this.stack
    };
  }
}

/**
 * Authentication Error
 */
export class AuthenticationError extends WebSocketError {
  constructor(message, context = {}) {
    super(message, 'AUTH_ERROR', context);
    this.name = 'AuthenticationError';
  }
}

/**
 * Authorization Error
 */
export class AuthorizationError extends WebSocketError {
  constructor(message, context = {}) {
    super(message, 'AUTHZ_ERROR', context);
    this.name = 'AuthorizationError';
  }
}

/**
 * Validation Error
 */
export class ValidationError extends WebSocketError {
  constructor(message, field = null, value = null, context = {}) {
    super(message, 'VALIDATION_ERROR', { field, value, ...context });
    this.name = 'ValidationError';
    this.field = field;
    this.value = value;
  }
}

/**
 * Conflict Error
 */
export class ConflictError extends WebSocketError {
  constructor(message, conflictType = 'unknown', context = {}) {
    super(message, 'CONFLICT_ERROR', { conflictType, ...context });
    this.name = 'ConflictError';
    this.conflictType = conflictType;
  }
}

/**
 * Rate Limit Error
 */
export class RateLimitError extends WebSocketError {
  constructor(message, limit = 0, window = 0, context = {}) {
    super(message, 'RATE_LIMIT_ERROR', { limit, window, ...context });
    this.name = 'RateLimitError';
    this.limit = limit;
    this.window = window;
  }
}

/**
 * Connection Error
 */
export class ConnectionError extends WebSocketError {
  constructor(message, reason = 'unknown', context = {}) {
    super(message, 'CONNECTION_ERROR', { reason, ...context });
    this.name = 'ConnectionError';
    this.reason = reason;
  }
}

/**
 * Room Error
 */
export class RoomError extends WebSocketError {
  constructor(message, roomId = null, context = {}) {
    super(message, 'ROOM_ERROR', { roomId, ...context });
    this.name = 'RoomError';
    this.roomId = roomId;
  }
}

/**
 * Annotation Error
 */
export class AnnotationError extends WebSocketError {
  constructor(message, annotationId = null, context = {}) {
    super(message, 'ANNOTATION_ERROR', { annotationId, ...context });
    this.name = 'AnnotationError';
    this.annotationId = annotationId;
  }
}

/**
 * Operational Transform Error
 */
export class OperationalTransformError extends WebSocketError {
  constructor(message, operation = null, context = {}) {
    super(message, 'TRANSFORM_ERROR', { operation, ...context });
    this.name = 'OperationalTransformError';
    this.operation = operation;
  }
}

/**
 * Message Queue Error
 */
export class MessageQueueError extends WebSocketError {
  constructor(message, queueType = null, context = {}) {
    super(message, 'QUEUE_ERROR', { queueType, ...context });
    this.name = 'MessageQueueError';
    this.queueType = queueType;
  }
}

/**
 * Presence Error
 */
export class PresenceError extends WebSocketError {
  constructor(message, userId = null, context = {}) {
    super(message, 'PRESENCE_ERROR', { userId, ...context });
    this.name = 'PresenceError';
    this.userId = userId;
  }
}

/**
 * Notification Error
 */
export class NotificationError extends WebSocketError {
  constructor(message, notificationType = null, context = {}) {
    super(message, 'NOTIFICATION_ERROR', { notificationType, ...context });
    this.name = 'NotificationError';
    this.notificationType = notificationType;
  }
}

/**
 * Cursor Management Error
 */
export class CursorError extends WebSocketError {
  constructor(message, cursorType = null, context = {}) {
    super(message, 'CURSOR_ERROR', { cursorType, ...context });
    this.name = 'CursorError';
    this.cursorType = cursorType;
  }
}

/**
 * Error Handler Utility
 */
export class ErrorHandler {
  constructor(logger) {
    this.logger = logger;
    this.errorCounts = new Map();
    this.errorHistory = [];
    this.maxHistorySize = 1000;
  }

  /**
   * Handle and log error with context
   */
  handle(error, context = {}) {
    const errorInfo = {
      name: error.name || 'Error',
      message: error.message,
      code: error.code || 'UNKNOWN_ERROR',
      context: { ...error.context, ...context },
      timestamp: new Date().toISOString(),
      stack: error.stack
    };

    // Count error occurrences
    const errorKey = `${error.name}:${error.code}`;
    this.errorCounts.set(errorKey, (this.errorCounts.get(errorKey) || 0) + 1);

    // Add to history
    this.errorHistory.push(errorInfo);
    if (this.errorHistory.length > this.maxHistorySize) {
      this.errorHistory.shift();
    }

    // Log based on error type
    if (error instanceof AuthenticationError || error instanceof AuthorizationError) {
      this.logger.security(error.message, errorInfo);
    } else if (error instanceof ValidationError) {
      this.logger.warn(`Validation Error: ${error.message}`, errorInfo);
    } else if (error instanceof ConflictError) {
      this.logger.conflict(error.conflictType, errorInfo);
    } else if (error instanceof RateLimitError) {
      this.logger.warn(`Rate Limit Exceeded: ${error.message}`, errorInfo);
    } else {
      this.logger.error(`${error.name}: ${error.message}`, errorInfo);
    }

    return errorInfo;
  }

  /**
   * Create error response for client
   */
  createErrorResponse(error, includeStack = false) {
    const response = {
      error: true,
      code: error.code || 'UNKNOWN_ERROR',
      message: error.message,
      timestamp: new Date().toISOString()
    };

    // Add context if available
    if (error.context && Object.keys(error.context).length > 0) {
      response.context = error.context;
    }

    // Include stack trace only in development
    if (includeStack && process.env.NODE_ENV === 'development') {
      response.stack = error.stack;
    }

    return response;
  }

  /**
   * Get error statistics
   */
  getErrorStats() {
    const now = new Date();
    const oneHourAgo = new Date(now.getTime() - 60 * 60 * 1000);
    const oneDayAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);

    const recentErrors = this.errorHistory.filter(err => 
      new Date(err.timestamp) > oneHourAgo
    );

    const dailyErrors = this.errorHistory.filter(err => 
      new Date(err.timestamp) > oneDayAgo
    );

    const errorsByType = {};
    this.errorHistory.forEach(err => {
      errorsByType[err.name] = (errorsByType[err.name] || 0) + 1;
    });

    return {
      total: this.errorHistory.length,
      recentHour: recentErrors.length,
      recentDay: dailyErrors.length,
      byType: errorsByType,
      topErrors: Array.from(this.errorCounts.entries())
        .sort((a, b) => b[1] - a[1])
        .slice(0, 10)
        .map(([key, count]) => ({ error: key, count })),
      timestamp: now.toISOString()
    };
  }

  /**
   * Clear error history
   */
  clearHistory() {
    this.errorHistory = [];
    this.errorCounts.clear();
  }
}

/**
 * Error Recovery Strategies
 */
export class ErrorRecovery {
  static async retryWithBackoff(operation, maxAttempts = 3, baseDelay = 1000) {
    let lastError;
    
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      try {
        return await operation();
      } catch (error) {
        lastError = error;
        
        if (attempt === maxAttempts) {
          throw lastError;
        }
        
        // Exponential backoff
        const delay = baseDelay * Math.pow(2, attempt - 1);
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
    
    throw lastError;
  }

  static async circuitBreaker(operation, threshold = 5, timeout = 60000) {
    if (!this.circuitBreakerState) {
      this.circuitBreakerState = {
        failures: 0,
        lastFailureTime: null,
        state: 'CLOSED' // CLOSED, OPEN, HALF_OPEN
      };
    }

    const state = this.circuitBreakerState;

    // Check if circuit should be half-open
    if (state.state === 'OPEN' && Date.now() - state.lastFailureTime > timeout) {
      state.state = 'HALF_OPEN';
    }

    // Reject if circuit is open
    if (state.state === 'OPEN') {
      throw new WebSocketError('Circuit breaker is OPEN', 'CIRCUIT_BREAKER_OPEN');
    }

    try {
      const result = await operation();
      
      // Reset on success
      if (state.state === 'HALF_OPEN') {
        state.state = 'CLOSED';
        state.failures = 0;
      }
      
      return result;
    } catch (error) {
      state.failures++;
      state.lastFailureTime = Date.now();
      
      // Open circuit if threshold reached
      if (state.failures >= threshold) {
        state.state = 'OPEN';
      }
      
      throw error;
    }
  }
}

/**
 * Error Validation Helpers
 */
export function isRetryableError(error) {
  const retryableCodes = [
    'CONNECTION_ERROR',
    'TIMEOUT_ERROR',
    'TEMPORARY_ERROR',
    'QUEUE_ERROR'
  ];
  
  return retryableCodes.includes(error.code);
}

export function isSecurityError(error) {
  return error instanceof AuthenticationError || 
         error instanceof AuthorizationError ||
         error.code === 'SECURITY_ERROR';
}

export function isUserError(error) {
  return error instanceof ValidationError ||
         error instanceof RateLimitError ||
         error.code === 'USER_ERROR';
}

/**
 * Error Middleware for Express/Socket.IO
 */
export function createErrorMiddleware(logger) {
  const errorHandler = new ErrorHandler(logger);
  
  return (error, req, res, next) => {
    const errorInfo = errorHandler.handle(error, {
      url: req.url,
      method: req.method,
      userAgent: req.headers['user-agent'],
      ip: req.ip
    });

    // Send appropriate error response
    const statusCode = getHttpStatusCode(error);
    const response = errorHandler.createErrorResponse(error, 
      process.env.NODE_ENV === 'development'
    );

    res.status(statusCode).json(response);
  };
}

/**
 * Socket.IO Error Handler
 */
export function createSocketErrorHandler(logger) {
  const errorHandler = new ErrorHandler(logger);
  
  return (socket, error, context = {}) => {
    const errorInfo = errorHandler.handle(error, {
      socketId: socket.id,
      userId: socket.user?.id,
      ...context
    });

    const response = errorHandler.createErrorResponse(error);
    socket.emit('error', response);
    
    return errorInfo;
  };
}

/**
 * Get HTTP status code from error
 */
function getHttpStatusCode(error) {
  if (error instanceof AuthenticationError) return 401;
  if (error instanceof AuthorizationError) return 403;
  if (error instanceof ValidationError) return 400;
  if (error instanceof ConflictError) return 409;
  if (error instanceof RateLimitError) return 429;
  if (error instanceof RoomError && error.code === 'ROOM_NOT_FOUND') return 404;
  
  return 500; // Internal Server Error
}

export default {
  WebSocketError,
  AuthenticationError,
  AuthorizationError,
  ValidationError,
  ConflictError,
  RateLimitError,
  ConnectionError,
  RoomError,
  AnnotationError,
  OperationalTransformError,
  MessageQueueError,
  PresenceError,
  NotificationError,
  CursorError,
  ErrorHandler,
  ErrorRecovery,
  isRetryableError,
  isSecurityError,
  isUserError,
  createErrorMiddleware,
  createSocketErrorHandler
};