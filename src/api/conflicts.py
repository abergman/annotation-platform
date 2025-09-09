"""
Conflict Management API

RESTful API endpoints for annotation conflict detection, resolution, and management.
Provides comprehensive conflict management capabilities for multi-user annotation projects.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from pydantic import BaseModel, Field

from src.core.database import get_db
from src.models.conflict import (
    AnnotationConflict, ConflictResolution, ConflictParticipant,
    ResolutionVote, ConflictNotification, ConflictSettings,
    ConflictType, ConflictStatus, ResolutionStrategy, ResolutionOutcome,
    get_conflict_summary, get_project_conflict_stats
)
from src.models.annotation import Annotation
from src.models.user import User
from src.models.project import Project
from src.core.conflict_detection import (
    ConflictDetectionEngine, detect_project_conflicts,
    setup_conflict_monitoring
)
from src.core.conflict_resolution import (
    ConflictResolutionEngine, resolve_conflict, submit_resolution_vote
)
from src.api.auth import get_current_user
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/conflicts", tags=["conflicts"])


# Pydantic models for request/response

class ConflictFilters(BaseModel):
    """Filters for conflict queries."""
    project_id: Optional[int] = None
    status: Optional[ConflictStatus] = None
    conflict_type: Optional[ConflictType] = None
    severity_level: Optional[str] = None
    assigned_resolver_id: Optional[int] = None
    detected_after: Optional[datetime] = None
    detected_before: Optional[datetime] = None


class ConflictDetectionRequest(BaseModel):
    """Request model for conflict detection."""
    project_id: int
    check_new_only: bool = True
    batch_size: int = Field(default=1000, ge=100, le=5000)
    force_detection: bool = False


class ResolutionRequest(BaseModel):
    """Request model for conflict resolution."""
    resolution_strategy: Optional[ResolutionStrategy] = None
    notes: Optional[str] = None
    force_resolution: bool = False


class VoteRequest(BaseModel):
    """Request model for resolution voting."""
    vote_choice: str = Field(..., description="Choice: annotation_a, annotation_b, merge, reject_both")
    rationale: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


class ConflictSettingsRequest(BaseModel):
    """Request model for updating conflict settings."""
    enable_conflict_detection: Optional[bool] = None
    span_overlap_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    confidence_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    auto_detection_enabled: Optional[bool] = None
    default_resolution_strategy: Optional[ResolutionStrategy] = None
    voting_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    expert_assignment_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    auto_merge_enabled: Optional[bool] = None
    notify_on_detection: Optional[bool] = None
    notify_annotators: Optional[bool] = None
    notify_project_admin: Optional[bool] = None
    resolution_timeout_hours: Optional[int] = Field(None, ge=1, le=168)  # 1 hour to 1 week
    max_resolution_attempts: Optional[int] = Field(None, ge=1, le=10)
    enable_automatic_escalation: Optional[bool] = None
    minimum_voter_count: Optional[int] = Field(None, ge=1, le=20)


class ConflictResponse(BaseModel):
    """Response model for conflict data."""
    id: int
    conflict_type: str
    conflict_description: str
    severity_level: str
    status: str
    conflict_score: float
    project_id: int
    text_id: int
    annotation_a_id: int
    annotation_b_id: int
    overlap_percentage: Optional[float]
    assigned_resolver_id: Optional[int]
    detected_at: datetime
    resolved_at: Optional[datetime]
    resolution_count: int = 0
    vote_count: int = 0


class ConflictStatsResponse(BaseModel):
    """Response model for conflict statistics."""
    total_conflicts: int
    status_breakdown: Dict[str, int]
    type_breakdown: Dict[str, int]
    average_resolution_time_hours: float
    resolved_conflicts_count: int
    pending_conflicts_count: int


# API Endpoints

@router.get("/", response_model=List[ConflictResponse])
async def list_conflicts(
    filters: ConflictFilters = Depends(),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List conflicts with optional filtering.
    """
    query = db.query(AnnotationConflict)
    
    # Apply filters
    if filters.project_id is not None:
        # Check if user has access to the project
        project = db.query(Project).filter_by(id=filters.project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # TODO: Add proper project access control
        query = query.filter(AnnotationConflict.project_id == filters.project_id)
    
    if filters.status is not None:
        query = query.filter(AnnotationConflict.status == filters.status)
    
    if filters.conflict_type is not None:
        query = query.filter(AnnotationConflict.conflict_type == filters.conflict_type)
    
    if filters.severity_level is not None:
        query = query.filter(AnnotationConflict.severity_level == filters.severity_level)
    
    if filters.assigned_resolver_id is not None:
        query = query.filter(AnnotationConflict.assigned_resolver_id == filters.assigned_resolver_id)
    
    if filters.detected_after is not None:
        query = query.filter(AnnotationConflict.detected_at >= filters.detected_after)
    
    if filters.detected_before is not None:
        query = query.filter(AnnotationConflict.detected_at <= filters.detected_before)
    
    # Get conflicts with counts
    conflicts = (
        query.offset(skip)
        .limit(limit)
        .all()
    )
    
    # Convert to response format
    response_conflicts = []
    for conflict in conflicts:
        conflict_dict = conflict.to_dict()
        conflict_dict['resolution_count'] = len(conflict.resolutions)
        conflict_dict['vote_count'] = len(conflict.votes)
        response_conflicts.append(ConflictResponse(**conflict_dict))
    
    return response_conflicts


@router.get("/{conflict_id}")
async def get_conflict(
    conflict_id: int,
    include_details: bool = Query(False, description="Include resolutions, votes, and participants"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed information about a specific conflict.
    """
    if include_details:
        conflict_data = get_conflict_summary(db, conflict_id)
        if not conflict_data:
            raise HTTPException(status_code=404, detail="Conflict not found")
        return conflict_data
    else:
        conflict = db.query(AnnotationConflict).filter_by(id=conflict_id).first()
        if not conflict:
            raise HTTPException(status_code=404, detail="Conflict not found")
        
        # TODO: Add access control
        return conflict.to_dict()


@router.post("/detect")
async def detect_conflicts(
    request: ConflictDetectionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Trigger conflict detection for a project.
    """
    # Verify project access
    project = db.query(Project).filter_by(id=request.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # TODO: Add proper project access control
    
    try:
        # Run conflict detection
        if request.force_detection:
            # Run in foreground for immediate results
            conflicts = detect_project_conflicts(
                db, 
                request.project_id, 
                request.check_new_only
            )
            
            return {
                "message": f"Detected {len(conflicts)} conflicts",
                "conflicts_detected": len(conflicts),
                "conflict_ids": [c.id for c in conflicts]
            }
        else:
            # Run in background
            background_tasks.add_task(
                _background_conflict_detection,
                db,
                request.project_id,
                request.check_new_only,
                request.batch_size
            )
            
            return {
                "message": "Conflict detection started in background",
                "project_id": request.project_id
            }
    
    except Exception as e:
        logger.error(f"Error in conflict detection: {e}")
        raise HTTPException(status_code=500, detail=f"Conflict detection failed: {str(e)}")


@router.post("/{conflict_id}/resolve")
async def resolve_conflict_endpoint(
    conflict_id: int,
    request: ResolutionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Attempt to resolve a conflict.
    """
    # Verify conflict exists and user has access
    conflict = db.query(AnnotationConflict).filter_by(id=conflict_id).first()
    if not conflict:
        raise HTTPException(status_code=404, detail="Conflict not found")
    
    # TODO: Add proper access control for resolution
    
    try:
        result = resolve_conflict(
            db, 
            conflict_id, 
            current_user.id,
            request.resolution_strategy
        )
        
        if result.success:
            return {
                "success": True,
                "message": result.description,
                "outcome": result.outcome.value if result.outcome else None,
                "confidence_score": result.confidence_score,
                "final_annotation_id": result.final_annotation.id if result.final_annotation else None,
                "metadata": result.metadata
            }
        else:
            return {
                "success": False,
                "message": result.description,
                "errors": result.errors or [],
                "metadata": result.metadata
            }
    
    except Exception as e:
        logger.error(f"Error resolving conflict {conflict_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Resolution failed: {str(e)}")


@router.post("/{conflict_id}/vote")
async def submit_vote(
    conflict_id: int,
    request: VoteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submit a vote for conflict resolution.
    """
    # Verify conflict exists and is in voting status
    conflict = db.query(AnnotationConflict).filter_by(id=conflict_id).first()
    if not conflict:
        raise HTTPException(status_code=404, detail="Conflict not found")
    
    if conflict.status not in [ConflictStatus.VOTING, ConflictStatus.ASSIGNED, ConflictStatus.IN_REVIEW]:
        raise HTTPException(
            status_code=400, 
            detail=f"Conflict is not open for voting (status: {conflict.status.value})"
        )
    
    # Validate vote choice
    valid_choices = ["annotation_a", "annotation_b", "merge", "reject_both", "escalate"]
    if request.vote_choice not in valid_choices:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid vote choice. Must be one of: {', '.join(valid_choices)}"
        )
    
    try:
        success = submit_resolution_vote(
            db,
            conflict_id,
            current_user.id,
            request.vote_choice,
            request.rationale,
            request.confidence
        )
        
        if success:
            # Update conflict status to voting if not already
            if conflict.status == ConflictStatus.ASSIGNED:
                conflict.status = ConflictStatus.VOTING
                db.commit()
            
            # Get updated vote count
            vote_count = len(conflict.votes)
            
            return {
                "success": True,
                "message": "Vote submitted successfully",
                "vote_choice": request.vote_choice,
                "total_votes": vote_count
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to submit vote")
    
    except Exception as e:
        logger.error(f"Error submitting vote for conflict {conflict_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Vote submission failed: {str(e)}")


@router.get("/{conflict_id}/votes")
async def get_conflict_votes(
    conflict_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all votes for a conflict.
    """
    conflict = db.query(AnnotationConflict).filter_by(id=conflict_id).first()
    if not conflict:
        raise HTTPException(status_code=404, detail="Conflict not found")
    
    # TODO: Add access control
    
    votes = []
    for vote in conflict.votes:
        vote_data = {
            "id": vote.id,
            "voter_id": vote.voter_id,
            "voter_username": vote.voter.username if vote.voter else None,
            "vote_choice": vote.vote_choice,
            "confidence": vote.confidence,
            "rationale": vote.rationale,
            "cast_at": vote.cast_at.isoformat() if vote.cast_at else None,
            "vote_weight": vote.vote_weight
        }
        votes.append(vote_data)
    
    # Calculate vote summary
    vote_counts = {}
    for vote in conflict.votes:
        choice = vote.vote_choice
        if choice not in vote_counts:
            vote_counts[choice] = 0
        vote_counts[choice] += 1
    
    return {
        "conflict_id": conflict_id,
        "total_votes": len(votes),
        "votes": votes,
        "vote_summary": vote_counts,
        "status": conflict.status.value
    }


@router.post("/{conflict_id}/assign")
async def assign_conflict(
    conflict_id: int,
    resolver_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Assign a conflict to a specific resolver.
    """
    # Verify conflict exists
    conflict = db.query(AnnotationConflict).filter_by(id=conflict_id).first()
    if not conflict:
        raise HTTPException(status_code=404, detail="Conflict not found")
    
    # Verify resolver exists
    resolver = db.query(User).filter_by(id=resolver_id).first()
    if not resolver:
        raise HTTPException(status_code=404, detail="Resolver not found")
    
    # TODO: Add proper access control
    
    try:
        conflict.assigned_resolver_id = resolver_id
        conflict.assigned_at = datetime.utcnow()
        conflict.status = ConflictStatus.ASSIGNED
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Conflict assigned to {resolver.username}",
            "conflict_id": conflict_id,
            "resolver_id": resolver_id,
            "assigned_at": conflict.assigned_at.isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error assigning conflict {conflict_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Assignment failed: {str(e)}")


@router.get("/projects/{project_id}/stats", response_model=ConflictStatsResponse)
async def get_project_conflict_stats_endpoint(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get conflict statistics for a project.
    """
    # Verify project exists and user has access
    project = db.query(Project).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # TODO: Add proper project access control
    
    try:
        stats = get_project_conflict_stats(db, project_id)
        return ConflictStatsResponse(**stats)
    
    except Exception as e:
        logger.error(f"Error getting conflict stats for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.get("/projects/{project_id}/settings")
async def get_project_conflict_settings(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get conflict resolution settings for a project.
    """
    project = db.query(Project).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # TODO: Add proper access control
    
    settings = (
        db.query(ConflictSettings)
        .filter_by(project_id=project_id)
        .first()
    )
    
    if not settings:
        # Create default settings
        settings = ConflictSettings(project_id=project_id)
        db.add(settings)
        db.commit()
    
    return {
        "project_id": project_id,
        "enable_conflict_detection": settings.enable_conflict_detection,
        "span_overlap_threshold": settings.span_overlap_threshold,
        "confidence_threshold": settings.confidence_threshold,
        "auto_detection_enabled": settings.auto_detection_enabled,
        "default_resolution_strategy": settings.default_resolution_strategy.value if settings.default_resolution_strategy else None,
        "voting_threshold": settings.voting_threshold,
        "expert_assignment_threshold": settings.expert_assignment_threshold,
        "auto_merge_enabled": settings.auto_merge_enabled,
        "notify_on_detection": settings.notify_on_detection,
        "notify_annotators": settings.notify_annotators,
        "notify_project_admin": settings.notify_project_admin,
        "resolution_timeout_hours": settings.resolution_timeout_hours,
        "max_resolution_attempts": settings.max_resolution_attempts,
        "enable_automatic_escalation": settings.enable_automatic_escalation,
        "minimum_voter_count": settings.minimum_voter_count,
        "created_at": settings.created_at.isoformat() if settings.created_at else None,
        "updated_at": settings.updated_at.isoformat() if settings.updated_at else None
    }


@router.put("/projects/{project_id}/settings")
async def update_project_conflict_settings(
    project_id: int,
    request: ConflictSettingsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update conflict resolution settings for a project.
    """
    project = db.query(Project).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # TODO: Add proper access control (project admin only)
    
    settings = (
        db.query(ConflictSettings)
        .filter_by(project_id=project_id)
        .first()
    )
    
    if not settings:
        settings = ConflictSettings(project_id=project_id)
        db.add(settings)
    
    # Update settings
    update_data = request.dict(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(settings, field):
            setattr(settings, field, value)
    
    settings.updated_at = datetime.utcnow()
    
    try:
        db.commit()
        return {
            "success": True,
            "message": "Conflict settings updated successfully",
            "project_id": project_id,
            "updated_fields": list(update_data.keys())
        }
    
    except Exception as e:
        logger.error(f"Error updating conflict settings for project {project_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")


@router.delete("/{conflict_id}")
async def delete_conflict(
    conflict_id: int,
    force: bool = Query(False, description="Force delete even if resolved"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a conflict (admin only).
    """
    conflict = db.query(AnnotationConflict).filter_by(id=conflict_id).first()
    if not conflict:
        raise HTTPException(status_code=404, detail="Conflict not found")
    
    # TODO: Add proper admin access control
    
    # Check if conflict can be deleted
    if conflict.status == ConflictStatus.RESOLVED and not force:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete resolved conflict without force flag"
        )
    
    try:
        db.delete(conflict)
        db.commit()
        
        return {
            "success": True,
            "message": f"Conflict {conflict_id} deleted successfully"
        }
    
    except Exception as e:
        logger.error(f"Error deleting conflict {conflict_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


# Background tasks

async def _background_conflict_detection(
    db: Session,
    project_id: int,
    check_new_only: bool,
    batch_size: int
):
    """Background task for conflict detection."""
    try:
        logger.info(f"Starting background conflict detection for project {project_id}")
        
        conflicts = detect_project_conflicts(db, project_id, check_new_only)
        
        logger.info(f"Background conflict detection completed: {len(conflicts)} conflicts detected")
        
        # TODO: Send notification to project admin about completion
        
    except Exception as e:
        logger.error(f"Background conflict detection failed for project {project_id}: {e}")


# Health check endpoint

@router.get("/health")
async def conflict_system_health(db: Session = Depends(get_db)):
    """
    Check the health of the conflict resolution system.
    """
    try:
        # Check database connectivity
        conflict_count = db.query(func.count(AnnotationConflict.id)).scalar()
        
        # Check recent conflicts
        recent_cutoff = datetime.utcnow() - timedelta(hours=24)
        recent_conflicts = (
            db.query(func.count(AnnotationConflict.id))
            .filter(AnnotationConflict.detected_at >= recent_cutoff)
            .scalar()
        )
        
        # Check pending resolutions
        pending_count = (
            db.query(func.count(AnnotationConflict.id))
            .filter(AnnotationConflict.status.in_([
                ConflictStatus.DETECTED,
                ConflictStatus.ASSIGNED,
                ConflictStatus.IN_REVIEW,
                ConflictStatus.VOTING
            ]))
            .scalar()
        )
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "total_conflicts": conflict_count,
            "recent_conflicts_24h": recent_conflicts,
            "pending_resolutions": pending_count,
            "database_connected": True
        }
    
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e),
                "database_connected": False
            }
        )