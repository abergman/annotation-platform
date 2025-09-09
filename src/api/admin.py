"""
Admin API Routes

Comprehensive administrative functionality for system management.
"""

import os
import json
import csv
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc, asc, or_, and_, text

from src.core.database import get_db
from src.middleware.admin_middleware import require_admin, require_super_admin, AuditLogger
from src.models.user import User
from src.models.project import Project
from src.models.text import Text
from src.models.annotation import Annotation
from src.models.label import Label
from src.models.audit_log import AuditLog, SystemLog, SecurityEvent
from src.core.config import settings
from src.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., regex=r'^[^@]+@[^@]+\.[^@]+$')
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None
    institution: Optional[str] = None
    role: str = Field(default="researcher")
    is_active: bool = Field(default=True)
    is_verified: bool = Field(default=False)
    is_admin: bool = Field(default=False)


class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[str] = Field(None, regex=r'^[^@]+@[^@]+\.[^@]+$')
    full_name: Optional[str] = None
    institution: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    is_admin: Optional[bool] = None


class BulkUserOperation(BaseModel):
    user_ids: List[int]
    operation: str = Field(..., regex="^(activate|deactivate|verify|unverify|delete|promote|demote)$")
    role: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    is_public: Optional[bool] = None
    owner_id: Optional[int] = None


class SystemConfig(BaseModel):
    config_key: str
    config_value: Any
    description: Optional[str] = None


class SystemStats(BaseModel):
    total_users: int
    active_users: int
    total_projects: int
    active_projects: int
    total_texts: int
    total_annotations: int
    total_labels: int
    system_uptime: Optional[str] = None
    disk_usage: Optional[Dict[str, Any]] = None
    memory_usage: Optional[Dict[str, Any]] = None


# ============================================================================
# USER MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/users", dependencies=[Depends(require_admin)])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None, description="Search by username, email, or full name"),
    role: Optional[str] = Query(None, description="Filter by role"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    is_admin: Optional[bool] = Query(None, description="Filter by admin status"),
    sort_by: str = Query("created_at", regex="^(username|email|created_at|last_login)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin)
):
    """List users with advanced filtering, search, and pagination."""
    
    query = db.query(User)
    
    # Apply filters
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                User.username.ilike(search_pattern),
                User.email.ilike(search_pattern),
                User.full_name.ilike(search_pattern)
            )
        )
    
    if role:
        query = query.filter(User.role == role)
    
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    
    if is_admin is not None:
        query = query.filter(User.is_admin == is_admin)
    
    # Apply sorting
    sort_column = getattr(User, sort_by)
    if sort_order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(asc(sort_column))
    
    # Get total count before pagination
    total = query.count()
    
    # Apply pagination
    users = query.offset(skip).limit(limit).all()
    
    # Log the action
    AuditLogger.log_admin_action(
        admin_user=current_admin,
        action="LIST_USERS",
        target_type="user",
        details={
            "filters": {"search": search, "role": role, "is_active": is_active, "is_admin": is_admin},
            "pagination": {"skip": skip, "limit": limit},
            "results_count": len(users)
        },
        db=db
    )
    
    return {
        "users": [user.to_dict() for user in users],
        "pagination": {
            "total": total,
            "skip": skip,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }
    }


@router.post("/users", dependencies=[Depends(require_admin)])
async def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin)
):
    """Create a new user account (admin only)."""
    
    # Check if username already exists
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    
    # Check if email already exists
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists"
        )
    
    # Only super admins can create admin users
    if user_data.is_admin and not (current_admin.role == 'super_admin' or 
                                   db.query(User).filter(User.is_admin == True).count() == 1):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can create admin users"
        )
    
    # Hash password
    from src.core.security import get_password_hash
    hashed_password = get_password_hash(user_data.password)
    
    # Create user
    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        institution=user_data.institution,
        role=user_data.role,
        is_active=user_data.is_active,
        is_verified=user_data.is_verified,
        is_admin=user_data.is_admin
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Log the action
    AuditLogger.log_admin_action(
        admin_user=current_admin,
        action="CREATE_USER",
        target_type="user",
        target_id=user.id,
        details={"username": user.username, "email": user.email, "role": user.role},
        db=db
    )
    
    return {"message": "User created successfully", "user": user.to_dict()}


@router.get("/users/{user_id}", dependencies=[Depends(require_admin)])
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin)
):
    """Get detailed information about a specific user."""
    
    user = db.query(User).options(
        joinedload(User.owned_projects),
        joinedload(User.annotations)
    ).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get user statistics
    project_count = len(user.owned_projects)
    annotation_count = len(user.annotations)
    
    user_data = user.to_dict()
    user_data.update({
        "project_count": project_count,
        "annotation_count": annotation_count,
        "recent_activity": []  # TODO: Implement recent activity tracking
    })
    
    # Log the action
    AuditLogger.log_admin_action(
        admin_user=current_admin,
        action="VIEW_USER",
        target_type="user",
        target_id=user.id,
        details={"username": user.username},
        db=db
    )
    
    return {"user": user_data}


@router.put("/users/{user_id}", dependencies=[Depends(require_admin)])
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin)
):
    """Update user information."""
    
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent admins from modifying their own admin status
    if user.id == current_admin.id and user_update.is_admin is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify your own admin status"
        )
    
    # Only super admins can grant/revoke admin privileges
    if user_update.is_admin is not None and user_update.is_admin != user.is_admin:
        if not (current_admin.role == 'super_admin' or 
                db.query(User).filter(User.is_admin == True).count() == 1):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super admins can modify admin privileges"
            )
    
    # Store original values for audit log
    original_values = {
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "is_admin": user.is_admin
    }
    
    # Update fields
    update_data = user_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    
    # Log the action
    AuditLogger.log_admin_action(
        admin_user=current_admin,
        action="UPDATE_USER",
        target_type="user",
        target_id=user.id,
        details={
            "username": user.username,
            "original_values": original_values,
            "updated_values": update_data
        },
        db=db
    )
    
    return {"message": "User updated successfully", "user": user.to_dict()}


@router.delete("/users/{user_id}", dependencies=[Depends(require_admin)])
async def delete_user(
    user_id: int,
    force: bool = Query(False, description="Force delete even if user has associated data"),
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin)
):
    """Delete a user account."""
    
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent deleting self
    if user.id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    # Check for associated data
    project_count = db.query(Project).filter(Project.owner_id == user_id).count()
    annotation_count = db.query(Annotation).filter(Annotation.annotator_id == user_id).count()
    
    if (project_count > 0 or annotation_count > 0) and not force:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User has {project_count} projects and {annotation_count} annotations. Use force=true to delete anyway."
        )
    
    username = user.username
    
    # Delete user and cascade delete associated data
    db.delete(user)
    db.commit()
    
    # Log the action
    AuditLogger.log_admin_action(
        admin_user=current_admin,
        action="DELETE_USER",
        target_type="user",
        target_id=user_id,
        details={
            "username": username,
            "force": force,
            "associated_data": {"projects": project_count, "annotations": annotation_count}
        },
        db=db
    )
    
    return {"message": f"User '{username}' deleted successfully"}


@router.post("/users/bulk", dependencies=[Depends(require_admin)])
async def bulk_user_operations(
    operation: BulkUserOperation,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin)
):
    """Perform bulk operations on multiple users."""
    
    users = db.query(User).filter(User.id.in_(operation.user_ids)).all()
    
    if len(users) != len(operation.user_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more users not found"
        )
    
    # Prevent operations on self
    if current_admin.id in operation.user_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot perform bulk operations on your own account"
        )
    
    results = []
    
    for user in users:
        try:
            if operation.operation == "activate":
                user.is_active = True
            elif operation.operation == "deactivate":
                user.is_active = False
            elif operation.operation == "verify":
                user.is_verified = True
            elif operation.operation == "unverify":
                user.is_verified = False
            elif operation.operation == "delete":
                db.delete(user)
                results.append({"user_id": user.id, "status": "deleted"})
                continue
            elif operation.operation == "promote":
                if not (current_admin.role == 'super_admin' or 
                        db.query(User).filter(User.is_admin == True).count() == 1):
                    results.append({"user_id": user.id, "status": "error", "message": "Insufficient permissions"})
                    continue
                user.is_admin = True
            elif operation.operation == "demote":
                if not (current_admin.role == 'super_admin' or 
                        db.query(User).filter(User.is_admin == True).count() == 1):
                    results.append({"user_id": user.id, "status": "error", "message": "Insufficient permissions"})
                    continue
                user.is_admin = False
            
            if operation.role and operation.operation not in ["delete"]:
                user.role = operation.role
            
            user.updated_at = datetime.utcnow()
            results.append({"user_id": user.id, "status": "success"})
            
        except Exception as e:
            results.append({"user_id": user.id, "status": "error", "message": str(e)})
    
    db.commit()
    
    # Log the action
    AuditLogger.log_admin_action(
        admin_user=current_admin,
        action="BULK_USER_OPERATION",
        target_type="user",
        details={
            "operation": operation.operation,
            "user_ids": operation.user_ids,
            "role": operation.role,
            "results": results
        },
        db=db
    )
    
    return {"message": "Bulk operation completed", "results": results}


# ============================================================================
# PROJECT ADMINISTRATION ENDPOINTS
# ============================================================================

@router.get("/projects", dependencies=[Depends(require_admin)])
async def list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None, description="Search by project name or description"),
    owner_id: Optional[int] = Query(None, description="Filter by owner ID"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    is_public: Optional[bool] = Query(None, description="Filter by public status"),
    sort_by: str = Query("created_at", regex="^(name|created_at|updated_at)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin)
):
    """List projects with advanced filtering and statistics."""
    
    query = db.query(Project).options(
        joinedload(Project.owner),
        joinedload(Project.texts),
        joinedload(Project.labels)
    )
    
    # Apply filters
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Project.name.ilike(search_pattern),
                Project.description.ilike(search_pattern)
            )
        )
    
    if owner_id:
        query = query.filter(Project.owner_id == owner_id)
    
    if is_active is not None:
        query = query.filter(Project.is_active == is_active)
    
    if is_public is not None:
        query = query.filter(Project.is_public == is_public)
    
    # Apply sorting
    sort_column = getattr(Project, sort_by)
    if sort_order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(asc(sort_column))
    
    # Get total count before pagination
    total = query.count()
    
    # Apply pagination
    projects = query.offset(skip).limit(limit).all()
    
    # Enhance project data with statistics
    project_data = []
    for project in projects:
        project_dict = project.to_dict()
        project_dict["owner_username"] = project.owner.username if project.owner else None
        
        # Get annotation statistics
        annotation_count = db.query(Annotation).join(Text).filter(Text.project_id == project.id).count()
        project_dict["annotation_count"] = annotation_count
        
        project_data.append(project_dict)
    
    # Log the action
    AuditLogger.log_admin_action(
        admin_user=current_admin,
        action="LIST_PROJECTS",
        target_type="project",
        details={
            "filters": {"search": search, "owner_id": owner_id, "is_active": is_active},
            "results_count": len(projects)
        },
        db=db
    )
    
    return {
        "projects": project_data,
        "pagination": {
            "total": total,
            "skip": skip,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }
    }


@router.get("/projects/{project_id}", dependencies=[Depends(require_admin)])
async def get_project_details(
    project_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin)
):
    """Get detailed project information including statistics."""
    
    project = db.query(Project).options(
        joinedload(Project.owner),
        joinedload(Project.texts),
        joinedload(Project.labels)
    ).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Get detailed statistics
    text_count = len(project.texts)
    label_count = len(project.labels)
    
    # Get annotation statistics
    annotation_stats = db.query(
        func.count(Annotation.id).label('total_annotations'),
        func.count(func.distinct(Annotation.annotator_id)).label('unique_annotators')
    ).join(Text).filter(Text.project_id == project_id).first()
    
    # Get annotator activity
    annotator_activity = db.query(
        User.username,
        func.count(Annotation.id).label('annotation_count')
    ).join(Annotation).join(Text).filter(
        Text.project_id == project_id
    ).group_by(User.username).all()
    
    project_data = project.to_dict()
    project_data.update({
        "owner_username": project.owner.username if project.owner else None,
        "statistics": {
            "text_count": text_count,
            "label_count": label_count,
            "total_annotations": annotation_stats.total_annotations or 0,
            "unique_annotators": annotation_stats.unique_annotators or 0,
            "annotator_activity": [
                {"username": username, "annotation_count": count}
                for username, count in annotator_activity
            ]
        }
    })
    
    # Log the action
    AuditLogger.log_admin_action(
        admin_user=current_admin,
        action="VIEW_PROJECT",
        target_type="project",
        target_id=project.id,
        details={"project_name": project.name},
        db=db
    )
    
    return {"project": project_data}


@router.put("/projects/{project_id}", dependencies=[Depends(require_admin)])
async def update_project(
    project_id: int,
    project_update: ProjectUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin)
):
    """Update project information."""
    
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Store original values for audit log
    original_values = {
        "name": project.name,
        "description": project.description,
        "is_active": project.is_active,
        "is_public": project.is_public,
        "owner_id": project.owner_id
    }
    
    # Update fields
    update_data = project_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)
    
    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(project)
    
    # Log the action
    AuditLogger.log_admin_action(
        admin_user=current_admin,
        action="UPDATE_PROJECT",
        target_type="project",
        target_id=project.id,
        details={
            "project_name": project.name,
            "original_values": original_values,
            "updated_values": update_data
        },
        db=db
    )
    
    return {"message": "Project updated successfully", "project": project.to_dict()}


@router.delete("/projects/{project_id}", dependencies=[Depends(require_admin)])
async def delete_project(
    project_id: int,
    force: bool = Query(False, description="Force delete even if project has associated data"),
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin)
):
    """Delete a project and optionally all associated data."""
    
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Check for associated data
    text_count = len(project.texts)
    annotation_count = db.query(Annotation).join(Text).filter(Text.project_id == project_id).count()
    
    if (text_count > 0 or annotation_count > 0) and not force:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Project has {text_count} texts and {annotation_count} annotations. Use force=true to delete anyway."
        )
    
    project_name = project.name
    
    # Delete project and cascade delete associated data
    db.delete(project)
    db.commit()
    
    # Log the action
    AuditLogger.log_admin_action(
        admin_user=current_admin,
        action="DELETE_PROJECT",
        target_type="project",
        target_id=project_id,
        details={
            "project_name": project_name,
            "force": force,
            "associated_data": {"texts": text_count, "annotations": annotation_count}
        },
        db=db
    )
    
    return {"message": f"Project '{project_name}' deleted successfully"}


# ============================================================================
# SYSTEM STATISTICS AND ANALYTICS
# ============================================================================

@router.get("/statistics/overview", dependencies=[Depends(require_admin)])
async def get_system_overview(
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin)
):
    """Get comprehensive system statistics and overview."""
    
    # Basic counts
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    total_projects = db.query(Project).count()
    active_projects = db.query(Project).filter(Project.is_active == True).count()
    total_texts = db.query(Text).count()
    total_annotations = db.query(Annotation).count()
    total_labels = db.query(Label).count()
    
    # Recent activity (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    new_users_30d = db.query(User).filter(User.created_at >= thirty_days_ago).count()
    new_projects_30d = db.query(Project).filter(Project.created_at >= thirty_days_ago).count()
    new_annotations_30d = db.query(Annotation).filter(Annotation.created_at >= thirty_days_ago).count()
    
    # User activity
    users_with_recent_login = db.query(User).filter(
        User.last_login >= thirty_days_ago,
        User.last_login.isnot(None)
    ).count()
    
    # Top active users
    top_annotators = db.query(
        User.username,
        func.count(Annotation.id).label('annotation_count')
    ).join(Annotation).group_by(User.username).order_by(
        desc('annotation_count')
    ).limit(10).all()
    
    # Project activity
    most_active_projects = db.query(
        Project.name,
        func.count(Annotation.id).label('annotation_count')
    ).join(Text).join(Annotation).group_by(Project.name).order_by(
        desc('annotation_count')
    ).limit(10).all()
    
    # System resource usage (basic)
    import psutil
    disk_usage = psutil.disk_usage('/')
    memory_info = psutil.virtual_memory()
    
    # Log the action
    AuditLogger.log_admin_action(
        admin_user=current_admin,
        action="VIEW_SYSTEM_OVERVIEW",
        target_type="system",
        details={},
        db=db
    )
    
    return {
        "overview": {
            "total_users": total_users,
            "active_users": active_users,
            "total_projects": total_projects,
            "active_projects": active_projects,
            "total_texts": total_texts,
            "total_annotations": total_annotations,
            "total_labels": total_labels
        },
        "recent_activity": {
            "new_users_30d": new_users_30d,
            "new_projects_30d": new_projects_30d,
            "new_annotations_30d": new_annotations_30d,
            "users_with_recent_login": users_with_recent_login
        },
        "top_annotators": [
            {"username": username, "annotation_count": count}
            for username, count in top_annotators
        ],
        "most_active_projects": [
            {"project_name": name, "annotation_count": count}
            for name, count in most_active_projects
        ],
        "system_resources": {
            "disk_usage": {
                "total": disk_usage.total,
                "used": disk_usage.used,
                "free": disk_usage.free,
                "percent": disk_usage.percent
            },
            "memory_usage": {
                "total": memory_info.total,
                "used": memory_info.used,
                "available": memory_info.available,
                "percent": memory_info.percent
            }
        }
    }


@router.get("/statistics/timeline", dependencies=[Depends(require_admin)])
async def get_system_timeline(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin)
):
    """Get timeline statistics for the specified number of days."""
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Daily user registrations
    daily_users = db.query(
        func.date(User.created_at).label('date'),
        func.count(User.id).label('count')
    ).filter(User.created_at >= start_date).group_by(
        func.date(User.created_at)
    ).order_by('date').all()
    
    # Daily project creation
    daily_projects = db.query(
        func.date(Project.created_at).label('date'),
        func.count(Project.id).label('count')
    ).filter(Project.created_at >= start_date).group_by(
        func.date(Project.created_at)
    ).order_by('date').all()
    
    # Daily annotation activity
    daily_annotations = db.query(
        func.date(Annotation.created_at).label('date'),
        func.count(Annotation.id).label('count')
    ).filter(Annotation.created_at >= start_date).group_by(
        func.date(Annotation.created_at)
    ).order_by('date').all()
    
    # Log the action
    AuditLogger.log_admin_action(
        admin_user=current_admin,
        action="VIEW_SYSTEM_TIMELINE",
        target_type="system",
        details={"days": days},
        db=db
    )
    
    return {
        "timeline": {
            "daily_users": [
                {"date": str(date), "count": count}
                for date, count in daily_users
            ],
            "daily_projects": [
                {"date": str(date), "count": count}
                for date, count in daily_projects
            ],
            "daily_annotations": [
                {"date": str(date), "count": count}
                for date, count in daily_annotations
            ]
        },
        "period": {
            "start_date": start_date.isoformat(),
            "end_date": datetime.utcnow().isoformat(),
            "days": days
        }
    }


# ============================================================================
# DATABASE MAINTENANCE AND HEALTH
# ============================================================================

@router.get("/health/database", dependencies=[Depends(require_admin)])
async def database_health_check(
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin)
):
    """Comprehensive database health check and statistics."""
    
    health_data = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {}
    }
    
    try:
        # Basic connectivity test
        db.execute(text("SELECT 1"))
        health_data["checks"]["connectivity"] = {"status": "ok", "message": "Database connection successful"}
        
        # Table integrity checks
        tables = ["users", "projects", "texts", "annotations", "labels", "audit_logs"]
        for table in tables:
            try:
                count = db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                health_data["checks"][f"table_{table}"] = {
                    "status": "ok",
                    "count": count,
                    "message": f"Table {table} accessible with {count} records"
                }
            except Exception as e:
                health_data["status"] = "degraded"
                health_data["checks"][f"table_{table}"] = {
                    "status": "error",
                    "error": str(e)
                }
        
        # Check for orphaned records
        orphaned_annotations = db.execute(text(
            "SELECT COUNT(*) FROM annotations a LEFT JOIN texts t ON a.text_id = t.id WHERE t.id IS NULL"
        )).scalar()
        
        orphaned_texts = db.execute(text(
            "SELECT COUNT(*) FROM texts t LEFT JOIN projects p ON t.project_id = p.id WHERE p.id IS NULL"
        )).scalar()
        
        health_data["checks"]["data_integrity"] = {
            "status": "ok" if orphaned_annotations == 0 and orphaned_texts == 0 else "warning",
            "orphaned_annotations": orphaned_annotations,
            "orphaned_texts": orphaned_texts,
            "message": "Data integrity check completed"
        }
        
        # Database size information
        try:
            db_size = db.execute(text("SELECT pg_size_pretty(pg_database_size(current_database()))")).scalar()
            health_data["checks"]["database_size"] = {
                "status": "ok",
                "size": db_size,
                "message": f"Database size: {db_size}"
            }
        except:
            health_data["checks"]["database_size"] = {
                "status": "info",
                "message": "Database size information not available"
            }
        
    except Exception as e:
        health_data["status"] = "unhealthy"
        health_data["checks"]["connectivity"] = {
            "status": "error",
            "error": str(e)
        }
    
    # Log the action
    AuditLogger.log_admin_action(
        admin_user=current_admin,
        action="DATABASE_HEALTH_CHECK",
        target_type="system",
        details={"status": health_data["status"]},
        db=db
    )
    
    return health_data


@router.post("/maintenance/cleanup", dependencies=[Depends(require_super_admin)])
async def database_cleanup(
    dry_run: bool = Query(True, description="Perform dry run without actual cleanup"),
    max_age_days: int = Query(90, description="Maximum age in days for log entries"),
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_super_admin)
):
    """Clean up old log entries and orphaned records."""
    
    cleanup_date = datetime.utcnow() - timedelta(days=max_age_days)
    
    cleanup_results = {
        "dry_run": dry_run,
        "cleanup_date": cleanup_date.isoformat(),
        "results": {}
    }
    
    try:
        # Clean up old audit logs
        old_audit_logs = db.query(AuditLog).filter(AuditLog.timestamp < cleanup_date)
        audit_count = old_audit_logs.count()
        
        if not dry_run:
            old_audit_logs.delete(synchronize_session=False)
        
        cleanup_results["results"]["audit_logs"] = {
            "status": "completed" if not dry_run else "simulated",
            "records_affected": audit_count
        }
        
        # Clean up old system logs
        old_system_logs = db.query(SystemLog).filter(SystemLog.timestamp < cleanup_date)
        system_count = old_system_logs.count()
        
        if not dry_run:
            old_system_logs.delete(synchronize_session=False)
        
        cleanup_results["results"]["system_logs"] = {
            "status": "completed" if not dry_run else "simulated",
            "records_affected": system_count
        }
        
        # Clean up resolved security events older than specified date
        old_security_events = db.query(SecurityEvent).filter(
            SecurityEvent.resolved == True,
            SecurityEvent.resolved_at < cleanup_date
        )
        security_count = old_security_events.count()
        
        if not dry_run:
            old_security_events.delete(synchronize_session=False)
        
        cleanup_results["results"]["security_events"] = {
            "status": "completed" if not dry_run else "simulated",
            "records_affected": security_count
        }
        
        if not dry_run:
            db.commit()
        
        cleanup_results["status"] = "success"
        
    except Exception as e:
        cleanup_results["status"] = "error"
        cleanup_results["error"] = str(e)
        if not dry_run:
            db.rollback()
    
    # Log the action
    AuditLogger.log_admin_action(
        admin_user=current_admin,
        action="DATABASE_CLEANUP",
        target_type="system",
        details={
            "dry_run": dry_run,
            "max_age_days": max_age_days,
            "results": cleanup_results
        },
        db=db
    )
    
    return cleanup_results


# ============================================================================
# AUDIT LOG MANAGEMENT
# ============================================================================

@router.get("/audit-logs", dependencies=[Depends(require_admin)])
async def get_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    admin_id: Optional[int] = Query(None, description="Filter by admin user ID"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    target_type: Optional[str] = Query(None, description="Filter by target type"),
    start_date: Optional[datetime] = Query(None, description="Filter from date"),
    end_date: Optional[datetime] = Query(None, description="Filter to date"),
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin)
):
    """Get audit logs with filtering and pagination."""
    
    query = db.query(AuditLog).options(joinedload(AuditLog.admin))
    
    # Apply filters
    if admin_id:
        query = query.filter(AuditLog.admin_id == admin_id)
    
    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action}%"))
    
    if target_type:
        query = query.filter(AuditLog.target_type == target_type)
    
    if start_date:
        query = query.filter(AuditLog.timestamp >= start_date)
    
    if end_date:
        query = query.filter(AuditLog.timestamp <= end_date)
    
    # Order by timestamp desc (newest first)
    query = query.order_by(desc(AuditLog.timestamp))
    
    # Get total count before pagination
    total = query.count()
    
    # Apply pagination
    audit_logs = query.offset(skip).limit(limit).all()
    
    return {
        "audit_logs": [log.to_dict() for log in audit_logs],
        "pagination": {
            "total": total,
            "skip": skip,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }
    }


@router.get("/security-events", dependencies=[Depends(require_admin)])
async def get_security_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    resolved: Optional[bool] = Query(None, description="Filter by resolution status"),
    start_date: Optional[datetime] = Query(None, description="Filter from date"),
    end_date: Optional[datetime] = Query(None, description="Filter to date"),
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin)
):
    """Get security events with filtering and pagination."""
    
    query = db.query(SecurityEvent).options(
        joinedload(SecurityEvent.user),
        joinedload(SecurityEvent.resolver)
    )
    
    # Apply filters
    if event_type:
        query = query.filter(SecurityEvent.event_type == event_type)
    
    if severity:
        query = query.filter(SecurityEvent.severity == severity)
    
    if resolved is not None:
        query = query.filter(SecurityEvent.resolved == resolved)
    
    if start_date:
        query = query.filter(SecurityEvent.timestamp >= start_date)
    
    if end_date:
        query = query.filter(SecurityEvent.timestamp <= end_date)
    
    # Order by timestamp desc (newest first)
    query = query.order_by(desc(SecurityEvent.timestamp))
    
    # Get total count before pagination
    total = query.count()
    
    # Apply pagination
    security_events = query.offset(skip).limit(limit).all()
    
    return {
        "security_events": [event.to_dict() for event in security_events],
        "pagination": {
            "total": total,
            "skip": skip,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }
    }


@router.put("/security-events/{event_id}/resolve", dependencies=[Depends(require_admin)])
async def resolve_security_event(
    event_id: int,
    resolution_notes: str = Query(..., description="Notes about the resolution"),
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin)
):
    """Mark a security event as resolved."""
    
    event = db.query(SecurityEvent).filter(SecurityEvent.id == event_id).first()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Security event not found"
        )
    
    event.resolved = True
    event.resolved_by = current_admin.id
    event.resolved_at = datetime.utcnow()
    event.resolution_notes = resolution_notes
    
    db.commit()
    db.refresh(event)
    
    # Log the action
    AuditLogger.log_admin_action(
        admin_user=current_admin,
        action="RESOLVE_SECURITY_EVENT",
        target_type="security_event",
        target_id=event.id,
        details={
            "event_type": event.event_type,
            "severity": event.severity,
            "resolution_notes": resolution_notes
        },
        db=db
    )
    
    return {"message": "Security event resolved successfully", "event": event.to_dict()}


# ============================================================================
# DATA EXPORT/IMPORT
# ============================================================================

@router.get("/export/system-data", dependencies=[Depends(require_super_admin)])
async def export_system_data(
    format: str = Query("json", regex="^(json|csv)$"),
    include_users: bool = Query(True),
    include_projects: bool = Query(True),
    include_annotations: bool = Query(False),
    include_audit_logs: bool = Query(False),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_super_admin)
):
    """Export system data in various formats."""
    
    export_data = {
        "export_info": {
            "timestamp": datetime.utcnow().isoformat(),
            "exported_by": current_admin.username,
            "format": format,
            "date_range": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None
            }
        }
    }
    
    # Build date filter for applicable queries
    date_filter = []
    if start_date:
        date_filter.append(lambda query, date_col: query.filter(date_col >= start_date))
    if end_date:
        date_filter.append(lambda query, date_col: query.filter(date_col <= end_date))
    
    try:
        # Export users
        if include_users:
            query = db.query(User)
            for filter_func in date_filter:
                query = filter_func(query, User.created_at)
            
            users = query.all()
            export_data["users"] = [
                {
                    k: v for k, v in user.to_dict().items() 
                    if k not in ["hashed_password"]  # Exclude sensitive data
                }
                for user in users
            ]
        
        # Export projects
        if include_projects:
            query = db.query(Project).options(joinedload(Project.owner))
            for filter_func in date_filter:
                query = filter_func(query, Project.created_at)
            
            projects = query.all()
            export_data["projects"] = [
                {
                    **project.to_dict(),
                    "owner_username": project.owner.username if project.owner else None
                }
                for project in projects
            ]
        
        # Export annotations (if requested)
        if include_annotations:
            query = db.query(Annotation).options(
                joinedload(Annotation.annotator),
                joinedload(Annotation.text),
                joinedload(Annotation.labels)
            )
            for filter_func in date_filter:
                query = filter_func(query, Annotation.created_at)
            
            annotations = query.all()
            export_data["annotations"] = [
                {
                    **annotation.to_dict(),
                    "annotator_username": annotation.annotator.username if annotation.annotator else None,
                    "text_content": annotation.text.content[:100] if annotation.text else None,  # Preview only
                    "label_names": [label.name for label in annotation.labels] if annotation.labels else []
                }
                for annotation in annotations
            ]
        
        # Export audit logs (if requested)
        if include_audit_logs:
            query = db.query(AuditLog).options(joinedload(AuditLog.admin))
            for filter_func in date_filter:
                query = filter_func(query, AuditLog.timestamp)
            
            audit_logs = query.all()
            export_data["audit_logs"] = [log.to_dict() for log in audit_logs]
        
        # Log the action
        AuditLogger.log_admin_action(
            admin_user=current_admin,
            action="EXPORT_SYSTEM_DATA",
            target_type="system",
            details={
                "format": format,
                "includes": {
                    "users": include_users,
                    "projects": include_projects,
                    "annotations": include_annotations,
                    "audit_logs": include_audit_logs
                },
                "date_range": {
                    "start": start_date.isoformat() if start_date else None,
                    "end": end_date.isoformat() if end_date else None
                }
            },
            db=db
        )
        
        # Return appropriate format
        if format == "json":
            from io import StringIO
            import json
            
            output = StringIO()
            json.dump(export_data, output, indent=2, default=str)
            output.seek(0)
            
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="application/json",
                headers={"Content-Disposition": f"attachment; filename=system_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"}
            )
        
        elif format == "csv":
            # For CSV, we'll create separate files for each data type
            # This is a simplified version - in practice, you might want to create a ZIP file
            from io import StringIO
            import csv
            
            output = StringIO()
            
            # Export users to CSV
            if include_users and "users" in export_data:
                writer = csv.DictWriter(output, fieldnames=export_data["users"][0].keys())
                writer.writeheader()
                writer.writerows(export_data["users"])
            
            output.seek(0)
            
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=users_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"}
            )
    
    except Exception as e:
        logger.error(f"Export failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {str(e)}"
        )


# ============================================================================
# CONFIGURATION MANAGEMENT
# ============================================================================

@router.get("/config", dependencies=[Depends(require_admin)])
async def get_system_configuration(
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin)
):
    """Get current system configuration (safe values only)."""
    
    # Return safe configuration values (not secrets)
    safe_config = {
        "application": {
            "app_name": settings.APP_NAME,
            "debug": settings.DEBUG,
            "host": settings.HOST,
            "port": settings.PORT
        },
        "features": {
            "max_file_size": settings.MAX_FILE_SIZE,
            "allowed_extensions": settings.ALLOWED_EXTENSIONS,
            "max_annotations_per_text": settings.MAX_ANNOTATIONS_PER_TEXT,
            "max_labels_per_project": settings.MAX_LABELS_PER_PROJECT,
            "export_formats": settings.EXPORT_FORMATS
        },
        "security": {
            "access_token_expire_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
            "algorithm": settings.ALGORITHM
        },
        "cors": {
            "allowed_origins": settings.ALLOWED_ORIGINS
        }
    }
    
    # Log the action
    AuditLogger.log_admin_action(
        admin_user=current_admin,
        action="VIEW_SYSTEM_CONFIG",
        target_type="system",
        details={},
        db=db
    )
    
    return {"configuration": safe_config}


# ============================================================================
# DASHBOARD DATA ENDPOINTS
# ============================================================================

@router.get("/dashboard/summary", dependencies=[Depends(require_admin)])
async def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin)
):
    """Get summary data for admin dashboard."""
    
    # Quick stats for dashboard cards
    today = datetime.utcnow().date()
    week_ago = datetime.utcnow() - timedelta(days=7)
    
    stats = {
        "totals": {
            "users": db.query(User).count(),
            "active_users": db.query(User).filter(User.is_active == True).count(),
            "projects": db.query(Project).count(),
            "active_projects": db.query(Project).filter(Project.is_active == True).count(),
            "annotations": db.query(Annotation).count(),
            "texts": db.query(Text).count()
        },
        "recent": {
            "new_users_today": db.query(User).filter(func.date(User.created_at) == today).count(),
            "new_projects_week": db.query(Project).filter(Project.created_at >= week_ago).count(),
            "new_annotations_week": db.query(Annotation).filter(Annotation.created_at >= week_ago).count(),
            "recent_logins": db.query(User).filter(
                User.last_login >= week_ago,
                User.last_login.isnot(None)
            ).count()
        },
        "alerts": {
            "inactive_users": db.query(User).filter(User.is_active == False).count(),
            "unresolved_security_events": db.query(SecurityEvent).filter(SecurityEvent.resolved == False).count()
        }
    }
    
    # Recent activity
    recent_users = db.query(User).order_by(desc(User.created_at)).limit(5).all()
    recent_projects = db.query(Project).options(joinedload(Project.owner)).order_by(desc(Project.created_at)).limit(5).all()
    
    stats["recent_activity"] = {
        "users": [{"id": u.id, "username": u.username, "created_at": u.created_at.isoformat()} for u in recent_users],
        "projects": [{"id": p.id, "name": p.name, "owner": p.owner.username if p.owner else None, "created_at": p.created_at.isoformat()} for p in recent_projects]
    }
    
    return stats