"""
Admin Helper Utilities

Utility functions to assist with administrative tasks.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, text

from src.models.user import User
from src.models.project import Project
from src.models.text import Text
from src.models.annotation import Annotation
from src.models.label import Label
from src.models.audit_log import AuditLog, SystemLog, SecurityEvent


class AdminStatsCalculator:
    """Helper class for calculating administrative statistics."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_user_statistics(self, user_id: int) -> Dict[str, Any]:
        """Get comprehensive statistics for a specific user."""
        
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return {}
        
        # Basic counts
        project_count = self.db.query(Project).filter(Project.owner_id == user_id).count()
        annotation_count = self.db.query(Annotation).filter(Annotation.annotator_id == user_id).count()
        
        # Recent activity (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_annotations = self.db.query(Annotation).filter(
            Annotation.annotator_id == user_id,
            Annotation.created_at >= thirty_days_ago
        ).count()
        
        # Activity timeline
        daily_activity = self.db.query(
            func.date(Annotation.created_at).label('date'),
            func.count(Annotation.id).label('count')
        ).filter(
            Annotation.annotator_id == user_id,
            Annotation.created_at >= thirty_days_ago
        ).group_by(func.date(Annotation.created_at)).all()
        
        # Project participation
        project_participation = self.db.query(
            Project.name,
            func.count(Annotation.id).label('annotation_count')
        ).join(Text).join(Annotation).filter(
            Annotation.annotator_id == user_id
        ).group_by(Project.name).order_by(desc('annotation_count')).limit(10).all()
        
        return {
            "user_info": user.to_dict(),
            "statistics": {
                "projects_owned": project_count,
                "total_annotations": annotation_count,
                "recent_annotations_30d": recent_annotations,
                "avg_annotations_per_day": recent_annotations / 30 if recent_annotations > 0 else 0
            },
            "activity_timeline": [
                {"date": str(date), "count": count}
                for date, count in daily_activity
            ],
            "project_participation": [
                {"project_name": name, "annotation_count": count}
                for name, count in project_participation
            ]
        }
    
    def get_project_health_score(self, project_id: int) -> Dict[str, Any]:
        """Calculate a health score for a project based on various metrics."""
        
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return {}
        
        # Get basic counts
        text_count = self.db.query(Text).filter(Text.project_id == project_id).count()
        annotation_count = self.db.query(Annotation).join(Text).filter(
            Text.project_id == project_id
        ).count()
        annotator_count = self.db.query(Annotation.annotator_id).join(Text).filter(
            Text.project_id == project_id
        ).distinct().count()
        
        # Calculate metrics
        metrics = {
            "text_count": text_count,
            "annotation_count": annotation_count,
            "annotator_count": annotator_count,
            "avg_annotations_per_text": annotation_count / text_count if text_count > 0 else 0,
            "avg_annotations_per_annotator": annotation_count / annotator_count if annotator_count > 0 else 0
        }
        
        # Calculate health score (0-100)
        health_score = 0
        
        # Text coverage (max 25 points)
        if text_count > 0:
            texts_with_annotations = self.db.query(Text.id).join(Annotation).filter(
                Text.project_id == project_id
            ).distinct().count()
            coverage = texts_with_annotations / text_count
            health_score += coverage * 25
        
        # Annotation density (max 25 points)
        if metrics["avg_annotations_per_text"] > 0:
            # Normalize to reasonable range (1-10 annotations per text is good)
            density_score = min(metrics["avg_annotations_per_text"] / 10, 1) * 25
            health_score += density_score
        
        # Annotator participation (max 25 points)
        if annotator_count > 0:
            # More annotators is generally better for reliability
            participation_score = min(annotator_count / 5, 1) * 25
            health_score += participation_score
        
        # Recent activity (max 25 points)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        recent_annotations = self.db.query(Annotation).join(Text).filter(
            Text.project_id == project_id,
            Annotation.created_at >= seven_days_ago
        ).count()
        
        if recent_annotations > 0:
            activity_score = min(recent_annotations / 50, 1) * 25  # 50+ annotations in week = full score
            health_score += activity_score
        
        # Determine health level
        if health_score >= 80:
            health_level = "Excellent"
        elif health_score >= 60:
            health_level = "Good"
        elif health_score >= 40:
            health_level = "Fair"
        elif health_score >= 20:
            health_level = "Poor"
        else:
            health_level = "Critical"
        
        return {
            "project_info": project.to_dict(),
            "metrics": metrics,
            "health_score": round(health_score, 2),
            "health_level": health_level,
            "recommendations": self._get_project_recommendations(metrics, health_score)
        }
    
    def _get_project_recommendations(self, metrics: Dict[str, Any], health_score: float) -> List[str]:
        """Generate recommendations for improving project health."""
        
        recommendations = []
        
        if metrics["text_count"] == 0:
            recommendations.append("Add texts to the project to begin annotation work")
        
        if metrics["annotation_count"] == 0:
            recommendations.append("Start annotation work by assigning texts to annotators")
        
        if metrics["annotator_count"] < 2:
            recommendations.append("Consider adding more annotators for better inter-annotator agreement")
        
        if metrics["avg_annotations_per_text"] < 1:
            recommendations.append("Increase annotation coverage - many texts remain unannotated")
        
        if health_score < 40:
            recommendations.append("Project requires immediate attention to improve annotation quality")
        
        return recommendations
    
    def get_system_anomalies(self) -> Dict[str, Any]:
        """Detect potential system anomalies and issues."""
        
        anomalies = {
            "inactive_users": [],
            "stalled_projects": [],
            "suspicious_activity": [],
            "data_integrity_issues": []
        }
        
        # Inactive users (registered but never logged in)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        inactive_users = self.db.query(User).filter(
            User.created_at < thirty_days_ago,
            User.last_login.is_(None),
            User.is_active == True
        ).all()
        
        anomalies["inactive_users"] = [
            {"id": user.id, "username": user.username, "created_at": user.created_at.isoformat()}
            for user in inactive_users
        ]
        
        # Stalled projects (no activity in 30 days)
        stalled_projects = self.db.query(Project).filter(
            Project.is_active == True,
            Project.updated_at < thirty_days_ago
        ).all()
        
        # Check if projects actually have no recent annotations
        for project in stalled_projects:
            recent_annotations = self.db.query(Annotation).join(Text).filter(
                Text.project_id == project.id,
                Annotation.created_at >= thirty_days_ago
            ).count()
            
            if recent_annotations == 0:
                anomalies["stalled_projects"].append({
                    "id": project.id,
                    "name": project.name,
                    "last_updated": project.updated_at.isoformat(),
                    "owner_username": project.owner.username if project.owner else None
                })
        
        # Data integrity issues
        # Orphaned annotations (annotations without texts)
        orphaned_annotations = self.db.execute(text(
            "SELECT COUNT(*) FROM annotations a LEFT JOIN texts t ON a.text_id = t.id WHERE t.id IS NULL"
        )).scalar()
        
        if orphaned_annotations > 0:
            anomalies["data_integrity_issues"].append({
                "type": "orphaned_annotations",
                "count": orphaned_annotations,
                "description": "Annotations exist without corresponding texts"
            })
        
        # Orphaned texts (texts without projects)
        orphaned_texts = self.db.execute(text(
            "SELECT COUNT(*) FROM texts t LEFT JOIN projects p ON t.project_id = p.id WHERE p.id IS NULL"
        )).scalar()
        
        if orphaned_texts > 0:
            anomalies["data_integrity_issues"].append({
                "type": "orphaned_texts",
                "count": orphaned_texts,
                "description": "Texts exist without corresponding projects"
            })
        
        return anomalies


class SecurityAnalyzer:
    """Helper class for security analysis and monitoring."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def analyze_login_patterns(self, days: int = 30) -> Dict[str, Any]:
        """Analyze user login patterns for security insights."""
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Users with multiple recent logins
        active_users = self.db.query(
            User.username,
            func.count(AuditLog.id).label('login_count')
        ).join(AuditLog, User.id == AuditLog.admin_id).filter(
            AuditLog.action == 'LOGIN',
            AuditLog.timestamp >= start_date
        ).group_by(User.username).order_by(desc('login_count')).limit(20).all()
        
        # Failed login attempts (if tracked in security events)
        failed_logins = self.db.query(SecurityEvent).filter(
            SecurityEvent.event_type == 'FAILED_LOGIN',
            SecurityEvent.timestamp >= start_date
        ).count()
        
        # Suspicious login patterns (multiple IPs per user)
        # This would require IP address tracking in audit logs
        
        return {
            "period_days": days,
            "most_active_users": [
                {"username": username, "login_count": count}
                for username, count in active_users
            ],
            "failed_login_attempts": failed_logins,
            "analysis_timestamp": datetime.utcnow().isoformat()
        }
    
    def generate_security_report(self) -> Dict[str, Any]:
        """Generate a comprehensive security report."""
        
        # Count unresolved security events by severity
        security_events = self.db.query(
            SecurityEvent.severity,
            func.count(SecurityEvent.id).label('count')
        ).filter(SecurityEvent.resolved == False).group_by(
            SecurityEvent.severity
        ).all()
        
        # Recent admin actions
        recent_admin_actions = self.db.query(AuditLog).filter(
            AuditLog.timestamp >= datetime.utcnow() - timedelta(days=7)
        ).order_by(desc(AuditLog.timestamp)).limit(50).all()
        
        # Admin user statistics
        admin_count = self.db.query(User).filter(User.is_admin == True).count()
        active_admin_count = self.db.query(User).filter(
            User.is_admin == True,
            User.is_active == True
        ).count()
        
        return {
            "summary": {
                "total_admins": admin_count,
                "active_admins": active_admin_count,
                "unresolved_security_events": sum(count for _, count in security_events)
            },
            "unresolved_events_by_severity": {
                severity: count for severity, count in security_events
            },
            "recent_admin_actions": [
                {
                    "action": log.action,
                    "admin_username": log.admin.username if log.admin else None,
                    "target_type": log.target_type,
                    "timestamp": log.timestamp.isoformat()
                }
                for log in recent_admin_actions
            ],
            "recommendations": self._generate_security_recommendations(
                admin_count, len(security_events)
            )
        }
    
    def _generate_security_recommendations(self, admin_count: int, unresolved_events: int) -> List[str]:
        """Generate security recommendations based on analysis."""
        
        recommendations = []
        
        if admin_count < 2:
            recommendations.append("Consider creating a backup admin account")
        
        if admin_count > 10:
            recommendations.append("Review admin user list - many admin accounts may pose security risk")
        
        if unresolved_events > 0:
            recommendations.append(f"Resolve {unresolved_events} pending security events")
        
        if unresolved_events > 10:
            recommendations.append("High number of unresolved security events - immediate attention required")
        
        return recommendations


def cleanup_old_records(db: Session, max_age_days: int = 90, dry_run: bool = True) -> Dict[str, Any]:
    """Clean up old system records."""
    
    cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)
    
    cleanup_stats = {
        "cutoff_date": cutoff_date.isoformat(),
        "dry_run": dry_run,
        "records_to_cleanup": {}
    }
    
    # Old audit logs
    old_audit_logs = db.query(AuditLog).filter(AuditLog.timestamp < cutoff_date)
    audit_count = old_audit_logs.count()
    cleanup_stats["records_to_cleanup"]["audit_logs"] = audit_count
    
    if not dry_run and audit_count > 0:
        old_audit_logs.delete(synchronize_session=False)
    
    # Old system logs
    old_system_logs = db.query(SystemLog).filter(SystemLog.timestamp < cutoff_date)
    system_count = old_system_logs.count()
    cleanup_stats["records_to_cleanup"]["system_logs"] = system_count
    
    if not dry_run and system_count > 0:
        old_system_logs.delete(synchronize_session=False)
    
    # Resolved security events older than cutoff
    old_security_events = db.query(SecurityEvent).filter(
        SecurityEvent.resolved == True,
        SecurityEvent.resolved_at < cutoff_date
    )
    security_count = old_security_events.count()
    cleanup_stats["records_to_cleanup"]["resolved_security_events"] = security_count
    
    if not dry_run and security_count > 0:
        old_security_events.delete(synchronize_session=False)
    
    if not dry_run:
        db.commit()
        cleanup_stats["status"] = "completed"
    else:
        cleanup_stats["status"] = "dry_run"
    
    cleanup_stats["total_records"] = audit_count + system_count + security_count
    
    return cleanup_stats