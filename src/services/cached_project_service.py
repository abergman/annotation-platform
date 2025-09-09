"""
Cached Project Service

Enhanced project service with comprehensive caching:
- Cache-aside pattern for project data
- Query result caching for expensive operations
- Distributed invalidation strategies
- Cache warming and preloading
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func

from ..models.project import Project
from ..models.user import User
from ..services.cache_manager import get_cache_manager
from ..utils.cache_decorators import cached, cache_project, cache_invalidate, CacheContext
from ..core.cache_service import CacheKey
from ..utils.logger import get_logger


logger = get_logger(__name__)


class CachedProjectService:
    """Project service with comprehensive caching"""
    
    def __init__(self):
        self.cache_manager = get_cache_manager()
    
    @cache_project(ttl=1800, include_stats=False)
    async def get_project_by_id(self, project_id: int, db: Session) -> Optional[Project]:
        """Get project by ID with caching"""
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if project:
                logger.debug(f"Loaded project {project_id} from database")
            return project
        except Exception as e:
            logger.error(f"Error loading project {project_id}: {str(e)}")
            return None
    
    @cached(ttl=3600, key_prefix="user_projects")
    async def get_user_projects(
        self, 
        user_id: int, 
        db: Session,
        include_public: bool = True,
        is_active: Optional[bool] = None
    ) -> List[Project]:
        """Get projects accessible by user with caching"""
        try:
            query = db.query(Project)
            
            # Filter by user access or public projects
            if include_public:
                query = query.filter(
                    or_(
                        Project.owner_id == user_id,
                        Project.collaborators.any(User.id == user_id),
                        Project.is_public == True
                    )
                )
            else:
                query = query.filter(
                    or_(
                        Project.owner_id == user_id,
                        Project.collaborators.any(User.id == user_id)
                    )
                )
            
            # Filter by active status if specified
            if is_active is not None:
                query = query.filter(Project.is_active == is_active)
            
            projects = query.order_by(desc(Project.updated_at)).all()
            logger.debug(f"Loaded {len(projects)} projects for user {user_id}")
            return projects
            
        except Exception as e:
            logger.error(f"Error loading projects for user {user_id}: {str(e)}")
            return []
    
    @cached(ttl=600, key_prefix="project_stats")
    async def get_project_statistics(self, project_id: int, db: Session) -> Dict[str, Any]:
        """Get cached project statistics"""
        try:
            # This would be an expensive query in practice
            from ..models.text import Text
            from ..models.annotation import Annotation
            from ..models.label import Label
            
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                return {}
            
            # Count texts
            text_count = db.query(func.count(Text.id)).filter(Text.project_id == project_id).scalar()
            
            # Count annotations
            annotation_count = db.query(func.count(Annotation.id)).join(Text).filter(
                Text.project_id == project_id
            ).scalar()
            
            # Count labels
            label_count = db.query(func.count(Label.id)).filter(Label.project_id == project_id).scalar()
            
            # Count unique annotators
            annotator_count = db.query(func.count(func.distinct(Annotation.user_id))).join(Text).filter(
                Text.project_id == project_id
            ).scalar()
            
            stats = {
                "project_id": project_id,
                "text_count": text_count or 0,
                "annotation_count": annotation_count or 0,
                "label_count": label_count or 0,
                "annotator_count": annotator_count or 0,
                "completion_rate": 0.0  # Calculate based on your business logic
            }
            
            # Calculate completion rate if we have texts
            if text_count > 0:
                # This is a simplified calculation - adjust based on your requirements
                annotated_texts = db.query(func.count(func.distinct(Text.id))).join(Annotation).filter(
                    Text.project_id == project_id
                ).scalar()
                stats["completion_rate"] = (annotated_texts or 0) / text_count * 100
            
            logger.debug(f"Calculated statistics for project {project_id}")
            return stats
            
        except Exception as e:
            logger.error(f"Error calculating statistics for project {project_id}: {str(e)}")
            return {
                "project_id": project_id,
                "text_count": 0,
                "annotation_count": 0,
                "label_count": 0,
                "annotator_count": 0,
                "completion_rate": 0.0,
                "error": str(e)
            }
    
    @cache_invalidate("user_projects:*", "project_stats:*")
    async def create_project(self, project_data: Dict[str, Any], owner_id: int, db: Session) -> Project:
        """Create new project with cache invalidation"""
        try:
            project = Project(
                name=project_data["name"],
                description=project_data.get("description"),
                annotation_guidelines=project_data.get("annotation_guidelines"),
                allow_multiple_labels=project_data.get("allow_multiple_labels", True),
                require_all_texts=project_data.get("require_all_texts", False),
                inter_annotator_agreement=project_data.get("inter_annotator_agreement", False),
                is_public=project_data.get("is_public", False),
                owner_id=owner_id
            )
            
            db.add(project)
            db.commit()
            db.refresh(project)
            
            # Cache the new project immediately
            await self.cache_manager.set_project(project.id, project)
            
            logger.info(f"Created project {project.id}: {project.name}")
            return project
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating project: {str(e)}")
            raise
    
    @cache_invalidate("user_projects:*", "project_stats:*")
    async def update_project(
        self, 
        project_id: int, 
        update_data: Dict[str, Any], 
        db: Session
    ) -> Optional[Project]:
        """Update project with cache invalidation"""
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                return None
            
            # Update fields
            for field, value in update_data.items():
                if hasattr(project, field) and value is not None:
                    setattr(project, field, value)
            
            db.commit()
            db.refresh(project)
            
            # Update cache immediately
            await self.cache_manager.set_project(project.id, project)
            
            logger.info(f"Updated project {project.id}")
            return project
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating project {project_id}: {str(e)}")
            raise
    
    @cache_invalidate("user_projects:*", "project_stats:*")
    async def delete_project(self, project_id: int, db: Session) -> bool:
        """Delete project with comprehensive cache invalidation"""
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                return False
            
            async with CacheContext([
                CacheKey.generate("project", project_id),
                CacheKey.pattern("project", project_id, "*"),
                CacheKey.pattern("text", f"project:{project_id}:*"),
                CacheKey.pattern("annotation", f"project:{project_id}:*"),
                CacheKey.pattern("query", f"*project:{project_id}*")
            ]):
                db.delete(project)
                db.commit()
            
            logger.info(f"Deleted project {project_id}")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting project {project_id}: {str(e)}")
            raise
    
    @cached(ttl=7200, key_prefix="public_projects")
    async def get_public_projects(
        self, 
        db: Session, 
        limit: int = 50, 
        offset: int = 0
    ) -> List[Project]:
        """Get public projects with caching"""
        try:
            projects = db.query(Project).filter(
                and_(
                    Project.is_public == True,
                    Project.is_active == True
                )
            ).order_by(desc(Project.created_at)).offset(offset).limit(limit).all()
            
            logger.debug(f"Loaded {len(projects)} public projects (offset={offset}, limit={limit})")
            return projects
            
        except Exception as e:
            logger.error(f"Error loading public projects: {str(e)}")
            return []
    
    @cached(ttl=1800, key_prefix="project_search")
    async def search_projects(
        self, 
        query: str, 
        user_id: int, 
        db: Session,
        limit: int = 20
    ) -> List[Project]:
        """Search projects with caching"""
        try:
            # Search in name and description
            search_filter = or_(
                Project.name.ilike(f"%{query}%"),
                Project.description.ilike(f"%{query}%")
            )
            
            # Filter by access permissions
            access_filter = or_(
                Project.owner_id == user_id,
                Project.collaborators.any(User.id == user_id),
                Project.is_public == True
            )
            
            projects = db.query(Project).filter(
                and_(
                    search_filter,
                    access_filter,
                    Project.is_active == True
                )
            ).order_by(desc(Project.updated_at)).limit(limit).all()
            
            logger.debug(f"Found {len(projects)} projects matching '{query}' for user {user_id}")
            return projects
            
        except Exception as e:
            logger.error(f"Error searching projects: {str(e)}")
            return []
    
    async def warm_project_cache(self, project_ids: List[int], db: Session) -> Dict[str, int]:
        """Warm cache for multiple projects"""
        results = {"success": 0, "failed": 0}
        
        for project_id in project_ids:
            try:
                # Load project
                project = await self.get_project_by_id(project_id, db)
                if project:
                    results["success"] += 1
                    
                    # Also warm statistics
                    await self.get_project_statistics(project_id, db)
                else:
                    results["failed"] += 1
                    
            except Exception as e:
                logger.warning(f"Failed to warm cache for project {project_id}: {str(e)}")
                results["failed"] += 1
        
        logger.info(f"Warmed cache for {results['success']}/{len(project_ids)} projects")
        return results
    
    async def invalidate_project_caches(self, project_id: int, cascade: bool = True) -> int:
        """Invalidate all caches related to a project"""
        patterns = [
            f"project:{project_id}",
            f"project:{project_id}:*",
            f"user_projects:*",
            f"project_stats:{project_id}:*"
        ]
        
        if cascade:
            patterns.extend([
                f"*project:{project_id}*",
                f"text:project:{project_id}:*",
                f"annotation:project:{project_id}:*",
                f"label:project:{project_id}:*"
            ])
        
        total_invalidated = 0
        for pattern in patterns:
            count = await self.cache_manager.invalidate_query_cache(pattern)
            total_invalidated += count
        
        logger.info(f"Invalidated {total_invalidated} cache entries for project {project_id}")
        return total_invalidated


# Global service instance
_cached_project_service: Optional[CachedProjectService] = None


def get_cached_project_service() -> CachedProjectService:
    """Get global cached project service instance"""
    global _cached_project_service
    if _cached_project_service is None:
        _cached_project_service = CachedProjectService()
    return _cached_project_service