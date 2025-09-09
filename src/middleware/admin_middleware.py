"""
Admin Middleware

Role-based access control middleware for administrative endpoints.
"""

from functools import wraps
from typing import Optional
from fastapi import HTTPException, status, Depends
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.security import get_current_user
from src.models.user import User
from src.utils.logger import get_logger

logger = get_logger(__name__)


def require_admin(current_user: User = Depends(get_current_user)):
    """
    Dependency that requires admin privileges.
    """
    if not current_user.is_admin:
        logger.warning(f"Unauthorized admin access attempt by user {current_user.username} (ID: {current_user.id})")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    logger.info(f"Admin access granted to user {current_user.username} (ID: {current_user.id})")
    return current_user


def require_super_admin(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Dependency that requires super admin privileges (first admin user or explicitly granted).
    """
    if not current_user.is_admin:
        logger.warning(f"Unauthorized super admin access attempt by user {current_user.username} (ID: {current_user.id})")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin privileges required"
        )
    
    # Check if this is the first admin user (super admin)
    admin_count = db.query(User).filter(User.is_admin == True).count()
    first_admin = db.query(User).filter(User.is_admin == True).order_by(User.created_at).first()
    
    if admin_count == 1 or (first_admin and first_admin.id == current_user.id):
        logger.info(f"Super admin access granted to user {current_user.username} (ID: {current_user.id})")
        return current_user
    
    # Check if user has explicit super admin role
    if hasattr(current_user, 'role') and current_user.role == 'super_admin':
        logger.info(f"Super admin access granted to user {current_user.username} (ID: {current_user.id})")
        return current_user
    
    logger.warning(f"Unauthorized super admin access attempt by user {current_user.username} (ID: {current_user.id})")
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Super admin privileges required"
    )


def require_role(required_role: str):
    """
    Factory function to create role-based dependencies.
    """
    def role_checker(current_user: User = Depends(get_current_user)):
        if not current_user.is_admin and current_user.role != required_role:
            logger.warning(
                f"Unauthorized role access attempt by user {current_user.username} "
                f"(ID: {current_user.id}, Role: {current_user.role}, Required: {required_role})"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' or admin privileges required"
            )
        
        logger.info(f"Role access granted to user {current_user.username} (ID: {current_user.id}, Role: {current_user.role})")
        return current_user
    
    return role_checker


class AuditLogger:
    """
    Utility class for logging admin actions for audit purposes.
    """
    
    @staticmethod
    def log_admin_action(
        admin_user: User,
        action: str,
        target_type: str,
        target_id: Optional[int] = None,
        details: Optional[dict] = None,
        db: Optional[Session] = None
    ):
        """
        Log administrative actions for audit trail.
        """
        log_data = {
            "admin_id": admin_user.id,
            "admin_username": admin_user.username,
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "details": details or {},
            "timestamp": None
        }
        
        from datetime import datetime
        log_data["timestamp"] = datetime.utcnow().isoformat()
        
        logger.info(f"Admin action logged: {log_data}")
        
        # If database session is provided, store in audit log table
        if db:
            try:
                from src.models.audit_log import AuditLog
                audit_entry = AuditLog(
                    admin_id=admin_user.id,
                    action=action,
                    target_type=target_type,
                    target_id=target_id,
                    details=details or {},
                    timestamp=datetime.utcnow()
                )
                db.add(audit_entry)
                db.commit()
            except Exception as e:
                logger.error(f"Failed to store audit log in database: {str(e)}")
