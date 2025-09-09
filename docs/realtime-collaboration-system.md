# Real-Time Collaboration System Design

## Overview
This document specifies the implementation of real-time collaborative features using WebSocket technology, enabling live collaboration, conflict resolution, and activity tracking for annotation teams.

## 1. WebSocket Infrastructure

### WebSocket Connection Management
```python
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List, Set, Optional, Any
import json
import asyncio
from datetime import datetime, timedelta
import uuid
from enum import Enum

class ConnectionType(Enum):
    ANNOTATOR = "annotator"
    OBSERVER = "observer"
    ADMIN = "admin"

class ActivityType(Enum):
    ANNOTATION_CREATED = "annotation_created"
    ANNOTATION_UPDATED = "annotation_updated"
    ANNOTATION_DELETED = "annotation_deleted"
    USER_JOINED = "user_joined"
    USER_LEFT = "user_left"
    CURSOR_MOVED = "cursor_moved"
    SELECTION_CHANGED = "selection_changed"
    COMMENT_ADDED = "comment_added"
    CONFLICT_DETECTED = "conflict_detected"
    CONFLICT_RESOLVED = "conflict_resolved"

@dataclass
class WebSocketConnection:
    """Represents a WebSocket connection with metadata."""
    websocket: WebSocket
    user_id: int
    project_id: int
    connection_id: str
    connection_type: ConnectionType
    connected_at: datetime
    last_activity: datetime
    session_data: Dict[str, Any]

class CollaborationManager:
    """Manages real-time collaboration WebSocket connections."""
    
    def __init__(self):
        # project_id -> {connection_id: WebSocketConnection}
        self.project_connections: Dict[int, Dict[str, WebSocketConnection]] = {}
        
        # user_id -> {project_id: connection_id}
        self.user_connections: Dict[int, Dict[int, str]] = {}
        
        # Active cursors: project_id -> {user_id: {position, timestamp}}
        self.active_cursors: Dict[int, Dict[int, Dict[str, Any]]] = {}
        
        # Pending changes for conflict detection
        self.pending_changes: Dict[int, List[Dict[str, Any]]] = {}
        
        # Message queue for offline users
        self.offline_message_queue: Dict[int, List[Dict[str, Any]]] = {}
    
    async def connect_user(
        self, 
        websocket: WebSocket, 
        user_id: int, 
        project_id: int,
        connection_type: ConnectionType = ConnectionType.ANNOTATOR
    ) -> str:
        """Connect a user to a project collaboration session."""
        await websocket.accept()
        
        connection_id = str(uuid.uuid4())
        connection = WebSocketConnection(
            websocket=websocket,
            user_id=user_id,
            project_id=project_id,
            connection_id=connection_id,
            connection_type=connection_type,
            connected_at=datetime.utcnow(),
            last_activity=datetime.utcnow(),
            session_data={}
        )
        
        # Store connection
        if project_id not in self.project_connections:
            self.project_connections[project_id] = {}
        self.project_connections[project_id][connection_id] = connection
        
        if user_id not in self.user_connections:
            self.user_connections[user_id] = {}
        self.user_connections[user_id][project_id] = connection_id
        
        # Initialize cursor tracking
        if project_id not in self.active_cursors:
            self.active_cursors[project_id] = {}
        
        # Notify other users about new connection
        await self.broadcast_to_project(
            project_id,
            {
                "type": ActivityType.USER_JOINED.value,
                "user_id": user_id,
                "connection_id": connection_id,
                "timestamp": datetime.utcnow().isoformat()
            },
            exclude_connection=connection_id
        )
        
        # Send existing active users to new connection
        active_users = [
            {
                "user_id": conn.user_id,
                "connection_type": conn.connection_type.value,
                "connected_at": conn.connected_at.isoformat()
            }
            for conn in self.project_connections[project_id].values()
            if conn.connection_id != connection_id
        ]
        
        await websocket.send_json({
            "type": "connection_established",
            "connection_id": connection_id,
            "active_users": active_users,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Send queued messages
        if user_id in self.offline_message_queue:
            for message in self.offline_message_queue[user_id]:
                await websocket.send_json(message)
            del self.offline_message_queue[user_id]
        
        return connection_id
    
    async def disconnect_user(self, connection_id: str) -> None:
        """Disconnect a user and clean up resources."""
        connection = None
        project_id = None
        user_id = None
        
        # Find and remove connection
        for pid, connections in self.project_connections.items():
            if connection_id in connections:
                connection = connections[connection_id]
                project_id = pid
                user_id = connection.user_id
                del connections[connection_id]
                break
        
        if not connection:
            return
        
        # Clean up user connections mapping
        if user_id in self.user_connections and project_id in self.user_connections[user_id]:
            del self.user_connections[user_id][project_id]
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
        
        # Remove cursor
        if project_id in self.active_cursors and user_id in self.active_cursors[project_id]:
            del self.active_cursors[project_id][user_id]
        
        # Notify other users about disconnection
        await self.broadcast_to_project(
            project_id,
            {
                "type": ActivityType.USER_LEFT.value,
                "user_id": user_id,
                "connection_id": connection_id,
                "session_duration": (datetime.utcnow() - connection.connected_at).total_seconds(),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    async def broadcast_to_project(
        self, 
        project_id: int, 
        message: Dict[str, Any],
        exclude_connection: Optional[str] = None,
        target_connection_types: Optional[List[ConnectionType]] = None
    ) -> None:
        """Broadcast message to all connections in a project."""
        if project_id not in self.project_connections:
            return
        
        connections = self.project_connections[project_id].values()
        
        # Filter connections based on criteria
        if exclude_connection:
            connections = [c for c in connections if c.connection_id != exclude_connection]
        
        if target_connection_types:
            connections = [c for c in connections if c.connection_type in target_connection_types]
        
        # Send message to all valid connections
        disconnected_connections = []
        
        for connection in connections:
            try:
                await connection.websocket.send_json(message)
                connection.last_activity = datetime.utcnow()
            except Exception as e:
                print(f"Failed to send message to connection {connection.connection_id}: {e}")
                disconnected_connections.append(connection.connection_id)
        
        # Clean up disconnected connections
        for connection_id in disconnected_connections:
            await self.disconnect_user(connection_id)
    
    async def send_to_user(
        self, 
        user_id: int, 
        project_id: int, 
        message: Dict[str, Any]
    ) -> bool:
        """Send message to a specific user in a project."""
        if (user_id not in self.user_connections or 
            project_id not in self.user_connections[user_id]):
            # Queue message for offline user
            if user_id not in self.offline_message_queue:
                self.offline_message_queue[user_id] = []
            self.offline_message_queue[user_id].append({
                **message,
                "queued_at": datetime.utcnow().isoformat()
            })
            return False
        
        connection_id = self.user_connections[user_id][project_id]
        connection = self.project_connections[project_id][connection_id]
        
        try:
            await connection.websocket.send_json(message)
            connection.last_activity = datetime.utcnow()
            return True
        except Exception as e:
            print(f"Failed to send message to user {user_id}: {e}")
            await self.disconnect_user(connection_id)
            return False
    
    async def handle_annotation_update(
        self, 
        project_id: int, 
        annotation_data: Dict[str, Any],
        source_user_id: int
    ) -> None:
        """Handle annotation update and broadcast to collaborators."""
        
        # Check for conflicts
        conflicts = await self.detect_annotation_conflicts(project_id, annotation_data)
        
        if conflicts:
            # Notify about conflicts
            await self.broadcast_to_project(project_id, {
                "type": ActivityType.CONFLICT_DETECTED.value,
                "annotation_id": annotation_data.get("id"),
                "conflicts": conflicts,
                "source_user_id": source_user_id,
                "timestamp": datetime.utcnow().isoformat()
            })
        else:
            # Broadcast update
            await self.broadcast_to_project(
                project_id,
                {
                    "type": ActivityType.ANNOTATION_UPDATED.value,
                    "annotation": annotation_data,
                    "source_user_id": source_user_id,
                    "timestamp": datetime.utcnow().isoformat()
                },
                exclude_connection=self.user_connections.get(source_user_id, {}).get(project_id)
            )
    
    async def detect_annotation_conflicts(
        self, 
        project_id: int, 
        annotation_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Detect conflicts with pending changes."""
        if project_id not in self.pending_changes:
            return []
        
        conflicts = []
        annotation_start = annotation_data.get("start_char", 0)
        annotation_end = annotation_data.get("end_char", 0)
        
        for pending_change in self.pending_changes[project_id]:
            pending_start = pending_change.get("start_char", 0)
            pending_end = pending_change.get("end_char", 0)
            
            # Check for overlap
            if (annotation_start < pending_end and annotation_end > pending_start):
                conflicts.append({
                    "type": "overlap",
                    "pending_change": pending_change,
                    "overlap_start": max(annotation_start, pending_start),
                    "overlap_end": min(annotation_end, pending_end)
                })
        
        return conflicts
    
    async def update_user_cursor(
        self, 
        user_id: int, 
        project_id: int, 
        cursor_position: Dict[str, Any]
    ) -> None:
        """Update user's cursor position and broadcast to others."""
        if project_id not in self.active_cursors:
            self.active_cursors[project_id] = {}
        
        self.active_cursors[project_id][user_id] = {
            **cursor_position,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Broadcast cursor update
        await self.broadcast_to_project(
            project_id,
            {
                "type": ActivityType.CURSOR_MOVED.value,
                "user_id": user_id,
                "cursor_position": cursor_position,
                "timestamp": datetime.utcnow().isoformat()
            },
            exclude_connection=self.user_connections.get(user_id, {}).get(project_id)
        )
    
    async def cleanup_inactive_connections(self, timeout_minutes: int = 30) -> None:
        """Clean up inactive connections."""
        timeout_threshold = datetime.utcnow() - timedelta(minutes=timeout_minutes)
        
        inactive_connections = []
        
        for project_id, connections in self.project_connections.items():
            for connection_id, connection in connections.items():
                if connection.last_activity < timeout_threshold:
                    inactive_connections.append(connection_id)
        
        for connection_id in inactive_connections:
            await self.disconnect_user(connection_id)

# Global collaboration manager instance
collaboration_manager = CollaborationManager()
```

### WebSocket Endpoints
```python
from fastapi import WebSocket, Depends, HTTPException
from src.core.security import get_current_user_websocket

@app.websocket("/ws/collaboration/{project_id}")
async def websocket_collaboration(
    websocket: WebSocket,
    project_id: int,
    token: str,
    connection_type: str = "annotator"
):
    """WebSocket endpoint for real-time collaboration."""
    
    try:
        # Authenticate user
        current_user = await get_current_user_websocket(token)
        
        # Verify project access
        project = await get_project_with_access_check(project_id, current_user.id)
        if not project:
            await websocket.close(code=4003, reason="Access denied")
            return
        
        # Connect user
        connection_id = await collaboration_manager.connect_user(
            websocket=websocket,
            user_id=current_user.id,
            project_id=project_id,
            connection_type=ConnectionType(connection_type)
        )
        
        try:
            while True:
                # Receive message
                data = await websocket.receive_json()
                
                # Handle different message types
                message_type = data.get("type")
                
                if message_type == "annotation_update":
                    await handle_annotation_update_message(
                        project_id, data, current_user.id
                    )
                elif message_type == "cursor_update":
                    await collaboration_manager.update_user_cursor(
                        current_user.id, project_id, data.get("cursor_position", {})
                    )
                elif message_type == "comment_add":
                    await handle_comment_message(
                        project_id, data, current_user.id
                    )
                elif message_type == "conflict_resolve":
                    await handle_conflict_resolution(
                        project_id, data, current_user.id
                    )
                elif message_type == "heartbeat":
                    # Update last activity
                    await websocket.send_json({"type": "heartbeat_ack"})
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown message type: {message_type}"
                    })
                    
        except WebSocketDisconnect:
            pass
        except Exception as e:
            print(f"WebSocket error: {e}")
        finally:
            await collaboration_manager.disconnect_user(connection_id)
            
    except Exception as e:
        print(f"WebSocket connection error: {e}")
        await websocket.close(code=4000, reason="Connection error")
```

## 2. Conflict Resolution System

### Database Schema
```sql
CREATE TABLE annotation_conflicts (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    text_id INTEGER NOT NULL REFERENCES texts(id) ON DELETE CASCADE,
    conflict_type VARCHAR(50) NOT NULL CHECK (conflict_type IN ('overlap', 'duplicate', 'disagreement', 'concurrent_edit')),
    conflicting_annotations JSONB NOT NULL, -- Array of annotation data
    conflict_metadata JSONB DEFAULT '{}',
    
    -- Resolution information
    resolution_strategy VARCHAR(50) CHECK (resolution_strategy IN ('manual', 'voting', 'expert_judgment', 'merge', 'split')),
    resolution_data JSONB DEFAULT '{}',
    resolved_annotation_id INTEGER REFERENCES annotations(id),
    resolved_by INTEGER REFERENCES users(id),
    resolution_date TIMESTAMP,
    resolution_notes TEXT,
    
    -- Status tracking
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'resolved', 'dismissed')),
    auto_detected BOOLEAN DEFAULT TRUE,
    severity_level INTEGER DEFAULT 1 CHECK (severity_level >= 1 AND severity_level <= 5),
    
    -- Timestamps
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT valid_conflicting_annotations CHECK (jsonb_array_length(conflicting_annotations) >= 2)
);

CREATE TABLE conflict_votes (
    id SERIAL PRIMARY KEY,
    conflict_id INTEGER NOT NULL REFERENCES annotation_conflicts(id) ON DELETE CASCADE,
    voter_id INTEGER NOT NULL REFERENCES users(id),
    vote_data JSONB NOT NULL, -- {preferred_annotation_id: 123, reasoning: "..."}
    vote_weight FLOAT DEFAULT 1.0,
    voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_vote_per_conflict UNIQUE(conflict_id, voter_id)
);

-- Indexes
CREATE INDEX idx_annotation_conflicts_project ON annotation_conflicts(project_id);
CREATE INDEX idx_annotation_conflicts_status ON annotation_conflicts(status);
CREATE INDEX idx_annotation_conflicts_detected_at ON annotation_conflicts(detected_at);
CREATE INDEX idx_conflict_votes_conflict ON conflict_votes(conflict_id);
```

### Conflict Detection Engine
```python
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import numpy as np

class ConflictType(Enum):
    OVERLAP = "overlap"
    DUPLICATE = "duplicate"
    DISAGREEMENT = "disagreement"
    CONCURRENT_EDIT = "concurrent_edit"
    BOUNDARY_MISMATCH = "boundary_mismatch"

class ConflictSeverity(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4
    BLOCKING = 5

@dataclass
class AnnotationConflict:
    """Represents a detected annotation conflict."""
    conflict_type: ConflictType
    severity: ConflictSeverity
    conflicting_annotations: List[Dict[str, Any]]
    conflict_metadata: Dict[str, Any]
    suggested_resolutions: List[Dict[str, Any]]
    auto_resolvable: bool = False

class ConflictDetector:
    """Detects conflicts between annotations in real-time."""
    
    def __init__(self):
        self.overlap_threshold = 0.3  # Minimum overlap to consider conflict
        self.boundary_tolerance = 5   # Character tolerance for boundary matching
        self.time_window_seconds = 30  # Window for concurrent edit detection
    
    async def detect_conflicts(
        self, 
        new_annotation: Dict[str, Any],
        existing_annotations: List[Dict[str, Any]],
        recent_edits: List[Dict[str, Any]] = None
    ) -> List[AnnotationConflict]:
        """Detect all types of conflicts for a new annotation."""
        
        conflicts = []
        
        # Check for overlapping annotations
        overlap_conflicts = self._detect_overlap_conflicts(new_annotation, existing_annotations)
        conflicts.extend(overlap_conflicts)
        
        # Check for duplicate annotations
        duplicate_conflicts = self._detect_duplicate_conflicts(new_annotation, existing_annotations)
        conflicts.extend(duplicate_conflicts)
        
        # Check for label disagreements
        disagreement_conflicts = self._detect_disagreement_conflicts(new_annotation, existing_annotations)
        conflicts.extend(disagreement_conflicts)
        
        # Check for concurrent edits
        if recent_edits:
            concurrent_conflicts = self._detect_concurrent_edit_conflicts(new_annotation, recent_edits)
            conflicts.extend(concurrent_conflicts)
        
        return conflicts
    
    def _detect_overlap_conflicts(
        self, 
        new_annotation: Dict[str, Any], 
        existing_annotations: List[Dict[str, Any]]
    ) -> List[AnnotationConflict]:
        """Detect overlapping span conflicts."""
        
        conflicts = []
        new_start = new_annotation.get("start_char", 0)
        new_end = new_annotation.get("end_char", 0)
        
        for existing in existing_annotations:
            existing_start = existing.get("start_char", 0)
            existing_end = existing.get("end_char", 0)
            
            # Calculate overlap
            overlap_start = max(new_start, existing_start)
            overlap_end = min(new_end, existing_end)
            
            if overlap_start < overlap_end:
                overlap_length = overlap_end - overlap_start
                new_length = new_end - new_start
                existing_length = existing_end - existing_start
                
                # Calculate overlap ratios
                overlap_ratio_new = overlap_length / new_length if new_length > 0 else 0
                overlap_ratio_existing = overlap_length / existing_length if existing_length > 0 else 0
                max_overlap_ratio = max(overlap_ratio_new, overlap_ratio_existing)
                
                if max_overlap_ratio >= self.overlap_threshold:
                    # Determine severity based on overlap ratio and label agreement
                    if new_annotation.get("label") == existing.get("label"):
                        severity = ConflictSeverity.LOW if max_overlap_ratio < 0.8 else ConflictSeverity.MEDIUM
                    else:
                        severity = ConflictSeverity.HIGH if max_overlap_ratio > 0.8 else ConflictSeverity.MEDIUM
                    
                    # Generate suggested resolutions
                    suggested_resolutions = []
                    
                    # Complete overlap - suggest merge or choose one
                    if max_overlap_ratio > 0.9:
                        if new_annotation.get("label") == existing.get("label"):
                            suggested_resolutions.append({
                                "strategy": "merge",
                                "description": "Merge overlapping annotations with same label",
                                "confidence": 0.9
                            })
                        else:
                            suggested_resolutions.append({
                                "strategy": "expert_judgment",
                                "description": "Manual review required for different labels",
                                "confidence": 0.7
                            })
                    
                    # Partial overlap - suggest boundary adjustment
                    else:
                        suggested_resolutions.append({
                            "strategy": "boundary_adjustment",
                            "description": "Adjust annotation boundaries to resolve overlap",
                            "suggested_boundaries": self._suggest_boundary_adjustment(
                                new_annotation, existing
                            ),
                            "confidence": 0.8
                        })
                    
                    conflicts.append(AnnotationConflict(
                        conflict_type=ConflictType.OVERLAP,
                        severity=severity,
                        conflicting_annotations=[new_annotation, existing],
                        conflict_metadata={
                            "overlap_ratio": max_overlap_ratio,
                            "overlap_span": {"start": overlap_start, "end": overlap_end},
                            "overlap_length": overlap_length
                        },
                        suggested_resolutions=suggested_resolutions,
                        auto_resolvable=max_overlap_ratio > 0.95 and new_annotation.get("label") == existing.get("label")
                    ))
        
        return conflicts
    
    def _detect_duplicate_conflicts(
        self, 
        new_annotation: Dict[str, Any], 
        existing_annotations: List[Dict[str, Any]]
    ) -> List[AnnotationConflict]:
        """Detect duplicate annotation conflicts."""
        
        conflicts = []
        
        for existing in existing_annotations:
            # Check for exact duplicates
            if (abs(new_annotation.get("start_char", 0) - existing.get("start_char", 0)) <= self.boundary_tolerance and
                abs(new_annotation.get("end_char", 0) - existing.get("end_char", 0)) <= self.boundary_tolerance and
                new_annotation.get("label") == existing.get("label")):
                
                conflicts.append(AnnotationConflict(
                    conflict_type=ConflictType.DUPLICATE,
                    severity=ConflictSeverity.MEDIUM,
                    conflicting_annotations=[new_annotation, existing],
                    conflict_metadata={
                        "boundary_difference": {
                            "start": abs(new_annotation.get("start_char", 0) - existing.get("start_char", 0)),
                            "end": abs(new_annotation.get("end_char", 0) - existing.get("end_char", 0))
                        }
                    },
                    suggested_resolutions=[
                        {
                            "strategy": "remove_duplicate",
                            "description": "Remove the duplicate annotation",
                            "keep_annotation_id": existing.get("id"),
                            "confidence": 0.95
                        }
                    ],
                    auto_resolvable=True
                ))
        
        return conflicts
    
    def _detect_disagreement_conflicts(
        self, 
        new_annotation: Dict[str, Any], 
        existing_annotations: List[Dict[str, Any]]
    ) -> List[AnnotationConflict]:
        """Detect label disagreement conflicts."""
        
        conflicts = []
        
        for existing in existing_annotations:
            # Check for same span, different label
            if (abs(new_annotation.get("start_char", 0) - existing.get("start_char", 0)) <= self.boundary_tolerance and
                abs(new_annotation.get("end_char", 0) - existing.get("end_char", 0)) <= self.boundary_tolerance and
                new_annotation.get("label") != existing.get("label")):
                
                conflicts.append(AnnotationConflict(
                    conflict_type=ConflictType.DISAGREEMENT,
                    severity=ConflictSeverity.HIGH,
                    conflicting_annotations=[new_annotation, existing],
                    conflict_metadata={
                        "labels": [new_annotation.get("label"), existing.get("label")],
                        "annotators": [new_annotation.get("annotator_id"), existing.get("annotator_id")]
                    },
                    suggested_resolutions=[
                        {
                            "strategy": "voting",
                            "description": "Let team vote on correct label",
                            "confidence": 0.8
                        },
                        {
                            "strategy": "expert_judgment", 
                            "description": "Escalate to project expert",
                            "confidence": 0.9
                        }
                    ],
                    auto_resolvable=False
                ))
        
        return conflicts
    
    def _suggest_boundary_adjustment(
        self, 
        ann1: Dict[str, Any], 
        ann2: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Suggest boundary adjustments to resolve overlap."""
        
        start1, end1 = ann1.get("start_char", 0), ann1.get("end_char", 0)
        start2, end2 = ann2.get("start_char", 0), ann2.get("end_char", 0)
        
        # Find overlap
        overlap_start = max(start1, start2)
        overlap_end = min(end1, end2)
        
        if overlap_start >= overlap_end:
            return {}  # No overlap
        
        # Suggest splitting the overlap
        overlap_mid = (overlap_start + overlap_end) // 2
        
        return {
            "strategy": "split_overlap",
            "annotation1_adjustment": {"end_char": overlap_mid},
            "annotation2_adjustment": {"start_char": overlap_mid},
            "rationale": f"Split overlap at character {overlap_mid}"
        }

class ConflictResolver:
    """Handles conflict resolution strategies."""
    
    async def resolve_conflict(
        self, 
        conflict: AnnotationConflict,
        resolution_strategy: str,
        resolution_data: Dict[str, Any],
        resolver_user_id: int,
        db: Session
    ) -> Dict[str, Any]:
        """Resolve a conflict using the specified strategy."""
        
        if resolution_strategy == "merge":
            return await self._resolve_by_merge(conflict, resolution_data, db)
        elif resolution_strategy == "voting":
            return await self._resolve_by_voting(conflict, resolution_data, db)
        elif resolution_strategy == "expert_judgment":
            return await self._resolve_by_expert(conflict, resolution_data, resolver_user_id, db)
        elif resolution_strategy == "boundary_adjustment":
            return await self._resolve_by_boundary_adjustment(conflict, resolution_data, db)
        elif resolution_strategy == "remove_duplicate":
            return await self._resolve_by_duplicate_removal(conflict, resolution_data, db)
        else:
            raise ValueError(f"Unknown resolution strategy: {resolution_strategy}")
    
    async def _resolve_by_merge(
        self, 
        conflict: AnnotationConflict, 
        resolution_data: Dict[str, Any],
        db: Session
    ) -> Dict[str, Any]:
        """Resolve conflict by merging annotations."""
        
        annotations = conflict.conflicting_annotations
        
        # Find the span that encompasses all conflicting annotations
        min_start = min(ann.get("start_char", 0) for ann in annotations)
        max_end = max(ann.get("end_char", 0) for ann in annotations)
        
        # Use the most common label
        labels = [ann.get("label") for ann in annotations if ann.get("label")]
        most_common_label = max(set(labels), key=labels.count) if labels else None
        
        # Merge metadata
        merged_metadata = {}
        for ann in annotations:
            if ann.get("metadata"):
                merged_metadata.update(ann["metadata"])
        
        # Create new merged annotation
        merged_annotation = {
            "start_char": min_start,
            "end_char": max_end,
            "label": most_common_label,
            "selected_text": resolution_data.get("selected_text", ""),
            "metadata": merged_metadata,
            "notes": f"Merged from {len(annotations)} conflicting annotations",
            "confidence_score": np.mean([ann.get("confidence_score", 1.0) for ann in annotations])
        }
        
        return {
            "resolution_type": "merge",
            "merged_annotation": merged_annotation,
            "removed_annotation_ids": [ann.get("id") for ann in annotations if ann.get("id")]
        }
    
    async def _resolve_by_voting(
        self, 
        conflict: AnnotationConflict,
        resolution_data: Dict[str, Any],
        db: Session
    ) -> Dict[str, Any]:
        """Resolve conflict through team voting."""
        
        # This would integrate with the voting system
        # For now, return the structure for voting resolution
        
        return {
            "resolution_type": "voting",
            "voting_session_id": resolution_data.get("voting_session_id"),
            "status": "pending_votes",
            "required_votes": resolution_data.get("required_votes", 3),
            "current_votes": 0
        }
```

### Real-time Conflict Notification
```python
async def handle_annotation_update_message(
    project_id: int, 
    message_data: Dict[str, Any], 
    user_id: int
) -> None:
    """Handle annotation update messages with conflict detection."""
    
    annotation_data = message_data.get("annotation", {})
    
    # Get existing annotations for conflict detection
    existing_annotations = await get_text_annotations(
        text_id=annotation_data.get("text_id"),
        exclude_id=annotation_data.get("id")
    )
    
    # Detect conflicts
    conflict_detector = ConflictDetector()
    conflicts = await conflict_detector.detect_conflicts(
        new_annotation=annotation_data,
        existing_annotations=existing_annotations
    )
    
    if conflicts:
        # Store conflicts in database
        for conflict in conflicts:
            conflict_record = AnnotationConflict(
                project_id=project_id,
                text_id=annotation_data.get("text_id"),
                conflict_type=conflict.conflict_type.value,
                conflicting_annotations=conflict.conflicting_annotations,
                conflict_metadata=conflict.conflict_metadata,
                severity_level=conflict.severity.value,
                auto_detected=True
            )
            
            db.add(conflict_record)
            db.commit()
            
            # Notify all users about the conflict
            await collaboration_manager.broadcast_to_project(
                project_id,
                {
                    "type": ActivityType.CONFLICT_DETECTED.value,
                    "conflict_id": conflict_record.id,
                    "conflict_type": conflict.conflict_type.value,
                    "severity": conflict.severity.value,
                    "conflicting_annotations": conflict.conflicting_annotations,
                    "suggested_resolutions": conflict.suggested_resolutions,
                    "auto_resolvable": conflict.auto_resolvable,
                    "detected_by_user_id": user_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            # If auto-resolvable, attempt automatic resolution
            if conflict.auto_resolvable and conflict.suggested_resolutions:
                try:
                    resolver = ConflictResolver()
                    resolution = await resolver.resolve_conflict(
                        conflict=conflict,
                        resolution_strategy=conflict.suggested_resolutions[0]["strategy"],
                        resolution_data=conflict.suggested_resolutions[0],
                        resolver_user_id=user_id,
                        db=db
                    )
                    
                    # Update conflict as resolved
                    conflict_record.status = "resolved"
                    conflict_record.resolution_strategy = conflict.suggested_resolutions[0]["strategy"]
                    conflict_record.resolution_data = resolution
                    conflict_record.resolved_by = user_id
                    conflict_record.resolution_date = datetime.utcnow()
                    
                    db.commit()
                    
                    # Notify about automatic resolution
                    await collaboration_manager.broadcast_to_project(
                        project_id,
                        {
                            "type": ActivityType.CONFLICT_RESOLVED.value,
                            "conflict_id": conflict_record.id,
                            "resolution": resolution,
                            "resolution_type": "automatic",
                            "resolved_by_user_id": user_id,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    )
                    
                except Exception as e:
                    print(f"Failed to auto-resolve conflict {conflict_record.id}: {e}")
    
    else:
        # No conflicts - broadcast the update
        await collaboration_manager.handle_annotation_update(
            project_id=project_id,
            annotation_data=annotation_data,
            source_user_id=user_id
        )
```

This real-time collaboration system enables seamless teamwork with automatic conflict detection, resolution workflows, and live activity tracking, essential for coordinated academic annotation projects.