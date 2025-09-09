"""
Labels API Routes

Label management endpoints for annotation categories and hierarchical labels.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_

from src.core.database import get_db
from src.core.security import get_current_user
from src.models.user import User
from src.models.label import Label
from src.models.project import Project

router = APIRouter()


# Pydantic models
class LabelCreate(BaseModel):
    name: str
    description: Optional[str] = None
    color: str = "#007bff"
    icon: Optional[str] = None
    parent_id: Optional[int] = None
    order_index: int = 0
    shortcut_key: Optional[str] = None
    metadata: Optional[dict] = None
    project_id: int


class LabelResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    color: str
    icon: Optional[str]
    parent_id: Optional[int]
    order_index: int
    is_active: bool
    shortcut_key: Optional[str]
    metadata: Optional[dict]
    usage_count: int
    created_at: Optional[str]
    updated_at: Optional[str]
    project_id: int
    annotation_count: int
    children: Optional[List] = None


class LabelUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    parent_id: Optional[int] = None
    order_index: Optional[int] = None
    is_active: Optional[bool] = None
    shortcut_key: Optional[str] = None
    metadata: Optional[dict] = None


@router.post("/", response_model=LabelResponse, status_code=status.HTTP_201_CREATED)
async def create_label(
    label_data: LabelCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new label."""
    
    # Verify project access
    project = db.query(Project).filter(Project.id == label_data.project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    if project.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only project owner can create labels"
        )
    
    # Check if label name already exists in project
    existing_label = db.query(Label).filter(
        Label.project_id == label_data.project_id,
        Label.name == label_data.name
    ).first()
    
    if existing_label:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Label with this name already exists in the project"
        )
    
    # Validate parent label if specified
    if label_data.parent_id:
        parent_label = db.query(Label).filter(
            Label.id == label_data.parent_id,
            Label.project_id == label_data.project_id
        ).first()
        
        if not parent_label:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent label not found in this project"
            )
    
    # Create label
    label = Label(
        name=label_data.name,
        description=label_data.description,
        color=label_data.color,
        icon=label_data.icon,
        parent_id=label_data.parent_id,
        order_index=label_data.order_index,
        shortcut_key=label_data.shortcut_key,
        metadata=label_data.metadata or {},
        project_id=label_data.project_id
    )
    
    db.add(label)
    db.commit()
    db.refresh(label)
    
    return LabelResponse(**label.to_dict())


@router.get("/", response_model=List[LabelResponse])
async def list_labels(
    project_id: Optional[int] = Query(None),
    parent_id: Optional[int] = Query(None),
    include_children: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List labels with optional hierarchy."""
    
    query = db.query(Label).join(Project)
    
    # Access control: only labels from accessible projects
    query = query.filter(
        or_(
            Project.owner_id == current_user.id,
            Project.is_public == True
        )
    )
    
    # Filter by project
    if project_id:
        query = query.filter(Label.project_id == project_id)
    
    # Filter by parent (for hierarchical listing)
    if parent_id is not None:
        query = query.filter(Label.parent_id == parent_id)
    
    # Order by project, parent, and order_index
    query = query.order_by(Label.project_id, Label.parent_id, Label.order_index, Label.name)
    
    # Apply pagination
    labels = query.offset(skip).limit(limit).all()
    
    return [LabelResponse(**label.to_dict(include_children=include_children)) for label in labels]


@router.get("/{label_id}", response_model=LabelResponse)
async def get_label(
    label_id: int,
    include_children: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific label by ID."""
    
    label = db.query(Label).filter(Label.id == label_id).first()
    
    if not label:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Label not found"
        )
    
    # Check project access
    if (label.project.owner_id != current_user.id and 
        not label.project.is_public):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this label"
        )
    
    return LabelResponse(**label.to_dict(include_children=include_children))


@router.put("/{label_id}", response_model=LabelResponse)
async def update_label(
    label_id: int,
    label_update: LabelUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a label."""
    
    label = db.query(Label).filter(Label.id == label_id).first()
    
    if not label:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Label not found"
        )
    
    # Check project ownership
    if label.project.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only project owner can update labels"
        )
    
    # Update fields
    update_data = label_update.dict(exclude_unset=True)
    
    # Check name uniqueness if name is being updated
    if "name" in update_data:
        existing_label = db.query(Label).filter(
            Label.project_id == label.project_id,
            Label.name == update_data["name"],
            Label.id != label.id
        ).first()
        
        if existing_label:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Label with this name already exists in the project"
            )
    
    # Validate parent if being updated
    if "parent_id" in update_data and update_data["parent_id"]:
        parent_label = db.query(Label).filter(
            Label.id == update_data["parent_id"],
            Label.project_id == label.project_id
        ).first()
        
        if not parent_label:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent label not found in this project"
            )
        
        # Prevent circular references
        if update_data["parent_id"] == label.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Label cannot be its own parent"
            )
    
    for field, value in update_data.items():
        setattr(label, field, value)
    
    db.commit()
    db.refresh(label)
    
    return LabelResponse(**label.to_dict())


@router.delete("/{label_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_label(
    label_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a label."""
    
    label = db.query(Label).filter(Label.id == label_id).first()
    
    if not label:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Label not found"
        )
    
    # Check project ownership
    if label.project.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only project owner can delete labels"
        )
    
    # Check if label has annotations
    if label.annotations:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete label that has annotations. Please remove annotations first."
        )
    
    # Check if label has child labels
    if hasattr(label, 'children') and label.children:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete label that has child labels. Please remove child labels first."
        )
    
    db.delete(label)
    db.commit()
    
    return None


@router.get("/project/{project_id}/hierarchy", response_model=List[LabelResponse])
async def get_label_hierarchy(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get label hierarchy for a project (root labels with children)."""
    
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
    
    # Get root labels (no parent) with their children
    root_labels = db.query(Label).filter(
        Label.project_id == project_id,
        Label.parent_id.is_(None)
    ).order_by(Label.order_index, Label.name).all()
    
    return [LabelResponse(**label.to_dict(include_children=True)) for label in root_labels]