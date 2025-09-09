"""
Text Model

Database model for texts to be annotated.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text as TextColumn, ForeignKey, JSON
from sqlalchemy.orm import relationship

from src.core.database import Base


class Text(Base):
    """Text model for documents to be annotated."""
    
    __tablename__ = "texts"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    content = Column(TextColumn, nullable=False)
    
    # File information
    original_filename = Column(String(255))
    file_type = Column(String(50))
    file_size = Column(Integer)
    
    # Text metadata
    language = Column(String(10), default="en")
    word_count = Column(Integer)
    character_count = Column(Integer)
    metadata = Column(JSON, default=dict)
    
    # Processing status
    is_processed = Column(String(20), default="pending")  # pending, processing, completed, failed
    processing_notes = Column(TextColumn)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign keys
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    
    # Relationships
    project = relationship("Project", back_populates="texts")
    annotations = relationship("Annotation", back_populates="text", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Text(id={self.id}, title='{self.title[:50]}...', project_id={self.project_id})>"
    
    def to_dict(self, include_content=True):
        """Convert text to dictionary."""
        result = {
            "id": self.id,
            "title": self.title,
            "original_filename": self.original_filename,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "language": self.language,
            "word_count": self.word_count,
            "character_count": self.character_count,
            "metadata": self.metadata,
            "is_processed": self.is_processed,
            "processing_notes": self.processing_notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "project_id": self.project_id,
            "annotation_count": len(self.annotations) if self.annotations else 0
        }
        
        if include_content:
            result["content"] = self.content
            
        return result