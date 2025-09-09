"""
Progress Tracker Utility

Real-time progress tracking for batch operations with WebSocket support,
performance metrics, and persistent progress logging.
"""

import asyncio
import json
import logging
import time
import psutil
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, asdict
from collections import deque
from threading import Lock
import weakref

from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from src.core.database import engine
from src.models.batch_models import BatchOperation, BatchProgress

logger = logging.getLogger(__name__)


@dataclass
class ProgressSnapshot:
    """Snapshot of operation progress at a point in time."""
    operation_id: str
    timestamp: datetime
    step_name: str
    step_description: str
    current_item: int
    total_items: int
    progress_percentage: float
    items_per_second: float
    estimated_completion: Optional[datetime]
    memory_usage_mb: float
    cpu_usage_percent: float
    metadata: Dict[str, Any]


@dataclass
class PerformanceMetrics:
    """Performance metrics for an operation."""
    avg_items_per_second: float
    peak_items_per_second: float
    avg_memory_usage_mb: float
    peak_memory_usage_mb: float
    avg_cpu_usage_percent: float
    peak_cpu_usage_percent: float
    total_execution_time: float
    total_items_processed: int


class ProgressTracker:
    """Advanced progress tracking system for batch operations."""
    
    def __init__(self, max_history_size: int = 1000, db_log_interval: int = 10):
        self.session_factory = sessionmaker(bind=engine)
        self.max_history_size = max_history_size
        self.db_log_interval = db_log_interval  # Log to DB every N updates
        
        # In-memory storage for active operations
        self._operations: Dict[str, Dict[str, Any]] = {}
        self._progress_history: Dict[str, deque] = {}
        self._performance_metrics: Dict[str, PerformanceMetrics] = {}
        self._callbacks: Dict[str, List[Callable]] = {}
        self._locks: Dict[str, Lock] = {}
        
        # Global lock for thread safety
        self._global_lock = Lock()
        
        # WebSocket connections for real-time updates
        self._websocket_connections = weakref.WeakSet()
        
        # Database logging counter
        self._db_log_counters: Dict[str, int] = {}
    
    def initialize_operation(
        self,
        operation_id: str,
        total_items: int,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Initialize progress tracking for a new operation."""
        with self._global_lock:
            self._locks[operation_id] = Lock()
        
        with self._locks[operation_id]:
            current_time = datetime.utcnow()
            
            self._operations[operation_id] = {
                "operation_id": operation_id,
                "total_items": total_items,
                "current_item": 0,
                "progress_percentage": 0.0,
                "description": description,
                "step_name": "Initializing",
                "step_description": "Setting up batch operation",
                "start_time": current_time,
                "last_update_time": current_time,
                "estimated_completion": None,
                "items_per_second": 0.0,
                "status": "initialized",
                "metadata": metadata or {},
                "error_message": None
            }
            
            self._progress_history[operation_id] = deque(maxlen=self.max_history_size)
            self._db_log_counters[operation_id] = 0
            
            # Log initial progress to database
            self._log_progress_to_db(operation_id, force=True)
            
            logger.info(f"Initialized progress tracking for operation {operation_id} with {total_items} items")
    
    def update_progress(
        self,
        operation_id: str,
        current_item: int,
        step_name: Optional[str] = None,
        step_description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update progress for an operation."""
        if operation_id not in self._operations:
            logger.warning(f"Operation {operation_id} not found for progress update")
            return
        
        with self._locks[operation_id]:
            operation = self._operations[operation_id]
            current_time = datetime.utcnow()
            
            # Calculate progress
            progress_percentage = (current_item / operation["total_items"] * 100) if operation["total_items"] > 0 else 0
            
            # Calculate items per second
            time_elapsed = (current_time - operation["last_update_time"]).total_seconds()
            if time_elapsed > 0:
                items_processed = current_item - operation["current_item"]
                current_items_per_second = items_processed / time_elapsed
                
                # Smooth the rate using exponential moving average
                if operation["items_per_second"] == 0:
                    operation["items_per_second"] = current_items_per_second
                else:
                    operation["items_per_second"] = (
                        0.3 * current_items_per_second + 0.7 * operation["items_per_second"]
                    )
            
            # Calculate estimated completion time
            if operation["items_per_second"] > 0:
                remaining_items = operation["total_items"] - current_item
                remaining_seconds = remaining_items / operation["items_per_second"]
                operation["estimated_completion"] = current_time + timedelta(seconds=remaining_seconds)
            
            # Update operation data
            operation.update({
                "current_item": current_item,
                "progress_percentage": progress_percentage,
                "last_update_time": current_time,
                "step_name": step_name or operation["step_name"],
                "step_description": step_description or operation["step_description"],
                "status": "running"
            })
            
            if metadata:
                operation["metadata"].update(metadata)
            
            # Get system metrics
            memory_usage_mb = psutil.Process().memory_info().rss / 1024 / 1024
            cpu_usage_percent = psutil.cpu_percent(interval=None)
            
            # Create progress snapshot
            snapshot = ProgressSnapshot(
                operation_id=operation_id,
                timestamp=current_time,
                step_name=operation["step_name"],
                step_description=operation["step_description"],
                current_item=current_item,
                total_items=operation["total_items"],
                progress_percentage=progress_percentage,
                items_per_second=operation["items_per_second"],
                estimated_completion=operation["estimated_completion"],
                memory_usage_mb=memory_usage_mb,
                cpu_usage_percent=cpu_usage_percent,
                metadata=operation["metadata"].copy()
            )
            
            # Add to history
            self._progress_history[operation_id].append(snapshot)
            
            # Update performance metrics
            self._update_performance_metrics(operation_id, snapshot)
            
            # Log to database periodically
            self._db_log_counters[operation_id] += 1
            if self._db_log_counters[operation_id] >= self.db_log_interval:
                self._log_progress_to_db(operation_id)
                self._db_log_counters[operation_id] = 0
            
            # Notify callbacks
            self._notify_callbacks(operation_id, snapshot)
            
            # Send WebSocket updates
            asyncio.create_task(self._broadcast_progress_update(operation_id, snapshot))
    
    def complete_operation(
        self,
        operation_id: str,
        final_message: str = "Operation completed successfully",
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Mark an operation as completed."""
        if operation_id not in self._operations:
            logger.warning(f"Operation {operation_id} not found for completion")
            return
        
        with self._locks[operation_id]:
            operation = self._operations[operation_id]
            current_time = datetime.utcnow()
            
            operation.update({
                "status": "completed",
                "progress_percentage": 100.0,
                "current_item": operation["total_items"],
                "step_name": "Completed",
                "step_description": final_message,
                "last_update_time": current_time,
                "completion_time": current_time
            })
            
            if metadata:
                operation["metadata"].update(metadata)
            
            # Final database log
            self._log_progress_to_db(operation_id, force=True)
            
            # Calculate final performance metrics
            total_time = (current_time - operation["start_time"]).total_seconds()
            final_metrics = PerformanceMetrics(
                avg_items_per_second=operation["total_items"] / total_time if total_time > 0 else 0,
                peak_items_per_second=max(
                    [s.items_per_second for s in self._progress_history[operation_id]], 
                    default=0
                ),
                avg_memory_usage_mb=sum(
                    s.memory_usage_mb for s in self._progress_history[operation_id]
                ) / len(self._progress_history[operation_id]) if self._progress_history[operation_id] else 0,
                peak_memory_usage_mb=max(
                    [s.memory_usage_mb for s in self._progress_history[operation_id]], 
                    default=0
                ),
                avg_cpu_usage_percent=sum(
                    s.cpu_usage_percent for s in self._progress_history[operation_id]
                ) / len(self._progress_history[operation_id]) if self._progress_history[operation_id] else 0,
                peak_cpu_usage_percent=max(
                    [s.cpu_usage_percent for s in self._progress_history[operation_id]], 
                    default=0
                ),
                total_execution_time=total_time,
                total_items_processed=operation["total_items"]
            )
            
            self._performance_metrics[operation_id] = final_metrics
            
            logger.info(f"Operation {operation_id} completed successfully")
    
    def fail_operation(
        self,
        operation_id: str,
        error_message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Mark an operation as failed."""
        if operation_id not in self._operations:
            logger.warning(f"Operation {operation_id} not found for failure")
            return
        
        with self._locks[operation_id]:
            operation = self._operations[operation_id]
            current_time = datetime.utcnow()
            
            operation.update({
                "status": "failed",
                "step_name": "Failed",
                "step_description": f"Operation failed: {error_message}",
                "error_message": error_message,
                "last_update_time": current_time,
                "completion_time": current_time
            })
            
            if metadata:
                operation["metadata"].update(metadata)
            
            # Final database log
            self._log_progress_to_db(operation_id, force=True)
            
            logger.error(f"Operation {operation_id} failed: {error_message}")
    
    def cancel_operation(
        self,
        operation_id: str,
        reason: str = "Operation cancelled by user"
    ) -> None:
        """Cancel an operation."""
        if operation_id not in self._operations:
            logger.warning(f"Operation {operation_id} not found for cancellation")
            return
        
        with self._locks[operation_id]:
            operation = self._operations[operation_id]
            current_time = datetime.utcnow()
            
            operation.update({
                "status": "cancelled",
                "step_name": "Cancelled",
                "step_description": reason,
                "last_update_time": current_time,
                "completion_time": current_time
            })
            
            # Final database log
            self._log_progress_to_db(operation_id, force=True)
            
            logger.info(f"Operation {operation_id} cancelled: {reason}")
    
    def get_progress(self, operation_id: str) -> Dict[str, Any]:
        """Get current progress information for an operation."""
        if operation_id not in self._operations:
            return {}
        
        with self._locks[operation_id]:
            operation = self._operations[operation_id].copy()
            
            # Convert datetime objects to ISO strings
            for key in ["start_time", "last_update_time", "estimated_completion", "completion_time"]:
                if key in operation and isinstance(operation[key], datetime):
                    operation[key] = operation[key].isoformat()
            
            return operation
    
    def get_progress_history(
        self,
        operation_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get progress history for an operation."""
        if operation_id not in self._progress_history:
            return []
        
        history = list(self._progress_history[operation_id])
        if limit:
            history = history[-limit:]
        
        # Convert snapshots to dictionaries
        return [
            {
                **asdict(snapshot),
                "timestamp": snapshot.timestamp.isoformat(),
                "estimated_completion": (
                    snapshot.estimated_completion.isoformat() 
                    if snapshot.estimated_completion else None
                )
            }
            for snapshot in history
        ]
    
    def get_performance_metrics(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """Get performance metrics for a completed operation."""
        if operation_id not in self._performance_metrics:
            return None
        
        return asdict(self._performance_metrics[operation_id])
    
    def add_progress_callback(
        self,
        operation_id: str,
        callback: Callable[[str, ProgressSnapshot], None]
    ) -> None:
        """Add a callback function for progress updates."""
        if operation_id not in self._callbacks:
            self._callbacks[operation_id] = []
        self._callbacks[operation_id].append(callback)
    
    def remove_progress_callback(
        self,
        operation_id: str,
        callback: Callable[[str, ProgressSnapshot], None]
    ) -> None:
        """Remove a progress callback."""
        if operation_id in self._callbacks:
            try:
                self._callbacks[operation_id].remove(callback)
            except ValueError:
                pass
    
    def cleanup_completed_operations(self, max_age_hours: int = 24) -> int:
        """Clean up old completed operations from memory."""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        cleaned_count = 0
        
        to_remove = []
        with self._global_lock:
            for operation_id, operation in self._operations.items():
                if (operation["status"] in ["completed", "failed", "cancelled"] and
                    "completion_time" in operation and
                    operation["completion_time"] < cutoff_time):
                    to_remove.append(operation_id)
        
        for operation_id in to_remove:
            self._cleanup_operation(operation_id)
            cleaned_count += 1
        
        logger.info(f"Cleaned up {cleaned_count} old operations")
        return cleaned_count
    
    def _cleanup_operation(self, operation_id: str) -> None:
        """Clean up all data for a specific operation."""
        with self._global_lock:
            # Remove from all data structures
            self._operations.pop(operation_id, None)
            self._progress_history.pop(operation_id, None)
            self._performance_metrics.pop(operation_id, None)
            self._callbacks.pop(operation_id, None)
            self._db_log_counters.pop(operation_id, None)
            
            # Remove lock
            lock = self._locks.pop(operation_id, None)
            if lock:
                del lock
    
    def _update_performance_metrics(
        self,
        operation_id: str,
        snapshot: ProgressSnapshot
    ) -> None:
        """Update running performance metrics."""
        # This is handled in real-time, final metrics calculated in complete_operation
        pass
    
    def _log_progress_to_db(self, operation_id: str, force: bool = False) -> None:
        """Log progress to database."""
        if operation_id not in self._operations:
            return
        
        try:
            session = self.session_factory()
            try:
                operation = self._operations[operation_id]
                
                # Get latest snapshot
                latest_snapshot = None
                if self._progress_history[operation_id]:
                    latest_snapshot = self._progress_history[operation_id][-1]
                
                # Create progress record
                progress_record = BatchProgress(
                    operation_id=operation_id,
                    step_name=operation["step_name"],
                    step_description=operation["step_description"],
                    current_item=operation["current_item"],
                    total_items=operation["total_items"],
                    progress_percentage=operation["progress_percentage"],
                    items_per_second=operation["items_per_second"],
                    memory_usage_mb=latest_snapshot.memory_usage_mb if latest_snapshot else 0,
                    cpu_usage_percent=latest_snapshot.cpu_usage_percent if latest_snapshot else 0,
                    status=operation["status"],
                    metadata=operation["metadata"]
                )
                
                session.add(progress_record)
                session.commit()
                
            finally:
                session.close()
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to log progress to database for {operation_id}: {str(e)}")
    
    def _notify_callbacks(self, operation_id: str, snapshot: ProgressSnapshot) -> None:
        """Notify registered callbacks of progress updates."""
        if operation_id in self._callbacks:
            for callback in self._callbacks[operation_id]:
                try:
                    callback(operation_id, snapshot)
                except Exception as e:
                    logger.error(f"Error in progress callback for {operation_id}: {str(e)}")
    
    async def _broadcast_progress_update(
        self,
        operation_id: str,
        snapshot: ProgressSnapshot
    ) -> None:
        """Broadcast progress update to WebSocket connections."""
        if not self._websocket_connections:
            return
        
        update_message = {
            "type": "progress_update",
            "operation_id": operation_id,
            "data": {
                **asdict(snapshot),
                "timestamp": snapshot.timestamp.isoformat(),
                "estimated_completion": (
                    snapshot.estimated_completion.isoformat() 
                    if snapshot.estimated_completion else None
                )
            }
        }
        
        # Send to all connected WebSocket clients
        disconnected = []
        for websocket in self._websocket_connections:
            try:
                await websocket.send_text(json.dumps(update_message))
            except Exception:
                disconnected.append(websocket)
        
        # Remove disconnected WebSockets
        for ws in disconnected:
            try:
                self._websocket_connections.discard(ws)
            except:
                pass
    
    def add_websocket_connection(self, websocket) -> None:
        """Add a WebSocket connection for real-time updates."""
        self._websocket_connections.add(websocket)
    
    def remove_websocket_connection(self, websocket) -> None:
        """Remove a WebSocket connection."""
        self._websocket_connections.discard(websocket)
    
    def get_active_operations(self) -> List[Dict[str, Any]]:
        """Get list of all active operations."""
        active_ops = []
        for operation_id, operation in self._operations.items():
            if operation["status"] in ["initialized", "running"]:
                op_data = self.get_progress(operation_id)
                active_ops.append(op_data)
        return active_ops
    
    def get_operation_summary(self, operation_id: str) -> Dict[str, Any]:
        """Get a summary of an operation including performance metrics."""
        progress = self.get_progress(operation_id)
        if not progress:
            return {}
        
        performance = self.get_performance_metrics(operation_id)
        history_count = len(self._progress_history.get(operation_id, []))
        
        return {
            "operation_id": operation_id,
            "status": progress.get("status"),
            "progress_percentage": progress.get("progress_percentage", 0),
            "current_item": progress.get("current_item", 0),
            "total_items": progress.get("total_items", 0),
            "items_per_second": progress.get("items_per_second", 0),
            "start_time": progress.get("start_time"),
            "estimated_completion": progress.get("estimated_completion"),
            "performance_metrics": performance,
            "history_points": history_count,
            "metadata": progress.get("metadata", {})
        }