"""
Project Model

Database model for annotation projects and their configuration.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship

from src.core.database import Base


class Project(Base):
    """Project model for organizing annotation tasks."""
    
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text)
    
    # Project settings
    annotation_guidelines = Column(Text)
    allow_multiple_labels = Column(Boolean, default=True)
    require_all_texts = Column(Boolean, default=False)
    inter_annotator_agreement = Column(Boolean, default=False)
    
    # Project metadata
    metadata = Column(JSON, default=dict)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_public = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign keys
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Relationships
    owner = relationship("User", back_populates="owned_projects")
    texts = relationship("Text", back_populates="project", cascade="all, delete-orphan")
    labels = relationship("Label", back_populates="project", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Project(id={self.id}, name='{self.name}', owner_id={self.owner_id})>"
    
    def to_dict(self):
        """Convert project to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "annotation_guidelines": self.annotation_guidelines,
            "allow_multiple_labels": self.allow_multiple_labels,
            "require_all_texts": self.require_all_texts,
            "inter_annotator_agreement": self.inter_annotator_agreement,
            "metadata": self.metadata,
            "is_active": self.is_active,
            "is_public": self.is_public,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "owner_id": self.owner_id,
            "text_count": len(self.texts) if self.texts else 0,
            "label_count": len(self.labels) if self.labels else 0
        }