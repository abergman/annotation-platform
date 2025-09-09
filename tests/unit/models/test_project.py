"""
Unit Tests for Project Model

Tests the Project model functionality including validation, relationships, and methods.
"""

import pytest
from datetime import datetime
from sqlalchemy.exc import IntegrityError

from src.models.project import Project
from src.models.user import User


class TestProjectModel:
    """Test cases for Project model."""

    @pytest.mark.unit
    def test_create_project(self, test_db, test_user):
        """Test creating a new project."""
        project = Project(
            name="Test Project",
            description="A test project for annotation",
            annotation_guidelines="Test guidelines",
            owner_id=test_user.id
        )
        test_db.add(project)
        test_db.commit()
        test_db.refresh(project)

        assert project.id is not None
        assert project.name == "Test Project"
        assert project.description == "A test project for annotation"
        assert project.annotation_guidelines == "Test guidelines"
        assert project.owner_id == test_user.id
        assert project.allow_multiple_labels is True  # Default value
        assert project.require_all_texts is False  # Default value
        assert project.inter_annotator_agreement is False  # Default value
        assert project.is_active is True  # Default value
        assert project.is_public is False  # Default value
        assert project.created_at is not None
        assert isinstance(project.created_at, datetime)

    @pytest.mark.unit
    def test_project_required_fields(self, test_db, test_user):
        """Test project with only required fields."""
        project = Project(
            name="Minimal Project",
            owner_id=test_user.id
        )
        test_db.add(project)
        test_db.commit()
        test_db.refresh(project)

        assert project.name == "Minimal Project"
        assert project.description is None
        assert project.owner_id == test_user.id

    @pytest.mark.unit
    def test_project_owner_relationship(self, test_db, test_user):
        """Test project-owner relationship."""
        project = Project(
            name="Relationship Test",
            owner_id=test_user.id
        )
        test_db.add(project)
        test_db.commit()
        test_db.refresh(project)

        # Test forward relationship
        assert project.owner.id == test_user.id
        assert project.owner.username == test_user.username

        # Test backward relationship
        assert project in test_user.owned_projects

    @pytest.mark.unit
    def test_project_to_dict(self, test_project):
        """Test project to_dict method."""
        project_dict = test_project.to_dict()
        
        required_fields = [
            "id", "name", "description", "annotation_guidelines",
            "allow_multiple_labels", "require_all_texts", 
            "inter_annotator_agreement", "metadata", "is_active", 
            "is_public", "created_at", "updated_at", "owner_id",
            "text_count", "label_count"
        ]
        
        for field in required_fields:
            assert field in project_dict
        
        # Check data types
        assert isinstance(project_dict["id"], int)
        assert isinstance(project_dict["allow_multiple_labels"], bool)
        assert isinstance(project_dict["text_count"], int)
        assert isinstance(project_dict["label_count"], int)

    @pytest.mark.unit
    def test_project_repr(self, test_project):
        """Test project string representation."""
        repr_str = repr(test_project)
        assert "Project" in repr_str
        assert str(test_project.id) in repr_str
        assert test_project.name in repr_str
        assert str(test_project.owner_id) in repr_str

    @pytest.mark.unit
    def test_project_metadata(self, test_db, test_user):
        """Test project metadata functionality."""
        metadata = {
            "domain": "medical",
            "language": "english",
            "difficulty": "advanced"
        }
        
        project = Project(
            name="Metadata Project",
            metadata=metadata,
            owner_id=test_user.id
        )
        test_db.add(project)
        test_db.commit()
        test_db.refresh(project)

        assert project.metadata == metadata
        assert project.metadata["domain"] == "medical"

    @pytest.mark.unit
    def test_project_configuration_options(self, test_db, test_user):
        """Test project configuration options."""
        project = Project(
            name="Config Project",
            allow_multiple_labels=False,
            require_all_texts=True,
            inter_annotator_agreement=True,
            owner_id=test_user.id
        )
        test_db.add(project)
        test_db.commit()
        test_db.refresh(project)

        assert project.allow_multiple_labels is False
        assert project.require_all_texts is True
        assert project.inter_annotator_agreement is True

    @pytest.mark.unit
    def test_project_public_private(self, test_db, test_user):
        """Test project visibility settings."""
        # Private project (default)
        private_project = Project(
            name="Private Project",
            owner_id=test_user.id
        )
        test_db.add(private_project)
        test_db.commit()

        assert private_project.is_public is False

        # Public project
        public_project = Project(
            name="Public Project",
            is_public=True,
            owner_id=test_user.id
        )
        test_db.add(public_project)
        test_db.commit()

        assert public_project.is_public is True

    @pytest.mark.unit
    def test_project_active_status(self, test_db, test_user):
        """Test project active/inactive status."""
        project = Project(
            name="Status Project",
            owner_id=test_user.id
        )
        test_db.add(project)
        test_db.commit()

        assert project.is_active is True

        # Deactivate project
        project.is_active = False
        test_db.commit()
        test_db.refresh(project)

        assert project.is_active is False

    @pytest.mark.unit
    def test_project_timestamps(self, test_db, test_user):
        """Test project timestamp functionality."""
        project = Project(
            name="Timestamp Project",
            owner_id=test_user.id
        )
        test_db.add(project)
        test_db.commit()
        test_db.refresh(project)
        
        created_at = project.created_at
        updated_at = project.updated_at

        # Update project
        project.description = "Updated description"
        test_db.commit()
        test_db.refresh(project)

        assert project.created_at == created_at  # Should not change
        assert project.updated_at > updated_at  # Should be updated

    @pytest.mark.unit
    def test_project_foreign_key_constraint(self, test_db):
        """Test foreign key constraint for owner_id."""
        project = Project(
            name="Invalid Owner Project",
            owner_id=99999  # Non-existent user ID
        )
        test_db.add(project)
        
        with pytest.raises(IntegrityError):
            test_db.commit()

    @pytest.mark.unit
    def test_project_annotation_guidelines(self, test_db, test_user):
        """Test annotation guidelines field."""
        guidelines = """
        1. Read the text carefully
        2. Identify key concepts
        3. Apply appropriate labels
        4. Provide explanatory comments
        """
        
        project = Project(
            name="Guidelines Project",
            annotation_guidelines=guidelines,
            owner_id=test_user.id
        )
        test_db.add(project)
        test_db.commit()
        test_db.refresh(project)

        assert project.annotation_guidelines == guidelines

    @pytest.mark.unit
    def test_project_name_indexing(self, test_db, test_user):
        """Test that project names are indexed for search."""
        project = Project(
            name="Searchable Project Name",
            owner_id=test_user.id
        )
        test_db.add(project)
        test_db.commit()

        # This should be fast due to indexing
        found_project = test_db.query(Project).filter(
            Project.name == "Searchable Project Name"
        ).first()

        assert found_project is not None
        assert found_project.id == project.id

    @pytest.mark.unit
    def test_project_default_metadata(self, test_db, test_user):
        """Test default metadata dictionary."""
        project = Project(
            name="Default Metadata Project",
            owner_id=test_user.id
        )
        test_db.add(project)
        test_db.commit()
        test_db.refresh(project)

        assert project.metadata == {}
        assert isinstance(project.metadata, dict)

    @pytest.mark.unit
    def test_project_long_name(self, test_db, test_user):
        """Test project with maximum length name."""
        long_name = "A" * 200  # Maximum length
        
        project = Project(
            name=long_name,
            owner_id=test_user.id
        )
        test_db.add(project)
        test_db.commit()
        test_db.refresh(project)

        assert project.name == long_name
        assert len(project.name) == 200