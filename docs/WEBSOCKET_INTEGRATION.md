# WebSocket Real-time Collaboration System

## Overview

This document describes the comprehensive WebSocket-based real-time collaboration system implemented for the text annotation platform. The system enables multiple users to collaborate simultaneously on annotation projects with real-time synchronization, conflict resolution, and presence awareness.

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Frontend (React)                              │
├─────────────────────────────────────────────────────────────────────────┤
│  useWebSocket Hook  │  Presence UI  │  Cursor Tracking  │ Notifications │
└─────────────────────┬───────────────────────────────────────────────────┘
                      │
                      │ WebSocket Connection
                      │
┌─────────────────────▼───────────────────────────────────────────────────┐
│                    WebSocket Server (Node.js)                          │
├─────────────────────────────────────────────────────────────────────────┤
│ • Room Management      • Presence Tracking    • Cursor Management      │
│ • Annotation Sync      • Operational Transform • Conflict Resolution   │
│ • Notification System  • Message Queuing      • Authentication        │
└─────────────────────┬───────────────────────────────────────────────────┘
                      │
              ┌───────┴────────┐
              │                │
┌─────────────▼──┐  ┌─────────▼──────┐
│   FastAPI      │  │     Redis      │
│   Backend      │  │   (Optional)   │
│                │  │                │
│ • User Auth    │  │ • Scaling      │
│ • Data Persist │  │ • State Sync   │
│ • API Routes   │  │ • Pub/Sub      │
└────────────────┘  └────────────────┘
```

### Core Features

1. **Real-time Annotation Sharing**
   - Live synchronization of annotation creation, updates, and deletions
   - Operational transforms for concurrent editing
   - Conflict detection and resolution

2. **User Presence & Awareness**
   - Real-time user status (online, idle, away)
   - Activity indicators (annotating, viewing, etc.)
   - Join/leave notifications

3. **Live Cursor Tracking**
   - Real-time cursor positions and text selections
   - Visual indicators for active users
   - Color-coded user identification

4. **Collaborative Editing**
   - Operational transforms for text operations
   - Position adjustment for concurrent edits
   - Conflict-free collaborative editing

5. **Smart Notifications**
   - Real-time updates and alerts
   - Priority-based notification system
   - Offline message queuing

6. **Conflict Resolution**
   - Automatic conflict detection
   - Multiple resolution strategies
   - Manual conflict resolution interface

## Implementation Details

### WebSocket Server (`src/websocket-server.js`)

The main WebSocket server handles:
- Socket.IO connections with authentication
- Room-based collaboration spaces
- Event routing and broadcasting
- Integration with FastAPI backend

**Key Events:**
- `join-project`: Join a collaborative room
- `annotation-create/update/delete`: Annotation operations
- `cursor-position`: Real-time cursor tracking
- `text-operation`: Collaborative text editing
- `notification`: Real-time notifications

### Authentication & Authorization

```javascript
// JWT-based authentication
io.use(authenticate); // Middleware validates tokens

// Room-level authorization
socket.on('join-project', async (data) => {
  const hasAccess = await validateProjectAccess(userId, projectId);
  if (!hasAccess) {
    socket.emit('error', { message: 'Unauthorized' });
    return;
  }
  // Join room...
});
```

### Room Management (`src/realtime/managers/RoomManager.js`)

Manages collaborative spaces:
- Dynamic room creation per project/document
- User presence tracking
- Room cleanup and resource management
- Statistics and analytics

```javascript
// Room structure: project:123:text:456
const roomId = textId ? 
  `project:${projectId}:text:${textId}` : 
  `project:${projectId}`;
```

### Presence Management (`src/realtime/managers/PresenceManager.js`)

Tracks user activity and status:
- Online/idle/away status detection
- Activity monitoring (annotating, viewing)
- Automatic status transitions
- Presence analytics

### Annotation Synchronization (`src/realtime/managers/AnnotationManager.js`)

Handles real-time annotation operations:
- Create/update/delete synchronization
- Version control and conflict detection
- Comment threading
- History tracking

### Operational Transforms (`src/realtime/collaboration/OperationalTransform.js`)

Enables conflict-free collaborative editing:
- Transform operations against concurrent changes
- Position adjustment for text operations
- Annotation position maintenance
- State vector synchronization

### Conflict Resolution (`src/realtime/collaboration/ConflictResolver.js`)

Intelligent conflict handling:
- Automatic conflict detection
- Multiple resolution strategies:
  - Last-write-wins
  - First-write-wins
  - Semantic merging
  - User priority-based
  - Voting-based
- Manual resolution interface

### Message Queuing (`src/realtime/queue/MessageQueue.js`)

Reliable message delivery:
- Offline user message queuing
- Priority-based delivery
- Message persistence
- Retry logic with exponential backoff

### Redis Integration (Optional)

For horizontal scaling:
- Distributed state management
- Cross-server message broadcasting
- Session persistence
- Distributed locking

## Frontend Integration

### React Hook (`frontend/src/hooks/useWebSocket.ts`)

```typescript
const [wsState, wsActions] = useWebSocket({
  autoConnect: true,
  reconnectAttempts: 5
});

// Join project room
await wsActions.joinProject('project-123', 'text-456');

// Create annotation
await wsActions.createAnnotation({
  startOffset: 10,
  endOffset: 20,
  text: 'Selected text',
  labels: ['important']
});

// Track cursor position
wsActions.updateCursorPosition({ offset: 25 }, 'text-456');
```

### Real-time UI Components

```typescript
// User presence indicator
const PresenceIndicator = () => {
  const [wsState] = useWebSocket();
  
  return (
    <div className="presence-users">
      {wsState.users.map(user => (
        <UserAvatar 
          key={user.userId}
          user={user}
          status={user.status}
          activity={user.activity}
        />
      ))}
    </div>
  );
};

// Live cursors overlay
const CursorOverlay = () => {
  const [wsState] = useWebSocket();
  
  return (
    <>
      {wsState.cursors.map(cursor => (
        <CursorIndicator
          key={cursor.userId}
          position={cursor.position}
          user={cursor.username}
          color={cursor.color}
        />
      ))}
    </>
  );
};
```

## Configuration

### Environment Variables

```bash
# WebSocket Server
WEBSOCKET_PORT=8001
ENABLE_WEBSOCKETS=true

# Redis (Optional)
REDIS_URL=redis://localhost:6379

# API Integration
API_URL=http://localhost:8000
FRONTEND_URL=http://localhost:5173

# Security
JWT_SECRET=your-secret-key

# Performance
MAX_ROOMS_PER_USER=10
MESSAGE_QUEUE_SIZE=1000
PRESENCE_TIMEOUT=300
```

## Running the System

### Development Setup

1. **Install dependencies:**
```bash
npm install
```

2. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. **Start WebSocket server:**
```bash
npm run websocket:dev
```

4. **Start FastAPI backend:**
```bash
cd src && python main.py
```

5. **Start React frontend:**
```bash
cd frontend && npm run dev
```

### Production Deployment

1. **With Docker:**
```yaml
# docker-compose.yml
services:
  websocket:
    build: .
    command: npm run websocket
    environment:
      - NODE_ENV=production
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis
      
  redis:
    image: redis:alpine
    volumes:
      - redis_data:/data
```

2. **With PM2:**
```bash
pm2 start scripts/start-websocket.js --name websocket-server
```

## Performance & Scaling

### Metrics & Monitoring

The system includes comprehensive metrics:
- Connection statistics
- Message throughput
- Response times
- Error rates
- Resource usage

Access metrics at: `http://localhost:8001/metrics`

### Horizontal Scaling

Enable Redis for multi-server deployment:
1. Set `REDIS_URL` environment variable
2. Configure Redis adapter for Socket.IO
3. Enable pub/sub message broadcasting
4. Use distributed locking for conflicts

### Performance Optimization

- Message throttling for rapid updates
- Connection pooling and reuse
- Efficient data structures for state management
- Background cleanup processes
- Compression for large payloads

## Testing

### Unit Tests

```bash
npm run test:websocket
```

### Integration Tests

Test WebSocket functionality:
```javascript
// Test real-time annotation sync
test('should sync annotations between users', async () => {
  const client1 = createTestClient();
  const client2 = createTestClient();
  
  await client1.joinRoom('project-123');
  await client2.joinRoom('project-123');
  
  const annotation = await client1.createAnnotation({
    text: 'test annotation'
  });
  
  const received = await client2.waitForEvent('annotation-created');
  expect(received.annotation.text).toBe('test annotation');
});
```

### Load Testing

Use Artillery for performance testing:
```yaml
# artillery.yml
config:
  target: 'http://localhost:8001'
  phases:
    - duration: 60
      arrivalRate: 10
scenarios:
  - name: "Real-time collaboration"
    weight: 100
    engine: socketio
```

## Security Considerations

1. **Authentication**
   - JWT token validation
   - Token expiration handling
   - Secure token transmission

2. **Authorization**
   - Room-level access control
   - Operation permissions
   - Rate limiting per user

3. **Data Validation**
   - Input sanitization
   - Schema validation
   - XSS prevention

4. **Network Security**
   - CORS configuration
   - WSS for production
   - Firewall rules

## Troubleshooting

### Common Issues

1. **Connection Failures**
   ```bash
   # Check WebSocket server status
   curl http://localhost:8001/health
   
   # Verify authentication
   # Ensure JWT_SECRET matches between services
   ```

2. **Redis Connection Issues**
   ```bash
   # Test Redis connectivity
   redis-cli ping
   
   # Check Redis logs
   docker logs redis-container
   ```

3. **Performance Issues**
   ```bash
   # Monitor metrics
   curl http://localhost:8001/metrics
   
   # Check resource usage
   npm run websocket -- --inspect
   ```

### Debug Mode

Enable debug logging:
```bash
LOG_LEVEL=debug npm run websocket:dev
```

## API Reference

### WebSocket Events

#### Client → Server

- `join-project`: Join collaborative room
- `leave-project`: Leave room
- `annotation-create`: Create annotation
- `annotation-update`: Update annotation
- `annotation-delete`: Delete annotation
- `cursor-position`: Update cursor position
- `text-selection`: Update text selection
- `text-operation`: Collaborative text edit
- `comment-create`: Add comment
- `notification-read`: Mark notification read

#### Server → Client

- `room-state`: Current room state
- `user-joined`: User joined room
- `user-left`: User left room
- `presence-update`: Presence status change
- `annotation-created`: New annotation
- `annotation-updated`: Annotation modified
- `annotation-deleted`: Annotation removed
- `annotation-conflict`: Conflict detected
- `cursor-update`: Cursor position change
- `selection-update`: Text selection change
- `text-operation-applied`: Text operation result
- `comment-created`: New comment
- `notification`: Real-time notification
- `error`: Error message

### REST Endpoints

- `GET /health`: Server health check
- `GET /metrics`: Performance metrics
- `GET /rooms`: Active rooms list

## Contributing

1. Follow existing code patterns
2. Add comprehensive tests
3. Update documentation
4. Use TypeScript for type safety
5. Follow security best practices

## License

MIT License - see LICENSE file for details.