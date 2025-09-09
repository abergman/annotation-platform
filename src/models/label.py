"""
Label Model

Database model for annotation labels/categories with hierarchical support.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship

from src.core.database import Base


class Label(Base):
    """Label model for annotation categories."""
    
    __tablename__ = "labels"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    
    # Visual properties
    color = Column(String(7), default="#007bff")  # Hex color code
    icon = Column(String(50))
    
    # Hierarchical support
    parent_id = Column(Integer, ForeignKey("labels.id"))
    order_index = Column(Integer, default=0)
    
    # Label configuration
    is_active = Column(Boolean, default=True)
    shortcut_key = Column(String(10))
    metadata = Column(JSON, default=dict)
    
    # Usage statistics
    usage_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign keys
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    
    # Relationships
    project = relationship("Project", back_populates="labels")
    annotations = relationship("Annotation", back_populates="label", cascade="all, delete-orphan")
    
    # Self-referential relationship for hierarchy
    parent = relationship("Label", remote_side=[id], backref="children")
    
    def __repr__(self):
        return f"<Label(id={self.id}, name='{self.name}', project_id={self.project_id})>"
    
    def to_dict(self, include_children=False):
        """Convert label to dictionary."""
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "color": self.color,
            "icon": self.icon,
            "parent_id": self.parent_id,
            "order_index": self.order_index,
            "is_active": self.is_active,
            "shortcut_key": self.shortcut_key,
            "metadata": self.metadata,
            "usage_count": self.usage_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "project_id": self.project_id,
            "annotation_count": len(self.annotations) if self.annotations else 0
        }
        
        if include_children and hasattr(self, 'children'):
            result["children"] = [child.to_dict() for child in self.children]
            
        return result