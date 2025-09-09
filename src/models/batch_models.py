"""
Batch Operation Models

Database models for tracking batch operations, progress, and errors.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON, Float, Boolean
from sqlalchemy.orm import relationship
from enum import Enum

from src.core.database import Base


class BatchOperationStatus(str, Enum):
    """Enum for batch operation status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class BatchOperationType(str, Enum):
    """Enum for batch operation types."""
    ANNOTATION_CREATE = "annotation_create"
    ANNOTATION_UPDATE = "annotation_update"
    ANNOTATION_DELETE = "annotation_delete"
    TEXT_IMPORT = "text_import"
    DATA_EXPORT = "data_export"
    ANNOTATION_VALIDATION = "annotation_validation"
    USER_PERMISSION_MANAGEMENT = "user_permission_management"
    LABEL_MANAGEMENT = "label_management"
    BULK_VALIDATION = "bulk_validation"
    QUALITY_ANALYSIS = "quality_analysis"


class BatchOperation(Base):
    """Model for tracking batch operations."""
    
    __tablename__ = "batch_operations"
    
    id = Column(String(36), primary_key=True)  # UUID
    operation_type = Column(String(50), nullable=False)
    status = Column(String(20), default=BatchOperationStatus.PENDING.value)
    
    # Progress tracking
    total_items = Column(Integer, default=0)
    processed_items = Column(Integer, default=0)
    failed_items = Column(Integer, default=0)
    success_items = Column(Integer, default=0)
    
    # Progress percentage and estimated time
    progress_percentage = Column(Float, default=0.0)
    estimated_duration = Column(Integer)  # seconds
    elapsed_time = Column(Integer, default=0)  # seconds
    
    # Operation details
    parameters = Column(JSON, default=dict)
    result_data = Column(JSON, default=dict)
    error_message = Column(Text)
    error_details = Column(JSON, default=dict)
    
    # Batch configuration
    chunk_size = Column(Integer, default=100)
    parallel_workers = Column(Integer, default=1)
    rollback_on_error = Column(Boolean, default=True)
    validate_before_process = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign keys
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"))
    
    # Relationships
    user = relationship("User")
    project = relationship("Project")
    progress_logs = relationship("BatchProgress", back_populates="operation", cascade="all, delete-orphan")
    errors = relationship("BatchError", back_populates="operation", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<BatchOperation(id={self.id}, type={self.operation_type}, status={self.status})>"
    
    def to_dict(self):
        """Convert batch operation to dictionary."""
        return {
            "id": self.id,
            "operation_type": self.operation_type,
            "status": self.status,
            "total_items": self.total_items,
            "processed_items": self.processed_items,
            "failed_items": self.failed_items,
            "success_items": self.success_items,
            "progress_percentage": self.progress_percentage,
            "estimated_duration": self.estimated_duration,
            "elapsed_time": self.elapsed_time,
            "parameters": self.parameters,
            "result_data": self.result_data,
            "error_message": self.error_message,
            "chunk_size": self.chunk_size,
            "parallel_workers": self.parallel_workers,
            "rollback_on_error": self.rollback_on_error,
            "validate_before_process": self.validate_before_process,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "user_id": self.user_id,
            "project_id": self.project_id,
            "error_count": len(self.errors) if self.errors else 0,
            "progress_log_count": len(self.progress_logs) if self.progress_logs else 0
        }


class BatchProgress(Base):
    """Model for tracking detailed batch operation progress."""
    
    __tablename__ = "batch_progress"
    
    id = Column(Integer, primary_key=True)
    operation_id = Column(String(36), ForeignKey("batch_operations.id"), nullable=False)
    
    # Progress details
    step_name = Column(String(200))
    step_description = Column(Text)
    current_item = Column(Integer, default=0)
    total_items = Column(Integer, default=0)
    progress_percentage = Column(Float, default=0.0)
    
    # Performance metrics
    items_per_second = Column(Float, default=0.0)
    memory_usage_mb = Column(Float, default=0.0)
    cpu_usage_percent = Column(Float, default=0.0)
    
    # Status and metadata
    status = Column(String(20), default="in_progress")
    metadata = Column(JSON, default=dict)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    operation = relationship("BatchOperation", back_populates="progress_logs")
    
    def __repr__(self):
        return f"<BatchProgress(id={self.id}, operation_id={self.operation_id}, step={self.step_name})>"
    
    def to_dict(self):
        """Convert progress record to dictionary."""
        return {
            "id": self.id,
            "operation_id": self.operation_id,
            "step_name": self.step_name,
            "step_description": self.step_description,
            "current_item": self.current_item,
            "total_items": self.total_items,
            "progress_percentage": self.progress_percentage,
            "items_per_second": self.items_per_second,
            "memory_usage_mb": self.memory_usage_mb,
            "cpu_usage_percent": self.cpu_usage_percent,
            "status": self.status,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class BatchError(Base):
    """Model for tracking batch operation errors."""
    
    __tablename__ = "batch_errors"
    
    id = Column(Integer, primary_key=True)
    operation_id = Column(String(36), ForeignKey("batch_operations.id"), nullable=False)
    
    # Error details
    error_type = Column(String(100))
    error_code = Column(String(50))
    error_message = Column(Text, nullable=False)
    error_stack_trace = Column(Text)
    
    # Context information
    item_index = Column(Integer)
    item_data = Column(JSON, default=dict)
    step_name = Column(String(200))
    context_data = Column(JSON, default=dict)
    
    # Error severity
    severity = Column(String(20), default="error")  # info, warning, error, critical
    is_recoverable = Column(Boolean, default=False)
    retry_count = Column(Integer, default=0)
    
    # Resolution tracking
    is_resolved = Column(Boolean, default=False)
    resolution_notes = Column(Text)
    resolved_by = Column(Integer, ForeignKey("users.id"))
    resolved_at = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    operation = relationship("BatchOperation", back_populates="errors")
    resolver = relationship("User", foreign_keys=[resolved_by])
    
    def __repr__(self):
        return f"<BatchError(id={self.id}, operation_id={self.operation_id}, type={self.error_type})>"
    
    def to_dict(self):
        """Convert error record to dictionary."""
        return {
            "id": self.id,
            "operation_id": self.operation_id,
            "error_type": self.error_type,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "item_index": self.item_index,
            "item_data": self.item_data,
            "step_name": self.step_name,
            "context_data": self.context_data,
            "severity": self.severity,
            "is_recoverable": self.is_recoverable,
            "retry_count": self.retry_count,
            "is_resolved": self.is_resolved,
            "resolution_notes": self.resolution_notes,
            "resolved_by": self.resolved_by,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class BatchValidationRule(Base):
    """Model for storing batch validation rules."""
    
    __tablename__ = "batch_validation_rules"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    
    # Rule configuration
    rule_type = Column(String(50), nullable=False)  # schema, business, consistency, quality
    rule_definition = Column(JSON, nullable=False)
    severity = Column(String(20), default="error")
    is_active = Column(Boolean, default=True)
    
    # Scope
    project_id = Column(Integer, ForeignKey("projects.id"))
    applies_to_operation_types = Column(JSON, default=list)
    
    # Usage statistics
    usage_count = Column(Integer, default=0)
    success_rate = Column(Float, default=0.0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project = relationship("Project")
    
    def __repr__(self):
        return f"<BatchValidationRule(id={self.id}, name={self.name}, type={self.rule_type})>"
    
    def to_dict(self):
        """Convert validation rule to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "rule_type": self.rule_type,
            "rule_definition": self.rule_definition,
            "severity": self.severity,
            "is_active": self.is_active,
            "project_id": self.project_id,
            "applies_to_operation_types": self.applies_to_operation_types,
            "usage_count": self.usage_count,
            "success_rate": self.success_rate,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }