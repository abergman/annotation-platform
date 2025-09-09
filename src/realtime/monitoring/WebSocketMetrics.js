/**
 * WebSocket Metrics and Monitoring System
 * 
 * Tracks performance, usage statistics, and health metrics for the WebSocket system
 */

import { setupLogging } from '../utils/logger.js';

const logger = setupLogging('websocket-metrics');

export class WebSocketMetrics {
  constructor(options = {}) {
    this.startTime = Date.now();
    this.metrics = {
      connections: {
        total: 0,
        active: 0,
        peak: 0,
        byRoom: new Map(),
        byUser: new Map()
      },
      messages: {
        total: 0,
        byType: new Map(),
        byRoom: new Map(),
        errors: 0,
        ratePerSecond: 0
      },
      annotations: {
        created: 0,
        updated: 0,
        deleted: 0,
        conflicts: 0,
        resolved: 0
      },
      performance: {
        averageResponseTime: 0,
        maxResponseTime: 0,
        operationTimes: new Map(),
        systemLoad: 0
      },
      rooms: {
        total: 0,
        active: new Set(),
        byProject: new Map()
      },
      errors: {
        total: 0,
        byType: new Map(),
        critical: 0
      }
    };

    // Sliding window for rate calculations
    this.messageWindow = [];
    this.windowSize = 60; // 60 seconds
    this.cleanupInterval = null;
    
    // Performance sampling
    this.responseTimes = [];
    this.maxSamples = 1000;
    
    // Initialize background monitoring
    this.startBackgroundMonitoring();
  }

  /**
   * Record new connection
   */
  recordConnection(userId, socketId, roomId = null) {
    this.metrics.connections.total++;
    this.metrics.connections.active++;
    this.metrics.connections.peak = Math.max(
      this.metrics.connections.peak, 
      this.metrics.connections.active
    );

    // Track by user
    if (userId) {
      if (!this.metrics.connections.byUser.has(userId)) {
        this.metrics.connections.byUser.set(userId, { connections: 0, rooms: new Set() });
      }
      const userMetrics = this.metrics.connections.byUser.get(userId);
      userMetrics.connections++;
      if (roomId) userMetrics.rooms.add(roomId);
    }

    // Track by room
    if (roomId) {
      if (!this.metrics.connections.byRoom.has(roomId)) {
        this.metrics.connections.byRoom.set(roomId, 0);
      }
      this.metrics.connections.byRoom.set(roomId, 
        this.metrics.connections.byRoom.get(roomId) + 1
      );
    }

    logger.debug('Connection recorded', { userId, socketId, roomId, 
      activeConnections: this.metrics.connections.active });
  }

  /**
   * Record disconnection
   */
  recordDisconnection(userId, reason = 'unknown', roomId = null) {
    this.metrics.connections.active = Math.max(0, this.metrics.connections.active - 1);

    // Update room metrics
    if (roomId && this.metrics.connections.byRoom.has(roomId)) {
      const current = this.metrics.connections.byRoom.get(roomId);
      if (current <= 1) {
        this.metrics.connections.byRoom.delete(roomId);
      } else {
        this.metrics.connections.byRoom.set(roomId, current - 1);
      }
    }

    logger.debug('Disconnection recorded', { userId, reason, roomId, 
      activeConnections: this.metrics.connections.active });
  }

  /**
   * Record message event
   */
  recordMessage(type, roomId = null, userId = null, responseTime = null) {
    const timestamp = Date.now();
    
    this.metrics.messages.total++;
    
    // Track by type
    const currentCount = this.metrics.messages.byType.get(type) || 0;
    this.metrics.messages.byType.set(type, currentCount + 1);
    
    // Track by room
    if (roomId) {
      const roomCount = this.metrics.messages.byRoom.get(roomId) || 0;
      this.metrics.messages.byRoom.set(roomId, roomCount + 1);
    }

    // Add to sliding window for rate calculation
    this.messageWindow.push(timestamp);
    this.cleanMessageWindow();

    // Track response time
    if (responseTime !== null) {
      this.recordResponseTime(type, responseTime);
    }

    logger.debug('Message recorded', { type, roomId, userId, responseTime });
  }

  /**
   * Record annotation event
   */
  recordAnnotationEvent(event, roomId = null, userId = null) {
    switch (event) {
      case 'create':
        this.metrics.annotations.created++;
        break;
      case 'update':
        this.metrics.annotations.updated++;
        break;
      case 'delete':
        this.metrics.annotations.deleted++;
        break;
      case 'conflict':
        this.metrics.annotations.conflicts++;
        break;
      case 'resolved':
        this.metrics.annotations.resolved++;
        break;
    }

    logger.debug('Annotation event recorded', { event, roomId, userId });
  }

  /**
   * Record room activity
   */
  recordRoomJoin(roomId, userId) {
    this.metrics.rooms.active.add(roomId);
    this.metrics.rooms.total = Math.max(this.metrics.rooms.total, this.metrics.rooms.active.size);
    
    logger.debug('Room join recorded', { roomId, userId });
  }

  recordRoomLeave(roomId, userId) {
    // Note: We don't immediately remove from active set as other users might still be in the room
    logger.debug('Room leave recorded', { roomId, userId });
  }

  /**
   * Record text operation
   */
  recordTextOperation(roomId, userId, operationType = 'unknown') {
    this.recordMessage(`text-operation-${operationType}`, roomId, userId);
  }

  /**
   * Record error
   */
  recordError(errorType, userId = null, severity = 'normal') {
    this.metrics.errors.total++;
    
    const currentCount = this.metrics.errors.byType.get(errorType) || 0;
    this.metrics.errors.byType.set(errorType, currentCount + 1);
    
    if (severity === 'critical') {
      this.metrics.errors.critical++;
    }

    logger.warn('Error recorded', { errorType, userId, severity });
  }

  /**
   * Record response time
   */
  recordResponseTime(operation, timeMs) {
    this.responseTimes.push(timeMs);
    
    // Keep only recent samples
    if (this.responseTimes.length > this.maxSamples) {
      this.responseTimes.shift();
    }

    // Update performance metrics
    this.metrics.performance.maxResponseTime = Math.max(
      this.metrics.performance.maxResponseTime, 
      timeMs
    );
    
    this.metrics.performance.averageResponseTime = 
      this.responseTimes.reduce((sum, time) => sum + time, 0) / this.responseTimes.length;

    // Track by operation type
    if (!this.metrics.performance.operationTimes.has(operation)) {
      this.metrics.performance.operationTimes.set(operation, []);
    }
    
    const operationTimes = this.metrics.performance.operationTimes.get(operation);
    operationTimes.push(timeMs);
    
    // Keep only recent samples per operation
    if (operationTimes.length > 100) {
      operationTimes.shift();
    }
  }

  /**
   * Get current statistics
   */
  getStats() {
    const now = Date.now();
    const uptime = now - this.startTime;
    
    return {
      uptime: uptime,
      timestamp: now,
      connectedUsers: this.metrics.connections.active,
      totalConnections: this.metrics.connections.total,
      peakConnections: this.metrics.connections.peak,
      activeRooms: this.metrics.rooms.active.size,
      totalMessages: this.metrics.messages.total,
      messagesPerSecond: this.calculateMessageRate(),
      annotationEvents: {
        created: this.metrics.annotations.created,
        updated: this.metrics.annotations.updated,
        deleted: this.metrics.annotations.deleted,
        conflicts: this.metrics.annotations.conflicts,
        resolved: this.metrics.annotations.resolved
      },
      performance: {
        averageResponseTime: this.metrics.performance.averageResponseTime.toFixed(2),
        maxResponseTime: this.metrics.performance.maxResponseTime
      },
      errors: {
        total: this.metrics.errors.total,
        critical: this.metrics.errors.critical,
        errorRate: this.calculateErrorRate()
      }
    };
  }

  /**
   * Get detailed statistics
   */
  getDetailedStats() {
    const basicStats = this.getStats();
    
    return {
      ...basicStats,
      messagesByType: Object.fromEntries(this.metrics.messages.byType),
      errorsByType: Object.fromEntries(this.metrics.errors.byType),
      roomActivity: Object.fromEntries(this.metrics.messages.byRoom),
      operationTimes: this.getOperationTimeStats(),
      systemHealth: this.getSystemHealthMetrics(),
      trends: this.getTrendMetrics()
    };
  }

  /**
   * Get operation time statistics
   */
  getOperationTimeStats() {
    const stats = {};
    
    for (const [operation, times] of this.metrics.performance.operationTimes.entries()) {
      if (times.length === 0) continue;
      
      const sorted = [...times].sort((a, b) => a - b);
      const sum = sorted.reduce((a, b) => a + b, 0);
      
      stats[operation] = {
        count: times.length,
        average: (sum / times.length).toFixed(2),
        median: sorted[Math.floor(sorted.length / 2)],
        p95: sorted[Math.floor(sorted.length * 0.95)],
        min: sorted[0],
        max: sorted[sorted.length - 1]
      };
    }
    
    return stats;
  }

  /**
   * Get system health metrics
   */
  getSystemHealthMetrics() {
    const memUsage = process.memoryUsage();
    const cpuUsage = process.cpuUsage();
    
    return {
      memory: {
        rss: Math.round(memUsage.rss / 1024 / 1024), // MB
        heapUsed: Math.round(memUsage.heapUsed / 1024 / 1024), // MB
        heapTotal: Math.round(memUsage.heapTotal / 1024 / 1024), // MB
        external: Math.round(memUsage.external / 1024 / 1024) // MB
      },
      cpu: {
        user: cpuUsage.user,
        system: cpuUsage.system
      },
      uptime: process.uptime(),
      version: process.version
    };
  }

  /**
   * Get trend metrics
   */
  getTrendMetrics() {
    const now = Date.now();
    const oneHourAgo = now - (60 * 60 * 1000);
    const oneDayAgo = now - (24 * 60 * 60 * 1000);
    
    // Messages in last hour vs last day (simplified)
    const recentMessages = this.messageWindow.filter(ts => ts > oneHourAgo).length;
    const hourlyRate = recentMessages; // Messages in last hour
    const dailyEstimate = hourlyRate * 24; // Rough estimate
    
    return {
      hourlyMessageRate: hourlyRate,
      estimatedDailyMessages: dailyEstimate,
      peakConnections: this.metrics.connections.peak,
      conflictRate: this.metrics.annotations.conflicts / Math.max(1, this.metrics.annotations.created),
      errorRate: this.calculateErrorRate()
    };
  }

  /**
   * Calculate current message rate (messages per second)
   */
  calculateMessageRate() {
    const now = Date.now();
    const oneSecondAgo = now - 1000;
    const recentMessages = this.messageWindow.filter(timestamp => timestamp > oneSecondAgo);
    
    this.metrics.messages.ratePerSecond = recentMessages.length;
    return recentMessages.length;
  }

  /**
   * Calculate error rate
   */
  calculateErrorRate() {
    if (this.metrics.messages.total === 0) return 0;
    return (this.metrics.errors.total / this.metrics.messages.total * 100).toFixed(2);
  }

  /**
   * Clean old entries from message window
   */
  cleanMessageWindow() {
    const now = Date.now();
    const windowStart = now - (this.windowSize * 1000);
    this.messageWindow = this.messageWindow.filter(timestamp => timestamp > windowStart);
  }

  /**
   * Start background monitoring
   */
  startBackgroundMonitoring() {
    // Clean up metrics every 5 minutes
    this.cleanupInterval = setInterval(() => {
      this.performCleanup();
    }, 5 * 60 * 1000);

    // Log metrics every minute
    setInterval(() => {
      this.logMetrics();
    }, 60 * 1000);

    logger.info('WebSocket metrics monitoring started');
  }

  /**
   * Perform cleanup of old data
   */
  performCleanup() {
    this.cleanMessageWindow();
    
    // Clean up inactive rooms from metrics
    const activeRoomIds = new Set();
    for (const roomId of this.metrics.connections.byRoom.keys()) {
      if (this.metrics.connections.byRoom.get(roomId) > 0) {
        activeRoomIds.add(roomId);
      }
    }
    this.metrics.rooms.active = activeRoomIds;

    // Clean up old user connections with no active connections
    for (const [userId, userMetrics] of this.metrics.connections.byUser.entries()) {
      if (userMetrics.connections <= 0) {
        this.metrics.connections.byUser.delete(userId);
      }
    }

    logger.debug('Metrics cleanup completed', {
      activeRooms: activeRoomIds.size,
      trackedUsers: this.metrics.connections.byUser.size
    });
  }

  /**
   * Log current metrics
   */
  logMetrics() {
    const stats = this.getStats();
    logger.info('WebSocket Metrics', {
      activeConnections: stats.connectedUsers,
      activeRooms: stats.activeRooms,
      messagesPerSecond: stats.messagesPerSecond,
      averageResponseTime: stats.performance.averageResponseTime,
      errorRate: stats.errors.errorRate
    });
  }

  /**
   * Export metrics for external monitoring systems
   */
  exportMetrics(format = 'json') {
    const stats = this.getDetailedStats();
    
    switch (format) {
      case 'prometheus':
        return this.exportPrometheusFormat(stats);
      case 'json':
      default:
        return JSON.stringify(stats, null, 2);
    }
  }

  /**
   * Export in Prometheus format
   */
  exportPrometheusFormat(stats) {
    const lines = [
      `# HELP websocket_connections_active Current active WebSocket connections`,
      `# TYPE websocket_connections_active gauge`,
      `websocket_connections_active ${stats.connectedUsers}`,
      ``,
      `# HELP websocket_connections_total Total WebSocket connections`,
      `# TYPE websocket_connections_total counter`,
      `websocket_connections_total ${stats.totalConnections}`,
      ``,
      `# HELP websocket_messages_total Total messages processed`,
      `# TYPE websocket_messages_total counter`,
      `websocket_messages_total ${stats.totalMessages}`,
      ``,
      `# HELP websocket_messages_per_second Current message rate`,
      `# TYPE websocket_messages_per_second gauge`,
      `websocket_messages_per_second ${stats.messagesPerSecond}`,
      ``,
      `# HELP websocket_response_time_average Average response time in milliseconds`,
      `# TYPE websocket_response_time_average gauge`,
      `websocket_response_time_average ${stats.performance.averageResponseTime}`,
      ``,
      `# HELP websocket_errors_total Total errors`,
      `# TYPE websocket_errors_total counter`,
      `websocket_errors_total ${stats.errors.total}`
    ];

    return lines.join('\n');
  }

  /**
   * Reset all metrics
   */
  reset() {
    this.startTime = Date.now();
    this.metrics = {
      connections: {
        total: 0,
        active: 0,
        peak: 0,
        byRoom: new Map(),
        byUser: new Map()
      },
      messages: {
        total: 0,
        byType: new Map(),
        byRoom: new Map(),
        errors: 0,
        ratePerSecond: 0
      },
      annotations: {
        created: 0,
        updated: 0,
        deleted: 0,
        conflicts: 0,
        resolved: 0
      },
      performance: {
        averageResponseTime: 0,
        maxResponseTime: 0,
        operationTimes: new Map(),
        systemLoad: 0
      },
      rooms: {
        total: 0,
        active: new Set(),
        byProject: new Map()
      },
      errors: {
        total: 0,
        byType: new Map(),
        critical: 0
      }
    };

    this.messageWindow = [];
    this.responseTimes = [];

    logger.info('WebSocket metrics reset');
  }

  /**
   * Destroy metrics system
   */
  destroy() {
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
    }

    logger.info('WebSocket metrics system destroyed');
  }
}