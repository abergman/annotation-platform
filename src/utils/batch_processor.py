"""
Batch Processor Utility

High-performance batch processing engine for annotation operations with
concurrent processing, memory optimization, and progress tracking.
"""

import asyncio
import logging
import time
import psutil
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Callable, Optional, AsyncGenerator, Union
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text

from src.core.database import engine
from src.models.batch_models import BatchOperation, BatchProgress, BatchError
from src.models.annotation import Annotation
from src.models.text import Text
from src.models.label import Label
from src.models.user import User
from src.models.project import Project

logger = logging.getLogger(__name__)


@dataclass
class BatchResult:
    """Result of a batch operation."""
    success_count: int
    failure_count: int
    errors: List[Dict[str, Any]]
    processed_items: List[Any]
    metadata: Dict[str, Any]
    execution_time: float


@dataclass
class ProcessingChunk:
    """A chunk of items to process."""
    chunk_id: str
    items: List[Any]
    start_index: int
    end_index: int


class BatchProcessor:
    """High-performance batch processor for annotation operations."""
    
    def __init__(self, max_workers: int = 4, chunk_size: int = 100):
        self.max_workers = max_workers
        self.chunk_size = chunk_size
        self.session_factory = sessionmaker(bind=engine)
        self._active_operations = {}
        self._performance_metrics = {}
        
    async def process_batch_operation(
        self,
        operation_id: str,
        items: List[Any],
        processor_func: Callable,
        validation_func: Optional[Callable] = None,
        progress_callback: Optional[Callable] = None,
        chunk_size: Optional[int] = None,
        max_workers: Optional[int] = None,
        rollback_on_error: bool = True
    ) -> BatchResult:
        """
        Process a batch operation with concurrent processing and progress tracking.
        
        Args:
            operation_id: Unique identifier for the operation
            items: List of items to process
            processor_func: Function to process each item
            validation_func: Optional validation function
            progress_callback: Optional progress callback function
            chunk_size: Size of processing chunks
            max_workers: Maximum number of concurrent workers
            rollback_on_error: Whether to rollback on error
            
        Returns:
            BatchResult with processing results
        """
        start_time = time.time()
        chunk_size = chunk_size or self.chunk_size
        max_workers = max_workers or self.max_workers
        
        logger.info(f"Starting batch operation {operation_id} with {len(items)} items")
        
        # Initialize operation tracking
        self._active_operations[operation_id] = {
            "start_time": start_time,
            "total_items": len(items),
            "processed_items": 0,
            "success_count": 0,
            "failure_count": 0,
            "status": "running"
        }
        
        success_count = 0
        failure_count = 0
        errors = []
        processed_items = []
        
        try:
            # Create processing chunks
            chunks = self._create_chunks(items, chunk_size)
            
            # Process chunks concurrently
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit chunk processing tasks
                future_to_chunk = {}
                for chunk in chunks:
                    future = executor.submit(
                        self._process_chunk,
                        operation_id,
                        chunk,
                        processor_func,
                        validation_func,
                        rollback_on_error
                    )
                    future_to_chunk[future] = chunk
                
                # Process completed chunks
                for future in as_completed(future_to_chunk):
                    chunk = future_to_chunk[future]
                    try:
                        chunk_result = future.result()
                        
                        # Update counters
                        success_count += chunk_result["success_count"]
                        failure_count += chunk_result["failure_count"]
                        errors.extend(chunk_result["errors"])
                        processed_items.extend(chunk_result["processed_items"])
                        
                        # Update operation tracking
                        self._active_operations[operation_id]["processed_items"] += len(chunk.items)
                        self._active_operations[operation_id]["success_count"] = success_count
                        self._active_operations[operation_id]["failure_count"] = failure_count
                        
                        # Call progress callback if provided
                        if progress_callback:
                            progress_percentage = (
                                self._active_operations[operation_id]["processed_items"] / 
                                self._active_operations[operation_id]["total_items"] * 100
                            )
                            await progress_callback(
                                operation_id,
                                progress_percentage,
                                self._active_operations[operation_id]["processed_items"],
                                success_count,
                                failure_count
                            )
                        
                    except Exception as e:
                        logger.error(f"Error processing chunk {chunk.chunk_id}: {str(e)}")
                        failure_count += len(chunk.items)
                        errors.append({
                            "chunk_id": chunk.chunk_id,
                            "error": str(e),
                            "item_count": len(chunk.items)
                        })
            
            # Calculate execution time
            execution_time = time.time() - start_time
            
            # Update operation status
            self._active_operations[operation_id]["status"] = "completed"
            self._active_operations[operation_id]["execution_time"] = execution_time
            
            # Store performance metrics
            self._performance_metrics[operation_id] = {
                "execution_time": execution_time,
                "items_per_second": len(items) / execution_time if execution_time > 0 else 0,
                "memory_usage_mb": psutil.Process().memory_info().rss / 1024 / 1024,
                "cpu_percent": psutil.cpu_percent(),
                "success_rate": success_count / len(items) if len(items) > 0 else 0
            }
            
            logger.info(
                f"Batch operation {operation_id} completed: "
                f"{success_count} success, {failure_count} failures, "
                f"{execution_time:.2f}s"
            )
            
            return BatchResult(
                success_count=success_count,
                failure_count=failure_count,
                errors=errors,
                processed_items=processed_items,
                metadata=self._performance_metrics[operation_id],
                execution_time=execution_time
            )
            
        except Exception as e:
            logger.error(f"Batch operation {operation_id} failed: {str(e)}")
            self._active_operations[operation_id]["status"] = "failed"
            raise
        finally:
            # Cleanup
            if operation_id in self._active_operations:
                del self._active_operations[operation_id]
    
    def _create_chunks(self, items: List[Any], chunk_size: int) -> List[ProcessingChunk]:
        """Create processing chunks from items list."""
        chunks = []
        for i in range(0, len(items), chunk_size):
            chunk_items = items[i:i + chunk_size]
            chunk = ProcessingChunk(
                chunk_id=str(uuid4()),
                items=chunk_items,
                start_index=i,
                end_index=min(i + chunk_size, len(items))
            )
            chunks.append(chunk)
        return chunks
    
    def _process_chunk(
        self,
        operation_id: str,
        chunk: ProcessingChunk,
        processor_func: Callable,
        validation_func: Optional[Callable] = None,
        rollback_on_error: bool = True
    ) -> Dict[str, Any]:
        """Process a single chunk of items."""
        session = self.session_factory()
        success_count = 0
        failure_count = 0
        errors = []
        processed_items = []
        
        try:
            # Begin database transaction
            session.begin()
            
            for i, item in enumerate(chunk.items):
                try:
                    # Validate item if validation function provided
                    if validation_func:
                        validation_result = validation_func(item)
                        if not validation_result.get("valid", True):
                            raise ValueError(f"Validation failed: {validation_result.get('error', 'Unknown error')}")
                    
                    # Process item
                    result = processor_func(item, session)
                    processed_items.append(result)
                    success_count += 1
                    
                except Exception as e:
                    failure_count += 1
                    error_info = {
                        "chunk_id": chunk.chunk_id,
                        "item_index": chunk.start_index + i,
                        "error": str(e),
                        "item_data": self._safe_serialize(item),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    errors.append(error_info)
                    
                    # Store error in database
                    self._log_batch_error(session, operation_id, error_info)
                    
                    # Rollback if configured and there are critical errors
                    if rollback_on_error and isinstance(e, (SQLAlchemyError, ValueError)):
                        logger.warning(f"Rolling back chunk {chunk.chunk_id} due to error: {str(e)}")
                        session.rollback()
                        session.begin()
                        # Mark all items in chunk as failed
                        failure_count = len(chunk.items)
                        success_count = 0
                        processed_items = []
                        break
            
            # Commit transaction if successful
            if success_count > 0:
                session.commit()
            
            return {
                "chunk_id": chunk.chunk_id,
                "success_count": success_count,
                "failure_count": failure_count,
                "errors": errors,
                "processed_items": processed_items
            }
            
        except Exception as e:
            session.rollback()
            logger.error(f"Critical error processing chunk {chunk.chunk_id}: {str(e)}")
            return {
                "chunk_id": chunk.chunk_id,
                "success_count": 0,
                "failure_count": len(chunk.items),
                "errors": [{
                    "chunk_id": chunk.chunk_id,
                    "error": f"Critical chunk error: {str(e)}",
                    "item_count": len(chunk.items),
                    "timestamp": datetime.utcnow().isoformat()
                }],
                "processed_items": []
            }
        finally:
            session.close()
    
    def _log_batch_error(self, session: Session, operation_id: str, error_info: Dict[str, Any]):
        """Log an error to the batch_errors table."""
        try:
            batch_error = BatchError(
                operation_id=operation_id,
                error_type=error_info.get("error_type", "processing_error"),
                error_message=error_info["error"][:1000],  # Limit message length
                item_index=error_info.get("item_index"),
                item_data=error_info.get("item_data", {}),
                step_name=error_info.get("step_name", "chunk_processing"),
                context_data={"chunk_id": error_info.get("chunk_id")},
                severity="error"
            )
            session.add(batch_error)
            session.flush()
        except Exception as e:
            logger.error(f"Failed to log batch error: {str(e)}")
    
    def _safe_serialize(self, obj: Any) -> Dict[str, Any]:
        """Safely serialize an object to a dictionary."""
        try:
            if hasattr(obj, "to_dict"):
                return obj.to_dict()
            elif isinstance(obj, dict):
                return obj
            elif isinstance(obj, (str, int, float, bool)):
                return {"value": obj}
            else:
                return {"type": str(type(obj)), "str": str(obj)[:200]}
        except Exception:
            return {"serialization_error": "Could not serialize object"}
    
    async def create_annotations_batch(
        self,
        operation_id: str,
        annotations_data: List[Dict[str, Any]],
        user_id: int,
        project_id: int,
        validate_before_create: bool = True,
        progress_callback: Optional[Callable] = None
    ) -> BatchResult:
        """
        Create annotations in batch with validation and progress tracking.
        """
        def processor_func(annotation_data: Dict[str, Any], session: Session) -> Annotation:
            # Create annotation object
            annotation = Annotation(
                start_char=annotation_data["start_char"],
                end_char=annotation_data["end_char"],
                selected_text=annotation_data["selected_text"],
                notes=annotation_data.get("notes"),
                confidence_score=annotation_data.get("confidence_score", 1.0),
                metadata=annotation_data.get("metadata", {}),
                context_before=annotation_data.get("context_before"),
                context_after=annotation_data.get("context_after"),
                text_id=annotation_data["text_id"],
                annotator_id=user_id,
                label_id=annotation_data["label_id"]
            )
            
            session.add(annotation)
            session.flush()  # Get ID without committing
            return annotation
        
        def validation_func(annotation_data: Dict[str, Any]) -> Dict[str, Any]:
            if not validate_before_create:
                return {"valid": True}
            
            # Basic validation
            required_fields = ["start_char", "end_char", "selected_text", "text_id", "label_id"]
            for field in required_fields:
                if field not in annotation_data:
                    return {"valid": False, "error": f"Missing required field: {field}"}
            
            # Validate span
            if annotation_data["start_char"] >= annotation_data["end_char"]:
                return {"valid": False, "error": "Invalid text span: start_char >= end_char"}
            
            # Check if text exists
            session = self.session_factory()
            try:
                text_exists = session.query(Text).filter(
                    Text.id == annotation_data["text_id"],
                    Text.project_id == project_id
                ).first() is not None
                
                if not text_exists:
                    return {"valid": False, "error": f"Text {annotation_data['text_id']} not found in project"}
                
                # Check if label exists
                label_exists = session.query(Label).filter(
                    Label.id == annotation_data["label_id"],
                    Label.project_id == project_id
                ).first() is not None
                
                if not label_exists:
                    return {"valid": False, "error": f"Label {annotation_data['label_id']} not found in project"}
                
                return {"valid": True}
            finally:
                session.close()
        
        return await self.process_batch_operation(
            operation_id=operation_id,
            items=annotations_data,
            processor_func=processor_func,
            validation_func=validation_func,
            progress_callback=progress_callback,
            rollback_on_error=True
        )
    
    async def update_annotations_batch(
        self,
        operation_id: str,
        updates_data: List[Dict[str, Any]],
        user_id: int,
        progress_callback: Optional[Callable] = None
    ) -> BatchResult:
        """Update annotations in batch."""
        
        def processor_func(update_data: Dict[str, Any], session: Session) -> Annotation:
            annotation_id = update_data["annotation_id"]
            updates = update_data["updates"]
            
            # Get annotation
            annotation = session.query(Annotation).filter(Annotation.id == annotation_id).first()
            if not annotation:
                raise ValueError(f"Annotation {annotation_id} not found")
            
            # Apply updates
            for field, value in updates.items():
                if hasattr(annotation, field):
                    setattr(annotation, field, value)
            
            # Update timestamp
            annotation.updated_at = datetime.utcnow()
            
            session.flush()
            return annotation
        
        def validation_func(update_data: Dict[str, Any]) -> Dict[str, Any]:
            if "annotation_id" not in update_data:
                return {"valid": False, "error": "Missing annotation_id"}
            
            if "updates" not in update_data or not update_data["updates"]:
                return {"valid": False, "error": "No updates provided"}
            
            return {"valid": True}
        
        return await self.process_batch_operation(
            operation_id=operation_id,
            items=updates_data,
            processor_func=processor_func,
            validation_func=validation_func,
            progress_callback=progress_callback,
            rollback_on_error=False  # Allow partial updates
        )
    
    async def delete_annotations_batch(
        self,
        operation_id: str,
        annotation_ids: List[int],
        user_id: int,
        progress_callback: Optional[Callable] = None
    ) -> BatchResult:
        """Delete annotations in batch."""
        
        def processor_func(annotation_id: int, session: Session) -> Dict[str, Any]:
            # Get annotation
            annotation = session.query(Annotation).filter(Annotation.id == annotation_id).first()
            if not annotation:
                raise ValueError(f"Annotation {annotation_id} not found")
            
            # Store info before deletion
            annotation_info = {
                "id": annotation.id,
                "text_id": annotation.text_id,
                "label_id": annotation.label_id,
                "selected_text": annotation.selected_text
            }
            
            # Delete annotation
            session.delete(annotation)
            session.flush()
            
            return annotation_info
        
        return await self.process_batch_operation(
            operation_id=operation_id,
            items=annotation_ids,
            processor_func=processor_func,
            progress_callback=progress_callback,
            rollback_on_error=False
        )
    
    def get_operation_status(self, operation_id: str) -> Dict[str, Any]:
        """Get the current status of a batch operation."""
        if operation_id in self._active_operations:
            return self._active_operations[operation_id]
        elif operation_id in self._performance_metrics:
            return {
                "status": "completed",
                "performance_metrics": self._performance_metrics[operation_id]
            }
        else:
            return {"status": "not_found"}
    
    def cancel_operation(self, operation_id: str) -> bool:
        """Cancel a running batch operation."""
        if operation_id in self._active_operations:
            self._active_operations[operation_id]["status"] = "cancelled"
            logger.info(f"Batch operation {operation_id} marked for cancellation")
            return True
        return False
    
    def get_performance_metrics(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """Get performance metrics for a completed operation."""
        return self._performance_metrics.get(operation_id)
    
    def cleanup_old_metrics(self, max_age_hours: int = 24):
        """Clean up old performance metrics."""
        cutoff_time = time.time() - (max_age_hours * 3600)
        
        to_remove = []
        for op_id, metrics in self._performance_metrics.items():
            if metrics.get("start_time", 0) < cutoff_time:
                to_remove.append(op_id)
        
        for op_id in to_remove:
            del self._performance_metrics[op_id]
        
        logger.info(f"Cleaned up {len(to_remove)} old performance metric records")