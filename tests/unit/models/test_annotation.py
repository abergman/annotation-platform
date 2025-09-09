"""
Unit Tests for Annotation Model

Tests the Annotation model functionality including validation, relationships, and methods.
"""

import pytest
from datetime import datetime
from sqlalchemy.exc import IntegrityError

from src.models.annotation import Annotation


class TestAnnotationModel:
    """Test cases for Annotation model."""

    @pytest.mark.unit
    def test_create_annotation(self, test_db, test_text, test_user, test_label):
        """Test creating a new annotation."""
        annotation = Annotation(
            start_char=10,
            end_char=25,
            selected_text="sample text",
            notes="This is a test annotation",
            text_id=test_text.id,
            annotator_id=test_user.id,
            label_id=test_label.id
        )
        test_db.add(annotation)
        test_db.commit()
        test_db.refresh(annotation)

        assert annotation.id is not None
        assert annotation.start_char == 10
        assert annotation.end_char == 25
        assert annotation.selected_text == "sample text"
        assert annotation.notes == "This is a test annotation"
        assert annotation.text_id == test_text.id
        assert annotation.annotator_id == test_user.id
        assert annotation.label_id == test_label.id
        assert annotation.confidence_score == 1.0  # Default value
        assert annotation.is_validated == "pending"  # Default value
        assert annotation.created_at is not None
        assert isinstance(annotation.created_at, datetime)

    @pytest.mark.unit
    def test_annotation_required_fields(self, test_db, test_text, test_user, test_label):
        """Test annotation with only required fields."""
        annotation = Annotation(
            start_char=0,
            end_char=5,
            selected_text="Hello",
            text_id=test_text.id,
            annotator_id=test_user.id,
            label_id=test_label.id
        )
        test_db.add(annotation)
        test_db.commit()
        test_db.refresh(annotation)

        assert annotation.start_char == 0
        assert annotation.end_char == 5
        assert annotation.selected_text == "Hello"
        assert annotation.notes is None
        assert annotation.confidence_score == 1.0

    @pytest.mark.unit
    def test_annotation_relationships(self, test_db, test_annotation):
        """Test annotation relationships."""
        # Test forward relationships
        assert test_annotation.text is not None
        assert test_annotation.annotator is not None
        assert test_annotation.label is not None

        assert test_annotation.text.id == test_annotation.text_id
        assert test_annotation.annotator.id == test_annotation.annotator_id
        assert test_annotation.label.id == test_annotation.label_id

        # Test backward relationships
        assert test_annotation in test_annotation.text.annotations
        assert test_annotation in test_annotation.annotator.annotations
        assert test_annotation in test_annotation.label.annotations

    @pytest.mark.unit
    def test_annotation_to_dict(self, test_annotation):
        """Test annotation to_dict method."""
        annotation_dict = test_annotation.to_dict()
        
        required_fields = [
            "id", "start_char", "end_char", "selected_text", "notes",
            "confidence_score", "metadata", "context_before", "context_after",
            "is_validated", "validation_notes", "created_at", "updated_at",
            "text_id", "annotator_id", "label_id", "label_name", 
            "label_color", "annotator_username"
        ]
        
        for field in required_fields:
            assert field in annotation_dict
        
        assert isinstance(annotation_dict["id"], int)
        assert isinstance(annotation_dict["start_char"], int)
        assert isinstance(annotation_dict["end_char"], int)
        assert isinstance(annotation_dict["confidence_score"], float)

    @pytest.mark.unit
    def test_annotation_repr(self, test_annotation):
        """Test annotation string representation."""
        repr_str = repr(test_annotation)
        assert "Annotation" in repr_str
        assert str(test_annotation.id) in repr_str
        assert str(test_annotation.text_id) in repr_str
        assert str(test_annotation.label_id) in repr_str

    @pytest.mark.unit
    def test_annotation_confidence_score(self, test_db, test_text, test_user, test_label):
        """Test annotation confidence scoring."""
        annotation = Annotation(
            start_char=0,
            end_char=10,
            selected_text="test text",
            confidence_score=0.75,
            text_id=test_text.id,
            annotator_id=test_user.id,
            label_id=test_label.id
        )
        test_db.add(annotation)
        test_db.commit()
        test_db.refresh(annotation)

        assert annotation.confidence_score == 0.75

    @pytest.mark.unit
    def test_annotation_validation_states(self, test_db, test_text, test_user, test_label):
        """Test annotation validation states."""
        states = ["pending", "approved", "rejected"]
        
        for state in states:
            annotation = Annotation(
                start_char=0,
                end_char=5,
                selected_text="test",
                is_validated=state,
                text_id=test_text.id,
                annotator_id=test_user.id,
                label_id=test_label.id
            )
            test_db.add(annotation)
            test_db.commit()
            test_db.refresh(annotation)
            
            assert annotation.is_validated == state

    @pytest.mark.unit
    def test_annotation_context(self, test_db, test_text, test_user, test_label):
        """Test annotation context information."""
        annotation = Annotation(
            start_char=10,
            end_char=20,
            selected_text="annotation",
            context_before="This is a test",
            context_after="for the system",
            text_id=test_text.id,
            annotator_id=test_user.id,
            label_id=test_label.id
        )
        test_db.add(annotation)
        test_db.commit()
        test_db.refresh(annotation)

        assert annotation.context_before == "This is a test"
        assert annotation.context_after == "for the system"

    @pytest.mark.unit
    def test_annotation_metadata(self, test_db, test_text, test_user, test_label):
        """Test annotation metadata functionality."""
        metadata = {
            "annotator_notes": "High confidence annotation",
            "review_status": "needs_review",
            "difficulty": "medium"
        }
        
        annotation = Annotation(
            start_char=0,
            end_char=10,
            selected_text="metadata",
            metadata=metadata,
            text_id=test_text.id,
            annotator_id=test_user.id,
            label_id=test_label.id
        )
        test_db.add(annotation)
        test_db.commit()
        test_db.refresh(annotation)

        assert annotation.metadata == metadata
        assert annotation.metadata["difficulty"] == "medium"

    @pytest.mark.unit
    def test_annotation_validation_workflow(self, test_db, test_text, test_user, test_label):
        """Test annotation validation workflow."""
        annotation = Annotation(
            start_char=0,
            end_char=10,
            selected_text="validate",
            is_validated="pending",
            text_id=test_text.id,
            annotator_id=test_user.id,
            label_id=test_label.id
        )
        test_db.add(annotation)
        test_db.commit()
        test_db.refresh(annotation)

        assert annotation.is_validated == "pending"

        # Approve annotation
        annotation.is_validated = "approved"
        annotation.validation_notes = "Annotation is accurate"
        test_db.commit()
        test_db.refresh(annotation)

        assert annotation.is_validated == "approved"
        assert annotation.validation_notes == "Annotation is accurate"

        # Reject annotation
        annotation.is_validated = "rejected"
        annotation.validation_notes = "Annotation span is incorrect"
        test_db.commit()
        test_db.refresh(annotation)

        assert annotation.is_validated == "rejected"
        assert annotation.validation_notes == "Annotation span is incorrect"

    @pytest.mark.unit
    def test_annotation_char_positions(self, test_db, test_text, test_user, test_label):
        """Test annotation character position validation."""
        # Valid positions
        annotation = Annotation(
            start_char=0,
            end_char=5,
            selected_text="Hello",
            text_id=test_text.id,
            annotator_id=test_user.id,
            label_id=test_label.id
        )
        test_db.add(annotation)
        test_db.commit()
        test_db.refresh(annotation)

        assert annotation.start_char < annotation.end_char
        assert annotation.start_char >= 0

    @pytest.mark.unit
    def test_annotation_timestamps(self, test_db, test_text, test_user, test_label):
        """Test annotation timestamp functionality."""
        annotation = Annotation(
            start_char=0,
            end_char=10,
            selected_text="timestamp",
            notes="Original note",
            text_id=test_text.id,
            annotator_id=test_user.id,
            label_id=test_label.id
        )
        test_db.add(annotation)
        test_db.commit()
        test_db.refresh(annotation)
        
        created_at = annotation.created_at
        updated_at = annotation.updated_at

        # Update annotation
        annotation.notes = "Updated note"
        test_db.commit()
        test_db.refresh(annotation)

        assert annotation.created_at == created_at  # Should not change
        assert annotation.updated_at > updated_at  # Should be updated

    @pytest.mark.unit
    def test_annotation_foreign_key_constraints(self, test_db):
        """Test foreign key constraints."""
        # Test with invalid text_id
        with pytest.raises(IntegrityError):
            annotation = Annotation(
                start_char=0,
                end_char=5,
                selected_text="test",
                text_id=99999,  # Non-existent
                annotator_id=1,
                label_id=1
            )
            test_db.add(annotation)
            test_db.commit()

    @pytest.mark.unit
    def test_annotation_edge_cases(self, test_db, test_text, test_user, test_label):
        """Test annotation edge cases."""
        # Zero-length annotation (just a position marker)
        annotation = Annotation(
            start_char=5,
            end_char=5,
            selected_text="",
            notes="Position marker",
            text_id=test_text.id,
            annotator_id=test_user.id,
            label_id=test_label.id
        )
        test_db.add(annotation)
        test_db.commit()
        test_db.refresh(annotation)

        assert annotation.start_char == annotation.end_char
        assert annotation.selected_text == ""

    @pytest.mark.unit
    def test_annotation_confidence_bounds(self, test_db, test_text, test_user, test_label):
        """Test annotation confidence score bounds."""
        # Minimum confidence
        min_annotation = Annotation(
            start_char=0,
            end_char=5,
            selected_text="min",
            confidence_score=0.0,
            text_id=test_text.id,
            annotator_id=test_user.id,
            label_id=test_label.id
        )
        test_db.add(min_annotation)
        test_db.commit()
        test_db.refresh(min_annotation)

        assert min_annotation.confidence_score == 0.0

        # Maximum confidence
        max_annotation = Annotation(
            start_char=0,
            end_char=5,
            selected_text="max",
            confidence_score=1.0,
            text_id=test_text.id,
            annotator_id=test_user.id,
            label_id=test_label.id
        )
        test_db.add(max_annotation)
        test_db.commit()
        test_db.refresh(max_annotation)

        assert max_annotation.confidence_score == 1.0

    @pytest.mark.unit
    def test_annotation_long_notes(self, test_db, test_text, test_user, test_label):
        """Test annotation with long notes."""
        long_notes = "This is a very long annotation note. " * 100
        
        annotation = Annotation(
            start_char=0,
            end_char=10,
            selected_text="long notes",
            notes=long_notes,
            text_id=test_text.id,
            annotator_id=test_user.id,
            label_id=test_label.id
        )
        test_db.add(annotation)
        test_db.commit()
        test_db.refresh(annotation)

        assert annotation.notes == long_notes
        assert len(annotation.notes) > 3000