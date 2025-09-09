"""
Batch Operations API for Annotation Management System

This module provides efficient batch operations for managing large annotation datasets
including creation, updates, validation, export, and user management operations.
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, validator
from uuid import uuid4
import asyncio
import json
import csv
import io
from datetime import datetime
import logging
from contextlib import asynccontextmanager

from src.core.database import get_db
from src.models.batch_models import BatchOperation, BatchProgress, BatchError
from src.models.annotation import Annotation
from src.models.label import Label
from src.models.user import User
from src.models.project import Project
from src.models.text import Text
from src.utils.batch_processor import BatchProcessor
from src.utils.progress_tracker import ProgressTracker
from src.utils.validation_engine import ValidationEngine
from src.core.security import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/batch", tags=["batch"])

# Pydantic Models for Request/Response
class BatchAnnotationCreate(BaseModel):
    """Model for batch annotation creation"""
    project_id: int
    annotations: List[Dict[str, Any]]
    validate_before_create: bool = True
    rollback_on_error: bool = True
    
    @validator('annotations')
    def validate_annotations(cls, v):
        if len(v) > 10000:
            raise ValueError("Maximum 10,000 annotations per batch")
        return v

class BatchTextImport(BaseModel):
    """Model for bulk text import"""
    project_id: int
    format: str = "json"  # json, csv, txt
    auto_detect_labels: bool = False
    chunk_size: int = 1000
    
class BatchValidationRequest(BaseModel):
    """Model for mass validation request"""
    annotation_ids: List[int]
    validation_type: str = "quality"  # quality, consistency, completeness
    auto_approve: bool = False
    approval_threshold: float = 0.8

class BatchExportRequest(BaseModel):
    """Model for batch export request"""
    project_id: int
    export_format: str = "json"  # json, csv, coco, yolo
    include_metadata: bool = True
    filter_criteria: Optional[Dict[str, Any]] = None
    
class BulkUserPermission(BaseModel):
    """Model for bulk user permission management"""
    user_ids: List[int]
    project_id: int
    permission_level: str  # read, write, admin
    action: str = "grant"  # grant, revoke, update

class BatchLabelManagement(BaseModel):
    """Model for batch label operations"""
    label_ids: List[int]
    action: str  # assign, unassign, merge, delete
    target_annotations: Optional[List[int]] = None
    merge_target_id: Optional[int] = None

class BatchOperationStatus(BaseModel):
    """Model for batch operation status response"""
    operation_id: str
    status: str  # pending, running, completed, failed, cancelled
    progress: float
    total_items: int
    processed_items: int
    failed_items: int
    created_at: datetime
    updated_at: datetime
    errors: List[str] = []
    
# Global batch processor instance
batch_processor = BatchProcessor()
progress_tracker = ProgressTracker()
validation_engine = ValidationEngine()

@router.post("/annotations/create", response_model=Dict[str, Any])
async def create_batch_annotations(
    request: BatchAnnotationCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create annotations in batch with progress tracking and rollback capability.
    
    This endpoint allows bulk creation of annotations with:
    - Real-time progress tracking
    - Validation before creation
    - Rollback capability on errors
    - Performance optimization for large datasets
    """
    try:
        # Validate project access
        project = db.query(Project).filter(Project.id == request.project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
            
        # Check user permissions
        if not has_write_permission(current_user, project):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        
        # Validate annotation data structure
        for i, annotation_data in enumerate(request.annotations):
            required_fields = ["start_char", "end_char", "selected_text", "text_id", "label_id"]
            for field in required_fields:
                if field not in annotation_data:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Missing required field '{field}' in annotation {i}"
                    )
        
        # Create batch operation record
        operation_id = str(uuid4())
        batch_op = BatchOperation(
            id=operation_id,
            operation_type="annotation_create",
            status="pending",
            total_items=len(request.annotations),
            user_id=current_user.id,
            project_id=request.project_id,
            parameters=request.dict(),
            validate_before_process=request.validate_before_create,
            rollback_on_error=request.rollback_on_error
        )
        db.add(batch_op)
        db.commit()
        
        # Initialize progress tracker
        progress_tracker.initialize_operation(
            operation_id, 
            len(request.annotations),
            "Creating annotations in batch",
            {"project_id": request.project_id, "user_id": current_user.id}
        )
        
        # Start background processing
        background_tasks.add_task(
            process_batch_annotation_creation,
            operation_id,
            request,
            current_user.id
        )
        
        logger.info(f"Started batch annotation creation: {operation_id} with {len(request.annotations)} items")
        
        return {
            "operation_id": operation_id,
            "status": "pending",
            "total_items": len(request.annotations),
            "message": "Batch annotation creation started",
            "estimated_duration": len(request.annotations) * 0.1,  # Rough estimate
            "validation_enabled": request.validate_before_create,
            "rollback_enabled": request.rollback_on_error
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting batch annotation creation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

async def process_batch_annotation_creation(
    operation_id: str,
    request: BatchAnnotationCreate,
    user_id: int
):
    """Background task for processing batch annotation creation"""
    # Use batch processor for efficient processing
    async def progress_callback(op_id, progress_pct, processed, success, failed):
        progress_tracker.update_progress(
            op_id,
            processed,
            f"Processing annotations: {success} success, {failed} failed",
            f"Progress: {progress_pct:.1f}%"
        )
    
    try:
        result = await batch_processor.create_annotations_batch(
            operation_id=operation_id,
            annotations_data=request.annotations,
            user_id=user_id,
            project_id=request.project_id,
            validate_before_create=request.validate_before_create,
            progress_callback=progress_callback
        )
        
        # Update final operation status
        from sqlalchemy.orm import sessionmaker
        from src.core.database import engine
        session_factory = sessionmaker(bind=engine)
        db = session_factory()
    
    try:
        
        try:
            batch_op = db.query(BatchOperation).filter(BatchOperation.id == operation_id).first()
            if batch_op:
                batch_op.status = "completed"
                batch_op.completed_at = datetime.utcnow()
                batch_op.processed_items = result.success_count
                batch_op.failed_items = result.failure_count
                batch_op.result_data = {
                    "created_annotations": [item.id for item in result.processed_items if hasattr(item, 'id')],
                    "errors": result.errors,
                    "execution_time": result.execution_time,
                    "performance_metrics": result.metadata
                }
                db.commit()
            
            progress_tracker.complete_operation(
                operation_id,
                f"Created {result.success_count} annotations with {result.failure_count} errors"
            )
            
            logger.info(f"Completed batch annotation creation: {operation_id}")
        finally:
            db.close()
        
    except Exception as e:
        # Handle failure
        from sqlalchemy.orm import sessionmaker
        from src.core.database import engine
        session_factory = sessionmaker(bind=engine)
        db = session_factory()
        try:
            batch_op = db.query(BatchOperation).filter(BatchOperation.id == operation_id).first()
            if batch_op:
                batch_op.status = "failed"
                batch_op.completed_at = datetime.utcnow()
                batch_op.error_message = str(e)
                db.commit()
        finally:
            db.close()
        
        progress_tracker.fail_operation(operation_id, str(e))
        logger.error(f"Batch annotation creation failed: {operation_id} - {str(e)}")

@router.post("/annotations/update", response_model=Dict[str, Any])
async def update_batch_annotations(
    annotation_ids: List[int],
    updates: Dict[str, Any],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update multiple annotations in batch.
    
    Supports updating any annotation field for multiple annotations simultaneously.
    """
    try:
        # Validate that annotations exist and user has permission
        annotations = db.query(Annotation).filter(Annotation.id.in_(annotation_ids)).all()
        
        if len(annotations) != len(annotation_ids):
            missing_ids = set(annotation_ids) - {a.id for a in annotations}
            raise HTTPException(
                status_code=404, 
                detail=f"Annotations not found: {list(missing_ids)}"
            )
        
        # Check permissions for each annotation
        for annotation in annotations:
            text = db.query(Text).filter(Text.id == annotation.text_id).first()
            if text:
                project = db.query(Project).filter(Project.id == text.project_id).first()
                if project and not has_write_permission(current_user, project):
                    raise HTTPException(
                        status_code=403, 
                        detail=f"Insufficient permissions for annotation {annotation.id}"
                    )
        
        # Create batch operation
        operation_id = str(uuid4())
        batch_op = BatchOperation(
            id=operation_id,
            operation_type="annotation_update",
            status="pending",
            total_items=len(annotation_ids),
            user_id=current_user.id,
            parameters={"annotation_ids": annotation_ids, "updates": updates}
        )
        db.add(batch_op)
        db.commit()
        
        # Initialize progress tracking
        progress_tracker.initialize_operation(
            operation_id,
            len(annotation_ids),
            "Updating annotations in batch"
        )
        
        # Prepare update data for batch processor
        updates_data = [
            {"annotation_id": ann_id, "updates": updates} 
            for ann_id in annotation_ids
        ]
        
        # Start background processing
        background_tasks.add_task(
            process_batch_annotation_updates,
            operation_id,
            updates_data,
            current_user.id
        )
        
        return {
            "operation_id": operation_id,
            "status": "pending",
            "total_items": len(annotation_ids),
            "message": "Batch annotation update started"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting batch annotation update: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/annotations/delete", response_model=Dict[str, Any])
async def delete_batch_annotations(
    annotation_ids: List[int],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete multiple annotations in batch.
    
    Permanently removes annotations with proper permission checking.
    """
    try:
        # Validate annotations and permissions
        annotations = db.query(Annotation).filter(Annotation.id.in_(annotation_ids)).all()
        
        if len(annotations) != len(annotation_ids):
            missing_ids = set(annotation_ids) - {a.id for a in annotations}
            raise HTTPException(
                status_code=404, 
                detail=f"Annotations not found: {list(missing_ids)}"
            )
        
        # Check permissions
        for annotation in annotations:
            text = db.query(Text).filter(Text.id == annotation.text_id).first()
            if text:
                project = db.query(Project).filter(Project.id == text.project_id).first()
                if project and not has_write_permission(current_user, project):
                    raise HTTPException(
                        status_code=403, 
                        detail=f"Insufficient permissions for annotation {annotation.id}"
                    )
        
        # Create batch operation
        operation_id = str(uuid4())
        batch_op = BatchOperation(
            id=operation_id,
            operation_type="annotation_delete",
            status="pending",
            total_items=len(annotation_ids),
            user_id=current_user.id,
            parameters={"annotation_ids": annotation_ids}
        )
        db.add(batch_op)
        db.commit()
        
        # Initialize progress tracking
        progress_tracker.initialize_operation(
            operation_id,
            len(annotation_ids),
            "Deleting annotations in batch"
        )
        
        # Start background processing
        background_tasks.add_task(
            process_batch_annotation_deletions,
            operation_id,
            annotation_ids,
            current_user.id
        )
        
        return {
            "operation_id": operation_id,
            "status": "pending",
            "total_items": len(annotation_ids),
            "message": "Batch annotation deletion started"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting batch annotation deletion: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/text/import", response_model=Dict[str, Any])
async def import_bulk_text(
    request: BatchTextImport,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Import text data in bulk with automatic processing and label detection
    """
    try:
        # Validate file format
        if not file.filename.endswith(('.json', '.csv', '.txt')):
            raise HTTPException(
                status_code=400, 
                detail="Unsupported file format. Use JSON, CSV, or TXT"
            )
        
        # Read file content
        content = await file.read()
        
        # Create batch operation
        operation_id = str(uuid4())
        batch_op = BatchOperation(
            id=operation_id,
            operation_type="text_import",
            status="pending",
            user_id=current_user.id,
            project_id=request.project_id,
            parameters={**request.dict(), "filename": file.filename}
        )
        db.add(batch_op)
        db.commit()
        
        # Start background processing
        background_tasks.add_task(
            process_bulk_text_import,
            operation_id,
            content,
            request,
            current_user.id
        )
        
        return {
            "operation_id": operation_id,
            "status": "pending",
            "message": "Bulk text import started"
        }
        
    except Exception as e:
        logger.error(f"Error starting bulk text import: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_batch_annotation_updates(
    operation_id: str,
    updates_data: List[Dict[str, Any]],
    user_id: int
):
    """Background task for processing batch annotation updates."""
    try:
        # Progress callback
        async def progress_callback(op_id, progress_pct, processed, success, failed):
            progress_tracker.update_progress(
                op_id,
                processed,
                f"Updating annotations: {success} success, {failed} failed",
                f"Progress: {progress_pct:.1f}%"
            )
        
        # Use batch processor for updates
        result = await batch_processor.update_annotations_batch(
            operation_id=operation_id,
            updates_data=updates_data,
            user_id=user_id,
            progress_callback=progress_callback
        )
        
        # Update final operation status
        from sqlalchemy.orm import sessionmaker
        from src.core.database import engine
        session_factory = sessionmaker(bind=engine)
        db = session_factory()
        
        try:
            batch_op = db.query(BatchOperation).filter(BatchOperation.id == operation_id).first()
            if batch_op:
                batch_op.status = "completed"
                batch_op.completed_at = datetime.utcnow()
                batch_op.processed_items = result.success_count
                batch_op.failed_items = result.failure_count
                batch_op.result_data = {
                    "updated_annotations": [item.id for item in result.processed_items if hasattr(item, 'id')],
                    "errors": result.errors,
                    "execution_time": result.execution_time,
                    "performance_metrics": result.metadata
                }
                db.commit()
            
            progress_tracker.complete_operation(
                operation_id,
                f"Updated {result.success_count} annotations with {result.failure_count} errors"
            )
            
        finally:
            db.close()
            
    except Exception as e:
        from sqlalchemy.orm import sessionmaker
        from src.core.database import engine
        session_factory = sessionmaker(bind=engine)
        db = session_factory()
        try:
            batch_op = db.query(BatchOperation).filter(BatchOperation.id == operation_id).first()
            if batch_op:
                batch_op.status = "failed"
                batch_op.completed_at = datetime.utcnow()
                batch_op.error_message = str(e)
                db.commit()
        finally:
            db.close()
        
        progress_tracker.fail_operation(operation_id, str(e))
        logger.error(f"Batch annotation update failed: {operation_id} - {str(e)}")


async def process_batch_annotation_deletions(
    operation_id: str,
    annotation_ids: List[int],
    user_id: int
):
    """Background task for processing batch annotation deletions."""
    try:
        # Progress callback
        async def progress_callback(op_id, progress_pct, processed, success, failed):
            progress_tracker.update_progress(
                op_id,
                processed,
                f"Deleting annotations: {success} success, {failed} failed",
                f"Progress: {progress_pct:.1f}%"
            )
        
        # Use batch processor for deletions
        result = await batch_processor.delete_annotations_batch(
            operation_id=operation_id,
            annotation_ids=annotation_ids,
            user_id=user_id,
            progress_callback=progress_callback
        )
        
        # Update final operation status
        from sqlalchemy.orm import sessionmaker
        from src.core.database import engine
        session_factory = sessionmaker(bind=engine)
        db = session_factory()
        
        try:
            batch_op = db.query(BatchOperation).filter(BatchOperation.id == operation_id).first()
            if batch_op:
                batch_op.status = "completed"
                batch_op.completed_at = datetime.utcnow()
                batch_op.processed_items = result.success_count
                batch_op.failed_items = result.failure_count
                batch_op.result_data = {
                    "deleted_annotations": result.processed_items,
                    "errors": result.errors,
                    "execution_time": result.execution_time,
                    "performance_metrics": result.metadata
                }
                db.commit()
            
            progress_tracker.complete_operation(
                operation_id,
                f"Deleted {result.success_count} annotations with {result.failure_count} errors"
            )
            
        finally:
            db.close()
            
    except Exception as e:
        from sqlalchemy.orm import sessionmaker
        from src.core.database import engine
        session_factory = sessionmaker(bind=engine)
        db = session_factory()
        try:
            batch_op = db.query(BatchOperation).filter(BatchOperation.id == operation_id).first()
            if batch_op:
                batch_op.status = "failed"
                batch_op.completed_at = datetime.utcnow()
                batch_op.error_message = str(e)
                db.commit()
        finally:
            db.close()
        
        progress_tracker.fail_operation(operation_id, str(e))
        logger.error(f"Batch annotation deletion failed: {operation_id} - {str(e)}")


async def process_bulk_text_import(
    operation_id: str,
    content: bytes,
    request: BatchTextImport,
    user_id: int
):
    """Background task for processing bulk text import with advanced import/export functionality."""
    try:
        # Use the enhanced import/export system
        from src.utils.batch_import_export import BatchImportExport
        
        import_export = BatchImportExport()
        
        # Progress callback
        async def progress_callback(current, total, progress_pct, success=None, failed=None):
            progress_tracker.update_progress(
                operation_id,
                current,
                f"Importing text data: {success or 0} success, {failed or 0} failed" if success is not None else "Importing text data",
                f"Progress: {progress_pct:.1f}%"
            )
        
        # Import annotations from file
        result = await import_export.import_annotations_from_file(
            file_content=content,
            file_format=request.format,
            project_id=request.project_id,
            user_id=user_id,
            progress_callback=progress_callback
        )
        
        # Update final operation status
        from sqlalchemy.orm import sessionmaker
        from src.core.database import engine
        session_factory = sessionmaker(bind=engine)
        db = session_factory()
    
    try:
        
        try:
            batch_op = db.query(BatchOperation).filter(BatchOperation.id == operation_id).first()
            if batch_op:
                batch_op.status = "completed"
                batch_op.completed_at = datetime.utcnow()
                batch_op.processed_items = result.success_count
                batch_op.failed_items = result.failure_count
                batch_op.result_data = {
                    "imported_items": [item.id for item in result.imported_items if hasattr(item, 'id')],
                    "errors": result.errors,
                    "validation_warnings": result.validation_warnings,
                    "metadata": result.metadata
                }
                db.commit()
            
            progress_tracker.complete_operation(
                operation_id,
                f"Imported {result.success_count} items with {result.failure_count} errors"
            )
            
        finally:
            db.close()
        
    except Exception as e:
        from sqlalchemy.orm import sessionmaker
        from src.core.database import engine
        session_factory = sessionmaker(bind=engine)
        db = session_factory()
        try:
            batch_op = db.query(BatchOperation).filter(BatchOperation.id == operation_id).first()
            if batch_op:
                batch_op.status = "failed"
                batch_op.completed_at = datetime.utcnow()
                batch_op.error_message = str(e)
                db.commit()
        finally:
            db.close()
        
        progress_tracker.fail_operation(operation_id, str(e))
        logger.error(f"Bulk text import failed: {operation_id} - {str(e)}")

@router.post("/annotations/validate", response_model=Dict[str, Any])
async def validate_batch_annotations(
    request: BatchValidationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Validate annotations in batch with automatic approval based on threshold
    """
    try:
        # Create batch operation
        operation_id = str(uuid4())
        batch_op = BatchOperation(
            id=operation_id,
            operation_type="annotation_validation",
            status="pending",
            total_items=len(request.annotation_ids),
            user_id=current_user.id,
            parameters=request.dict()
        )
        db.add(batch_op)
        db.commit()
        
        # Start background processing
        background_tasks.add_task(
            process_batch_validation,
            operation_id,
            request,
            current_user.id
        )
        
        return {
            "operation_id": operation_id,
            "status": "pending",
            "total_items": len(request.annotation_ids),
            "message": "Batch validation started"
        }
        
    except Exception as e:
        logger.error(f"Error starting batch validation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_batch_validation(
    operation_id: str,
    request: BatchValidationRequest,
    user_id: int
):
    """Background task for processing batch validation"""
    db = next(get_db())
    
    try:
        # Update operation status
        batch_op = db.query(BatchOperation).filter(BatchOperation.id == operation_id).first()
        batch_op.status = "running"
        batch_op.started_at = datetime.utcnow()
        db.commit()
        
        progress_tracker.initialize_operation(
            operation_id,
            len(request.annotation_ids),
            "Validating annotations"
        )
        
        validation_results = []
        approved_count = 0
        
        for i, annotation_id in enumerate(request.annotation_ids):
            try:
                annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
                if not annotation:
                    validation_results.append({
                        "annotation_id": annotation_id,
                        "status": "not_found",
                        "score": 0.0
                    })
                    continue
                
                # Perform validation
                validation_result = await validation_engine.validate_annotation_by_type(
                    annotation,
                    request.validation_type
                )
                
                # Auto-approve if threshold met
                approved = False
                if request.auto_approve and validation_result.score >= request.approval_threshold:
                    annotation.status = "approved"
                    annotation.approved_by = user_id
                    annotation.approved_at = datetime.utcnow()
                    approved = True
                    approved_count += 1
                
                validation_results.append({
                    "annotation_id": annotation_id,
                    "status": "approved" if approved else "validated",
                    "score": validation_result.score,
                    "issues": validation_result.issues
                })
                
                # Update progress
                progress_tracker.update_progress(
                    operation_id,
                    i + 1,
                    f"Validated {i + 1}/{len(request.annotation_ids)} annotations"
                )
                
            except Exception as e:
                validation_results.append({
                    "annotation_id": annotation_id,
                    "status": "error",
                    "error": str(e)
                })
        
        db.commit()
        
        # Update operation status
        batch_op.status = "completed"
        batch_op.completed_at = datetime.utcnow()
        batch_op.processed_items = len(validation_results)
        batch_op.result_data = {
            "validation_results": validation_results,
            "approved_count": approved_count
        }
        db.commit()
        
        progress_tracker.complete_operation(
            operation_id,
            f"Validated {len(validation_results)} annotations, approved {approved_count}"
        )
        
    except Exception as e:
        batch_op.status = "failed"
        batch_op.completed_at = datetime.utcnow()
        batch_op.error_message = str(e)
        db.commit()
        
        progress_tracker.fail_operation(operation_id, str(e))
        logger.error(f"Batch validation failed: {operation_id} - {str(e)}")
        
    finally:
        db.close()

@router.post("/export", response_model=Dict[str, Any])
async def export_batch_data(
    request: BatchExportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export annotations and data in batch with progress tracking
    """
    try:
        # Create batch operation
        operation_id = str(uuid4())
        batch_op = BatchOperation(
            id=operation_id,
            operation_type="data_export",
            status="pending",
            user_id=current_user.id,
            project_id=request.project_id,
            parameters=request.dict()
        )
        db.add(batch_op)
        db.commit()
        
        # Start background processing
        background_tasks.add_task(
            process_batch_export,
            operation_id,
            request,
            current_user.id
        )
        
        return {
            "operation_id": operation_id,
            "status": "pending",
            "message": "Batch export started"
        }
        
    except Exception as e:
        logger.error(f"Error starting batch export: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_batch_export(
    operation_id: str,
    request: BatchExportRequest,
    user_id: int
):
    """Background task for processing batch export"""
    db = next(get_db())
    
    try:
        # Update operation status
        batch_op = db.query(BatchOperation).filter(BatchOperation.id == operation_id).first()
        batch_op.status = "running"
        batch_op.started_at = datetime.utcnow()
        db.commit()
        
        # Query annotations with filters
        query = db.query(Annotation).filter(Annotation.project_id == request.project_id)
        
        if request.filter_criteria:
            query = apply_export_filters(query, request.filter_criteria)
        
        annotations = query.all()
        batch_op.total_items = len(annotations)
        db.commit()
        
        progress_tracker.initialize_operation(
            operation_id,
            len(annotations),
            "Exporting data"
        )
        
        # Export data based on format
        export_data = await export_annotations_by_format(
            annotations,
            request.export_format,
            request.include_metadata,
            operation_id
        )
        
        # Save export file
        export_filename = f"export_{operation_id}.{request.export_format}"
        export_path = f"exports/{export_filename}"
        
        with open(export_path, 'w') as f:
            if request.export_format == 'json':
                json.dump(export_data, f, indent=2)
            elif request.export_format == 'csv':
                writer = csv.DictWriter(f, fieldnames=export_data[0].keys())
                writer.writeheader()
                writer.writerows(export_data)
        
        # Update operation status
        batch_op.status = "completed"
        batch_op.completed_at = datetime.utcnow()
        batch_op.processed_items = len(annotations)
        batch_op.result_data = {
            "export_file": export_filename,
            "export_path": export_path,
            "record_count": len(annotations)
        }
        db.commit()
        
        progress_tracker.complete_operation(
            operation_id,
            f"Exported {len(annotations)} records"
        )
        
    except Exception as e:
        batch_op.status = "failed"
        batch_op.completed_at = datetime.utcnow()
        batch_op.error_message = str(e)
        db.commit()
        
        progress_tracker.fail_operation(operation_id, str(e))
        logger.error(f"Batch export failed: {operation_id} - {str(e)}")
        
    finally:
        db.close()

@router.post("/users/permissions", response_model=Dict[str, Any])
async def manage_bulk_user_permissions(
    request: BulkUserPermission,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Manage user permissions in bulk
    """
    try:
        # Check admin permissions
        if not is_admin_user(current_user):
            raise HTTPException(status_code=403, detail="Admin permissions required")
        
        # Create batch operation
        operation_id = str(uuid4())
        batch_op = BatchOperation(
            id=operation_id,
            operation_type="user_permission_management",
            status="pending",
            total_items=len(request.user_ids),
            user_id=current_user.id,
            project_id=request.project_id,
            parameters=request.dict()
        )
        db.add(batch_op)
        db.commit()
        
        # Start background processing
        background_tasks.add_task(
            process_bulk_user_permissions,
            operation_id,
            request,
            current_user.id
        )
        
        return {
            "operation_id": operation_id,
            "status": "pending",
            "total_items": len(request.user_ids),
            "message": "Bulk user permission management started"
        }
        
    except Exception as e:
        logger.error(f"Error starting bulk user permission management: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_bulk_user_permissions(
    operation_id: str,
    request: BulkUserPermission,
    admin_user_id: int
):
    """Background task for processing bulk user permission changes"""
    db = next(get_db())
    
    try:
        # Update operation status
        batch_op = db.query(BatchOperation).filter(BatchOperation.id == operation_id).first()
        batch_op.status = "running"
        batch_op.started_at = datetime.utcnow()
        db.commit()
        
        progress_tracker.initialize_operation(
            operation_id,
            len(request.user_ids),
            "Managing user permissions"
        )
        
        permission_results = []
        
        for i, user_id in enumerate(request.user_ids):
            try:
                user = db.query(User).filter(User.id == user_id).first()
                if not user:
                    permission_results.append({
                        "user_id": user_id,
                        "status": "user_not_found"
                    })
                    continue
                
                # Apply permission changes based on action
                if request.action == "grant":
                    await grant_user_permission(user, request.project_id, request.permission_level)
                elif request.action == "revoke":
                    await revoke_user_permission(user, request.project_id)
                elif request.action == "update":
                    await update_user_permission(user, request.project_id, request.permission_level)
                
                permission_results.append({
                    "user_id": user_id,
                    "status": "success",
                    "action": request.action,
                    "permission_level": request.permission_level
                })
                
                # Update progress
                progress_tracker.update_progress(
                    operation_id,
                    i + 1,
                    f"Updated permissions for {i + 1}/{len(request.user_ids)} users"
                )
                
            except Exception as e:
                permission_results.append({
                    "user_id": user_id,
                    "status": "error",
                    "error": str(e)
                })
        
        db.commit()
        
        # Update operation status
        batch_op.status = "completed"
        batch_op.completed_at = datetime.utcnow()
        batch_op.processed_items = len(permission_results)
        batch_op.result_data = {"permission_results": permission_results}
        db.commit()
        
        progress_tracker.complete_operation(
            operation_id,
            f"Updated permissions for {len(permission_results)} users"
        )
        
    except Exception as e:
        batch_op.status = "failed"
        batch_op.completed_at = datetime.utcnow()
        batch_op.error_message = str(e)
        db.commit()
        
        progress_tracker.fail_operation(operation_id, str(e))
        logger.error(f"Bulk user permission management failed: {operation_id} - {str(e)}")
        
    finally:
        db.close()

@router.post("/labels/manage", response_model=Dict[str, Any])
async def manage_batch_labels(
    request: BatchLabelManagement,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Manage labels in batch (assign, unassign, merge, delete)
    """
    try:
        # Create batch operation
        operation_id = str(uuid4())
        batch_op = BatchOperation(
            id=operation_id,
            operation_type="label_management",
            status="pending",
            total_items=len(request.label_ids),
            user_id=current_user.id,
            parameters=request.dict()
        )
        db.add(batch_op)
        db.commit()
        
        # Start background processing
        background_tasks.add_task(
            process_batch_label_management,
            operation_id,
            request,
            current_user.id
        )
        
        return {
            "operation_id": operation_id,
            "status": "pending",
            "total_items": len(request.label_ids),
            "message": "Batch label management started"
        }
        
    except Exception as e:
        logger.error(f"Error starting batch label management: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/operations/{operation_id}/status", response_model=BatchOperationStatus)
async def get_batch_operation_status(
    operation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get the status and progress of a batch operation
    """
    try:
        batch_op = db.query(BatchOperation).filter(BatchOperation.id == operation_id).first()
        if not batch_op:
            raise HTTPException(status_code=404, detail="Batch operation not found")
        
        # Check if user has access to this operation
        if batch_op.user_id != current_user.id and not is_admin_user(current_user):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get progress information
        progress_info = progress_tracker.get_progress(operation_id)
        
        return BatchOperationStatus(
            operation_id=batch_op.id,
            status=batch_op.status,
            progress=progress_info.get('progress_percentage', 0),
            total_items=batch_op.total_items or 0,
            processed_items=batch_op.processed_items or 0,
            failed_items=batch_op.failed_items or 0,
            created_at=batch_op.created_at,
            updated_at=batch_op.updated_at,
            errors=batch_op.result_data.get('errors', []) if batch_op.result_data else []
        )
        
    except Exception as e:
        logger.error(f"Error getting batch operation status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/operations/{operation_id}/cancel")
async def cancel_batch_operation(
    operation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Cancel a running batch operation
    """
    try:
        batch_op = db.query(BatchOperation).filter(BatchOperation.id == operation_id).first()
        if not batch_op:
            raise HTTPException(status_code=404, detail="Batch operation not found")
        
        # Check permissions
        if batch_op.user_id != current_user.id and not is_admin_user(current_user):
            raise HTTPException(status_code=403, detail="Access denied")
        
        if batch_op.status not in ["pending", "running"]:
            raise HTTPException(
                status_code=400, 
                detail="Operation cannot be cancelled in current status"
            )
        
        # Cancel the operation
        batch_op.status = "cancelled"
        batch_op.completed_at = datetime.utcnow()
        db.commit()
        
        # Cancel progress tracking
        progress_tracker.cancel_operation(operation_id, "Cancelled by user")
        
        return {"message": "Operation cancelled successfully"}
        
    except Exception as e:
        logger.error(f"Error cancelling batch operation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/operations", response_model=List[BatchOperationStatus])
async def list_batch_operations(
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = None,
    operation_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List batch operations for the current user
    """
    try:
        query = db.query(BatchOperation)
        
        # Filter by user unless admin
        if not is_admin_user(current_user):
            query = query.filter(BatchOperation.user_id == current_user.id)
        
        # Apply filters
        if status:
            query = query.filter(BatchOperation.status == status)
        if operation_type:
            query = query.filter(BatchOperation.operation_type == operation_type)
        
        # Order and paginate
        operations = query.order_by(BatchOperation.created_at.desc()).offset(skip).limit(limit).all()
        
        # Convert to response format
        result = []
        for op in operations:
            progress_info = progress_tracker.get_progress(op.id)
            result.append(BatchOperationStatus(
                operation_id=op.id,
                status=op.status,
                progress=progress_info.get('progress_percentage', 0),
                total_items=op.total_items or 0,
                processed_items=op.processed_items or 0,
                failed_items=op.failed_items or 0,
                created_at=op.created_at,
                updated_at=op.updated_at,
                errors=op.result_data.get('errors', []) if op.result_data else []
            ))
        
        return result
        
    except Exception as e:
        logger.error(f"Error listing batch operations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Helper functions
async def rollback_created_annotations(annotation_ids: List[int], db: Session):
    """Rollback created annotations in case of error"""
    try:
        for annotation_id in annotation_ids:
            annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
            if annotation:
                db.delete(annotation)
        db.commit()
        logger.info(f"Rolled back {len(annotation_ids)} annotations")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to rollback annotations: {str(e)}")
        raise

async def parse_import_content(content: bytes, format: str) -> List[Dict[str, Any]]:
    """Parse import content based on format with enhanced error handling"""
    try:
        text_content = content.decode('utf-8')
        
        if format.lower() == 'json':
            data = json.loads(text_content)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                # Handle single object or objects with annotations key
                if 'annotations' in data:
                    return data['annotations']
                else:
                    return [data]
            else:
                raise ValueError("Invalid JSON format: expected object or array")
        
        elif format.lower() == 'csv':
            reader = csv.DictReader(io.StringIO(text_content))
            data = list(reader)
            if not data:
                raise ValueError("CSV file is empty or has no valid data")
            return data
        
        elif format.lower() == 'jsonl':
            lines = text_content.strip().split('\n')
            data = []
            for i, line in enumerate(lines):
                if line.strip():
                    try:
                        data.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        raise ValueError(f"Invalid JSON on line {i+1}: {str(e)}")
            return data
        
        elif format.lower() == 'txt':
            lines = text_content.split('\n')
            return [{"text": line.strip()} for line in lines if line.strip()]
        
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    except UnicodeDecodeError as e:
        raise ValueError(f"File encoding error: {str(e)}")
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON parsing error: {str(e)}")
    except Exception as e:
        raise ValueError(f"Content parsing error: {str(e)}")

async def detect_labels(text: str) -> List[str]:
    """Auto-detect labels from text content using basic heuristics"""
    # This is a basic implementation. In production, you would use:
    # - Named Entity Recognition (NER) models
    # - Machine learning classifiers
    # - Rule-based pattern matching
    # - External APIs (spaCy, NLTK, etc.)
    
    detected_labels = []
    text_lower = text.lower()
    
    # Basic pattern matching for common entities
    patterns = {
        'PERSON': ['mr.', 'mrs.', 'dr.', 'prof.', 'john', 'mary', 'smith', 'johnson'],
        'ORGANIZATION': ['inc.', 'corp.', 'ltd.', 'llc', 'company', 'corporation'],
        'LOCATION': ['city', 'street', 'avenue', 'road', 'state', 'country'],
        'DATE': ['january', 'february', 'march', 'april', 'may', 'june',
                'july', 'august', 'september', 'october', 'november', 'december'],
        'MONEY': ['$', 'dollar', 'euro', 'pound', 'yen', 'cost', 'price']
    }
    
    for label, keywords in patterns.items():
        if any(keyword in text_lower for keyword in keywords):
            detected_labels.append(label)
    
    return detected_labels

async def export_annotations_by_format(
    annotations: List[Annotation],
    format: str,
    include_metadata: bool,
    operation_id: str
) -> List[Dict[str, Any]]:
    """Export annotations in specified format"""
    export_data = []
    
    for i, annotation in enumerate(annotations):
        data = {
            "id": annotation.id,
            "text": annotation.text,
            "labels": [label.name for label in annotation.labels],
            "status": annotation.status,
            "created_at": annotation.created_at.isoformat(),
            "updated_at": annotation.updated_at.isoformat()
        }
        
        if include_metadata:
            data["metadata"] = annotation.metadata
            data["user_id"] = annotation.user_id
            data["project_id"] = annotation.project_id
        
        export_data.append(data)
        
        # Update progress periodically
        if i % 100 == 0:
            progress_tracker.update_progress(
                operation_id,
                i + 1,
                f"Exported {i + 1}/{len(annotations)} records"
            )
    
    return export_data

def apply_export_filters(query, filter_criteria: Dict[str, Any]):
    """Apply filters to export query"""
    if 'status' in filter_criteria:
        query = query.filter(Annotation.status == filter_criteria['status'])
    if 'created_after' in filter_criteria:
        query = query.filter(Annotation.created_at >= filter_criteria['created_after'])
    if 'created_before' in filter_criteria:
        query = query.filter(Annotation.created_at <= filter_criteria['created_before'])
    if 'user_id' in filter_criteria:
        query = query.filter(Annotation.user_id == filter_criteria['user_id'])
    
    return query

async def grant_user_permission(user: User, project_id: int, permission_level: str):
    """Grant user permission for project"""
    # Implementation for granting permissions
    pass

async def revoke_user_permission(user: User, project_id: int):
    """Revoke user permission for project"""
    # Implementation for revoking permissions
    pass

async def update_user_permission(user: User, project_id: int, permission_level: str):
    """Update user permission for project"""
    # Implementation for updating permissions
    pass

async def process_batch_label_management(
    operation_id: str,
    request: BatchLabelManagement,
    user_id: int
):
    """Background task for processing batch label management operations"""
    from sqlalchemy.orm import sessionmaker
    from src.core.database import engine
    session_factory = sessionmaker(bind=engine)
    db = session_factory()
    
    try:
        # Update operation status
        batch_op = db.query(BatchOperation).filter(BatchOperation.id == operation_id).first()
        if batch_op:
            batch_op.status = "running"
            batch_op.started_at = datetime.utcnow()
            db.commit()
        
        progress_tracker.initialize_operation(
            operation_id,
            len(request.label_ids),
            f"Managing labels: {request.action}"
        )
        
        processed_count = 0
        errors = []
        results = []
        
        for i, label_id in enumerate(request.label_ids):
            try:
                label = db.query(Label).filter(Label.id == label_id).first()
                if not label:
                    errors.append({"label_id": label_id, "error": "Label not found"})
                    continue
                
                if request.action == "assign" and request.target_annotations:
                    # Assign label to annotations
                    for ann_id in request.target_annotations:
                        annotation = db.query(Annotation).filter(Annotation.id == ann_id).first()
                        if annotation:
                            annotation.label_id = label_id
                            results.append({"annotation_id": ann_id, "assigned_label": label_id})
                
                elif request.action == "unassign" and request.target_annotations:
                    # Remove label from annotations
                    for ann_id in request.target_annotations:
                        annotation = db.query(Annotation).filter(Annotation.id == ann_id).first()
                        if annotation and annotation.label_id == label_id:
                            annotation.label_id = None
                            results.append({"annotation_id": ann_id, "unassigned_label": label_id})
                
                elif request.action == "merge" and request.merge_target_id:
                    # Merge label into target label
                    target_label = db.query(Label).filter(Label.id == request.merge_target_id).first()
                    if target_label:
                        # Update all annotations using this label to use target label
                        annotations = db.query(Annotation).filter(Annotation.label_id == label_id).all()
                        for annotation in annotations:
                            annotation.label_id = request.merge_target_id
                        
                        # Delete the merged label
                        db.delete(label)
                        results.append({
                            "merged_label": label_id, 
                            "target_label": request.merge_target_id,
                            "annotations_updated": len(annotations)
                        })
                
                elif request.action == "delete":
                    # Delete label and handle annotations
                    annotations_count = db.query(Annotation).filter(Annotation.label_id == label_id).count()
                    
                    # Remove label from annotations
                    db.query(Annotation).filter(Annotation.label_id == label_id).update({"label_id": None})
                    
                    # Delete label
                    db.delete(label)
                    results.append({
                        "deleted_label": label_id,
                        "annotations_affected": annotations_count
                    })
                
                processed_count += 1
                
                # Update progress
                progress_tracker.update_progress(
                    operation_id,
                    i + 1,
                    f"Processed {i + 1}/{len(request.label_ids)} labels"
                )
                
            except Exception as e:
                errors.append({"label_id": label_id, "error": str(e)})
                logger.error(f"Error processing label {label_id}: {str(e)}")
        
        db.commit()
        
        # Update final operation status
        if batch_op:
            batch_op.status = "completed"
            batch_op.completed_at = datetime.utcnow()
            batch_op.processed_items = processed_count
            batch_op.failed_items = len(errors)
            batch_op.result_data = {
                "results": results,
                "errors": errors,
                "action": request.action
            }
            db.commit()
        
        progress_tracker.complete_operation(
            operation_id,
            f"Completed label management: {processed_count} processed, {len(errors)} errors"
        )
        
    except Exception as e:
        if batch_op:
            batch_op.status = "failed"
            batch_op.completed_at = datetime.utcnow()
            batch_op.error_message = str(e)
            db.commit()
        
        progress_tracker.fail_operation(operation_id, str(e))
        logger.error(f"Batch label management failed: {operation_id} - {str(e)}")
        
    finally:
        db.close()

def has_write_permission(user: User, project: Project) -> bool:
    """Check if user has write permission for project"""
    # Check if user is project owner or has admin role
    return user.id == project.owner_id or user.is_admin or user.role == "admin"

def is_admin_user(user: User) -> bool:
    """Check if user is an admin"""
    return user.is_admin or user.role == "admin"