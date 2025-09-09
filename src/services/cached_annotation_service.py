"""
Cached Annotation Service

Enhanced annotation service with intelligent caching:
- Cache frequently accessed annotations
- Batch loading optimization
- Real-time cache invalidation
- Annotation aggregation caching
"""

from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func
from datetime import datetime, timedelta

from ..models.annotation import Annotation
from ..models.text import Text
from ..models.user import User
from ..models.label import Label
from ..services.cache_manager import get_cache_manager
from ..utils.cache_decorators import cached, cache_annotations, cache_invalidate, CacheContext
from ..core.cache_service import CacheKey
from ..utils.logger import get_logger


logger = get_logger(__name__)


class CachedAnnotationService:
    """Annotation service with comprehensive caching"""
    
    def __init__(self):
        self.cache_manager = get_cache_manager()
    
    @cached(ttl=900, key_prefix="annotation")
    async def get_annotation_by_id(self, annotation_id: int, db: Session) -> Optional[Annotation]:
        """Get annotation by ID with caching"""
        try:
            annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
            if annotation:
                logger.debug(f"Loaded annotation {annotation_id} from database")
            return annotation
        except Exception as e:
            logger.error(f"Error loading annotation {annotation_id}: {str(e)}")
            return None
    
    @cache_annotations(ttl=900)
    async def get_text_annotations(
        self,
        text_id: int,
        db: Session,
        user_id: Optional[int] = None,
        label_ids: Optional[List[int]] = None,
        include_deleted: bool = False
    ) -> List[Annotation]:
        """Get annotations for a text with caching"""
        try:
            query = db.query(Annotation).filter(Annotation.text_id == text_id)
            
            # Filter by user if specified
            if user_id is not None:
                query = query.filter(Annotation.user_id == user_id)
            
            # Filter by labels if specified
            if label_ids:
                query = query.filter(Annotation.label_id.in_(label_ids))
            
            # Filter deleted annotations
            if not include_deleted:
                query = query.filter(Annotation.is_deleted == False)
            
            annotations = query.order_by(Annotation.start_char).all()
            logger.debug(f"Loaded {len(annotations)} annotations for text {text_id}")
            return annotations
            
        except Exception as e:
            logger.error(f"Error loading annotations for text {text_id}: {str(e)}")
            return []
    
    @cached(ttl=1200, key_prefix="user_annotations")
    async def get_user_annotations(
        self,
        user_id: int,
        db: Session,
        project_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Annotation]:
        """Get user's annotations with caching"""
        try:
            query = db.query(Annotation).filter(Annotation.user_id == user_id)
            
            # Filter by project if specified
            if project_id:
                query = query.join(Text).filter(Text.project_id == project_id)
            
            # Order by most recent first
            annotations = query.filter(Annotation.is_deleted == False)\
                .order_by(desc(Annotation.created_at))\
                .offset(offset).limit(limit).all()
            
            logger.debug(f"Loaded {len(annotations)} annotations for user {user_id}")
            return annotations
            
        except Exception as e:
            logger.error(f"Error loading user {user_id} annotations: {str(e)}")
            return []
    
    @cached(ttl=600, key_prefix="annotation_stats")
    async def get_annotation_statistics(
        self,
        project_id: Optional[int] = None,
        user_id: Optional[int] = None,
        text_id: Optional[int] = None,
        db: Session = None
    ) -> Dict[str, Any]:
        """Get annotation statistics with caching"""
        try:
            base_query = db.query(Annotation).filter(Annotation.is_deleted == False)
            
            # Apply filters
            if project_id:
                base_query = base_query.join(Text).filter(Text.project_id == project_id)
            if user_id:
                base_query = base_query.filter(Annotation.user_id == user_id)
            if text_id:
                base_query = base_query.filter(Annotation.text_id == text_id)
            
            # Count total annotations
            total_count = base_query.count()
            
            # Count by label
            label_counts = db.query(
                Label.name,
                func.count(Annotation.id).label('count')
            ).join(Annotation).filter(Annotation.is_deleted == False)
            
            if project_id:
                label_counts = label_counts.join(Text).filter(Text.project_id == project_id)
            if user_id:
                label_counts = label_counts.filter(Annotation.user_id == user_id)
            if text_id:
                label_counts = label_counts.filter(Annotation.text_id == text_id)
                
            label_counts = label_counts.group_by(Label.name).all()
            
            # Count unique annotators
            annotator_count = base_query.with_entities(
                func.count(func.distinct(Annotation.user_id))
            ).scalar()
            
            # Calculate average annotation length
            avg_length = base_query.with_entities(
                func.avg(Annotation.end_char - Annotation.start_char)
            ).scalar()
            
            # Recent activity (last 24 hours)
            recent_threshold = datetime.utcnow() - timedelta(hours=24)
            recent_count = base_query.filter(
                Annotation.created_at >= recent_threshold
            ).count()
            
            stats = {
                "total_annotations": total_count,
                "unique_annotators": annotator_count or 0,
                "average_length": round(float(avg_length or 0), 2),
                "recent_activity": recent_count,
                "label_distribution": {name: count for name, count in label_counts},
                "generated_at": datetime.utcnow().isoformat()
            }
            
            logger.debug(f"Calculated annotation statistics: {total_count} total annotations")
            return stats
            
        except Exception as e:
            logger.error(f"Error calculating annotation statistics: {str(e)}")
            return {
                "total_annotations": 0,
                "unique_annotators": 0,
                "average_length": 0.0,
                "recent_activity": 0,
                "label_distribution": {},
                "error": str(e)
            }
    
    @cache_invalidate("text:*:annotations*", "user_annotations:*", "annotation_stats:*")
    async def create_annotation(
        self,
        annotation_data: Dict[str, Any],
        user_id: int,
        db: Session
    ) -> Annotation:
        """Create new annotation with cache invalidation"""
        try:
            annotation = Annotation(
                text_id=annotation_data["text_id"],
                user_id=user_id,
                label_id=annotation_data["label_id"],
                start_char=annotation_data["start_char"],
                end_char=annotation_data["end_char"],
                confidence=annotation_data.get("confidence", 1.0),
                notes=annotation_data.get("notes")
            )
            
            db.add(annotation)
            db.commit()
            db.refresh(annotation)
            
            # Cache the new annotation immediately
            key = CacheKey.generate("annotation", annotation.id)
            await self.cache_manager.cache.set(key, annotation, ttl=900)
            
            logger.info(f"Created annotation {annotation.id} for text {annotation.text_id}")
            return annotation
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating annotation: {str(e)}")
            raise
    
    @cache_invalidate("text:*:annotations*", "user_annotations:*", "annotation_stats:*")
    async def update_annotation(
        self,
        annotation_id: int,
        update_data: Dict[str, Any],
        db: Session
    ) -> Optional[Annotation]:
        """Update annotation with cache invalidation"""
        try:
            annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
            if not annotation:
                return None
            
            # Store old values for cache invalidation
            old_text_id = annotation.text_id
            
            # Update fields
            for field, value in update_data.items():
                if hasattr(annotation, field) and value is not None:
                    setattr(annotation, field, value)
            
            annotation.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(annotation)
            
            # Update cache immediately
            key = CacheKey.generate("annotation", annotation.id)
            await self.cache_manager.cache.set(key, annotation, ttl=900)
            
            # Invalidate text annotations cache if text changed
            if old_text_id != annotation.text_id:
                old_key = CacheKey.pattern("text", old_text_id, "annotations:*")
                await self.cache_manager.cache.flush_pattern(old_key)
            
            logger.info(f"Updated annotation {annotation.id}")
            return annotation
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating annotation {annotation_id}: {str(e)}")
            raise
    
    @cache_invalidate("text:*:annotations*", "user_annotations:*", "annotation_stats:*")
    async def delete_annotation(self, annotation_id: int, db: Session, soft_delete: bool = True) -> bool:
        """Delete annotation with cache invalidation"""
        try:
            annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
            if not annotation:
                return False
            
            if soft_delete:
                annotation.is_deleted = True
                annotation.updated_at = datetime.utcnow()
                db.commit()
            else:
                db.delete(annotation)
                db.commit()
            
            # Remove from cache
            key = CacheKey.generate("annotation", annotation_id)
            await self.cache_manager.cache.delete(key)
            
            logger.info(f"{'Soft ' if soft_delete else ''}deleted annotation {annotation_id}")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting annotation {annotation_id}: {str(e)}")
            raise
    
    @cached(ttl=1800, key_prefix="annotation_conflicts")
    async def get_annotation_conflicts(
        self,
        text_id: int,
        db: Session,
        overlap_threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """Get overlapping annotations that might be conflicts"""
        try:
            annotations = await self.get_text_annotations(text_id, db)
            
            conflicts = []
            
            # Check for overlaps between different users
            for i, ann1 in enumerate(annotations):
                for ann2 in annotations[i + 1:]:
                    if ann1.user_id != ann2.user_id:
                        # Calculate overlap
                        overlap_start = max(ann1.start_char, ann2.start_char)
                        overlap_end = min(ann1.end_char, ann2.end_char)
                        
                        if overlap_start < overlap_end:
                            overlap_length = overlap_end - overlap_start
                            ann1_length = ann1.end_char - ann1.start_char
                            ann2_length = ann2.end_char - ann2.start_char
                            
                            overlap_ratio = overlap_length / min(ann1_length, ann2_length)
                            
                            if overlap_ratio >= overlap_threshold:
                                conflicts.append({
                                    "annotation1_id": ann1.id,
                                    "annotation2_id": ann2.id,
                                    "overlap_ratio": round(overlap_ratio, 3),
                                    "overlap_start": overlap_start,
                                    "overlap_end": overlap_end,
                                    "different_labels": ann1.label_id != ann2.label_id
                                })
            
            logger.debug(f"Found {len(conflicts)} potential conflicts for text {text_id}")
            return conflicts
            
        except Exception as e:
            logger.error(f"Error detecting conflicts for text {text_id}: {str(e)}")
            return []
    
    async def batch_create_annotations(
        self,
        annotations_data: List[Dict[str, Any]],
        user_id: int,
        db: Session
    ) -> Tuple[List[Annotation], List[str]]:
        """Create multiple annotations efficiently with batch cache operations"""
        created_annotations = []
        errors = []
        
        try:
            # Group by text_id for cache invalidation
            text_ids = set()
            
            for ann_data in annotations_data:
                try:
                    annotation = Annotation(
                        text_id=ann_data["text_id"],
                        user_id=user_id,
                        label_id=ann_data["label_id"],
                        start_char=ann_data["start_char"],
                        end_char=ann_data["end_char"],
                        confidence=ann_data.get("confidence", 1.0),
                        notes=ann_data.get("notes")
                    )
                    
                    db.add(annotation)
                    text_ids.add(ann_data["text_id"])
                    
                except Exception as e:
                    errors.append(f"Failed to create annotation: {str(e)}")
            
            if created_annotations:
                db.commit()
                
                # Refresh all annotations
                for annotation in created_annotations:
                    db.refresh(annotation)
                
                # Batch cache operations
                async with CacheContext():
                    # Cache new annotations
                    for annotation in created_annotations:
                        key = CacheKey.generate("annotation", annotation.id)
                        await self.cache_manager.cache.set(key, annotation, ttl=900)
                    
                    # Invalidate affected text annotation caches
                    for text_id in text_ids:
                        pattern = CacheKey.pattern("text", text_id, "annotations:*")
                        await self.cache_manager.cache.flush_pattern(pattern)
                
                logger.info(f"Batch created {len(created_annotations)} annotations")
            
            return created_annotations, errors
            
        except Exception as e:
            db.rollback()
            error_msg = f"Batch annotation creation failed: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
            return [], errors
    
    async def warm_annotation_cache(self, text_ids: List[int], db: Session) -> Dict[str, int]:
        """Warm annotation cache for multiple texts"""
        results = {"success": 0, "failed": 0}
        
        for text_id in text_ids:
            try:
                annotations = await self.get_text_annotations(text_id, db)
                if annotations is not None:
                    results["success"] += 1
                else:
                    results["failed"] += 1
                    
            except Exception as e:
                logger.warning(f"Failed to warm annotation cache for text {text_id}: {str(e)}")
                results["failed"] += 1
        
        logger.info(f"Warmed annotation cache for {results['success']}/{len(text_ids)} texts")
        return results
    
    async def get_cache_info(self) -> Dict[str, Any]:
        """Get cache information for annotations"""
        try:
            # Get annotation-related cache keys
            patterns = [
                "annotation:*",
                "text:*:annotations*",
                "user_annotations:*",
                "annotation_stats:*",
                "annotation_conflicts:*"
            ]
            
            cache_info = {}
            for pattern in patterns:
                keys = await self.cache_manager.cache.keys(pattern)
                cache_info[pattern] = len(keys)
            
            return {
                "cache_distribution": cache_info,
                "total_cached_items": sum(cache_info.values()),
                "service_metrics": self.cache_manager.cache.get_metrics()
            }
            
        except Exception as e:
            logger.error(f"Error getting cache info: {str(e)}")
            return {"error": str(e)}


# Global service instance
_cached_annotation_service: Optional[CachedAnnotationService] = None


def get_cached_annotation_service() -> CachedAnnotationService:
    """Get global cached annotation service instance"""
    global _cached_annotation_service
    if _cached_annotation_service is None:
        _cached_annotation_service = CachedAnnotationService()
    return _cached_annotation_service