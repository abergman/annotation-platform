"""
Conflict Resolution Models

Database models for annotation conflict detection, tracking, and resolution.
Supports multiple resolution strategies and comprehensive audit trails.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, Text, ForeignKey, 
    JSON, Float, Boolean, Enum, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from enum import Enum as PyEnum
from typing import Dict, Any, List, Optional

from src.core.database import Base


class ConflictType(PyEnum):
    """Types of annotation conflicts."""
    SPAN_OVERLAP = "span_overlap"
    LABEL_CONFLICT = "label_conflict"
    SPAN_MISMATCH = "span_mismatch"
    CONTEXT_DISAGREEMENT = "context_disagreement"
    QUALITY_DISPUTE = "quality_dispute"


class ConflictStatus(PyEnum):
    """Conflict resolution status states."""
    DETECTED = "detected"
    ASSIGNED = "assigned"
    IN_REVIEW = "in_review"
    VOTING = "voting"
    EXPERT_REVIEW = "expert_review"
    RESOLVED = "resolved"
    ARCHIVED = "archived"
    DISMISSED = "dismissed"


class ResolutionStrategy(PyEnum):
    """Available conflict resolution strategies."""
    AUTO_MERGE = "auto_merge"
    VOTING = "voting"
    EXPERT_REVIEW = "expert_review"
    USER_CONSENSUS = "user_consensus"
    WEIGHTED_VOTING = "weighted_voting"
    MANUAL_OVERRIDE = "manual_override"


class ResolutionOutcome(PyEnum):
    """Possible outcomes of conflict resolution."""
    MERGED = "merged"
    ANNOTATION_A_SELECTED = "annotation_a_selected"
    ANNOTATION_B_SELECTED = "annotation_b_selected"
    NEW_ANNOTATION_CREATED = "new_annotation_created"
    BOTH_REJECTED = "both_rejected"
    SPLIT_DECISION = "split_decision"
    ESCALATED = "escalated"


class AnnotationConflict(Base):
    """Primary model for tracking annotation conflicts."""
    
    __tablename__ = "annotation_conflicts"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Conflict identification
    conflict_type = Column(Enum(ConflictType), nullable=False)
    conflict_description = Column(Text, nullable=False)
    severity_level = Column(String(20), default="medium")  # low, medium, high, critical
    
    # Conflicting annotations
    annotation_a_id = Column(Integer, ForeignKey("annotations.id"), nullable=False)
    annotation_b_id = Column(Integer, ForeignKey("annotations.id"), nullable=False)
    additional_annotation_ids = Column(JSON, default=list)  # For multi-way conflicts
    
    # Conflict details
    overlap_start = Column(Integer, nullable=True)  # Start of overlapping region
    overlap_end = Column(Integer, nullable=True)    # End of overlapping region
    overlap_percentage = Column(Float, nullable=True)  # Percentage of overlap
    conflict_score = Column(Float, default=1.0)    # Severity score (0.0-1.0)
    
    # Project context
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    text_id = Column(Integer, ForeignKey("texts.id"), nullable=False)
    
    # Resolution tracking
    status = Column(Enum(ConflictStatus), default=ConflictStatus.DETECTED)
    resolution_strategy = Column(Enum(ResolutionStrategy), nullable=True)
    assigned_resolver_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolution_deadline = Column(DateTime, nullable=True)
    
    # Metadata
    detection_metadata = Column(JSON, default=dict)  # Algorithm details, thresholds, etc.
    context_data = Column(JSON, default=dict)        # Additional context information
    
    # Timestamps
    detected_at = Column(DateTime, default=datetime.utcnow)
    assigned_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    annotation_a = relationship("Annotation", foreign_keys=[annotation_a_id])
    annotation_b = relationship("Annotation", foreign_keys=[annotation_b_id])
    project = relationship("Project")
    text = relationship("Text")
    assigned_resolver = relationship("User", foreign_keys=[assigned_resolver_id])
    
    resolutions = relationship("ConflictResolution", back_populates="conflict", cascade="all, delete-orphan")
    participants = relationship("ConflictParticipant", back_populates="conflict", cascade="all, delete-orphan")
    votes = relationship("ResolutionVote", back_populates="conflict", cascade="all, delete-orphan")
    notifications = relationship("ConflictNotification", back_populates="conflict", cascade="all, delete-orphan")
    
    # Indexes for performance
    __table_args__ = (
        Index("idx_conflict_status_project", "status", "project_id"),
        Index("idx_conflict_detected_at", "detected_at"),
        Index("idx_conflict_annotations", "annotation_a_id", "annotation_b_id"),
        Index("idx_conflict_resolver", "assigned_resolver_id", "status"),
    )
    
    def __repr__(self):
        return f"<AnnotationConflict(id={self.id}, type={self.conflict_type}, status={self.status})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert conflict to dictionary representation."""
        return {
            "id": self.id,
            "conflict_type": self.conflict_type.value if self.conflict_type else None,
            "conflict_description": self.conflict_description,
            "severity_level": self.severity_level,
            "annotation_a_id": self.annotation_a_id,
            "annotation_b_id": self.annotation_b_id,
            "additional_annotation_ids": self.additional_annotation_ids,
            "overlap_start": self.overlap_start,
            "overlap_end": self.overlap_end,
            "overlap_percentage": self.overlap_percentage,
            "conflict_score": self.conflict_score,
            "project_id": self.project_id,
            "text_id": self.text_id,
            "status": self.status.value if self.status else None,
            "resolution_strategy": self.resolution_strategy.value if self.resolution_strategy else None,
            "assigned_resolver_id": self.assigned_resolver_id,
            "resolution_deadline": self.resolution_deadline.isoformat() if self.resolution_deadline else None,
            "detection_metadata": self.detection_metadata,
            "context_data": self.context_data,
            "detected_at": self.detected_at.isoformat() if self.detected_at else None,
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ConflictResolution(Base):
    """Model for tracking conflict resolution attempts and outcomes."""
    
    __tablename__ = "conflict_resolutions"
    
    id = Column(Integer, primary_key=True, index=True)
    conflict_id = Column(Integer, ForeignKey("annotation_conflicts.id"), nullable=False)
    
    # Resolution details
    resolution_strategy = Column(Enum(ResolutionStrategy), nullable=False)
    outcome = Column(Enum(ResolutionOutcome), nullable=True)
    resolution_description = Column(Text, nullable=False)
    
    # Result details
    final_annotation_id = Column(Integer, ForeignKey("annotations.id"), nullable=True)
    merged_annotation_data = Column(JSON, nullable=True)  # For merged annotations
    confidence_score = Column(Float, nullable=True)       # Confidence in resolution
    
    # Resolution metadata
    resolver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    resolution_method = Column(String(100), nullable=True)  # Algorithm or process used
    resolution_data = Column(JSON, default=dict)           # Additional resolution data
    
    # Quality metrics
    resolution_quality_score = Column(Float, nullable=True)  # Post-resolution quality assessment
    reviewer_feedback = Column(Text, nullable=True)
    
    # Timestamps
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    conflict = relationship("AnnotationConflict", back_populates="resolutions")
    resolver = relationship("User")
    final_annotation = relationship("Annotation", foreign_keys=[final_annotation_id])
    
    def __repr__(self):
        return f"<ConflictResolution(id={self.id}, conflict_id={self.conflict_id}, strategy={self.resolution_strategy})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert resolution to dictionary representation."""
        return {
            "id": self.id,
            "conflict_id": self.conflict_id,
            "resolution_strategy": self.resolution_strategy.value if self.resolution_strategy else None,
            "outcome": self.outcome.value if self.outcome else None,
            "resolution_description": self.resolution_description,
            "final_annotation_id": self.final_annotation_id,
            "merged_annotation_data": self.merged_annotation_data,
            "confidence_score": self.confidence_score,
            "resolver_id": self.resolver_id,
            "resolution_method": self.resolution_method,
            "resolution_data": self.resolution_data,
            "resolution_quality_score": self.resolution_quality_score,
            "reviewer_feedback": self.reviewer_feedback,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ConflictParticipant(Base):
    """Model for tracking participants in conflict resolution."""
    
    __tablename__ = "conflict_participants"
    
    id = Column(Integer, primary_key=True, index=True)
    conflict_id = Column(Integer, ForeignKey("annotation_conflicts.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Participation details
    role = Column(String(50), nullable=False)  # annotator, resolver, expert, observer
    participation_type = Column(String(50), default="active")  # active, passive, invited
    
    # Status tracking
    invited_at = Column(DateTime, nullable=True)
    joined_at = Column(DateTime, nullable=True)
    last_activity_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Participation metadata
    notification_preferences = Column(JSON, default=dict)
    contribution_data = Column(JSON, default=dict)  # Comments, votes, etc.
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    conflict = relationship("AnnotationConflict", back_populates="participants")
    user = relationship("User")
    
    # Unique constraint
    __table_args__ = (
        Index("idx_unique_conflict_participant", "conflict_id", "user_id", unique=True),
    )
    
    def __repr__(self):
        return f"<ConflictParticipant(id={self.id}, conflict_id={self.conflict_id}, user_id={self.user_id}, role={self.role})>"


class ResolutionVote(Base):
    """Model for tracking votes in democratic conflict resolution."""
    
    __tablename__ = "resolution_votes"
    
    id = Column(Integer, primary_key=True, index=True)
    conflict_id = Column(Integer, ForeignKey("annotation_conflicts.id"), nullable=False)
    voter_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Vote details
    vote_choice = Column(String(100), nullable=False)  # annotation_a, annotation_b, merge, reject, etc.
    vote_weight = Column(Float, default=1.0)          # For weighted voting
    confidence = Column(Float, nullable=True)         # Voter's confidence in their choice
    
    # Vote justification
    rationale = Column(Text, nullable=True)
    evidence_data = Column(JSON, default=dict)        # Supporting evidence or reasoning
    
    # Timestamps
    cast_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    conflict = relationship("AnnotationConflict", back_populates="votes")
    voter = relationship("User")
    
    # Unique constraint - one vote per user per conflict
    __table_args__ = (
        Index("idx_unique_conflict_vote", "conflict_id", "voter_id", unique=True),
    )
    
    def __repr__(self):
        return f"<ResolutionVote(id={self.id}, conflict_id={self.conflict_id}, choice={self.vote_choice})>"


class ConflictNotification(Base):
    """Model for managing conflict-related notifications."""
    
    __tablename__ = "conflict_notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    conflict_id = Column(Integer, ForeignKey("annotation_conflicts.id"), nullable=False)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Notification details
    notification_type = Column(String(100), nullable=False)  # conflict_detected, assigned, resolved, etc.
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    
    # Delivery tracking
    delivery_method = Column(String(50), default="in_app")  # in_app, email, webhook
    is_read = Column(Boolean, default=False)
    is_delivered = Column(Boolean, default=False)
    
    # Priority and scheduling
    priority = Column(String(20), default="normal")  # low, normal, high, urgent
    scheduled_for = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    
    # Metadata
    notification_data = Column(JSON, default=dict)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    delivered_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)
    
    # Relationships
    conflict = relationship("AnnotationConflict", back_populates="notifications")
    recipient = relationship("User")
    
    # Indexes for performance
    __table_args__ = (
        Index("idx_notification_recipient_read", "recipient_id", "is_read"),
        Index("idx_notification_scheduled", "scheduled_for"),
        Index("idx_notification_type_priority", "notification_type", "priority"),
    )
    
    def __repr__(self):
        return f"<ConflictNotification(id={self.id}, type={self.notification_type}, recipient_id={self.recipient_id})>"


class ConflictSettings(Base):
    """Model for storing project-specific conflict resolution settings."""
    
    __tablename__ = "conflict_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, unique=True)
    
    # Detection settings
    enable_conflict_detection = Column(Boolean, default=True)
    span_overlap_threshold = Column(Float, default=0.1)    # Minimum overlap percentage
    confidence_threshold = Column(Float, default=0.5)      # Minimum confidence for detection
    auto_detection_enabled = Column(Boolean, default=True)
    
    # Resolution strategy preferences
    default_resolution_strategy = Column(Enum(ResolutionStrategy), default=ResolutionStrategy.VOTING)
    voting_threshold = Column(Float, default=0.6)          # Minimum agreement for voting resolution
    expert_assignment_threshold = Column(Float, default=0.8) # Conflict score threshold for expert review
    auto_merge_enabled = Column(Boolean, default=False)
    
    # Notification preferences
    notify_on_detection = Column(Boolean, default=True)
    notify_annotators = Column(Boolean, default=True)
    notify_project_admin = Column(Boolean, default=True)
    notification_delay_minutes = Column(Integer, default=5) # Delay before sending notifications
    
    # Escalation settings
    resolution_timeout_hours = Column(Integer, default=48)  # Hours before escalation
    max_resolution_attempts = Column(Integer, default=3)
    enable_automatic_escalation = Column(Boolean, default=True)
    
    # Quality control
    require_resolution_review = Column(Boolean, default=False)
    track_resolver_performance = Column(Boolean, default=True)
    minimum_voter_count = Column(Integer, default=3)
    
    # Custom settings
    custom_settings = Column(JSON, default=dict)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project = relationship("Project")
    
    def __repr__(self):
        return f"<ConflictSettings(id={self.id}, project_id={self.project_id})>"


# Utility functions for conflict management

def create_conflict_tables(engine):
    """Create all conflict-related tables."""
    Base.metadata.create_all(engine)


def get_conflict_summary(session, conflict_id: int) -> Dict[str, Any]:
    """Get comprehensive conflict summary with all related data."""
    conflict = session.query(AnnotationConflict).filter_by(id=conflict_id).first()
    if not conflict:
        return None
    
    summary = conflict.to_dict()
    
    # Add related data
    summary['resolutions'] = [res.to_dict() for res in conflict.resolutions]
    summary['participants'] = [p.to_dict() for p in conflict.participants]
    summary['votes'] = [vote.to_dict() for vote in conflict.votes]
    summary['notifications'] = [notif.to_dict() for notif in conflict.notifications]
    
    return summary


def get_project_conflict_stats(session, project_id: int) -> Dict[str, Any]:
    """Get conflict statistics for a project."""
    from sqlalchemy import func
    
    # Base query
    base_query = session.query(AnnotationConflict).filter_by(project_id=project_id)
    
    # Count by status
    status_counts = (
        session.query(
            AnnotationConflict.status,
            func.count(AnnotationConflict.id).label('count')
        )
        .filter_by(project_id=project_id)
        .group_by(AnnotationConflict.status)
        .all()
    )
    
    # Count by type
    type_counts = (
        session.query(
            AnnotationConflict.conflict_type,
            func.count(AnnotationConflict.id).label('count')
        )
        .filter_by(project_id=project_id)
        .group_by(AnnotationConflict.conflict_type)
        .all()
    )
    
    # Resolution times
    resolved_conflicts = base_query.filter(
        AnnotationConflict.status == ConflictStatus.RESOLVED,
        AnnotationConflict.resolved_at.isnot(None),
        AnnotationConflict.detected_at.isnot(None)
    ).all()
    
    resolution_times = []
    for conflict in resolved_conflicts:
        if conflict.resolved_at and conflict.detected_at:
            resolution_time = (conflict.resolved_at - conflict.detected_at).total_seconds() / 3600
            resolution_times.append(resolution_time)
    
    avg_resolution_time = sum(resolution_times) / len(resolution_times) if resolution_times else 0
    
    return {
        'total_conflicts': base_query.count(),
        'status_breakdown': {status.value: count for status, count in status_counts},
        'type_breakdown': {ctype.value: count for ctype, count in type_counts},
        'average_resolution_time_hours': avg_resolution_time,
        'resolved_conflicts_count': len(resolved_conflicts),
        'pending_conflicts_count': base_query.filter(
            AnnotationConflict.status.in_([
                ConflictStatus.DETECTED, 
                ConflictStatus.ASSIGNED, 
                ConflictStatus.IN_REVIEW,
                ConflictStatus.VOTING,
                ConflictStatus.EXPERT_REVIEW
            ])
        ).count()
    }