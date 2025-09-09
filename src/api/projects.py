"""
Projects API Routes

Project management endpoints for creating and managing annotation projects.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_

from src.core.database import get_db
from src.core.security import get_current_user
from src.models.user import User
from src.models.project import Project

router = APIRouter()


# Pydantic models
class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    annotation_guidelines: Optional[str] = None
    allow_multiple_labels: bool = True
    require_all_texts: bool = False
    inter_annotator_agreement: bool = False
    is_public: bool = False


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    annotation_guidelines: Optional[str] = None
    allow_multiple_labels: Optional[bool] = None
    require_all_texts: Optional[bool] = None
    inter_annotator_agreement: Optional[bool] = None
    is_public: Optional[bool] = None
    is_active: Optional[bool] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    annotation_guidelines: Optional[str]
    allow_multiple_labels: bool
    require_all_texts: bool
    inter_annotator_agreement: bool
    is_active: bool
    is_public: bool
    created_at: Optional[str]
    updated_at: Optional[str]
    owner_id: int
    text_count: int
    label_count: int


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new annotation project."""
    
    project = Project(
        name=project_data.name,
        description=project_data.description,
        annotation_guidelines=project_data.annotation_guidelines,
        allow_multiple_labels=project_data.allow_multiple_labels,
        require_all_texts=project_data.require_all_texts,
        inter_annotator_agreement=project_data.inter_annotator_agreement,
        is_public=project_data.is_public,
        owner_id=current_user.id
    )
    
    db.add(project)
    db.commit()
    db.refresh(project)
    
    return ProjectResponse(**project.to_dict())


@router.get("/", response_model=List[ProjectResponse])
async def list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
    search: Optional[str] = Query(None),
    owner_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List projects with pagination and search."""
    
    query = db.query(Project)
    
    # Filter by owner if requested
    if owner_only:
        query = query.filter(Project.owner_id == current_user.id)
    else:
        # Show user's projects and public projects
        query = query.filter(
            or_(
                Project.owner_id == current_user.id,
                Project.is_public == True
            )
        )
    
    # Search filter
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                Project.name.ilike(search_filter),
                Project.description.ilike(search_filter)
            )
        )
    
    # Apply pagination
    projects = query.offset(skip).limit(limit).all()
    
    return [ProjectResponse(**project.to_dict()) for project in projects]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific project by ID."""
    
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Check access permissions
    if project.owner_id != current_user.id and not project.is_public:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this project"
        )
    
    return ProjectResponse(**project.to_dict())


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    project_update: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a project."""
    
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Check ownership
    if project.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only project owner can update the project"
        )
    
    # Update fields
    update_data = project_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)
    
    db.commit()
    db.refresh(project)
    
    return ProjectResponse(**project.to_dict())


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a project."""
    
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Check ownership
    if project.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only project owner can delete the project"
        )
    
    db.delete(project)
    db.commit()
    
    return None