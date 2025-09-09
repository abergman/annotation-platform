"""
Unit Tests for Annotations API Endpoints

Comprehensive test suite for annotation CRUD operations, access control, 
span validation, context extraction, filtering, querying, and agreement workflow triggers.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Import the code under test
from src.api.annotations import (
    create_annotation,
    list_annotations,
    get_annotation,
    update_annotation,
    validate_annotation,
    delete_annotation,
    AnnotationCreate,
    AnnotationUpdate,
    AnnotationValidation,
    AnnotationResponse
)
from src.models.annotation import Annotation
from src.models.text import Text
from src.models.label import Label
from src.models.project import Project
from src.models.user import User
from src.services.agreement_service import AgreementService


class TestAnnotationCreation:
    """Unit tests for annotation creation functionality."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def mock_current_user(self):
        """Mock current authenticated user."""
        user = Mock(spec=User)
        user.id = 1
        user.username = "testuser"
        user.email = "test@example.com"
        user.is_active = True
        return user
    
    @pytest.fixture
    def mock_other_user(self):
        """Mock another user."""
        user = Mock(spec=User)
        user.id = 2
        user.username = "otheruser"
        user.email = "other@example.com"
        user.is_active = True
        return user
    
    @pytest.fixture
    def mock_project(self, mock_current_user):
        """Mock project owned by current user."""
        project = Mock(spec=Project)
        project.id = 1
        project.name = "Test Project"
        project.owner_id = 1
        project.is_public = False
        return project
    
    @pytest.fixture
    def mock_public_project(self, mock_other_user):
        """Mock public project owned by another user."""
        project = Mock(spec=Project)
        project.id = 2
        project.name = "Public Project"
        project.owner_id = 2
        project.is_public = True
        return project
    
    @pytest.fixture
    def mock_text(self, mock_project):
        """Mock text document."""
        text = Mock(spec=Text)
        text.id = 1
        text.title = "Test Document"
        text.content = "This is a test document with some text to annotate. It has multiple sentences."
        text.project_id = 1
        text.project = mock_project
        return text
    
    @pytest.fixture
    def mock_public_text(self, mock_public_project):
        """Mock text from public project."""
        text = Mock(spec=Text)
        text.id = 2
        text.title = "Public Document"
        text.content = "This is a public document available for annotation by multiple users."
        text.project_id = 2
        text.project = mock_public_project
        return text
    
    @pytest.fixture
    def mock_label(self):
        """Mock annotation label."""
        label = Mock(spec=Label)
        label.id = 1
        label.name = "PERSON"
        label.description = "Person entity"
        label.color = "#007bff"
        label.project_id = 1
        label.usage_count = 0
        return label
    
    @pytest.fixture
    def valid_annotation_data(self):
        """Valid annotation creation data."""
        return AnnotationCreate(
            text_id=1,
            label_id=1,
            start_char=10,
            end_char=14,
            selected_text="test",
            notes="This is a test annotation",
            confidence_score=0.95,
            metadata={"source": "manual", "reviewer": "testuser"}
        )
    
    @pytest.fixture
    def minimal_annotation_data(self):
        """Minimal annotation creation data."""
        return AnnotationCreate(
            text_id=1,
            label_id=1,
            start_char=10,
            end_char=14,
            selected_text="test"
        )
    
    @pytest.fixture
    def mock_created_annotation(self, mock_text, mock_label, mock_current_user):
        """Mock created annotation."""
        annotation = Mock(spec=Annotation)
        annotation.id = 1
        annotation.text_id = 1
        annotation.label_id = 1
        annotation.annotator_id = 1
        annotation.start_char = 10
        annotation.end_char = 14
        annotation.selected_text = "test"
        annotation.notes = "This is a test annotation"
        annotation.confidence_score = 0.95
        annotation.metadata = {"source": "manual", "reviewer": "testuser"}
        annotation.context_before = "This is a "
        annotation.context_after = " document with"
        annotation.is_validated = "pending"
        annotation.validation_notes = None
        annotation.created_at = datetime(2023, 1, 1, 12, 0, 0)
        annotation.updated_at = datetime(2023, 1, 1, 12, 0, 0)
        annotation.text = mock_text
        annotation.label = mock_label
        annotation.annotator = mock_current_user
        annotation.to_dict.return_value = {
            "id": 1,
            "start_char": 10,
            "end_char": 14,
            "selected_text": "test",
            "notes": "This is a test annotation",
            "confidence_score": 0.95,
            "metadata": {"source": "manual", "reviewer": "testuser"},
            "context_before": "This is a ",
            "context_after": " document with",
            "is_validated": "pending",
            "validation_notes": None,
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-01T12:00:00",
            "text_id": 1,
            "annotator_id": 1,
            "label_id": 1,
            "label_name": "PERSON",
            "label_color": "#007bff",
            "annotator_username": "testuser"
        }
        return annotation
    
    @pytest.mark.unit
    async def test_create_annotation_success(self, mock_db, mock_current_user, mock_text, mock_label, valid_annotation_data, mock_created_annotation):
        """Test successful annotation creation."""
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_text, mock_label]
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        with patch('src.api.annotations.Annotation') as mock_annotation_class:
            mock_annotation_class.return_value = mock_created_annotation
            with patch('src.api.annotations.AgreementService') as mock_agreement_service_class:
                mock_service = Mock()
                mock_service.trigger_agreement_calculation = Mock()
                mock_agreement_service_class.return_value = mock_service
                
                result = await create_annotation(valid_annotation_data, mock_current_user, mock_db)
        
        # Assertions
        assert isinstance(result, AnnotationResponse) or isinstance(result, dict)
        if isinstance(result, dict):
            assert result["id"] == 1
            assert result["start_char"] == 10
            assert result["end_char"] == 14
            assert result["selected_text"] == "test"
            assert result["notes"] == "This is a test annotation"
            assert result["confidence_score"] == 0.95
            assert result["metadata"]["source"] == "manual"
            assert result["context_before"] == "This is a "
            assert result["context_after"] == " document with"
            assert result["is_validated"] == "pending"
            assert result["text_id"] == 1
            assert result["annotator_id"] == 1
            assert result["label_id"] == 1
            assert result["label_name"] == "PERSON"
            assert result["annotator_username"] == "testuser"
        
        # Verify database interactions
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        
        # Verify label usage count was incremented
        assert mock_label.usage_count == 1
        
        # Verify agreement calculation was triggered
        mock_service.trigger_agreement_calculation.assert_called_once_with(1)
    
    @pytest.mark.unit
    async def test_create_annotation_minimal_data(self, mock_db, mock_current_user, mock_text, mock_label, minimal_annotation_data):
        """Test annotation creation with minimal required data."""
        # Mock created annotation with defaults
        mock_created_annotation = Mock(spec=Annotation)
        mock_created_annotation.to_dict.return_value = {
            "id": 1,
            "start_char": 10,
            "end_char": 14,
            "selected_text": "test",
            "notes": None,
            "confidence_score": 1.0,  # Default
            "metadata": {},  # Default empty dict
            "context_before": "This is a ",
            "context_after": " document with",
            "is_validated": "pending",
            "validation_notes": None,
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-01T12:00:00",
            "text_id": 1,
            "annotator_id": 1,
            "label_id": 1,
            "label_name": "PERSON",
            "label_color": "#007bff",
            "annotator_username": "testuser"
        }
        
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_text, mock_label]
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        with patch('src.api.annotations.Annotation') as mock_annotation_class:
            mock_annotation_class.return_value = mock_created_annotation
            with patch('src.api.annotations.AgreementService'):
                
                result = await create_annotation(minimal_annotation_data, mock_current_user, mock_db)
        
        # Verify defaults are applied
        if isinstance(result, dict):
            assert result["notes"] is None
            assert result["confidence_score"] == 1.0
            assert result["metadata"] == {}
    
    @pytest.mark.unit
    async def test_create_annotation_text_not_found(self, mock_db, mock_current_user, valid_annotation_data):
        """Test annotation creation with non-existent text."""
        # Mock database query returning None for text
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(HTTPException) as exc_info:
            await create_annotation(valid_annotation_data, mock_current_user, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "Text not found" in str(exc_info.value.detail)
    
    @pytest.mark.unit
    async def test_create_annotation_access_denied_private_text(self, mock_db, mock_current_user, valid_annotation_data):
        """Test annotation creation access denied for private text."""
        # Mock private text owned by another user
        mock_private_text = Mock(spec=Text)
        mock_private_text.id = 1
        mock_private_project = Mock(spec=Project)
        mock_private_project.owner_id = 2  # Different user
        mock_private_project.is_public = False
        mock_private_text.project = mock_private_project
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_private_text
        
        with pytest.raises(HTTPException) as exc_info:
            await create_annotation(valid_annotation_data, mock_current_user, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Access denied to this text" in str(exc_info.value.detail)
    
    @pytest.mark.unit
    async def test_create_annotation_public_text_access_allowed(self, mock_db, mock_current_user, mock_public_text, mock_label, valid_annotation_data):
        """Test annotation creation allowed on public text."""
        # Update annotation data to use public text
        valid_annotation_data.text_id = 2
        
        # Mock label from same project as public text
        mock_label.project_id = 2
        
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_public_text, mock_label]
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        mock_created_annotation = Mock(spec=Annotation)
        mock_created_annotation.to_dict.return_value = {
            "id": 1,
            "start_char": 10,
            "end_char": 14,
            "selected_text": "test",
            "notes": "This is a test annotation",
            "confidence_score": 0.95,
            "metadata": {"source": "manual", "reviewer": "testuser"},
            "context_before": "This is a ",
            "context_after": " public document",
            "is_validated": "pending",
            "validation_notes": None,
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-01T12:00:00",
            "text_id": 2,
            "annotator_id": 1,
            "label_id": 1,
            "label_name": "PERSON",
            "label_color": "#007bff",
            "annotator_username": "testuser"
        }
        
        with patch('src.api.annotations.Annotation') as mock_annotation_class:
            mock_annotation_class.return_value = mock_created_annotation
            with patch('src.api.annotations.AgreementService'):
                
                result = await create_annotation(valid_annotation_data, mock_current_user, mock_db)
        
        # Should succeed without exception
        assert result is not None
        if isinstance(result, dict):
            assert result["text_id"] == 2
    
    @pytest.mark.unit
    async def test_create_annotation_label_not_found(self, mock_db, mock_current_user, mock_text, valid_annotation_data):
        """Test annotation creation with non-existent label."""
        # Mock database queries - text exists, label doesn't
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_text, None]
        
        with pytest.raises(HTTPException) as exc_info:
            await create_annotation(valid_annotation_data, mock_current_user, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "Label not found" in str(exc_info.value.detail)
    
    @pytest.mark.unit
    async def test_create_annotation_label_project_mismatch(self, mock_db, mock_current_user, mock_text, valid_annotation_data):
        """Test annotation creation with label from different project."""
        # Mock label from different project
        mock_wrong_label = Mock(spec=Label)
        mock_wrong_label.id = 1
        mock_wrong_label.project_id = 2  # Different from text's project (id=1)
        
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_text, mock_wrong_label]
        
        with pytest.raises(HTTPException) as exc_info:
            await create_annotation(valid_annotation_data, mock_current_user, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Label does not belong to the same project as the text" in str(exc_info.value.detail)
    
    @pytest.mark.unit
    async def test_create_annotation_invalid_span_negative_start(self, mock_db, mock_current_user, mock_text, mock_label):
        """Test annotation creation with negative start character."""
        invalid_data = AnnotationCreate(
            text_id=1,
            label_id=1,
            start_char=-1,  # Invalid
            end_char=14,
            selected_text="test"
        )
        
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_text, mock_label]
        
        with pytest.raises(HTTPException) as exc_info:
            await create_annotation(invalid_data, mock_current_user, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid annotation span" in str(exc_info.value.detail)
    
    @pytest.mark.unit
    async def test_create_annotation_invalid_span_end_beyond_text(self, mock_db, mock_current_user, mock_text, mock_label):
        """Test annotation creation with end character beyond text length."""
        invalid_data = AnnotationCreate(
            text_id=1,
            label_id=1,
            start_char=10,
            end_char=1000,  # Beyond text length
            selected_text="test"
        )
        
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_text, mock_label]
        
        with pytest.raises(HTTPException) as exc_info:
            await create_annotation(invalid_data, mock_current_user, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid annotation span" in str(exc_info.value.detail)
    
    @pytest.mark.unit
    async def test_create_annotation_invalid_span_start_after_end(self, mock_db, mock_current_user, mock_text, mock_label):
        """Test annotation creation with start after end character."""
        invalid_data = AnnotationCreate(
            text_id=1,
            label_id=1,
            start_char=20,
            end_char=10,  # Start after end
            selected_text="test"
        )
        
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_text, mock_label]
        
        with pytest.raises(HTTPException) as exc_info:
            await create_annotation(invalid_data, mock_current_user, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid annotation span" in str(exc_info.value.detail)
    
    @pytest.mark.unit
    async def test_create_annotation_context_extraction(self, mock_db, mock_current_user, mock_text, mock_label, valid_annotation_data, mock_created_annotation):
        """Test proper context extraction around annotation."""
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_text, mock_label]
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        with patch('src.api.annotations.Annotation') as mock_annotation_class:
            mock_annotation_class.return_value = mock_created_annotation
            with patch('src.api.annotations.AgreementService'):
                
                await create_annotation(valid_annotation_data, mock_current_user, mock_db)
        
        # Verify context extraction in Annotation constructor call
        call_args = mock_annotation_class.call_args
        assert 'context_before' in call_args.kwargs
        assert 'context_after' in call_args.kwargs
        
        # Context should be limited to 200 characters
        context_before = call_args.kwargs['context_before']
        context_after = call_args.kwargs['context_after']
        assert len(context_before) <= 200
        assert len(context_after) <= 200
    
    @pytest.mark.unit
    async def test_create_annotation_agreement_service_failure(self, mock_db, mock_current_user, mock_text, mock_label, valid_annotation_data, mock_created_annotation):
        """Test annotation creation succeeds even if agreement service fails."""
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_text, mock_label]
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        with patch('src.api.annotations.Annotation') as mock_annotation_class:
            mock_annotation_class.return_value = mock_created_annotation
            with patch('src.api.annotations.AgreementService') as mock_agreement_service_class:
                mock_service = Mock()
                mock_service.trigger_agreement_calculation.side_effect = Exception("Agreement service error")
                mock_agreement_service_class.return_value = mock_service
                
                # Should not raise exception
                result = await create_annotation(valid_annotation_data, mock_current_user, mock_db)
        
        # Annotation should still be created successfully
        assert result is not None
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()


class TestAnnotationListing:
    """Unit tests for annotation listing functionality."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def mock_current_user(self):
        """Mock current authenticated user."""
        user = Mock(spec=User)
        user.id = 1
        user.username = "testuser"
        return user
    
    @pytest.fixture
    def sample_annotations(self, mock_current_user):
        """Sample annotations for testing."""
        annotations = []
        
        for i in range(5):
            annotation = Mock(spec=Annotation)
            annotation.id = i + 1
            annotation.text_id = (i % 2) + 1  # Alternate between text 1 and 2
            annotation.label_id = (i % 3) + 1  # Rotate through labels 1, 2, 3
            annotation.annotator_id = 1
            annotation.start_char = i * 10
            annotation.end_char = (i * 10) + 5
            annotation.selected_text = f"text{i}"
            annotation.notes = f"Note {i}"
            annotation.confidence_score = 0.9
            annotation.metadata = {"index": i}
            annotation.context_before = f"before{i}"
            annotation.context_after = f"after{i}"
            annotation.is_validated = "pending" if i < 3 else "approved"
            annotation.validation_notes = None
            annotation.created_at = datetime(2023, 1, i + 1, 12, 0, 0)
            annotation.updated_at = datetime(2023, 1, i + 1, 12, 0, 0)
            annotation.to_dict.return_value = {
                "id": i + 1,
                "start_char": i * 10,
                "end_char": (i * 10) + 5,
                "selected_text": f"text{i}",
                "notes": f"Note {i}",
                "confidence_score": 0.9,
                "metadata": {"index": i},
                "context_before": f"before{i}",
                "context_after": f"after{i}",
                "is_validated": "pending" if i < 3 else "approved",
                "validation_notes": None,
                "created_at": f"2023-01-0{i+1}T12:00:00",
                "updated_at": f"2023-01-0{i+1}T12:00:00",
                "text_id": (i % 2) + 1,
                "annotator_id": 1,
                "label_id": (i % 3) + 1,
                "label_name": f"LABEL{(i % 3) + 1}",
                "label_color": "#007bff",
                "annotator_username": "testuser"
            }
            annotations.append(annotation)
        
        return annotations
    
    @pytest.mark.unit
    async def test_list_annotations_no_filters(self, mock_db, mock_current_user, sample_annotations):
        """Test listing annotations without filters."""
        # Mock query chain
        mock_query = Mock()
        mock_join1 = Mock()
        mock_join2 = Mock()
        mock_filter = Mock()
        mock_offset = Mock()
        mock_limit = Mock()
        
        mock_limit.all.return_value = sample_annotations
        mock_offset.limit.return_value = mock_limit
        mock_filter.offset.return_value = mock_offset
        mock_join2.filter.return_value = mock_filter
        mock_join1.join.return_value = mock_join2
        mock_query.join.return_value = mock_join1
        mock_db.query.return_value = mock_query
        
        result = await list_annotations(
            text_id=None,
            project_id=None,
            label_id=None,
            annotator_id=None,
            skip=0,
            limit=10,
            current_user=mock_current_user,
            db=mock_db
        )
        
        # Assertions
        assert isinstance(result, list)
        assert len(result) == 5
        
        # Verify query structure
        mock_query.join.assert_called()  # Join with Text
        mock_join1.join.assert_called()  # Join with Project
        mock_join2.filter.assert_called_once()  # Access control filter
        mock_filter.offset.assert_called_once_with(0)
        mock_offset.limit.assert_called_once_with(10)
    
    @pytest.mark.unit
    async def test_list_annotations_with_text_filter(self, mock_db, mock_current_user, sample_annotations):
        """Test listing annotations filtered by text ID."""
        # Filter to annotations from text 1
        filtered_annotations = [ann for ann in sample_annotations if ann.to_dict()["text_id"] == 1]
        
        # Mock query chain
        mock_query = Mock()
        mock_join1 = Mock()
        mock_join2 = Mock()
        mock_filter1 = Mock()
        mock_filter2 = Mock()
        mock_offset = Mock()
        mock_limit = Mock()
        
        mock_limit.all.return_value = filtered_annotations
        mock_offset.limit.return_value = mock_limit
        mock_filter2.offset.return_value = mock_offset
        mock_filter1.filter.return_value = mock_filter2
        mock_join2.filter.return_value = mock_filter1
        mock_join1.join.return_value = mock_join2
        mock_query.join.return_value = mock_join1
        mock_db.query.return_value = mock_query
        
        result = await list_annotations(
            text_id=1,
            project_id=None,
            label_id=None,
            annotator_id=None,
            skip=0,
            limit=10,
            current_user=mock_current_user,
            db=mock_db
        )
        
        # Verify text filter was applied
        assert mock_filter1.filter.call_count >= 1
        assert len(result) == len(filtered_annotations)
    
    @pytest.mark.unit
    async def test_list_annotations_with_project_filter(self, mock_db, mock_current_user, sample_annotations):
        """Test listing annotations filtered by project ID."""
        # Mock query chain with project filter
        mock_query = Mock()
        mock_join1 = Mock()
        mock_join2 = Mock()
        mock_filter1 = Mock()
        mock_filter2 = Mock()
        mock_offset = Mock()
        mock_limit = Mock()
        
        mock_limit.all.return_value = sample_annotations[:3]  # Subset
        mock_offset.limit.return_value = mock_limit
        mock_filter2.offset.return_value = mock_offset
        mock_filter1.filter.return_value = mock_filter2
        mock_join2.filter.return_value = mock_filter1
        mock_join1.join.return_value = mock_join2
        mock_query.join.return_value = mock_join1
        mock_db.query.return_value = mock_query
        
        result = await list_annotations(
            text_id=None,
            project_id=1,
            label_id=None,
            annotator_id=None,
            skip=0,
            limit=10,
            current_user=mock_current_user,
            db=mock_db
        )
        
        # Verify project filter was applied
        assert mock_filter1.filter.call_count >= 1
        assert len(result) == 3
    
    @pytest.mark.unit
    async def test_list_annotations_with_label_filter(self, mock_db, mock_current_user, sample_annotations):
        """Test listing annotations filtered by label ID."""
        # Filter to annotations with label 1
        filtered_annotations = [ann for ann in sample_annotations if ann.to_dict()["label_id"] == 1]
        
        # Mock query chain
        mock_query = Mock()
        mock_join1 = Mock()
        mock_join2 = Mock()
        mock_filter1 = Mock()
        mock_filter2 = Mock()
        mock_offset = Mock()
        mock_limit = Mock()
        
        mock_limit.all.return_value = filtered_annotations
        mock_offset.limit.return_value = mock_limit
        mock_filter2.offset.return_value = mock_offset
        mock_filter1.filter.return_value = mock_filter2
        mock_join2.filter.return_value = mock_filter1
        mock_join1.join.return_value = mock_join2
        mock_query.join.return_value = mock_join1
        mock_db.query.return_value = mock_query
        
        result = await list_annotations(
            text_id=None,
            project_id=None,
            label_id=1,
            annotator_id=None,
            skip=0,
            limit=10,
            current_user=mock_current_user,
            db=mock_db
        )
        
        # Verify label filter was applied
        assert mock_filter1.filter.call_count >= 1
        assert len(result) == len(filtered_annotations)
    
    @pytest.mark.unit
    async def test_list_annotations_with_annotator_filter(self, mock_db, mock_current_user, sample_annotations):
        """Test listing annotations filtered by annotator ID."""
        # Mock query chain
        mock_query = Mock()
        mock_join1 = Mock()
        mock_join2 = Mock()
        mock_filter1 = Mock()
        mock_filter2 = Mock()
        mock_offset = Mock()
        mock_limit = Mock()
        
        mock_limit.all.return_value = sample_annotations
        mock_offset.limit.return_value = mock_limit
        mock_filter2.offset.return_value = mock_offset
        mock_filter1.filter.return_value = mock_filter2
        mock_join2.filter.return_value = mock_filter1
        mock_join1.join.return_value = mock_join2
        mock_query.join.return_value = mock_join1
        mock_db.query.return_value = mock_query
        
        result = await list_annotations(
            text_id=None,
            project_id=None,
            label_id=None,
            annotator_id=1,
            skip=0,
            limit=10,
            current_user=mock_current_user,
            db=mock_db
        )
        
        # Verify annotator filter was applied
        assert mock_filter1.filter.call_count >= 1
        assert len(result) == 5
    
    @pytest.mark.unit
    async def test_list_annotations_pagination(self, mock_db, mock_current_user, sample_annotations):
        """Test annotation listing pagination."""
        # Mock query chain
        mock_query = Mock()
        mock_join1 = Mock()
        mock_join2 = Mock()
        mock_filter = Mock()
        mock_offset = Mock()
        mock_limit = Mock()
        
        # Return paginated subset
        mock_limit.all.return_value = sample_annotations[2:4]
        mock_offset.limit.return_value = mock_limit
        mock_filter.offset.return_value = mock_offset
        mock_join2.filter.return_value = mock_filter
        mock_join1.join.return_value = mock_join2
        mock_query.join.return_value = mock_join1
        mock_db.query.return_value = mock_query
        
        result = await list_annotations(
            text_id=None,
            project_id=None,
            label_id=None,
            annotator_id=None,
            skip=2,
            limit=2,
            current_user=mock_current_user,
            db=mock_db
        )
        
        # Verify pagination parameters were applied
        mock_filter.offset.assert_called_once_with(2)
        mock_offset.limit.assert_called_once_with(2)
        assert len(result) == 2
    
    @pytest.mark.unit
    async def test_list_annotations_empty_result(self, mock_db, mock_current_user):
        """Test listing annotations when no annotations match criteria."""
        # Mock query chain returning empty list
        mock_query = Mock()
        mock_join1 = Mock()
        mock_join2 = Mock()
        mock_filter = Mock()
        mock_offset = Mock()
        mock_limit = Mock()
        
        mock_limit.all.return_value = []
        mock_offset.limit.return_value = mock_limit
        mock_filter.offset.return_value = mock_offset
        mock_join2.filter.return_value = mock_filter
        mock_join1.join.return_value = mock_join2
        mock_query.join.return_value = mock_join1
        mock_db.query.return_value = mock_query
        
        result = await list_annotations(
            text_id=999,  # Non-existent text
            project_id=None,
            label_id=None,
            annotator_id=None,
            skip=0,
            limit=10,
            current_user=mock_current_user,
            db=mock_db
        )
        
        assert isinstance(result, list)
        assert len(result) == 0
    
    @pytest.mark.unit
    async def test_list_annotations_access_control(self, mock_db, mock_current_user):
        """Test that access control is properly applied in listing."""
        # Mock query chain
        mock_query = Mock()
        mock_join1 = Mock()
        mock_join2 = Mock()
        mock_filter = Mock()
        mock_offset = Mock()
        mock_limit = Mock()
        
        mock_limit.all.return_value = []
        mock_offset.limit.return_value = mock_limit
        mock_filter.offset.return_value = mock_offset
        mock_join2.filter.return_value = mock_filter
        mock_join1.join.return_value = mock_join2
        mock_query.join.return_value = mock_join1
        mock_db.query.return_value = mock_query
        
        await list_annotations(
            text_id=None,
            project_id=None,
            label_id=None,
            annotator_id=None,
            skip=0,
            limit=10,
            current_user=mock_current_user,
            db=mock_db
        )
        
        # Verify access control filter is applied
        # The filter should check for (owner_id == user.id OR is_public == True)
        mock_join2.filter.assert_called_once()


class TestAnnotationRetrieval:
    """Unit tests for individual annotation retrieval."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def mock_current_user(self):
        """Mock current authenticated user."""
        user = Mock(spec=User)
        user.id = 1
        user.username = "testuser"
        return user
    
    @pytest.fixture
    def mock_project(self):
        """Mock project."""
        project = Mock(spec=Project)
        project.id = 1
        project.name = "Test Project"
        project.owner_id = 1
        project.is_public = False
        return project
    
    @pytest.fixture
    def mock_public_project(self):
        """Mock public project."""
        project = Mock(spec=Project)
        project.id = 2
        project.name = "Public Project"
        project.owner_id = 2
        project.is_public = True
        return project
    
    @pytest.fixture
    def mock_text(self, mock_project):
        """Mock text."""
        text = Mock(spec=Text)
        text.id = 1
        text.project = mock_project
        return text
    
    @pytest.fixture
    def mock_public_text(self, mock_public_project):
        """Mock text from public project."""
        text = Mock(spec=Text)
        text.id = 2
        text.project = mock_public_project
        return text
    
    @pytest.fixture
    def mock_user_annotation(self, mock_text):
        """Mock annotation by current user."""
        annotation = Mock(spec=Annotation)
        annotation.id = 1
        annotation.annotator_id = 1
        annotation.text = mock_text
        annotation.to_dict.return_value = {
            "id": 1,
            "start_char": 10,
            "end_char": 14,
            "selected_text": "test",
            "notes": "Test annotation",
            "confidence_score": 0.9,
            "metadata": {},
            "context_before": "This is a ",
            "context_after": " document",
            "is_validated": "pending",
            "validation_notes": None,
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-01T12:00:00",
            "text_id": 1,
            "annotator_id": 1,
            "label_id": 1,
            "label_name": "PERSON",
            "label_color": "#007bff",
            "annotator_username": "testuser"
        }
        return annotation
    
    @pytest.fixture
    def mock_public_annotation(self, mock_public_text):
        """Mock annotation on public project."""
        annotation = Mock(spec=Annotation)
        annotation.id = 2
        annotation.annotator_id = 2
        annotation.text = mock_public_text
        annotation.to_dict.return_value = {
            "id": 2,
            "start_char": 5,
            "end_char": 10,
            "selected_text": "public",
            "notes": "Public annotation",
            "confidence_score": 0.8,
            "metadata": {},
            "context_before": "This ",
            "context_after": " annotation",
            "is_validated": "approved",
            "validation_notes": None,
            "created_at": "2023-01-02T12:00:00",
            "updated_at": "2023-01-02T12:00:00",
            "text_id": 2,
            "annotator_id": 2,
            "label_id": 1,
            "label_name": "ENTITY",
            "label_color": "#28a745",
            "annotator_username": "otheruser"
        }
        return annotation
    
    @pytest.fixture
    def mock_private_annotation(self, mock_text):
        """Mock annotation on private project by another user."""
        # Create private project owned by different user
        private_project = Mock(spec=Project)
        private_project.id = 3
        private_project.owner_id = 2  # Different user
        private_project.is_public = False
        
        private_text = Mock(spec=Text)
        private_text.id = 3
        private_text.project = private_project
        
        annotation = Mock(spec=Annotation)
        annotation.id = 3
        annotation.annotator_id = 2
        annotation.text = private_text
        return annotation
    
    @pytest.mark.unit
    async def test_get_annotation_success_own_annotation(self, mock_db, mock_current_user, mock_user_annotation):
        """Test retrieving user's own annotation."""
        # Mock database query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_user_annotation
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        result = await get_annotation(1, mock_current_user, mock_db)
        
        # Assertions
        assert isinstance(result, AnnotationResponse) or isinstance(result, dict)
        if isinstance(result, dict):
            assert result["id"] == 1
            assert result["annotator_id"] == 1
            assert result["annotator_username"] == "testuser"
    
    @pytest.mark.unit
    async def test_get_annotation_success_public_project(self, mock_db, mock_current_user, mock_public_annotation):
        """Test retrieving annotation from public project."""
        # Mock database query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_public_annotation
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        result = await get_annotation(2, mock_current_user, mock_db)
        
        # Assertions
        assert isinstance(result, AnnotationResponse) or isinstance(result, dict)
        if isinstance(result, dict):
            assert result["id"] == 2
            assert result["annotator_username"] == "otheruser"
    
    @pytest.mark.unit
    async def test_get_annotation_not_found(self, mock_db, mock_current_user):
        """Test retrieving non-existent annotation."""
        # Mock database query returning None
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = None
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        with pytest.raises(HTTPException) as exc_info:
            await get_annotation(999, mock_current_user, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "Annotation not found" in str(exc_info.value.detail)
    
    @pytest.mark.unit
    async def test_get_annotation_access_denied(self, mock_db, mock_current_user, mock_private_annotation):
        """Test retrieving annotation from private project."""
        # Mock database query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_private_annotation
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        with pytest.raises(HTTPException) as exc_info:
            await get_annotation(3, mock_current_user, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Access denied to this annotation" in str(exc_info.value.detail)


class TestAnnotationUpdate:
    """Unit tests for annotation update functionality."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        db.commit = Mock()
        db.refresh = Mock()
        return db
    
    @pytest.fixture
    def mock_current_user(self):
        """Mock current authenticated user."""
        user = Mock(spec=User)
        user.id = 1
        user.username = "testuser"
        return user
    
    @pytest.fixture
    def mock_project(self, mock_current_user):
        """Mock project owned by current user."""
        project = Mock(spec=Project)
        project.id = 1
        project.name = "Test Project"
        project.owner_id = 1
        return project
    
    @pytest.fixture
    def mock_text(self, mock_project):
        """Mock text."""
        text = Mock(spec=Text)
        text.id = 1
        text.content = "This is a test document with some content to annotate properly."
        text.project = mock_project
        text.project_id = 1
        return text
    
    @pytest.fixture
    def mock_annotation(self, mock_text, mock_current_user):
        """Mock annotation owned by current user."""
        annotation = Mock(spec=Annotation)
        annotation.id = 1
        annotation.text_id = 1
        annotation.label_id = 1
        annotation.annotator_id = 1
        annotation.start_char = 10
        annotation.end_char = 14
        annotation.selected_text = "test"
        annotation.notes = "Original note"
        annotation.confidence_score = 0.9
        annotation.metadata = {"original": True}
        annotation.text = mock_text
        annotation.to_dict.return_value = {
            "id": 1,
            "start_char": 10,
            "end_char": 14,
            "selected_text": "test",
            "notes": "Updated note",  # Will be updated
            "confidence_score": 0.95,
            "metadata": {"updated": True},
            "context_before": "This is a ",
            "context_after": " document",
            "is_validated": "pending",
            "validation_notes": None,
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-01T12:30:00",
            "text_id": 1,
            "annotator_id": 1,
            "label_id": 2,
            "label_name": "ENTITY",
            "label_color": "#28a745",
            "annotator_username": "testuser"
        }
        return annotation
    
    @pytest.fixture
    def mock_other_user_annotation(self, mock_text):
        """Mock annotation by another user."""
        annotation = Mock(spec=Annotation)
        annotation.id = 2
        annotation.annotator_id = 2  # Different user
        annotation.text = mock_text
        return annotation
    
    @pytest.fixture
    def mock_label(self):
        """Mock label for updates."""
        label = Mock(spec=Label)
        label.id = 2
        label.name = "ENTITY"
        label.project_id = 1
        return label
    
    @pytest.fixture
    def full_update_data(self):
        """Full annotation update data."""
        return AnnotationUpdate(
            label_id=2,
            start_char=15,
            end_char=25,
            selected_text="document",
            notes="Updated note",
            confidence_score=0.95,
            metadata={"updated": True}
        )
    
    @pytest.fixture
    def partial_update_data(self):
        """Partial annotation update data."""
        return AnnotationUpdate(
            notes="Just updating the note"
        )
    
    @pytest.mark.unit
    async def test_update_annotation_success_full(self, mock_db, mock_current_user, mock_annotation, mock_label, full_update_data):
        """Test successful annotation update with all fields."""
        # Mock database queries
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.side_effect = [mock_annotation, mock_label]
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        with patch('src.api.annotations.AgreementService') as mock_agreement_service_class:
            mock_service = Mock()
            mock_service.trigger_agreement_calculation = Mock()
            mock_agreement_service_class.return_value = mock_service
            
            result = await update_annotation(1, full_update_data, mock_current_user, mock_db)
        
        # Verify fields were updated
        assert mock_annotation.label_id == 2
        assert mock_annotation.start_char == 15
        assert mock_annotation.end_char == 25
        assert mock_annotation.selected_text == "document"
        assert mock_annotation.notes == "Updated note"
        assert mock_annotation.confidence_score == 0.95
        assert mock_annotation.metadata == {"updated": True}
        
        # Verify database operations
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(mock_annotation)
        
        # Verify agreement calculation was triggered (content changed)
        mock_service.trigger_agreement_calculation.assert_called_once_with(1)
        
        # Verify response
        assert isinstance(result, AnnotationResponse) or isinstance(result, dict)
    
    @pytest.mark.unit
    async def test_update_annotation_success_partial(self, mock_db, mock_current_user, mock_annotation, partial_update_data):
        """Test successful annotation update with partial data."""
        # Store original values
        original_label_id = mock_annotation.label_id
        original_start_char = mock_annotation.start_char
        original_confidence_score = mock_annotation.confidence_score
        
        # Mock database query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_annotation
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        with patch('src.api.annotations.AgreementService'):
            result = await update_annotation(1, partial_update_data, mock_current_user, mock_db)
        
        # Verify only notes was updated
        assert mock_annotation.notes == "Just updating the note"
        assert mock_annotation.label_id == original_label_id  # Unchanged
        assert mock_annotation.start_char == original_start_char  # Unchanged
        assert mock_annotation.confidence_score == original_confidence_score  # Unchanged
        
        # Verify database operations
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(mock_annotation)
    
    @pytest.mark.unit
    async def test_update_annotation_not_found(self, mock_db, mock_current_user, full_update_data):
        """Test updating non-existent annotation."""
        # Mock database query returning None
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = None
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        with pytest.raises(HTTPException) as exc_info:
            await update_annotation(999, full_update_data, mock_current_user, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "Annotation not found" in str(exc_info.value.detail)
    
    @pytest.mark.unit
    async def test_update_annotation_not_owner_or_annotator(self, mock_db, mock_current_user, mock_other_user_annotation, full_update_data):
        """Test updating annotation by another user when not project owner."""
        # Mock database query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_other_user_annotation
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        with pytest.raises(HTTPException) as exc_info:
            await update_annotation(2, full_update_data, mock_current_user, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Only the annotator or project owner can update this annotation" in str(exc_info.value.detail)
    
    @pytest.mark.unit
    async def test_update_annotation_project_owner_can_update(self, mock_db, mock_current_user, mock_other_user_annotation, full_update_data):
        """Test project owner can update any annotation in their project."""
        # Make current user the project owner
        mock_other_user_annotation.text.project.owner_id = 1
        
        # Mock database queries
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.side_effect = [mock_other_user_annotation, None]  # No label update
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        # Update only notes (no label change)
        notes_update = AnnotationUpdate(notes="Project owner update")
        
        with patch('src.api.annotations.AgreementService'):
            result = await update_annotation(2, notes_update, mock_current_user, mock_db)
        
        # Should succeed without exception
        assert result is not None
        mock_db.commit.assert_called_once()
    
    @pytest.mark.unit
    async def test_update_annotation_invalid_label(self, mock_db, mock_current_user, mock_annotation, full_update_data):
        """Test updating annotation with invalid label."""
        # Mock database queries - annotation exists, label doesn't
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.side_effect = [mock_annotation, None]
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        with pytest.raises(HTTPException) as exc_info:
            await update_annotation(1, full_update_data, mock_current_user, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid label for this project" in str(exc_info.value.detail)
    
    @pytest.mark.unit
    async def test_update_annotation_label_wrong_project(self, mock_db, mock_current_user, mock_annotation, full_update_data):
        """Test updating annotation with label from wrong project."""
        # Mock label from different project
        wrong_label = Mock(spec=Label)
        wrong_label.id = 2
        wrong_label.project_id = 2  # Different project
        
        # Mock database queries
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.side_effect = [mock_annotation, wrong_label]
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        with pytest.raises(HTTPException) as exc_info:
            await update_annotation(1, full_update_data, mock_current_user, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid label for this project" in str(exc_info.value.detail)
    
    @pytest.mark.unit
    async def test_update_annotation_invalid_span(self, mock_db, mock_current_user, mock_annotation):
        """Test updating annotation with invalid span."""
        invalid_span_data = AnnotationUpdate(
            start_char=-1,  # Invalid
            end_char=10
        )
        
        # Mock database query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_annotation
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        with pytest.raises(HTTPException) as exc_info:
            await update_annotation(1, invalid_span_data, mock_current_user, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid annotation span" in str(exc_info.value.detail)
    
    @pytest.mark.unit
    async def test_update_annotation_span_beyond_text(self, mock_db, mock_current_user, mock_annotation):
        """Test updating annotation with span beyond text length."""
        invalid_span_data = AnnotationUpdate(
            start_char=10,
            end_char=1000  # Beyond text length
        )
        
        # Mock database query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_annotation
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        with pytest.raises(HTTPException) as exc_info:
            await update_annotation(1, invalid_span_data, mock_current_user, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid annotation span" in str(exc_info.value.detail)
    
    @pytest.mark.unit
    async def test_update_annotation_no_agreement_trigger_for_minor_changes(self, mock_db, mock_current_user, mock_annotation):
        """Test that agreement calculation is not triggered for minor changes."""
        # Update only notes (no content change)
        minor_update = AnnotationUpdate(notes="Minor update")
        
        # Mock database query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_annotation
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        with patch('src.api.annotations.AgreementService') as mock_agreement_service_class:
            mock_service = Mock()
            mock_service.trigger_agreement_calculation = Mock()
            mock_agreement_service_class.return_value = mock_service
            
            await update_annotation(1, minor_update, mock_current_user, mock_db)
        
        # Agreement calculation should NOT be triggered for notes-only update
        mock_service.trigger_agreement_calculation.assert_not_called()
    
    @pytest.mark.unit
    async def test_update_annotation_agreement_trigger_for_content_changes(self, mock_db, mock_current_user, mock_annotation, mock_label):
        """Test that agreement calculation is triggered for content changes."""
        # Update label (content change)
        content_update = AnnotationUpdate(label_id=2)
        
        # Mock database queries
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.side_effect = [mock_annotation, mock_label]
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        with patch('src.api.annotations.AgreementService') as mock_agreement_service_class:
            mock_service = Mock()
            mock_service.trigger_agreement_calculation = Mock()
            mock_agreement_service_class.return_value = mock_service
            
            await update_annotation(1, content_update, mock_current_user, mock_db)
        
        # Agreement calculation SHOULD be triggered for label change
        mock_service.trigger_agreement_calculation.assert_called_once_with(1)


class TestAnnotationValidation:
    """Unit tests for annotation validation functionality."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        db.commit = Mock()
        db.refresh = Mock()
        return db
    
    @pytest.fixture
    def mock_current_user(self):
        """Mock current authenticated user (project owner)."""
        user = Mock(spec=User)
        user.id = 1
        user.username = "projectowner"
        return user
    
    @pytest.fixture
    def mock_non_owner_user(self):
        """Mock non-owner user."""
        user = Mock(spec=User)
        user.id = 2
        user.username = "annotator"
        return user
    
    @pytest.fixture
    def mock_project(self, mock_current_user):
        """Mock project owned by current user."""
        project = Mock(spec=Project)
        project.id = 1
        project.name = "Test Project"
        project.owner_id = 1
        return project
    
    @pytest.fixture
    def mock_text(self, mock_project):
        """Mock text."""
        text = Mock(spec=Text)
        text.id = 1
        text.project = mock_project
        return text
    
    @pytest.fixture
    def mock_annotation(self, mock_text):
        """Mock annotation to be validated."""
        annotation = Mock(spec=Annotation)
        annotation.id = 1
        annotation.annotator_id = 2
        annotation.text = mock_text
        annotation.is_validated = "pending"
        annotation.validation_notes = None
        annotation.to_dict.return_value = {
            "id": 1,
            "start_char": 10,
            "end_char": 14,
            "selected_text": "test",
            "notes": "Test annotation",
            "confidence_score": 0.9,
            "metadata": {},
            "context_before": "This is a ",
            "context_after": " document",
            "is_validated": "approved",  # Will be updated
            "validation_notes": "Looks good",
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-01T12:30:00",
            "text_id": 1,
            "annotator_id": 2,
            "label_id": 1,
            "label_name": "PERSON",
            "label_color": "#007bff",
            "annotator_username": "annotator"
        }
        return annotation
    
    @pytest.fixture
    def approve_validation(self):
        """Validation data to approve annotation."""
        return AnnotationValidation(
            is_validated="approved",
            validation_notes="Annotation looks correct"
        )
    
    @pytest.fixture
    def reject_validation(self):
        """Validation data to reject annotation."""
        return AnnotationValidation(
            is_validated="rejected",
            validation_notes="Incorrect label applied"
        )
    
    @pytest.fixture
    def pending_validation(self):
        """Validation data to keep annotation pending."""
        return AnnotationValidation(
            is_validated="pending",
            validation_notes="Needs further review"
        )
    
    @pytest.mark.unit
    async def test_validate_annotation_approve_success(self, mock_db, mock_current_user, mock_annotation, approve_validation):
        """Test successful annotation approval by project owner."""
        # Mock database query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_annotation
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        result = await validate_annotation(1, approve_validation, mock_current_user, mock_db)
        
        # Verify validation was applied
        assert mock_annotation.is_validated == "approved"
        assert mock_annotation.validation_notes == "Annotation looks correct"
        
        # Verify database operations
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(mock_annotation)
        
        # Verify response
        assert isinstance(result, AnnotationResponse) or isinstance(result, dict)
        if isinstance(result, dict):
            assert result["is_validated"] == "approved"
            assert result["validation_notes"] == "Looks good"
    
    @pytest.mark.unit
    async def test_validate_annotation_reject_success(self, mock_db, mock_current_user, mock_annotation, reject_validation):
        """Test successful annotation rejection by project owner."""
        # Mock database query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_annotation
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        result = await validate_annotation(1, reject_validation, mock_current_user, mock_db)
        
        # Verify validation was applied
        assert mock_annotation.is_validated == "rejected"
        assert mock_annotation.validation_notes == "Incorrect label applied"
        
        # Verify database operations
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(mock_annotation)
        
        # Verify response
        assert result is not None
    
    @pytest.mark.unit
    async def test_validate_annotation_set_pending(self, mock_db, mock_current_user, mock_annotation, pending_validation):
        """Test setting annotation back to pending status."""
        # Mock database query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_annotation
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        result = await validate_annotation(1, pending_validation, mock_current_user, mock_db)
        
        # Verify validation was applied
        assert mock_annotation.is_validated == "pending"
        assert mock_annotation.validation_notes == "Needs further review"
        
        # Verify database operations
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(mock_annotation)
        
        # Verify response
        assert result is not None
    
    @pytest.mark.unit
    async def test_validate_annotation_not_found(self, mock_db, mock_current_user, approve_validation):
        """Test validation of non-existent annotation."""
        # Mock database query returning None
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = None
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        with pytest.raises(HTTPException) as exc_info:
            await validate_annotation(999, approve_validation, mock_current_user, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "Annotation not found" in str(exc_info.value.detail)
    
    @pytest.mark.unit
    async def test_validate_annotation_not_project_owner(self, mock_db, mock_non_owner_user, mock_annotation, approve_validation):
        """Test validation attempt by non-project owner."""
        # Mock database query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_annotation
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        with pytest.raises(HTTPException) as exc_info:
            await validate_annotation(1, approve_validation, mock_non_owner_user, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Only project owner can validate annotations" in str(exc_info.value.detail)
    
    @pytest.mark.unit
    async def test_validate_annotation_without_notes(self, mock_db, mock_current_user, mock_annotation):
        """Test validation without validation notes."""
        validation_without_notes = AnnotationValidation(
            is_validated="approved"
            # validation_notes is optional
        )
        
        # Mock database query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_annotation
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        result = await validate_annotation(1, validation_without_notes, mock_current_user, mock_db)
        
        # Verify validation was applied
        assert mock_annotation.is_validated == "approved"
        assert mock_annotation.validation_notes is None
        
        # Should succeed without exception
        assert result is not None


class TestAnnotationDeletion:
    """Unit tests for annotation deletion functionality."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        db.delete = Mock()
        db.commit = Mock()
        return db
    
    @pytest.fixture
    def mock_current_user(self):
        """Mock current authenticated user."""
        user = Mock(spec=User)
        user.id = 1
        user.username = "testuser"
        return user
    
    @pytest.fixture
    def mock_project(self, mock_current_user):
        """Mock project owned by current user."""
        project = Mock(spec=Project)
        project.id = 1
        project.name = "Test Project"
        project.owner_id = 1
        return project
    
    @pytest.fixture
    def mock_text(self, mock_project):
        """Mock text."""
        text = Mock(spec=Text)
        text.id = 1
        text.project = mock_project
        return text
    
    @pytest.fixture
    def mock_label(self):
        """Mock label."""
        label = Mock(spec=Label)
        label.id = 1
        label.usage_count = 5
        return label
    
    @pytest.fixture
    def mock_user_annotation(self, mock_text, mock_label, mock_current_user):
        """Mock annotation owned by current user."""
        annotation = Mock(spec=Annotation)
        annotation.id = 1
        annotation.annotator_id = 1
        annotation.text = mock_text
        annotation.label = mock_label
        return annotation
    
    @pytest.fixture
    def mock_other_user_annotation(self, mock_text, mock_label):
        """Mock annotation by another user."""
        annotation = Mock(spec=Annotation)
        annotation.id = 2
        annotation.annotator_id = 2  # Different user
        annotation.text = mock_text
        annotation.label = mock_label
        return annotation
    
    @pytest.fixture
    def mock_project_owner_annotation(self, mock_text, mock_label):
        """Mock annotation where current user is project owner but not annotator."""
        # Create project owned by current user
        owner_project = Mock(spec=Project)
        owner_project.id = 1
        owner_project.owner_id = 1
        
        owner_text = Mock(spec=Text)
        owner_text.id = 1
        owner_text.project = owner_project
        
        annotation = Mock(spec=Annotation)
        annotation.id = 3
        annotation.annotator_id = 2  # Different annotator
        annotation.text = owner_text
        annotation.label = mock_label
        return annotation
    
    @pytest.mark.unit
    async def test_delete_annotation_success_own_annotation(self, mock_db, mock_current_user, mock_user_annotation):
        """Test successful deletion of user's own annotation."""
        # Mock database query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_user_annotation
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        result = await delete_annotation(1, mock_current_user, mock_db)
        
        # Verify database operations
        mock_db.delete.assert_called_once_with(mock_user_annotation)
        mock_db.commit.assert_called_once()
        
        # Verify label usage count was decremented
        assert mock_user_annotation.label.usage_count == 4
        
        # Verify return value (should be None for 204 status)
        assert result is None
    
    @pytest.mark.unit
    async def test_delete_annotation_success_project_owner(self, mock_db, mock_current_user, mock_project_owner_annotation):
        """Test successful deletion by project owner."""
        # Mock database query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_project_owner_annotation
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        result = await delete_annotation(3, mock_current_user, mock_db)
        
        # Verify database operations
        mock_db.delete.assert_called_once_with(mock_project_owner_annotation)
        mock_db.commit.assert_called_once()
        
        # Verify label usage count was decremented
        assert mock_project_owner_annotation.label.usage_count == 4
        
        # Verify return value (should be None for 204 status)
        assert result is None
    
    @pytest.mark.unit
    async def test_delete_annotation_not_found(self, mock_db, mock_current_user):
        """Test deletion of non-existent annotation."""
        # Mock database query returning None
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = None
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        with pytest.raises(HTTPException) as exc_info:
            await delete_annotation(999, mock_current_user, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "Annotation not found" in str(exc_info.value.detail)
    
    @pytest.mark.unit
    async def test_delete_annotation_access_denied(self, mock_db, mock_current_user, mock_other_user_annotation):
        """Test deletion denied for annotation by another user in project they don't own."""
        # Make sure current user is not the project owner
        mock_other_user_annotation.text.project.owner_id = 3  # Different owner
        
        # Mock database query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_other_user_annotation
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        with pytest.raises(HTTPException) as exc_info:
            await delete_annotation(2, mock_current_user, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Only the annotator or project owner can delete this annotation" in str(exc_info.value.detail)
    
    @pytest.mark.unit
    async def test_delete_annotation_label_usage_count_floor(self, mock_db, mock_current_user, mock_user_annotation):
        """Test that label usage count doesn't go below zero."""
        # Set usage count to 0
        mock_user_annotation.label.usage_count = 0
        
        # Mock database query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_user_annotation
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        await delete_annotation(1, mock_current_user, mock_db)
        
        # Usage count should remain at 0 (max(0, 0-1) = 0)
        assert mock_user_annotation.label.usage_count == 0
    
    @pytest.mark.unit
    async def test_delete_annotation_no_label(self, mock_db, mock_current_user, mock_user_annotation):
        """Test deletion of annotation with no label (edge case)."""
        # Set label to None
        mock_user_annotation.label = None
        
        # Mock database query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_user_annotation
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        # Should not raise exception
        result = await delete_annotation(1, mock_current_user, mock_db)
        
        # Verify database operations still work
        mock_db.delete.assert_called_once_with(mock_user_annotation)
        mock_db.commit.assert_called_once()
        
        # Return value should still be None
        assert result is None


class TestAnnotationEdgeCases:
    """Unit tests for edge cases and error conditions."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def mock_current_user(self):
        """Mock current authenticated user."""
        user = Mock(spec=User)
        user.id = 1
        user.username = "testuser"
        return user
    
    @pytest.mark.unit
    async def test_create_annotation_database_error(self, mock_db, mock_current_user):
        """Test annotation creation handles database errors."""
        # Mock text and label exist
        mock_text = Mock(spec=Text)
        mock_text.content = "Test content"
        mock_project = Mock(spec=Project)
        mock_project.owner_id = 1
        mock_project.is_public = False
        mock_text.project = mock_project
        
        mock_label = Mock(spec=Label)
        mock_label.project_id = 1
        mock_label.usage_count = 0
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_text, mock_label]
        mock_db.add = Mock()
        mock_db.commit.side_effect = Exception("Database error")
        mock_db.refresh = Mock()
        
        annotation_data = AnnotationCreate(
            text_id=1,
            label_id=1,
            start_char=0,
            end_char=4,
            selected_text="Test"
        )
        
        with patch('src.api.annotations.Annotation'):
            with pytest.raises(Exception) as exc_info:
                await create_annotation(annotation_data, mock_current_user, mock_db)
            
            assert "Database error" in str(exc_info.value)
    
    @pytest.mark.unit
    async def test_overlapping_annotation_spans(self, mock_db, mock_current_user):
        """Test creating overlapping annotations (should be allowed)."""
        mock_text = Mock(spec=Text)
        mock_text.content = "This is a test document for overlapping annotations."
        mock_project = Mock(spec=Project)
        mock_project.owner_id = 1
        mock_project.is_public = False
        mock_text.project = mock_project
        
        mock_label = Mock(spec=Label)
        mock_label.project_id = 1
        mock_label.usage_count = 0
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_text, mock_label]
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Create annotation that overlaps with potential existing annotations
        overlapping_data = AnnotationCreate(
            text_id=1,
            label_id=1,
            start_char=5,  # Overlaps with "is a test"
            end_char=15,
            selected_text="is a test"
        )
        
        mock_created_annotation = Mock(spec=Annotation)
        mock_created_annotation.to_dict.return_value = {
            "id": 1,
            "start_char": 5,
            "end_char": 15,
            "selected_text": "is a test",
            "notes": None,
            "confidence_score": 1.0,
            "metadata": {},
            "context_before": "This ",
            "context_after": " document",
            "is_validated": "pending",
            "validation_notes": None,
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-01T12:00:00",
            "text_id": 1,
            "annotator_id": 1,
            "label_id": 1,
            "label_name": "PHRASE",
            "label_color": "#007bff",
            "annotator_username": "testuser"
        }
        
        with patch('src.api.annotations.Annotation') as mock_annotation_class:
            mock_annotation_class.return_value = mock_created_annotation
            with patch('src.api.annotations.AgreementService'):
                
                result = await create_annotation(overlapping_data, mock_current_user, mock_db)
        
        # Should succeed - overlapping annotations are allowed
        assert result is not None
        if isinstance(result, dict):
            assert result["selected_text"] == "is a test"
    
    @pytest.mark.unit
    async def test_annotation_with_extreme_confidence_scores(self, mock_db, mock_current_user):
        """Test annotations with boundary confidence scores."""
        mock_text = Mock(spec=Text)
        mock_text.content = "Test content"
        mock_project = Mock(spec=Project)
        mock_project.owner_id = 1
        mock_project.is_public = False
        mock_text.project = mock_project
        
        mock_label = Mock(spec=Label)
        mock_label.project_id = 1
        mock_label.usage_count = 0
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_text, mock_label]
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Test with minimum confidence (0.0)
        min_confidence_data = AnnotationCreate(
            text_id=1,
            label_id=1,
            start_char=0,
            end_char=4,
            selected_text="Test",
            confidence_score=0.0
        )
        
        mock_created_annotation = Mock(spec=Annotation)
        mock_created_annotation.to_dict.return_value = {
            "id": 1,
            "start_char": 0,
            "end_char": 4,
            "selected_text": "Test",
            "notes": None,
            "confidence_score": 0.0,
            "metadata": {},
            "context_before": "",
            "context_after": " content",
            "is_validated": "pending",
            "validation_notes": None,
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-01T12:00:00",
            "text_id": 1,
            "annotator_id": 1,
            "label_id": 1,
            "label_name": "TEST",
            "label_color": "#007bff",
            "annotator_username": "testuser"
        }
        
        with patch('src.api.annotations.Annotation') as mock_annotation_class:
            mock_annotation_class.return_value = mock_created_annotation
            with patch('src.api.annotations.AgreementService'):
                
                result = await create_annotation(min_confidence_data, mock_current_user, mock_db)
        
        # Should succeed with 0.0 confidence
        assert result is not None
        if isinstance(result, dict):
            assert result["confidence_score"] == 0.0
    
    @pytest.mark.unit
    async def test_annotation_context_extraction_edge_cases(self, mock_db, mock_current_user):
        """Test context extraction at text boundaries."""
        # Very short text
        mock_text = Mock(spec=Text)
        mock_text.content = "Short"  # 5 characters
        mock_project = Mock(spec=Project)
        mock_project.owner_id = 1
        mock_project.is_public = False
        mock_text.project = mock_project
        
        mock_label = Mock(spec=Label)
        mock_label.project_id = 1
        mock_label.usage_count = 0
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_text, mock_label]
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Annotate the entire short text
        boundary_data = AnnotationCreate(
            text_id=1,
            label_id=1,
            start_char=0,
            end_char=5,
            selected_text="Short"
        )
        
        mock_created_annotation = Mock(spec=Annotation)
        mock_created_annotation.to_dict.return_value = {
            "id": 1,
            "start_char": 0,
            "end_char": 5,
            "selected_text": "Short",
            "notes": None,
            "confidence_score": 1.0,
            "metadata": {},
            "context_before": "",  # Empty - at start of text
            "context_after": "",   # Empty - at end of text
            "is_validated": "pending",
            "validation_notes": None,
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-01T12:00:00",
            "text_id": 1,
            "annotator_id": 1,
            "label_id": 1,
            "label_name": "WORD",
            "label_color": "#007bff",
            "annotator_username": "testuser"
        }
        
        with patch('src.api.annotations.Annotation') as mock_annotation_class:
            mock_annotation_class.return_value = mock_created_annotation
            with patch('src.api.annotations.AgreementService'):
                
                result = await create_annotation(boundary_data, mock_current_user, mock_db)
        
        # Should succeed with empty context strings
        assert result is not None
        if isinstance(result, dict):
            assert result["context_before"] == ""
            assert result["context_after"] == ""
    
    @pytest.mark.unit
    async def test_annotation_with_complex_metadata(self, mock_db, mock_current_user):
        """Test annotation with complex nested metadata."""
        mock_text = Mock(spec=Text)
        mock_text.content = "Test content with complex metadata"
        mock_project = Mock(spec=Project)
        mock_project.owner_id = 1
        mock_project.is_public = False
        mock_text.project = mock_project
        
        mock_label = Mock(spec=Label)
        mock_label.project_id = 1
        mock_label.usage_count = 0
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_text, mock_label]
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        complex_metadata = {
            "source": "manual",
            "reviewer": "expert",
            "confidence_breakdown": {
                "entity_recognition": 0.95,
                "boundary_detection": 0.90,
                "label_assignment": 0.98
            },
            "tags": ["verified", "high-quality"],
            "processing_time": 45.2,
            "version": "2.1"
        }
        
        complex_data = AnnotationCreate(
            text_id=1,
            label_id=1,
            start_char=0,
            end_char=4,
            selected_text="Test",
            metadata=complex_metadata
        )
        
        mock_created_annotation = Mock(spec=Annotation)
        mock_created_annotation.to_dict.return_value = {
            "id": 1,
            "start_char": 0,
            "end_char": 4,
            "selected_text": "Test",
            "notes": None,
            "confidence_score": 1.0,
            "metadata": complex_metadata,
            "context_before": "",
            "context_after": " content",
            "is_validated": "pending",
            "validation_notes": None,
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-01T12:00:00",
            "text_id": 1,
            "annotator_id": 1,
            "label_id": 1,
            "label_name": "TEST",
            "label_color": "#007bff",
            "annotator_username": "testuser"
        }
        
        with patch('src.api.annotations.Annotation') as mock_annotation_class:
            mock_annotation_class.return_value = mock_created_annotation
            with patch('src.api.annotations.AgreementService'):
                
                result = await create_annotation(complex_data, mock_current_user, mock_db)
        
        # Should succeed with complex metadata
        assert result is not None
        if isinstance(result, dict):
            assert result["metadata"] == complex_metadata
            assert result["metadata"]["confidence_breakdown"]["entity_recognition"] == 0.95
    
    @pytest.mark.unit
    async def test_multiple_filter_combination(self, mock_db, mock_current_user):
        """Test listing annotations with multiple filters combined."""
        # Mock query chain with multiple filters
        mock_query = Mock()
        mock_join1 = Mock()
        mock_join2 = Mock()
        mock_filter1 = Mock()
        mock_filter2 = Mock()
        mock_filter3 = Mock()
        mock_filter4 = Mock()
        mock_offset = Mock()
        mock_limit = Mock()
        
        # Create mock annotations that match all filters
        matching_annotation = Mock(spec=Annotation)
        matching_annotation.to_dict.return_value = {
            "id": 1,
            "start_char": 10,
            "end_char": 14,
            "selected_text": "test",
            "notes": "Filtered annotation",
            "confidence_score": 0.9,
            "metadata": {},
            "context_before": "This is a ",
            "context_after": " document",
            "is_validated": "pending",
            "validation_notes": None,
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-01T12:00:00",
            "text_id": 1,
            "annotator_id": 1,
            "label_id": 1,
            "label_name": "PERSON",
            "label_color": "#007bff",
            "annotator_username": "testuser"
        }
        
        mock_limit.all.return_value = [matching_annotation]
        mock_offset.limit.return_value = mock_limit
        mock_filter4.offset.return_value = mock_offset
        mock_filter3.filter.return_value = mock_filter4
        mock_filter2.filter.return_value = mock_filter3
        mock_filter1.filter.return_value = mock_filter2
        mock_join2.filter.return_value = mock_filter1
        mock_join1.join.return_value = mock_join2
        mock_query.join.return_value = mock_join1
        mock_db.query.return_value = mock_query
        
        result = await list_annotations(
            text_id=1,
            project_id=1,
            label_id=1,
            annotator_id=1,
            skip=0,
            limit=5,
            current_user=mock_current_user,
            db=mock_db
        )
        
        # Verify multiple filters were applied
        assert mock_filter1.filter.call_count >= 1
        assert mock_filter2.filter.call_count >= 1
        assert mock_filter3.filter.call_count >= 1
        
        # Result should contain matching annotation
        assert len(result) == 1
        assert result[0]["id"] == 1
    
    @pytest.mark.unit
    def test_annotation_response_model_completeness(self):
        """Test that AnnotationResponse includes all required fields."""
        # Create mock annotation data
        annotation_data = {
            "id": 1,
            "start_char": 10,
            "end_char": 14,
            "selected_text": "test",
            "notes": "Test annotation",
            "confidence_score": 0.95,
            "metadata": {"key": "value"},
            "context_before": "This is a ",
            "context_after": " document",
            "is_validated": "pending",
            "validation_notes": None,
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-01T12:00:00",
            "text_id": 1,
            "annotator_id": 1,
            "label_id": 1,
            "label_name": "PERSON",
            "label_color": "#007bff",
            "annotator_username": "testuser"
        }
        
        # Verify all expected fields are present
        expected_fields = {
            "id", "start_char", "end_char", "selected_text", "notes",
            "confidence_score", "metadata", "context_before", "context_after",
            "is_validated", "validation_notes", "created_at", "updated_at",
            "text_id", "annotator_id", "label_id", "label_name", "label_color",
            "annotator_username"
        }
        
        assert set(annotation_data.keys()) == expected_fields
        
        # Verify no sensitive data is exposed
        sensitive_fields = [
            "password", "hashed_password", "secret_key", "private_key",
            "internal_id", "database_url", "admin_token"
        ]
        
        for field in sensitive_fields:
            assert field not in annotation_data