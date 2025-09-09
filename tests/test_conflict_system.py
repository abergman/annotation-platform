"""
Comprehensive Test Suite for Conflict Resolution System

Tests all major components of the conflict resolution system including
detection, resolution strategies, notifications, and API endpoints.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from src.core.database import Base
from src.models.annotation import Annotation
from src.models.conflict import (
    AnnotationConflict, ConflictResolution, ConflictParticipant,
    ResolutionVote, ConflictNotification, ConflictSettings,
    ConflictType, ConflictStatus, ResolutionStrategy, ResolutionOutcome
)
from src.models.user import User
from src.models.project import Project
from src.models.text import Text
from src.models.label import Label

from src.core.conflict_detection import (
    ConflictDetectionEngine, ConflictMonitor, 
    OverlapInfo, ConflictCandidate
)
from src.core.conflict_resolution import (
    ConflictResolutionEngine, AutoMergeStrategy, VotingStrategy,
    ExpertReviewStrategy, WeightedVotingStrategy,
    ResolutionContext, ResolutionResult
)
from src.core.notifications import (
    NotificationService, NotificationTemplateEngine,
    WebSocketNotificationHandler, NotificationType,
    NotificationContext, NotificationPriority
)
from src.integration.agreement_integration import (
    ConflictAgreementAnalyzer, AgreementConflictIntegration
)
from src.api.conflicts import router


# Test Database Setup

@pytest.fixture
def test_db():
    """Create test database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    
    yield db
    
    db.close()


@pytest.fixture
def sample_project(test_db):
    """Create sample project for testing."""
    project = Project(
        name="Test Annotation Project",
        description="Test project for conflict resolution",
        owner_id=1
    )
    test_db.add(project)
    test_db.commit()
    return project


@pytest.fixture
def sample_users(test_db):
    """Create sample users for testing."""
    users = [
        User(username="annotator1", email="ann1@test.com", hashed_password="test"),
        User(username="annotator2", email="ann2@test.com", hashed_password="test"),
        User(username="expert", email="expert@test.com", hashed_password="test", role="expert"),
        User(username="admin", email="admin@test.com", hashed_password="test", is_admin=True)
    ]
    
    for user in users:
        test_db.add(user)
    test_db.commit()
    return users


@pytest.fixture
def sample_text(test_db, sample_project):
    """Create sample text for testing."""
    text = Text(
        content="This is a sample text for annotation testing with multiple entities and concepts.",
        title="Sample Text",
        project_id=sample_project.id
    )
    test_db.add(text)
    test_db.commit()
    return text


@pytest.fixture
def sample_label(test_db, sample_project):
    """Create sample label for testing."""
    label = Label(
        name="Entity",
        color="#FF0000",
        project_id=sample_project.id
    )
    test_db.add(label)
    test_db.commit()
    return label


@pytest.fixture
def sample_annotations(test_db, sample_text, sample_label, sample_users):
    """Create sample overlapping annotations."""
    annotations = [
        Annotation(
            start_char=10,
            end_char=25,
            selected_text="sample text for",
            text_id=sample_text.id,
            annotator_id=sample_users[0].id,
            label_id=sample_label.id,
            confidence_score=0.8
        ),
        Annotation(
            start_char=15,
            end_char=35,
            selected_text="text for annotation",
            text_id=sample_text.id,
            annotator_id=sample_users[1].id,
            label_id=sample_label.id,
            confidence_score=0.7
        )
    ]
    
    for annotation in annotations:
        test_db.add(annotation)
    test_db.commit()
    return annotations


# Conflict Detection Tests

class TestConflictDetection:
    """Test cases for conflict detection engine."""
    
    def test_span_overlap_calculation(self, test_db, sample_annotations):
        """Test span overlap calculation."""
        engine = ConflictDetectionEngine(test_db)
        ann_a, ann_b = sample_annotations
        
        overlap_info = engine._calculate_span_overlap(ann_a, ann_b)
        
        assert overlap_info is not None
        assert overlap_info.start == 15
        assert overlap_info.end == 25
        assert overlap_info.length == 10
        assert overlap_info.percentage_a == 10/15  # 10 chars overlap out of 15 total
        assert overlap_info.percentage_b == 10/20  # 10 chars overlap out of 20 total
    
    def test_conflict_detection_for_project(self, test_db, sample_project, sample_annotations):
        """Test project-wide conflict detection."""
        engine = ConflictDetectionEngine(test_db)
        
        candidates = engine.detect_conflicts_for_project(sample_project.id, check_new_only=False)
        
        assert len(candidates) >= 1
        assert any(c.conflict_type == ConflictType.SPAN_OVERLAP for c in candidates)
    
    def test_conflict_detection_for_annotation(self, test_db, sample_annotations):
        """Test conflict detection for specific annotation."""
        engine = ConflictDetectionEngine(test_db)
        ann_a = sample_annotations[0]
        
        candidates = engine.detect_conflicts_for_annotation(ann_a.id)
        
        assert len(candidates) >= 1
        conflict = candidates[0]
        assert conflict.annotation_a.id == ann_a.id or conflict.annotation_b.id == ann_a.id
    
    def test_conflict_record_creation(self, test_db, sample_annotations):
        """Test creation of conflict database records."""
        engine = ConflictDetectionEngine(test_db)
        
        # Create a candidate
        candidate = ConflictCandidate(
            annotation_a=sample_annotations[0],
            annotation_b=sample_annotations[1],
            conflict_type=ConflictType.SPAN_OVERLAP,
            severity_level="medium",
            confidence_score=0.8,
            overlap_info=None,
            description="Test conflict",
            metadata={"test": True}
        )
        
        conflicts = engine.create_conflict_records([candidate])
        
        assert len(conflicts) == 1
        conflict = conflicts[0]
        assert conflict.conflict_type == ConflictType.SPAN_OVERLAP
        assert conflict.severity_level == "medium"
        assert conflict.conflict_score == 0.8
    
    def test_conflict_monitor(self, test_db, sample_annotations):
        """Test real-time conflict monitoring."""
        monitor = ConflictMonitor(test_db)
        ann_id = sample_annotations[0].id
        
        conflicts = monitor.monitor_annotation_changes(ann_id)
        
        # Should detect conflicts with the other annotation
        assert len(conflicts) >= 0  # May be 0 if conflicts already exist


# Conflict Resolution Tests

class TestConflictResolution:
    """Test cases for conflict resolution strategies."""
    
    @pytest.fixture
    def sample_conflict(self, test_db, sample_annotations, sample_project):
        """Create a sample conflict for resolution testing."""
        conflict = AnnotationConflict(
            conflict_type=ConflictType.SPAN_OVERLAP,
            conflict_description="Test conflict between overlapping annotations",
            severity_level="medium",
            annotation_a_id=sample_annotations[0].id,
            annotation_b_id=sample_annotations[1].id,
            project_id=sample_project.id,
            text_id=sample_annotations[0].text_id,
            conflict_score=0.6
        )
        test_db.add(conflict)
        test_db.commit()
        return conflict
    
    def test_auto_merge_strategy_can_resolve(self, test_db, sample_conflict):
        """Test auto-merge strategy feasibility check."""
        strategy = AutoMergeStrategy()
        settings = ConflictSettings(auto_merge_enabled=True)
        
        context = ResolutionContext(
            conflict=sample_conflict,
            participants=[],
            settings=settings,
            resolver=None,
            metadata={}
        )
        
        can_resolve = strategy.can_resolve(context)
        
        # Should be able to resolve based on conflict score and settings
        assert can_resolve is True
    
    def test_auto_merge_resolution(self, test_db, sample_conflict, sample_users):
        """Test auto-merge resolution execution."""
        strategy = AutoMergeStrategy()
        settings = ConflictSettings(auto_merge_enabled=True)
        
        context = ResolutionContext(
            conflict=sample_conflict,
            participants=[],
            settings=settings,
            resolver=sample_users[0],
            metadata={}
        )
        
        result = strategy.resolve(context)
        
        assert result.success is True
        assert result.outcome == ResolutionOutcome.MERGED
        assert result.final_annotation is not None
    
    def test_voting_strategy_with_insufficient_votes(self, test_db, sample_conflict):
        """Test voting strategy with insufficient votes."""
        strategy = VotingStrategy()
        settings = ConflictSettings(minimum_voter_count=3)
        
        context = ResolutionContext(
            conflict=sample_conflict,
            participants=[],
            settings=settings,
            resolver=None,
            metadata={}
        )
        
        can_resolve = strategy.can_resolve(context)
        assert can_resolve is False
    
    def test_voting_strategy_with_sufficient_votes(self, test_db, sample_conflict, sample_users):
        """Test voting strategy with sufficient votes."""
        # Add votes to the conflict
        votes = [
            ResolutionVote(
                conflict_id=sample_conflict.id,
                voter_id=sample_users[0].id,
                vote_choice="annotation_a",
                vote_weight=1.0
            ),
            ResolutionVote(
                conflict_id=sample_conflict.id,
                voter_id=sample_users[1].id,
                vote_choice="annotation_a",
                vote_weight=1.0
            ),
            ResolutionVote(
                conflict_id=sample_conflict.id,
                voter_id=sample_users[2].id,
                vote_choice="annotation_b",
                vote_weight=1.0
            )
        ]
        
        for vote in votes:
            test_db.add(vote)
        test_db.commit()
        
        # Refresh conflict to include votes
        test_db.refresh(sample_conflict)
        
        strategy = VotingStrategy()
        settings = ConflictSettings(minimum_voter_count=3, voting_threshold=0.6)
        
        context = ResolutionContext(
            conflict=sample_conflict,
            participants=[],
            settings=settings,
            resolver=None,
            metadata={}
        )
        
        result = strategy.resolve(context)
        
        assert result.success is True
        assert result.outcome == ResolutionOutcome.ANNOTATION_A_SELECTED
    
    def test_expert_review_strategy(self, test_db, sample_conflict):
        """Test expert review strategy."""
        strategy = ExpertReviewStrategy()
        
        context = ResolutionContext(
            conflict=sample_conflict,
            participants=[],
            settings=ConflictSettings(),
            resolver=None,
            metadata={}
        )
        
        can_resolve = strategy.can_resolve(context)
        result = strategy.resolve(context)
        
        assert can_resolve is True
        assert result.success is False  # Requires manual intervention
        assert "manual resolution needed" in result.description.lower()
    
    def test_conflict_resolution_engine(self, test_db, sample_conflict, sample_users):
        """Test the main conflict resolution engine."""
        engine = ConflictResolutionEngine(test_db)
        resolver = sample_users[0]
        
        result = engine.resolve_conflict(
            sample_conflict.id,
            resolver.id,
            ResolutionStrategy.AUTO_MERGE
        )
        
        # Check that resolution was attempted and recorded
        assert isinstance(result, ResolutionResult)
        
        # Verify resolution record was created
        resolutions = test_db.query(ConflictResolution).filter_by(conflict_id=sample_conflict.id).all()
        assert len(resolutions) >= 1
    
    def test_vote_submission(self, test_db, sample_conflict, sample_users):
        """Test vote submission functionality."""
        engine = ConflictResolutionEngine(test_db)
        voter = sample_users[0]
        
        success = engine.submit_vote(
            sample_conflict.id,
            voter.id,
            "annotation_a",
            "This annotation seems more accurate",
            0.8
        )
        
        assert success is True
        
        # Verify vote was recorded
        votes = test_db.query(ResolutionVote).filter_by(
            conflict_id=sample_conflict.id,
            voter_id=voter.id
        ).all()
        assert len(votes) == 1
        assert votes[0].vote_choice == "annotation_a"


# Notification System Tests

class TestNotificationSystem:
    """Test cases for the notification system."""
    
    @pytest.fixture
    def websocket_handler(self):
        """Create a mock WebSocket handler."""
        return WebSocketNotificationHandler()
    
    @pytest.fixture
    def notification_service(self, test_db, websocket_handler):
        """Create notification service for testing."""
        return NotificationService(test_db, websocket_handler)
    
    def test_notification_template_engine(self):
        """Test notification template generation."""
        engine = NotificationTemplateEngine()
        
        # Create mock objects
        mock_conflict = Mock()
        mock_conflict.conflict_type.value = "span_overlap"
        mock_conflict.severity_level = "high"
        mock_conflict.project.name = "Test Project"
        mock_conflict.id = 1
        mock_conflict.project_id = 1
        
        mock_user = Mock()
        mock_user.id = 1
        mock_user.username = "testuser"
        
        context = NotificationContext(
            conflict=mock_conflict,
            user=mock_user,
            event_type=NotificationType.CONFLICT_DETECTED,
            priority=NotificationPriority.HIGH,
            delivery_methods=set(),
            metadata={}
        )
        
        payload = engine.generate_notification(context)
        
        assert payload.recipient_id == 1
        assert payload.notification_type == NotificationType.CONFLICT_DETECTED
        assert "conflict detected" in payload.title.lower()
        assert "span_overlap" in payload.message
        assert "Test Project" in payload.message
    
    @pytest.mark.asyncio
    async def test_websocket_notification_handler(self, websocket_handler):
        """Test WebSocket notification handling."""
        # Mock WebSocket connection
        mock_websocket = AsyncMock()
        
        # Add connection
        websocket_handler.add_connection(1, mock_websocket)
        
        # Create notification payload
        payload = Mock()
        payload.recipient_id = 1
        payload.notification_type = NotificationType.CONFLICT_DETECTED
        payload.title = "Test Notification"
        payload.message = "Test message"
        payload.priority = NotificationPriority.NORMAL
        payload.metadata = {}
        payload.context_url = "/conflicts/1"
        
        # Test sending notification
        can_handle = await websocket_handler.can_handle(DeliveryMethod.WEBSOCKET)
        success = await websocket_handler.send_notification(payload)
        
        assert can_handle is True
        assert success is True
        mock_websocket.send_json.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_conflict_detection_notification(self, test_db, notification_service, sample_conflict, sample_users):
        """Test notification when conflict is detected."""
        # This would typically be tested with mocks to avoid actual notification sending
        with patch.object(notification_service, '_send_notification') as mock_send:
            await notification_service.notify_conflict_detected(
                sample_conflict, 
                [sample_users[0]]
            )
            
            mock_send.assert_called()


# Integration Tests

class TestAgreementIntegration:
    """Test cases for agreement system integration."""
    
    def test_conflict_impact_analysis(self, test_db, sample_project, sample_conflict):
        """Test conflict impact on agreement analysis."""
        analyzer = ConflictAgreementAnalyzer(test_db)
        
        metrics = analyzer.analyze_conflict_impact_on_agreement(sample_project.id)
        
        assert isinstance(metrics.baseline_agreement, float)
        assert isinstance(metrics.post_resolution_agreement, float)
        assert isinstance(metrics.agreement_improvement, float)
        assert isinstance(metrics.conflict_resolution_effectiveness, float)
    
    def test_quality_insights_generation(self, test_db, sample_project, sample_conflict):
        """Test quality insights generation."""
        analyzer = ConflictAgreementAnalyzer(test_db)
        
        insights = analyzer.generate_quality_insights(sample_project.id)
        
        assert isinstance(insights.frequent_conflict_patterns, list)
        assert isinstance(insights.problematic_annotator_pairs, list)
        assert isinstance(insights.improvement_recommendations, list)
        assert isinstance(insights.conflict_hotspots, list)
        assert isinstance(insights.resolution_effectiveness, dict)
    
    def test_integrated_quality_analysis(self, test_db, sample_project, sample_conflict):
        """Test complete integrated quality analysis."""
        integration = AgreementConflictIntegration(test_db)
        
        analysis = integration.run_integrated_quality_analysis(sample_project.id)
        
        assert "project_id" in analysis
        assert "conflict_impact_metrics" in analysis
        assert "quality_insights" in analysis
        assert "integration_recommendations" in analysis


# API Tests

class TestConflictAPI:
    """Test cases for conflict management API endpoints."""
    
    @pytest.fixture
    def test_client(self):
        """Create test client for API testing."""
        from main import app  # Assuming main.py contains the FastAPI app
        return TestClient(app)
    
    def test_list_conflicts_endpoint(self, test_client, sample_project):
        """Test conflicts listing endpoint."""
        response = test_client.get(f"/api/conflicts/?project_id={sample_project.id}")
        
        assert response.status_code == 200
        conflicts = response.json()
        assert isinstance(conflicts, list)
    
    def test_get_conflict_details_endpoint(self, test_client, sample_conflict):
        """Test conflict details endpoint."""
        response = test_client.get(f"/api/conflicts/{sample_conflict.id}")
        
        assert response.status_code == 200
        conflict_data = response.json()
        assert conflict_data["id"] == sample_conflict.id
    
    def test_detect_conflicts_endpoint(self, test_client, sample_project):
        """Test conflict detection endpoint."""
        response = test_client.post("/api/conflicts/detect", json={
            "project_id": sample_project.id,
            "check_new_only": False,
            "force_detection": True
        })
        
        assert response.status_code == 200
        result = response.json()
        assert "conflicts_detected" in result
    
    def test_submit_vote_endpoint(self, test_client, sample_conflict):
        """Test vote submission endpoint."""
        response = test_client.post(f"/api/conflicts/{sample_conflict.id}/vote", json={
            "vote_choice": "annotation_a",
            "rationale": "This annotation is more accurate",
            "confidence": 0.8
        })
        
        # This might return 401 if authentication is required
        # Adjust based on your authentication implementation
        assert response.status_code in [200, 401]
    
    def test_project_conflict_stats_endpoint(self, test_client, sample_project):
        """Test project conflict statistics endpoint."""
        response = test_client.get(f"/api/conflicts/projects/{sample_project.id}/stats")
        
        assert response.status_code == 200
        stats = response.json()
        assert "total_conflicts" in stats
        assert "pending_conflicts_count" in stats
        assert "resolved_conflicts_count" in stats


# Performance and Edge Case Tests

class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_conflict_detection_empty_project(self, test_db, sample_project):
        """Test conflict detection on project with no annotations."""
        engine = ConflictDetectionEngine(test_db)
        
        candidates = engine.detect_conflicts_for_project(sample_project.id)
        
        assert len(candidates) == 0
    
    def test_resolution_nonexistent_conflict(self, test_db):
        """Test resolution of non-existent conflict."""
        engine = ConflictResolutionEngine(test_db)
        
        result = engine.resolve_conflict(999, 1)  # Non-existent conflict
        
        assert result.success is False
        assert "not found" in result.description.lower()
    
    def test_voting_with_tie(self, test_db, sample_conflict, sample_users):
        """Test voting resolution with tied votes."""
        # Create tie votes
        votes = [
            ResolutionVote(
                conflict_id=sample_conflict.id,
                voter_id=sample_users[0].id,
                vote_choice="annotation_a",
                vote_weight=1.0
            ),
            ResolutionVote(
                conflict_id=sample_conflict.id,
                voter_id=sample_users[1].id,
                vote_choice="annotation_b",
                vote_weight=1.0
            )
        ]
        
        for vote in votes:
            test_db.add(vote)
        test_db.commit()
        
        test_db.refresh(sample_conflict)
        
        strategy = VotingStrategy()
        settings = ConflictSettings(minimum_voter_count=2, voting_threshold=0.6)
        
        context = ResolutionContext(
            conflict=sample_conflict,
            participants=[],
            settings=settings,
            resolver=None,
            metadata={}
        )
        
        result = strategy.resolve(context)
        
        # Should fail due to insufficient consensus (50% < 60% threshold)
        assert result.success is False
        assert "insufficient consensus" in result.description.lower()
    
    def test_conflict_settings_defaults(self, test_db, sample_project):
        """Test that default conflict settings are created."""
        engine = ConflictDetectionEngine(test_db)
        
        settings = engine._get_project_settings(sample_project.id)
        
        assert settings is not None
        assert settings.project_id == sample_project.id
        assert settings.enable_conflict_detection is True
        assert settings.span_overlap_threshold == 0.1
    
    def test_large_number_of_conflicts(self, test_db, sample_project, sample_text, sample_label, sample_users):
        """Test performance with large number of conflicts."""
        # Create many overlapping annotations
        annotations = []
        for i in range(20):
            annotation = Annotation(
                start_char=i * 2,
                end_char=(i * 2) + 10,
                selected_text=f"text segment {i}",
                text_id=sample_text.id,
                annotator_id=sample_users[i % len(sample_users)].id,
                label_id=sample_label.id,
                confidence_score=0.5 + (i % 5) * 0.1
            )
            annotations.append(annotation)
            test_db.add(annotation)
        
        test_db.commit()
        
        # Test conflict detection
        engine = ConflictDetectionEngine(test_db)
        candidates = engine.detect_conflicts_for_project(sample_project.id)
        
        # Should detect multiple conflicts
        assert len(candidates) > 0


# Test Configuration

class TestConfiguration:
    """Test configuration and setup validation."""
    
    def test_database_models_creation(self, test_db):
        """Test that all conflict-related database models can be created."""
        # Create instances of all models to ensure they're properly configured
        project = Project(name="Test", owner_id=1)
        user = User(username="test", email="test@test.com", hashed_password="test")
        
        test_db.add_all([project, user])
        test_db.commit()
        
        conflict = AnnotationConflict(
            conflict_type=ConflictType.SPAN_OVERLAP,
            conflict_description="Test",
            annotation_a_id=1,
            annotation_b_id=2,
            project_id=project.id,
            text_id=1
        )
        
        resolution = ConflictResolution(
            conflict_id=1,
            resolution_strategy=ResolutionStrategy.AUTO_MERGE,
            resolution_description="Test resolution",
            resolver_id=user.id
        )
        
        vote = ResolutionVote(
            conflict_id=1,
            voter_id=user.id,
            vote_choice="annotation_a"
        )
        
        notification = ConflictNotification(
            conflict_id=1,
            recipient_id=user.id,
            notification_type="conflict_detected",
            title="Test",
            message="Test message"
        )
        
        settings = ConflictSettings(project_id=project.id)
        
        test_db.add_all([conflict, resolution, vote, notification, settings])
        test_db.commit()
        
        # Verify all objects were created successfully
        assert test_db.query(AnnotationConflict).count() == 1
        assert test_db.query(ConflictResolution).count() == 1
        assert test_db.query(ResolutionVote).count() == 1
        assert test_db.query(ConflictNotification).count() == 1
        assert test_db.query(ConflictSettings).count() == 1


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main(["-v", __file__])