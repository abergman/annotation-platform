"""
Texts API Routes

Text document management endpoints for upload and text processing.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_
import os
import aiofiles

from src.core.database import get_db
from src.core.security import get_current_user
from src.core.config import settings
from src.models.user import User
from src.models.project import Project
from src.models.text import Text
from src.utils.text_processor import process_uploaded_file

router = APIRouter()


# Pydantic models
class TextCreate(BaseModel):
    title: str
    content: str
    project_id: int
    language: str = "en"
    metadata: Optional[dict] = None


class TextResponse(BaseModel):
    id: int
    title: str
    content: Optional[str] = None
    original_filename: Optional[str]
    file_type: Optional[str]
    file_size: Optional[int]
    language: str
    word_count: Optional[int]
    character_count: Optional[int]
    metadata: Optional[dict]
    is_processed: str
    processing_notes: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]
    project_id: int
    annotation_count: int


class TextUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    language: Optional[str] = None
    metadata: Optional[dict] = None


@router.post("/", response_model=TextResponse, status_code=status.HTTP_201_CREATED)
async def create_text(
    text_data: TextCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new text document."""
    
    # Verify project access
    project = db.query(Project).filter(Project.id == text_data.project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    if project.owner_id != current_user.id and not project.is_public:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this project"
        )
    
    # Calculate text statistics
    word_count = len(text_data.content.split())
    character_count = len(text_data.content)
    
    text = Text(
        title=text_data.title,
        content=text_data.content,
        project_id=text_data.project_id,
        language=text_data.language,
        word_count=word_count,
        character_count=character_count,
        metadata=text_data.metadata or {},
        is_processed="completed"
    )
    
    db.add(text)
    db.commit()
    db.refresh(text)
    
    return TextResponse(**text.to_dict())


@router.post("/upload", response_model=TextResponse, status_code=status.HTTP_201_CREATED)
async def upload_text_file(
    project_id: int,
    file: UploadFile = File(...),
    title: Optional[str] = None,
    language: str = "en",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload and process a text file."""
    
    # Verify project access
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    if project.owner_id != current_user.id and not project.is_public:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this project"
        )
    
    # Validate file
    if file.size > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {settings.MAX_FILE_SIZE} bytes"
        )
    
    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not supported. Allowed types: {settings.ALLOWED_EXTENSIONS}"
        )
    
    # Create text record
    text = Text(
        title=title or file.filename,
        content="",  # Will be populated after processing
        original_filename=file.filename,
        file_type=file_extension,
        file_size=file.size,
        project_id=project_id,
        language=language,
        is_processed="processing"
    )
    
    db.add(text)
    db.commit()
    db.refresh(text)
    
    try:
        # Process the uploaded file
        content = await process_uploaded_file(file, file_extension)
        
        # Update text with processed content
        text.content = content
        text.word_count = len(content.split())
        text.character_count = len(content)
        text.is_processed = "completed"
        
    except Exception as e:
        text.is_processed = "failed"
        text.processing_notes = str(e)
    
    db.commit()
    db.refresh(text)
    
    return TextResponse(**text.to_dict())


@router.get("/", response_model=List[TextResponse])
async def list_texts(
    project_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List texts with pagination and search."""
    
    query = db.query(Text)
    
    # Filter by project if specified
    if project_id:
        # Verify project access
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        if project.owner_id != current_user.id and not project.is_public:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this project"
            )
        
        query = query.filter(Text.project_id == project_id)
    else:
        # Show texts from accessible projects only
        accessible_projects = db.query(Project).filter(
            or_(
                Project.owner_id == current_user.id,
                Project.is_public == True
            )
        ).all()
        
        project_ids = [p.id for p in accessible_projects]
        if project_ids:
            query = query.filter(Text.project_id.in_(project_ids))
        else:
            return []  # No accessible projects
    
    # Search filter
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                Text.title.ilike(search_filter),
                Text.content.ilike(search_filter)
            )
        )
    
    # Apply pagination
    texts = query.offset(skip).limit(limit).all()
    
    return [TextResponse(**text.to_dict(include_content=False)) for text in texts]


@router.get("/{text_id}", response_model=TextResponse)
async def get_text(
    text_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific text by ID."""
    
    text = db.query(Text).filter(Text.id == text_id).first()
    
    if not text:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Text not found"
        )
    
    # Check project access
    if text.project.owner_id != current_user.id and not text.project.is_public:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this text"
        )
    
    return TextResponse(**text.to_dict())


@router.put("/{text_id}", response_model=TextResponse)
async def update_text(
    text_id: int,
    text_update: TextUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a text."""
    
    text = db.query(Text).filter(Text.id == text_id).first()
    
    if not text:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Text not found"
        )
    
    # Check project ownership
    if text.project.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only project owner can update texts"
        )
    
    # Update fields
    update_data = text_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        if field == "content":
            # Recalculate statistics if content changes
            text.word_count = len(value.split())
            text.character_count = len(value)
        setattr(text, field, value)
    
    db.commit()
    db.refresh(text)
    
    return TextResponse(**text.to_dict())


@router.delete("/{text_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_text(
    text_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a text."""
    
    text = db.query(Text).filter(Text.id == text_id).first()
    
    if not text:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Text not found"
        )
    
    # Check project ownership
    if text.project.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only project owner can delete texts"
        )
    
    db.delete(text)
    db.commit()
    
    return None