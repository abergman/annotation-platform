"""
Annotation Model

Database model for text annotations with support for spans and labels.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON, Float
from sqlalchemy.orm import relationship

from src.core.database import Base


class Annotation(Base):
    """Annotation model for labeled text spans."""
    
    __tablename__ = "annotations"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Text span information
    start_char = Column(Integer, nullable=False)
    end_char = Column(Integer, nullable=False)
    selected_text = Column(Text, nullable=False)
    
    # Annotation metadata
    notes = Column(Text)
    confidence_score = Column(Float, default=1.0)  # 0.0 to 1.0
    metadata = Column(JSON, default=dict)
    
    # Context information
    context_before = Column(String(200))  # Text before the annotation
    context_after = Column(String(200))   # Text after the annotation
    
    # Validation status
    is_validated = Column(String(20), default="pending")  # pending, approved, rejected
    validation_notes = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign keys
    text_id = Column(Integer, ForeignKey("texts.id"), nullable=False)
    annotator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    label_id = Column(Integer, ForeignKey("labels.id"), nullable=False)
    
    # Relationships
    text = relationship("Text", back_populates="annotations")
    annotator = relationship("User", back_populates="annotations")
    label = relationship("Label", back_populates="annotations")
    
    def __repr__(self):
        return f"<Annotation(id={self.id}, text_id={self.text_id}, label_id={self.label_id})>"
    
    def to_dict(self):
        """Convert annotation to dictionary."""
        return {
            "id": self.id,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "selected_text": self.selected_text,
            "notes": self.notes,
            "confidence_score": self.confidence_score,
            "metadata": self.metadata,
            "context_before": self.context_before,
            "context_after": self.context_after,
            "is_validated": self.is_validated,
            "validation_notes": self.validation_notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "text_id": self.text_id,
            "annotator_id": self.annotator_id,
            "label_id": self.label_id,
            "label_name": self.label.name if self.label else None,
            "label_color": self.label.color if self.label else None,
            "annotator_username": self.annotator.username if self.annotator else None
        }