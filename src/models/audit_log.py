"""
Audit Log Model

Database model for tracking administrative actions and security events.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from src.core.database import Base


class AuditLog(Base):
    """Audit log model for tracking administrative actions."""
    
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(100), nullable=False, index=True)
    target_type = Column(String(50), nullable=False, index=True)
    target_id = Column(Integer, nullable=True, index=True)
    details = Column(JSON)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    ip_address = Column(String(45))  # IPv6 compatible
    user_agent = Column(Text)
    
    # Relationships
    admin = relationship("User", foreign_keys=[admin_id])
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, admin_id={self.admin_id}, action='{self.action}', timestamp='{self.timestamp}')>"
    
    def to_dict(self):
        """Convert audit log to dictionary."""
        return {
            "id": self.id,
            "admin_id": self.admin_id,
            "admin_username": self.admin.username if self.admin else None,
            "action": self.action,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "details": self.details,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent
        }


class SystemLog(Base):
    """System log model for tracking system events and errors."""
    
    __tablename__ = "system_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    level = Column(String(20), nullable=False, index=True)  # INFO, WARNING, ERROR, CRITICAL
    category = Column(String(50), nullable=False, index=True)  # AUTH, DATABASE, API, etc.
    message = Column(Text, nullable=False)
    details = Column(JSON)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    source = Column(String(100))  # Source module/function
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    session_id = Column(String(100), nullable=True, index=True)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    
    def __repr__(self):
        return f"<SystemLog(id={self.id}, level='{self.level}', category='{self.category}', timestamp='{self.timestamp}')>"
    
    def to_dict(self):
        """Convert system log to dictionary."""
        return {
            "id": self.id,
            "level": self.level,
            "category": self.category,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "source": self.source,
            "user_id": self.user_id,
            "username": self.user.username if self.user else None,
            "session_id": self.session_id
        }


class SecurityEvent(Base):
    """Security event model for tracking security-related incidents."""
    
    __tablename__ = "security_events"
    
    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(50), nullable=False, index=True)  # FAILED_LOGIN, SUSPICIOUS_ACTIVITY, etc.
    severity = Column(String(20), nullable=False, index=True)  # LOW, MEDIUM, HIGH, CRITICAL
    description = Column(Text, nullable=False)
    ip_address = Column(String(45), nullable=True, index=True)
    user_agent = Column(Text)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    username = Column(String(50), nullable=True, index=True)  # Store username even if user doesn't exist
    details = Column(JSON)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    resolved = Column(Boolean, default=False, index=True)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_notes = Column(Text)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    resolver = relationship("User", foreign_keys=[resolved_by])
    
    def __repr__(self):
        return f"<SecurityEvent(id={self.id}, event_type='{self.event_type}', severity='{self.severity}', timestamp='{self.timestamp}')>"
    
    def to_dict(self):
        """Convert security event to dictionary."""
        return {
            "id": self.id,
            "event_type": self.event_type,
            "severity": self.severity,
            "description": self.description,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "user_id": self.user_id,
            "username": self.username,
            "details": self.details,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "resolved": self.resolved,
            "resolved_by": self.resolved_by,
            "resolver_username": self.resolver.username if self.resolver else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolution_notes": self.resolution_notes
        }