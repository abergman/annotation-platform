"""
Unit Tests for Text Model

Tests the Text model functionality including validation, relationships, and methods.
"""

import pytest
from datetime import datetime
from sqlalchemy.exc import IntegrityError

from src.models.text import Text


class TestTextModel:
    """Test cases for Text model."""

    @pytest.mark.unit
    def test_create_text(self, test_db, test_project):
        """Test creating a new text document."""
        text = Text(
            title="Test Document",
            content="This is a test document content for annotation purposes.",
            project_id=test_project.id
        )
        test_db.add(text)
        test_db.commit()
        test_db.refresh(text)

        assert text.id is not None
        assert text.title == "Test Document"
        assert text.content == "This is a test document content for annotation purposes."
        assert text.project_id == test_project.id
        assert text.language == "en"  # Default value
        assert text.is_processed == "pending"  # Default value
        assert text.created_at is not None
        assert isinstance(text.created_at, datetime)

    @pytest.mark.unit
    def test_text_required_fields(self, test_db, test_project):
        """Test text with only required fields."""
        text = Text(
            title="Minimal Text",
            content="Minimal content",
            project_id=test_project.id
        )
        test_db.add(text)
        test_db.commit()
        test_db.refresh(text)

        assert text.title == "Minimal Text"
        assert text.content == "Minimal content"
        assert text.project_id == test_project.id
        assert text.original_filename is None
        assert text.file_type is None

    @pytest.mark.unit
    def test_text_project_relationship(self, test_db, test_project):
        """Test text-project relationship."""
        text = Text(
            title="Relationship Test",
            content="Test content",
            project_id=test_project.id
        )
        test_db.add(text)
        test_db.commit()
        test_db.refresh(text)

        # Test forward relationship
        assert text.project.id == test_project.id
        assert text.project.name == test_project.name

        # Test backward relationship
        assert text in test_project.texts

    @pytest.mark.unit
    def test_text_to_dict_with_content(self, test_text):
        """Test text to_dict method with content included."""
        text_dict = test_text.to_dict(include_content=True)
        
        required_fields = [
            "id", "title", "content", "original_filename", "file_type",
            "file_size", "language", "word_count", "character_count",
            "metadata", "is_processed", "processing_notes", "created_at",
            "updated_at", "project_id", "annotation_count"
        ]
        
        for field in required_fields:
            assert field in text_dict
        
        assert "content" in text_dict
        assert isinstance(text_dict["id"], int)
        assert isinstance(text_dict["annotation_count"], int)

    @pytest.mark.unit
    def test_text_to_dict_without_content(self, test_text):
        """Test text to_dict method without content."""
        text_dict = test_text.to_dict(include_content=False)
        
        assert "content" not in text_dict
        assert "title" in text_dict
        assert "id" in text_dict

    @pytest.mark.unit
    def test_text_repr(self, test_text):
        """Test text string representation."""
        repr_str = repr(test_text)
        assert "Text" in repr_str
        assert str(test_text.id) in repr_str
        assert test_text.title[:50] in repr_str
        assert str(test_text.project_id) in repr_str

    @pytest.mark.unit
    def test_text_file_information(self, test_db, test_project):
        """Test text with file information."""
        text = Text(
            title="Uploaded Document",
            content="Content from uploaded file",
            original_filename="document.pdf",
            file_type="application/pdf",
            file_size=1024000,
            project_id=test_project.id
        )
        test_db.add(text)
        test_db.commit()
        test_db.refresh(text)

        assert text.original_filename == "document.pdf"
        assert text.file_type == "application/pdf"
        assert text.file_size == 1024000

    @pytest.mark.unit
    def test_text_language_setting(self, test_db, test_project):
        """Test text with different languages."""
        text = Text(
            title="Spanish Document",
            content="Este es un documento en español",
            language="es",
            project_id=test_project.id
        )
        test_db.add(text)
        test_db.commit()
        test_db.refresh(text)

        assert text.language == "es"

    @pytest.mark.unit
    def test_text_word_and_character_counts(self, test_db, test_project):
        """Test text with word and character counts."""
        content = "This is a test document with exactly ten words here."
        text = Text(
            title="Count Test",
            content=content,
            word_count=10,
            character_count=len(content),
            project_id=test_project.id
        )
        test_db.add(text)
        test_db.commit()
        test_db.refresh(text)

        assert text.word_count == 10
        assert text.character_count == len(content)

    @pytest.mark.unit
    def test_text_metadata(self, test_db, test_project):
        """Test text metadata functionality."""
        metadata = {
            "author": "Dr. Jane Smith",
            "publication_year": 2023,
            "journal": "Test Journal",
            "keywords": ["annotation", "NLP", "research"]
        }
        
        text = Text(
            title="Metadata Text",
            content="Text with metadata",
            metadata=metadata,
            project_id=test_project.id
        )
        test_db.add(text)
        test_db.commit()
        test_db.refresh(text)

        assert text.metadata == metadata
        assert text.metadata["author"] == "Dr. Jane Smith"
        assert "annotation" in text.metadata["keywords"]

    @pytest.mark.unit
    def test_text_processing_status(self, test_db, test_project):
        """Test text processing status tracking."""
        text = Text(
            title="Processing Test",
            content="Text to be processed",
            is_processed="processing",
            processing_notes="Currently extracting features",
            project_id=test_project.id
        )
        test_db.add(text)
        test_db.commit()
        test_db.refresh(text)

        assert text.is_processed == "processing"
        assert text.processing_notes == "Currently extracting features"

        # Update to completed
        text.is_processed = "completed"
        text.processing_notes = "Processing completed successfully"
        test_db.commit()
        test_db.refresh(text)

        assert text.is_processed == "completed"
        assert text.processing_notes == "Processing completed successfully"

    @pytest.mark.unit
    def test_text_processing_states(self, test_db, test_project):
        """Test all processing states."""
        states = ["pending", "processing", "completed", "failed"]
        
        for state in states:
            text = Text(
                title=f"State {state}",
                content="Test content",
                is_processed=state,
                project_id=test_project.id
            )
            test_db.add(text)
            test_db.commit()
            test_db.refresh(text)
            
            assert text.is_processed == state

    @pytest.mark.unit
    def test_text_timestamps(self, test_db, test_project):
        """Test text timestamp functionality."""
        text = Text(
            title="Timestamp Test",
            content="Original content",
            project_id=test_project.id
        )
        test_db.add(text)
        test_db.commit()
        test_db.refresh(text)
        
        created_at = text.created_at
        updated_at = text.updated_at

        # Update text
        text.content = "Updated content"
        test_db.commit()
        test_db.refresh(text)

        assert text.created_at == created_at  # Should not change
        assert text.updated_at > updated_at  # Should be updated

    @pytest.mark.unit
    def test_text_foreign_key_constraint(self, test_db):
        """Test foreign key constraint for project_id."""
        text = Text(
            title="Invalid Project Text",
            content="Test content",
            project_id=99999  # Non-existent project ID
        )
        test_db.add(text)
        
        with pytest.raises(IntegrityError):
            test_db.commit()

    @pytest.mark.unit
    def test_text_long_title(self, test_db, test_project):
        """Test text with maximum length title."""
        long_title = "A" * 500  # Maximum length
        
        text = Text(
            title=long_title,
            content="Test content",
            project_id=test_project.id
        )
        test_db.add(text)
        test_db.commit()
        test_db.refresh(text)

        assert text.title == long_title
        assert len(text.title) == 500

    @pytest.mark.unit
    def test_text_long_content(self, test_db, test_project):
        """Test text with very long content."""
        long_content = "This is a very long text content. " * 1000
        
        text = Text(
            title="Long Content Test",
            content=long_content,
            project_id=test_project.id
        )
        test_db.add(text)
        test_db.commit()
        test_db.refresh(text)

        assert text.content == long_content
        assert len(text.content) > 30000

    @pytest.mark.unit
    def test_text_default_metadata(self, test_db, test_project):
        """Test default metadata dictionary."""
        text = Text(
            title="Default Metadata Test",
            content="Test content",
            project_id=test_project.id
        )
        test_db.add(text)
        test_db.commit()
        test_db.refresh(text)

        assert text.metadata == {}
        assert isinstance(text.metadata, dict)

    @pytest.mark.unit
    def test_text_empty_content(self, test_db, test_project):
        """Test text with empty content."""
        text = Text(
            title="Empty Content Test",
            content="",
            project_id=test_project.id
        )
        test_db.add(text)
        test_db.commit()
        test_db.refresh(text)

        assert text.content == ""
        assert text.title == "Empty Content Test"