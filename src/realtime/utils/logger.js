/**
 * Logging Utility for Real-time WebSocket System
 * 
 * Provides structured logging with context and performance tracking
 */

import winston from 'winston';
import path from 'path';

// Global logger instances cache
const loggers = new Map();

/**
 * Setup logging configuration
 */
export function setupLogging(component, options = {}) {
  // Return cached logger if exists
  if (loggers.has(component)) {
    return loggers.get(component);
  }

  const {
    level = process.env.LOG_LEVEL || 'info',
    logDir = process.env.LOG_DIR || 'logs',
    enableConsole = true,
    enableFile = true,
    maxFiles = 7,
    maxSize = '50m'
  } = options;

  // Create custom format for WebSocket logging
  const logFormat = winston.format.combine(
    winston.format.timestamp({
      format: 'YYYY-MM-DD HH:mm:ss.SSS'
    }),
    winston.format.errors({ stack: true }),
    winston.format.json(),
    winston.format.printf(({ timestamp, level, message, component: comp, ...meta }) => {
      const baseInfo = {
        timestamp,
        level: level.toUpperCase(),
        component: comp || component,
        message
      };

      // Add metadata if present
      if (Object.keys(meta).length > 0) {
        baseInfo.meta = meta;
      }

      return JSON.stringify(baseInfo);
    })
  );

  // Console format for development
  const consoleFormat = winston.format.combine(
    winston.format.timestamp({
      format: 'HH:mm:ss.SSS'
    }),
    winston.format.colorize(),
    winston.format.printf(({ timestamp, level, message, component: comp, ...meta }) => {
      const metaStr = Object.keys(meta).length > 0 ? 
        ` ${JSON.stringify(meta)}` : '';
      return `[${timestamp}] ${level} [${comp || component}] ${message}${metaStr}`;
    })
  );

  // Configure transports
  const transports = [];

  // Console transport
  if (enableConsole) {
    transports.push(new winston.transports.Console({
      level,
      format: consoleFormat,
      handleExceptions: true,
      handleRejections: true
    }));
  }

  // File transports
  if (enableFile) {
    // General log file
    transports.push(new winston.transports.File({
      filename: path.join(logDir, `${component}.log`),
      level,
      format: logFormat,
      maxsize: maxSize,
      maxFiles,
      tailable: true,
      handleExceptions: true,
      handleRejections: true
    }));

    // Error log file
    transports.push(new winston.transports.File({
      filename: path.join(logDir, `${component}-error.log`),
      level: 'error',
      format: logFormat,
      maxsize: maxSize,
      maxFiles,
      tailable: true,
      handleExceptions: true,
      handleRejections: true
    }));

    // WebSocket specific metrics log
    if (component.includes('websocket') || component.includes('realtime')) {
      transports.push(new winston.transports.File({
        filename: path.join(logDir, 'websocket-metrics.log'),
        level: 'info',
        format: logFormat,
        maxsize: maxSize,
        maxFiles,
        tailable: true
      }));
    }
  }

  // Create logger instance
  const logger = winston.createLogger({
    level,
    format: logFormat,
    defaultMeta: { component },
    transports,
    exitOnError: false
  });

  // Add custom methods for WebSocket-specific logging
  logger.websocketEvent = function(event, data = {}) {
    this.info(`WebSocket Event: ${event}`, {
      event,
      eventData: data,
      category: 'websocket_event'
    });
  };

  logger.performance = function(operation, duration, metadata = {}) {
    this.info(`Performance: ${operation}`, {
      operation,
      duration: `${duration}ms`,
      ...metadata,
      category: 'performance'
    });
  };

  logger.userAction = function(userId, action, details = {}) {
    this.info(`User Action: ${action}`, {
      userId,
      action,
      ...details,
      category: 'user_action'
    });
  };

  logger.roomActivity = function(roomId, activity, details = {}) {
    this.info(`Room Activity: ${activity}`, {
      roomId,
      activity,
      ...details,
      category: 'room_activity'
    });
  };

  logger.annotationEvent = function(annotationId, event, details = {}) {
    this.info(`Annotation: ${event}`, {
      annotationId,
      event,
      ...details,
      category: 'annotation'
    });
  };

  logger.conflict = function(conflictType, details = {}) {
    this.warn(`Conflict: ${conflictType}`, {
      conflictType,
      ...details,
      category: 'conflict'
    });
  };

  logger.security = function(event, details = {}) {
    this.warn(`Security: ${event}`, {
      securityEvent: event,
      ...details,
      category: 'security'
    });
  };

  // Cache the logger
  loggers.set(component, logger);

  return logger;
}

/**
 * Create a performance timer
 */
export function createPerformanceTimer(component, operation) {
  const logger = setupLogging(component);
  const startTime = performance.now();
  
  return {
    end: (metadata = {}) => {
      const duration = performance.now() - startTime;
      logger.performance(operation, duration.toFixed(2), metadata);
      return duration;
    }
  };
}

/**
 * Request/Response logging middleware
 */
export function createRequestLogger(component) {
  const logger = setupLogging(component);
  
  return (req, res, next) => {
    const startTime = Date.now();
    const requestId = req.headers['x-request-id'] || 
                     `req_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    
    // Add request ID to request
    req.requestId = requestId;
    
    // Log incoming request
    logger.info('HTTP Request', {
      requestId,
      method: req.method,
      url: req.url,
      userAgent: req.headers['user-agent'],
      ip: req.ip || req.connection.remoteAddress,
      category: 'http_request'
    });
    
    // Log response when finished
    res.on('finish', () => {
      const duration = Date.now() - startTime;
      logger.info('HTTP Response', {
        requestId,
        method: req.method,
        url: req.url,
        statusCode: res.statusCode,
        duration: `${duration}ms`,
        category: 'http_response'
      });
    });
    
    next();
  };
}

/**
 * WebSocket connection logger
 */
export function logWebSocketConnection(logger, socket, event, data = {}) {
  const connectionInfo = {
    socketId: socket.id,
    userId: socket.user?.id,
    username: socket.user?.username,
    ip: socket.handshake.address,
    userAgent: socket.handshake.headers['user-agent'],
    timestamp: new Date().toISOString(),
    ...data
  };
  
  logger.websocketEvent(event, connectionInfo);
}

/**
 * Error logger with context
 */
export function logError(logger, error, context = {}) {
  const errorInfo = {
    message: error.message,
    stack: error.stack,
    name: error.name,
    code: error.code,
    ...context,
    timestamp: new Date().toISOString()
  };
  
  logger.error('Error occurred', errorInfo);
}

/**
 * Batch operation logger
 */
export function logBatchOperation(logger, operation, items, results) {
  const stats = {
    operation,
    totalItems: items.length,
    successful: results.filter(r => r.success).length,
    failed: results.filter(r => !r.success).length,
    duration: results.reduce((sum, r) => sum + (r.duration || 0), 0),
    timestamp: new Date().toISOString()
  };
  
  logger.info(`Batch Operation: ${operation}`, {
    ...stats,
    category: 'batch_operation'
  });
}

/**
 * Security event logger
 */
export function logSecurityEvent(logger, event, details = {}) {
  logger.security(event, {
    severity: details.severity || 'medium',
    source: details.source || 'system',
    action: details.action || 'logged',
    timestamp: new Date().toISOString(),
    ...details
  });
}

/**
 * Rate limiting logger
 */
export function logRateLimit(logger, identifier, limit, window) {
  logger.warn('Rate Limit Exceeded', {
    identifier,
    limit,
    window: `${window}ms`,
    category: 'rate_limit',
    timestamp: new Date().toISOString()
  });
}

/**
 * Clean up old log files
 */
export async function cleanupLogs(logDir, maxAge = 30) {
  try {
    const fs = await import('fs/promises');
    const files = await fs.readdir(logDir);
    const now = Date.now();
    const maxAgeMs = maxAge * 24 * 60 * 60 * 1000; // Convert days to milliseconds
    
    let cleanedFiles = 0;
    
    for (const file of files) {
      if (file.endsWith('.log')) {
        const filePath = path.join(logDir, file);
        const stats = await fs.stat(filePath);
        
        if (now - stats.mtime.getTime() > maxAgeMs) {
          await fs.unlink(filePath);
          cleanedFiles++;
        }
      }
    }
    
    if (cleanedFiles > 0) {
      const logger = setupLogging('log-cleanup');
      logger.info(`Cleaned up ${cleanedFiles} old log files`);
    }
    
  } catch (error) {
    const logger = setupLogging('log-cleanup');
    logger.error('Error cleaning up logs:', error);
  }
}

/**
 * Get logger statistics
 */
export function getLoggerStats() {
  const stats = {
    activeLoggers: loggers.size,
    components: Array.from(loggers.keys()),
    timestamp: new Date().toISOString()
  };
  
  return stats;
}

/**
 * Structured data logger for analytics
 */
export function createAnalyticsLogger(component) {
  const logger = setupLogging(`${component}-analytics`);
  
  return {
    track: (event, properties = {}) => {
      logger.info(`Analytics: ${event}`, {
        event,
        properties,
        timestamp: new Date().toISOString(),
        category: 'analytics'
      });
    },
    
    timing: (operation, duration, properties = {}) => {
      logger.info(`Timing: ${operation}`, {
        operation,
        duration: `${duration}ms`,
        properties,
        timestamp: new Date().toISOString(),
        category: 'timing'
      });
    },
    
    counter: (metric, value = 1, properties = {}) => {
      logger.info(`Counter: ${metric}`, {
        metric,
        value,
        properties,
        timestamp: new Date().toISOString(),
        category: 'counter'
      });
    }
  };
}

export default setupLogging;