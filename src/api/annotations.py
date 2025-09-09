"""
Annotations API Routes

Text annotation management endpoints for creating and managing annotations.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
import logging

from src.core.database import get_db
from src.core.security import get_current_user
from src.models.user import User
from src.models.annotation import Annotation
from src.models.text import Text
from src.models.label import Label
from src.services.agreement_service import AgreementService

router = APIRouter()


# Pydantic models
class AnnotationCreate(BaseModel):
    text_id: int
    label_id: int
    start_char: int
    end_char: int
    selected_text: str
    notes: Optional[str] = None
    confidence_score: float = 1.0
    metadata: Optional[dict] = None


class AnnotationResponse(BaseModel):
    id: int
    start_char: int
    end_char: int
    selected_text: str
    notes: Optional[str]
    confidence_score: float
    metadata: Optional[dict]
    context_before: Optional[str]
    context_after: Optional[str]
    is_validated: str
    validation_notes: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]
    text_id: int
    annotator_id: int
    label_id: int
    label_name: Optional[str]
    label_color: Optional[str]
    annotator_username: Optional[str]


class AnnotationUpdate(BaseModel):
    label_id: Optional[int] = None
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    selected_text: Optional[str] = None
    notes: Optional[str] = None
    confidence_score: Optional[float] = None
    metadata: Optional[dict] = None


class AnnotationValidation(BaseModel):
    is_validated: str  # pending, approved, rejected
    validation_notes: Optional[str] = None


@router.post("/", response_model=AnnotationResponse, status_code=status.HTTP_201_CREATED)
async def create_annotation(
    annotation_data: AnnotationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new annotation."""
    
    # Verify text exists and user has access
    text = db.query(Text).filter(Text.id == annotation_data.text_id).first()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Text not found"
        )
    
    if text.project.owner_id != current_user.id and not text.project.is_public:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this text"
        )
    
    # Verify label exists and belongs to the same project
    label = db.query(Label).filter(Label.id == annotation_data.label_id).first()
    if not label:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Label not found"
        )
    
    if label.project_id != text.project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Label does not belong to the same project as the text"
        )
    
    # Validate annotation span
    if (annotation_data.start_char < 0 or 
        annotation_data.end_char > len(text.content) or
        annotation_data.start_char >= annotation_data.end_char):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid annotation span"
        )
    
    # Extract context
    context_start = max(0, annotation_data.start_char - 100)
    context_end = min(len(text.content), annotation_data.end_char + 100)
    context_before = text.content[context_start:annotation_data.start_char]
    context_after = text.content[annotation_data.end_char:context_end]
    
    # Create annotation
    annotation = Annotation(
        text_id=annotation_data.text_id,
        label_id=annotation_data.label_id,
        annotator_id=current_user.id,
        start_char=annotation_data.start_char,
        end_char=annotation_data.end_char,
        selected_text=annotation_data.selected_text,
        notes=annotation_data.notes,
        confidence_score=annotation_data.confidence_score,
        metadata=annotation_data.metadata or {},
        context_before=context_before[-200:],  # Last 200 chars
        context_after=context_after[:200]      # First 200 chars
    )
    
    db.add(annotation)
    
    # Update label usage count
    label.usage_count += 1
    
    db.commit()
    db.refresh(annotation)
    
    # Trigger agreement calculation if enabled
    try:
        agreement_service = AgreementService(db)
        agreement_service.trigger_agreement_calculation(annotation.id)
    except Exception as e:
        # Don't fail annotation creation if agreement calculation fails
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to trigger agreement calculation: {str(e)}")
    
    return AnnotationResponse(**annotation.to_dict())


@router.get("/", response_model=List[AnnotationResponse])
async def list_annotations(
    text_id: Optional[int] = Query(None),
    project_id: Optional[int] = Query(None),
    label_id: Optional[int] = Query(None),
    annotator_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List annotations with filters."""
    
    query = db.query(Annotation).join(Text).join(Text.project)
    
    # Access control: only annotations from accessible projects
    query = query.filter(
        or_(
            Text.project.has(owner_id=current_user.id),
            Text.project.has(is_public=True)
        )
    )
    
    # Apply filters
    if text_id:
        query = query.filter(Annotation.text_id == text_id)
    
    if project_id:
        query = query.filter(Text.project_id == project_id)
    
    if label_id:
        query = query.filter(Annotation.label_id == label_id)
    
    if annotator_id:
        query = query.filter(Annotation.annotator_id == annotator_id)
    
    # Apply pagination
    annotations = query.offset(skip).limit(limit).all()
    
    return [AnnotationResponse(**annotation.to_dict()) for annotation in annotations]


@router.get("/{annotation_id}", response_model=AnnotationResponse)
async def get_annotation(
    annotation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific annotation by ID."""
    
    annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
    
    if not annotation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Annotation not found"
        )
    
    # Check project access
    if (annotation.text.project.owner_id != current_user.id and 
        not annotation.text.project.is_public):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this annotation"
        )
    
    return AnnotationResponse(**annotation.to_dict())


@router.put("/{annotation_id}", response_model=AnnotationResponse)
async def update_annotation(
    annotation_id: int,
    annotation_update: AnnotationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update an annotation."""
    
    annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
    
    if not annotation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Annotation not found"
        )
    
    # Check if user can modify (annotator or project owner)
    if (annotation.annotator_id != current_user.id and 
        annotation.text.project.owner_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the annotator or project owner can update this annotation"
        )
    
    # Update fields
    update_data = annotation_update.dict(exclude_unset=True)
    
    # Validate label if being updated
    if "label_id" in update_data:
        label = db.query(Label).filter(Label.id == update_data["label_id"]).first()
        if not label or label.project_id != annotation.text.project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid label for this project"
            )
    
    # Validate span if being updated
    if "start_char" in update_data or "end_char" in update_data:
        start_char = update_data.get("start_char", annotation.start_char)
        end_char = update_data.get("end_char", annotation.end_char)
        
        if (start_char < 0 or 
            end_char > len(annotation.text.content) or
            start_char >= end_char):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid annotation span"
            )
    
    for field, value in update_data.items():
        setattr(annotation, field, value)
    
    db.commit()
    db.refresh(annotation)
    
    # Trigger agreement calculation if enabled and annotation content changed
    if any(field in update_data for field in ['label_id', 'start_char', 'end_char']):
        try:
            agreement_service = AgreementService(db)
            agreement_service.trigger_agreement_calculation(annotation.id)
        except Exception as e:
            # Don't fail annotation update if agreement calculation fails
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to trigger agreement calculation: {str(e)}")
    
    return AnnotationResponse(**annotation.to_dict())


@router.put("/{annotation_id}/validate", response_model=AnnotationResponse)
async def validate_annotation(
    annotation_id: int,
    validation: AnnotationValidation,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Validate or reject an annotation (project owner only)."""
    
    annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
    
    if not annotation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Annotation not found"
        )
    
    # Only project owner can validate
    if annotation.text.project.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only project owner can validate annotations"
        )
    
    annotation.is_validated = validation.is_validated
    annotation.validation_notes = validation.validation_notes
    
    db.commit()
    db.refresh(annotation)
    
    return AnnotationResponse(**annotation.to_dict())


@router.delete("/{annotation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_annotation(
    annotation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete an annotation."""
    
    annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
    
    if not annotation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Annotation not found"
        )
    
    # Check if user can delete (annotator or project owner)
    if (annotation.annotator_id != current_user.id and 
        annotation.text.project.owner_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the annotator or project owner can delete this annotation"
        )
    
    # Update label usage count
    if annotation.label:
        annotation.label.usage_count = max(0, annotation.label.usage_count - 1)
    
    db.delete(annotation)
    db.commit()
    
    return None