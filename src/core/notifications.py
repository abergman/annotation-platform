"""
Real-time Notification System

Comprehensive notification system for conflict resolution events.
Supports multiple delivery methods including in-app, email, and webhooks.
Integrates with WebSocket for real-time updates.
"""

from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from enum import Enum as PyEnum
import asyncio
import logging
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from src.models.conflict import (
    AnnotationConflict, ConflictNotification, ConflictSettings,
    ConflictStatus, ConflictType
)
from src.models.user import User
from src.models.project import Project

logger = logging.getLogger(__name__)


class NotificationType(PyEnum):
    """Types of conflict-related notifications."""
    CONFLICT_DETECTED = "conflict_detected"
    CONFLICT_ASSIGNED = "conflict_assigned"
    RESOLUTION_REQUESTED = "resolution_requested"
    VOTE_REQUESTED = "vote_requested"
    CONFLICT_RESOLVED = "conflict_resolved"
    CONFLICT_ESCALATED = "conflict_escalated"
    RESOLUTION_FAILED = "resolution_failed"
    DEADLINE_APPROACHING = "deadline_approaching"
    DEADLINE_MISSED = "deadline_missed"
    PARTICIPANT_JOINED = "participant_joined"
    VOTE_SUBMITTED = "vote_submitted"
    EXPERT_REVIEW_NEEDED = "expert_review_needed"


class DeliveryMethod(PyEnum):
    """Available notification delivery methods."""
    IN_APP = "in_app"
    EMAIL = "email"
    WEBHOOK = "webhook"
    WEBSOCKET = "websocket"
    SMS = "sms"


class NotificationPriority(PyEnum):
    """Notification priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class NotificationContext:
    """Context information for notification generation."""
    conflict: AnnotationConflict
    user: User
    event_type: NotificationType
    priority: NotificationPriority
    metadata: Dict[str, Any] = field(default_factory=dict)
    delivery_methods: Set[DeliveryMethod] = field(default_factory=set)
    scheduled_for: Optional[datetime] = None
    expires_at: Optional[datetime] = None


@dataclass
class NotificationPayload:
    """Structured notification payload."""
    recipient_id: int
    notification_type: NotificationType
    title: str
    message: str
    priority: NotificationPriority
    delivery_methods: Set[DeliveryMethod]
    metadata: Dict[str, Any]
    scheduled_for: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    context_url: Optional[str] = None


class NotificationHandler(ABC):
    """Abstract base class for notification handlers."""
    
    @abstractmethod
    async def can_handle(self, delivery_method: DeliveryMethod) -> bool:
        """Check if this handler can process the given delivery method."""
        pass
    
    @abstractmethod
    async def send_notification(self, payload: NotificationPayload) -> bool:
        """Send notification using this handler."""
        pass


class InAppNotificationHandler(NotificationHandler):
    """Handler for in-app notifications."""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    async def can_handle(self, delivery_method: DeliveryMethod) -> bool:
        return delivery_method == DeliveryMethod.IN_APP
    
    async def send_notification(self, payload: NotificationPayload) -> bool:
        """Store notification in database for in-app display."""
        try:
            notification = ConflictNotification(
                conflict_id=payload.metadata.get('conflict_id'),
                recipient_id=payload.recipient_id,
                notification_type=payload.notification_type.value,
                title=payload.title,
                message=payload.message,
                delivery_method=DeliveryMethod.IN_APP.value,
                priority=payload.priority.value,
                scheduled_for=payload.scheduled_for,
                expires_at=payload.expires_at,
                notification_data=payload.metadata,
                is_delivered=True,
                delivered_at=datetime.utcnow()
            )
            
            self.db.add(notification)
            self.db.commit()
            
            logger.info(f"In-app notification created for user {payload.recipient_id}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to create in-app notification: {e}")
            self.db.rollback()
            return False


class WebSocketNotificationHandler(NotificationHandler):
    """Handler for real-time WebSocket notifications."""
    
    def __init__(self):
        self.active_connections: Dict[int, Set[Any]] = {}  # user_id -> set of websocket connections
    
    async def can_handle(self, delivery_method: DeliveryMethod) -> bool:
        return delivery_method == DeliveryMethod.WEBSOCKET
    
    async def send_notification(self, payload: NotificationPayload) -> bool:
        """Send real-time notification via WebSocket."""
        try:
            user_connections = self.active_connections.get(payload.recipient_id, set())
            
            if not user_connections:
                logger.info(f"No active WebSocket connections for user {payload.recipient_id}")
                return False
            
            websocket_message = {
                "type": "conflict_notification",
                "notification_type": payload.notification_type.value,
                "title": payload.title,
                "message": payload.message,
                "priority": payload.priority.value,
                "metadata": payload.metadata,
                "timestamp": datetime.utcnow().isoformat(),
                "context_url": payload.context_url
            }
            
            # Send to all active connections for the user
            successful_sends = 0
            dead_connections = set()
            
            for connection in user_connections:
                try:
                    await connection.send_json(websocket_message)
                    successful_sends += 1
                except Exception as e:
                    logger.warning(f"WebSocket connection failed: {e}")
                    dead_connections.add(connection)
            
            # Clean up dead connections
            for dead_conn in dead_connections:
                user_connections.discard(dead_conn)
            
            logger.info(f"WebSocket notification sent to {successful_sends} connections for user {payload.recipient_id}")
            return successful_sends > 0
        
        except Exception as e:
            logger.error(f"Failed to send WebSocket notification: {e}")
            return False
    
    def add_connection(self, user_id: int, websocket_connection):
        """Add a WebSocket connection for a user."""
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket_connection)
    
    def remove_connection(self, user_id: int, websocket_connection):
        """Remove a WebSocket connection for a user."""
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket_connection)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]


class EmailNotificationHandler(NotificationHandler):
    """Handler for email notifications."""
    
    def __init__(self, smtp_config: Dict[str, Any]):
        self.smtp_config = smtp_config
        # TODO: Initialize email client (SMTP, SendGrid, etc.)
    
    async def can_handle(self, delivery_method: DeliveryMethod) -> bool:
        return delivery_method == DeliveryMethod.EMAIL
    
    async def send_notification(self, payload: NotificationPayload) -> bool:
        """Send email notification."""
        try:
            # TODO: Implement actual email sending
            # This is a placeholder implementation
            
            logger.info(f"Email notification would be sent to user {payload.recipient_id}")
            logger.info(f"Subject: {payload.title}")
            logger.info(f"Message: {payload.message}")
            
            # Simulate email sending
            await asyncio.sleep(0.1)
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return False


class WebhookNotificationHandler(NotificationHandler):
    """Handler for webhook notifications."""
    
    def __init__(self):
        # TODO: Initialize HTTP client for webhook calls
        pass
    
    async def can_handle(self, delivery_method: DeliveryMethod) -> bool:
        return delivery_method == DeliveryMethod.WEBHOOK
    
    async def send_notification(self, payload: NotificationPayload) -> bool:
        """Send webhook notification."""
        try:
            # TODO: Implement actual webhook sending
            # This would make HTTP POST requests to configured endpoints
            
            webhook_payload = {
                "notification_type": payload.notification_type.value,
                "recipient_id": payload.recipient_id,
                "title": payload.title,
                "message": payload.message,
                "priority": payload.priority.value,
                "metadata": payload.metadata,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Webhook notification would be sent for user {payload.recipient_id}")
            logger.info(f"Payload: {webhook_payload}")
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to send webhook notification: {e}")
            return False


class NotificationTemplateEngine:
    """Engine for generating notification content based on templates."""
    
    def __init__(self):
        self.templates = {
            NotificationType.CONFLICT_DETECTED: {
                "title": "New annotation conflict detected",
                "message": "A conflict has been detected between annotations in project '{project_name}'. "
                          "Conflict type: {conflict_type}. Severity: {severity_level}."
            },
            NotificationType.CONFLICT_ASSIGNED: {
                "title": "Conflict assigned for resolution",
                "message": "You have been assigned to resolve a {conflict_type} conflict in project '{project_name}'. "
                          "Please review and provide a resolution."
            },
            NotificationType.VOTE_REQUESTED: {
                "title": "Vote requested for conflict resolution",
                "message": "Your vote is requested to resolve a {conflict_type} conflict in project '{project_name}'. "
                          "Please review the conflicting annotations and cast your vote."
            },
            NotificationType.CONFLICT_RESOLVED: {
                "title": "Conflict resolved",
                "message": "The {conflict_type} conflict in project '{project_name}' has been resolved "
                          "using {resolution_strategy}. Outcome: {outcome}."
            },
            NotificationType.CONFLICT_ESCALATED: {
                "title": "Conflict escalated to expert review",
                "message": "The {conflict_type} conflict in project '{project_name}' has been escalated "
                          "to expert review due to resolution difficulties."
            },
            NotificationType.DEADLINE_APPROACHING: {
                "title": "Resolution deadline approaching",
                "message": "The resolution deadline for a {conflict_type} conflict in project '{project_name}' "
                          "is approaching. Please complete resolution within {time_remaining}."
            },
            NotificationType.DEADLINE_MISSED: {
                "title": "Resolution deadline missed",
                "message": "The resolution deadline for a {conflict_type} conflict in project '{project_name}' "
                          "has been missed. The conflict will be escalated."
            },
            NotificationType.EXPERT_REVIEW_NEEDED: {
                "title": "Expert review required",
                "message": "Your expertise is needed to review a complex {conflict_type} conflict "
                          "in project '{project_name}'. This conflict requires expert judgment."
            }
        }
    
    def generate_notification(self, context: NotificationContext) -> NotificationPayload:
        """Generate notification content from context."""
        template = self.templates.get(context.event_type)
        if not template:
            # Fallback template
            template = {
                "title": f"Conflict notification: {context.event_type.value}",
                "message": f"A conflict event occurred in project ID {context.conflict.project_id}"
            }
        
        # Prepare template variables
        template_vars = {
            "conflict_type": context.conflict.conflict_type.value,
            "severity_level": context.conflict.severity_level,
            "project_name": context.conflict.project.name if context.conflict.project else "Unknown",
            "user_name": context.user.username,
            **context.metadata
        }
        
        # Format title and message
        title = template["title"].format(**template_vars)
        message = template["message"].format(**template_vars)
        
        # Generate context URL
        context_url = f"/conflicts/{context.conflict.id}"
        
        return NotificationPayload(
            recipient_id=context.user.id,
            notification_type=context.event_type,
            title=title,
            message=message,
            priority=context.priority,
            delivery_methods=context.delivery_methods,
            metadata={
                **context.metadata,
                "conflict_id": context.conflict.id,
                "project_id": context.conflict.project_id
            },
            scheduled_for=context.scheduled_for,
            expires_at=context.expires_at,
            context_url=context_url
        )


class NotificationService:
    """Main notification service for conflict resolution events."""
    
    def __init__(self, db_session: Session, websocket_handler: Optional[WebSocketNotificationHandler] = None):
        self.db = db_session
        self.template_engine = NotificationTemplateEngine()
        
        # Initialize handlers
        self.handlers: List[NotificationHandler] = [
            InAppNotificationHandler(db_session)
        ]
        
        if websocket_handler:
            self.handlers.append(websocket_handler)
        
        # TODO: Initialize other handlers based on configuration
        # self.handlers.extend([
        #     EmailNotificationHandler(email_config),
        #     WebhookNotificationHandler()
        # ])
    
    async def notify_conflict_detected(
        self, 
        conflict: AnnotationConflict, 
        recipients: Optional[List[User]] = None
    ):
        """Send notifications when a conflict is detected."""
        settings = self._get_project_settings(conflict.project_id)
        
        if not settings.notify_on_detection:
            return
        
        # Determine recipients
        if not recipients:
            recipients = self._get_conflict_participants(conflict)
        
        # Add project admin if configured
        if settings.notify_project_admin and conflict.project.owner:
            recipients.append(conflict.project.owner)
        
        # Create notification contexts
        for recipient in recipients:
            context = NotificationContext(
                conflict=conflict,
                user=recipient,
                event_type=NotificationType.CONFLICT_DETECTED,
                priority=self._determine_priority(conflict),
                delivery_methods=self._get_user_delivery_methods(recipient, settings),
                expires_at=datetime.utcnow() + timedelta(days=7)
            )
            
            await self._send_notification(context)
    
    async def notify_conflict_assigned(self, conflict: AnnotationConflict, assignee: User):
        """Send notification when conflict is assigned."""
        context = NotificationContext(
            conflict=conflict,
            user=assignee,
            event_type=NotificationType.CONFLICT_ASSIGNED,
            priority=NotificationPriority.HIGH,
            delivery_methods={DeliveryMethod.IN_APP, DeliveryMethod.WEBSOCKET}
        )
        
        await self._send_notification(context)
    
    async def notify_vote_requested(self, conflict: AnnotationConflict, voters: List[User]):
        """Send notifications requesting votes."""
        for voter in voters:
            context = NotificationContext(
                conflict=conflict,
                user=voter,
                event_type=NotificationType.VOTE_REQUESTED,
                priority=NotificationPriority.NORMAL,
                delivery_methods={DeliveryMethod.IN_APP, DeliveryMethod.WEBSOCKET},
                expires_at=datetime.utcnow() + timedelta(days=3)
            )
            
            await self._send_notification(context)
    
    async def notify_conflict_resolved(
        self, 
        conflict: AnnotationConflict, 
        resolution_strategy: str,
        outcome: str
    ):
        """Send notifications when conflict is resolved."""
        participants = self._get_conflict_participants(conflict)
        
        for participant in participants:
            context = NotificationContext(
                conflict=conflict,
                user=participant,
                event_type=NotificationType.CONFLICT_RESOLVED,
                priority=NotificationPriority.NORMAL,
                delivery_methods={DeliveryMethod.IN_APP, DeliveryMethod.WEBSOCKET},
                metadata={
                    "resolution_strategy": resolution_strategy,
                    "outcome": outcome
                }
            )
            
            await self._send_notification(context)
    
    async def notify_conflict_escalated(self, conflict: AnnotationConflict, experts: List[User]):
        """Send notifications when conflict is escalated."""
        for expert in experts:
            context = NotificationContext(
                conflict=conflict,
                user=expert,
                event_type=NotificationType.EXPERT_REVIEW_NEEDED,
                priority=NotificationPriority.HIGH,
                delivery_methods={DeliveryMethod.IN_APP, DeliveryMethod.WEBSOCKET, DeliveryMethod.EMAIL}
            )
            
            await self._send_notification(context)
    
    async def notify_deadline_approaching(self, conflict: AnnotationConflict, time_remaining: str):
        """Send notifications when resolution deadline is approaching."""
        if conflict.assigned_resolver:
            context = NotificationContext(
                conflict=conflict,
                user=conflict.assigned_resolver,
                event_type=NotificationType.DEADLINE_APPROACHING,
                priority=NotificationPriority.HIGH,
                delivery_methods={DeliveryMethod.IN_APP, DeliveryMethod.WEBSOCKET},
                metadata={"time_remaining": time_remaining}
            )
            
            await self._send_notification(context)
    
    async def _send_notification(self, context: NotificationContext):
        """Send notification using appropriate handlers."""
        try:
            # Generate notification payload
            payload = self.template_engine.generate_notification(context)
            
            # Send using each delivery method
            for delivery_method in payload.delivery_methods:
                for handler in self.handlers:
                    if await handler.can_handle(delivery_method):
                        success = await handler.send_notification(payload)
                        if success:
                            logger.debug(f"Notification sent via {delivery_method.value} to user {payload.recipient_id}")
                        else:
                            logger.warning(f"Failed to send notification via {delivery_method.value} to user {payload.recipient_id}")
                        break
        
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
    
    def _get_conflict_participants(self, conflict: AnnotationConflict) -> List[User]:
        """Get users who should be notified about the conflict."""
        participants = set()
        
        # Add annotators
        if conflict.annotation_a and conflict.annotation_a.annotator:
            participants.add(conflict.annotation_a.annotator)
        
        if conflict.annotation_b and conflict.annotation_b.annotator:
            participants.add(conflict.annotation_b.annotator)
        
        # Add assigned resolver
        if conflict.assigned_resolver:
            participants.add(conflict.assigned_resolver)
        
        # Add participants from database
        for participant in conflict.participants:
            if participant.user:
                participants.add(participant.user)
        
        return list(participants)
    
    def _determine_priority(self, conflict: AnnotationConflict) -> NotificationPriority:
        """Determine notification priority based on conflict characteristics."""
        if conflict.severity_level == "critical":
            return NotificationPriority.URGENT
        elif conflict.severity_level == "high":
            return NotificationPriority.HIGH
        elif conflict.severity_level == "medium":
            return NotificationPriority.NORMAL
        else:
            return NotificationPriority.LOW
    
    def _get_user_delivery_methods(
        self, 
        user: User, 
        settings: ConflictSettings
    ) -> Set[DeliveryMethod]:
        """Get preferred delivery methods for a user."""
        # Default delivery methods
        methods = {DeliveryMethod.IN_APP}
        
        # Add WebSocket for real-time updates
        methods.add(DeliveryMethod.WEBSOCKET)
        
        # TODO: Add user-specific preferences
        # This could be stored in user profile or separate preferences table
        
        return methods
    
    def _get_project_settings(self, project_id: int) -> ConflictSettings:
        """Get conflict settings for a project."""
        settings = (
            self.db.query(ConflictSettings)
            .filter_by(project_id=project_id)
            .first()
        )
        
        if not settings:
            settings = ConflictSettings(project_id=project_id)
            self.db.add(settings)
            self.db.commit()
        
        return settings


class NotificationScheduler:
    """Scheduler for delayed and recurring notifications."""
    
    def __init__(self, notification_service: NotificationService):
        self.notification_service = notification_service
        self.scheduled_tasks: Dict[str, asyncio.Task] = {}
    
    async def schedule_deadline_reminders(self, conflict: AnnotationConflict):
        """Schedule deadline reminder notifications."""
        if not conflict.resolution_deadline:
            return
        
        now = datetime.utcnow()
        deadline = conflict.resolution_deadline
        
        # Schedule reminder 24 hours before deadline
        reminder_time = deadline - timedelta(hours=24)
        if reminder_time > now:
            task_id = f"deadline_reminder_{conflict.id}_24h"
            delay = (reminder_time - now).total_seconds()
            
            task = asyncio.create_task(
                self._delayed_notification(
                    delay,
                    conflict,
                    NotificationType.DEADLINE_APPROACHING,
                    {"time_remaining": "24 hours"}
                )
            )
            
            self.scheduled_tasks[task_id] = task
        
        # Schedule reminder 2 hours before deadline
        final_reminder_time = deadline - timedelta(hours=2)
        if final_reminder_time > now:
            task_id = f"deadline_reminder_{conflict.id}_2h"
            delay = (final_reminder_time - now).total_seconds()
            
            task = asyncio.create_task(
                self._delayed_notification(
                    delay,
                    conflict,
                    NotificationType.DEADLINE_APPROACHING,
                    {"time_remaining": "2 hours"}
                )
            )
            
            self.scheduled_tasks[task_id] = task
        
        # Schedule deadline missed notification
        if deadline > now:
            task_id = f"deadline_missed_{conflict.id}"
            delay = (deadline - now).total_seconds() + 300  # 5 minutes after deadline
            
            task = asyncio.create_task(
                self._delayed_notification(
                    delay,
                    conflict,
                    NotificationType.DEADLINE_MISSED,
                    {}
                )
            )
            
            self.scheduled_tasks[task_id] = task
    
    async def _delayed_notification(
        self,
        delay_seconds: float,
        conflict: AnnotationConflict,
        notification_type: NotificationType,
        metadata: Dict[str, Any]
    ):
        """Send a notification after a delay."""
        try:
            await asyncio.sleep(delay_seconds)
            
            if notification_type == NotificationType.DEADLINE_APPROACHING:
                await self.notification_service.notify_deadline_approaching(
                    conflict, metadata.get("time_remaining", "soon")
                )
            elif notification_type == NotificationType.DEADLINE_MISSED:
                # TODO: Implement deadline missed notification
                logger.warning(f"Deadline missed for conflict {conflict.id}")
        
        except asyncio.CancelledError:
            logger.info(f"Scheduled notification cancelled for conflict {conflict.id}")
        except Exception as e:
            logger.error(f"Error in delayed notification: {e}")
    
    def cancel_scheduled_notifications(self, conflict_id: int):
        """Cancel all scheduled notifications for a conflict."""
        tasks_to_cancel = [
            task_id for task_id in self.scheduled_tasks.keys()
            if f"_{conflict_id}_" in task_id
        ]
        
        for task_id in tasks_to_cancel:
            task = self.scheduled_tasks.pop(task_id, None)
            if task and not task.done():
                task.cancel()


# Convenience functions

def create_notification_service(
    db_session: Session,
    websocket_handler: Optional[WebSocketNotificationHandler] = None
) -> NotificationService:
    """Create a configured notification service."""
    return NotificationService(db_session, websocket_handler)


def create_websocket_handler() -> WebSocketNotificationHandler:
    """Create a WebSocket notification handler."""
    return WebSocketNotificationHandler()